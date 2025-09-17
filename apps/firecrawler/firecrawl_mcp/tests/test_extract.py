"""
Tests for extraction tools in the Firecrawler MCP server.

This module tests the extract and extract_status tools using FastMCP in-memory
testing patterns with real API integration tests and comprehensive error scenario coverage.
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import AgentOptions, ExtractResponse, ScrapeOptions
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.extract import register_extract_tools


class TestExtractTools:
    """Test suite for extraction tools."""

    @pytest.fixture
    def extract_server(self, test_env):
        """Create FastMCP server with extraction tools registered."""
        server = FastMCP("TestExtractServer")
        register_extract_tools(server)
        return server

    @pytest.fixture
    async def extract_client(self, extract_server):
        """Create MCP client for extraction tools."""
        async with Client(extract_server) as client:
            yield client

    @pytest.fixture
    def mock_extract_response(self):
        """Mock successful extract response."""
        return ExtractResponse(
            id="extract-job-12345",
            status="completed",
            data=[
                {
                    "url": "https://example.com",
                    "extracted_data": {
                        "title": "Example Company",
                        "description": "A leading technology company",
                        "contact": {
                            "email": "contact@example.com",
                            "phone": "+1-555-0123"
                        },
                        "products": [
                            {"name": "Product A", "price": "$99"},
                            {"name": "Product B", "price": "$149"}
                        ]
                    },
                    "source": "https://example.com"
                }
            ]
        )

    @pytest.fixture
    def mock_extract_job_response(self):
        """Mock extract job initiation response."""
        return ExtractResponse(
            id="extract-job-12345",
            status="processing",
            url="https://api.firecrawl.dev/v2/extract/extract-job-12345"
        )

    @pytest.fixture
    def valid_extract_schema(self):
        """Valid extraction schema for testing."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "contact": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "phone": {"type": "string"}
                    }
                },
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["title"]
        }


class TestExtractBasicFunctionality(TestExtractTools):
    """Test basic extraction functionality."""

    async def test_extract_with_prompt_success(self, extract_client, mock_extract_response):
        """Test successful extraction with prompt."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.return_value = mock_extract_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await extract_client.call_tool("extract", {
                "urls": ["https://example.com"],
                "prompt": "Extract company information including name, description, and contact details"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "Example Company" in response_data
            assert "completed" in response_data

            mock_client.extract.assert_called_once()
            call_args = mock_client.extract.call_args[1]
            assert call_args["urls"] == ["https://example.com"]
            assert "company information" in call_args["prompt"]

    async def test_extract_with_schema_success(self, extract_client, mock_extract_response, valid_extract_schema):
        """Test successful extraction with schema."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.return_value = mock_extract_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await extract_client.call_tool("extract", {
                "urls": ["https://example.com"],
                "schema": valid_extract_schema
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "Example Company" in response_data

            call_args = mock_client.extract.call_args[1]
            assert call_args["schema"] == valid_extract_schema

    async def test_extract_with_prompt_and_schema(self, extract_client, mock_extract_response, valid_extract_schema):
        """Test extraction with both prompt and schema."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.return_value = mock_extract_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await extract_client.call_tool("extract", {
                "urls": ["https://example.com"],
                "prompt": "Extract company details",
                "schema": valid_extract_schema,
                "system_prompt": "You are an expert data extractor specializing in business information"
            })

            assert result.content[0].type == "text"

            call_args = mock_client.extract.call_args[1]
            assert call_args["prompt"] == "Extract company details"
            assert call_args["schema"] == valid_extract_schema
            assert "expert data extractor" in call_args["system_prompt"]

    async def test_extract_with_full_options(self, extract_client, mock_extract_response):
        """Test extraction with comprehensive options."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.return_value = mock_extract_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            scrape_options = ScrapeOptions(
                formats=["markdown"],
                onlyMainContent=True
            )

            agent_options = AgentOptions(
                model="gpt-4",
                temperature=0.1
            )

            result = await extract_client.call_tool("extract", {
                "urls": ["https://example.com", "https://example.com/about"],
                "prompt": "Extract all company information",
                "allow_external_links": True,
                "enable_web_search": True,
                "show_sources": True,
                "scrape_options": scrape_options.model_dump(),
                "ignore_invalid_urls": False,
                "integration": "custom-extractor",
                "agent": agent_options.model_dump()
            })

            assert result.content[0].type == "text"

            call_args = mock_client.extract.call_args[1]
            assert call_args["allow_external_links"] is True
            assert call_args["enable_web_search"] is True
            assert call_args["show_sources"] is True
            assert call_args["integration"] == "custom-extractor"

    async def test_extract_multiple_urls(self, extract_client, mock_extract_response):
        """Test extraction with multiple URLs."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.return_value = mock_extract_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            urls = [
                "https://example.com",
                "https://example.com/about",
                "https://example.com/products",
                "https://example.com/contact"
            ]

            result = await extract_client.call_tool("extract", {
                "urls": urls,
                "prompt": "Extract structured company data"
            })

            assert result.content[0].type == "text"

            call_args = mock_client.extract.call_args[1]
            assert call_args["urls"] == urls


class TestExtractValidation(TestExtractTools):
    """Test extraction parameter validation."""

    async def test_extract_empty_urls_error(self, extract_client):
        """Test extraction with empty URLs list."""
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": [],
                "prompt": "Extract data"
            })

        assert "URLs list cannot be empty" in str(exc_info.value)

    async def test_extract_too_many_urls_error(self, extract_client):
        """Test extraction with too many URLs."""
        urls = [f"https://example.com/page{i}" for i in range(101)]

        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": urls,
                "prompt": "Extract data"
            })

        assert "Too many URLs" in str(exc_info.value)

    async def test_extract_invalid_urls_validation(self, extract_client):
        """Test extraction with invalid URLs."""
        urls = ["https://example.com", "invalid-url", ""]

        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": urls,
                "prompt": "Extract data",
                "ignore_invalid_urls": False
            })

        assert "Invalid URLs found" in str(exc_info.value)

    async def test_extract_no_prompt_or_schema_error(self, extract_client):
        """Test extraction without prompt or schema."""
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": ["https://example.com"]
            })

        assert "Either prompt or schema must be provided" in str(exc_info.value)

    async def test_extract_parameter_length_validation(self, extract_client):
        """Test extraction parameter length validation."""
        # Test prompt too long
        long_prompt = "x" * 10001
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": ["https://example.com"],
                "prompt": long_prompt
            })
        assert "validation" in str(exc_info.value).lower()

        # Test system prompt too long
        long_system_prompt = "x" * 5001
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": ["https://example.com"],
                "prompt": "Extract data",
                "system_prompt": long_system_prompt
            })
        assert "validation" in str(exc_info.value).lower()

        # Test integration field too long
        long_integration = "x" * 101
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract", {
                "urls": ["https://example.com"],
                "prompt": "Extract data",
                "integration": long_integration
            })
        assert "validation" in str(exc_info.value).lower()


class TestExtractStatusFunctionality(TestExtractTools):
    """Test extract status checking functionality."""

    async def test_extract_status_success(self, extract_client, mock_extract_response):
        """Test successful extract status checking."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_extract_status.return_value = mock_extract_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await extract_client.call_tool("extract_status", {
                "job_id": "extract-job-12345"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "extract-job-12345" in response_data
            assert "completed" in response_data
            mock_client.get_extract_status.assert_called_once_with(job_id="extract-job-12345")

    async def test_extract_status_processing(self, extract_client):
        """Test extract status for processing job."""
        processing_response = ExtractResponse(
            id="extract-job-12345",
            status="processing",
            url="https://api.firecrawl.dev/v2/extract/extract-job-12345"
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_extract_status.return_value = processing_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await extract_client.call_tool("extract_status", {
                "job_id": "extract-job-12345"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "processing" in response_data

    async def test_extract_status_failed(self, extract_client):
        """Test extract status for failed job."""
        failed_response = ExtractResponse(
            id="extract-job-12345",
            status="failed",
            error="Extraction failed due to invalid content"
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_extract_status.return_value = failed_response
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            result = await extract_client.call_tool("extract_status", {
                "job_id": "extract-job-12345"
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "failed" in response_data

    async def test_extract_status_empty_job_id_error(self, extract_client):
        """Test extract status with empty job ID."""
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract_status", {"job_id": ""})

        assert "Job ID cannot be empty" in str(exc_info.value)

    async def test_extract_status_job_id_validation(self, extract_client):
        """Test extract status job ID validation."""
        # Test job ID too long
        long_job_id = "x" * 257
        with pytest.raises(Exception) as exc_info:
            await extract_client.call_tool("extract_status", {
                "job_id": long_job_id
            })
        assert "validation" in str(exc_info.value).lower()


class TestExtractErrorHandling(TestExtractTools):
    """Test error handling for extraction tools."""

    async def test_extract_unauthorized_error(self, extract_client):
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.side_effect = UnauthorizedError("Invalid API key")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await extract_client.call_tool("extract", {
                    "urls": ["https://example.com"],
                    "prompt": "Extract data"
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_extract_rate_limit_error(self, extract_client):
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.side_effect = RateLimitError("Rate limit exceeded")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await extract_client.call_tool("extract", {
                    "urls": ["https://example.com"],
                    "prompt": "Extract data"
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_extract_bad_request_error(self, extract_client):
        """Test handling of bad request errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.side_effect = BadRequestError("Invalid extraction parameters")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await extract_client.call_tool("extract", {
                    "urls": ["https://example.com"],
                    "prompt": "Extract data"
                })

            assert "Invalid extraction parameters" in str(exc_info.value)

    async def test_extract_generic_error(self, extract_client):
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.extract.side_effect = Exception("Network error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await extract_client.call_tool("extract", {
                    "urls": ["https://example.com"],
                    "prompt": "Extract data"
                })

            assert "Unexpected error" in str(exc_info.value)

    async def test_extract_status_generic_error(self, extract_client):
        """Test handling of generic errors in status check."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client_manager = Mock()
            mock_client = Mock()
            mock_client.get_extract_status.side_effect = Exception("Network error")
            mock_client_manager.client = mock_client
            mock_get_client.return_value = mock_client_manager

            with pytest.raises(Exception) as exc_info:
                await extract_client.call_tool("extract_status", {
                    "job_id": "extract-job-12345"
                })

            assert "Unexpected error" in str(exc_info.value)


class TestExtractToolRegistration(TestExtractTools):
    """Test extraction tool registration and availability."""

    async def test_extract_tools_are_registered(self, extract_client):
        """Test that all extraction tools are properly registered."""
        tools = await extract_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "extract" in tool_names
        assert "extract_status" in tool_names

    async def test_extract_tool_schemas_are_valid(self, extract_client):
        """Test that extraction tool schemas are properly defined."""
        tools = await extract_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        # Test extract tool schema
        extract_tool = tool_dict["extract"]
        assert extract_tool.description is not None
        assert extract_tool.inputSchema is not None
        assert "urls" in extract_tool.inputSchema["properties"]

        # Test extract_status tool schema
        extract_status_tool = tool_dict["extract_status"]
        assert extract_status_tool.description is not None
        assert extract_status_tool.inputSchema is not None
        assert "job_id" in extract_status_tool.inputSchema["properties"]

    def test_register_extract_tools_returns_tool_names(self):
        """Test that register_extract_tools returns the correct tool names."""
        server = FastMCP("TestServer")
        tool_names = register_extract_tools(server)

        assert tool_names == ["extract", "extract_status"]


@pytest.mark.integration
class TestExtractIntegrationTests(TestExtractTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_extract_integration(self, extract_client):
        """Test real extraction with actual API."""
        result = await extract_client.call_tool("extract", {
            "urls": ["https://httpbin.org/json"],
            "prompt": "Extract any JSON data structure and format information"
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text
        # Should contain extracted data from httpbin.org/json
        assert "slideshow" in response_data or "completed" in response_data

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_extract_with_schema(self, extract_client):
        """Test real extraction with schema validation."""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["title"]
        }

        result = await extract_client.call_tool("extract", {
            "urls": ["https://httpbin.org/html"],
            "schema": schema,
            "prompt": "Extract the page title and main content"
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text
        assert "Herman Melville" in response_data or "completed" in response_data
