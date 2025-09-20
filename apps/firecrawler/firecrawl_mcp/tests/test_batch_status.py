"""
Tests for batch status monitoring in the Firecrawler MCP server.

This module focuses on comprehensive batch status checking functionality,
including job monitoring, pagination, and status transitions.
"""

import os
from collections.abc import AsyncGenerator
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import BatchScrapeJob, Document
from firecrawl.v2.utils.error_handler import (
    FirecrawlError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.scrape import register_scrape_tools


class TestBatchStatusOperations:
    """Test suite for batch status monitoring operations."""

    @pytest.fixture
    def status_server(self) -> FastMCP:
        """Create FastMCP server with batch status tools."""
        server = FastMCP("TestStatusServer")
        register_scrape_tools(server)
        return server

    @pytest.fixture
    async def status_client(self, status_server: FastMCP) -> AsyncGenerator[Client, None]:
        """Create MCP client for status operations."""
        async with Client(status_server) as client:
            yield client

    @pytest.fixture
    def sample_documents(self) -> list[Document]:
        """Create sample documents for test responses."""
        return [
            Document(
                content="# Page 1\n\nContent of page 1",
                metadata={
                    "title": "Page 1",
                    "url": "https://example.com/page1",
                    "statusCode": 200,
                    "language": "en"
                },
                markdown="# Page 1\n\nContent of page 1"
            ),
            Document(
                content="# Page 2\n\nContent of page 2",
                metadata={
                    "title": "Page 2",
                    "url": "https://example.com/page2",
                    "statusCode": 200,
                    "language": "en"
                },
                markdown="# Page 2\n\nContent of page 2"
            ),
            Document(
                content="# Page 3\n\nContent of page 3",
                metadata={
                    "title": "Page 3",
                    "url": "https://example.com/page3",
                    "statusCode": 200,
                    "language": "en"
                },
                markdown="# Page 3\n\nContent of page 3"
            )
        ]

    def create_batch_job(
        self,
        job_id: str = "test-job-123",
        status: str = "completed",
        total: int = 10,
        completed: int = 10,
        credits_used: int = 25,
        data: list[Document] | None = None
    ) -> BatchScrapeJob:
        """Helper to create batch job objects."""
        return BatchScrapeJob(
            id=job_id,
            status=status,
            total=total,
            completed=completed,
            creditsUsed=credits_used,
            expiresAt="2024-12-31T23:59:59Z",
            data=data or []
        )


class TestBatchStatusBasicFunctionality(TestBatchStatusOperations):
    """Test basic batch status functionality."""

    async def test_batch_status_completed_job(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test status check for completed job."""
        completed_job = self.create_batch_job(
            job_id="completed-job-123",
            status="completed",
            total=3,
            completed=3,
            credits_used=9,
            data=sample_documents
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = completed_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "completed-job-123"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "completed-job-123" in response_data
            assert "completed" in response_data
            assert "3/3" in response_data

            mock_client.get_batch_scrape_status.assert_called_once_with(
                job_id="completed-job-123",
                pagination_config=None
            )

    async def test_batch_status_in_progress_job(self, status_client: Client) -> None:
        """Test status check for in-progress job."""
        in_progress_job = self.create_batch_job(
            job_id="progress-job-456",
            status="scraping",
            total=10,
            completed=6,
            credits_used=15,
            data=[]
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = in_progress_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "progress-job-456"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "progress-job-456" in response_data
            assert "scraping" in response_data
            assert "6/10" in response_data

    async def test_batch_status_failed_job(self, status_client: Client) -> None:
        """Test status check for failed job."""
        failed_job = self.create_batch_job(
            job_id="failed-job-789",
            status="failed",
            total=5,
            completed=2,
            credits_used=5,
            data=[]
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = failed_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "failed-job-789"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "failed-job-789" in response_data
            assert "failed" in response_data
            assert "2/5" in response_data

    async def test_batch_status_cancelled_job(self, status_client: Client) -> None:
        """Test status check for cancelled job."""
        cancelled_job = self.create_batch_job(
            job_id="cancelled-job-000",
            status="cancelled",
            total=8,
            completed=4,
            credits_used=10,
            data=[]
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = cancelled_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "cancelled-job-000"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "cancelled-job-000" in response_data
            assert "cancelled" in response_data
            assert "4/8" in response_data


class TestBatchStatusPagination(TestBatchStatusOperations):
    """Test pagination functionality in batch status."""

    async def test_batch_status_default_pagination(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test batch status with default pagination (auto_paginate=True)."""
        job_with_data = self.create_batch_job(
            job_id="paginated-job-123",
            status="completed",
            total=3,
            completed=3,
            credits_used=9,
            data=sample_documents
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = job_with_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "paginated-job-123"
            })

            assert result.content[0].type == "text"

            # Verify default pagination (auto_paginate=True, no limits)
            mock_client.get_batch_scrape_status.assert_called_once_with(
                job_id="paginated-job-123",
                pagination_config=None
            )

    async def test_batch_status_disabled_pagination(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test batch status with disabled auto-pagination."""
        job_with_data = self.create_batch_job(
            job_id="no-pagination-job",
            status="completed",
            data=sample_documents
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = job_with_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "no-pagination-job",
                "auto_paginate": False
            })

            assert result.content[0].type == "text"

            # Verify pagination config was created with auto_paginate=False
            call_args = mock_client.get_batch_scrape_status.call_args
            pagination_config = call_args[1]["pagination_config"]
            assert pagination_config is not None
            assert pagination_config.auto_paginate is False

    async def test_batch_status_max_pages_limit(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test batch status with max pages limit."""
        job_with_data = self.create_batch_job(data=sample_documents)

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = job_with_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "test-job-123",
                "max_pages": 5
            })

            assert result.content[0].type == "text"

            call_args = mock_client.get_batch_scrape_status.call_args
            pagination_config = call_args[1]["pagination_config"]
            assert pagination_config.max_pages == 5

    async def test_batch_status_max_results_limit(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test batch status with max results limit."""
        job_with_data = self.create_batch_job(data=sample_documents)

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = job_with_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "test-job-123",
                "max_results": 50
            })

            assert result.content[0].type == "text"

            call_args = mock_client.get_batch_scrape_status.call_args
            pagination_config = call_args[1]["pagination_config"]
            assert pagination_config.max_results == 50

    async def test_batch_status_combined_pagination_limits(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test batch status with combined pagination limits."""
        job_with_data = self.create_batch_job(data=sample_documents)

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = job_with_data
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "test-job-123",
                "auto_paginate": False,
                "max_pages": 3,
                "max_results": 25
            })

            assert result.content[0].type == "text"

            call_args = mock_client.get_batch_scrape_status.call_args
            pagination_config = call_args[1]["pagination_config"]
            assert pagination_config.auto_paginate is False
            assert pagination_config.max_pages == 3
            assert pagination_config.max_results == 25


class TestBatchStatusValidation(TestBatchStatusOperations):
    """Test parameter validation for batch status."""

    async def test_batch_status_empty_job_id_error(self, status_client: Client) -> None:
        """Test batch status with empty job ID."""
        with pytest.raises(ToolError) as exc_info:
            await status_client.call_tool("batch_status", {"job_id": ""})

        assert "Job ID cannot be empty" in str(exc_info.value)

    async def test_batch_status_whitespace_job_id_error(self, status_client: Client) -> None:
        """Test batch status with whitespace-only job ID."""
        with pytest.raises(ToolError) as exc_info:
            await status_client.call_tool("batch_status", {"job_id": "   "})

        assert "Job ID cannot be empty" in str(exc_info.value)

    async def test_batch_status_pagination_parameter_validation(self, status_client: Client) -> None:
        """Test pagination parameter validation."""
        # Test invalid max_pages values
        invalid_max_pages = [0, -1, -10]
        for invalid_value in invalid_max_pages:
            with pytest.raises(ToolError):
                await status_client.call_tool("batch_status", {
                    "job_id": "test-job",
                    "max_pages": invalid_value
                })

        # Test invalid max_results values
        invalid_max_results = [0, -1, -50]
        for invalid_value in invalid_max_results:
            with pytest.raises(ToolError):
                await status_client.call_tool("batch_status", {
                    "job_id": "test-job",
                    "max_results": invalid_value
                })

        # Test max values
        with pytest.raises(ToolError):
            await status_client.call_tool("batch_status", {
                "job_id": "test-job",
                "max_pages": 101  # Above limit
            })

        with pytest.raises(ToolError):
            await status_client.call_tool("batch_status", {
                "job_id": "test-job",
                "max_results": 10001  # Above limit
            })

    async def test_batch_status_job_id_length_validation(self, status_client: Client) -> None:
        """Test job ID length validation."""
        # Very long job ID (over 256 characters)
        long_job_id = "a" * 257

        with pytest.raises(ToolError):
            await status_client.call_tool("batch_status", {
                "job_id": long_job_id
            })


class TestBatchStatusProgressReporting(TestBatchStatusOperations):
    """Test progress reporting in batch status."""

    async def test_batch_status_progress_calculation(self, status_client: Client) -> None:
        """Test progress calculation for different job states."""
        test_scenarios = [
            (10, 0),    # Just started
            (10, 3),    # 30% complete
            (10, 5),    # 50% complete
            (10, 8),    # 80% complete
            (10, 10),   # Completed
        ]

        for total, completed in test_scenarios:
            job = self.create_batch_job(
                status="scraping",
                total=total,
                completed=completed
            )

            with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
                mock_client_manager = Mock()
                mock_client = Mock()
                mock_client.get_batch_scrape_status.return_value = job
                mock_client_manager.client = mock_client
                mock_get_client.return_value = mock_client_manager

                result = await status_client.call_tool("batch_status", {
                    "job_id": "progress-test"
                })

                assert result.content[0].type == "text"
                response_data = result.content[0].text
                assert f"{completed}/{total}" in response_data

    async def test_batch_status_progress_edge_cases(self, status_client: Client) -> None:
        """Test progress calculation edge cases."""
        # Division by zero case (total = 0)
        edge_case_job = BatchScrapeJob(
            id="edge-case-job",
            status="completed",
            total=0,
            completed=0,
            creditsUsed=0,
            expiresAt="2024-12-31T23:59:59Z",
            data=[]
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = edge_case_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "edge-case-job"
            })

            assert result.content[0].type == "text"
            # Should handle division by zero gracefully


class TestBatchStatusErrorHandling(TestBatchStatusOperations):
    """Test error handling in batch status operations."""

    async def test_batch_status_job_not_found(self, status_client: Client) -> None:
        """Test handling of job not found error."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.side_effect = FirecrawlError("Job not found")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(ToolError) as exc_info:
                await status_client.call_tool("batch_status", {
                    "job_id": "nonexistent-job"
                })

            assert "Firecrawl API error" in str(exc_info.value)

    async def test_batch_status_unauthorized_error(self, status_client: Client) -> None:
        """Test handling of unauthorized error."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.side_effect = UnauthorizedError("Invalid API key")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(ToolError) as exc_info:
                await status_client.call_tool("batch_status", {
                    "job_id": "test-job"
                })

            assert "Firecrawl API error" in str(exc_info.value)

    async def test_batch_status_client_initialization_error(self, status_client: Client) -> None:
        """Test error when client cannot be initialized."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Client not available")

            with pytest.raises(ToolError) as exc_info:
                await status_client.call_tool("batch_status", {
                    "job_id": "test-job"
                })

            assert "Unexpected error" in str(exc_info.value)

    async def test_batch_status_generic_api_error(self, status_client: Client) -> None:
        """Test handling of generic API errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.side_effect = FirecrawlError("API error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(ToolError) as exc_info:
                await status_client.call_tool("batch_status", {
                    "job_id": "test-job"
                })

            assert "Firecrawl API error" in str(exc_info.value)


class TestBatchStatusDataHandling(TestBatchStatusOperations):
    """Test data handling in batch status responses."""

    async def test_batch_status_with_large_dataset(self, status_client: Client) -> None:
        """Test batch status with large amount of result data."""
        # Create a large dataset
        large_documents = []
        for i in range(100):
            doc = Document(
                content=f"# Page {i}\n\nContent for page {i}" + "x" * 1000,  # Add bulk content
                metadata={
                    "title": f"Page {i}",
                    "url": f"https://example.com/page{i}",
                    "statusCode": 200
                },
                markdown=f"# Page {i}\n\nContent for page {i}"
            )
            large_documents.append(doc)

        large_job = self.create_batch_job(
            job_id="large-data-job",
            status="completed",
            total=100,
            completed=100,
            credits_used=200,
            data=large_documents
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = large_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "large-data-job"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "large-data-job" in response_data
            # Should handle large datasets without errors

    async def test_batch_status_empty_data_set(self, status_client: Client) -> None:
        """Test batch status with empty data set."""
        empty_job = self.create_batch_job(
            job_id="empty-job",
            status="completed",
            total=5,
            completed=5,
            credits_used=10,
            data=[]
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = empty_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "empty-job"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "empty-job" in response_data
            assert "completed" in response_data

    async def test_batch_status_partial_data_set(self, status_client: Client, sample_documents: list[Document]) -> None:
        """Test batch status where data count doesn't match completed count."""
        # Job says 10 completed but only has 3 documents
        partial_job = self.create_batch_job(
            job_id="partial-job",
            status="completed",
            total=10,
            completed=10,
            credits_used=25,
            data=sample_documents  # Only 3 documents
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_batch_scrape_status.return_value = partial_job
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await status_client.call_tool("batch_status", {
                "job_id": "partial-job"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "partial-job" in response_data
            # Should handle the mismatch gracefully


@pytest.mark.integration
class TestBatchStatusIntegration(TestBatchStatusOperations):
    """Integration tests for batch status with real API."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_batch_status_check(self, status_client: Client) -> None:
        """Test real batch status checking."""
        # Note: This test requires a valid job ID from a previous batch scrape
        # In a real scenario, we would first create a batch job, then check its status

        # For this test, we'll check if the error handling works correctly
        # when checking a non-existent job
        with pytest.raises(ToolError) as exc_info:
            await status_client.call_tool("batch_status", {
                "job_id": "nonexistent-job-12345"
            })

        # Should get a proper error message
        assert "Firecrawl API error" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_batch_status_with_pagination(self, status_client: Client) -> None:
        """Test real batch status with pagination options."""
        # This test demonstrates how pagination would work with a real job
        # In practice, this would use a valid job ID

        try:
            result = await status_client.call_tool("batch_status", {
                "job_id": "test-job-for-pagination",
                "auto_paginate": False,
                "max_results": 10
            })

            # If we somehow get a valid response, verify the structure
            assert result.content[0].type == "text"

        except Exception as e:
            # Expected for non-existent job - verify it's the right type of error
            assert "Firecrawl API error" in str(e) or "not found" in str(e).lower()
