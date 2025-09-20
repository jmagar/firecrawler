"""
Error processing and formatting tests for the Firecrawler MCP server.

This module tests the error handling middleware components, including error
transformation, retry logic, circuit breaker patterns, and error statistics
using FastMCP in-memory testing patterns.
"""

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    RequestTimeoutError,
    UnauthorizedError,
)

from firecrawl_mcp.core.exceptions import (
    MCPClientError,
    MCPError,
    MCPServerError,
    MCPTimeoutError,
    MCPValidationError,
)
from firecrawl_mcp.middleware.error_handling import (
    CircuitBreakerMiddleware,
    ErrorHandlingMiddleware,
    ErrorStatistics,
    RetryMiddleware,
)


class MockMiddlewareContext(MiddlewareContext[Any]):
    """Mock middleware context for testing."""

    def __init__(
        self,
        method: str = "test_method",
        source: str = "client",
        message: Any = None,
        **kwargs: Any
    ) -> None:
        mock_message = message or Mock()
        mock_fastmcp_context = Mock()
        # Set up async methods for fastmcp_context
        mock_fastmcp_context.info = AsyncMock()
        mock_fastmcp_context.warning = AsyncMock()
        mock_fastmcp_context.error = AsyncMock()

        # Initialize parent with required arguments
        super().__init__(
            message=mock_message,
            fastmcp_context=mock_fastmcp_context,
            source=source,  # type: ignore
            type="request",
            method=method
        )

        # Allow additional attributes to be set
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestErrorStatistics:
    """Test ErrorStatistics functionality."""

    def test_error_statistics_initialization(self) -> None:
        """Test error statistics initialization."""
        stats = ErrorStatistics()

        assert stats.total_errors == 0
        assert len(stats.errors_by_type) == 0
        assert len(stats.errors_by_operation) == 0
        assert len(stats.recent_errors) == 0
        assert stats.max_recent_errors == 100

    def test_add_error(self) -> None:
        """Test adding errors to statistics."""
        stats = ErrorStatistics()

        error = ValueError("Test error")
        context = {"tool": "test_tool", "client": "test_client"}

        stats.add_error(error, "test_operation", context)

        assert stats.total_errors == 1
        assert stats.errors_by_type["ValueError"] == 1
        assert stats.errors_by_operation["test_operation"] == 1
        assert len(stats.recent_errors) == 1

        recent_error = stats.recent_errors[0]
        assert recent_error["error_type"] == "ValueError"
        assert recent_error["operation"] == "test_operation"
        assert recent_error["message"] == "Test error"
        assert recent_error["context"] == context
        assert "timestamp" in recent_error

    def test_multiple_errors(self) -> None:
        """Test adding multiple errors of different types."""
        stats = ErrorStatistics()

        stats.add_error(ValueError("Error 1"), "operation_a")
        stats.add_error(ValueError("Error 2"), "operation_a")
        stats.add_error(TypeError("Error 3"), "operation_b")

        assert stats.total_errors == 3
        assert stats.errors_by_type["ValueError"] == 2
        assert stats.errors_by_type["TypeError"] == 1
        assert stats.errors_by_operation["operation_a"] == 2
        assert stats.errors_by_operation["operation_b"] == 1

    def test_recent_errors_limit(self) -> None:
        """Test that recent errors are limited in size."""
        stats = ErrorStatistics(max_recent_errors=3)

        # Add more errors than the limit
        for i in range(5):
            stats.add_error(ValueError(f"Error {i}"), "test_operation")

        assert stats.total_errors == 5
        assert len(stats.recent_errors) == 3  # Should be limited

        # Should contain the most recent errors
        messages = [err["message"] for err in stats.recent_errors]
        assert "Error 2" in messages
        assert "Error 3" in messages
        assert "Error 4" in messages
        assert "Error 0" not in messages
        assert "Error 1" not in messages

    def test_get_stats(self) -> None:
        """Test getting statistics summary."""
        stats = ErrorStatistics()

        stats.add_error(ValueError("Error 1"), "operation_a")
        stats.add_error(TypeError("Error 2"), "operation_b")

        summary = stats.get_stats()

        assert summary["total_errors"] == 2
        assert summary["errors_by_type"]["ValueError"] == 1
        assert summary["errors_by_type"]["TypeError"] == 1
        assert summary["errors_by_operation"]["operation_a"] == 1
        assert summary["errors_by_operation"]["operation_b"] == 1
        assert summary["recent_error_count"] == 2

    def test_get_recent_errors(self) -> None:
        """Test getting recent errors with optional limit."""
        stats = ErrorStatistics()

        for i in range(5):
            stats.add_error(ValueError(f"Error {i}"), "test_operation")

        # Get all recent errors
        all_recent = stats.get_recent_errors()
        assert len(all_recent) == 5

        # Get limited recent errors
        limited_recent = stats.get_recent_errors(limit=3)
        assert len(limited_recent) == 3

        # Should get the most recent ones
        messages = [err["message"] for err in limited_recent]
        assert "Error 2" in messages
        assert "Error 3" in messages
        assert "Error 4" in messages


class TestErrorHandlingMiddleware:
    """Test ErrorHandlingMiddleware functionality."""

    @pytest.fixture
    def error_middleware(self) -> ErrorHandlingMiddleware:
        """Create an error handling middleware instance."""
        return ErrorHandlingMiddleware(
            include_traceback=True,
            transform_errors=True,
            mask_sensitive_data=True,
            enable_statistics=True
        )

    @pytest.fixture
    def minimal_error_middleware(self) -> ErrorHandlingMiddleware:
        """Create a minimal error handling middleware."""
        return ErrorHandlingMiddleware(
            include_traceback=False,
            transform_errors=False,
            enable_statistics=False
        )

    async def test_successful_request_passthrough(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test that successful requests pass through unchanged."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> dict[str, str]:
            return {"result": "success"}

        result = await error_middleware.on_message(context, mock_next)
        assert result == {"result": "success"}

    async def test_error_transformation_firecrawl_to_mcp(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test transformation of Firecrawl errors to MCP errors."""
        context = MockMiddlewareContext(method="test_scrape")

        async def mock_next(_ctx: Any) -> None:
            raise BadRequestError("Invalid URL format", 400)

        with pytest.raises(ToolError) as exc_info:
            await error_middleware.on_message(context, mock_next)

        error = exc_info.value
        assert "Invalid URL format" in str(error)

    async def test_error_transformation_unauthorized(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test transformation of unauthorized errors."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise UnauthorizedError("Invalid API key", 401)

        with pytest.raises(ToolError) as exc_info:
            await error_middleware.on_message(context, mock_next)

        error = exc_info.value
        assert "Invalid API key" in str(error)

    async def test_error_transformation_timeout(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test transformation of timeout errors."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise RequestTimeoutError("Request timed out", 408)

        with pytest.raises(ToolError) as exc_info:
            await error_middleware.on_message(context, mock_next)

        error = exc_info.value
        assert "Request timed out" in str(error)

    async def test_error_transformation_rate_limit(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test transformation of rate limit errors."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise RateLimitError("Rate limit exceeded", 429)

        with pytest.raises(ToolError) as exc_info:
            await error_middleware.on_message(context, mock_next)

        error = exc_info.value
        assert "Rate limit exceeded" in str(error)

    async def test_error_transformation_standard_exceptions(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test transformation of standard Python exceptions."""
        context = MockMiddlewareContext()

        # Test ValueError -> MCPValidationError
        async def value_error_next(_ctx: Any) -> None:
            raise ValueError("Invalid parameter value")

        with pytest.raises(MCPValidationError) as exc_info:
            await error_middleware.on_message(context, value_error_next)

        assert "Invalid parameter value" in str(exc_info.value)

        # Test ConnectionError -> MCPClientError
        async def connection_error_next(_ctx: Any) -> None:
            raise ConnectionError("Failed to connect")

        with pytest.raises(MCPClientError) as client_exc_info:
            await error_middleware.on_message(context, connection_error_next)

        assert "Failed to connect" in str(client_exc_info.value)

        # Test TimeoutError -> MCPTimeoutError
        async def timeout_error_next(_ctx: Any) -> None:
            raise TimeoutError("Operation timed out")

        with pytest.raises(MCPTimeoutError) as timeout_exc_info:
            await error_middleware.on_message(context, timeout_error_next)

        assert "Operation timed out" in str(timeout_exc_info.value)

    async def test_mcp_error_passthrough(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test that MCP errors pass through without transformation."""
        context = MockMiddlewareContext()

        original_error = MCPValidationError("Original MCP error")

        async def mock_next(_ctx: Any) -> None:
            raise original_error

        with pytest.raises(MCPValidationError) as exc_info:
            await error_middleware.on_message(context, mock_next)

        # Should be the same error instance
        assert exc_info.value is original_error

    async def test_generic_error_transformation(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test transformation of generic exceptions to MCPServerError."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise RuntimeError("Unexpected error")

        with pytest.raises(MCPServerError) as exc_info:
            await error_middleware.on_message(context, mock_next)

        error = exc_info.value
        assert "Unexpected error" in str(error)

    def test_context_extraction(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test extraction of context information for error handling."""
        mock_message = Mock()
        mock_message.name = "test_tool"
        mock_message.arguments = {"url": "https://example.com", "api_key": "secret"}

        context = MockMiddlewareContext(
            method="test_method",
            source="test_client",
            message=mock_message
        )

        extracted = error_middleware._extract_context(context)

        assert extracted["method"] == "test_method"
        assert extracted["source"] == "test_client"
        assert extracted["tool_name"] == "test_tool"
        assert "timestamp" in extracted

        # Arguments should be included and sensitive data masked
        assert "arguments" in extracted
        args = extracted["arguments"]
        assert args["url"] == "https://example.com"
        assert args["api_key"] == "***MASKED***"

    def test_sensitive_data_masking(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test masking of sensitive data in error context."""
        sensitive_data = {
            "api_key": "secret-key-123",
            "password": "secret-password",
            "auth_token": "bearer-token-xyz",
            "safe_field": "safe_value",
            "nested": {
                "secret": "nested-secret",
                "normal": "normal_value"
            }
        }

        masked = error_middleware._mask_sensitive_dict(sensitive_data)

        assert masked["api_key"] == "***MASKED***"
        assert masked["password"] == "***MASKED***"
        assert masked["auth_token"] == "***MASKED***"
        assert masked["safe_field"] == "safe_value"
        assert masked["nested"]["secret"] == "***MASKED***"
        assert masked["nested"]["normal"] == "normal_value"

    async def test_error_statistics_collection(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test that error statistics are collected properly."""
        context = MockMiddlewareContext(method="test_operation")

        async def mock_next(_ctx: Any) -> None:
            raise ValueError("Test error")

        with pytest.raises(MCPValidationError):
            await error_middleware.on_message(context, mock_next)

        stats = error_middleware.get_error_statistics()
        assert stats["total_errors"] == 1
        assert "MCPValidationError" in stats["errors_by_type"]
        assert "test_operation" in stats["errors_by_operation"]

        recent = error_middleware.get_recent_errors()
        assert len(recent) == 1
        assert recent[0]["error_type"] == "MCPValidationError"

    async def test_error_callback(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test custom error callback functionality."""
        callback_calls: list[tuple[str, str]] = []

        def custom_callback(error: Exception, context: Any) -> None:
            callback_calls.append((type(error).__name__, context.method))

        error_middleware.error_callback = custom_callback

        context = MockMiddlewareContext(method="callback_test")

        async def mock_next(_ctx: Any) -> None:
            raise ValueError("Callback test error")

        with pytest.raises(MCPValidationError):
            await error_middleware.on_message(context, mock_next)

        assert len(callback_calls) == 1
        assert callback_calls[0] == ("MCPValidationError", "callback_test")

    async def test_error_callback_exception_handling(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test that exceptions in error callbacks are handled gracefully."""
        def failing_callback(_error: Exception, _context: Any) -> None:
            raise RuntimeError("Callback failed")

        error_middleware.error_callback = failing_callback

        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise ValueError("Original error")

        with patch.object(error_middleware.logger, 'error') as mock_log:
            with pytest.raises(MCPValidationError):
                await error_middleware.on_message(context, mock_next)

            # Should have logged the callback error
            mock_log.assert_called()
            assert any("Error in error callback" in str(call) for call in mock_log.call_args_list)

    async def test_no_transformation_when_disabled(self, minimal_error_middleware: ErrorHandlingMiddleware) -> None:
        """Test that error transformation can be disabled."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise BadRequestError("Original Firecrawl error", 400)

        with pytest.raises(BadRequestError) as exc_info:
            await minimal_error_middleware.on_message(context, mock_next)

        # Should be the original error, not transformed
        assert "Original Firecrawl error" in str(exc_info.value)
        assert isinstance(exc_info.value, BadRequestError)

    def test_reset_statistics(self, error_middleware: ErrorHandlingMiddleware) -> None:
        """Test resetting error statistics."""
        # Add some errors first
        async def add_errors() -> None:
            context = MockMiddlewareContext()

            async def mock_next(_ctx: Any) -> None:
                raise ValueError("Test error")

            with pytest.raises(MCPValidationError):
                await error_middleware.on_message(context, mock_next)

        asyncio.run(add_errors())

        # Verify stats exist
        stats = error_middleware.get_error_statistics()
        assert stats["total_errors"] > 0

        # Reset and verify empty
        error_middleware.reset_statistics()
        stats = error_middleware.get_error_statistics()
        assert stats["total_errors"] == 0


class TestRetryMiddleware:
    """Test RetryMiddleware functionality."""

    @pytest.fixture
    def retry_middleware(self) -> RetryMiddleware:
        """Create a retry middleware instance."""
        return RetryMiddleware(
            max_retries=3,
            base_delay=0.01,  # Small delay for fast tests
            max_delay=0.1,
            exponential_base=2.0,
            jitter=False  # Disable jitter for predictable testing
        )

    async def test_successful_request_no_retry(self, retry_middleware: RetryMiddleware) -> None:
        """Test that successful requests don't trigger retries."""
        context = MockMiddlewareContext()
        call_count = 0

        async def mock_next(_ctx: Any) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            return {"result": "success"}

        result = await retry_middleware.on_request(context, mock_next)

        assert result == {"result": "success"}
        assert call_count == 1  # Should only be called once

    async def test_retry_on_retryable_error(self, retry_middleware: RetryMiddleware) -> None:
        """Test retrying on retryable errors."""
        context = MockMiddlewareContext()
        call_count = 0

        async def mock_next(_ctx: Any) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary connection error")
            return {"result": "success"}

        result = await retry_middleware.on_request(context, mock_next)

        assert result == {"result": "success"}
        assert call_count == 3  # Should have retried twice

    async def test_retry_exhaustion(self, retry_middleware: RetryMiddleware) -> None:
        """Test behavior when retries are exhausted."""
        context = MockMiddlewareContext()
        call_count = 0

        async def mock_next(_ctx: Any) -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent connection error")

        with pytest.raises(ConnectionError) as exc_info:
            await retry_middleware.on_request(context, mock_next)

        assert "Persistent connection error" in str(exc_info.value)
        assert call_count == 4  # Initial call + 3 retries

    async def test_no_retry_on_non_retryable_error(self, retry_middleware: RetryMiddleware) -> None:
        """Test that non-retryable errors are not retried."""
        context = MockMiddlewareContext()
        call_count = 0

        async def mock_next(_ctx: Any) -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Validation error")  # Not in retry_exceptions

        with pytest.raises(ValueError):
            await retry_middleware.on_request(context, mock_next)

        assert call_count == 1  # Should not retry

    async def test_custom_retry_callback(self) -> None:
        """Test custom retry callback logic."""
        def custom_retry_callback(error: Exception, attempt: int) -> bool:
            # Only retry ValueError on first attempt
            return isinstance(error, ValueError) and attempt == 0

        middleware = RetryMiddleware(
            max_retries=2,
            base_delay=0.01,
            retry_callback=custom_retry_callback
        )

        context = MockMiddlewareContext()
        call_count = 0

        async def mock_next(_ctx: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Custom retry test")
            return "success"

        result = await middleware.on_request(context, mock_next)

        assert result == "success"
        assert call_count == 2  # Initial + 1 retry (callback limits to first attempt)

    async def test_retry_callback_exception_handling(self) -> None:
        """Test handling exceptions in retry callback."""
        def failing_callback(_error: Exception, _attempt: int) -> bool:
            raise RuntimeError("Callback failed")

        middleware = RetryMiddleware(
            max_retries=2,
            base_delay=0.01,
            retry_callback=failing_callback
        )

        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise ConnectionError("Test error")

        # Should handle callback exception gracefully and not retry
        with pytest.raises(ConnectionError):
            await middleware.on_request(context, mock_next)

    def test_delay_calculation(self, retry_middleware: RetryMiddleware) -> None:
        """Test exponential backoff delay calculation."""
        # Test delay calculation
        delay_0 = retry_middleware._calculate_delay(0)
        delay_1 = retry_middleware._calculate_delay(1)
        delay_2 = retry_middleware._calculate_delay(2)

        assert delay_0 == 0.01  # base_delay
        assert delay_1 == 0.02  # base_delay * 2^1
        assert delay_2 == 0.04  # base_delay * 2^2

    def test_delay_max_limit(self) -> None:
        """Test that delay respects maximum limit."""
        middleware = RetryMiddleware(
            base_delay=1.0,
            max_delay=2.0,
            exponential_base=10.0,  # Would cause large delays
            jitter=False  # Disable jitter for predictable testing
        )

        delay = middleware._calculate_delay(5)  # Would be 1.0 * 10^5 = 100000
        assert delay == 2.0  # Should be capped at max_delay

    def test_jitter_application(self) -> None:
        """Test that jitter is applied when enabled."""
        middleware = RetryMiddleware(
            base_delay=1.0,
            jitter=True
        )

        delays = [middleware._calculate_delay(0) for _ in range(10)]

        # With jitter, delays should vary
        assert len(set(delays)) > 1
        # All delays should be around base_delay ± 10%
        for delay in delays:
            assert 0.9 <= delay <= 1.1


class TestCircuitBreakerMiddleware:
    """Test CircuitBreakerMiddleware functionality."""

    @pytest.fixture
    def circuit_breaker(self) -> CircuitBreakerMiddleware:
        """Create a circuit breaker middleware instance."""
        return CircuitBreakerMiddleware(
            failure_threshold=3,
            recovery_timeout=0.1,  # Small timeout for fast tests
            expected_exceptions=(MCPServerError, MCPClientError, ConnectionError)
        )

    async def test_successful_requests_keep_circuit_closed(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test that successful requests keep the circuit closed."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> dict[str, str]:
            return {"result": "success"}

        # Multiple successful requests
        for _ in range(5):
            result = await circuit_breaker.on_request(context, mock_next)
            assert result == {"result": "success"}

        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0

    async def test_failures_open_circuit(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test that consecutive failures open the circuit."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise MCPServerError("Server error")

        # Make failures up to threshold
        for i in range(3):
            with pytest.raises(MCPServerError):
                await circuit_breaker.on_request(context, mock_next)

            if i < 2:  # Before threshold
                assert circuit_breaker.state == "CLOSED"
            else:  # At threshold
                assert circuit_breaker.state == "OPEN"

    async def test_open_circuit_rejects_requests(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test that open circuit rejects requests immediately."""
        context = MockMiddlewareContext()

        # Open the circuit by causing failures
        async def failing_next(_ctx: Any) -> None:
            raise MCPServerError("Server error")

        for _ in range(3):  # Reach failure threshold
            with pytest.raises(MCPServerError):
                await circuit_breaker.on_request(context, failing_next)

        assert circuit_breaker.state == "OPEN"

        # Now requests should be rejected immediately
        async def would_succeed_next(_ctx: Any) -> dict[str, str]:
            return {"result": "success"}

        with pytest.raises(MCPServerError) as exc_info:
            await circuit_breaker.on_request(context, would_succeed_next)

        error = exc_info.value
        assert "Circuit breaker is OPEN" in str(error)
        assert "service temporarily unavailable" in str(error)

    async def test_circuit_recovery_to_half_open(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test circuit recovery to half-open state."""
        context = MockMiddlewareContext()

        # Open the circuit
        async def failing_next(_ctx: Any) -> None:
            raise MCPServerError("Server error")

        for _ in range(3):
            with pytest.raises(MCPServerError):
                await circuit_breaker.on_request(context, failing_next)

        assert circuit_breaker.state == "OPEN"

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next request should transition to HALF_OPEN and succeed
        async def success_next(_ctx: Any) -> dict[str, str]:
            return {"result": "recovered"}

        result = await circuit_breaker.on_request(context, success_next)

        assert result == {"result": "recovered"}
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0

    async def test_half_open_failure_returns_to_open(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test that failure in half-open state returns to open."""
        context = MockMiddlewareContext()

        # Open the circuit
        async def failing_next(_ctx: Any) -> None:
            raise MCPServerError("Server error")

        for _ in range(3):
            with pytest.raises(MCPServerError):
                await circuit_breaker.on_request(context, failing_next)

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Fail in half-open state
        with pytest.raises(MCPServerError):
            await circuit_breaker.on_request(context, failing_next)

        assert circuit_breaker.state == "OPEN"

    async def test_non_expected_exceptions_ignored(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test that non-expected exceptions don't affect circuit state."""
        context = MockMiddlewareContext()

        async def mock_next(_ctx: Any) -> None:
            raise ValueError("Not an expected exception")

        # This exception should not count towards circuit breaking
        with pytest.raises(ValueError):
            await circuit_breaker.on_request(context, mock_next)

        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0

    def test_get_circuit_state(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test getting circuit breaker state."""
        state = circuit_breaker.get_state()

        assert state["state"] == "CLOSED"
        assert state["failure_count"] == 0
        assert state["failure_threshold"] == 3
        assert "time_since_last_failure" in state
        assert state["recovery_timeout"] == 0.1

    def test_reset_circuit(self, circuit_breaker: CircuitBreakerMiddleware) -> None:
        """Test resetting circuit breaker state."""
        # Simulate some failures
        circuit_breaker.failure_count = 2
        circuit_breaker.last_failure_time = time.time()
        circuit_breaker.state = "OPEN"

        circuit_breaker.reset()

        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_failure_time == 0.0


# Helper functions to replace the removed factory functions
def create_error_handling_middleware_for_test(debug_mode: bool = False, enable_metrics: bool = False) -> ErrorHandlingMiddleware:
    """Create error handling middleware for testing."""
    return ErrorHandlingMiddleware(
        include_traceback=debug_mode,
        transform_errors=True,
        mask_sensitive_data=True,
        enable_statistics=enable_metrics
    )

def create_retry_middleware_for_test(development_mode: bool = False, debug_mode: bool = False) -> RetryMiddleware | None:
    """Create retry middleware for testing."""
    if debug_mode:
        return None

    if development_mode:
        return RetryMiddleware(
            max_retries=2,
            base_delay=0.5,
            max_delay=5.0
        )
    else:
        return RetryMiddleware(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0
        )

class TestErrorHandlingFactory:
    """Test error handling middleware factory functions."""

    def test_create_error_handling_middleware(self) -> None:
        """Test creating error handling middleware from config."""
        debug_mode = True
        enable_metrics = True

        middleware = create_error_handling_middleware_for_test(debug_mode, enable_metrics)

        assert isinstance(middleware, ErrorHandlingMiddleware)
        assert middleware.include_traceback is True
        assert middleware.transform_errors is True
        assert middleware.mask_sensitive_data is True
        assert middleware.enable_statistics is True

    def test_create_retry_middleware_development(self) -> None:
        """Test creating retry middleware for development."""
        development_mode = True
        debug_mode = False

        middleware = create_retry_middleware_for_test(development_mode, debug_mode)

        assert isinstance(middleware, RetryMiddleware)
        assert middleware.max_retries == 2
        assert middleware.base_delay == 0.5
        assert middleware.max_delay == 5.0

    def test_create_retry_middleware_production(self) -> None:
        """Test creating retry middleware for production."""
        development_mode = False
        debug_mode = False

        middleware = create_retry_middleware_for_test(development_mode, debug_mode)

        assert isinstance(middleware, RetryMiddleware)
        assert middleware.max_retries == 3
        assert middleware.base_delay == 1.0
        assert middleware.max_delay == 30.0

    def test_create_retry_middleware_debug_disabled(self) -> None:
        """Test that retry middleware is disabled in debug mode."""
        development_mode = False
        debug_mode = True

        middleware = create_retry_middleware_for_test(development_mode, debug_mode)

        assert middleware is None


class TestErrorHandlingIntegration:
    """Test error handling integration scenarios."""

    async def test_retry_with_circuit_breaker(self) -> None:
        """Test retry middleware combined with circuit breaker."""
        retry_middleware = RetryMiddleware(
            max_retries=2,
            base_delay=0.01,
            retry_exceptions=(ConnectionError,)
        )

        circuit_breaker = CircuitBreakerMiddleware(
            failure_threshold=3,
            recovery_timeout=0.1,
            expected_exceptions=(ConnectionError,)
        )

        context = MockMiddlewareContext()
        failure_count = 0

        async def failing_next(_ctx: Any) -> None:
            nonlocal failure_count
            failure_count += 1
            raise ConnectionError("Persistent failure")

        # Combine middlewares (circuit breaker first, then retry)
        async def combined_middleware(ctx: Any, call_next: Callable[..., Any]) -> Any:
            return await circuit_breaker.on_request(
                ctx,
                lambda c: retry_middleware.on_request(c, call_next)
            )

        # Should retry and eventually fail, contributing to circuit breaker
        with pytest.raises(ConnectionError):
            await combined_middleware(context, failing_next)

        # Each retry attempt should count as a failure for circuit breaker
        assert circuit_breaker.failure_count > 0

    async def test_error_handling_with_statistics(self) -> None:
        """Test comprehensive error handling with statistics collection."""
        error_middleware = ErrorHandlingMiddleware(
            transform_errors=True,
            enable_statistics=True
        )

        context = MockMiddlewareContext(method="comprehensive_test")

        # Test various error types
        test_errors = [
            BadRequestError("Bad request", 400),
            UnauthorizedError("Unauthorized", 401),
            RequestTimeoutError("Timeout", 408),
            ValueError("Validation error"),
            ConnectionError("Connection failed")
        ]

        for error in test_errors:
            async def error_next(_ctx: Any, error: Exception = error) -> None:
                raise error

            with pytest.raises((MCPError, ToolError)):
                await error_middleware.on_message(context, error_next)

        # Check statistics
        stats = error_middleware.get_error_statistics()
        assert stats["total_errors"] == 5
        assert stats["errors_by_operation"]["comprehensive_test"] == 5

        # Should have different error types
        error_types = set(stats["errors_by_type"].keys())
        assert len(error_types) >= 3  # At least 3 different MCP error types

    async def test_concurrent_error_handling(self) -> None:
        """Test error handling with concurrent operations."""
        error_middleware = ErrorHandlingMiddleware(enable_statistics=True)

        async def error_operation(operation_name: str, error_type: Exception) -> None:
            context = MockMiddlewareContext(method=operation_name)

            async def error_next(_ctx: Any) -> None:
                raise error_type

            with contextlib.suppress(MCPError, ToolError):
                await error_middleware.on_message(context, error_next)

        # Launch concurrent error operations
        tasks = [
            error_operation("op_1", ValueError("Error 1")),
            error_operation("op_2", ConnectionError("Error 2")),
            error_operation("op_3", TimeoutError("Error 3")),
            error_operation("op_1", ValueError("Error 4")),  # Same operation
            error_operation("op_2", TypeError("Error 5"))   # Different error type
        ]

        await asyncio.gather(*tasks)

        # Check that all errors were recorded
        stats = error_middleware.get_error_statistics()
        assert stats["total_errors"] == 5
        assert stats["errors_by_operation"]["op_1"] == 2
        assert stats["errors_by_operation"]["op_2"] == 2
        assert stats["errors_by_operation"]["op_3"] == 1
