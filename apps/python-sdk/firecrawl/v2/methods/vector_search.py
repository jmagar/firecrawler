"""
Vector search functionality for Firecrawl v2 API.
"""

from typing import Any
from ..types import VectorSearchRequest, VectorSearchData, VectorSearchTiming, VectorSearchResult
from ..utils import HttpClient, handle_response_error

def vector_search(
    client: HttpClient,
    request: VectorSearchRequest
) -> VectorSearchData:
    """
    Perform a vector search.
    
    Args:
        client: HTTP client instance
        request: Vector search request
        
    Returns:
        VectorSearchData with search results
        
    Raises:
        FirecrawlError: If the vector search operation fails
    """
    request_data = _prepare_vector_search_request(request)
    try:
        response = client.post("/v2/vector-search", request_data)
        if response.status_code != 200:
            handle_response_error(response, "vector search")
        response_data = response.json()
        if not response_data.get("success"):
            handle_response_error(response, "vector search")

        data = response_data.get("data", {}) or {}

        # Normalize timing data from camelCase to snake_case
        timing_data = data.get("timing", {})
        normalized_timing = {}
        if "queryEmbeddingMs" in timing_data:
            normalized_timing["query_embedding_ms"] = timing_data["queryEmbeddingMs"]
        if "vectorSearchMs" in timing_data:
            normalized_timing["vector_search_ms"] = timing_data["vectorSearchMs"]
        if "totalMs" in timing_data:
            normalized_timing["total_ms"] = timing_data["totalMs"]

        # Create timing object
        timing = VectorSearchTiming(**normalized_timing)

        # Parse results with list comprehension
        results = [VectorSearchResult(**result_data) for result_data in data.get("results", [])]

        # Create response data
        search_data = VectorSearchData(
            results=results,
            query=data.get("query", ""),
            total_results=data.get("totalResults", 0),
            limit=data.get("limit", 10),
            offset=data.get("offset", 0),
            threshold=data.get("threshold", 0.7),
            timing=timing
        )

        return search_data
    except Exception as err:
        # If the error is an HTTP error from requests, handle it
        if hasattr(err, "response"):
            handle_response_error(getattr(err, "response"), "vector search")
        raise err

def _validate_vector_search_request(request: VectorSearchRequest) -> VectorSearchRequest:
    """
    Validate and normalize vector search request.
    
    Args:
        request: Vector search request to validate
        
    Returns:
        Validated request
        
    Raises:
        ValueError: If request is invalid
    """
    # Validate query
    if not request.query or not request.query.strip():
        raise ValueError("Query cannot be empty")

    if len(request.query) > 1000:
        raise ValueError("Query cannot exceed 1000 characters")

    # Validate limit
    if request.limit is not None:
        if request.limit <= 0:
            raise ValueError("Limit must be positive")
        if request.limit > 100:
            raise ValueError("Limit cannot exceed 100")

    # Validate offset
    if request.offset is not None:
        if request.offset < 0:
            raise ValueError("Offset must be non-negative")

    # Validate threshold
    if request.threshold is not None:
        if request.threshold < 0 or request.threshold > 1:
            raise ValueError("Threshold must be between 0 and 1")
    return request

def _prepare_vector_search_request(request: VectorSearchRequest) -> dict[str, Any]:
    """
    Prepare a vector search request payload.
    
    Args:
        request: Vector search request
        
    Returns:
        Request payload dictionary
    """
    validated_request = _validate_vector_search_request(request)

    data: dict[str, Any] = {
        "query": validated_request.query.strip()
    }

    # Add optional parameters if provided using dict comprehension approach
    optional_params = {
        "limit": validated_request.limit,
        "offset": validated_request.offset,
        "threshold": validated_request.threshold,
        "includeContent": validated_request.include_content,
    }

    # Add non-None optional parameters
    data.update({k: v for k, v in optional_params.items() if v is not None})
    if validated_request.filters is not None:
        # Convert filters to API format with camelCase
        filters = validated_request.filters.model_dump(exclude_none=True)
        api_filters = {}
        for key, value in filters.items():
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
        data["filters"] = api_filters
    if validated_request.origin is not None and validated_request.origin.strip():
        data["origin"] = validated_request.origin.strip()
    if validated_request.integration is not None and validated_request.integration.strip():
        data["integration"] = validated_request.integration.strip()

    return data
