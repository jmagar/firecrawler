"""
Error processing and response formatting middleware for the Firecrawler MCP server.

This module provides comprehensive error handling middleware that processes exceptions,
formats responses, implements retry logic, and provides proper error transformation
following FastMCP and Firecrawl patterns.
"""

import asyncio
import logging
import random
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError, ResourceError, PromptError

from firecrawl.v2.utils.error_handler import (
    FirecrawlError,
    RequestTimeoutError,
)

from ..core.config import MCPConfig
from ..core.exceptions import (
    MCPAuthenticationError,
    MCPClientError,
    MCPError,
    MCPServerError,
    MCPTimeoutError,
    MCPValidationError,
    handle_firecrawl_error,
)
from ..core.exceptions import mcp_log_error

logger = logging.getLogger(__name__)


@dataclass
class ErrorStatistics:
    """Statistics for error tracking."""

    total_errors: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    errors_by_operation: dict[str, int] = field(default_factory=dict)
    recent_errors: list[dict[str, Any]] = field(default_factory=list)
    max_recent_errors: int = 100

    def add_error(
        self,
        error: Exception,
        operation: str,
        context: dict[str, Any] | None = None
    ) -> None:
        """Add an error to statistics."""
        self.total_errors += 1

        error_type = type(error).__name__
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.errors_by_operation[operation] = self.errors_by_operation.get(operation, 0) + 1

        # Add to recent errors
        error_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "error_type": error_type,
            "operation": operation,
            "message": str(error),
            "context": context or {}
        }

        self.recent_errors.append(error_entry)

        # Keep only recent errors
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]

    def get_stats(self) -> dict[str, Any]:
        """Get error statistics."""
        return {
            "total_errors": self.total_errors,
            "errors_by_type": dict(self.errors_by_type),
            "errors_by_operation": dict(self.errors_by_operation),
            "recent_error_count": len(self.recent_errors)
        }

    def get_recent_errors(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent errors."""
        if limit:
            return self.recent_errors[-limit:]
        return self.recent_errors.copy()


class ErrorHandlingMiddleware(Middleware):
    """
    Comprehensive error handling and transformation middleware.
    
    Provides error logging, transformation, statistics tracking, and
    standardized error response formatting for MCP clients.
    """

    def __init__(
        self,
        logger_name: str | None = None,
        include_traceback: bool = False,
        transform_errors: bool = True,
        error_callback: Callable[[Exception, MiddlewareContext], None] | None = None,
        mask_sensitive_data: bool = True,
        enable_statistics: bool = True
    ):
        """
        Initialize error handling middleware.
        
        Args:
            logger_name: Custom logger name
            include_traceback: Whether to include traceback in error responses
            transform_errors: Whether to transform Firecrawl errors to MCP errors
            error_callback: Optional callback for custom error handling
            mask_sensitive_data: Whether to mask sensitive data in error logs
            enable_statistics: Whether to collect error statistics
        """
        self.logger = logging.getLogger(logger_name or __name__)
        self.include_traceback = include_traceback
        self.transform_errors = transform_errors
        self.error_callback = error_callback
        self.mask_sensitive_data = mask_sensitive_data
        self.enable_statistics = enable_statistics

        # Error statistics
        self.statistics = ErrorStatistics() if enable_statistics else None

        # Sensitive field patterns to mask
        self.sensitive_patterns = {
            'api_key', 'token', 'password', 'secret', 'auth', 'authorization'
        }

    async def on_message(self, context: MiddlewareContext, call_next):
        """Handle all messages with comprehensive error processing."""
        try:
            return await call_next(context)

        except Exception as error:
            # Process and transform the error
            processed_error = await self._process_error(error, context)

            # Log the error
            await self._log_error(processed_error, context)

            # Update statistics
            if self.statistics:
                operation = getattr(context, 'method', 'unknown')
                error_context = self._extract_context(context)
                self.statistics.add_error(processed_error, operation, error_context)

            # Call custom error callback if provided
            if self.error_callback:
                try:
                    self.error_callback(processed_error, context)
                except Exception as callback_error:
                    if context.fastmcp_context:
                        await context.fastmcp_context.error(f"Error in error callback: {callback_error}")

            # Re-raise the processed error
            raise processed_error

    async def _process_error(self, error: Exception, context: MiddlewareContext) -> Exception:
        """Process and potentially transform an error."""
        # If transformation is disabled, return original error
        if not self.transform_errors:
            return error

        # Extract context for error transformation
        error_context = self._extract_context(context)

        # Transform Firecrawl errors to MCP errors
        if isinstance(error, FirecrawlError):
            return handle_firecrawl_error(error, error_context)

        # Transform standard exceptions to appropriate MCP errors
        if isinstance(error, ValueError):
            return MCPValidationError(
                message=str(error),
                details={"original_error": type(error).__name__, **error_context}
            )

        if isinstance(error, ConnectionError):
            return MCPClientError(
                message=f"Connection error: {error}",
                connection_info=error_context
            )

        if isinstance(error, TimeoutError):
            return MCPTimeoutError(
                message=f"Operation timed out: {error}",
                operation=error_context.get('method'),
                details=error_context
            )

        if isinstance(error, PermissionError):
            return MCPAuthenticationError(
                message=f"Permission denied: {error}",
                details=error_context
            )

        # For MCP-specific errors, just return as-is
        if isinstance(error, MCPError):
            return error

        # For tool/resource/prompt specific errors (if they exist)
        # Note: These would be specific FastMCP errors, but we're using a generic approach

        # For all other errors, wrap in generic MCP server error
        return MCPServerError(
            message=f"Internal server error: {error}",
            details={
                "original_error": type(error).__name__,
                "original_message": str(error),
                **error_context
            }
        )

    def _extract_context(self, context: MiddlewareContext) -> dict[str, Any]:
        """Extract relevant context information for error handling."""
        error_context = {
            "method": getattr(context, 'method', 'unknown'),
            "source": getattr(context, 'source', 'unknown'),
            "type": getattr(context, 'type', 'unknown'),
            "timestamp": datetime.now(UTC).isoformat()
        }

        # Add message information if available
        if hasattr(context, 'message'):
            message = context.message
            if hasattr(message, 'name'):
                error_context["tool_name"] = message.name
            if hasattr(message, 'uri'):
                error_context["resource_uri"] = message.uri
            if hasattr(message, 'arguments'):
                # Mask sensitive arguments
                args = message.arguments
                if self.mask_sensitive_data and isinstance(args, dict):
                    args = self._mask_sensitive_dict(args)
                error_context["arguments"] = args

        return error_context

    def _mask_sensitive_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive data in dictionary."""
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            key_lower = key.lower()

            if any(pattern in key_lower for pattern in self.sensitive_patterns):
                if value:
                    masked[key] = "***MASKED***"
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_dict(value)
            else:
                masked[key] = value

        return masked

    async def _log_error(self, error: Exception, context: MiddlewareContext) -> None:
        """Log error with appropriate detail level."""
        # Use the existing log_error function from core.exceptions
        error_context = self._extract_context(context)
        mcp_log_error(error, error_context)

        # Add traceback for detailed logging
        if self.include_traceback and context.fastmcp_context:
            await context.fastmcp_context.error(f"Full traceback for {type(error).__name__}:\n{traceback.format_exc()}")

    def get_error_statistics(self) -> dict[str, Any]:
        """Get current error statistics."""
        if not self.statistics:
            return {"error": "Statistics not enabled"}

        return self.statistics.get_stats()

    def get_recent_errors(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent errors."""
        if not self.statistics:
            return []

        return self.statistics.get_recent_errors(limit)

    def reset_statistics(self) -> None:
        """Reset error statistics."""
        if self.statistics:
            self.statistics = ErrorStatistics()


class RetryMiddleware(Middleware):
    """
    Automatic retry middleware with exponential backoff.
    
    Provides automatic retry logic for transient failures with configurable
    retry policies and exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_exceptions: tuple[type[Exception], ...] | None = None,
        retry_callback: Callable[[Exception, int], bool] | None = None
    ):
        """
        Initialize retry middleware.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
            retry_exceptions: Tuple of exception types to retry
            retry_callback: Optional callback to determine if retry should happen
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_callback = retry_callback

        # Default exceptions to retry
        self.retry_exceptions = retry_exceptions or (
            ConnectionError,
            TimeoutError,
            MCPTimeoutError,
            MCPClientError,
            RequestTimeoutError
        )

    async def on_request(self, context: MiddlewareContext, call_next):
        """Apply retry logic to requests."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await call_next(context)

            except Exception as error:
                last_error = error

                # Check if we should retry this error
                should_retry = await self._should_retry(error, attempt, context)

                if not should_retry or attempt >= self.max_retries:
                    # Log retry exhaustion
                    if attempt > 0 and context.fastmcp_context:
                        await context.fastmcp_context.warning(
                            f"Retry exhausted for {context.method} after {attempt} attempts. "
                            f"Final error: {type(error).__name__}: {error}"
                        )
                    raise error

                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)

                if context.fastmcp_context:
                    await context.fastmcp_context.info(
                        f"Retrying {context.method} (attempt {attempt + 1}/{self.max_retries + 1}) "
                        f"after {delay:.2f}s delay. Error: {type(error).__name__}: {error}"
                    )

                # Wait before retry
                await asyncio.sleep(delay)

        # This should never be reached, but just in case
        if last_error:
            raise last_error
        else:
            raise MCPServerError("Retry loop completed without error or result")

    async def _should_retry(self, error: Exception, attempt: int, context: MiddlewareContext) -> bool:
        """Determine if an error should be retried."""
        # Check custom retry callback first
        if self.retry_callback:
            try:
                return self.retry_callback(error, attempt)
            except Exception as callback_error:
                if context.fastmcp_context:
                    await context.fastmcp_context.error(f"Error in retry callback: {callback_error}")
                return False

        # Check if error type is in retry exceptions
        return isinstance(error, self.retry_exceptions)

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        # Exponential backoff
        delay = self.base_delay * (self.exponential_base ** attempt)

        # Apply maximum delay
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)

        # Ensure non-negative delay
        return max(0.0, delay)


class CircuitBreakerMiddleware(Middleware):
    """
    Circuit breaker middleware to prevent cascading failures.
    
    Implements circuit breaker pattern to temporarily stop calling
    failing services and allow them time to recover.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exceptions: tuple[type[Exception], ...] | None = None
    ):
        """
        Initialize circuit breaker middleware.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exceptions: Exceptions that count as failures
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions or (
            MCPServerError,
            MCPClientError,
            MCPTimeoutError,
            ConnectionError,
            TimeoutError
        )

        # Circuit state
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def on_request(self, context: MiddlewareContext, call_next):
        """Apply circuit breaker logic."""
        current_time = time.time()

        # Check if circuit should transition from OPEN to HALF_OPEN
        if (self.state == "OPEN" and
            current_time - self.last_failure_time >= self.recovery_timeout):
            self.state = "HALF_OPEN"
            if context.fastmcp_context:
                await context.fastmcp_context.info("Circuit breaker transitioning to HALF_OPEN state")

        # If circuit is OPEN, reject requests immediately
        if self.state == "OPEN":
            raise MCPServerError(
                "Circuit breaker is OPEN - service temporarily unavailable",
                component="circuit_breaker",
                details={
                    "failure_count": self.failure_count,
                    "time_until_retry": self.recovery_timeout - (current_time - self.last_failure_time)
                }
            )

        try:
            result = await call_next(context)

            # Success - reset failure count if in HALF_OPEN state
            if self.state == "HALF_OPEN":
                self.failure_count = 0
                self.state = "CLOSED"
                if context.fastmcp_context:
                    await context.fastmcp_context.info("Circuit breaker returning to CLOSED state")

            return result

        except Exception as error:
            # Check if this is a failure we should count
            if isinstance(error, self.expected_exceptions):
                self.failure_count += 1
                self.last_failure_time = current_time

                # Open circuit if threshold reached
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    if context.fastmcp_context:
                        await context.fastmcp_context.warning(
                            f"Circuit breaker OPEN after {self.failure_count} failures. "
                            f"Will retry in {self.recovery_timeout}s"
                        )

            raise error

    def get_state(self) -> dict[str, Any]:
        """Get current circuit breaker state."""
        current_time = time.time()
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "time_since_last_failure": current_time - self.last_failure_time,
            "recovery_timeout": self.recovery_timeout
        }

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"


# Factory functions removed - use direct instantiation with FastMCP
# Example:
# mcp.add_middleware(ErrorHandlingMiddleware(include_traceback=True, transform_errors=True))
# mcp.add_middleware(RetryMiddleware(max_retries=3, base_delay=1.0))
# mcp.add_middleware(CircuitBreakerMiddleware(failure_threshold=5))
