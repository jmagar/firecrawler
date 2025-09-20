"""
Vector search tool for the Firecrawl MCP server.

This module implements the firerag tool for vector database Q&A that returns raw
semantic search results without any LLM synthesis layers. The tool provides
comprehensive filtering, response size management, and pagination following
FastMCP patterns.
"""

import copy
import json
import logging
import os
import re
from typing import Annotated, Any, Literal

import asyncpg  # type: ignore[import-untyped]
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import (
    VectorSearchData,
    VectorSearchFilters,
    VectorSearchRequest,
    VectorSearchResult,
    VectorSearchTiming,
)
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)


async def get_document_by_id(document_id: str) -> dict[str, Any] | None:
    """
    Retrieve document from vector database by ID.

    Args:
        document_id: The document ID (job_id in database)

    Returns:
        Document data if found, None if not found

    Raises:
        ToolError: If database connection fails or configuration is missing
    """
    connection_string = os.getenv("FIRECRAWLER_NUQ_DATABASE_URL")
    if not connection_string:
        raise ToolError("Vector database not configured (FIRECRAWLER_NUQ_DATABASE_URL missing)")

    try:
        conn = await asyncpg.connect(connection_string)
        try:
            row = await conn.fetchrow(
                "SELECT job_id, metadata, content, created_at FROM nuq.document_vectors WHERE job_id = $1",
                document_id
            )
            return dict(row) if row else None
        finally:
            await conn.close()
    except Exception as e:
        raise ToolError(f"Database connection error: {e!s}") from e


def estimate_response_tokens(data: Any) -> int:
    """
    Estimate tokens using 3-chars-per-token approximation.

    This provides a conservative estimate for MCP token limit checking.

    Args:
        data: Any object to estimate tokens for

    Returns:
        Estimated token count
    """
    try:
        # Convert data to JSON string for consistent estimation
        if hasattr(data, 'model_dump'):
            # Pydantic model
            text = json.dumps(data.model_dump(), ensure_ascii=False)
        elif hasattr(data, '__dict__'):
            # Regular object
            text = json.dumps(data.__dict__, default=str, ensure_ascii=False)
        else:
            # Fallback to string representation
            text = json.dumps(data, default=str, ensure_ascii=False)

        # Conservative estimate: 3 characters per token
        return len(text) // 3
    except Exception:
        # Fallback for non-serializable objects
        return len(str(data)) // 3


def optimize_response_size(
    vector_data: Any,
    target_tokens: int,
    current_estimate: int,
    _limit: int  # Unused parameter, keeping for API compatibility
) -> tuple[Any, dict[str, Any]]:
    """
    Progressive optimization levels to reduce response size.

    Args:
        vector_data: Vector search data to optimize
        target_tokens: Target token count
        current_estimate: Current estimated token count
        synthesis_mode: Current synthesis mode
        limit: Current result limit

    Returns:
        Tuple of (optimized_data, optimization_metadata)
    """
    optimization_metadata: dict[str, Any] = {
        "original_estimate": current_estimate,
        "target_tokens": target_tokens,
        "optimization_level": 0,
        "actions_taken": []
    }

    if current_estimate <= target_tokens:
        return vector_data, optimization_metadata

    # Make a copy to avoid modifying original data
    if hasattr(vector_data, 'model_copy'):
        optimized_data = vector_data.model_copy(deep=True)
    else:
        # Fallback for non-Pydantic objects
        optimized_data = copy.deepcopy(vector_data)

    # Level 1: Reduce content truncation to 250 chars
    if hasattr(optimized_data, 'results') and optimized_data.results:
        for result in optimized_data.results:
            if hasattr(result, 'content') and result.content and len(result.content) > 250:
                result.content = result.content[:250] + "..."

        new_estimate = estimate_response_tokens(optimized_data)
        if new_estimate <= target_tokens:
            optimization_metadata["optimization_level"] = 1
            optimization_metadata["actions_taken"].append("truncated_content_250")
            optimization_metadata["final_estimate"] = new_estimate
            return optimized_data, optimization_metadata

    # Level 2: Limit results to min(limit, 5)
    if hasattr(optimized_data, 'results') and optimized_data.results and len(optimized_data.results) > 5:
        optimized_data.results = optimized_data.results[:5]

        new_estimate = estimate_response_tokens(optimized_data)
        if new_estimate <= target_tokens:
            optimization_metadata["optimization_level"] = 2
            if "truncated_content_250" not in optimization_metadata["actions_taken"]:
                optimization_metadata["actions_taken"].append("truncated_content_250")
            optimization_metadata["actions_taken"].append("limited_to_5_results")
            optimization_metadata["final_estimate"] = new_estimate
            return optimized_data, optimization_metadata

    # Level 3: Return titles, similarity, URLs only
    if hasattr(optimized_data, 'results') and optimized_data.results:
        for result in optimized_data.results:
            # Keep only essential fields
            if hasattr(result, 'content'):
                result.content = None
            # Keep title, similarity, url, and minimal metadata
            if hasattr(result, 'metadata') and result.metadata:
                # Keep only sourceURL from metadata
                source_url = result.metadata.get("sourceURL")
                result.metadata = {"sourceURL": source_url} if source_url else {}

        new_estimate = estimate_response_tokens(optimized_data)
        optimization_metadata["optimization_level"] = 3
        if "truncated_content_250" not in optimization_metadata["actions_taken"]:
            optimization_metadata["actions_taken"].append("truncated_content_250")
        if "limited_to_5_results" not in optimization_metadata["actions_taken"]:
            optimization_metadata["actions_taken"].append("limited_to_5_results")
        optimization_metadata["actions_taken"].append("minimal_fields_only")
        optimization_metadata["final_estimate"] = new_estimate
        return optimized_data, optimization_metadata

    # If we get here, return what we have
    optimization_metadata["final_estimate"] = estimate_response_tokens(optimized_data)
    return optimized_data, optimization_metadata


def _prepare_vector_search_payload(search_params: dict[str, Any]) -> dict[str, Any]:
    """Convert internal search parameters to the v2 API payload format."""
    payload: dict[str, Any] = {
        "query": search_params["query"],
    }

    optional_params = {
        "limit": search_params.get("limit"),
        "offset": search_params.get("offset"),
        "threshold": search_params.get("threshold"),
        "includeContent": search_params.get("include_content"),
    }

    payload.update({k: v for k, v in optional_params.items() if v is not None})

    filters = search_params.get("filters")
    if filters:
        api_filters: dict[str, Any] = {}
        for key, value in filters.items():
            if value is None:
                continue
            if key == "repository_org":
                api_filters["repositoryOrg"] = value
            elif key == "repository_full_name":
                api_filters["repositoryFullName"] = value
            elif key == "content_type":
                api_filters["contentType"] = value
            elif key == "date_range":
                api_filters["dateRange"] = value
            else:
                api_filters[key] = value
        if api_filters:
            payload["filters"] = api_filters

    return payload


def _convert_response_to_vector_data(
    response_data: dict[str, Any],
    search_params: dict[str, Any]
) -> VectorSearchData:
    """Convert raw API response data to VectorSearchData model."""
    timing_payload = response_data.get("timing") or {}
    timing = VectorSearchTiming(
        query_embedding_ms=int(timing_payload.get("queryEmbeddingMs") or timing_payload.get("query_embedding_ms") or 0),
        vector_search_ms=int(timing_payload.get("vectorSearchMs") or timing_payload.get("vector_search_ms") or 0),
        total_ms=int(timing_payload.get("totalMs") or timing_payload.get("total_ms") or 0),
    )

    results_payload = response_data.get("results") or []
    results: list[VectorSearchResult] = []
    for result in results_payload:
        if isinstance(result, VectorSearchResult):
            results.append(result)
            continue
        result_dict = dict(result)
        result_dict.setdefault("metadata", {})
        results.append(VectorSearchResult(**result_dict))

    limit_value = response_data.get("limit")
    if limit_value is None:
        limit_value = search_params.get("limit")
    if limit_value is None:
        limit_value = 10

    offset_value = response_data.get("offset")
    if offset_value is None:
        offset_value = search_params.get("offset") or 0

    threshold_value = response_data.get("threshold")
    if threshold_value is None:
        threshold_value = search_params.get("threshold")
    if threshold_value is None:
        threshold_value = 0.0

    return VectorSearchData(
        results=results,
        query=response_data.get("query") or search_params["query"],
        total_results=response_data.get("totalResults", len(results)),
        limit=limit_value,
        offset=offset_value,
        threshold=threshold_value,
        threshold_history=response_data.get("thresholdHistory"),
        timing=timing,
    )


def _fallback_vector_search(client: Any, search_params: dict[str, Any]) -> VectorSearchData:
    """Retry vector search with the updated v2 payload when legacy clients fail."""
    http_client = getattr(client, "http_client", None)
    if http_client is None:
        raise FirecrawlError(
            "Firecrawl client does not expose http_client; cannot retry vector search with updated payload"
        )

    payload = _prepare_vector_search_payload(search_params)
    response = http_client.post("/v2/vector-search", payload)

    try:
        response.raise_for_status()
    except Exception as http_error:  # pragma: no cover - requests raises specific exceptions
        raise FirecrawlError(f"Vector search retry failed: {http_error}") from http_error

    try:
        json_body = response.json()
    except ValueError as json_error:
        raise FirecrawlError("Vector search retry returned invalid JSON") from json_error
    if not json_body.get("success"):
        error_message = json_body.get("message") or "Vector search retry failed"
        raise FirecrawlError(error_message)

    data = json_body.get("data") or {}
    return _convert_response_to_vector_data(data, search_params)


async def _call_vector_search(
    client: Any,
    search_params: dict[str, Any],
    ctx: Context
) -> VectorSearchData:
    """Invoke vector search, retrying with v2 payload when legacy schemas fail."""
    try:
        return client.vector_search(**search_params)
    except FirecrawlError as error:
        error_text = str(error)
        if "minSimilarityThreshold" not in error_text:
            raise

        await ctx.info(
            "Firecrawl client rejected 'minSimilarityThreshold'; retrying with updated 'threshold' schema"
        )

        return _fallback_vector_search(client, search_params)

async def paginate_vector_search(
    client: Any,
    search_request: dict[str, Any],
    pagination_config: dict[str, Any],
    ctx: Context
) -> tuple[list[Any], dict[str, Any]]:
    """
    Make multiple vector_search calls with increasing offsets.

    Args:
        client: Firecrawl client
        search_request: Base search request parameters
        pagination_config: Pagination configuration
        ctx: FastMCP context for logging

    Returns:
        Tuple of (aggregated_results, pagination_metadata)
    """
    all_results: list[Any] = []
    pagination_metadata: dict[str, Any] = {
        "pages_fetched": 0,
        "total_results": 0,
        "stopped_reason": None
    }

    max_pages = pagination_config.get("max_pages", 10)
    max_results = pagination_config.get("max_results")
    base_limit = search_request.get("limit", 10)
    current_offset = search_request.get("offset", 0)

    page = 0
    while page < max_pages:
        try:
            # Update offset for current page
            current_request = search_request.copy()
            current_request["offset"] = current_offset + (page * base_limit)

            await ctx.info(f"Fetching page {page + 1} with offset {current_request['offset']}")

            # Perform vector search for this page
            page_data = await _call_vector_search(client, current_request, ctx)

            if not page_data or not hasattr(page_data, 'results') or not page_data.results:
                pagination_metadata["stopped_reason"] = "no_more_results"
                break

            # Add results to aggregated list
            all_results.extend(page_data.results)
            pagination_metadata["pages_fetched"] = page + 1
            pagination_metadata["total_results"] = len(all_results)

            # Check if we've hit max_results limit
            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                pagination_metadata["total_results"] = len(all_results)
                pagination_metadata["stopped_reason"] = "max_results_reached"
                break

            # If this page returned fewer results than limit, we've reached the end
            if len(page_data.results) < base_limit:
                pagination_metadata["stopped_reason"] = "end_of_results"
                break

            page += 1

        except Exception as e:
            await ctx.error(f"Error fetching page {page + 1}: {e}")
            pagination_metadata["stopped_reason"] = f"error_on_page_{page + 1}"
            break

    if pagination_metadata["stopped_reason"] is None:
        pagination_metadata["stopped_reason"] = "max_pages_reached"

    return all_results, pagination_metadata


def _serialize_vector_data(
    vector_data: Any,
    query: str,
    limit: int | None,
    offset: int | None
) -> dict[str, Any]:
    """Convert vector search data to plain Python structures."""
    try:
        data: dict[str, Any]
        if hasattr(vector_data, 'model_dump'):
            data = vector_data.model_dump()
        else:
            results = getattr(vector_data, 'results', [])
            serialized_results = [
                r.model_dump() if hasattr(r, 'model_dump') else r
                for r in results
            ]

            total_results = getattr(vector_data, 'total_results', None)
            if total_results is None:
                total_results = getattr(vector_data, 'total', len(serialized_results))

            data = {
                "results": serialized_results,
                "total_results": total_results,
                "query": getattr(vector_data, 'query', query),
                "limit": getattr(vector_data, 'limit', limit),
                "offset": getattr(vector_data, 'offset', offset),
                "threshold": getattr(vector_data, 'threshold', None),
            }

            if hasattr(vector_data, 'timing'):
                data["timing"] = vector_data.timing

            if hasattr(vector_data, 'pagination'):
                data["pagination"] = vector_data.pagination

        threshold_history = getattr(vector_data, 'threshold_history', None)
        if threshold_history:
            data["thresholdHistory"] = list(threshold_history)

        # Ensure results are JSON-serializable
        if 'results' in data:
            data['results'] = [
                r.model_dump() if hasattr(r, 'model_dump') else r
                for r in data['results']
            ]

        return data
    except Exception:
        # Fallback best-effort serialization
        return {
            "query": query,
            "limit": limit,
            "offset": offset,
            "results": [],
            "total_results": 0,
        }


def register_firerag_tools(mcp: FastMCP) -> None:
    """Register the firerag tool with the FastMCP server."""

    @mcp.tool(
        name="firerag",
        description="Perform semantic vector search over your Firecrawl vector database and return high-similarity document chunks with optional filters and pagination.",
        annotations={
            "title": "Vector Search",
            "readOnlyHint": True,       # Only searches stored data
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True
        }
    )
    async def firerag(
        ctx: Context,
        query: Annotated[str, Field(
            description="Natural language query for semantic search",
            min_length=1,
            max_length=1000
        )],
        limit: Annotated[int, Field(
            description="Maximum number of vector search results to return",
            ge=1,
            le=100
        )] = 10,
        offset: Annotated[int, Field(
            description="Number of results to skip for pagination",
            ge=0
        )] = 0,
        threshold: Annotated[float | None, Field(
            description="Minimum similarity threshold for results (0.0-1.0)",
            ge=0.0,
            le=1.0
        )] = None,
        include_content: Annotated[bool, Field(
            description="Whether to include full content in results"
        )] = True,
        # Filtering options
        domain: Annotated[str | None, Field(
            description="Filter by specific domain (e.g., 'docs.python.org')"
        )] = None,
        repository: Annotated[str | None, Field(
            description="Filter by repository name (e.g., 'pandas')"
        )] = None,
        repository_org: Annotated[str | None, Field(
            description="Filter by repository organization (e.g., 'microsoft')"
        )] = None,
        repository_full_name: Annotated[str | None, Field(
            description="Filter by full repository name (e.g., 'microsoft/vscode')"
        )] = None,
        content_type: Annotated[Literal["readme", "api-docs", "tutorial", "configuration", "code", "other"] | None, Field(
            description="Filter by content type"
        )] = None,
        date_from: Annotated[str | None, Field(
            description="Filter results from this date (ISO format: YYYY-MM-DD)"
        )] = None,
        date_to: Annotated[str | None, Field(
            description="Filter results until this date (ISO format: YYYY-MM-DD)"
        )] = None,
        # Response size management
        max_response_tokens: Annotated[int, Field(
            description="Maximum response tokens to stay under MCP 25k limit",
            ge=1000,
            le=24000
        )] = 20000,
        auto_optimize: Annotated[bool, Field(
            description="Automatically optimize large responses"
        )] = True,
        # Advanced pagination
        auto_paginate: Annotated[bool, Field(
            description="Fetch multiple pages automatically"
        )] = False,
        max_pages: Annotated[int | None, Field(
            description="Limit pagination API calls",
            ge=1,
            le=20
        )] = None,
        max_results: Annotated[int | None, Field(
            description="Stop when enough results collected",
            ge=1,
            le=1000
        )] = None
    ) -> dict[str, Any]:
        """
        Perform semantic vector search against stored Firecrawl embeddings.

        This tool searches the vector database using natural language queries,
        applies comprehensive filtering, and returns the matching chunks along
        with metadata. Optional pagination and response-size optimization help
        keep responses within MCP transport limits.

        Args:
            ctx: FastMCP context for logging and progress reporting
            query: Natural language search query
            limit: Maximum number of results to return
            offset: Number of results to skip (pagination)
            threshold: Minimum similarity score (0.0-1.0). Defaults to the server configuration
            include_content: Whether to include full content
            domain: Filter by domain
            repository: Filter by repository name
            repository_org: Filter by organization
            repository_full_name: Filter by full repo name
            content_type: Filter by content type
            date_from: Start date filter (ISO format)
            date_to: End date filter (ISO format)
            max_response_tokens: Maximum response tokens to stay under MCP limit
            auto_optimize: Automatically optimize large responses
            auto_paginate: Fetch multiple pages automatically
            max_pages: Limit pagination API calls
            max_results: Stop when enough results collected

        Returns:
            Dictionary payload containing vector search data and applied filters

        Raises:
            ToolError: If vector search fails
        """
        try:
            await ctx.info(f"Starting FireRAG vector search for query: '{query}'")

            # Build filters
            filters = None
            filter_params: dict[str, Any] = {}

            if any([domain, repository, repository_org, repository_full_name, content_type, date_from, date_to]):
                filter_dict: dict[str, Any] = {}

                if domain:
                    filter_dict["domain"] = domain
                    filter_params["domain"] = domain

                if repository:
                    filter_dict["repository"] = repository
                    filter_params["repository"] = repository

                if repository_org:
                    filter_dict["repository_org"] = repository_org
                    filter_params["repository_org"] = repository_org

                if repository_full_name:
                    filter_dict["repository_full_name"] = repository_full_name
                    filter_params["repository_full_name"] = repository_full_name

                if content_type:
                    filter_dict["content_type"] = content_type
                    filter_params["content_type"] = content_type

                if date_from or date_to:
                    date_range: dict[str, str] = {}
                    if date_from:
                        date_range["from"] = date_from
                        filter_params["date_from"] = date_from
                    if date_to:
                        date_range["to"] = date_to
                        filter_params["date_to"] = date_to
                    filter_dict["date_range"] = date_range

                filters = VectorSearchFilters(**filter_dict)

            # Create vector search request
            search_request = VectorSearchRequest(
                query=query,
                limit=limit,
                offset=offset,
                threshold=threshold,
                include_content=include_content,
                filters=filters
            )

            client = get_firecrawl_client()

            await ctx.info("Performing vector similarity search...")

            # Prepare search parameters for potential pagination
            search_params: dict[str, Any] = {
                "query": search_request.query,
                "limit": search_request.limit,
                "offset": search_request.offset,
                "include_content": search_request.include_content
            }
            if search_request.threshold is not None:
                search_params["threshold"] = search_request.threshold

            # Add filters if present
            if search_request.filters:
                search_params["filters"] = search_request.filters.model_dump(exclude_none=True)

            try:
                if auto_paginate:
                    await ctx.info("Auto-pagination enabled, fetching multiple pages...")
                    pagination_config = {
                        "max_pages": max_pages or 10,
                        "max_results": max_results
                    }

                    all_results, pagination_metadata = await paginate_vector_search(
                        client, search_params, pagination_config, ctx
                    )

                    vector_data = type('VectorSearchData', (), {
                        'results': all_results,
                        'total': len(all_results),
                        'query': search_request.query,
                        'limit': search_request.limit,
                        'offset': search_request.offset,
                        'threshold': search_params.get("threshold"),
                        'pagination': pagination_metadata
                    })()

                    await ctx.info(
                        f"Pagination complete: {pagination_metadata['pages_fetched']} pages, {len(all_results)} total results"
                    )
                else:
                    vector_data = await _call_vector_search(client, search_params, ctx)

            except FirecrawlError as e:
                await ctx.error(f"Vector search failed: {e}")
                raise handle_firecrawl_error(e, "vector search") from e

            if not vector_data or not hasattr(vector_data, 'results'):
                raise ToolError("Vector search returned no results or failed")

            applied_threshold = getattr(vector_data, 'threshold', search_request.threshold)
            await ctx.info(
                f"Vector search completed: {len(vector_data.results)} results (effective threshold: {applied_threshold})"
            )

            optimization_metadata = None

            if auto_optimize:
                estimated_tokens = estimate_response_tokens(vector_data)
                await ctx.info(
                    f"Estimated response tokens: {estimated_tokens} (limit: {max_response_tokens})"
                )

                if estimated_tokens > max_response_tokens:
                    await ctx.info("Response too large, applying optimizations...")

                    optimized_data, optimization_metadata = optimize_response_size(
                        vector_data,
                        max_response_tokens,
                        estimated_tokens,
                        limit or 10
                    )

                    vector_data = optimized_data
                    await ctx.info(
                        "Optimization complete: "
                        f"level {optimization_metadata['optimization_level']}"
                        f", actions {optimization_metadata['actions_taken']}"
                    )

            response_payload = _serialize_vector_data(
                vector_data,
                query,
                search_request.limit,
                search_request.offset
            )

            response_payload["result_count"] = len(response_payload.get("results", []))
            response_payload["filters_applied"] = filter_params

            if optimization_metadata:
                response_payload["optimization_metadata"] = optimization_metadata

            if hasattr(vector_data, 'pagination'):
                response_payload["pagination_metadata"] = vector_data.pagination

            await ctx.info("FireRAG search complete")

            return response_payload

        except FirecrawlError as e:
            await ctx.error(f"Firecrawl API error in FireRAG: {e}")
            raise handle_firecrawl_error(e, "FireRAG vector search") from e
        except Exception as e:
            await ctx.error(f"Unexpected error in FireRAG: {e}")
            raise ToolError(f"FireRAG search failed: {e!s}") from e

    @mcp.tool(
        name="retrieve",
        description="Retrieve complete document information by ID from vector search results",
        annotations={
            "title": "Document Retrieval",
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True
        }
    )
    async def retrieve(
        ctx: Context,
        document_id: Annotated[str, Field(
            description="Document ID from firerag search results (36-character UUID format)",
            pattern=r"^[a-f0-9\-]{36}$"
        )]
    ) -> dict[str, Any]:
        """
        Retrieve complete document information by ID from vector database.

        This tool fetches full document details using the document ID returned
        from firerag search results. It provides access to complete content and
        metadata for a specific document.

        Args:
            ctx: FastMCP context for logging and progress reporting
            document_id: 36-character UUID format document identifier

        Returns:
            Dictionary containing complete document information

        Raises:
            ToolError: If document not found, invalid ID format, or database error
        """
        try:
            await ctx.info(f"Retrieving document by ID: {document_id}")

            # Validate UUID format
            if not document_id or not document_id.strip():
                raise ToolError("Document ID cannot be empty")

            if not re.match(r"^[a-f0-9\-]{36}$", document_id):
                raise ToolError("Invalid document ID format. Expected 36-character UUID format")

            # Retrieve document from database
            document_data = await get_document_by_id(document_id)

            if not document_data:
                raise ToolError(f"Document not found with ID: {document_id}")

            await ctx.info("Document retrieved successfully")

            # Parse metadata if it's a JSON string
            metadata = document_data.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            # Construct response matching firerag pattern
            response = {
                "success": True,
                "document": {
                    "id": document_data["job_id"],
                    "url": metadata.get("sourceURL"),
                    "title": metadata.get("title"),
                    "content": document_data.get("content"),
                    "metadata": {
                        "sourceURL": metadata.get("sourceURL"),
                        "scrapedAt": metadata.get("scrapedAt"),
                        "domain": metadata.get("domain"),
                        "repositoryName": metadata.get("repositoryName"),
                        "repositoryOrg": metadata.get("repositoryOrg"),
                        "repositoryFullName": metadata.get("repositoryFullName"),
                        "filePath": metadata.get("filePath"),
                        "branchVersion": metadata.get("branchVersion"),
                        "contentType": metadata.get("contentType"),
                        "wordCount": metadata.get("wordCount"),
                        **{k: v for k, v in metadata.items() if k not in [
                            "sourceURL", "scrapedAt", "domain", "repositoryName",
                            "repositoryOrg", "repositoryFullName", "filePath",
                            "branchVersion", "contentType", "wordCount"
                        ]}
                    },
                    "created_at": (
                        document_data["created_at"].isoformat()
                        if document_data.get("created_at") is not None
                        else None
                    ),
                },
                "message": "Document retrieved successfully"
            }

            await ctx.info(f"Document retrieval complete for ID: {document_id}")
            return response

        except ToolError:
            # Re-raise ToolErrors as-is
            raise
        except Exception as e:
            await ctx.error(f"Unexpected error retrieving document {document_id}: {e}")
            raise ToolError(f"Document retrieval failed: {e!s}") from e


# Export the registration function
__all__ = ["register_firerag_tools"]
