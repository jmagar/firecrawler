"""
FastMCP-aligned resources package for configuration and status information.

This package provides comprehensive MCP resources following FastMCP patterns:
- Direct @mcp.resource decoration (no wrapper functions)
- Resource templates for dynamic URI access
- Simple error handling with direct exception raising
- Basic caching for expensive operations
- Clean, maintainable architecture

Resources include:
- Server configuration and environment settings
- API connectivity and health status
- Usage statistics and operational metrics
- Recent logs and error summaries
- Dynamic access via resource templates

Resources follow FastMCP documentation patterns exactly for optimal
client integration and performance.
"""

from .resources import (
    get_active_operations,
    get_api_status,
    get_config_section,
    get_component_status,
    get_environment_config,
    get_logs_by_level,
    get_recent_logs,
    get_server_config,
    get_server_status,
    get_system_status,
    get_usage_statistics,
    setup_resources,
)

__all__ = [
    "get_active_operations",
    "get_api_status",
    "get_config_section",
    "get_component_status", 
    "get_environment_config",
    "get_logs_by_level",
    "get_recent_logs",
    "get_server_config",
    "get_server_status",
    "get_system_status",
    "get_usage_statistics",
    "setup_resources"
]
