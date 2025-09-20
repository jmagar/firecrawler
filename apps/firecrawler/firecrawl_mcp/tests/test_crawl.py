"""
Tests for crawling tools in the Firecrawler MCP server.

This module tests the crawl tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import CrawlJob, CrawlRequest, CrawlResponse, Document
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.crawl import (
    _convert_to_crawl_request,
    _validate_crawl_parameters,
    register_crawl_tools,
)


class TestCrawlTools:
    """Test suite for crawling tools."""

    @pytest.fixture
    def crawl_server(self) -> FastMCP:
        """Create FastMCP server with crawling tools registered."""
        server = FastMCP("TestCrawlServer")
        register_crawl_tools(server)
        return server

    @pytest.fixture
    async def crawl_client(self, crawl_server: FastMCP) -> AsyncGenerator[Client, None]:
        """Create MCP client for crawling tools."""
        async with Client(crawl_server) as client:
            yield client

    @pytest.fixture
    def mock_crawl_response(self) -> CrawlResponse:
        """Mock successful crawl response."""
        return CrawlResponse(
            id="crawl-job-12345",
            url="https://api.firecrawl.dev/v1/crawl/crawl-job-12345"
        )

    @pytest.fixture
    def mock_crawl_job(self) -> CrawlJob:
        """Mock crawl job status response."""
        return CrawlJob(
            id="crawl-job-12345",
            status="completed",
            total=5,
            completed=5,
            credits_used=10,
            expires_at=datetime.now(),
            data=[
                Document(
                    content="# Home Page\n\nWelcome to our website.",
                    metadata={
                        "title": "Home Page",
                        "url": "https://example.com/",
                        "statusCode": 200,
                        "language": "en"
                    }
                ),
                Document(
                    content="# About Us\n\nLearn more about our company.",
                    metadata={
                        "title": "About Us",
                        "url": "https://example.com/about",
                        "statusCode": 200,
                        "language": "en"
                    }
                )
            ]
        )

    @pytest.fixture
    def valid_crawl_params(self) -> dict[str, Any]:
        """Valid crawl parameters for testing."""
        return {
            "url": "https://example.com",
            "limit": 10,
            "max_concurrency": 3,
            "exclude_paths": ["/admin", "/private"],
            "include_paths": ["/blog/*", "/docs/*"],
            "max_discovery_depth": 3,
            "allow_subdomains": False,
            "crawl_entire_domain": False
        }


class TestCrawlBasicFunctionality(TestCrawlTools):
    """Test basic crawling functionality."""

    async def test_crawl_success(self, crawl_client: Client, mock_crawl_response: CrawlResponse) -> None:
        """Test successful crawl job initiation."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.return_value = mock_crawl_response
            mock_get_client.return_value = mock_client

            result = await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "limit": 10
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "crawl-job-12345" in response_data
            mock_client.start_crawl.assert_called_once()

    async def test_crawl_with_full_options(self, crawl_client: Client, mock_crawl_response: CrawlResponse, valid_crawl_params: dict[str, Any]) -> None:
        """Test crawling with comprehensive options."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.return_value = mock_crawl_response
            mock_get_client.return_value = mock_client

            result = await crawl_client.call_tool("crawl", valid_crawl_params)

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "crawl-job-12345" in response_data

            # Verify start_crawl was called
            mock_client.start_crawl.assert_called_once()

    async def test_crawl_with_ai_prompt(self, crawl_client: Client, mock_crawl_response: CrawlResponse) -> None:
        """Test crawling with AI-guided prompt."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.return_value = mock_crawl_response
            mock_get_client.return_value = mock_client

            result = await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "prompt": "Find all product pages and pricing information",
                "limit": 20
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "crawl-job-12345" in response_data
            mock_client.start_crawl.assert_called_once()

    async def test_crawl_with_webhook(self, crawl_client: Client, mock_crawl_response: CrawlResponse) -> None:
        """Test crawling with webhook notifications."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.return_value = mock_crawl_response
            mock_get_client.return_value = mock_client

            webhook_url = "https://webhook.example.com/notify"
            result = await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "webhook": webhook_url,
                "limit": 5
            })

            assert result.content[0].type == "text"
            mock_client.start_crawl.assert_called_once()

    async def test_crawl_parameter_validation(self, crawl_client: Client) -> None:
        """Test crawl parameter validation."""
        # Test invalid URL
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "invalid-url"
            })
        assert "http" in str(exc_info.value).lower()

        # Test excessive concurrency
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "max_concurrency": 100
            })
        assert "concurrency" in str(exc_info.value).lower()

    async def test_crawl_regex_pattern_validation(self, crawl_client: Client) -> None:
        """Test validation of regex patterns in exclude/include paths."""
        # Test invalid regex pattern
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "exclude_paths": ["[invalid-regex"]
            })
        assert "regex" in str(exc_info.value).lower()

        # Test invalid include pattern
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "include_paths": ["*invalid-regex["]
            })
        assert "regex" in str(exc_info.value).lower()


class TestCrawlErrorHandling(TestCrawlTools):
    """Test error handling for crawl tools."""

    async def test_crawl_unauthorized_error(self, crawl_client: Client) -> None:
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.side_effect = UnauthorizedError("Invalid API key")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_crawl_rate_limit_error(self, crawl_client: Client) -> None:
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.side_effect = RateLimitError("Rate limit exceeded")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_crawl_bad_request_error(self, crawl_client: Client) -> None:
        """Test handling of bad request errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.side_effect = BadRequestError("Invalid crawl parameters")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Invalid crawl parameters" in str(exc_info.value)

    async def test_crawl_generic_error(self, crawl_client: Client) -> None:
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.start_crawl.side_effect = Exception("Network error")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Unexpected error" in str(exc_info.value)


class TestCrawlUtilityFunctions(TestCrawlTools):
    """Test utility functions for crawl operations."""

    def test_validate_crawl_parameters_success(self, valid_crawl_params: dict[str, Any]) -> None:
        """Test successful parameter validation."""
        # Should not raise any exception
        _validate_crawl_parameters(
            url=valid_crawl_params["url"],
            exclude_paths=valid_crawl_params.get("exclude_paths"),
            include_paths=valid_crawl_params.get("include_paths"),
            max_concurrency=valid_crawl_params.get("max_concurrency")
        )

    def test_validate_crawl_parameters_invalid_url(self) -> None:
        """Test parameter validation with invalid URL."""
        with pytest.raises(ToolError) as exc_info:
            _validate_crawl_parameters(url="invalid-url")

        assert "must start with http://" in str(exc_info.value)

    def test_validate_crawl_parameters_invalid_regex(self) -> None:
        """Test parameter validation with invalid regex patterns."""
        with pytest.raises(ToolError) as exc_info:
            _validate_crawl_parameters(
                url="https://example.com",
                exclude_paths=["[invalid-regex"]
            )

        assert "Invalid regex pattern" in str(exc_info.value)

    def test_convert_to_crawl_request(self, valid_crawl_params: dict[str, Any]) -> None:
        """Test conversion from MCP params to CrawlRequest."""
        request = _convert_to_crawl_request(
            url=valid_crawl_params["url"],
            limit=valid_crawl_params.get("limit"),
            max_concurrency=valid_crawl_params.get("max_concurrency"),
            exclude_paths=valid_crawl_params.get("exclude_paths"),
            include_paths=valid_crawl_params.get("include_paths"),
            max_discovery_depth=valid_crawl_params.get("max_discovery_depth"),
            allow_subdomains=bool(valid_crawl_params.get("allow_subdomains", False)),
            crawl_entire_domain=bool(valid_crawl_params.get("crawl_entire_domain", False))
        )

        assert isinstance(request, CrawlRequest)
        assert request.url == valid_crawl_params["url"]
        assert request.limit == valid_crawl_params.get("limit")
        assert request.max_concurrency == valid_crawl_params.get("max_concurrency")
        assert request.exclude_paths == valid_crawl_params.get("exclude_paths")
        assert request.include_paths == valid_crawl_params.get("include_paths")


class TestCrawlToolRegistration(TestCrawlTools):
    """Test crawl tool registration and schema validation."""

    async def test_crawl_tool_registered(self, crawl_client: Client) -> None:
        """Test that crawl tool is properly registered."""
        tools = await crawl_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "crawl" in tool_names

    async def test_crawl_tool_schema(self, crawl_client: Client) -> None:
        """Test that crawl tool has proper schema."""
        tools = await crawl_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        crawl_tool = tool_dict["crawl"]
        assert crawl_tool.description is not None
        assert crawl_tool.inputSchema is not None

        # Check required parameters
        properties = crawl_tool.inputSchema["properties"]
        assert "url" in properties

        # Check URL pattern validation
        url_prop = properties["url"]
        assert "pattern" in url_prop
        assert "http" in url_prop["pattern"]

    def test_register_crawl_tools_function_exists(self) -> None:
        """Test that register_crawl_tools function works."""
        server = FastMCP("TestServer")
        register_crawl_tools(server)

        # Server should have tools registered - we can't easily test this
        # since FastMCP doesn't expose list_tools method directly
        # but we can verify the function completes without error
        assert True


@pytest.mark.integration
class TestCrawlIntegrationTests(TestCrawlTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_integration(self, crawl_client: Client) -> None:
        """Test real crawling with actual API."""
        result = await crawl_client.call_tool("crawl", {
            "url": "https://httpbin.org",
            "limit": 3,
            "max_concurrency": 1
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain job ID or other success indicator
        assert "httpbin.org" in response_data or "crawl" in response_data.lower()

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_with_prompt(self, crawl_client: Client) -> None:
        """Test real crawling with AI prompt."""
        result = await crawl_client.call_tool("crawl", {
            "url": "https://httpbin.org",
            "prompt": "Find API documentation and examples",
            "limit": 2,
            "max_concurrency": 1
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain job ID or other success indicator
        assert "httpbin.org" in response_data or "crawl" in response_data.lower()
