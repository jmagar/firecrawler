"""
Tests for the firerag vector search tool.

This suite focuses on raw vector retrieval behaviour without LLM synthesis.
"""

import json
from unittest.mock import Mock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import (
    VectorSearchData,
    VectorSearchResult,
    VectorSearchTiming,
)
from firecrawl.v2.utils.error_handler import FirecrawlError

from firecrawl_mcp.tools.firerag import register_firerag_tools


@pytest.fixture
def firerag_server(test_env):
    """Create FastMCP server with firerag tools registered."""
    server = FastMCP("TestFireRAGServer")
    register_firerag_tools(server)
    return server


@pytest.fixture
async def firerag_client(firerag_server):
    """Create MCP client for firerag tools."""
    async with Client(firerag_server) as client:
        yield client


@pytest.fixture
def vector_search_result():
    """Provide a single vector search result."""
    return [
        VectorSearchResult(
            id="doc-1",
            url="https://docs.example.com/page",
            title="Example Page",
            content="Example content about @ mentions.",
            similarity=0.68,
            metadata={
                "sourceURL": "https://docs.example.com/page",
                "domain": "docs.example.com",
                "contentType": "documentation",
            },
        )
    ]


@pytest.fixture
def vector_search_data(vector_search_result):
    """Build vector search data for successful responses."""
    return VectorSearchData(
        results=vector_search_result,
        query="test query",
        total_results=len(vector_search_result),
        limit=5,
        offset=0,
        threshold=0.6,
        timing=VectorSearchTiming(query_embedding_ms=50, vector_search_ms=120, total_ms=170),
    )


class TestFireRAGRawBehaviour:
    """Validate raw vector search behaviour."""

    async def test_firerag_returns_serialized_results(
        self,
        firerag_client,
        vector_search_data,
    ):
        with patch("firecrawl_mcp.tools.firerag.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = vector_search_data
            mock_get_client.return_value = mock_client

            result = await firerag_client.call_tool("firerag", {"query": "test query"})

            assert result.content[0].type == "text"
            payload = json.loads(result.content[0].text)
            assert payload["result_count"] == 1
            assert payload["results"][0]["id"] == "doc-1"
            assert payload["filters_applied"] == {}

    async def test_firerag_forwards_filters(
        self,
        firerag_client,
        vector_search_data,
    ):
        with patch("firecrawl_mcp.tools.firerag.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = vector_search_data
            mock_get_client.return_value = mock_client

            await firerag_client.call_tool(
                "firerag",
                {
                    "query": "docs",
                    "domain": "docs.example.com",
                    "repository": "docs",
                    "repository_org": "example",
                    "content_type": "tutorial",
                },
            )

            kwargs = mock_client.vector_search.call_args.kwargs
            assert kwargs["filters"]["domain"] == "docs.example.com"
            assert kwargs["filters"]["repository"] == "docs"
            assert kwargs["filters"]["repository_org"] == "example"
            assert kwargs["filters"]["content_type"] == "tutorial"

    async def test_firerag_threshold_optional(
        self,
        firerag_client,
        vector_search_data,
    ):
        with patch("firecrawl_mcp.tools.firerag.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.return_value = vector_search_data
            mock_get_client.return_value = mock_client

            await firerag_client.call_tool("firerag", {"query": "docs"})
            kwargs = mock_client.vector_search.call_args.kwargs
            assert "threshold" not in kwargs

    async def test_firerag_auto_paginate_uses_helper(
        self,
        firerag_client,
        vector_search_result,
    ):
        with (
            patch("firecrawl_mcp.tools.firerag.get_firecrawl_client") as mock_get_client,
            patch("firecrawl_mcp.tools.firerag.paginate_vector_search") as mock_paginate,
        ):
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            mock_paginate.return_value = (
                vector_search_result,
                {"pages_fetched": 1, "total_results": 1, "stopped_reason": "end_of_results"},
            )

            result = await firerag_client.call_tool(
                "firerag",
                {"query": "docs", "auto_paginate": True},
            )

            mock_paginate.assert_called_once()
            payload = json.loads(result.content[0].text)
            assert payload["result_count"] == 1
            assert payload["pagination_metadata"]["pages_fetched"] == 1

    async def test_firerag_propagates_api_errors(
        self,
        firerag_client,
    ):
        with patch("firecrawl_mcp.tools.firerag.get_firecrawl_client") as mock_get_client:
            mock_client = Mock()
            mock_client.vector_search.side_effect = FirecrawlError("bad request")
            mock_get_client.return_value = mock_client

            with pytest.raises(ToolError):
                await firerag_client.call_tool("firerag", {"query": "docs"})
