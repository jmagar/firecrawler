"""
Core utilities package for FastMCP-compatible Firecrawl integration.

This package provides lightweight utilities for the Firecrawl MCP server:
- Environment-based client access following FastMCP patterns
- Simple environment variable utilities
- FastMCP ToolError-compatible error handling
- Backward compatibility for gradual migration

The core package is now aligned with FastMCP patterns and significantly simplified.
"""

from .client import get_firecrawl_client, get_client_status
from .config import get_env_bool, get_env_float, get_env_int, get_server_info, validate_environment
from .exceptions import create_tool_error, handle_firecrawl_error

# Backward compatibility imports (deprecated)
from .client import get_client, initialize_client, reset_client
from .config import MCPConfig, load_config
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
)

__all__ = [
    # FastMCP-compatible utilities (recommended)
    "get_firecrawl_client",
    "get_client_status",
    "get_env_bool",
    "get_env_float", 
    "get_env_int",
    "get_server_info",
    "validate_environment",
    "create_tool_error",
    "handle_firecrawl_error",

    # Backward compatibility (deprecated)
    "get_client",
    "initialize_client",
    "reset_client",
    "MCPConfig",
    "load_config",
    "MCPError",
    "MCPConfigurationError",
    "MCPClientError", 
    "MCPToolError",
    "MCPValidationError",
    "MCPAuthenticationError",
    "MCPRateLimitError",
    "MCPResourceError",
    "MCPTimeoutError",
    "MCPServerError",
    "create_error_response",
]
