"""
Tests for search tools in the Firecrawler MCP server.

This module tests the firesearch tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import (
    ImageSearchResult,
    NewsSearchResult,
    ScrapeOptions,
    SearchData,
    WebSearchResult,
)
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.firesearch import register_firesearch_tools


class TestFiresearchTools:
    """Test suite for firesearch tools."""

    @pytest.fixture
    def firesearch_server(self, test_env):
        """Create FastMCP server with firesearch tools registered."""
        server = FastMCP("TestFiresearchServer")
        register_firesearch_tools(server)
        return server

    @pytest.fixture
    async def firesearch_client(self, firesearch_server):
        """Create MCP client for firesearch tools."""
        async with Client(firesearch_server) as client:
            yield client

    @pytest.fixture
    def mock_search_data(self):
        """Mock comprehensive search response."""
        return SearchData(
            web=[
                WebSearchResult(
                    url="https://example.com/article1",
                    title="Python Programming Guide",
                    description="Comprehensive guide to Python programming with examples and best practices.",
                    content="# Python Programming Guide\n\nThis guide covers Python fundamentals...",
                    snippet="Learn Python programming with this comprehensive guide covering syntax, data structures, and best practices.",
                    position=1
                ),
                WebSearchResult(
                    url="https://docs.python.org/3/",
                    title="Python 3 Documentation",
                    description="Official Python 3 documentation with tutorials and reference materials.",
                    content="# Python 3 Documentation\n\nWelcome to the Python documentation...",
                    snippet="Official documentation for Python 3 programming language.",
                    position=2
                )
            ],
            news=[
                NewsSearchResult(
                    url="https://news.example.com/python-update",
                    title="Python 3.12 Released with New Features",
                    description="Latest Python release brings performance improvements and new syntax features.",
                    content="# Python 3.12 Released\n\nThe Python development team announced...",
                    snippet="Python 3.12 introduces significant performance improvements and new language features.",
                    published_date="2024-01-15T10:00:00Z",
                    source="Tech News"
                )
            ],
            images=[
                ImageSearchResult(
                    url="https://images.example.com/python-logo.png",
                    title="Python Logo",
                    description="Official Python programming language logo",
                    thumbnail_url="https://images.example.com/thumb/python-logo.png",
                    alt_text="Python programming language logo",
                    width=512,
                    height=512
                )
            ]
        )

    @pytest.fixture
    def mock_web_only_search_data(self):
        """Mock search response with only web results."""
        return SearchData(
            web=[
                WebSearchResult(
                    url="https://example.com/tutorial",
                    title="Web Development Tutorial",
                    description="Learn web development with modern frameworks and tools.",
                    snippet="Complete tutorial on modern web development techniques.",
                    position=1
                )
            ],
            news=None,
            images=None
        )

    @pytest.fixture
    def mock_github_search_data(self):
        """Mock search response with GitHub category results."""
        return SearchData(
            web=[
                WebSearchResult(
                    url="https://github.com/python/cpython",
                    title="python/cpython: The Python programming language",
                    description="The Python programming language source code repository",
                    snippet="Official CPython implementation repository on GitHub",
                    position=1
                ),
                WebSearchResult(
                    url="https://github.com/requests/requests",
                    title="requests/requests: Python HTTP library",
                    description="A simple, yet elegant HTTP library for Python",
                    snippet="HTTP library for Python - elegant and simple",
                    position=2
                )
            ]
        )


class TestFiresearchBasicFunctionality(TestFiresearchTools):
    """Test basic firesearch functionality."""

    async def test_firesearch_basic_success(self, firesearch_client, mock_search_data):
        """Test successful basic web search."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "Python programming"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "Python Programming Guide" in response_data
            assert "Python 3.12 Released" in response_data
            assert "Python Logo" in response_data

            # Verify default parameters
            mock_client.search.assert_called_once()
            call_args = mock_client.search.call_args[1]
            assert call_args["query"] == "Python programming"
            assert call_args["sources"] == ["web"]
            assert call_args["limit"] == 5

    async def test_firesearch_web_only(self, firesearch_client, mock_web_only_search_data):
        """Test search with only web sources."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_web_only_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "web development",
                "sources": ["web"],
                "limit": 3
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "Web Development Tutorial" in response_data

            call_args = mock_client.search.call_args[1]
            assert call_args["sources"] == ["web"]
            assert call_args["limit"] == 3

    async def test_firesearch_multiple_sources(self, firesearch_client, mock_search_data):
        """Test search with multiple source types."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "Python programming",
                "sources": ["web", "news", "images"],
                "limit": 10
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "3 total results" in response_data

            call_args = mock_client.search.call_args[1]
            assert call_args["sources"] == ["web", "news", "images"]
            assert call_args["limit"] == 10

    async def test_firesearch_with_location(self, firesearch_client, mock_search_data):
        """Test search with geographic location filter."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "Python jobs",
                "location": "San Francisco, CA"
            })

            assert result.content[0].type == "text"

            call_args = mock_client.search.call_args[1]
            assert call_args["location"] == "San Francisco, CA"

    async def test_firesearch_with_time_filter(self, firesearch_client, mock_search_data):
        """Test search with time-based filters."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "Python news",
                "tbs": "qdr:w",  # Past week
                "sources": ["news"]
            })

            assert result.content[0].type == "text"

            call_args = mock_client.search.call_args[1]
            assert call_args["tbs"] == "qdr:w"

    async def test_firesearch_with_categories(self, firesearch_client, mock_github_search_data):
        """Test search with category filters."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_github_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "Python libraries",
                "categories": ["github"]
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "github.com" in response_data

            call_args = mock_client.search.call_args[1]
            assert call_args["categories"] == ["github"]

    async def test_firesearch_with_scraping(self, firesearch_client, mock_search_data):
        """Test search with content scraping enabled."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            scrape_options = ScrapeOptions(
                formats=["markdown"],
                onlyMainContent=True
            )

            result = await firesearch_client.call_tool("firesearch", {
                "query": "Python tutorial",
                "scrape_options": scrape_options.model_dump()
            })

            assert result.content[0].type == "text"

            call_args = mock_client.search.call_args[1]
            assert call_args["scrape_options"] is not None

    async def test_firesearch_with_full_options(self, firesearch_client, mock_search_data):
        """Test search with comprehensive options."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await firesearch_client.call_tool("firesearch", {
                "query": "machine learning Python",
                "sources": ["web", "news"],
                "categories": ["research"],
                "limit": 20,
                "location": "United States",
                "tbs": "qdr:m",
                "ignore_invalid_urls": True,
                "timeout": 120000
            })

            assert result.content[0].type == "text"

            call_args = mock_client.search.call_args[1]
            assert call_args["query"] == "machine learning Python"
            assert call_args["sources"] == ["web", "news"]
            assert call_args["categories"] == ["research"]
            assert call_args["limit"] == 20
            assert call_args["location"] == "United States"
            assert call_args["tbs"] == "qdr:m"
            assert call_args["ignore_invalid_urls"] is True
            assert call_args["timeout"] == 120000


class TestFiresearchValidation(TestFiresearchTools):
    """Test firesearch parameter validation."""

    async def test_firesearch_empty_query_error(self, firesearch_client):
        """Test search with empty query."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {"query": ""})

        assert "Search query cannot be empty" in str(exc_info.value)

    async def test_firesearch_whitespace_only_query_error(self, firesearch_client):
        """Test search with whitespace-only query."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {"query": "   "})

        assert "Search query cannot be empty" in str(exc_info.value)

    async def test_firesearch_query_length_validation(self, firesearch_client):
        """Test search query length validation."""
        long_query = "x" * 501
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {"query": long_query})

        assert "validation" in str(exc_info.value).lower()

    async def test_firesearch_invalid_source_types(self, firesearch_client):
        """Test search with invalid source types."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "sources": ["invalid_source"]
            })

        assert "Invalid source type" in str(exc_info.value)

    async def test_firesearch_invalid_source_type_format(self, firesearch_client):
        """Test search with non-string source types."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "sources": [123]
            })

        assert "Source must be a string" in str(exc_info.value)

    async def test_firesearch_invalid_category_types(self, firesearch_client):
        """Test search with invalid category types."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "categories": ["invalid_category"]
            })

        assert "Invalid category type" in str(exc_info.value)

    async def test_firesearch_invalid_category_format(self, firesearch_client):
        """Test search with non-string category types."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "categories": [456]
            })

        assert "Category must be a string" in str(exc_info.value)

    async def test_firesearch_invalid_limit_range(self, firesearch_client):
        """Test search with invalid limit values."""
        # Test limit too low
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "limit": 0
            })
        assert "Limit must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

        # Test limit too high
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "limit": 101
            })
        assert "Limit must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    async def test_firesearch_invalid_timeout_range(self, firesearch_client):
        """Test search with invalid timeout values."""
        # Test timeout too low
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "timeout": 500
            })
        assert "Timeout must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

        # Test timeout too high
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "timeout": 400000
            })
        assert "Timeout must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    async def test_firesearch_invalid_tbs_values(self, firesearch_client):
        """Test search with invalid time-based search values."""
        with pytest.raises(Exception) as exc_info:
            await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "tbs": "invalid_tbs"
            })

        assert "Invalid tbs value" in str(exc_info.value)

    async def test_firesearch_valid_tbs_values(self, firesearch_client, mock_search_data):
        """Test search with valid time-based search values."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            valid_tbs_values = ["qdr:h", "qdr:d", "qdr:w", "qdr:m", "qdr:y", "d", "w", "m", "y"]

            for tbs_value in valid_tbs_values:
                result = await firesearch_client.call_tool("firesearch", {
                    "query": "test",
                    "tbs": tbs_value
                })
                assert result.content[0].type == "text"

    async def test_firesearch_custom_date_range_tbs(self, firesearch_client, mock_search_data):
        """Test search with custom date range tbs format."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.return_value = mock_search_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            # Custom date range format should be allowed
            result = await firesearch_client.call_tool("firesearch", {
                "query": "test",
                "tbs": "cdr:1,cd_min:01/01/2024,cd_max:12/31/2024"
            })
            assert result.content[0].type == "text"


class TestFiresearchErrorHandling(TestFiresearchTools):
    """Test error handling for firesearch tools."""

    async def test_firesearch_unauthorized_error(self, firesearch_client):
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.side_effect = UnauthorizedError("Invalid API key")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await firesearch_client.call_tool("firesearch", {
                    "query": "test"
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_firesearch_rate_limit_error(self, firesearch_client):
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.side_effect = RateLimitError("Rate limit exceeded")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await firesearch_client.call_tool("firesearch", {
                    "query": "test"
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_firesearch_bad_request_error(self, firesearch_client):
        """Test handling of bad request errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.side_effect = BadRequestError("Invalid search query")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await firesearch_client.call_tool("firesearch", {
                    "query": "test"
                })

            assert "Invalid search query" in str(exc_info.value)

    async def test_firesearch_generic_error(self, firesearch_client):
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.search.side_effect = Exception("Network error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await firesearch_client.call_tool("firesearch", {
                    "query": "test"
                })

            assert "Unexpected error" in str(exc_info.value)


class TestFiresearchToolRegistration(TestFiresearchTools):
    """Test firesearch tool registration and availability."""

    async def test_firesearch_tool_registered(self, firesearch_client):
        """Test that firesearch tool is properly registered."""
        tools = await firesearch_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "firesearch" in tool_names

    async def test_firesearch_tool_schema_valid(self, firesearch_client):
        """Test that firesearch tool has proper schema."""
        tools = await firesearch_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        firesearch_tool = tool_dict["firesearch"]
        assert firesearch_tool.description is not None
        assert firesearch_tool.inputSchema is not None

        # Check required parameters
        properties = firesearch_tool.inputSchema["properties"]
        assert "query" in properties

        # Check query length constraints
        query_prop = properties["query"]
        assert "minLength" in query_prop
        assert "maxLength" in query_prop

    def test_register_firesearch_tools_returns_tool_names(self):
        """Test that register_firesearch_tools returns the correct tool names."""
        server = FastMCP("TestServer")
        tool_names = register_firesearch_tools(server)

        assert tool_names == ["firesearch"]


@pytest.mark.integration
class TestFiresearchIntegrationTests(TestFiresearchTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_firesearch_integration(self, firesearch_client):
        """Test real search with actual API."""
        result = await firesearch_client.call_tool("firesearch", {
            "query": "Python programming tutorial",
            "limit": 3
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain search results about Python
        assert "Python" in response_data or "programming" in response_data

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_firesearch_with_news(self, firesearch_client):
        """Test real search with news sources."""
        result = await firesearch_client.call_tool("firesearch", {
            "query": "artificial intelligence news",
            "sources": ["web", "news"],
            "limit": 2
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain search results
        assert "artificial intelligence" in response_data or "AI" in response_data

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_firesearch_with_time_filter(self, firesearch_client):
        """Test real search with time-based filtering."""
        result = await firesearch_client.call_tool("firesearch", {
            "query": "technology trends",
            "tbs": "qdr:w",  # Past week
            "limit": 2
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain recent search results
        assert "technology" in response_data or "trends" in response_data
