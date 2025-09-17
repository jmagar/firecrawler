# Core Services Guide - FastMCP Integration

This directory contains FastMCP-compatible utilities for environment configuration, client management, and error handling for the Firecrawl MCP server.

## FastMCP-Aligned Implementation Patterns

### Environment-Based Configuration
```python
from firecrawl_mcp.core.config import (
    get_env_bool, 
    get_env_int, 
    get_env_float,
    get_server_info,
    validate_environment
)

# Simple environment variable access
api_key = os.getenv("FIRECRAWL_API_KEY", "")
base_url = os.getenv("FIRECRAWL_API_BASE_URL", "https://api.firecrawl.dev")
debug_mode = get_env_bool("FIRECRAWLER_DEBUG", False)
timeout = get_env_int("FIRECRAWLER_TIMEOUT", 30)

# Server info for FastMCP integration
server_info = get_server_info()  # Returns server metadata
environment_status = validate_environment()  # Validates required env vars
```

### Stateless Client Management
```python
from firecrawl_mcp.core.client import get_firecrawl_client, get_client_status

# Create new Firecrawl client from environment variables
client = get_firecrawl_client()  # Stateless - creates new client each time

# Check client connectivity status
status = get_client_status()  # Returns connection and auth status
```

### FastMCP Error Handling
```python
from firecrawl_mcp.core.exceptions import (
    handle_firecrawl_error,
    create_tool_error,
    log_error
)
from fastmcp.exceptions import ToolError

try:
    result = client.scrape(url)
except FirecrawlError as e:
    # Convert Firecrawl errors to FastMCP ToolError
    raise handle_firecrawl_error(e, context="scraping operation")

# Create custom ToolError (always sent to clients)
raise create_tool_error("Invalid URL provided", {"url": url, "error_type": "validation"})
```

## Core Components (FastMCP-Aligned)

### client.py
- **get_firecrawl_client()**: Creates stateless Firecrawl client from environment
- **get_client_status()**: Returns client connectivity and authentication status
- **Deprecated**: `get_client()` - use `get_firecrawl_client()` instead

### config.py
- **get_env_bool/int/float()**: Type-safe environment variable accessors
- **get_server_info()**: Server metadata for FastMCP integration
- **validate_environment()**: Environment validation without complex classes
- **Deprecated**: `MCPConfig` class - use simple environment functions instead

### exceptions.py
- **handle_firecrawl_error()**: Converts FirecrawlError to FastMCP ToolError
- **create_tool_error()**: Creates properly formatted ToolError instances
- **log_error()**: Structured error logging compatible with FastMCP
- **Deprecated**: `MCPError` hierarchy - use FastMCP ToolError instead

## FastMCP Integration Patterns

### Tool Implementation with Context
```python
from fastmcp import FastMCP, Context
from firecrawl_mcp.core.client import get_firecrawl_client
from firecrawl_mcp.core.exceptions import handle_firecrawl_error

mcp = FastMCP("Firecrawl Server")

@mcp.tool
async def scrape_url(url: str, ctx: Context) -> str:
    """Example tool using FastMCP Context and core utilities."""
    await ctx.info(f"Starting scrape operation for {url}")
    
    try:
        client = get_firecrawl_client()
        result = client.scrape(url)
        
        await ctx.info(f"Successfully scraped {len(result.content)} characters")
        return result.content
        
    except FirecrawlError as e:
        await ctx.error(f"Scraping failed for {url}: {e}")
        raise handle_firecrawl_error(e, context=f"scraping {url}")
```

### Server Initialization with Environment Auto-Configuration
```python
from fastmcp import FastMCP
from firecrawl_mcp.core.config import validate_environment

# FastMCP auto-configures from environment variables
mcp = FastMCP(name="Firecrawl MCP Server")

# Validate required environment at startup
env_status = validate_environment()
if not env_status["valid"]:
    raise ToolError(f"Environment validation failed: {env_status['errors']}")
```

### FastMCP Middleware Integration
```python
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware

# Add FastMCP middleware in logical order
mcp.add_middleware(ErrorHandlingMiddleware())
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=10))
mcp.add_middleware(TimingMiddleware())
mcp.add_middleware(LoggingMiddleware())
```

## Best Practices (FastMCP-Aligned)

### Client Management
- Use `get_firecrawl_client()` for stateless client creation
- No connection pooling needed - FastMCP handles concurrent requests
- Environment-based configuration only - no complex config objects
- Handle authentication errors with FastMCP ToolError

### Configuration
- Use simple environment variable functions instead of complex classes
- Validate environment early with `validate_environment()`
- Follow FastMCP patterns for environment-based configuration
- Use `get_server_info()` for server metadata

### Error Handling
- Always use `handle_firecrawl_error()` to convert to ToolError
- Use `create_tool_error()` for custom error messages
- ToolError messages are always sent to clients (no masking)
- Log errors with structured context using `log_error()`

### FastMCP Context Usage
- Accept `ctx: Context` parameter in tools for logging
- Use `await ctx.info()`, `await ctx.warning()`, `await ctx.error()` for client logging
- Context provides progress reporting and resource management
- Context enables proper FastMCP middleware integration

## Migration Guide

### Deprecated → Current Patterns

**Configuration:**
```python
# OLD (deprecated)
from firecrawl_mcp.core.config import MCPConfig
config = MCPConfig()
api_key = config.firecrawl_api_key

# NEW (recommended)
from firecrawl_mcp.core.config import get_env_bool
import os
api_key = os.getenv("FIRECRAWL_API_KEY", "")
debug = get_env_bool("FIRECRAWLER_DEBUG", False)
```

**Client Management:**
```python
# OLD (deprecated)
from firecrawl_mcp.core.client import get_client
client = await get_client()

# NEW (recommended)
from firecrawl_mcp.core.client import get_firecrawl_client
client = get_firecrawl_client()  # No await needed - synchronous
```

**Error Handling:**
```python
# OLD (deprecated)
from firecrawl_mcp.core.exceptions import MCPClientError
raise MCPClientError("Something failed")

# NEW (recommended)
from firecrawl_mcp.core.exceptions import create_tool_error
raise create_tool_error("Something failed", {"context": "additional_info"})
```

## Initialization
- FastMCP auto-configures from environment variables
- Use `validate_environment()` to check required variables early
- No complex initialization - FastMCP handles server lifecycle
- Middleware added with `mcp.add_middleware()` calls