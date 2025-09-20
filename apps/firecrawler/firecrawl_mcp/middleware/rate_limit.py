"""
Rate limiting middleware following Firecrawl API patterns for the MCP server.

This module provides rate limiting middleware that follows the same patterns used
in the Firecrawl API, with support for different rate limits per operation type
and client identification.
"""

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from ..core.config import MCPConfig

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting rules."""

    # Requests per minute limits
    scrape_per_minute: int = 100
    crawl_per_minute: int = 15
    search_per_minute: int = 100
    extract_per_minute: int = 100
    map_per_minute: int = 100
    batch_per_minute: int = 50
    vector_search_per_minute: int = 200

    # Requests per hour limits
    scrape_per_hour: int = 1000
    crawl_per_hour: int = 100
    search_per_hour: int = 1000
    extract_per_hour: int = 500
    map_per_hour: int = 500
    batch_per_hour: int = 200
    vector_search_per_hour: int = 2000

    # Global limits
    global_per_minute: int = 500
    global_per_hour: int = 5000

    # Burst allowances
    burst_multiplier: float = 1.5

    @classmethod
    def from_config(cls, config: MCPConfig) -> "RateLimitConfig":
        """Create rate limit configuration from MCP config."""
        return cls(
            # Use config values if available, otherwise use defaults
            scrape_per_minute=getattr(config, 'rate_limit_scrape_per_minute', 100),
            global_per_minute=getattr(config, 'rate_limit_requests_per_minute', 500),
            global_per_hour=getattr(config, 'rate_limit_requests_per_hour', 5000),
            burst_multiplier=getattr(config, 'rate_limit_burst_multiplier', 1.5)
        )


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            bool: True if tokens were consumed, False if not available
        """
        now = time.time()
        time_passed = now - self.last_refill

        # Add tokens based on time passed
        tokens_to_add = time_passed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

        # Try to consume tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def time_until_tokens(self, tokens: int = 1) -> float:
        """
        Calculate time until specified tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            float: Time in seconds until tokens are available
        """
        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


@dataclass
class SlidingWindow:
    """Sliding window counter for rate limiting."""

    capacity: int
    window_seconds: int
    timestamps: deque = field(default_factory=deque)

    def add_request(self) -> bool:
        """
        Add a request to the sliding window.

        Returns:
            bool: True if request was allowed, False if rate limit exceeded
        """
        now = time.time()
        cutoff_time = now - self.window_seconds

        # Remove old timestamps
        while self.timestamps and self.timestamps[0] < cutoff_time:
            self.timestamps.popleft()

        # Check if we can add another request
        if len(self.timestamps) < self.capacity:
            self.timestamps.append(now)
            return True

        return False

    def time_until_available(self) -> float:
        """
        Calculate time until a slot becomes available.

        Returns:
            float: Time in seconds until a request can be made
        """
        if len(self.timestamps) < self.capacity:
            return 0.0

        # Time until oldest request expires
        oldest_timestamp = self.timestamps[0]
        return float((oldest_timestamp + self.window_seconds) - time.time())


class ClientIdentifier:
    """Utility for identifying clients for rate limiting."""

    @staticmethod
    def get_client_id(context: MiddlewareContext) -> str:
        """
        Extract client identifier from context.

        Args:
            context: Middleware context

        Returns:
            str: Client identifier
        """
        # Try to extract from various sources
        client_id = "default"

        # Check for FastMCP context with client info
        if hasattr(context, 'fastmcp_context') and context.fastmcp_context:
            fastmcp_ctx = context.fastmcp_context

            # Try to get client ID from context state
            if hasattr(fastmcp_ctx, 'get_state'):
                stored_client_id = fastmcp_ctx.get_state('client_id')
                if stored_client_id:
                    client_id = stored_client_id

            # Try to get from transport info
            if hasattr(fastmcp_ctx, 'transport_info'):
                transport_info = fastmcp_ctx.transport_info
                if isinstance(transport_info, dict):
                    # For HTTP transport, use remote address
                    if 'remote_addr' in transport_info:
                        client_id = f"ip_{transport_info['remote_addr']}"
                    # For other transports, use connection info
                    elif 'connection_id' in transport_info:
                        client_id = f"conn_{transport_info['connection_id']}"

        # Fallback to source information
        if client_id == "default" and hasattr(context, 'source'):
            client_id = f"source_{context.source}"

        return client_id

    @staticmethod
    def get_operation_type(context: MiddlewareContext) -> str:
        """
        Extract operation type from context.

        Args:
            context: Middleware context

        Returns:
            str: Operation type for rate limiting
        """
        method = (context.method or "").lower()

        # Map MCP methods to Firecrawl operation types
        if 'tool' in method and hasattr(context, 'message') and hasattr(context.message, 'name'):
            tool_name = context.message.name.lower()

            # Define operation mappings to reduce return statements
            operation_mappings = [
                (['scrape'], 'scrape'),
                (['batch'], 'batch'),
                (['crawl'], 'crawl'),
                (['search', 'firesearch'], 'search'),
                (['extract'], 'extract'),
                (['map'], 'map'),
                (['vector', 'firerag'], 'vector_search'),
            ]

            # Check for batch first (most specific)
            if 'batch' in tool_name:
                return 'batch'

            # Check other mappings
            for keywords, operation_type in operation_mappings:
                if any(keyword in tool_name for keyword in keywords):
                    return operation_type

        # Default mapping
        return 'general'


class RateLimitingMiddleware(Middleware):
    """
    Token bucket rate limiting middleware.

    Implements rate limiting using token bucket algorithm with configurable
    rates per operation type, following Firecrawl API patterns.
    """

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        client_identifier: Callable[[MiddlewareContext], str] | None = None,
        operation_identifier: Callable[[MiddlewareContext], str] | None = None,
        enable_burst: bool = True,
        global_rate_limit: bool = True
    ):
        """
        Initialize rate limiting middleware.

        Args:
            config: Rate limiting configuration
            client_identifier: Function to identify clients
            operation_identifier: Function to identify operation types
            enable_burst: Whether to allow burst requests
            global_rate_limit: Whether to enforce global rate limits
        """
        self.config = config or RateLimitConfig()
        self.client_identifier = client_identifier or ClientIdentifier.get_client_id
        self.operation_identifier = operation_identifier or ClientIdentifier.get_operation_type
        self.enable_burst = enable_burst
        self.global_rate_limit = global_rate_limit

        # Thread-safe storage for rate limiters
        self._lock = threading.Lock()
        self._client_buckets: dict[str, dict[str, TokenBucket]] = defaultdict(dict)
        self._global_buckets: dict[str, TokenBucket] = {}

        # Initialize global buckets
        self._initialize_global_buckets()

    def _initialize_global_buckets(self) -> None:
        """Initialize global rate limiting buckets."""
        # Global per-minute bucket
        self._global_buckets['minute'] = TokenBucket(
            capacity=self.config.global_per_minute,
            tokens=self.config.global_per_minute,
            refill_rate=self.config.global_per_minute / 60.0  # tokens per second
        )

        # Global per-hour bucket
        self._global_buckets['hour'] = TokenBucket(
            capacity=self.config.global_per_hour,
            tokens=self.config.global_per_hour,
            refill_rate=self.config.global_per_hour / 3600.0  # tokens per second
        )

    def _get_operation_limits(self, operation: str) -> dict[str, int]:
        """Get rate limits for an operation type."""
        limits = {
            'scrape': {
                'per_minute': self.config.scrape_per_minute,
                'per_hour': self.config.scrape_per_hour
            },
            'crawl': {
                'per_minute': self.config.crawl_per_minute,
                'per_hour': self.config.crawl_per_hour
            },
            'search': {
                'per_minute': self.config.search_per_minute,
                'per_hour': self.config.search_per_hour
            },
            'extract': {
                'per_minute': self.config.extract_per_minute,
                'per_hour': self.config.extract_per_hour
            },
            'map': {
                'per_minute': self.config.map_per_minute,
                'per_hour': self.config.map_per_hour
            },
            'batch': {
                'per_minute': self.config.batch_per_minute,
                'per_hour': self.config.batch_per_hour
            },
            'vector_search': {
                'per_minute': self.config.vector_search_per_minute,
                'per_hour': self.config.vector_search_per_hour
            }
        }

        # Default to general limits
        return limits.get(operation, {
            'per_minute': self.config.global_per_minute // 10,  # Conservative default
            'per_hour': self.config.global_per_hour // 10
        })

    def _get_client_bucket(self, client_id: str, operation: str, time_window: str) -> TokenBucket:
        """Get or create a token bucket for a client and operation."""
        bucket_key = f"{operation}_{time_window}"

        if bucket_key not in self._client_buckets[client_id]:
            limits = self._get_operation_limits(operation)

            if time_window == 'minute':
                capacity = limits['per_minute']
                refill_rate = capacity / 60.0  # tokens per second
            elif time_window == 'hour':
                capacity = limits['per_hour']
                refill_rate = capacity / 3600.0  # tokens per second
            else:
                raise ValueError(f"Unknown time window: {time_window}")

            # Apply burst multiplier if enabled
            if self.enable_burst:
                capacity = int(capacity * self.config.burst_multiplier)

            self._client_buckets[client_id][bucket_key] = TokenBucket(
                capacity=capacity,
                tokens=capacity,
                refill_rate=refill_rate
            )

        return self._client_buckets[client_id][bucket_key]

    async def on_request(self, context: MiddlewareContext, call_next: Callable) -> Any:
        """Apply rate limiting to requests."""
        if not self.config:
            return await call_next(context)

        # Identify client and operation
        client_id = self.client_identifier(context)
        operation = self.operation_identifier(context)

        with self._lock:
            # Check global rate limits first
            if self.global_rate_limit:
                global_minute_bucket = self._global_buckets['minute']
                global_hour_bucket = self._global_buckets['hour']

                if not global_minute_bucket.consume():
                    wait_time = global_minute_bucket.time_until_tokens()
                    raise ToolError(f"Global rate limit exceeded (per minute). Retry in {wait_time:.1f}s")

                if not global_hour_bucket.consume():
                    wait_time = global_hour_bucket.time_until_tokens()
                    raise ToolError(f"Global rate limit exceeded (per hour). Retry in {wait_time:.1f}s")

            # Check client-specific rate limits
            minute_bucket = self._get_client_bucket(client_id, operation, 'minute')
            hour_bucket = self._get_client_bucket(client_id, operation, 'hour')

            if not minute_bucket.consume():
                wait_time = minute_bucket.time_until_tokens()
                raise ToolError(f"Rate limit exceeded for {operation} operations (per minute). Retry in {wait_time:.1f}s")

            if not hour_bucket.consume():
                wait_time = hour_bucket.time_until_tokens()
                raise ToolError(f"Rate limit exceeded for {operation} operations (per hour). Retry in {wait_time:.1f}s")

        # Continue with request processing
        return await call_next(context)

    def get_rate_limit_status(self, client_id: str | None = None) -> dict[str, Any]:
        """
        Get current rate limit status.

        Args:
            client_id: Specific client ID to check, or None for global status

        Returns:
            Dict containing rate limit status information
        """
        with self._lock:
            status = {
                "timestamp": datetime.now(UTC).isoformat(),
                "global": {
                    "minute": {
                        "limit": int(self._global_buckets['minute'].capacity),
                        "remaining": int(self._global_buckets['minute'].tokens),
                        "reset_time": int(time.time() + 60)
                    },
                    "hour": {
                        "limit": int(self._global_buckets['hour'].capacity),
                        "remaining": int(self._global_buckets['hour'].tokens),
                        "reset_time": int(time.time() + 3600)
                    }
                }
            }

            if client_id and client_id in self._client_buckets:
                client_status: dict[str, dict[str, dict[str, int]]] = {}
                for bucket_key, bucket in self._client_buckets[client_id].items():
                    operation, time_window = bucket_key.rsplit('_', 1)

                    if operation not in client_status:
                        client_status[operation] = {}

                    reset_seconds = 60 if time_window == 'minute' else 3600
                    client_status[operation][time_window] = {
                        "limit": int(bucket.capacity),
                        "remaining": int(bucket.tokens),
                        "reset_time": int(time.time() + reset_seconds)
                    }

                status["client"] = client_status

            return status

    def reset_client_limits(self, client_id: str) -> None:
        """Reset rate limits for a specific client."""
        with self._lock:
            if client_id in self._client_buckets:
                del self._client_buckets[client_id]


class SlidingWindowRateLimitingMiddleware(Middleware):
    """
    Sliding window rate limiting middleware.

    Implements precise time-based rate limiting using sliding windows,
    providing more accurate rate limiting than token buckets but with
    higher memory usage.
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_minutes: int = 1,
        client_identifier: Callable[[MiddlewareContext], str] | None = None,
        operation_identifier: Callable[[MiddlewareContext], str] | None = None,
        per_operation_limits: dict[str, dict[str, int]] | None = None
    ):
        """
        Initialize sliding window rate limiting middleware.

        Args:
            max_requests: Maximum requests per window
            window_minutes: Window size in minutes
            client_identifier: Function to identify clients
            operation_identifier: Function to identify operations
            per_operation_limits: Custom limits per operation type
        """
        self.max_requests = max_requests
        self.window_seconds = window_minutes * 60
        self.client_identifier = client_identifier or ClientIdentifier.get_client_id
        self.operation_identifier = operation_identifier or ClientIdentifier.get_operation_type
        self.per_operation_limits = per_operation_limits or {}

        # Thread-safe storage
        self._lock = threading.Lock()
        self._client_windows: dict[str, dict[str, SlidingWindow]] = defaultdict(dict)

    def _get_window(self, client_id: str, operation: str) -> SlidingWindow:
        """Get or create sliding window for client and operation."""
        window_key = f"{operation}_{self.window_seconds}"

        if window_key not in self._client_windows[client_id]:
            # Get operation-specific limits or use defaults
            limits = self.per_operation_limits.get(operation, {})
            capacity = limits.get('max_requests', self.max_requests)
            window_seconds = limits.get('window_seconds', self.window_seconds)

            self._client_windows[client_id][window_key] = SlidingWindow(
                capacity=capacity,
                window_seconds=window_seconds
            )

        return self._client_windows[client_id][window_key]

    async def on_request(self, context: MiddlewareContext, call_next: Callable) -> Any:
        """Apply sliding window rate limiting."""
        client_id = self.client_identifier(context)
        operation = self.operation_identifier(context)

        with self._lock:
            window = self._get_window(client_id, operation)

            if not window.add_request():
                wait_time = window.time_until_available()
                raise ToolError(f"Rate limit exceeded for {operation} operations. Retry in {wait_time:.1f}s")

        return await call_next(context)
