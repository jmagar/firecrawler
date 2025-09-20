# MCP (Model Context Protocol) Development Guide

## Overview
The Firecrawl MCP server (`apps/firecrawler`) exposes Firecrawl API functionality to LLM clients using the Model Context Protocol.

## Architecture
- **Framework**: FastMCP (modern async patterns)
- **Components**: Tools, Resources, Prompts
- **Language**: Python 3.11+

## Key Development Patterns

### Function Signatures
All MCP functions must:
- Be async functions
- Accept Context parameter
- Return typed dictionaries

```python
async def my_tool(param: str, ctx: Context) -> dict[str, Any]:
    await ctx.info("Executing tool")
    return {"result": "success"}
```

### Type Annotations
- Use modern Python typing: `dict[str, Any]` NOT `Dict[str, Any]`
- Always include return type hints
- Import Context from fastmcp

### Resource Registration
```python
def setup_resources(server_mcp: FastMCP) -> None:
    server_mcp.resource(
        "firecrawl://resource/path",
        name="Resource Name",
        description="Clear description",
        mime_type="application/json",
        tags={"tag1", "tag2"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True
        }
    )(resource_function)
```

### Error Handling
```python
from fastmcp.exceptions import ResourceError, ToolError

try:
    result = await operation()
except SpecificError as e:
    await ctx.error(f"Operation failed: {e}")
    raise ToolError(f"Failed: {e}")
```

### Logging
- Use Context for all logging
- `await ctx.info()` for information
- `await ctx.warning()` for warnings  
- `await ctx.error()` for errors

## Module Structure
- `tools/` - Action functions (scraping, crawling)
- `resources/` - Read-only data (config, status)
- `prompts/` - Reusable prompt templates
- `utils/` - Shared utilities

## Development Workflow
1. Implement core async function with Context
2. Add comprehensive error handling
3. Register with full metadata
4. Add Context-based logging
5. Test with MCP clients
6. Update module CLAUDE.md if needed

## Testing Considerations
- Test with various MCP clients
- Verify error handling paths
- Check metadata completeness
- Validate async operations
- Ensure proper Context usage

## Common Pitfalls to Avoid
- Forgetting async keyword
- Missing Context parameter
- Using old typing (Dict vs dict)
- Generic error messages
- Missing component metadata
- Synchronous operations in async context