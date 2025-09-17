"""
Tests for vector search tools in the Firecrawler MCP server.

This module tests the firerag tool using FastMCP in-memory testing patterns
with real API integration tests and comprehensive error scenario coverage.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import Client, FastMCP
from firecrawl.v2.types import (
    VectorSearchData,
    VectorSearchResponse,
    VectorSearchResult,
    VectorSearchTiming,
)
from firecrawl.v2.utils.error_handler import (
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.tools.firerag import (
    FireRAGConfig,
    _get_default_system_prompt,
    _perform_llm_synthesis,
    register_firerag_tools,
)


class TestFireRAGTools:
    """Test suite for firerag tools."""

    @pytest.fixture
    def firerag_server(self, test_env):
        """Create FastMCP server with firerag tools registered."""
        server = FastMCP("TestFireRAGServer")
        register_firerag_tools(server)
        return server

    @pytest.fixture
    async def firerag_client(self, firerag_server):
        """Create MCP client for firerag tools."""
        async with Client(firerag_server) as client:
            yield client

    @pytest.fixture
    def mock_vector_search_results(self):
        """Mock vector search results."""
        return [
            VectorSearchResult(
                id="doc-1",
                url="https://docs.python.org/3/tutorial/",
                title="Python Tutorial",
                content="Python is a powerful programming language that is easy to learn and use. This tutorial covers the basics of Python programming including syntax, data types, functions, and object-oriented programming concepts.",
                similarity=0.95,
                metadata={
                    "sourceURL": "https://docs.python.org/3/tutorial/",
                    "domain": "docs.python.org",
                    "repository": "python-docs",
                    "content_type": "tutorial",
                    "date_created": "2024-01-01"
                }
            ),
            VectorSearchResult(
                id="doc-2",
                url="https://docs.python.org/3/library/",
                title="Python Standard Library",
                content="The Python Standard Library contains modules for common programming tasks including file I/O, system calls, internet protocols, and data processing. It provides a rich set of modules and packages.",
                similarity=0.87,
                metadata={
                    "sourceURL": "https://docs.python.org/3/library/",
                    "domain": "docs.python.org",
                    "repository": "python-docs",
                    "content_type": "api-docs",
                    "date_created": "2024-01-01"
                }
            ),
            VectorSearchResult(
                id="doc-3",
                url="https://github.com/python/cpython/blob/main/README.rst",
                title="CPython README",
                content="CPython is the reference implementation of the Python programming language. Written in C and Python, CPython is the default and most widely used implementation of the Python language.",
                similarity=0.82,
                metadata={
                    "sourceURL": "https://github.com/python/cpython/blob/main/README.rst",
                    "domain": "github.com",
                    "repository": "cpython",
                    "repository_org": "python",
                    "repository_full_name": "python/cpython",
                    "content_type": "readme",
                    "date_created": "2024-01-01"
                }
            )
        ]

    @pytest.fixture
    def mock_vector_search_response(self, mock_vector_search_results):
        """Mock complete vector search response."""
        vector_data = VectorSearchData(
            results=mock_vector_search_results,
            total_results=len(mock_vector_search_results),
            timing=VectorSearchTiming(
                query_embedding_ms=50,
                vector_search_ms=120,
                total_ms=170
            )
        )

        return VectorSearchResponse(
            success=True,
            data=vector_data
        )

    @pytest.fixture
    def valid_firerag_config(self):
        """Valid FireRAG configuration for testing."""
        return FireRAGConfig(
            mode="synthesis",
            llm_provider="openai",
            model="gpt-3.5-turbo",
            temperature=0.1,
            max_tokens=500,
            system_prompt="You are a helpful assistant specialized in Python programming."
        )


class TestFireRAGBasicFunctionality(TestFireRAGTools):
    """Test basic FireRAG functionality."""

    async def test_firerag_raw_mode_success(self, firerag_client, mock_vector_search_response):
        """Test successful vector search in raw mode."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            config = FireRAGConfig(mode="raw")
            result = await firerag_client.call_tool("firerag", {
                "query": "How to learn Python programming?",
                "config": config.model_dump()
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "Python Tutorial" in response_data
            assert "3" in response_data  # Should mention 3 results
            assert "synthesis" not in response_data.lower()  # Raw mode shouldn't mention synthesis

    async def test_firerag_synthesis_mode_success(self, firerag_client, mock_vector_search_response):
        """Test successful vector search with LLM synthesis."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            # Mock the LLM synthesis
            with patch("firecrawl_mcp.tools.firerag._perform_llm_synthesis") as mock_synthesis:
                mock_synthesis.return_value = {
                    "answer": "To learn Python programming, start with the official Python tutorial at docs.python.org. The tutorial covers basic syntax, data types, and programming concepts. You can also explore the Python Standard Library for built-in modules and functions.",
                    "model": "gpt-3.5-turbo",
                    "tokens": 75,
                    "timing": {"synthesis_ms": 1500}
                }

                config = FireRAGConfig(mode="synthesis")
                result = await firerag_client.call_tool("firerag", {
                    "query": "How to learn Python programming?",
                    "config": config.model_dump()
                })

                assert result.content[0].type == "text"
                response_data = result.content[0].text
                assert "To learn Python programming" in response_data
                assert "docs.python.org" in response_data

    async def test_firerag_hybrid_mode_success(self, firerag_client, mock_vector_search_response):
        """Test successful vector search in hybrid mode."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            with patch("firecrawl_mcp.tools.firerag._perform_llm_synthesis") as mock_synthesis:
                mock_synthesis.return_value = {
                    "answer": "Based on the search results, Python is a powerful and easy-to-learn programming language...",
                    "model": "gpt-3.5-turbo",
                    "tokens": 50,
                    "timing": {"synthesis_ms": 1200}
                }

                config = FireRAGConfig(mode="hybrid")
                result = await firerag_client.call_tool("firerag", {
                    "query": "What is Python?",
                    "config": config.model_dump()
                })

                assert result.content[0].type == "text"
                response_data = result.content[0].text
                assert "vector_results" in response_data
                assert "synthesis" in response_data

    async def test_firerag_with_filters(self, firerag_client, mock_vector_search_response):
        """Test FireRAG with comprehensive filtering."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            result = await firerag_client.call_tool("firerag", {
                "query": "Python documentation",
                "domain": "docs.python.org",
                "repository": "python-docs",
                "content_type": "tutorial",
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "threshold": 0.8,
                "limit": 5,
                "config": {"mode": "raw"}
            })

            assert result.content[0].type == "text"

            # Verify filters were applied in the vector search request
            call_args = mock_client.vector_search.call_args[0][0]
            assert call_args.filters is not None
            assert call_args.filters.domain == "docs.python.org"
            assert call_args.filters.repository == "python-docs"
            assert call_args.filters.content_type == "tutorial"
            assert call_args.threshold == 0.8
            assert call_args.limit == 5

    async def test_firerag_with_repository_filters(self, firerag_client, mock_vector_search_response):
        """Test FireRAG with repository-specific filters."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            result = await firerag_client.call_tool("firerag", {
                "query": "CPython implementation",
                "repository_org": "python",
                "repository_full_name": "python/cpython",
                "config": {"mode": "raw"}
            })

            assert result.content[0].type == "text"

            call_args = mock_client.vector_search.call_args[0][0]
            assert call_args.filters.repository_org == "python"
            assert call_args.filters.repository_full_name == "python/cpython"

    async def test_firerag_pagination(self, firerag_client, mock_vector_search_response):
        """Test FireRAG with pagination parameters."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            result = await firerag_client.call_tool("firerag", {
                "query": "Python examples",
                "limit": 20,
                "offset": 10,
                "config": {"mode": "raw"}
            })

            assert result.content[0].type == "text"

            call_args = mock_client.vector_search.call_args[0][0]
            assert call_args.limit == 20
            assert call_args.offset == 10

    async def test_firerag_include_content_false(self, firerag_client, mock_vector_search_response):
        """Test FireRAG with content inclusion disabled."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = mock_vector_search_response
            mock_get_client.return_value = mock_client

            result = await firerag_client.call_tool("firerag", {
                "query": "Python info",
                "include_content": False,
                "config": {"mode": "raw"}
            })

            assert result.content[0].type == "text"

            call_args = mock_client.vector_search.call_args[0][0]
            assert call_args.include_content is False


class TestFireRAGValidation(TestFireRAGTools):
    """Test FireRAG parameter validation."""

    async def test_firerag_empty_query_error(self, firerag_client):
        """Test FireRAG with empty query."""
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {"query": ""})

        assert "validation" in str(exc_info.value).lower()

    async def test_firerag_query_too_long_error(self, firerag_client):
        """Test FireRAG with query too long."""
        long_query = "x" * 1001
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {"query": long_query})

        assert "validation" in str(exc_info.value).lower()

    async def test_firerag_invalid_limit_range(self, firerag_client):
        """Test FireRAG with invalid limit values."""
        # Test limit too low
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "limit": 0
            })
        assert "validation" in str(exc_info.value).lower()

        # Test limit too high
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "limit": 101
            })
        assert "validation" in str(exc_info.value).lower()

    async def test_firerag_invalid_offset(self, firerag_client):
        """Test FireRAG with invalid offset value."""
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "offset": -1
            })
        assert "validation" in str(exc_info.value).lower()

    async def test_firerag_invalid_threshold_range(self, firerag_client):
        """Test FireRAG with invalid threshold values."""
        # Test threshold too low
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "threshold": -0.1
            })
        assert "validation" in str(exc_info.value).lower()

        # Test threshold too high
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "threshold": 1.1
            })
        assert "validation" in str(exc_info.value).lower()

    async def test_firerag_invalid_content_type(self, firerag_client):
        """Test FireRAG with invalid content type."""
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "content_type": "invalid_type"
            })
        assert "validation" in str(exc_info.value).lower()

    async def test_firerag_invalid_config_values(self, firerag_client):
        """Test FireRAG with invalid configuration values."""
        # Invalid mode
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "config": {"mode": "invalid_mode"}
            })
        assert "validation" in str(exc_info.value).lower()

        # Invalid temperature
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "config": {"temperature": 3.0}
            })
        assert "validation" in str(exc_info.value).lower()

        # Invalid max_tokens
        with pytest.raises(Exception) as exc_info:
            await firerag_client.call_tool("firerag", {
                "query": "test",
                "config": {"max_tokens": 10}
            })
        assert "validation" in str(exc_info.value).lower()


class TestFireRAGErrorHandling(TestFireRAGTools):
    """Test error handling for FireRAG tools."""

    async def test_firerag_no_results_error(self, firerag_client):
        """Test handling when vector search returns no results."""
        empty_response = VectorSearchResponse(
            success=True,
            data=VectorSearchData(
                results=[],
                total_results=0,
                timing=VectorSearchTiming(
                    query_embedding_ms=50,
                    vector_search_ms=120,
                    total_ms=170
                )
            )
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = empty_response
            mock_get_client.return_value = mock_client

            result = await firerag_client.call_tool("firerag", {
                "query": "nonexistent topic",
                "config": {"mode": "raw"}
            })

            assert result.content[0].type == "text"
            response_data = result.content[0].text
            assert "0" in response_data  # Should report 0 results

    async def test_firerag_search_failure_error(self, firerag_client):
        """Test handling of vector search failures."""
        failed_response = VectorSearchResponse(
            success=False,
            data=None
        )

        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = failed_response
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await firerag_client.call_tool("firerag", {
                    "query": "test query"
                })

            assert "Vector search returned no results or failed" in str(exc_info.value)

    async def test_firerag_unauthorized_error(self, firerag_client):
        """Test handling of unauthorized errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.side_effect = UnauthorizedError("Invalid API key")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await firerag_client.call_tool("firerag", {
                    "query": "test query"
                })

            assert "Invalid API key" in str(exc_info.value)

    async def test_firerag_rate_limit_error(self, firerag_client):
        """Test handling of rate limit errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.side_effect = RateLimitError("Rate limit exceeded")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await firerag_client.call_tool("firerag", {
                    "query": "test query"
                })

            assert "Rate limit exceeded" in str(exc_info.value)

    async def test_firerag_generic_error(self, firerag_client):
        """Test handling of generic errors."""
        with patch("firecrawl_mcp.core.client.get_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.side_effect = Exception("Network error")
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await firerag_client.call_tool("firerag", {
                    "query": "test query"
                })

            assert "FireRAG search failed" in str(exc_info.value)


class TestFireRAGLLMSynthesis(TestFireRAGTools):
    """Test LLM synthesis functionality."""

    @pytest.mark.asyncio
    async def test_llm_synthesis_fallback_summary(self, mock_vector_search_results):
        """Test LLM synthesis fallback to summary when no LLM is available."""
        from fastmcp import Context

        # Create a mock context
        mock_ctx = Mock(spec=Context)
        mock_ctx.warning = AsyncMock()

        config = FireRAGConfig(mode="synthesis")

        result = await _perform_llm_synthesis(
            mock_ctx, "What is Python?", mock_vector_search_results, config
        )

        assert result["answer"] is not None
        assert "Python Tutorial" in result["answer"]
        assert result["model"] == "summary_fallback"
        assert result["tokens"] > 0

    @pytest.mark.asyncio
    async def test_llm_synthesis_with_mcp_client(self, mock_vector_search_results):
        """Test LLM synthesis using MCP client sampling."""
        from fastmcp import Context

        # Create a mock context with sampling capability
        mock_ctx = Mock(spec=Context)
        mock_ctx.warning = AsyncMock()

        # Mock successful sampling
        mock_sample_result = Mock()
        mock_sample_result.text = "Python is a high-level programming language known for its simplicity and readability. It's widely used for web development, data science, and automation."
        mock_ctx.sample = AsyncMock(return_value=mock_sample_result)

        config = FireRAGConfig(mode="synthesis")

        result = await _perform_llm_synthesis(
            mock_ctx, "What is Python?", mock_vector_search_results, config
        )

        assert result["answer"] == mock_sample_result.text
        assert result["model"] == "mcp_client_llm"
        assert result["tokens"] > 0

    @pytest.mark.asyncio
    async def test_llm_synthesis_context_building(self, mock_vector_search_results):
        """Test that LLM synthesis properly builds context from search results."""
        from fastmcp import Context

        mock_ctx = Mock(spec=Context)
        mock_ctx.warning = AsyncMock()

        config = FireRAGConfig(mode="synthesis")

        # This will fall back to summary mode, but we can verify context building
        result = await _perform_llm_synthesis(
            mock_ctx, "What is Python?", mock_vector_search_results, config
        )

        # The summary should contain information from the search results
        assert "Python Tutorial" in result["answer"]
        assert "CPython README" in result["answer"]
        assert "docs.python.org" in result["answer"]

    def test_default_system_prompt(self):
        """Test the default system prompt generation."""
        prompt = _get_default_system_prompt()

        assert "helpful AI assistant" in prompt
        assert "vector search results" in prompt
        assert "context" in prompt
        assert "sources" in prompt


class TestFireRAGToolRegistration(TestFireRAGTools):
    """Test FireRAG tool registration and schema validation."""

    async def test_firerag_tool_registered(self, firerag_client):
        """Test that firerag tool is properly registered."""
        tools = await firerag_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "firerag" in tool_names

    async def test_firerag_tool_schema_valid(self, firerag_client):
        """Test that firerag tool has proper schema."""
        tools = await firerag_client.list_tools()
        tool_dict = {tool.name: tool for tool in tools}

        firerag_tool = tool_dict["firerag"]
        assert firerag_tool.description is not None
        assert firerag_tool.inputSchema is not None

        # Check required parameters
        properties = firerag_tool.inputSchema["properties"]
        assert "query" in properties

        # Check query constraints
        query_prop = properties["query"]
        assert "minLength" in query_prop
        assert "maxLength" in query_prop

    def test_register_firerag_tools_returns_tool_names(self):
        """Test that register_firerag_tools returns the correct tool names."""
        server = FastMCP("TestServer")
        tool_names = register_firerag_tools(server)

        assert tool_names == ["firerag"]


class TestFireRAGConfigModel(TestFireRAGTools):
    """Test FireRAG configuration model."""

    def test_firerag_config_defaults(self):
        """Test FireRAG configuration defaults."""
        config = FireRAGConfig()

        assert config.mode == "synthesis"
        assert config.llm_provider is None
        assert config.model is None
        assert config.temperature == 0.1
        assert config.max_tokens == 1000
        assert config.system_prompt is None

    def test_firerag_config_validation(self):
        """Test FireRAG configuration validation."""
        # Valid configuration
        config = FireRAGConfig(
            mode="hybrid",
            llm_provider="openai",
            model="gpt-4",
            temperature=0.5,
            max_tokens=2000
        )
        assert config.mode == "hybrid"
        assert config.llm_provider == "openai"
        assert config.model == "gpt-4"

        # Invalid mode should raise validation error
        with pytest.raises(Exception):
            FireRAGConfig(mode="invalid_mode")

        # Invalid temperature should raise validation error
        with pytest.raises(Exception):
            FireRAGConfig(temperature=3.0)

        # Invalid max_tokens should raise validation error
        with pytest.raises(Exception):
            FireRAGConfig(max_tokens=10)


@pytest.mark.integration
class TestFireRAGIntegrationTests(TestFireRAGTools):
    """Integration tests requiring real API access."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_firerag_raw_mode(self, firerag_client):
        """Test real FireRAG search in raw mode."""
        result = await firerag_client.call_tool("firerag", {
            "query": "Python programming tutorial",
            "limit": 3,
            "config": {"mode": "raw"}
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain vector search results
        assert "similarity" in response_data or "results" in response_data

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    async def test_real_firerag_with_filters(self, firerag_client):
        """Test real FireRAG search with domain filtering."""
        result = await firerag_client.call_tool("firerag", {
            "query": "Python documentation",
            "domain": "docs.python.org",
            "limit": 2,
            "config": {"mode": "raw"}
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain filtered results
        assert "docs.python.org" in response_data or "results" in response_data

    @pytest.mark.skipif(
        not os.getenv("FIRECRAWL_API_KEY") or not os.getenv("OPENAI_API_KEY"),
        reason="FIRECRAWL_API_KEY and OPENAI_API_KEY not available"
    )
    async def test_real_firerag_synthesis_mode(self, firerag_client):
        """Test real FireRAG search with LLM synthesis."""
        result = await firerag_client.call_tool("firerag", {
            "query": "How to install Python packages?",
            "limit": 3,
            "config": {
                "mode": "synthesis",
                "llm_provider": "openai",
                "model": "gpt-3.5-turbo",
                "max_tokens": 300
            }
        })

        assert result.content[0].type == "text"
        response_data = result.content[0].text

        # Should contain synthesized answer
        assert "install" in response_data.lower() or "package" in response_data.lower()
