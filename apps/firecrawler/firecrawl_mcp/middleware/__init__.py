"""
Middleware package for request/response processing.

This package provides middleware components that handle cross-cutting concerns
for the Firecrawl MCP server using FastMCP's Context injection patterns:

- timing: Performance metrics and timing middleware
- logging: Request/response logging with rotating files
- rate_limit: Rate limiting following Firecrawl API patterns
- error_handling: Error processing and response formatting

Middleware components integrate with FastMCP's context system rather than
traditional middleware chains, accessing functionality through the context
parameter in tool implementations.
"""

from .error_handling import (
    CircuitBreakerMiddleware,
    ErrorHandlingMiddleware,
    RetryMiddleware,
)
from .logging import LoggingMiddleware, StructuredLoggingMiddleware
from .rate_limit import (
    RateLimitingMiddleware,
    SlidingWindowRateLimitingMiddleware,
)
from .timing import DetailedTimingMiddleware, TimingMiddleware

__all__ = [
    "CircuitBreakerMiddleware",
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "RateLimitingMiddleware",
    "RetryMiddleware",
    "SlidingWindowRateLimitingMiddleware",
    "StructuredLoggingMiddleware",
    "TimingMiddleware",
]
