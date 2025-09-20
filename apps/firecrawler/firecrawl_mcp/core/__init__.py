"""
Core utilities package for FastMCP-compatible Firecrawl integration.

This package provides lightweight utilities for the Firecrawl MCP server:
- Environment-based client access following FastMCP patterns
- Simple environment variable utilities
- FastMCP ToolError-compatible error handling
- Backward compatibility for gradual migration

The core package is now aligned with FastMCP patterns and significantly simplified.
"""

# Backward compatibility imports (deprecated)
from .client import (
    get_client,
    get_client_status,
    get_firecrawl_client,
    initialize_client,
    reset_client,
)
from .config import (
    MCPConfig,
    get_env_bool,
    get_env_float,
    get_env_int,
    get_server_info,
    load_config,
    validate_environment,
)
from .exceptions import (
    MCPAuthenticationError,
    MCPClientError,
    MCPConfigurationError,
    MCPError,
    MCPRateLimitError,
    MCPResourceError,
    MCPServerError,
    MCPTimeoutError,
    MCPToolError,
    MCPValidationError,
    create_error_response,
    create_tool_error,
    handle_firecrawl_error,
)

__all__ = [
    "MCPAuthenticationError",
    "MCPClientError",
    "MCPConfig",
    "MCPConfigurationError",
    "MCPError",
    "MCPRateLimitError",
    "MCPResourceError",
    "MCPServerError",
    "MCPTimeoutError",
    "MCPToolError",
    "MCPValidationError",
    "create_error_response",
    "create_tool_error",
    "get_client",
    "get_client_status",
    "get_env_bool",
    "get_env_float",
    "get_env_int",
    "get_firecrawl_client",
    "get_server_info",
    "handle_firecrawl_error",
    "initialize_client",
    "load_config",
    "reset_client",
    "validate_environment",
]
