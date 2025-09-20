"""
FastMCP-compatible error utilities.

This module provides simple error handling utilities that work with FastMCP's ToolError,
replacing the complex custom error hierarchy.
"""

import logging
from typing import Any

from fastmcp.exceptions import ToolError
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    FirecrawlError,
    InternalServerError,
    PaymentRequiredError,
    RateLimitError,
    RequestTimeoutError,
    UnauthorizedError,
    WebsiteNotSupportedError,
)

logger = logging.getLogger(__name__)


def handle_firecrawl_error(
    error: FirecrawlError,
    context: str | None = None
) -> ToolError:
    """
    Convert Firecrawl errors to FastMCP ToolError with context.
    
    Args:
        error: The original Firecrawl error
        context: Additional context string
        
    Returns:
        ToolError: FastMCP-compatible error with enhanced information
    """
    # Create enhanced error message
    message = str(error)
    if context:
        message = f"{message} (Context: {context})"

    # Map specific error types to more informative messages
    error_type_messages = {
        BadRequestError: "Invalid request parameters",
        UnauthorizedError: "Authentication failed - check API key",
        PaymentRequiredError: "Payment required - check account credits",
        WebsiteNotSupportedError: "Website not supported for scraping",
        RequestTimeoutError: "Request timed out - try again later",
        RateLimitError: "Rate limit exceeded - please wait before retrying",
        InternalServerError: "Internal server error occurred",
    }

    error_prefix = error_type_messages.get(type(error), "Firecrawl API error")
    enhanced_message = f"{error_prefix}: {message}"

    logger.error(f"Converted Firecrawl error: {type(error).__name__} -> ToolError")
    return ToolError(enhanced_message)


def create_tool_error(message: str, details: dict[str, Any] | None = None) -> ToolError:
    """
    Create a ToolError with optional details in the message.
    
    Args:
        message: Error message
        details: Optional details to include in message
        
    Returns:
        ToolError: FastMCP-compatible error
    """
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        enhanced_message = f"{message} (Details: {detail_str})"
    else:
        enhanced_message = message

    return ToolError(enhanced_message)


def mcp_log_error(error: Exception, context: dict[str, Any] | None = None) -> None:
    """
    Log an error with context information.
    
    Args:
        error: The error to log
        context: Additional context information
    """
    context = context or {}

    # Create log message
    log_message = f"{type(error).__name__}: {error}"
    if context:
        context_info = ", ".join(f"{k}={v}" for k, v in context.items())
        log_message = f"{log_message} (Context: {context_info})"

    # Log based on error type
    if isinstance(error, ToolError):
        logger.warning(log_message)
    else:
        logger.error(log_message, exc_info=True)



# Backward compatibility - deprecated error classes
class MCPError(Exception):
    """DEPRECATED: Use ToolError instead."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        logger.warning("MCPError is deprecated, use ToolError instead")


class MCPConfigurationError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPClientError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPToolError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPValidationError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPAuthenticationError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPRateLimitError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPResourceError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPTimeoutError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


class MCPServerError(MCPError):
    """DEPRECATED: Use ToolError instead."""
    pass


def create_error_response(error: Exception) -> dict[str, Any]:
    """
    DEPRECATED: Create error response.
    
    Use FastMCP's built-in error handling instead.
    """
    logger.warning("create_error_response() is deprecated")
    return {
        "error": type(error).__name__,
        "message": str(error),
        "error_code": "UNKNOWN_ERROR",
        "details": {},
        "status_code": None
    }
