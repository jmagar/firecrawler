"""
Pytest configuration and shared fixtures for Firecrawler MCP server tests.

This module provides shared pytest fixtures, configuration, and utilities for testing
the Firecrawler MCP server following FastMCP in-memory testing patterns.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from firecrawl_mcp.core.client import reset_client
from firecrawl_mcp.core.config import MCPConfig
from firecrawl_mcp.core.exceptions import MCPError

# Test environment configuration
TEST_CONFIG = {
    "FIRECRAWL_API_KEY": "fc-test-key-1234567890abcdef",
    "FIRECRAWL_API_URL": "https://api.firecrawl.dev",
    "FIRECRAWL_TIMEOUT": "30.0",
    "FIRECRAWL_MAX_RETRIES": "2",
    "MCP_SERVER_NAME": "Test Firecrawler MCP Server",
    "LOG_LEVEL": "DEBUG",
    "RATE_LIMIT_ENABLED": "false",
    "AUTH_ENABLED": "false",
    "CACHE_ENABLED": "false",
    "DEVELOPMENT_MODE": "true",
    "DEBUG_MODE": "true",
}


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def clean_environment():
    """Simple environment cleanup following FastMCP self-contained patterns."""
    # Reset the global client before each test
    reset_client()
    
    yield
    
    # Reset global client after test
    reset_client()


@pytest.fixture
def test_env() -> Generator[dict[str, str], None, None]:
    """Provide test environment variables."""
    with patch.dict(os.environ, TEST_CONFIG):
        yield TEST_CONFIG


@pytest.fixture
def mock_firecrawl_client():
    """Create a mock Firecrawl client for testing."""
    mock_client = Mock()

    # Mock successful responses
    mock_client.scrape.return_value = {
        "data": {
            "content": "Test content",
            "metadata": {"title": "Test Page", "url": "https://example.com"}
        }
    }

    mock_client.get_credit_usage.return_value = Mock(
        remaining=1000,
        total=2000,
        used=1000
    )

    mock_client.search.return_value = {
        "data": [
            {
                "url": "https://example.com",
                "title": "Test Result",
                "content": "Test search result content"
            }
        ]
    }

    return mock_client


@pytest.fixture
async def async_mock_firecrawl_client():
    """Create an async mock Firecrawl client for testing."""
    mock_client = AsyncMock()

    # Mock successful async responses
    mock_client.scrape.return_value = {
        "data": {
            "content": "Test content",
            "metadata": {"title": "Test Page", "url": "https://example.com"}
        }
    }

    mock_client.get_credit_usage.return_value = Mock(
        remaining=1000,
        total=2000,
        used=1000
    )

    mock_client.search.return_value = {
        "data": [
            {
                "url": "https://example.com",
                "title": "Test Result",
                "content": "Test search result content"
            }
        ]
    }

    return mock_client


@pytest.fixture
def valid_config(test_env) -> MCPConfig:
    """Create a valid MCP configuration for testing."""
    return MCPConfig()


@pytest.fixture
def invalid_config() -> MCPConfig:
    """Create an invalid MCP configuration for testing."""
    # Create config without required API key
    with patch.dict(os.environ, {}, clear=True):
        config = MCPConfig.__new__(MCPConfig)
        config.firecrawl_api_key = None
        config.firecrawl_api_url = "https://api.firecrawl.dev"
        config.firecrawl_timeout = 30.0
        config.firecrawl_max_retries = 3
        config.firecrawl_backoff_factor = 0.5
        config.server_name = "Test Server"
        config.server_version = "1.0.0"
        config.log_level = "INFO"
        config.rate_limit_enabled = True
        config.auth_enabled = False
        config.cache_enabled = True
        config.vector_search_enabled = True
        config.debug_mode = False
        config.development_mode = False
        return config


@pytest.fixture
def temp_log_file() -> Generator[Path, None, None]:
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        log_path = Path(f.name)

    yield log_path

    # Cleanup
    if log_path.exists():
        log_path.unlink()


@pytest.fixture
def basic_test_server() -> FastMCP:
    """Create a basic FastMCP server for testing following FastMCP patterns."""
    server = FastMCP("TestFirecrawlerMCP")

    @server.tool
    def test_tool(message: str) -> str:
        """A simple test tool."""
        return f"Test response: {message}"

    @server.tool
    def error_tool() -> str:
        """A tool that always raises an error."""
        raise ToolError("Test error message")

    @server.resource("test://config")
    def test_config() -> dict[str, Any]:
        """A test resource."""
        return {"test": True, "version": "1.0.0"}

    return server


# Client fixture removed - create clients within test functions using:
# async with Client(server) as client:
#     # test code here
# This follows FastMCP best practices and avoids event loop issues.


@pytest.fixture
def mock_successful_client_validation(mock_firecrawl_client):
    """Mock successful client validation."""
    with patch("firecrawl_mcp.core.client.FirecrawlClient", return_value=mock_firecrawl_client):
        yield mock_firecrawl_client


@pytest.fixture
def mock_failed_client_validation():
    """Mock failed client validation."""
    mock_client = Mock()
    mock_client.get_credit_usage.side_effect = Exception("Connection failed")

    with patch("firecrawl_mcp.core.client.FirecrawlClient", return_value=mock_client):
        yield mock_client


@pytest.fixture
def sample_scrape_response() -> dict[str, Any]:
    """Sample scrape response for testing."""
    return {
        "data": {
            "content": "# Test Page\n\nThis is test content for scraping.",
            "metadata": {
                "title": "Test Page",
                "description": "A test page for scraping",
                "url": "https://example.com",
                "statusCode": 200,
                "language": "en",
                "sourceURL": "https://example.com"
            },
            "markdown": "# Test Page\n\nThis is test content for scraping.",
            "html": "<html><head><title>Test Page</title></head><body><h1>Test Page</h1><p>This is test content for scraping.</p></body></html>",
            "rawHtml": "<html><head><title>Test Page</title></head><body><h1>Test Page</h1><p>This is test content for scraping.</p></body></html>",
            "links": ["https://example.com/page1", "https://example.com/page2"],
            "screenshot": "https://example.com/screenshot.png",
            "actions": {
                "screenshots": ["https://example.com/screenshot.png"]
            }
        }
    }


@pytest.fixture
def sample_search_response() -> dict[str, Any]:
    """Sample search response for testing."""
    return {
        "data": [
            {
                "url": "https://example.com/result1",
                "title": "First Search Result",
                "content": "Content of the first search result",
                "description": "Description of the first result"
            },
            {
                "url": "https://example.com/result2",
                "title": "Second Search Result",
                "content": "Content of the second search result",
                "description": "Description of the second result"
            }
        ]
    }


@pytest.fixture
def sample_crawl_response() -> dict[str, Any]:
    """Sample crawl response for testing."""
    return {
        "jobId": "test-job-12345",
        "status": "active",
        "url": "https://example.com",
        "createdAt": "2024-01-01T00:00:00Z",
        "completedAt": None,
        "crawlProgressData": {
            "total": 10,
            "completed": 2,
            "creditsUsed": 5
        }
    }


@pytest.fixture
def sample_vector_search_response() -> dict[str, Any]:
    """Sample vector search response for testing."""
    return {
        "data": [
            {
                "id": "doc-1",
                "content": "Sample document content for vector search",
                "metadata": {
                    "url": "https://example.com/doc1",
                    "title": "Sample Document 1",
                    "source": "web"
                },
                "similarity": 0.95
            },
            {
                "id": "doc-2",
                "content": "Another sample document for testing",
                "metadata": {
                    "url": "https://example.com/doc2",
                    "title": "Sample Document 2",
                    "source": "web"
                },
                "similarity": 0.87
            }
        ]
    }


# Utility functions for testing
def assert_mcp_error(error: Exception, expected_type: type, expected_code: str | None = None):
    """Assert that an error is of the expected MCP error type with optional code check."""
    assert isinstance(error, expected_type), f"Expected {expected_type.__name__}, got {type(error).__name__}"

    if expected_code and isinstance(error, MCPError):
        assert error.error_code == expected_code, f"Expected error code {expected_code}, got {error.error_code}"


def create_test_config(**overrides) -> dict[str, str]:
    """Create a test configuration with optional overrides."""
    config = TEST_CONFIG.copy()
    config.update(overrides)
    return config


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1) -> bool:
    """Wait for a condition to become true within a timeout."""
    elapsed = 0.0
    while elapsed < timeout:
        if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False
