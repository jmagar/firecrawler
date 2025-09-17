"""
Tests for mapping tools in the Firecrawler MCP server.

This module tests the map tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import LinkData, Location, MapData
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.map import register_map_tools


class TestMapTools:
    """Test suite for mapping tools."""

    @pytest.fixture
    def map_server(self, test_env):
        """Create FastMCP server with mapping tools registered."""
        server = FastMCP("TestMapServer")
        register_map_tools(server)
        return server

    @pytest.fixture
    async def map_client(self, map_server):
        """Create MCP client for mapping tools."""
        async with Client(map_server) as client:
            yield client

    @pytest.fixture
    def mock_map_data(self):
        """Mock successful map response."""
        return MapData(
            links=[
                LinkData(
                    url="https://example.com/",
                    title="Home Page",
                    description="Welcome to our website"
                ),
                LinkData(
                    url="https://example.com/about",
                    title="About Us",
                    description="Learn more about our company"
                ),
                LinkData(
                    url="https://example.com/products",
                    title="Products",
                    description="Our product offerings"
                ),
                LinkData(
                    url="https://example.com/contact",
                    title="Contact Us",
                    description="Get in touch with us"
                ),
                LinkData(
                    url="https://example.com/blog",
                    title="Blog",
                    description="Latest news and updates"
                )
            ]
        )

    @pytest.fixture
    def mock_sitemap_only_data(self):
        """Mock map response with sitemap-only discovery."""
        return MapData(
            links=[
                LinkData(
                    url="https://example.com/",
                    title="Home",
                    description="Main page"
                ),
                LinkData(
                    url="https://example.com/products",
                    title="Products",
                    description="Product catalog"
                )
            ]
        )

    @pytest.fixture
    def valid_location(self):
        """Valid location configuration for testing."""
        return Location(
            country="US",
            languages=["en"]
        )


class TestMapBasicFunctionality(TestMapTools):
    """Test basic mapping functionality."""

    async def test_map_success(self, map_client, mock_map_data):
        """Test successful URL mapping."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "5" in response_data  # Should mention 5 URLs discovered
            assert "example.com" in response_data

            mock_client.map.assert_called_once_with(url="https://example.com", options=None)

    async def test_map_with_search_filter(self, map_client, mock_map_data):
        """Test mapping with search filter."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com",
                "search": "product"
            })

            assert result.content[0].type == "text"

            # Verify search filter was passed
            call_args = mock_client.map.call_args
            options = call_args[1]["options"]
            assert options is not None
            assert options.search == "product"

    async def test_map_with_sitemap_options(self, map_client, mock_sitemap_only_data):
        """Test mapping with different sitemap strategies."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_sitemap_only_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            # Test sitemap only
            result = await map_client.call_tool("map", {
                "url": "https://example.com",
                "sitemap": "only"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "2" in response_data  # Should mention 2 URLs discovered

            call_args = mock_client.map.call_args
            options = call_args[1]["options"]
            assert options.sitemap == "only"

    async def test_map_with_full_options(self, map_client, mock_map_data, valid_location):
        """Test mapping with comprehensive options."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com",
                "search": "blog",
                "sitemap": "include",
                "include_subdomains": True,
                "limit": 50,
                "timeout": 60,
                "integration": "custom-mapper",
                "location": valid_location.model_dump()
            })

            assert result.content[0].type == "text"

            # Verify all options were passed
            call_args = mock_client.map.call_args
            options = call_args[1]["options"]
            assert options is not None
            assert options.search == "blog"
            assert options.sitemap == "include"
            assert options.include_subdomains is True
            assert options.limit == 50
            assert options.timeout == 60
            assert options.integration == "custom-mapper"
            assert options.location is not None

    async def test_map_with_subdomain_discovery(self, map_client, mock_map_data):
        """Test mapping with subdomain discovery enabled."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com",
                "include_subdomains": True,
                "limit": 100
            })

            assert result.content[0].type == "text"

            call_args = mock_client.map.call_args
            options = call_args[1]["options"]
            assert options.include_subdomains is True
            assert options.limit == 100

    async def test_map_with_timeout_and_limit(self, map_client, mock_map_data):
        """Test mapping with timeout and URL limit constraints."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com",
                "timeout": 120,
                "limit": 1000
            })

            assert result.content[0].type == "text"

            call_args = mock_client.map.call_args
            options = call_args[1]["options"]
            assert options.timeout == 120
            assert options.limit == 1000


class TestMapValidation(TestMapTools):
    """Test mapping parameter validation."""

    async def test_map_empty_url_error(self, map_client):
        """Test mapping with empty URL."""
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {"url": ""})

        assert "URL cannot be empty" in str(exc_info.value)

    async def test_map_invalid_url_format(self, map_client):
        """Test mapping with invalid URL format."""
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {"url": "invalid-url"})

        # Should fail Pydantic validation for URL pattern
        assert "validation" in str(exc_info.value).lower()

    async def test_map_invalid_url_protocol(self, map_client):
        """Test mapping with URL missing protocol."""
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {"url": "example.com"})

        # Should fail either pattern validation or our additional check
        error_msg = str(exc_info.value)
        assert "validation" in error_msg.lower() or "http" in error_msg

    async def test_map_invalid_sitemap_value(self, map_client):
        """Test mapping with invalid sitemap value."""
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "sitemap": "invalid"
            })

        assert "Invalid sitemap value" in str(exc_info.value)

    async def test_map_invalid_timeout_range(self, map_client):
        """Test mapping with invalid timeout values."""
        # Test timeout too low
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "timeout": 0
            })
        assert "Timeout must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

        # Test timeout too high
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "timeout": 301
            })
        assert "Timeout must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    async def test_map_invalid_limit_range(self, map_client):
        """Test mapping with invalid limit values."""
        # Test limit too low
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "limit": 0
            })
        assert "Limit must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

        # Test limit too high
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "limit": 10001
            })
        assert "Limit must be between" in str(exc_info.value) or "validation" in str(exc_info.value).lower()

    async def test_map_parameter_length_validation(self, map_client):
        """Test mapping parameter length validation."""
        # Test search filter too long
        long_search = "x" * 501
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "search": long_search
            })
        assert "validation" in str(exc_info.value).lower()

        # Test integration field too long
        long_integration = "x" * 101
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": "https://example.com",
                "integration": long_integration
            })
        assert "validation" in str(exc_info.value).lower()

        # Test URL too long
        long_url = "https://example.com/" + "x" * 2048
        with pytest.raises(Exception) as exc_info:
            await map_client.call_tool("map", {
                "url": long_url
            })
        assert "validation" in str(exc_info.value).lower()


class TestMapProgressReporting(TestMapTools):
    """Test mapping progress reporting and metadata."""

    async def test_map_metadata_reporting(self, map_client, mock_map_data):
        """Test that mapping reports URL metadata correctly."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = mock_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text

            # Should report counts of URLs with metadata
            assert "titles" in response_data
            assert "descriptions" in response_data

    async def test_map_empty_results(self, map_client):
        """Test mapping with no URLs discovered."""
        empty_map_data = MapData(links=[])

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = empty_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "0" in response_data  # Should report 0 URLs discovered

    async def test_map_large_results(self, map_client):
        """Test mapping with large number of URLs discovered."""
        # Create mock data with many URLs
        large_links = [
            LinkData(
                url=f"https://example.com/page{i}",
                title=f"Page {i}",
                description=f"Description for page {i}"
            )
            for i in range(100)
        ]
        large_map_data = MapData(links=large_links)

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.return_value = large_map_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await map_client.call_tool("map", {
                "url": "https://example.com",
                "limit": 100
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "100" in response_data  # Should report 100 URLs discovered


class TestMapErrorHandling(TestMapTools):
    """Test error handling for mapping tools."""

    async def test_map_unauthorized_error(self, map_client):
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.side_effect = UnauthorizedError("Invalid API key")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await map_client.call_tool("map", {
                    "url": "https://example.com"
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_map_rate_limit_error(self, map_client):
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.side_effect = RateLimitError("Rate limit exceeded")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await map_client.call_tool("map", {
                    "url": "https://example.com"
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_map_bad_request_error(self, map_client):
        """Test handling of bad request errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.side_effect = BadRequestError("Invalid URL for mapping")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await map_client.call_tool("map", {
                    "url": "https://example.com"
                })

            assert "Invalid URL for mapping" in str(exc_info.value)

    async def test_map_generic_error(self, map_client):
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.map.side_effect = Exception("Network error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await map_client.call_tool("map", {
                    "url": "https://example.com"
                })

            assert "Unexpected error" in str(exc_info.value)


class TestMapToolRegistration(TestMapTools):
    """Test mapping tool registration and availability."""

    async def test_map_tool_registered(self, map_client):
        """Test that map tool is properly registered."""
        tools = await map_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "map" in tool_names

    async def test_map_tool_schema_valid(self, map_client):
        """Test that map tool has proper schema."""
        tools = await map_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        map_tool = tool_dict["map"]
        assert map_tool.description is not None
        assert map_tool.inputSchema is not None

        # Check required parameters
        properties = map_tool.inputSchema["properties"]
        assert "url" in properties

        # Check URL pattern validation
        url_prop = properties["url"]
        assert "pattern" in url_prop
        assert "http" in url_prop["pattern"]

    def test_register_map_tools_returns_tool_names(self):
        """Test that register_map_tools returns the correct tool names."""
        server = FastMCP("TestServer")
        tool_names = register_map_tools(server)

        assert tool_names == ["map"]


@pytest.mark.integration
class TestMapIntegrationTests(TestMapTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_map_integration(self, map_client):
        """Test real mapping with actual API."""
        result = await map_client.call_tool("map", {
            "url": "https://httpbin.org",
            "limit": 10
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should discover some URLs from httpbin.org
        assert "httpbin.org" in response_data
        assert "discovered" in response_data

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_map_with_sitemap_only(self, map_client):
        """Test real mapping with sitemap-only strategy."""
        result = await map_client.call_tool("map", {
            "url": "https://httpbin.org",
            "sitemap": "only",
            "limit": 5
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should report the mapping results
        assert "discovered" in response_data or "URLs" in response_data

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_map_with_search_filter(self, map_client):
        """Test real mapping with search filter."""
        result = await map_client.call_tool("map", {
            "url": "https://httpbin.org",
            "search": "json",
            "limit": 5
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should report the filtered mapping results
        assert "discovered" in response_data
