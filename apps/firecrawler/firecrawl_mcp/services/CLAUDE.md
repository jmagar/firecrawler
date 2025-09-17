# FastMCP Tools Guide

This directory provides guidance for implementing Firecrawl functionality using FastMCP's simple, decorator-based patterns.

## FastMCP Tool Patterns

FastMCP emphasizes simplicity through decorated functions rather than complex service hierarchies. All business logic should be implemented directly in `@tool` functions with `Context` parameter injection for dependencies.

### Basic Tool Pattern

```python
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from typing import Annotated
from pydantic import Field

from ..core.client import get_client

mcp = FastMCP("FirecrawlMCP")

@mcp.tool
async def scrape_url(
    url: Annotated[str, Field(description="URL to scrape")],
    options: dict | None = None,
    ctx: Context
) -> dict:
    """Scrape a single URL and return structured content."""
    await ctx.info(f"Starting scrape of: {url}")
    
    try:
        client = get_client()
        result = await client.scrape(url, **(options or {}))
        
        await ctx.info("Scraping completed successfully")
        return result
        
    except Exception as e:
        await ctx.error(f"Scraping failed: {e}")
        raise ToolError(f"Failed to scrape {url}: {e}")
```

### Context Parameter Injection

FastMCP uses the `Context` parameter to provide access to:
- **Logging**: `ctx.debug()`, `ctx.info()`, `ctx.warning()`, `ctx.error()`
- **Progress Reporting**: `ctx.report_progress(progress, total)`
- **Resource Access**: `ctx.read_resource(uri)`
- **State Management**: `ctx.set_state(key, value)`, `ctx.get_state(key)`

```python
@mcp.tool
async def crawl_website(
    url: Annotated[str, "Website URL to crawl"],
    max_pages: Annotated[int, Field(ge=1, le=100)] = 10,
    ctx: Context
) -> dict:
    """Crawl a website and return discovered URLs."""
    await ctx.info(f"Starting crawl of {url} (max {max_pages} pages)")
    
    client = get_client()
    discovered_urls = []
    
    for i in range(max_pages):
        await ctx.report_progress(i, max_pages)
        # Crawling logic here
        
    await ctx.report_progress(max_pages, max_pages)
    return {"discovered_urls": discovered_urls, "total": len(discovered_urls)}
```

## Cross-Cutting Concerns with Middleware

FastMCP handles logging, metrics, timing, and error handling through middleware rather than built-in service infrastructure.

### Timing and Performance Monitoring

```python
from fastmcp.server.middleware.timing import TimingMiddleware, DetailedTimingMiddleware

# Add timing middleware for performance monitoring
mcp.add_middleware(TimingMiddleware())

# Or use detailed timing for operation-specific metrics
mcp.add_middleware(DetailedTimingMiddleware())
```

### Logging and Observability

```python
from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware

# Human-readable logging
mcp.add_middleware(LoggingMiddleware(
    include_payloads=True,
    max_payload_length=1000
))

# JSON-structured logging for log aggregation
mcp.add_middleware(StructuredLoggingMiddleware(include_payloads=True))
```

### Error Handling

```python
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

# Centralized error handling and transformation
mcp.add_middleware(ErrorHandlingMiddleware(
    include_traceback=True,
    transform_errors=True
))
```

### Rate Limiting

```python
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

# Protect against abuse
mcp.add_middleware(RateLimitingMiddleware(
    max_requests_per_second=10.0,
    burst_capacity=20
))
```

## Tool Implementation Examples

### Content Processing Tools

```python
@mcp.tool
async def extract_structured_data(
    url: str,
    schema: dict,
    ctx: Context
) -> dict:
    """Extract structured data from a webpage using AI."""
    await ctx.info(f"Extracting data from {url}")
    
    client = get_client()
    content = await client.scrape(url)
    
    # AI extraction logic here
    extracted_data = await client.extract(content, schema)
    
    return extracted_data

@mcp.tool  
async def search_web(
    query: Annotated[str, "Search query"],
    max_results: Annotated[int, Field(ge=1, le=20)] = 10,
    ctx: Context
) -> list[dict]:
    """Search the web and return results."""
    await ctx.info(f"Searching for: {query}")
    
    client = get_client()
    results = await client.search(query, limit=max_results)
    
    return results
```

### Batch Processing Tools

```python
@mcp.tool
async def batch_scrape(
    urls: list[str],
    options: dict | None = None,
    ctx: Context
) -> dict:
    """Scrape multiple URLs in batch."""
    total_urls = len(urls)
    await ctx.info(f"Starting batch scrape of {total_urls} URLs")
    
    client = get_client()
    results = []
    errors = []
    
    for i, url in enumerate(urls):
        await ctx.report_progress(i, total_urls)
        
        try:
            result = await client.scrape(url, **(options or {}))
            results.append({"url": url, "data": result})
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
            await ctx.warning(f"Failed to scrape {url}: {e}")
    
    await ctx.report_progress(total_urls, total_urls)
    
    return {
        "successful": results,
        "failed": errors,
        "total_processed": total_urls,
        "success_rate": len(results) / total_urls
    }
```

## Input Validation with Type Annotations

Use Pydantic's validation instead of custom validation infrastructure:

```python
from typing import Literal
from pydantic import Field, HttpUrl

@mcp.tool
async def scrape_with_options(
    url: Annotated[HttpUrl, "Valid HTTP/HTTPS URL"],
    format: Literal["markdown", "html", "text"] = "markdown",
    wait_for: Annotated[int, Field(ge=0, le=30000)] = 0,
    include_links: bool = True,
    ctx: Context
) -> dict:
    """Scrape URL with specific formatting and wait options."""
    options = {
        "formats": [format],
        "waitFor": wait_for,
        "includeLinks": include_links
    }
    
    client = get_client()
    return await client.scrape(str(url), **options)
```

## Error Handling Best Practices

Use simple `ToolError` exceptions rather than complex error infrastructure:

```python
from fastmcp.exceptions import ToolError

@mcp.tool
async def process_document(url: str, ctx: Context) -> dict:
    """Process a document with proper error handling."""
    
    # Validate input
    if not url.startswith(('http://', 'https://')):
        raise ToolError("Invalid URL: must start with http:// or https://")
    
    try:
        client = get_client()
        result = await client.scrape(url)
        
        if not result:
            raise ToolError(f"No content found at {url}")
            
        return result
        
    except Exception as e:
        # Let middleware handle logging, just raise appropriate error
        raise ToolError(f"Failed to process document: {e}")
```

## Configuration Access

Access configuration through global accessors rather than dependency injection:

```python
from ..core.config import get_config

@mcp.tool
async def get_service_status(ctx: Context) -> dict:
    """Get current service configuration and status."""
    config = get_config()
    
    return {
        "api_key_configured": bool(config.api_key),
        "base_url": config.base_url,
        "max_retries": config.max_retries,
        "timeout": config.timeout
    }
```

## Testing Tools

Test tools as simple functions rather than complex service mocks:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_scrape_tool():
    """Test scrape tool functionality."""
    mock_client = AsyncMock()
    mock_client.scrape.return_value = {"content": "test content"}
    
    with patch('firecrawl_mcp.tools.get_client', return_value=mock_client):
        # Test the actual tool function
        result = await scrape_url("https://example.com", None, mock_context)
        
    assert result["content"] == "test content"
    mock_client.scrape.assert_called_once()
```

## Migration from Service Pattern

If migrating from service-based patterns:

1. **Extract business logic** from service methods to `@tool` functions
2. **Replace constructor injection** with Context parameter injection  
3. **Remove service response wrappers** - return data directly
4. **Move cross-cutting concerns** to middleware
5. **Use ToolError** for error handling instead of complex error conversion

This approach aligns with FastMCP's philosophy of simplicity and direct implementation.