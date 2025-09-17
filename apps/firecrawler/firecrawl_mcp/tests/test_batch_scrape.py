"""
Tests for batch scraping operations in the Firecrawler MCP server.

This module focuses specifically on comprehensive batch scraping functionality,
including parallel processing, error handling, and edge cases.
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import (
    BatchScrapeResponse,
)
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    FirecrawlError,
    InternalServerError,
    RateLimitError,
)

from firecrawl_mcp.tools.scrape import register_scrape_tools


class TestBatchScrapeOperations:
    """Test suite for batch scraping operations."""

    @pytest.fixture
    def batch_server(self, test_env):
        """Create FastMCP server with batch scraping tools."""
        server = FastMCP("TestBatchServer")
        register_scrape_tools(server)
        return server

    @pytest.fixture
    async def batch_client(self, batch_server):
        """Create MCP client for batch operations."""
        async with Client(batch_server) as client:
            yield client

    @pytest.fixture
    def large_url_list(self):
        """Generate a large list of URLs for testing."""
        return [f"https://example.com/page{i}" for i in range(1, 101)]

    @pytest.fixture
    def mixed_url_list(self):
        """Generate a mixed list of valid and invalid URLs."""
        return [
            "https://example.com/page1",
            "http://example.com/page2",
            "invalid-url",
            "",
            "https://example.com/page3",
            "ftp://example.com/file",  # Unsupported protocol
            "https://example.com/page4",
        ]

    @pytest.fixture
    def mock_batch_response_active(self):
        """Mock batch response in active state."""
        return BatchScrapeResponse(
            id="batch-job-active-123",
            url="https://api.firecrawl.dev/v2/batch/scrape/batch-job-active-123",
            status="active"
        )

    @pytest.fixture
    def mock_batch_response_queued(self):
        """Mock batch response in queued state."""
        return BatchScrapeResponse(
            id="batch-job-queued-456",
            url="https://api.firecrawl.dev/v2/batch/scrape/batch-job-queued-456",
            status="queued"
        )


class TestBatchScrapeParameterValidation(TestBatchScrapeOperations):
    """Test parameter validation for batch scraping."""

    async def test_batch_scrape_url_count_limits(self, batch_client):
        """Test URL count validation limits."""
        # Test minimum (should pass)
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            # Single URL should work
            result = await batch_client.call_tool("batch_scrape", {
                "urls": ["https://example.com"]
            })
            assert result.content[0].type == "text"

        # Test maximum (should fail)
        urls_over_limit = [f"https://example.com/page{i}" for i in range(1001)]
        with pytest.raises(Exception) as exc_info:
            await batch_client.call_tool("batch_scrape", {
                "urls": urls_over_limit
            })
        assert "Too many URLs" in str(exc_info.value)

    async def test_batch_scrape_url_format_validation(self, batch_client, mixed_url_list):
        """Test URL format validation."""
        # Test with ignore_invalid_urls=False (default)
        with pytest.raises(Exception) as exc_info:
            await batch_client.call_tool("batch_scrape", {
                "urls": mixed_url_list,
                "ignore_invalid_urls": False
            })
        assert "Invalid URLs found" in str(exc_info.value)

        # Test with ignore_invalid_urls=True should succeed
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await batch_client.call_tool("batch_scrape", {
                "urls": mixed_url_list,
                "ignore_invalid_urls": True
            })
            assert result.content[0].type == "text"

    async def test_batch_scrape_concurrency_validation(self, batch_client):
        """Test concurrency parameter validation."""
        test_cases = [
            {"max_concurrency": -1, "should_fail": True},
            {"max_concurrency": 0, "should_fail": True},
            {"max_concurrency": 1, "should_fail": False},
            {"max_concurrency": 25, "should_fail": False},
            {"max_concurrency": 50, "should_fail": False},
            {"max_concurrency": 51, "should_fail": True},
            {"max_concurrency": 100, "should_fail": True},
        ]

        for test_case in test_cases:
            if test_case["should_fail"]:
                with pytest.raises(Exception):
                    await batch_client.call_tool("batch_scrape", {
                        "urls": ["https://example.com"],
                        "max_concurrency": test_case["max_concurrency"]
                    })
            else:
                with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
                    mock_client_manager = Mock()
                    mock_client = Mock()
                    mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                        id="test-job", url="test-url", status="active"
                    )
                    mock_client_manager.client = mock_client
                    mock_get_client.return_value = mock_client_manager

                    result = await batch_client.call_tool("batch_scrape", {
                        "urls": ["https://example.com"],
                        "max_concurrency": test_case["max_concurrency"]
                    })
                    assert result.content[0].type == "text"

    async def test_batch_scrape_webhook_validation(self, batch_client):
        """Test webhook URL validation."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            # Valid webhook URL
            result = await batch_client.call_tool("batch_scrape", {
                "urls": ["https://example.com"],
                "webhook": "https://webhook.example.com/notify"
            })
            assert result.content[0].type == "text"

            # Verify webhook was passed to client
            call_args = mock_client.start_batch_scrape.call_args
            assert call_args[1]["webhook"] == "https://webhook.example.com/notify"


class TestBatchScrapeExecution(TestBatchScrapeOperations):
    """Test batch scraping execution scenarios."""

    async def test_batch_scrape_with_custom_options(self, batch_client):
        """Test batch scraping with custom scrape options."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            options = {
                "formats": ["markdown", "html"],
                "onlyMainContent": True,
                "includeTags": ["h1", "h2", "p", "a"],
                "excludeTags": ["script", "style"],
                "timeout": 45000,
                "screenshot": True
            }

            result = await batch_client.call_tool("batch_scrape", {
                "urls": ["https://example.com/page1", "https://example.com/page2"],
                "options": options,
                "max_concurrency": 3
            })

            assert result.content[0].type == "text"

            # Verify options were passed correctly
            call_args = mock_client.start_batch_scrape.call_args
            passed_options = call_args[1]["options"]
            assert passed_options is not None

    async def test_batch_scrape_large_scale(self, batch_client, large_url_list):
        """Test batch scraping with large number of URLs."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="large-batch-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await batch_client.call_tool("batch_scrape", {
                "urls": large_url_list,
                "max_concurrency": 10
            })

            assert result.content[0].type == "text"

            # Verify all URLs were passed
            call_args = mock_client.start_batch_scrape.call_args
            assert len(call_args[1]["urls"]) == 100

    async def test_batch_scrape_progress_reporting(self, batch_client):
        """Test progress reporting during batch scrape initialization."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="progress-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            urls = [f"https://example.com/page{i}" for i in range(50)]

            result = await batch_client.call_tool("batch_scrape", {
                "urls": urls,
                "max_concurrency": 5
            })

            assert result.content[0].type == "text"
            # Progress reporting is internal - we just verify the call succeeded


class TestBatchScrapeErrorScenarios(TestBatchScrapeOperations):
    """Test error scenarios in batch scraping."""

    async def test_batch_scrape_client_initialization_error(self, batch_client):
        """Test error when client cannot be initialized."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Client initialization failed")

            with pytest.raises(Exception) as exc_info:
                await batch_client.call_tool("batch_scrape", {
                    "urls": ["https://example.com"]
                })

            assert "Unexpected error" in str(exc_info.value)

    async def test_batch_scrape_api_error_handling(self, batch_client):
        """Test handling of various API errors."""
        error_scenarios = [
            (BadRequestError("Invalid request format"), "Firecrawl API error"),
            (RateLimitError("Rate limit exceeded"), "Firecrawl API error"),
            (InternalServerError("Server error"), "Firecrawl API error"),
            (FirecrawlError("Generic API error"), "Firecrawl API error"),
        ]

        for error, expected_message in error_scenarios:
            with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
                mock_client_manager = Mock()
                mock_client = Mock()
                mock_client.start_batch_scrape.side_effect = error
                mock_client_manager.client = mock_client
                mock_get_client.return_value = mock_client_manager

                with pytest.raises(Exception) as exc_info:
                    await batch_client.call_tool("batch_scrape", {
                        "urls": ["https://example.com"]
                    })

                assert expected_message in str(exc_info.value)

    async def test_batch_scrape_network_timeout(self, batch_client):
        """Test handling of network timeouts."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.side_effect = TimeoutError("Network timeout")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await batch_client.call_tool("batch_scrape", {
                    "urls": ["https://example.com"]
                })

            assert "Unexpected error" in str(exc_info.value)


class TestBatchScrapePerformance(TestBatchScrapeOperations):
    """Test performance aspects of batch scraping."""

    async def test_batch_scrape_response_time(self, batch_client):
        """Test that batch scrape initialization is reasonably fast."""
        import time

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="perf-test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            start_time = time.time()

            result = await batch_client.call_tool("batch_scrape", {
                "urls": [f"https://example.com/page{i}" for i in range(20)]
            })

            end_time = time.time()
            execution_time = end_time - start_time

            assert result.content[0].type == "text"
            # Should complete quickly (under 1 second for mocked call)
            assert execution_time < 1.0

    async def test_batch_scrape_memory_efficiency(self, batch_client):
        """Test memory efficiency with large URL lists."""
        # This test ensures that large URL lists don't cause memory issues
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="memory-test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            # Create a large list of URLs
            large_urls = [f"https://example.com/page{i}" for i in range(500)]

            result = await batch_client.call_tool("batch_scrape", {
                "urls": large_urls,
                "max_concurrency": 10
            })

            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory

            assert result.content[0].type == "text"
            # Memory increase should be reasonable (less than 50MB for this test)
            assert memory_increase < 50 * 1024 * 1024


class TestBatchScrapeEdgeCases(TestBatchScrapeOperations):
    """Test edge cases in batch scraping."""

    async def test_batch_scrape_duplicate_urls(self, batch_client):
        """Test batch scraping with duplicate URLs."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="duplicate-test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            urls_with_duplicates = [
                "https://example.com/page1",
                "https://example.com/page2",
                "https://example.com/page1",  # Duplicate
                "https://example.com/page3",
                "https://example.com/page2",  # Duplicate
            ]

            result = await batch_client.call_tool("batch_scrape", {
                "urls": urls_with_duplicates
            })

            assert result.content[0].type == "text"

            # Verify all URLs (including duplicates) were passed to the API
            call_args = mock_client.start_batch_scrape.call_args
            assert len(call_args[1]["urls"]) == 5

    async def test_batch_scrape_unicode_urls(self, batch_client):
        """Test batch scraping with Unicode URLs."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="unicode-test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            unicode_urls = [
                "https://example.com/测试页面",
                "https://example.com/página-de-prueba",
                "https://example.com/тестовая-страница",
                "https://example.com/テストページ"
            ]

            result = await batch_client.call_tool("batch_scrape", {
                "urls": unicode_urls
            })

            assert result.content[0].type == "text"

    async def test_batch_scrape_very_long_urls(self, batch_client):
        """Test batch scraping with very long URLs."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.start_batch_scrape.return_value = BatchScrapeResponse(
                id="long-url-test-job", url="test-url", status="active"
            )
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            # Create a very long URL (under typical browser limits)
            long_path = "a" * 1000
            long_url = f"https://example.com/{''.join([long_path, '?param=', long_path])}"

            result = await batch_client.call_tool("batch_scrape", {
                "urls": [long_url]
            })

            assert result.content[0].type == "text"


@pytest.mark.integration
class TestBatchScrapeIntegration(TestBatchScrapeOperations):
    """Integration tests for batch scraping with real API."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_batch_scrape_small_scale(self, batch_client):
        """Test real batch scraping with a small number of URLs."""
        test_urls = [
            "https://httpbin.org/html",
            "https://httpbin.org/json",
            "https://httpbin.org/headers"
        ]

        result = await batch_client.call_tool("batch_scrape", {
            "urls": test_urls,
            "max_concurrency": 2
        })

        assert result.content[0].type == "text"

        # Verify we got a job ID back
        import json
        batch_data = json.loads(result.content[0].text)
        assert "id" in batch_data
        assert batch_data["status"] in ["active", "queued"]

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_batch_scrape_with_options(self, batch_client):
        """Test real batch scraping with custom options."""
        test_urls = [
            "https://httpbin.org/html"
        ]

        options = {
            "formats": ["markdown"],
            "onlyMainContent": True,
            "timeout": 30000
        }

        result = await batch_client.call_tool("batch_scrape", {
            "urls": test_urls,
            "options": options
        })

        assert result.content[0].type == "text"

        import json
        batch_data = json.loads(result.content[0].text)
        assert "id" in batch_data
