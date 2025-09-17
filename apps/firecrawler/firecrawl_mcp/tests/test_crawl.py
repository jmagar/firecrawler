"""
Tests for crawling tools in the Firecrawler MCP server.

This module tests the crawl tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import CrawlJob, CrawlRequest, CrawlResponse, Document
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.core.exceptions import (
    MCPValidationError,
)
from firecrawl_mcp.tools.crawl import (
    CrawlParams,
    CrawlResult,
    _convert_crawl_job_to_result,
    _convert_to_crawl_request,
    _validate_crawl_parameters,
    register_crawl_tools,
)


class TestCrawlTools:
    """Test suite for crawling tools."""

    @pytest.fixture
    def crawl_server(self, test_env):
        """Create FastMCP server with crawling tools registered."""
        server = FastMCP("TestCrawlServer")
        register_crawl_tools(server)
        return server

    @pytest.fixture
    async def crawl_client(self, crawl_server):
        """Create MCP client for crawling tools."""
        async with Client(crawl_server) as client:
            yield client

    @pytest.fixture
    def mock_crawl_response(self):
        """Mock successful crawl response."""
        return CrawlResponse(
            id="crawl-job-12345",
            url="https://api.firecrawl.dev/v1/crawl/crawl-job-12345"
        )

    @pytest.fixture
    def mock_crawl_job(self):
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
    def valid_crawl_params(self):
        """Valid crawl parameters for testing."""
        return CrawlParams(
            url="https://example.com",
            limit=10,
            max_concurrency=3,
            exclude_paths=["/admin", "/private"],
            include_paths=["/blog/*", "/docs/*"],
            max_discovery_depth=3,
            allow_subdomains=False,
            crawl_entire_domain=False
        )


class TestCrawlBasicFunctionality(TestCrawlTools):
    """Test basic crawling functionality."""

    async def test_crawl_success(self, crawl_client, mock_crawl_response):
        """Test successful crawl job initiation."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.return_value = mock_crawl_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "limit": 10
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "crawl-job-12345" in response_data
            assert "success" in response_data
            mock_client.crawl.start_crawl.assert_called_once()

    async def test_crawl_with_full_options(self, crawl_client, mock_crawl_response, valid_crawl_params):
        """Test crawling with comprehensive options."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.return_value = mock_crawl_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_client.call_tool("crawl", valid_crawl_params.model_dump())

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "crawl-job-12345" in response_data

            # Verify all parameters were passed
            call_args = mock_client.crawl.start_crawl.call_args[0][0]
            assert call_args.url == "https://example.com"
            assert call_args.limit == 10
            assert call_args.max_concurrency == 3
            assert call_args.exclude_paths == ["/admin", "/private"]
            assert call_args.include_paths == ["/blog/*", "/docs/*"]

    async def test_crawl_with_ai_prompt(self, crawl_client, mock_crawl_response):
        """Test crawling with AI-guided prompt."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.return_value = mock_crawl_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "prompt": "Find all product pages and pricing information",
                "limit": 20
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "crawl-job-12345" in response_data

            call_args = mock_client.crawl.start_crawl.call_args[0][0]
            assert call_args.prompt == "Find all product pages and pricing information"

    async def test_crawl_with_webhook(self, crawl_client, mock_crawl_response):
        """Test crawling with webhook notifications."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.return_value = mock_crawl_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            webhook_url = "https://webhook.example.com/notify"
            result = await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "webhook": webhook_url,
                "limit": 5
            })

            assert result.content[0].type == "text"
            call_args = mock_client.crawl.start_crawl.call_args[0][0]
            assert call_args.webhook == webhook_url

    async def test_crawl_parameter_validation(self, crawl_client):
        """Test crawl parameter validation."""
        # Test invalid URL
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "invalid-url"
            })
        assert "validation" in str(exc_info.value).lower()

        # Test excessive concurrency
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "max_concurrency": 100
            })
        assert "concurrency" in str(exc_info.value).lower()

        # Test excessive depth
        with pytest.raises(Exception) as exc_info:
            await crawl_client.call_tool("crawl", {
                "url": "https://example.com",
                "max_discovery_depth": 20
            })
        assert "validation" in str(exc_info.value).lower()

    async def test_crawl_regex_pattern_validation(self, crawl_client):
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

    async def test_crawl_unauthorized_error(self, crawl_client):
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.side_effect = UnauthorizedError("Invalid API key")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_crawl_rate_limit_error(self, crawl_client):
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.side_effect = RateLimitError("Rate limit exceeded")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_crawl_bad_request_error(self, crawl_client):
        """Test handling of bad request errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.side_effect = BadRequestError("Invalid crawl parameters")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Invalid crawl parameters" in str(exc_info.value)

    async def test_crawl_generic_error(self, crawl_client):
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.start_crawl.side_effect = Exception("Network error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_client.call_tool("crawl", {
                    "url": "https://example.com"
                })

            assert "Unexpected error" in str(exc_info.value)


class TestCrawlUtilityFunctions(TestCrawlTools):
    """Test utility functions for crawl operations."""

    def test_validate_crawl_parameters_success(self, valid_crawl_params):
        """Test successful parameter validation."""
        # Should not raise any exception
        _validate_crawl_parameters(valid_crawl_params)

    def test_validate_crawl_parameters_invalid_url(self):
        """Test parameter validation with invalid URL."""
        params = CrawlParams(url="invalid-url")

        with pytest.raises(MCPValidationError) as exc_info:
            _validate_crawl_parameters(params)

        assert "must start with http://" in str(exc_info.value)

    def test_validate_crawl_parameters_invalid_regex(self):
        """Test parameter validation with invalid regex patterns."""
        params = CrawlParams(
            url="https://example.com",
            exclude_paths=["[invalid-regex"]
        )

        with pytest.raises(MCPValidationError) as exc_info:
            _validate_crawl_parameters(params)

        assert "Invalid regex pattern" in str(exc_info.value)

    def test_convert_to_crawl_request(self, valid_crawl_params):
        """Test conversion from MCP params to CrawlRequest."""
        request = _convert_to_crawl_request(valid_crawl_params)

        assert isinstance(request, CrawlRequest)
        assert request.url == valid_crawl_params.url
        assert request.limit == valid_crawl_params.limit
        assert request.max_concurrency == valid_crawl_params.max_concurrency
        assert request.exclude_paths == valid_crawl_params.exclude_paths
        assert request.include_paths == valid_crawl_params.include_paths

    def test_convert_crawl_job_to_result(self, mock_crawl_job):
        """Test conversion from CrawlJob to result format."""
        result = _convert_crawl_job_to_result(mock_crawl_job, "test-job-id")

        assert isinstance(result, CrawlResult)
        assert result.success is True
        assert result.job_id == "test-job-id"
        assert result.status == "completed"
        assert result.total == 5
        assert result.completed == 5
        assert result.data_count == 2
        assert len(result.data) == 2
        assert "successfully" in result.message


class TestCrawlToolRegistration(TestCrawlTools):
    """Test crawl tool registration and schema validation."""

    async def test_crawl_tool_registered(self, crawl_client):
        """Test that crawl tool is properly registered."""
        tools = await crawl_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "crawl" in tool_names

    async def test_crawl_tool_schema(self, crawl_client):
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

    def test_register_crawl_tools_function_exists(self):
        """Test that register_crawl_tools function works."""
        server = FastMCP("TestServer")
        register_crawl_tools(server)

        # Server should have tools registered
        tools = server.list_tools()
        tool_names = [tool.name for tool in tools]
        assert "crawl" in tool_names


@pytest.mark.integration
class TestCrawlIntegrationTests(TestCrawlTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_integration(self, crawl_client):
        """Test real crawling with actual API."""
        result = await crawl_client.call_tool("crawl", {
            "url": "https://httpbin.org",
            "limit": 3,
            "max_concurrency": 1
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain job ID
        import json
        crawl_data = json.loads(response_data)
        assert "job_id" in crawl_data
        assert crawl_data["success"] is True

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_with_prompt(self, crawl_client):
        """Test real crawling with AI prompt."""
        result = await crawl_client.call_tool("crawl", {
            "url": "https://httpbin.org",
            "prompt": "Find API documentation and examples",
            "limit": 2,
            "max_concurrency": 1
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        import json
        crawl_data = json.loads(response_data)
        assert crawl_data["success"] is True
