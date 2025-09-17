"""
Performance metrics and timing middleware for the Firecrawler MCP server.

This module provides comprehensive timing middleware that tracks performance metrics
for all MCP operations, following FastMCP patterns with integration to Firecrawl's
performance monitoring requirements.
"""

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

from ..core.config import MCPConfig

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance measurement."""

    operation: str
    method: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error_type: str | None = None
    error_message: str | None = None
    client_info: str | None = None

    @property
    def timestamp(self) -> str:
        """ISO timestamp of when the operation started."""
        return datetime.fromtimestamp(self.start_time, UTC).isoformat()


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""

    operation: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    recent_durations: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_duration_ms(self) -> float:
        """Average duration in milliseconds."""
        if self.total_requests == 0:
            return 0.0
        return self.total_duration_ms / self.total_requests

    @property
    def p95_duration_ms(self) -> float:
        """95th percentile duration in milliseconds."""
        if not self.recent_durations:
            return 0.0
        sorted_durations = sorted(self.recent_durations)
        index = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(index, len(sorted_durations) - 1)]

    def add_measurement(self, duration_ms: float, success: bool) -> None:
        """Add a new measurement to the statistics."""
        self.total_requests += 1
        self.total_duration_ms += duration_ms
        self.recent_durations.append(duration_ms)

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation": self.operation,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(self.success_rate, 2),
            "average_duration_ms": round(self.average_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2),
            "max_duration_ms": round(self.max_duration_ms, 2),
            "p95_duration_ms": round(self.p95_duration_ms, 2)
        }


class TimingMiddleware(Middleware):
    """
    Basic timing middleware that logs request durations.
    
    Provides simple timing information for all MCP requests with
    configurable logging and basic statistics tracking.
    """

    def __init__(
        self,
        logger_name: str | None = None,
        log_slow_requests: bool = True,
        slow_request_threshold_ms: float = 1000.0,
        enable_stats: bool = True
    ):
        """
        Initialize timing middleware.
        
        Args:
            logger_name: Custom logger name, defaults to module logger
            log_slow_requests: Whether to log requests that exceed threshold
            slow_request_threshold_ms: Threshold for slow request logging
            enable_stats: Whether to collect basic statistics
        """
        self.logger = logging.getLogger(logger_name or __name__)
        self.log_slow_requests = log_slow_requests
        self.slow_request_threshold_ms = slow_request_threshold_ms
        self.enable_stats = enable_stats

        # Thread-safe statistics storage
        self._stats_lock = threading.Lock()
        self._operation_stats: dict[str, PerformanceStats] = defaultdict(
            lambda: PerformanceStats("")
        )

        # Recent metrics for debugging (limited size)
        self._recent_metrics: deque = deque(maxlen=1000)

    async def on_request(self, context: MiddlewareContext, call_next):
        """
        FastMCP hook for timing all requests.
        
        Args:
            context: FastMCP middleware context
            call_next: Function to continue middleware chain
            
        Returns:
            The result of the request
        """
        start_time = time.perf_counter()
        error_info = None
        operation = context.method

        try:
            result = await call_next(context)
            success = True
            return result

        except Exception as error:
            success = False
            error_info = {
                "type": type(error).__name__,
                "message": str(error)
            }
            raise

        finally:
            # Calculate timing
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            # Create performance metric
            metric = PerformanceMetric(
                operation=operation,
                method=context.method,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                success=success,
                error_type=error_info["type"] if error_info else None,
                error_message=error_info["message"] if error_info else None,
                client_info=context.source
            )

            # Log the timing
            await self._log_timing(context, metric)

            # Update statistics
            if self.enable_stats:
                self._update_stats(metric)

            # Store recent metric
            self._recent_metrics.append(metric)

    # Decorator pattern removed - use FastMCP hooks instead

    async def _log_timing(self, context: MiddlewareContext, metric: PerformanceMetric) -> None:
        """Log timing information."""
        # Format log message
        status = "SUCCESS" if metric.success else "FAILED"
        log_msg = f"{metric.method} {status} in {metric.duration_ms:.2f}ms"

        # Add error information if applicable
        if not metric.success and metric.error_type:
            log_msg += f" ({metric.error_type})"

        # Log with appropriate level using FastMCP context
        if context.fastmcp_context:
            if not metric.success:
                await context.fastmcp_context.error(log_msg)
            elif self.log_slow_requests and metric.duration_ms > self.slow_request_threshold_ms:
                await context.fastmcp_context.warning(f"SLOW REQUEST: {log_msg}")
            else:
                await context.fastmcp_context.debug(log_msg)

    def _update_stats(self, metric: PerformanceMetric) -> None:
        """Update operation statistics."""
        with self._stats_lock:
            stats = self._operation_stats[metric.operation]
            if not stats.operation:  # Initialize operation name
                stats.operation = metric.operation
            stats.add_measurement(metric.duration_ms, metric.success)

    def get_stats(self) -> dict[str, Any]:
        """Get current performance statistics."""
        with self._stats_lock:
            return {
                operation: stats.to_dict()
                for operation, stats in self._operation_stats.items()
            }

    def get_recent_metrics(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent performance metrics."""
        recent = list(self._recent_metrics)
        if limit:
            recent = recent[-limit:]

        return [
            {
                "operation": metric.operation,
                "method": metric.method,
                "duration_ms": round(metric.duration_ms, 2),
                "success": metric.success,
                "timestamp": metric.timestamp,
                "error_type": metric.error_type,
                "client_info": metric.client_info
            }
            for metric in recent
        ]

    def reset_stats(self) -> None:
        """Reset all performance statistics."""
        with self._stats_lock:
            self._operation_stats.clear()
            self._recent_metrics.clear()


class DetailedTimingMiddleware(TimingMiddleware):
    """
    Detailed timing middleware with operation-specific tracking.
    
    Extends basic timing with granular timing for specific operation types
    and detailed statistics tracking.
    """

    def __init__(
        self,
        logger_name: str | None = None,
        log_slow_requests: bool = True,
        slow_request_threshold_ms: float = 1000.0,
        enable_stats: bool = True,
        track_tool_performance: bool = True,
        track_resource_performance: bool = True,
        track_prompt_performance: bool = True
    ):
        """
        Initialize detailed timing middleware.
        
        Args:
            logger_name: Custom logger name
            log_slow_requests: Whether to log slow requests
            slow_request_threshold_ms: Threshold for slow request logging
            enable_stats: Whether to collect statistics
            track_tool_performance: Whether to track tool execution timing
            track_resource_performance: Whether to track resource access timing
            track_prompt_performance: Whether to track prompt timing
        """
        super().__init__(logger_name, log_slow_requests, slow_request_threshold_ms, enable_stats)

        self.track_tool_performance = track_tool_performance
        self.track_resource_performance = track_resource_performance
        self.track_prompt_performance = track_prompt_performance

        # Detailed operation tracking
        self._tool_stats: dict[str, PerformanceStats] = defaultdict(
            lambda: PerformanceStats("")
        )
        self._resource_stats: dict[str, PerformanceStats] = defaultdict(
            lambda: PerformanceStats("")
        )
        self._prompt_stats: dict[str, PerformanceStats] = defaultdict(
            lambda: PerformanceStats("")
        )

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """FastMCP hook for timing tool calls."""
        if not self.track_tool_performance:
            return await call_next(context)

        start_time = time.perf_counter()
        tool_name = context.message.name if hasattr(context.message, 'name') else 'unknown'

        try:
            result = await call_next(context)
            success = True
            return result

        except Exception:
            success = False
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log tool-specific timing
            status = "SUCCESS" if success else "FAILED"
            if context.fastmcp_context:
                await context.fastmcp_context.debug(f"Tool '{tool_name}' {status} in {duration_ms:.2f}ms")

            # Update tool statistics
            if self.enable_stats:
                with self._stats_lock:
                    stats = self._tool_stats[tool_name]
                    if not stats.operation:
                        stats.operation = f"tool:{tool_name}"
                    stats.add_measurement(duration_ms, success)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """FastMCP hook for timing resource reads."""
        if not self.track_resource_performance:
            return await call_next(context)

        start_time = time.perf_counter()
        resource_uri = context.message.uri if hasattr(context.message, 'uri') else 'unknown'

        try:
            result = await call_next(context)
            success = True
            return result

        except Exception:
            success = False
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log resource-specific timing
            status = "SUCCESS" if success else "FAILED"
            if context.fastmcp_context:
                await context.fastmcp_context.debug(f"Resource '{resource_uri}' {status} in {duration_ms:.2f}ms")

            # Update resource statistics
            if self.enable_stats:
                with self._stats_lock:
                    stats = self._resource_stats[resource_uri]
                    if not stats.operation:
                        stats.operation = f"resource:{resource_uri}"
                    stats.add_measurement(duration_ms, success)

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """FastMCP hook for timing prompt requests."""
        if not self.track_prompt_performance:
            return await call_next(context)

        start_time = time.perf_counter()
        prompt_name = context.message.name if hasattr(context.message, 'name') else 'unknown'

        try:
            result = await call_next(context)
            success = True
            return result

        except Exception:
            success = False
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log prompt-specific timing
            status = "SUCCESS" if success else "FAILED"
            if context.fastmcp_context:
                await context.fastmcp_context.debug(f"Prompt '{prompt_name}' {status} in {duration_ms:.2f}ms")

            # Update prompt statistics
            if self.enable_stats:
                with self._stats_lock:
                    stats = self._prompt_stats[prompt_name]
                    if not stats.operation:
                        stats.operation = f"prompt:{prompt_name}"
                    stats.add_measurement(duration_ms, success)

    def get_detailed_stats(self) -> dict[str, Any]:
        """Get detailed performance statistics including tools, resources, and prompts."""
        with self._stats_lock:
            return {
                "general": self.get_stats(),
                "tools": {
                    name: stats.to_dict()
                    for name, stats in self._tool_stats.items()
                },
                "resources": {
                    uri: stats.to_dict()
                    for uri, stats in self._resource_stats.items()
                },
                "prompts": {
                    name: stats.to_dict()
                    for name, stats in self._prompt_stats.items()
                }
            }

    def reset_stats(self) -> None:
        """Reset all performance statistics including detailed stats."""
        super().reset_stats()
        with self._stats_lock:
            self._tool_stats.clear()
            self._resource_stats.clear()
            self._prompt_stats.clear()


# Factory function removed - use direct instantiation with FastMCP
# Example:
# mcp.add_middleware(TimingMiddleware(log_slow_requests=True, enable_stats=True))
# mcp.add_middleware(DetailedTimingMiddleware(track_tool_performance=True))
