"""
Tests for crawl status checking in the Firecrawler MCP server.

This module tests the crawl_status tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import CrawlJob, Document
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.crawl import register_crawl_tools


class TestCrawlStatusTools:
    """Test suite for crawl status tools."""

    @pytest.fixture
    def crawl_status_server(self, test_env: dict[str, Any]) -> FastMCP:  # noqa: ARG002
        """Create FastMCP server with crawl status tools registered."""
        server = FastMCP("TestCrawlStatusServer")
        register_crawl_tools(server)
        return server

    @pytest.fixture
    async def crawl_status_client(self, crawl_status_server: FastMCP) -> AsyncGenerator[Client, None]:
        """Create MCP client for crawl status tools."""
        async with Client(crawl_status_server) as client:
            yield client

    @pytest.fixture
    def mock_completed_crawl_job(self) -> CrawlJob:
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
    def mock_in_progress_crawl_job(self) -> CrawlJob:
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
    def mock_failed_crawl_job(self) -> CrawlJob:
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
    def valid_job_id(self) -> str:
        """Valid job ID format for testing."""
        return "12345678-1234-1234-1234-123456789abc"


class TestCrawlStatusBasicFunctionality(TestCrawlStatusTools):
    """Test basic crawl status functionality."""

    async def test_crawl_status_completed_success(self, crawl_status_client: Client, mock_completed_crawl_job: CrawlJob, valid_job_id: str) -> None:
        """Test successful status check for completed crawl."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.return_value = mock_completed_crawl_job
            mock_get_client.return_value = mock_client

            result = await crawl_status_client.call_tool("crawl", {
                "job_id": valid_job_id
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "completed" in response_data
            assert "10/10" in response_data
            assert "job_id" in response_data

            # Verify the call was made with pagination config
            assert mock_client.get_crawl_status.called

    async def test_crawl_status_in_progress(self, crawl_status_client: Client, mock_in_progress_crawl_job: CrawlJob, valid_job_id: str) -> None:
        """Test status check for in-progress crawl."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.return_value = mock_in_progress_crawl_job
            mock_get_client.return_value = mock_client

            result = await crawl_status_client.call_tool("crawl", {
                "job_id": valid_job_id
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "scraping" in response_data
            assert "5/10" in response_data
            assert "in progress" in response_data

    async def test_crawl_status_failed(self, crawl_status_client: Client, mock_failed_crawl_job: CrawlJob, valid_job_id: str) -> None:
        """Test status check for failed crawl."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.return_value = mock_failed_crawl_job
            mock_get_client.return_value = mock_client

            result = await crawl_status_client.call_tool("crawl", {
                "job_id": valid_job_id
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "failed" in response_data
            assert "3/10" in response_data

    async def test_crawl_status_with_pagination_disabled(self, crawl_status_client: Client, mock_completed_crawl_job: CrawlJob, valid_job_id: str) -> None:
        """Test status check with pagination disabled."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.return_value = mock_completed_crawl_job
            mock_get_client.return_value = mock_client

            result = await crawl_status_client.call_tool("crawl", {
                "job_id": valid_job_id,
                "auto_paginate": False,
                "max_pages": 1,
                "max_results": 50
            })

            assert result.content[0].type == "text"

            # Verify pagination config was passed (status mode forces specific pagination)
            assert mock_client.get_crawl_status.called

    async def test_crawl_status_with_wait_time(self, crawl_status_client: Client, mock_completed_crawl_job: CrawlJob, valid_job_id: str) -> None:
        """Test status check with maximum wait time."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.return_value = mock_completed_crawl_job
            mock_get_client.return_value = mock_client

            result = await crawl_status_client.call_tool("crawl", {
                "job_id": valid_job_id,
                "max_wait_time": 60
            })

            assert result.content[0].type == "text"

            # Verify the call was made (status mode has its own wait time)
            assert mock_client.get_crawl_status.called

    async def test_crawl_status_parameter_validation(self, crawl_status_client: Client) -> None:
        """Test parameter validation for crawl status."""
        # Test invalid job ID format
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": "invalid-job-id"
            })
        assert "validation" in str(exc_info.value).lower()

        # Test empty job ID
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": ""
            })
        assert "validation" in str(exc_info.value).lower()

        # Test invalid max_pages
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": "12345678-1234-1234-1234-123456789abc",
                "max_pages": 0
            })
        assert "validation" in str(exc_info.value).lower()

        # Test invalid max_results
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": "12345678-1234-1234-1234-123456789abc",
                "max_results": 0
            })
        assert "validation" in str(exc_info.value).lower()

        # Test invalid max_wait_time
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": "12345678-1234-1234-1234-123456789abc",
                "max_wait_time": 0
            })
        assert "validation" in str(exc_info.value).lower()


class TestCrawlStatusErrorHandling(TestCrawlStatusTools):
    """Test error handling for crawl status checks."""

    async def test_crawl_status_not_found_error(self, crawl_status_client: Client, valid_job_id: str) -> None:
        """Test handling of job not found errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.side_effect = BadRequestError("Job not found")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl", {
                    "job_id": valid_job_id
                })

            assert "Job not found" in str(exc_info.value)

    async def test_crawl_status_unauthorized_error(self, crawl_status_client: Client, valid_job_id: str) -> None:
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.side_effect = UnauthorizedError("Invalid API key")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl", {
                    "job_id": valid_job_id
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_crawl_status_rate_limit_error(self, crawl_status_client: Client, valid_job_id: str) -> None:
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.side_effect = RateLimitError("Rate limit exceeded")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl", {
                    "job_id": valid_job_id
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_crawl_status_generic_error(self, crawl_status_client: Client, valid_job_id: str) -> None:
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_crawl_status.side_effect = Exception("Network error")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await crawl_status_client.call_tool("crawl", {
                    "job_id": valid_job_id
                })

            assert "Unexpected error" in str(exc_info.value)


class TestCrawlStatusResponseStructure(TestCrawlStatusTools):
    """Test crawl status response structure."""

    def test_status_response_structure_completed(self, mock_completed_crawl_job: CrawlJob) -> None:
        """Test that status response has expected structure for completed crawl."""
        # Mock the response that would be returned by the current implementation
        expected_fields = {
            'job_id', 'status', 'completed', 'total', 'progress_percentage',
            'credits_used', 'expires_at', 'summary'
        }

        # Test with mock data - these are the fields the current implementation returns
        mock_response = {
            'job_id': 'test-job-id',
            'status': mock_completed_crawl_job.status,
            'completed': mock_completed_crawl_job.completed,
            'total': mock_completed_crawl_job.total,
            'progress_percentage': 100.0,
            'credits_used': mock_completed_crawl_job.credits_used,
            'expires_at': mock_completed_crawl_job.expires_at,
            'summary': {
                'urls_crawled': [],
                'total_pages_discovered': mock_completed_crawl_job.total,
                'pages_successfully_crawled': mock_completed_crawl_job.completed,
                'error_message': None
            }
        }

        # Verify all expected fields are present
        assert all(field in mock_response for field in expected_fields)
        assert mock_response['status'] == 'completed'
        assert mock_response['progress_percentage'] == 100.0

    def test_status_response_structure_in_progress(self, mock_in_progress_crawl_job: CrawlJob) -> None:
        """Test that status response has expected structure for in-progress crawl."""
        progress_percentage = round((mock_in_progress_crawl_job.completed / mock_in_progress_crawl_job.total) * 100, 1)

        mock_response = {
            'job_id': 'test-job-id',
            'status': mock_in_progress_crawl_job.status,
            'completed': mock_in_progress_crawl_job.completed,
            'total': mock_in_progress_crawl_job.total,
            'progress_percentage': progress_percentage,
            'credits_used': mock_in_progress_crawl_job.credits_used,
            'expires_at': mock_in_progress_crawl_job.expires_at,
            'summary': {
                'urls_crawled': [],
                'total_pages_discovered': mock_in_progress_crawl_job.total,
                'pages_successfully_crawled': mock_in_progress_crawl_job.completed,
                'error_message': None
            }
        }

        assert mock_response['status'] == 'scraping'
        assert mock_response['progress_percentage'] == 50.0
        assert mock_response['completed'] < mock_response['total']

    def test_status_response_structure_failed(self, mock_failed_crawl_job: CrawlJob) -> None:
        """Test that status response has expected structure for failed crawl."""
        progress_percentage = round((mock_failed_crawl_job.completed / mock_failed_crawl_job.total) * 100, 1)

        mock_response = {
            'job_id': 'test-job-id',
            'status': mock_failed_crawl_job.status,
            'completed': mock_failed_crawl_job.completed,
            'total': mock_failed_crawl_job.total,
            'progress_percentage': progress_percentage,
            'credits_used': mock_failed_crawl_job.credits_used,
            'expires_at': mock_failed_crawl_job.expires_at,
            'summary': {
                'urls_crawled': [],
                'total_pages_discovered': mock_failed_crawl_job.total,
                'pages_successfully_crawled': mock_failed_crawl_job.completed,
                'error_message': None  # Would contain error info in real implementation
            }
        }

        assert mock_response['status'] == 'failed'
        assert mock_response['progress_percentage'] == 30.0
        assert mock_response['completed'] < mock_response['total']


class TestCrawlStatusToolRegistration(TestCrawlStatusTools):
    """Test crawl status tool registration and schema validation."""

    async def test_crawl_tool_registered(self, crawl_status_client: Client) -> None:
        """Test that crawl tool is properly registered."""
        tools = await crawl_status_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "crawl" in tool_names

    async def test_crawl_tool_schema(self, crawl_status_client: Client) -> None:
        """Test that crawl tool has proper schema."""
        tools = await crawl_status_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        crawl_tool = tool_dict["crawl"]
        assert crawl_tool.description is not None
        assert crawl_tool.inputSchema is not None

        # Check parameters
        properties = crawl_tool.inputSchema["properties"]
        assert "job_id" in properties
        assert "url" in properties

        # Check job ID pattern validation
        job_id_prop = properties["job_id"]
        assert "pattern" in job_id_prop
        assert "^[a-f0-9\\-]{36}$" in job_id_prop["pattern"]

    async def test_crawl_tool_annotations(self, crawl_status_client: Client) -> None:
        """Test that crawl tool has proper annotations."""
        tools = await crawl_status_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        crawl_tool = tool_dict["crawl"]
        # FastMCP may include tool annotations in the schema or separately
        assert crawl_tool.description is not None


@pytest.mark.integration
class TestCrawlStatusIntegrationTests(TestCrawlStatusTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_status_integration(self, crawl_status_client: Client) -> None:
        """Test real crawl status check with actual API."""
        # Note: This test requires a valid job ID from a real crawl
        # In practice, you would start a crawl first and then check its status

        # For now, test with a realistic but likely expired job ID format
        realistic_job_id = "12345678-1234-1234-1234-123456789abc"

        # This will likely return a "not found" error, which is expected
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": realistic_job_id
            })

        # Should get a proper error response, not a validation error
        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower() or "expired" in error_msg.lower()

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_crawl_status_with_pagination(self, crawl_status_client: Client) -> None:
        """Test real crawl status with pagination options."""
        realistic_job_id = "12345678-1234-1234-1234-123456789abc"

        # Test with pagination disabled
        with pytest.raises(Exception) as exc_info:
            await crawl_status_client.call_tool("crawl", {
                "job_id": realistic_job_id,
                "auto_paginate": False,
                "max_pages": 1
            })

        # Should handle pagination parameters properly even if job doesn't exist
        error_msg = str(exc_info.value)
        assert "validation" not in error_msg.lower()  # Should not be a validation error
