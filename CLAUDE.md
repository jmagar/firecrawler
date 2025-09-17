Firecrawl is a web scraper API. The directory you have access to is a monorepo:
 - `apps/api` has the actual API and worker code
 - `apps/js-sdk`, `apps/python-sdk`, and `apps/rust-sdk` are various SDKs

When making changes to the API, here are the general steps you should take:
1. Write some end-to-end tests that assert your win conditions, if they don't already exist
  - 1 happy path (more is encouraged if there are multiple happy paths with significantly different code paths taken)
  - 1+ failure path(s)
  - Generally, E2E (called `snips` in the API) is always preferred over unit testing.
  - In the API, always use `scrapeTimeout` from `./lib` to set the timeout you use for scrapes.
  - These tests will be ran on a variety of configurations. You should gate tests in the following manner:
    - If it requires fire-engine: `!process.env.TEST_SUITE_SELF_HOSTED`
    - If it requires AI: `!process.env.TEST_SUITE_SELF_HOSTED || process.env.OPENAI_API_KEY || process.env.OLLAMA_BASE_URL`
2. Write code to achieve your win conditions
3. Run your tests using `pnpm harness jest ...`
  - `pnpm harness` is a command that gets the API server and workers up for you to run the tests. Don't try to `pnpm start` manually.
  - The full test suite takes a long time to run, so you should try to only execute the relevant tests locally, and let CI run the full test suite.
4. Push to a branch, open a PR, and let CI run to verify your win condition.
Keep these steps in mind while building your TODO list.

## MCP (Model Context Protocol) Development

The `apps/firecrawler` directory contains a complete MCP server implementation that exposes Firecrawl API functionality to LLM clients. This section covers the essential patterns for developing MCP components in this project.

### MCP Architecture Overview

The MCP server provides three main component types:
- **Tools**: Functions that LLMs can call to perform actions (scraping, crawling, etc.)
- **Resources**: Read-only data sources that LLMs can access (configuration, status, logs)
- **Prompts**: Reusable prompt templates for common tasks

### Core Development Patterns

All MCP components follow modern FastMCP patterns with these key requirements:

#### Function Signatures
```python
# Tools and Resources use async functions with Context
async def my_tool(param: str, ctx: Context) -> dict[str, Any]:
    """Tool description."""
    await ctx.info("Tool executed")  # Logging via context
    return {"result": "success"}

async def my_resource(ctx: Context) -> dict[str, Any]:
    """Resource description."""
    await ctx.info("Resource accessed")
    return {"data": "value"}
```

#### Type Annotations
- Use modern Python typing: `dict[str, Any]` not `Dict[str, Any]`
- Always type hint return values and parameters
- Import Context from `fastmcp`

#### Resource Registration Pattern
```python
def setup_resources(server_mcp: FastMCP) -> None:
    """Register all resources with full metadata."""
    server_mcp.resource(
        "firecrawl://config/server",
        name="Server Configuration",
        description="Current server configuration and environment variables",
        mime_type="application/json",
        tags={"configuration", "server"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True
        }
    )(get_server_config)
```

#### Error Handling
```python
from fastmcp.exceptions import ResourceError, ToolError

async def my_function(ctx: Context) -> dict[str, Any]:
    try:
        # Operation logic
        result = await some_operation()
        return {"result": result}
    except SomeSpecificError as e:
        await ctx.error(f"Operation failed: {e}")
        raise ToolError(f"Failed to complete operation: {e}")
```

### Module-Specific Documentation

For detailed implementation guides, see the CLAUDE.md files in each module:
- **Resources**: `apps/firecrawler/firecrawl_mcp/resources/CLAUDE.md`
- **Tools**: `apps/firecrawler/firecrawl_mcp/tools/CLAUDE.md` 
- **Prompts**: `apps/firecrawler/firecrawl_mcp/prompts/CLAUDE.md`

### Development Workflow for MCP Components

When developing MCP components, follow this workflow:

1. **Implement the core function** with proper async/Context signature
2. **Add comprehensive error handling** with appropriate MCP exceptions
3. **Register with full metadata** including name, description, tags, annotations
4. **Add logging via Context** for debugging and monitoring
5. **Test with MCP clients** to verify functionality
6. **Update module-specific documentation** if adding new patterns

### Key Differences from Regular API Development

- **Context Parameter**: All MCP functions receive a `Context` object for logging and request metadata
- **Async Required**: MCP functions must be async for proper integration
- **Rich Metadata**: Components include detailed metadata for LLM discovery and usage
- **Error Handling**: Use specific MCP exceptions rather than generic HTTP responses
- **Resource URI Schemes**: Use consistent URI schemes like `firecrawl://` for resource identification