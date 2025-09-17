# Resources Implementation Guide

This directory implements MCP resources that expose server configuration, status information, and operational data to MCP clients.

## Implementation Patterns

### FastMCP Resource Structure
```python
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ResourceError
from typing import Any

# Resource function using correct async + Context pattern
async def get_server_config(ctx: Context) -> dict[str, Any]:
    """Expose current server configuration and environment variables."""
    try:
        config = load_config()
        result = {
            "api_base_url": config.firecrawl_api_base_url,
            "log_level": config.log_level,
            "transport": config.transport,
            "middleware_enabled": ["timing", "logging", "rate_limit", "error_handling"]
        }
        await ctx.info("Server configuration retrieved successfully")
        return result
    except Exception as e:
        await ctx.error(f"Failed to get server config: {e}")
        raise ResourceError(f"Configuration unavailable: {e}")

# Resource registration with full metadata
def setup_resources(server_mcp: FastMCP) -> None:
    server_mcp.resource(
        "firecrawl://config/server",
        name="Server Configuration",
        description="Current server configuration including environment variables and feature flags",
        mime_type="application/json",
        tags={"configuration", "server"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True
        }
    )(get_server_config)
```

### Resource Categories

#### Configuration Resources
- **server_config**: Current server settings and environment variables
- **middleware_config**: Active middleware configuration and status
- **client_config**: Firecrawl SDK client configuration and connectivity

#### Status Resources
- **health_status**: Server health, API connectivity, and system status
- **operation_stats**: Current operation counts, queue status, and performance metrics
- **credit_usage**: API credit consumption and limits (when available)

#### Operational Resources
- **active_jobs**: Currently running crawl and batch operations
- **error_logs**: Recent error summaries and troubleshooting information
- **performance_metrics**: Response times, throughput, and resource utilization

## Best Practices

### Data Structure
- Return structured, JSON-serializable data
- Include timestamps for time-sensitive information  
- Use consistent field naming across resources
- Provide nested objects for complex configuration
- Use modern Python typing: `dict[str, Any]` not `Dict[str, Any]`
- Always include Context parameter for logging and metadata

### Security Considerations
- Never expose API keys or sensitive credentials
- Sanitize configuration data before returning
- Include only necessary operational information
- Log resource access for audit purposes

### Performance
- Cache expensive resource calculations
- Implement lazy loading for complex data
- Set appropriate refresh intervals
- Monitor resource access patterns

### Error Handling
```python
from fastmcp.exceptions import ResourceError

async def get_resource_data(ctx: Context) -> dict[str, Any]:
    """Example resource with proper error handling."""
    try:
        # Attempt to get data
        data = await fetch_data()
        await ctx.info("Data retrieved successfully")
        return data
    except ConnectionError as e:
        await ctx.error(f"Connection failed: {e}")
        # Return partial data when possible
        return {
            "status": "partial",
            "error": "API connectivity issue",
            "cached_data": get_cached_data()
        }
    except Exception as e:
        await ctx.error(f"Unexpected error: {e}")
        raise ResourceError(f"Resource unavailable: {e}")
```

**Error Handling Best Practices:**
- Use `ResourceError` for resource-specific failures
- Log errors via Context for debugging
- Return partial data when some information is unavailable
- Include error indicators in resource responses
- Provide meaningful error messages
- Gracefully handle API connectivity issues

## Resource Integration

### Client Access
Resources are accessible to MCP clients through standard resource URIs:
- `firecrawl://config` - Server configuration
- `firecrawl://status` - Health and operational status
- `firecrawl://jobs` - Active operations and queue status

### Tool Integration
Tools can reference resources for:
- Configuration-based parameter defaults
- Status-aware error handling
- Performance-optimized operation routing
- Credit-aware request limiting

### Monitoring Integration
Resources provide data for:
- External monitoring systems
- Dashboard implementations
- Alerting and notification systems
- Performance analysis tools

## Resource Templates

Resource templates allow dynamic URI access with parameters:

```python
# Template function with URI parameters
async def get_logs_by_level(level: str, ctx: Context) -> dict[str, Any]:
    """Get log entries filtered by specific log level."""
    if level.lower() not in ["info", "warning", "error", "critical"]:
        raise ResourceError(f"Invalid log level: {level}")
    
    # Implementation logic...
    await ctx.info(f"Filtered logs retrieved for level: {level}")
    return {"level": level, "entries": filtered_entries}

# Registration with template URI
server_mcp.resource(
    "firecrawl://logs/{level}",
    name="Filtered Logs",
    description="Log entries filtered by specific log level (info, warning, error, critical)",
    mime_type="application/json",
    tags={"logs", "filtering", "debugging"},
    annotations={
        "readOnlyHint": True,
        "idempotentHint": False
    }
)(get_logs_by_level)
```

## Implementation Notes

### Function Requirements
- **Always use async**: All resource functions must be async
- **Context parameter**: Include `ctx: Context` for logging and metadata
- **Modern typing**: Use `dict[str, Any]` not `Dict[str, Any]`
- **Error handling**: Use `ResourceError` for failures
- **Logging**: Use `await ctx.info()` and `await ctx.error()`

### Registration Pattern
- Use `setup_resources(server_mcp: FastMCP)` function
- Include full metadata: name, description, mime_type, tags, annotations
- Use consistent URI schemes: `firecrawl://category/resource`
- Set appropriate annotations for client optimization

### Dynamic Updates
- Resources reflect real-time server state
- Configuration changes are immediately visible
- Operation status updates in near real-time
- Historical data includes recent trends

### Versioning
- Maintain backward compatibility in resource schemas
- Include version information in resource metadata
- Support multiple resource format versions
- Document schema changes and migration paths