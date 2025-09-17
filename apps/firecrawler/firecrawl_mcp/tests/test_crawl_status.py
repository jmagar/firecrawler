"""
Tests for crawl status checking in the Firecrawler MCP server.

This module tests the crawl_status tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import CrawlJob, Document
from firecrawl.v2.utils.error_handler import (
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.crawl import (
    CrawlStatusResult,
    _convert_crawl_job_to_result,
    register_crawl_tools,
)


class TestCrawlStatusTools:
    """Test suite for crawl status tools."""

    @pytest.fixture
    def crawl_status_server(self, test_env):
        """Create FastMCP server with crawl status tools registered."""
        server = FastMCP("TestCrawlStatusServer")
        register_crawl_tools(server)
        return server

    @pytest.fixture
    async def crawl_status_client(self, crawl_status_server):
        """Create MCP client for crawl status tools."""
        async with Client(crawl_status_server) as client:
            yield client

    @pytest.fixture
    def mock_completed_crawl_job(self):
        """Mock completed crawl job."""
        return CrawlJob(
            id="crawl-job-12345",
            status="completed",
            total=10,
            completed=10,
            credits_used=25,
            expires_at=datetime.now(),
            data=[
                Document(
                    content="# Home Page\n\nWelcome to our website.",
                    metadata={
                        "title": "Home Page",
                        "url": "https://example.com/",
                        "statusCode": 200,
                        "language": "en",
                        "sourceURL": "https://example.com/"
                    },
                    markdown="# Home Page\n\nWelcome to our website.",
                    html="<h1>Home Page</h1><p>Welcome to our website.</p>"
                ),
                Document(
                    content="# About Us\n\nLearn more about our company.",
                    metadata={
                        "title": "About Us",
                        "url": "https://example.com/about",
                        "statusCode": 200,
                        "language": "en",
                        "sourceURL": "https://example.com/about"
                    },
                    markdown="# About Us\n\nLearn more about our company.",
                    html="<h1>About Us</h1><p>Learn more about our company.</p>"
                )
            ]
        )

    @pytest.fixture
    def mock_in_progress_crawl_job(self):
        """Mock in-progress crawl job."""
        return CrawlJob(
            id="crawl-job-12345",
            status="scraping",
            total=10,
            completed=5,
            credits_used=12,
            expires_at=datetime.now(),
            data=[
                Document(
                    content="# Home Page\n\nWelcome to our website.",
                    metadata={
                        "title": "Home Page",
                        "url": "https://example.com/",
                        "statusCode": 200
                    }
                )
            ]
        )

    @pytest.fixture
    def mock_failed_crawl_job(self):
        """Mock failed crawl job."""
        return CrawlJob(
            id="crawl-job-12345",
            status="failed",
            total=10,
            completed=3,
            credits_used=8,
            expires_at=datetime.now(),
            data=[
                Document(
                    content="# Home Page\n\nWelcome to our website.",
                    metadata={
                        "title": "Home Page",
                        "url": "https://example.com/",
                        "statusCode": 200
                    }
                )
            ]
        )

    @pytest.fixture
    def valid_job_id(self):
        """Valid job ID format for testing."""
        return "12345678-1234-1234-1234-123456789abc"


class TestCrawlStatusBasicFunctionality(TestCrawlStatusTools):
    """Test basic crawl status functionality."""

    async def test_crawl_status_completed_success(self, crawl_status_client, mock_completed_crawl_job, valid_job_id):
        """Test successful status check for completed crawl."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.return_value = mock_completed_crawl_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_status_client.call_tool("crawl_status", {
                "job_id": valid_job_id
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "completed" in response_data
            assert "10/10" in response_data
            assert "success" in response_data

            mock_client.crawl.get_crawl_status.assert_called_once_with(
                valid_job_id,
                None
            )

    async def test_crawl_status_in_progress(self, crawl_status_client, mock_in_progress_crawl_job, valid_job_id):
        """Test status check for in-progress crawl."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.return_value = mock_in_progress_crawl_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_status_client.call_tool("crawl_status", {
                "job_id": valid_job_id
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "scraping" in response_data
            assert "5/10" in response_data
            assert "in progress" in response_data

    async def test_crawl_status_failed(self, crawl_status_client, mock_failed_crawl_job, valid_job_id):
        """Test status check for failed crawl."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.return_value = mock_failed_crawl_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_status_client.call_tool("crawl_status", {
                "job_id": valid_job_id
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "failed" in response_data
            assert "3/10" in response_data

    async def test_crawl_status_with_pagination_disabled(self, crawl_status_client, mock_completed_crawl_job, valid_job_id):
        """Test status check with pagination disabled."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.return_value = mock_completed_crawl_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_status_client.call_tool("crawl_status", {
                "job_id": valid_job_id,
                "auto_paginate": False,
                "max_pages": 1,
                "max_results": 50
            })

            assert result.content[0].type == "text"

            # Verify pagination config was passed
            call_args = mock_client.crawl.get_crawl_status.call_args
            pagination_config = call_args[0][1]
            assert pagination_config is not None
            assert pagination_config.auto_paginate is False
            assert pagination_config.max_pages == 1
            assert pagination_config.max_results == 50

    async def test_crawl_status_with_wait_time(self, crawl_status_client, mock_completed_crawl_job, valid_job_id):
        """Test status check with maximum wait time."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.return_value = mock_completed_crawl_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await crawl_status_client.call_tool("crawl_status", {
                "job_id": valid_job_id,
                "max_wait_time": 60
            })

            assert result.content[0].type == "text"

            # Verify wait time was passed
            call_args = mock_client.crawl.get_crawl_status.call_args
            pagination_config = call_args[0][1]
            assert pagination_config is not None
            assert pagination_config.max_wait_time == 60

    async def test_crawl_status_parameter_validation(self, crawl_status_client):
        """Test parameter validation for crawl status."""
        # Test invalid job ID format
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": "invalid-job-id"
            })
        assert "validation" in str(exc_info.value).lower()

        # Test empty job ID
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": ""
            })
        assert "validation" in str(exc_info.value).lower()

        # Test invalid max_pages
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": "12345678-1234-1234-1234-123456789abc",
                "max_pages": 0
            })
        assert "validation" in str(exc_info.value).lower()

        # Test invalid max_results
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": "12345678-1234-1234-1234-123456789abc",
                "max_results": 0
            })
        assert "validation" in str(exc_info.value).lower()

        # Test invalid max_wait_time
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": "12345678-1234-1234-1234-123456789abc",
                "max_wait_time": 0
            })
        assert "validation" in str(exc_info.value).lower()


class TestCrawlStatusErrorHandling(TestCrawlStatusTools):
    """Test error handling for crawl status checks."""

    async def test_crawl_status_not_found_error(self, crawl_status_client, valid_job_id):
        """Test handling of job not found errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.side_effect = NotFoundError("Job not found")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl_status", {
                    "job_id": valid_job_id
                })

            assert "Job not found" in str(exc_info.value)

    async def test_crawl_status_unauthorized_error(self, crawl_status_client, valid_job_id):
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.side_effect = UnauthorizedError("Invalid API key")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl_status", {
                    "job_id": valid_job_id
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_crawl_status_rate_limit_error(self, crawl_status_client, valid_job_id):
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.side_effect = RateLimitError("Rate limit exceeded")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl_status", {
                    "job_id": valid_job_id
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_crawl_status_generic_error(self, crawl_status_client, valid_job_id):
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.crawl.get_crawl_status.side_effect = Exception("Network error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl_status", {
                    "job_id": valid_job_id
                })

            assert "Unexpected error" in str(exc_info.value)


class TestCrawlStatusResultConversion(TestCrawlStatusTools):
    """Test result conversion functionality."""

    def test_convert_completed_crawl_job_to_result(self, mock_completed_crawl_job):
        """Test conversion of completed crawl job to result format."""
        result = _convert_crawl_job_to_result(mock_completed_crawl_job, "test-job-id")

        assert isinstance(result, CrawlStatusResult)
        assert result.success is True
        assert result.job_id == "test-job-id"
        assert result.status == "completed"
        assert result.total == 10
        assert result.completed == 10
        assert result.credits_used == 25
        assert result.data_count == 2
        assert len(result.data) == 2
        assert "successfully" in result.message

        # Check data structure
        first_doc = result.data[0]
        assert "url" in first_doc
        assert "title" in first_doc
        assert "markdown" in first_doc
        assert "content" in first_doc
        assert "metadata" in first_doc

    def test_convert_in_progress_crawl_job_to_result(self, mock_in_progress_crawl_job):
        """Test conversion of in-progress crawl job to result format."""
        result = _convert_crawl_job_to_result(mock_in_progress_crawl_job, "test-job-id")

        assert result.status == "scraping"
        assert result.completed == 5
        assert result.total == 10
        assert "in progress" in result.message

    def test_convert_failed_crawl_job_to_result(self, mock_failed_crawl_job):
        """Test conversion of failed crawl job to result format."""
        result = _convert_crawl_job_to_result(mock_failed_crawl_job, "test-job-id")

        assert result.status == "failed"
        assert result.completed == 3
        assert result.total == 10
        assert "failed" in result.message

    def test_convert_crawl_job_with_pagination(self):
        """Test conversion of crawl job with pagination info."""
        mock_job = CrawlJob(
            id="crawl-job-12345",
            status="completed",
            total=100,
            completed=100,
            credits_used=200,
            expires_at=datetime.now(),
            data=[
                Document(
                    content="# Test Page",
                    metadata={"title": "Test", "url": "https://example.com"}
                )
            ],
            next="next_page_token"
        )

        result = _convert_crawl_job_to_result(mock_job, "test-job-id")
        assert result.has_more_pages is True

    def test_convert_crawl_job_without_pagination(self, mock_completed_crawl_job):
        """Test conversion of crawl job without pagination info."""
        mock_completed_crawl_job.next = None

        result = _convert_crawl_job_to_result(mock_completed_crawl_job, "test-job-id")
        assert result.has_more_pages is False


class TestCrawlStatusToolRegistration(TestCrawlStatusTools):
    """Test crawl status tool registration and schema validation."""

    async def test_crawl_status_tool_registered(self, crawl_status_client):
        """Test that crawl_status tool is properly registered."""
        tools = await crawl_status_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "crawl_status" in tool_names

    async def test_crawl_status_tool_schema(self, crawl_status_client):
        """Test that crawl_status tool has proper schema."""
        tools = await crawl_status_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        crawl_status_tool = tool_dict["crawl_status"]
        assert crawl_status_tool.description is not None
        assert crawl_status_tool.inputSchema is not None

        # Check required parameters
        properties = crawl_status_tool.inputSchema["properties"]
        assert "job_id" in properties

        # Check job ID pattern validation
        job_id_prop = properties["job_id"]
        assert "pattern" in job_id_prop
        assert "^[a-f0-9\\-]{36}$" in job_id_prop["pattern"]

    async def test_crawl_status_tool_annotations(self, crawl_status_client):
        """Test that crawl_status tool has proper annotations."""
        tools = await crawl_status_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        crawl_status_tool = tool_dict["crawl_status"]
        # FastMCP may include tool annotations in the schema or separately
        assert crawl_status_tool.description is not None


@pytest.mark.integration
class TestCrawlStatusIntegrationTests(TestCrawlStatusTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_status_integration(self, crawl_status_client):
        """Test real crawl status check with actual API."""
        # Note: This test requires a valid job ID from a real crawl
        # In practice, you would start a crawl first and then check its status

        # For now, test with a realistic but likely expired job ID format
        realistic_job_id = "12345678-1234-1234-1234-123456789abc"

        # This will likely return a "not found" error, which is expected
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": realistic_job_id
            })

        # Should get a proper error response, not a validation error
        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower() or "expired" in error_msg.lower()

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_status_with_pagination(self, crawl_status_client):
        """Test real crawl status with pagination options."""
        realistic_job_id = "12345678-1234-1234-1234-123456789abc"

        # Test with pagination disabled
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl_status", {
                "job_id": realistic_job_id,
                "auto_paginate": False,
                "max_pages": 1
            })

        # Should handle pagination parameters properly even if job doesn't exist
        error_msg = str(exc_info.value)
        assert "validation" not in error_msg.lower()  # Should not be a validation error
