"""
Rate limiting behavior tests for the Firecrawler MCP server.

This module tests the rate limiting middleware components, including token bucket
algorithms, sliding window rate limiting, client identification, and integration
with Firecrawl API patterns using FastMCP in-memory testing patterns.
"""

import asyncio
import time
from typing import Any
from unittest.mock import Mock

import pytest

from firecrawl_mcp.core.config import MCPConfig
from firecrawl_mcp.core.exceptions import MCPRateLimitError
from firecrawl_mcp.middleware.rate_limit import (
    ClientIdentifier,
    RateLimitConfig,
    RateLimitingMiddleware,
    SlidingWindow,
    SlidingWindowRateLimitingMiddleware,
    TokenBucket,
    create_rate_limiting_middleware,
)


class MockMiddlewareContext:
    """Mock middleware context for testing."""

    def __init__(
        self,
        method: str = "test_method",
        source: str = "test_client",
        message: Any = None,
        fastmcp_context: Any = None,
        **kwargs
    ):
        self.method = method
        self.source = source
        self.message = message
        self.fastmcp_context = fastmcp_context
        # Allow additional attributes to be set
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestRateLimitConfig:
    """Test RateLimitConfig functionality."""

    def test_default_config(self):
        """Test default rate limit configuration."""
        config = RateLimitConfig()

        assert config.scrape_per_minute == 100
        assert config.crawl_per_minute == 15
        assert config.search_per_minute == 100
        assert config.extract_per_minute == 100
        assert config.map_per_minute == 100
        assert config.batch_per_minute == 50
        assert config.vector_search_per_minute == 200

        assert config.global_per_minute == 500
        assert config.global_per_hour == 5000
        assert config.burst_multiplier == 1.5

    def test_from_config(self):
        """Test creating rate limit config from MCP config."""
        mcp_config = MCPConfig()
        mcp_config.rate_limit_requests_per_minute = 100
        mcp_config.rate_limit_requests_per_hour = 1000

        rate_config = RateLimitConfig.from_config(mcp_config)

        assert rate_config.global_per_minute == 100
        assert rate_config.global_per_hour == 1000


class TestTokenBucket:
    """Test TokenBucket algorithm."""

    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(
            capacity=10.0,
            tokens=10.0,
            refill_rate=1.0  # 1 token per second
        )

        assert bucket.capacity == 10.0
        assert bucket.tokens == 10.0
        assert bucket.refill_rate == 1.0

    def test_consume_tokens_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10.0, tokens=10.0, refill_rate=1.0)

        # Should be able to consume tokens
        assert bucket.consume(5) is True
        assert bucket.tokens == 5.0

        assert bucket.consume(3) is True
        assert bucket.tokens == 2.0

    def test_consume_tokens_failure(self):
        """Test token consumption failure when insufficient tokens."""
        bucket = TokenBucket(capacity=10.0, tokens=3.0, refill_rate=1.0)

        # Should not be able to consume more tokens than available
        assert bucket.consume(5) is False
        assert bucket.tokens == 3.0  # Should remain unchanged

    def test_token_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10.0, tokens=5.0, refill_rate=2.0)  # 2 tokens per second

        # Simulate time passing
        original_time = bucket.last_refill
        bucket.last_refill = original_time - 1.0  # 1 second ago

        # Consuming should trigger refill
        success = bucket.consume(1)

        assert success is True
        # Should have refilled 2 tokens (2.0 rate * 1 second) - 1 consumed = 6 tokens
        assert bucket.tokens == 6.0

    def test_token_refill_capacity_limit(self):
        """Test that token refill respects capacity limit."""
        bucket = TokenBucket(capacity=10.0, tokens=8.0, refill_rate=5.0)

        # Simulate time passing
        bucket.last_refill = bucket.last_refill - 1.0  # 1 second ago

        # Should refill to capacity, not beyond
        bucket.consume(0)  # Trigger refill
        assert bucket.tokens == 10.0  # Capped at capacity

    def test_time_until_tokens(self):
        """Test calculating time until tokens are available."""
        bucket = TokenBucket(capacity=10.0, tokens=2.0, refill_rate=1.0)

        # Need 5 tokens, have 2, need 3 more at 1 per second = 3 seconds
        time_needed = bucket.time_until_tokens(5)
        assert time_needed == 3.0

        # Already have enough tokens
        time_needed = bucket.time_until_tokens(1)
        assert time_needed == 0.0


class TestSlidingWindow:
    """Test SlidingWindow algorithm."""

    def test_sliding_window_initialization(self):
        """Test sliding window initialization."""
        window = SlidingWindow(capacity=5, window_seconds=60)

        assert window.capacity == 5
        assert window.window_seconds == 60
        assert len(window.timestamps) == 0

    def test_add_request_success(self):
        """Test adding requests within capacity."""
        window = SlidingWindow(capacity=3, window_seconds=60)

        assert window.add_request() is True
        assert window.add_request() is True
        assert window.add_request() is True
        assert len(window.timestamps) == 3

    def test_add_request_failure(self):
        """Test adding requests beyond capacity."""
        window = SlidingWindow(capacity=2, window_seconds=60)

        assert window.add_request() is True
        assert window.add_request() is True
        assert window.add_request() is False  # Should fail
        assert len(window.timestamps) == 2

    def test_window_expiration(self):
        """Test that old timestamps are removed."""
        window = SlidingWindow(capacity=3, window_seconds=1)  # 1 second window

        # Add some requests
        assert window.add_request() is True
        assert window.add_request() is True

        # Simulate time passing
        current_time = time.time()
        window.timestamps[0] = current_time - 2.0  # 2 seconds ago (expired)

        # Adding another request should clean up expired timestamp
        assert window.add_request() is True
        assert len(window.timestamps) == 2  # One expired, one new

    def test_time_until_available(self):
        """Test calculating time until slot becomes available."""
        window = SlidingWindow(capacity=2, window_seconds=10)

        # Fill the window
        current_time = time.time()
        window.timestamps.append(current_time - 5)  # 5 seconds ago
        window.timestamps.append(current_time - 3)  # 3 seconds ago

        # Should need to wait until oldest expires (5 more seconds)
        time_needed = window.time_until_available()
        assert 4.9 <= time_needed <= 5.1  # Allow for small timing variations


class TestClientIdentifier:
    """Test ClientIdentifier functionality."""

    def test_default_client_id(self):
        """Test default client ID extraction."""
        context = MockMiddlewareContext(source="test_source")

        client_id = ClientIdentifier.get_client_id(context)
        assert client_id == "source_test_source"

    def test_fastmcp_context_client_id(self):
        """Test client ID extraction from FastMCP context."""
        mock_fastmcp_context = Mock()
        mock_fastmcp_context.get_state = Mock(return_value="custom_client_123")

        context = MockMiddlewareContext(fastmcp_context=mock_fastmcp_context)

        client_id = ClientIdentifier.get_client_id(context)
        assert client_id == "custom_client_123"

    def test_transport_info_client_id(self):
        """Test client ID extraction from transport info."""
        mock_fastmcp_context = Mock()
        mock_fastmcp_context.get_state = Mock(return_value=None)
        mock_fastmcp_context.transport_info = {"remote_addr": "192.168.1.100"}

        context = MockMiddlewareContext(fastmcp_context=mock_fastmcp_context)

        client_id = ClientIdentifier.get_client_id(context)
        assert client_id == "ip_192.168.1.100"

    def test_operation_type_extraction(self):
        """Test operation type extraction from method."""
        # Test tool methods
        mock_message = Mock()
        mock_message.name = "scrape_url"
        context = MockMiddlewareContext(method="tools/call", message=mock_message)

        op_type = ClientIdentifier.get_operation_type(context)
        assert op_type == "scrape"

        # Test batch operations
        mock_message.name = "batch_scrape"
        op_type = ClientIdentifier.get_operation_type(context)
        assert op_type == "batch"

        # Test search operations
        mock_message.name = "firesearch"
        op_type = ClientIdentifier.get_operation_type(context)
        assert op_type == "search"

        # Test vector operations
        mock_message.name = "firerag"
        op_type = ClientIdentifier.get_operation_type(context)
        assert op_type == "vector_search"

    def test_general_operation_fallback(self):
        """Test fallback to general operation type."""
        context = MockMiddlewareContext(method="unknown_method")

        op_type = ClientIdentifier.get_operation_type(context)
        assert op_type == "general"


class TestRateLimitingMiddleware:
    """Test RateLimitingMiddleware functionality."""

    @pytest.fixture
    def rate_config(self):
        """Create a test rate limit configuration."""
        return RateLimitConfig(
            scrape_per_minute=10,
            scrape_per_hour=100,
            global_per_minute=50,
            global_per_hour=500,
            burst_multiplier=1.0  # Disable burst for predictable testing
        )

    @pytest.fixture
    def rate_limiting_middleware(self, rate_config):
        """Create a rate limiting middleware instance."""
        return RateLimitingMiddleware(
            config=rate_config,
            enable_burst=False,
            global_rate_limit=True
        )

    async def test_successful_request_within_limits(self, rate_limiting_middleware):
        """Test successful request processing within rate limits."""
        mock_message = Mock()
        mock_message.name = "scrape_url"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        result = await rate_limiting_middleware.on_request(context, mock_next)
        assert result == {"result": "success"}

    async def test_rate_limit_exceeded_per_minute(self, rate_limiting_middleware):
        """Test rate limit exceeded for per-minute limits."""
        mock_message = Mock()
        mock_message.name = "scrape_url"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        # Make requests up to the limit
        for _ in range(10):  # scrape_per_minute = 10
            await rate_limiting_middleware.on_request(context, mock_next)

        # Next request should fail
        with pytest.raises(MCPRateLimitError) as exc_info:
            await rate_limiting_middleware.on_request(context, mock_next)

        error = exc_info.value
        assert "Rate limit exceeded for scrape operations (per minute)" in str(error)
        assert error.rate_limit_type == "scrape_minute"

    async def test_global_rate_limit_exceeded(self, rate_limiting_middleware):
        """Test global rate limit exceeded."""
        # Create different operations to hit global limit
        contexts = []
        for i in range(5):  # Create different tools
            mock_message = Mock()
            mock_message.name = f"tool_{i}"
            contexts.append(MockMiddlewareContext(
                method="tools/call",
                message=mock_message,
                source=f"client_{i}"
            ))

        async def mock_next(ctx):
            return {"result": "success"}

        # Exhaust global per-minute limit (50)
        for _ in range(50):
            for context in contexts:
                await rate_limiting_middleware.on_request(context, mock_next)
                break  # Just use first context repeatedly

        # Next request should fail with global rate limit
        with pytest.raises(MCPRateLimitError) as exc_info:
            await rate_limiting_middleware.on_request(contexts[0], mock_next)

        error = exc_info.value
        assert "Global rate limit exceeded" in str(error)

    async def test_different_clients_separate_limits(self, rate_limiting_middleware):
        """Test that different clients have separate rate limits."""
        mock_message = Mock()
        mock_message.name = "scrape_url"

        client1_context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="client_1"
        )
        client2_context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="client_2"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        # Exhaust limit for client 1
        for _ in range(10):
            await rate_limiting_middleware.on_request(client1_context, mock_next)

        # Client 1 should be rate limited
        with pytest.raises(MCPRateLimitError):
            await rate_limiting_middleware.on_request(client1_context, mock_next)

        # Client 2 should still work
        result = await rate_limiting_middleware.on_request(client2_context, mock_next)
        assert result == {"result": "success"}

    async def test_different_operations_separate_limits(self, rate_limiting_middleware):
        """Test that different operations have separate rate limits."""
        scrape_message = Mock()
        scrape_message.name = "scrape_url"
        search_message = Mock()
        search_message.name = "firesearch"

        scrape_context = MockMiddlewareContext(
            method="tools/call",
            message=scrape_message,
            source="test_client"
        )
        search_context = MockMiddlewareContext(
            method="tools/call",
            message=search_message,
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        # Exhaust scrape limit
        for _ in range(10):
            await rate_limiting_middleware.on_request(scrape_context, mock_next)

        # Scrape should be rate limited
        with pytest.raises(MCPRateLimitError):
            await rate_limiting_middleware.on_request(scrape_context, mock_next)

        # Search should still work (different operation type)
        result = await rate_limiting_middleware.on_request(search_context, mock_next)
        assert result == {"result": "success"}

    def test_get_rate_limit_status(self, rate_limiting_middleware):
        """Test getting rate limit status."""
        status = rate_limiting_middleware.get_rate_limit_status()

        assert "timestamp" in status
        assert "global" in status
        assert "minute" in status["global"]
        assert "hour" in status["global"]

        global_minute = status["global"]["minute"]
        assert global_minute["limit"] == 50
        assert global_minute["remaining"] == 50
        assert "reset_time" in global_minute

    def test_get_client_rate_limit_status(self, rate_limiting_middleware):
        """Test getting rate limit status for specific client."""
        # First make a request to create client buckets
        async def setup_client():
            mock_message = Mock()
            mock_message.name = "scrape_url"
            context = MockMiddlewareContext(
                method="tools/call",
                message=mock_message,
                source="test_client"
            )

            async def mock_next(ctx):
                return "success"

            await rate_limiting_middleware.on_request(context, mock_next)

        asyncio.run(setup_client())

        status = rate_limiting_middleware.get_rate_limit_status("test_client")

        assert "client" in status
        client_status = status["client"]
        assert "scrape" in client_status
        assert "minute" in client_status["scrape"]
        assert "hour" in client_status["scrape"]

    def test_reset_client_limits(self, rate_limiting_middleware):
        """Test resetting rate limits for a specific client."""
        # Setup client buckets first
        async def setup_and_reset():
            mock_message = Mock()
            mock_message.name = "scrape_url"
            context = MockMiddlewareContext(
                method="tools/call",
                message=mock_message,
                source="test_client"
            )

            async def mock_next(ctx):
                return "success"

            # Use some rate limit
            await rate_limiting_middleware.on_request(context, mock_next)

            # Reset client limits
            rate_limiting_middleware.reset_client_limits("test_client")

            # Should be able to make requests again
            for _ in range(10):
                await rate_limiting_middleware.on_request(context, mock_next)

        # This should not raise any exceptions
        asyncio.run(setup_and_reset())


class TestSlidingWindowRateLimitingMiddleware:
    """Test SlidingWindowRateLimitingMiddleware functionality."""

    @pytest.fixture
    def sliding_middleware(self):
        """Create a sliding window rate limiting middleware."""
        return SlidingWindowRateLimitingMiddleware(
            max_requests=5,
            window_minutes=1,
            per_operation_limits={
                "scrape": {"max_requests": 3, "window_seconds": 60}
            }
        )

    async def test_sliding_window_within_limits(self, sliding_middleware):
        """Test requests within sliding window limits."""
        mock_message = Mock()
        mock_message.name = "general_tool"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        # Should be able to make requests up to limit
        for _ in range(5):
            result = await sliding_middleware.on_request(context, mock_next)
            assert result == {"result": "success"}

    async def test_sliding_window_exceeded(self, sliding_middleware):
        """Test sliding window rate limit exceeded."""
        mock_message = Mock()
        mock_message.name = "general_tool"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        # Exhaust the limit
        for _ in range(5):
            await sliding_middleware.on_request(context, mock_next)

        # Next request should fail
        with pytest.raises(MCPRateLimitError) as exc_info:
            await sliding_middleware.on_request(context, mock_next)

        error = exc_info.value
        assert "Rate limit exceeded for general operations" in str(error)
        assert error.rate_limit_type == "general_sliding"

    async def test_operation_specific_limits(self, sliding_middleware):
        """Test operation-specific sliding window limits."""
        mock_message = Mock()
        mock_message.name = "scrape_url"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        # Should be able to make 3 scrape requests (operation-specific limit)
        for _ in range(3):
            result = await sliding_middleware.on_request(context, mock_next)
            assert result == {"result": "success"}

        # 4th request should fail
        with pytest.raises(MCPRateLimitError):
            await sliding_middleware.on_request(context, mock_next)


class TestRateLimitingFactory:
    """Test rate limiting middleware factory functions."""

    def test_create_rate_limiting_enabled(self):
        """Test creating rate limiting middleware when enabled."""
        config = MCPConfig()
        config.rate_limit_enabled = True
        config.rate_limit_requests_per_minute = 100
        config.rate_limit_requests_per_hour = 1000

        middleware = create_rate_limiting_middleware(config)

        assert isinstance(middleware, RateLimitingMiddleware)
        assert middleware.config.global_per_minute == 100
        assert middleware.config.global_per_hour == 1000
        assert middleware.enable_burst is True
        assert middleware.global_rate_limit is True

    def test_create_rate_limiting_disabled(self):
        """Test that no middleware is created when rate limiting is disabled."""
        config = MCPConfig()
        config.rate_limit_enabled = False

        middleware = create_rate_limiting_middleware(config)

        assert middleware is None


class TestRateLimitingIntegration:
    """Test rate limiting integration scenarios."""

    async def test_rate_limiting_with_token_refill(self):
        """Test rate limiting with token bucket refill over time."""
        config = RateLimitConfig(
            scrape_per_minute=60,  # 1 token per second
            global_per_minute=120,  # 2 tokens per second
            burst_multiplier=1.0
        )

        middleware = RateLimitingMiddleware(
            config=config,
            enable_burst=False,
            global_rate_limit=True
        )

        mock_message = Mock()
        mock_message.name = "scrape_url"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def mock_next(ctx):
            await asyncio.sleep(0.1)  # Small delay
            return {"result": "success"}

        # Use all tokens quickly
        for _ in range(60):
            await middleware.on_request(context, mock_next)

        # Should be rate limited now
        with pytest.raises(MCPRateLimitError):
            await middleware.on_request(context, mock_next)

        # Wait for token refill (1 second = 1 token)
        await asyncio.sleep(1.1)

        # Should be able to make one more request
        result = await middleware.on_request(context, mock_next)
        assert result == {"result": "success"}

    async def test_concurrent_rate_limiting(self):
        """Test rate limiting with concurrent requests."""
        config = RateLimitConfig(
            scrape_per_minute=10,
            global_per_minute=50,
            burst_multiplier=1.0
        )

        middleware = RateLimitingMiddleware(
            config=config,
            enable_burst=False,
            global_rate_limit=True
        )

        mock_message = Mock()
        mock_message.name = "scrape_url"

        async def make_request(client_id: str):
            context = MockMiddlewareContext(
                method="tools/call",
                message=mock_message,
                source=client_id
            )

            async def mock_next(ctx):
                return f"result_{client_id}"

            try:
                return await middleware.on_request(context, mock_next)
            except MCPRateLimitError:
                return "rate_limited"

        # Launch concurrent requests from different clients
        tasks = []
        for i in range(5):  # 5 clients
            for j in range(8):  # 8 requests each
                tasks.append(make_request(f"client_{i}"))

        results = await asyncio.gather(*tasks)

        # Some should succeed, some should be rate limited
        successful = [r for r in results if r != "rate_limited"]
        rate_limited = [r for r in results if r == "rate_limited"]

        assert len(successful) > 0
        assert len(rate_limited) > 0
        assert len(successful) + len(rate_limited) == 40

    def test_rate_limit_error_details(self):
        """Test that rate limit errors contain proper details."""
        config = RateLimitConfig(scrape_per_minute=1)
        middleware = RateLimitingMiddleware(config=config, enable_burst=False)

        mock_message = Mock()
        mock_message.name = "scrape_url"
        context = MockMiddlewareContext(
            method="tools/call",
            message=mock_message,
            source="test_client"
        )

        async def test_error():
            async def mock_next(ctx):
                return "success"

            # Use up the token
            await middleware.on_request(context, mock_next)

            # Next request should raise detailed error
            with pytest.raises(MCPRateLimitError) as exc_info:
                await middleware.on_request(context, mock_next)

            error = exc_info.value
            assert error.rate_limit_type == "scrape_minute"
            assert "reset_time" in error.details
            assert "current_usage" in error.details
            assert "limit" in error.details

        asyncio.run(test_error())
