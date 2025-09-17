# Testing Framework Usage and Best Practices

Firecrawler MCP server uses FastMCP in-memory testing patterns for comprehensive test coverage. This guide covers testing framework usage, patterns, and best practices for developing reliable test suites.

## Testing Architecture

### FastMCP In-Memory Testing

The primary testing approach uses FastMCP's in-memory transport, providing deterministic, fast tests without network overhead:

```python
from fastmcp import Client
from firecrawl_mcp.server import create_server

async def test_scrape_tool():
    """Test scrape tool using in-memory client."""
    server = create_server()
    
    async with Client(server) as client:
        result = await client.call_tool(
            "scrape",
            {"url": "https://example.com", "formats": ["markdown"]}
        )
        assert result.is_error is False
        assert "content" in result.content[0].text
```

**Benefits:**
- Tests complete in milliseconds, not seconds
- Deterministic behavior without network variability  
- Full debugging support with breakpoints
- No deployment or service management required

### Test Organization

Test files mirror the source directory structure:

```
firecrawl_mcp/tests/
├── conftest.py              # Pytest configuration and fixtures
├── test_core.py             # Core client and configuration tests
├── test_timing.py           # Timing middleware tests
├── test_logging.py          # Logging middleware tests
├── test_rate_limit.py       # Rate limiting tests
├── test_error_handling.py   # Error handling tests
├── test_scrape.py           # Scraping tool tests
├── test_batch_scrape.py     # Batch operations tests
├── test_batch_status.py     # Batch status monitoring tests
├── test_crawl.py            # Crawling functionality tests
├── test_crawl_status.py     # Crawl status checking tests
├── test_extract.py          # Extraction tool tests
├── test_map.py              # Mapping tool tests
├── test_firesearch.py       # Search tool tests
├── test_firerag.py          # Vector search tests
├── test_prompts.py          # Prompt template tests
└── test_resources.py        # Resource access tests
```

## Test Configuration

### Pytest Configuration (`conftest.py`)

```python
import pytest
import os
import tempfile
from pathlib import Path
from firecrawl_mcp.core.config import Config
from firecrawl_mcp.server import create_server

@pytest.fixture
def test_config():
    """Provide test configuration with safe defaults."""
    return Config(
        firecrawl_api_key="test-key-123",
        firecrawl_api_base_url="https://api.firecrawl.dev",
        log_level="DEBUG",
        rate_limit_requests=1000,  # High limit for testing
        performance_threshold_ms=10000
    )

@pytest.fixture
def temp_logs():
    """Provide temporary log directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_dir = Path(temp_dir) / "logs"
        log_dir.mkdir()
        yield log_dir

@pytest.fixture
async def test_server(test_config):
    """Create test server with mocked configuration."""
    server = create_server()
    # Configure with test settings
    server.config = test_config
    return server

@pytest.fixture
def mock_api_responses():
    """Provide mock API response data for testing."""
    return {
        "scrape_success": {
            "success": True,
            "data": {
                "markdown": "# Test Page\n\nThis is test content.",
                "metadata": {"title": "Test Page", "description": "Test"}
            }
        },
        "batch_queued": {
            "success": True,
            "id": "batch_test_123",
            "status": "processing"
        },
        "crawl_started": {
            "success": True,
            "id": "crawl_test_456",
            "status": "scraping"
        }
    }
```

### Environment-Gated Integration Tests

```python
import os
import pytest

@pytest.mark.skipif(
    not os.getenv("FIRECRAWL_API_KEY"),
    reason="Integration tests require FIRECRAWL_API_KEY"
)
@pytest.mark.integration
async def test_real_api_scraping():
    """Integration test with real Firecrawl API."""
    from firecrawl_mcp.core.client import get_firecrawl_client
    
    client = get_firecrawl_client()
    result = await client.scrape("https://example.com")
    
    assert result.success is True
    assert result.data is not None
    assert "markdown" in result.data

@pytest.mark.skipif(
    not os.getenv("FIRECRAWL_API_KEY") or not os.getenv("VECTOR_DB_URL"),
    reason="Vector tests require API key and database"
)
@pytest.mark.integration
async def test_vector_search_integration():
    """Test vector search with real database."""
    # Test with actual vector database
    pass
```

## Core Testing Patterns

### 1. Tool Testing

```python
import pytest
from fastmcp import Client
from firecrawl_mcp.server import create_server

class TestScrapeTools:
    @pytest.fixture
    async def server(self, test_config):
        server = create_server()
        server.config = test_config
        return server
    
    async def test_scrape_basic_functionality(self, server):
        """Test basic scrape tool functionality."""
        async with Client(server) as client:
            result = await client.call_tool(
                "scrape",
                {
                    "url": "https://example.com",
                    "formats": ["markdown"],
                    "onlyMainContent": True
                }
            )
            
            assert result.is_error is False
            assert len(result.content) > 0
            assert "markdown" in result.content[0].text.lower()
    
    async def test_scrape_invalid_url(self, server):
        """Test scrape tool with invalid URL."""
        async with Client(server) as client:
            result = await client.call_tool(
                "scrape",
                {"url": "not-a-valid-url", "formats": ["markdown"]}
            )
            
            assert result.is_error is True
            assert "invalid url" in result.content[0].text.lower()
    
    @pytest.mark.parametrize("format_type", ["markdown", "html", "text"])
    async def test_scrape_format_options(self, server, format_type):
        """Test scrape tool with different format options."""
        async with Client(server) as client:
            result = await client.call_tool(
                "scrape",
                {"url": "https://example.com", "formats": [format_type]}
            )
            
            assert result.is_error is False
            assert format_type in result.content[0].text
```

### 2. Middleware Testing

```python
import time
import pytest
from unittest.mock import AsyncMock, patch
from firecrawl_mcp.middleware.timing import TimingMiddleware
from fastmcp.server.middleware import MiddlewareContext

class TestTimingMiddleware:
    @pytest.fixture
    def timing_middleware(self):
        return TimingMiddleware()
    
    async def test_request_timing_measurement(self, timing_middleware):
        """Test that request timing is accurately measured."""
        mock_context = MiddlewareContext(
            method="tools/call",
            source="client",
            type="request",
            message=AsyncMock(),
            timestamp=time.time()
        )
        
        async def mock_call_next(context):
            # Simulate processing time
            await asyncio.sleep(0.1)
            return {"success": True}
        
        start_time = time.time()
        result = await timing_middleware.on_request(mock_context, mock_call_next)
        end_time = time.time()
        
        assert result["success"] is True
        # Verify timing was approximately correct
        assert 0.09 <= (end_time - start_time) <= 0.15
    
    async def test_timing_error_handling(self, timing_middleware):
        """Test timing middleware handles errors correctly."""
        mock_context = MiddlewareContext(
            method="tools/call",
            source="client", 
            type="request",
            message=AsyncMock(),
            timestamp=time.time()
        )
        
        async def mock_call_next_error(context):
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await timing_middleware.on_request(mock_context, mock_call_next_error)
```

### 3. Error Testing

```python
class TestErrorHandling:
    async def test_tool_error_propagation(self, server):
        """Test that tool errors are properly propagated."""
        async with Client(server) as client:
            # Test with invalid parameters
            result = await client.call_tool(
                "scrape",
                {"url": ""}  # Empty URL should cause error
            )
            
            assert result.is_error is True
            assert "url" in result.content[0].text.lower()
    
    async def test_rate_limit_error(self, server):
        """Test rate limiting error responses."""
        # Configure server with very low rate limit
        server.middleware[2].requests_per_minute = 1
        
        async with Client(server) as client:
            # First request should succeed
            result1 = await client.call_tool("scrape", {"url": "https://example.com"})
            assert result1.is_error is False
            
            # Second immediate request should fail
            result2 = await client.call_tool("scrape", {"url": "https://example.com"})
            assert result2.is_error is True
            assert "rate limit" in result2.content[0].text.lower()
    
    async def test_network_error_handling(self, server):
        """Test handling of network-related errors."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = aiohttp.ClientConnectorError(
                connection_key=None, 
                os_error=OSError("Connection refused")
            )
            
            async with Client(server) as client:
                result = await client.call_tool(
                    "scrape", 
                    {"url": "https://unreachable.example.com"}
                )
                
                assert result.is_error is True
                assert "connection" in result.content[0].text.lower()
```

### 4. Performance Testing

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

class TestPerformance:
    async def test_concurrent_requests(self, server):
        """Test server performance under concurrent load."""
        async with Client(server) as client:
            # Create multiple concurrent requests
            tasks = []
            for i in range(10):
                task = client.call_tool(
                    "scrape",
                    {"url": f"https://example.com/page{i}"}
                )
                tasks.append(task)
            
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time
            
            # All requests should complete in reasonable time
            assert duration < 5.0
            
            # Most requests should succeed (some may fail due to rate limiting)
            successful = sum(1 for r in results if not r.is_error)
            assert successful >= 5
    
    async def test_memory_usage(self, server):
        """Test memory usage remains reasonable under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        async with Client(server) as client:
            # Perform many operations
            for _ in range(100):
                await client.call_tool(
                    "scrape",
                    {"url": "https://example.com", "formats": ["markdown"]}
                )
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
```

## Testing Best Practices

### 1. Test Structure and Organization

```python
class TestFeatureGroup:
    """Group related tests in classes for better organization."""
    
    @pytest.fixture(autouse=True)
    async def setup_method(self):
        """Setup run before each test method."""
        self.test_data = {}
        self.cleanup_tasks = []
    
    async def teardown_method(self):
        """Cleanup after each test method."""
        for task in self.cleanup_tasks:
            await task()
    
    async def test_specific_behavior(self):
        """Test one specific behavior with clear assertions."""
        # Arrange
        input_data = {"url": "https://example.com"}
        
        # Act
        result = await self.perform_action(input_data)
        
        # Assert
        assert result.success is True
        assert result.data is not None
        assert "expected_content" in result.data
```

### 2. Effective Mocking

```python
from unittest.mock import AsyncMock, patch, MagicMock

class TestWithMocks:
    @patch('firecrawl_mcp.core.client.FirecrawlApp')
    async def test_with_mocked_client(self, mock_firecrawl_class):
        """Test with mocked Firecrawl client."""
        # Setup mock
        mock_client = AsyncMock()
        mock_client.scrape.return_value = MagicMock(
            success=True,
            data={"markdown": "# Test Content"}
        )
        mock_firecrawl_class.return_value = mock_client
        
        # Test
        async with Client(server) as client:
            result = await client.call_tool("scrape", {"url": "https://example.com"})
        
        # Verify mock was called correctly
        mock_client.scrape.assert_called_once_with("https://example.com")
        assert result.is_error is False
```

### 3. Data-Driven Testing

```python
@pytest.mark.parametrize("url,expected_success", [
    ("https://example.com", True),
    ("https://httpbin.org/html", True),
    ("http://localhost:99999", False),  # Connection refused
    ("not-a-url", False),  # Invalid URL
    ("", False),  # Empty URL
])
async def test_scrape_various_urls(server, url, expected_success):
    """Test scrape tool with various URL inputs."""
    async with Client(server) as client:
        result = await client.call_tool("scrape", {"url": url})
        
        if expected_success:
            assert result.is_error is False
        else:
            assert result.is_error is True
```

### 4. Async Resource Management

```python
class TestAsyncResources:
    @pytest.fixture
    async def database_connection(self):
        """Async fixture for database connection."""
        conn = await asyncpg.connect("postgresql://test_db")
        try:
            yield conn
        finally:
            await conn.close()
    
    async def test_with_database(self, database_connection):
        """Test that properly manages async resources."""
        # Use database connection
        result = await database_connection.fetchval("SELECT 1")
        assert result == 1
        
        # Connection cleanup handled by fixture
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest firecrawl_mcp/tests/test_scrape.py

# Run tests with specific marker
uv run pytest -m "not integration"

# Run with coverage report
uv run pytest --cov=firecrawl_mcp --cov-report=html

# Run with detailed output
uv run pytest -v -s
```

### Test Markers

```bash
# Skip integration tests (faster for development)
uv run pytest -m "not integration"

# Run only integration tests
uv run pytest -m integration

# Skip tests requiring external processes
uv run pytest -m "not client_process"

# Run performance tests
uv run pytest -m performance
```

### Parallel Test Execution

```bash
# Run tests in parallel (requires pytest-xdist)
uv run pytest -n auto

# Run with specific number of workers
uv run pytest -n 4
```

## Troubleshooting Tests

### Common Issues

**Tests Hanging:**
- Check for unclosed async resources
- Verify proper client cleanup in test fixtures
- Look for deadlocks in concurrent operations

**Flaky Tests:**
- Add appropriate timeouts for async operations
- Use deterministic test data instead of random values
- Properly mock external dependencies

**Memory Leaks:**
- Ensure all async contexts are properly closed
- Check for circular references in test fixtures
- Monitor memory usage in long-running test suites

### Debug Mode

```bash
# Run with debug logging
export FIRECRAWLER_LOG_LEVEL=DEBUG
uv run pytest -v -s

# Drop into debugger on failure
uv run pytest --pdb

# Stop on first failure
uv run pytest -x
```

## Continuous Integration

### GitHub Actions Configuration

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install uv
        uv sync
    
    - name: Run unit tests
      run: uv run pytest -m "not integration" --cov=firecrawl_mcp
    
    - name: Run integration tests
      if: env.FIRECRAWL_API_KEY
      run: uv run pytest -m integration
      env:
        FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
```

This comprehensive testing framework ensures reliable, maintainable test suites that provide confidence in the Firecrawler MCP server implementation while following FastMCP best practices.