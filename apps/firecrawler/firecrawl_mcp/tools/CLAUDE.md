# Tools Implementation Guide

This directory contains the 10 core Firecrawl MCP tools that expose web scraping, crawling, and AI-powered functionality through the FastMCP protocol.

## Implementation Patterns

### FastMCP Tool Decorators
```python
from fastmcp import mcp
from pydantic import BaseModel, Field

class ScrapeRequest(BaseModel):
    url: str = Field(description="URL to scrape")
    formats: list[str] = Field(default=["markdown"])

@mcp.tool()
def scrape(request: ScrapeRequest) -> str:
    """Scrape content from a single URL with advanced options."""
    # Implementation using Firecrawl SDK
```

### Error Handling
- Use `ToolError` for user-facing errors
- Catch and wrap Firecrawl SDK exceptions appropriately
- Include context in error messages (URL, operation type)
- Handle rate limits with exponential backoff

### Async Implementation
- All tools must be async-compatible
- Use centralized client manager from `firecrawl_mcp.core.client`
- Implement proper resource cleanup
- Support progress reporting for long operations

## Tool Organization

### scrape.py
- `scrape`: Single URL content extraction
- `batch_scrape`: Multiple URL processing with queuing
- `batch_status`: Monitor batch operation progress

### crawl.py  
- `crawl`: Asynchronous website crawling
- `crawl_status`: Monitor crawl job progress

### extract.py
- `extract`: AI-powered structured data extraction using LLM

### map.py
- `map`: Website URL discovery and mapping

### firesearch.py
- `firesearch`: Web search with optional content extraction

### firerag.py
- `firerag`: Vector database Q&A with configurable LLM synthesis

## Best Practices

### Parameter Validation
- Use Pydantic models for all tool parameters
- Include field descriptions for MCP parameter hints
- Set sensible defaults to reduce user friction
- Validate URLs, limits, and enum values

### Response Formatting
- Return structured data when possible
- Include operation IDs for async operations
- Provide clear progress indicators
- Format errors consistently across tools

### Performance
- Implement request caching where appropriate
- Use connection pooling for HTTP requests
- Limit concurrent operations to prevent overload
- Monitor and log performance metrics

### SDK Integration
- Import from `firecrawl_mcp.core.client` for unified client access
- Use configuration from `firecrawl_mcp.core.config`
- Handle authentication through centralized client management
- Follow SDK v2 patterns and method signatures

## Testing
- Use FastMCP in-memory testing patterns
- Mock external dependencies only when necessary
- Test error conditions and edge cases
- Validate parameter schemas and response formats