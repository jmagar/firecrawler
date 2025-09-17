# Testing Implementation Guide

This directory contains comprehensive test suites for all Firecrawl MCP server components using FastMCP in-memory testing patterns.

## Testing Patterns

### FastMCP In-Memory Testing
```python
import pytest
from fastmcp import FastMCP, Client

@pytest.mark.asyncio
async def test_scrape_tool():
    """Test scrape tool using FastMCP in-memory client."""
    # Create server with tool directly in test
    server = FastMCP("test-server")
    
    @server.tool
    def scrape(url: str, formats: list = None) -> str:
        """Test scrape tool."""
        return f"Scraped content from {url} with formats {formats}"
    
    async with Client(server) as client:
        result = await client.call_tool(
            "scrape",
            {"url": "https://example.com", "formats": ["markdown"]}
        )
        assert result.content[0].type == "text"
        assert "Scraped content from https://example.com" in result.content[0].text
```

### Inline Snapshot Testing
```python
import pytest
from inline_snapshot import snapshot
from fastmcp import FastMCP, Client

@pytest.mark.asyncio
async def test_tool_schema_generation():
    """Test that tool schemas are generated correctly using inline snapshots."""
    server = FastMCP("test-server")
    
    @server.tool
    def calculate_tax(amount: float, rate: float = 0.1) -> dict:
        """Calculate tax on an amount."""
        return {"amount": amount, "tax": amount * rate, "total": amount * (1 + rate)}
    
    tools = server.list_tools()
    schema = tools[0].inputSchema
    
    # First run: snapshot() is empty, gets auto-populated
    # Subsequent runs: compares against stored snapshot
    # Update with: pytest --inline-snapshot=fix
    assert schema == snapshot({
        "type": "object", 
        "properties": {
            "amount": {"type": "number"}, 
            "rate": {"type": "number", "default": 0.1}
        }, 
        "required": ["amount"]
    })
```

### Environment-Gated Integration Tests
```python
import os
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_scraping():
    """Integration test with real Firecrawl API."""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        pytest.skip("FIRECRAWL_API_KEY not available")
    
    # Real API testing when credentials available
    # Test implementation here
```

## Test Categories

### Core Testing (test_core.py)
- **Client Management**: SDK client initialization and configuration
- **Configuration**: Environment variable validation and defaults
- **Error Handling**: Exception hierarchy and error propagation
- **Authentication**: API key validation and client authentication

### Middleware Testing
- **test_timing.py**: Performance measurement and metrics collection
- **test_logging.py**: Log output validation and file rotation
- **test_rate_limit.py**: Rate limiting behavior and backoff logic
- **test_error_handling.py**: Error processing and response formatting

### Tool Testing
- **test_scrape.py**: Single URL scraping with various options
- **test_batch_scrape.py**: Batch operations and queue management
- **test_batch_status.py**: Batch status monitoring and progress
- **test_crawl.py**: Website crawling and job management
- **test_crawl_status.py**: Crawl status checking and progress
- **test_extract.py**: AI extraction with schema validation
- **test_map.py**: URL mapping and discovery
- **test_firesearch.py**: Web search functionality
- **test_firerag.py**: Vector search and RAG operations

### Component Testing
- **test_prompts.py**: Prompt template validation and parameterization
- **test_resources.py**: Resource access and content validation

## Best Practices

### Test Structure
- Use descriptive test names that explain the scenario
- Group related tests in test classes
- Use setup and teardown fixtures for common initialization
- Implement parametrized tests for multiple input scenarios

### Async Testing
- Use `@pytest.mark.asyncio` for async test functions
- Implement proper async resource cleanup
- Test concurrent operation handling
- Validate async error propagation

### Error Testing
- Test all error conditions and edge cases
- Validate error message format and content
- Test error recovery and retry mechanisms
- Ensure proper error logging and reporting

### Performance Testing
- Include performance benchmarks for critical operations
- Test timeout handling and cancellation
- Validate resource cleanup under load
- Monitor memory usage in long-running tests

## Test Configuration

### Environment Setup
```python
# conftest.py
import pytest
from firecrawl_mcp.core.config import Config

@pytest.fixture
def test_config():
    """Provide test configuration with safe defaults."""
    return Config(
        firecrawl_api_key="test-key",
        firecrawl_api_base_url="https://api.firecrawl.dev",
        log_level="DEBUG"
    )
```

### Fixtures
- **server fixtures**: FastMCP server instances with tools defined directly in fixtures
- **mock_firecrawl_client**: Mocked SDK client for unit tests
- **test_config**: Configuration with test-safe defaults
- **temp_logs**: Temporary log directory for testing

### Test Data
- **sample_urls**: Collection of test URLs for scraping
- **mock_responses**: Predefined API response fixtures
- **test_schemas**: JSON schemas for extraction testing
- **error_scenarios**: Predefined error conditions for testing

## Integration Testing

### API Integration
- Gate tests with environment variable checks
- Use real API endpoints when credentials available
- Implement fallback to mock responses when unavailable
- Test both cloud and self-hosted API configurations

### Database Integration
- Test vector search functionality with real database
- Validate embedding generation and storage
- Test search filtering and ranking
- Verify data consistency and integrity

### End-to-End Testing
- Test complete workflows from tool call to response
- Validate middleware processing chains
- Test error recovery across component boundaries
- Verify logging and metrics collection

## Performance Testing
- Benchmark critical path operations
- Test concurrent request handling
- Validate memory usage and cleanup
- Monitor resource utilization under load