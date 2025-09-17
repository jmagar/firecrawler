"""
Vector search tool for the Firecrawl MCP server.

This module implements the firerag tool for vector database Q&A with configurable
LLM synthesis. The tool provides comprehensive filtering, configurable response modes
(raw chunks vs LLM-synthesized answers), and OpenAI/Ollama integration following
FastMCP patterns.
"""

import logging
from typing import Annotated, Any, Literal

from fastmcp import Context
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import (
    VectorSearchData,
    VectorSearchFilters,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
    VectorSearchTiming,
)
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import BaseModel, Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)




# FireRAG response types - using SDK types directly for better alignment
type FireRAGRawResponse = VectorSearchData
type FireRAGSynthesisResponse = dict[str, Any]  # Structured dict with vector data + synthesis


def register_firerag_tools(mcp_instance):
    """Register the firerag tool with the FastMCP server instance."""

    @mcp_instance.tool(
        name="firerag",
        description="Perform semantic vector search with optional LLM synthesis for Q&A. Search the vector database using natural language queries with advanced filtering and configurable response modes."
    )
    async def firerag(
        ctx: Context,
        query: Annotated[str, Field(
            description="Natural language query for semantic search",
            min_length=1,
            max_length=1000
        )],
        limit: int | None = Field(
            default=10,
            description="Maximum number of vector search results to return",
            ge=1,
            le=100
        ),
        offset: int | None = Field(
            default=0,
            description="Number of results to skip for pagination",
            ge=0
        ),
        threshold: float | None = Field(
            default=0.7,
            description="Minimum similarity threshold for results (0.0-1.0)",
            ge=0.0,
            le=1.0
        ),
        include_content: bool | None = Field(
            default=True,
            description="Whether to include full content in results"
        ),
        # Filtering options
        domain: str | None = Field(
            default=None,
            description="Filter by specific domain (e.g., 'docs.python.org')"
        ),
        repository: str | None = Field(
            default=None,
            description="Filter by repository name (e.g., 'pandas')"
        ),
        repository_org: str | None = Field(
            default=None,
            description="Filter by repository organization (e.g., 'microsoft')"
        ),
        repository_full_name: str | None = Field(
            default=None,
            description="Filter by full repository name (e.g., 'microsoft/vscode')"
        ),
        content_type: Literal["readme", "api-docs", "tutorial", "configuration", "code", "other"] | None = Field(
            default=None,
            description="Filter by content type"
        ),
        date_from: str | None = Field(
            default=None,
            description="Filter results from this date (ISO format: YYYY-MM-DD)"
        ),
        date_to: str | None = Field(
            default=None,
            description="Filter results until this date (ISO format: YYYY-MM-DD)"
        ),
        # LLM synthesis configuration
        synthesis_mode: Annotated[Literal["raw", "synthesis", "hybrid"], Field(
            description="Response mode: 'raw' returns raw chunks, 'synthesis' returns LLM-synthesized answer, 'hybrid' returns both"
        )] = "synthesis",
        llm_provider: Annotated[Literal["openai", "ollama"] | None, Field(
            description="LLM provider for synthesis. Auto-detected if not specified"
        )] = None,
        llm_model: Annotated[str | None, Field(
            description="Model name for synthesis. Uses provider defaults if not specified"
        )] = None,
        llm_temperature: Annotated[float | None, Field(
            description="Temperature for LLM synthesis",
            ge=0.0,
            le=2.0
        )] = 0.1,
        llm_max_tokens: Annotated[int | None, Field(
            description="Maximum tokens for LLM synthesis",
            ge=50,
            le=4000
        )] = 1000,
        llm_system_prompt: Annotated[str | None, Field(
            description="Custom system prompt for synthesis. Uses default if not specified"
        )] = None
    ) -> FireRAGRawResponse | FireRAGSynthesisResponse:
        """
        Perform semantic vector search with optional LLM synthesis.
        
        This tool searches the vector database using natural language queries,
        applies comprehensive filtering, and optionally synthesizes results
        using configured LLM providers (OpenAI/Ollama).
        
        Args:
            ctx: FastMCP context for logging and progress reporting
            query: Natural language search query
            limit: Maximum number of results to return
            offset: Number of results to skip (pagination)
            threshold: Minimum similarity score (0.0-1.0)
            include_content: Whether to include full content
            domain: Filter by domain
            repository: Filter by repository name
            repository_org: Filter by organization
            repository_full_name: Filter by full repo name
            content_type: Filter by content type
            date_from: Start date filter (ISO format)
            date_to: End date filter (ISO format)
            synthesis_mode: Response mode for LLM synthesis
            llm_provider: LLM provider for synthesis
            llm_model: Model name for synthesis
            llm_temperature: Temperature for LLM synthesis
            llm_max_tokens: Maximum tokens for LLM synthesis
            llm_system_prompt: Custom system prompt for synthesis
            
        Returns:
            VectorSearchData for raw mode, or dict with vector data and synthesis for synthesis/hybrid modes
            
        Raises:
            ToolError: If vector search fails or LLM synthesis encounters errors
        """
        try:
            await ctx.info(f"Starting FireRAG vector search for query: '{query}'")

            # Build synthesis configuration
            rag_config = {
                "mode": synthesis_mode,
                "llm_provider": llm_provider,
                "model": llm_model,
                "temperature": llm_temperature,
                "max_tokens": llm_max_tokens,
                "system_prompt": llm_system_prompt
            }

            # Build filters
            filters = None
            filter_params = {}

            if any([domain, repository, repository_org, repository_full_name, content_type, date_from, date_to]):
                filter_dict = {}

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
                    date_range = {}
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

            # Get Firecrawl client and perform vector search
            client = get_firecrawl_client()

            await ctx.info("Performing vector similarity search...")
            search_start_time = ctx.request_id  # Use request_id as timing marker

            try:
                search_response = client.vector_search(search_request)
            except FirecrawlError as e:
                await ctx.error(f"Vector search failed: {e}")
                handle_firecrawl_error(e, "vector search")

            if not search_response.success or not search_response.data:
                raise ToolError("Vector search returned no results or failed")

            vector_data = search_response.data
            await ctx.info(f"Found {len(vector_data.results)} results with similarity >= {threshold}")

            # For raw mode, return SDK VectorSearchData directly
            if rag_config["mode"] == "raw":
                await ctx.info("FireRAG search complete. Mode: raw")
                return vector_data

            # For synthesis/hybrid modes, return structured dict with SDK data + synthesis
            response_data = {
                "query": query,
                "mode": rag_config["mode"],
                "vector_search_data": vector_data,  # Include full SDK VectorSearchData
                "filters_applied": filter_params
            }

            # Handle LLM synthesis if requested
            if rag_config["mode"] in ["synthesis", "hybrid"] and vector_data.results:
                await ctx.info("Performing LLM synthesis of search results...")

                synthesis_result = await _perform_llm_synthesis(
                    ctx, query, vector_data.results, rag_config
                )

                response_data.update({
                    "synthesis": synthesis_result["answer"],
                    "synthesis_model": synthesis_result["model"],
                    "synthesis_tokens": synthesis_result["tokens"],
                    "synthesis_timing": synthesis_result["timing"]
                })

            await ctx.info(f"FireRAG search complete. Mode: {rag_config['mode']}")

            return response_data

        except FirecrawlError as e:
            await ctx.error(f"Firecrawl API error in FireRAG: {e}")
            handle_firecrawl_error(e, "FireRAG vector search")
        except Exception as e:
            await ctx.error(f"Unexpected error in FireRAG: {e}")
            raise ToolError(f"FireRAG search failed: {e!s}")


async def _perform_llm_synthesis(
    ctx: Context,
    query: str,
    results: list[VectorSearchResult],
    config: dict[str, Any]
) -> dict[str, Any]:
    """
    Perform LLM synthesis of vector search results.
    
    Args:
        ctx: FastMCP context
        query: Original search query
        results: Vector search results to synthesize
        config: LLM synthesis configuration
        
    Returns:
        Dictionary with synthesis result, model info, and timing
        
    Raises:
        ToolError: If synthesis fails
    """
    try:
        # Build context from search results
        context_chunks = []
        for i, result in enumerate(results[:10], 1):  # Limit to top 10 for synthesis
            content = result.content or result.title or "No content available"
            source = result.metadata.get("sourceURL", result.url)
            context_chunks.append(f"[{i}] {content[:500]}... (Source: {source})")

        context_text = "\n\n".join(context_chunks)

        # Build system prompt
        system_prompt = config["system_prompt"] or _get_default_system_prompt()

        # Build user prompt
        user_prompt = f"""
Query: {query}

Context from vector search results:
{context_text}

Please provide a comprehensive answer to the query based on the context provided above. 
Include specific references to the sources where relevant information was found.
"""

        # Attempt synthesis using available methods
        synthesis_start = 0  # Placeholder for timing

        # Try using FastMCP's sampling capability first
        try:
            sample_result = await ctx.sample(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=config["max_tokens"]
            )

            if sample_result and hasattr(sample_result, 'text'):
                return {
                    "answer": sample_result.text,
                    "model": "mcp_client_llm",
                    "tokens": len(sample_result.text.split()) * 1.3,  # Rough estimate
                    "timing": {"synthesis_ms": 0}  # Timing not available from sample
                }
        except Exception as e:
            await ctx.warning(f"MCP client LLM synthesis failed: {e}")

        # Fallback: Try OpenAI if configured
        if config["llm_provider"] == "openai" or not config["llm_provider"]:
            try:
                import os

                import openai

                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    client = openai.OpenAI(api_key=api_key)

                    response = client.chat.completions.create(
                        model=config["model"] or "gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=config["temperature"],
                        max_tokens=config["max_tokens"]
                    )

                    return {
                        "answer": response.choices[0].message.content,
                        "model": response.model,
                        "tokens": response.usage.total_tokens if response.usage else None,
                        "timing": {"synthesis_ms": 0}
                    }
            except Exception as e:
                await ctx.warning(f"OpenAI synthesis failed: {e}")

        # Fallback: Try Ollama if configured
        if config["llm_provider"] == "ollama" or not config["llm_provider"]:
            try:
                import os

                import httpx

                ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                model = config["model"] or "llama2"

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{ollama_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:",
                            "stream": False,
                            "options": {
                                "temperature": config["temperature"],
                                "num_predict": config["max_tokens"]
                            }
                        },
                        timeout=60.0
                    )

                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "answer": result.get("response", ""),
                            "model": model,
                            "tokens": len(result.get("response", "").split()) * 1.3,
                            "timing": {"synthesis_ms": 0}
                        }
            except Exception as e:
                await ctx.warning(f"Ollama synthesis failed: {e}")

        # Final fallback: Return a basic summary
        await ctx.warning("LLM synthesis unavailable, returning summary of results")

        summary_parts = [f"Found {len(results)} relevant results for query: {query}\n"]

        for i, result in enumerate(results[:5], 1):
            title = result.title or "Untitled"
            source = result.metadata.get("sourceURL", result.url)
            similarity = f"{result.similarity:.3f}"
            summary_parts.append(f"{i}. {title} (similarity: {similarity}) - {source}")

        if len(results) > 5:
            summary_parts.append(f"... and {len(results) - 5} more results")

        return {
            "answer": "\n".join(summary_parts),
            "model": "summary_fallback",
            "tokens": len(" ".join(summary_parts).split()),
            "timing": {"synthesis_ms": 0}
        }

    except Exception as e:
        raise ToolError(f"LLM synthesis failed: {e!s}")


def _get_default_system_prompt() -> str:
    """Get the default system prompt for LLM synthesis."""
    return """You are a helpful AI assistant that answers questions based on provided context from vector search results.

Your task is to:
1. Analyze the provided context from vector search results
2. Answer the user's query comprehensively using the relevant information
3. Include specific references to sources when citing information
4. If the context doesn't contain enough information to answer the query, clearly state this
5. Provide clear, well-structured responses that directly address the query

Guidelines:
- Only use information from the provided context
- Be accurate and avoid speculation
- Cite sources using the provided URLs when referencing specific information
- If conflicting information exists, note this and explain the differences
- Keep responses concise but comprehensive"""


    return ["firerag"]


# Export the registration function
__all__ = ["register_firerag_tools"]
