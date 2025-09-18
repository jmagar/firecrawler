"""
Web search tool for the Firecrawl MCP server.

This module implements the firesearch tool for web search with optional content extraction.
The tool provides comprehensive parameter validation, optional scraping integration,
and flexible result formatting following FastMCP patterns.
"""

import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import ScrapeOptions, SearchData
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)


def register_firesearch_tools(mcp: FastMCP) -> None:
    """Register the firesearch tool with the FastMCP server."""

    @mcp.tool(
        name="firesearch",
        description="Search the web for information with optional content extraction. Returns search results from multiple sources (web, news, images) with optional full content scraping.",
        annotations={
            "title": "Web Search Engine",
            "readOnlyHint": True,       # Only searches, doesn't modify
            "destructiveHint": False,   # Safe search operation
            "openWorldHint": True,      # Searches external web
            "idempotentHint": False     # Search results may change over time
        }
    )
    async def firesearch(
        ctx: Context,
        query: Annotated[str, Field(
            description="Search query string",
            min_length=1,
            max_length=500
        )],
        sources: list[str] | None = Field(
            default=None,
            description="List of source types to search (web, news, images). Defaults to ['web'] if not specified"
        ),
        categories: list[str] | None = Field(
            default=None,
            description="List of category filters (github, research). Optional category-based filtering"
        ),
        limit: int | None = Field(
            default=5,
            description="Maximum number of search results to return per source type",
            ge=1,
            le=100
        ),
        location: str | None = Field(
            default=None,
            description="Geographic location for search results (e.g., 'United States', 'London')"
        ),
        tbs: str | None = Field(
            default=None,
            description="Time-based search filter (e.g., 'qdr:d' for past day, 'qdr:w' for past week, 'qdr:m' for past month)"
        ),
        ignore_invalid_urls: bool | None = Field(
            default=None,
            description="Whether to ignore invalid URLs and continue processing"
        ),
        timeout: int | None = Field(
            default=60000,
            description="Request timeout in milliseconds",
            ge=1000,
            le=300000
        ),
        scrape_options: ScrapeOptions | None = Field(
            default=None,
            description="Optional scraping configuration to extract full content from search results"
        )
    ) -> SearchData:
        """
        Search the web for information with optional content extraction.
        
        This tool performs web search across multiple sources and optionally extracts
        full content from the found URLs. It supports comprehensive parameter validation,
        multiple source types, geographic filtering, and time-based constraints.
        
        Args:
            query: Search query string
            sources: List of source types to search (web, news, images)
            categories: List of category filters (github, research)
            limit: Maximum number of search results to return per source type
            location: Geographic location for search results
            tbs: Time-based search filter
            ignore_invalid_urls: Whether to ignore invalid URLs and continue processing
            timeout: Request timeout in milliseconds
            scrape_options: Optional scraping configuration to extract full content
            ctx: MCP context for logging and progress reporting
            
        Returns:
            SearchData: Search results grouped by source type with optional scraped content
            
        Raises:
            ToolError: If search fails or configuration is invalid
        """
        await ctx.info(f"Starting web search for query: '{query}'")

        try:
            # Get the Firecrawl client
            client = get_firecrawl_client()

            # Validate and normalize query
            if not query.strip():
                raise ToolError("Search query cannot be empty")

            query = query.strip()

            # Validate and normalize sources
            if sources is None:
                sources = ["web"]

            # Validate source types
            valid_source_types = {"web", "news", "images"}
            for source in sources:
                if not isinstance(source, str):
                    raise ToolError(f"Source must be a string, got: {type(source)}")
                if source not in valid_source_types:
                    raise ToolError(f"Invalid source type: {source}. Valid types: {list(valid_source_types)}")

            # Validate categories
            if categories is not None:
                valid_category_types = {"github", "research"}
                for category in categories:
                    if not isinstance(category, str):
                        raise ToolError(f"Category must be a string, got: {type(category)}")
                    if category not in valid_category_types:
                        raise ToolError(f"Invalid category type: {category}. Valid types: {list(valid_category_types)}")

            # Validate other parameters
            if limit is not None and (limit < 1 or limit > 100):
                raise ToolError("Limit must be between 1 and 100")

            if timeout is not None and (timeout < 1000 or timeout > 300000):
                raise ToolError("Timeout must be between 1000ms and 300000ms (5 minutes)")

            # Validate time-based search parameter
            if tbs is not None:
                valid_tbs_values = {
                    "qdr:h", "qdr:d", "qdr:w", "qdr:m", "qdr:y",  # Google time filters
                    "d", "w", "m", "y"  # Short forms
                }

                if tbs not in valid_tbs_values and not tbs.startswith("cdr:"):
                    raise ToolError(f"Invalid tbs value: {tbs}. Valid values: {list(valid_tbs_values)} or custom date range format: cdr:1,cd_min:MM/DD/YYYY,cd_max:MM/DD/YYYY")

            # Report progress
            await ctx.report_progress(20, 100)

            # Log search parameters
            await ctx.info(f"Search parameters: sources={sources}, limit={limit}, location={location}")
            if scrape_options:
                await ctx.info("Scraping enabled - will extract full content from search results")

            # Report progress
            await ctx.report_progress(40, 100)

            # Perform the search using the client's search method
            await ctx.info("Executing web search")
            search_data = client.search(
                query=query,
                sources=sources,
                categories=categories,
                limit=limit,
                location=location,
                tbs=tbs,
                ignore_invalid_urls=ignore_invalid_urls,
                timeout=timeout,
                scrape_options=scrape_options
            )

            # Report progress
            await ctx.report_progress(80, 100)

            # Count total results
            total_results = 0
            if search_data.web:
                total_results += len(search_data.web)
            if search_data.news:
                total_results += len(search_data.news)
            if search_data.images:
                total_results += len(search_data.images)

            # Report completion
            await ctx.report_progress(100, 100)
            await ctx.info(f"Search completed successfully with {total_results} total results")

            # Log detailed results
            logger.info(
                f"Search completed for query '{query}': "
                f"web={len(search_data.web) if search_data.web else 0}, "
                f"news={len(search_data.news) if search_data.news else 0}, "
                f"images={len(search_data.images) if search_data.images else 0}, "
                f"scraping={'enabled' if scrape_options else 'disabled'}"
            )

            return search_data

        except FirecrawlError as e:
            error_msg = f"Firecrawl API error during search: {e}"
            await ctx.error(error_msg)
            raise handle_firecrawl_error(e, "firesearch")

        except Exception as e:
            error_msg = f"Unexpected error during search: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    return ["firesearch"]


# Tool exports for registration
__all__ = [
    "register_firesearch_tools"
]
