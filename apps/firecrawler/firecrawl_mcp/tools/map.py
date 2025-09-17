"""
Website URL discovery and mapping tool for the Firecrawl MCP server.

This module implements the map tool for comprehensive URL discovery and mapping
from websites including sitemap parsing, subdomain exploration, and URL filtering.
"""

import logging
from typing import Annotated

from fastmcp import Context
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import Location, MapData, MapOptions
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)


def register_map_tools(mcp_instance):
    """Register map tool with the FastMCP server instance."""

    @mcp_instance.tool(
        name="map",
        description="Discover and map URLs from a website including sitemap parsing, subdomain exploration, and comprehensive URL discovery."
    )
    async def map(
        ctx: Context,
        url: Annotated[str, Field(
            description="Website URL to map and discover URLs from",
            pattern=r"^https?://.*",
            min_length=1,
            max_length=2048
        )],
        search: str | None = Field(
            default=None,
            description="Search filter to limit discovered URLs to specific patterns",
            max_length=500
        ),
        sitemap: str | None = Field(
            default="include",
            description="Sitemap handling strategy: 'only' (only from sitemap), 'include' (sitemap + discovery), 'skip' (no sitemap)"
        ),
        include_subdomains: bool | None = Field(
            default=None,
            description="Whether to include URLs from subdomains in the mapping"
        ),
        limit: int | None = Field(
            default=None,
            description="Maximum number of URLs to discover",
            ge=1,
            le=10000
        ),
        timeout: int | None = Field(
            default=None,
            description="Timeout in seconds for the mapping operation",
            ge=1,
            le=300
        ),
        integration: str | None = Field(
            default=None,
            description="Integration identifier for custom processing",
            max_length=100
        ),
        location: Location | None = Field(
            default=None,
            description="Geographic location configuration for mapping"
        )
    ) -> MapData:
        """
        Discover and map URLs from a website with comprehensive discovery options.
        
        This tool performs comprehensive URL discovery from a website including
        sitemap parsing, crawling, subdomain exploration, and intelligent filtering
        to provide a complete map of available URLs.
        
        Args:
            url: Website URL to map and discover URLs from
            search: Search filter to limit discovered URLs to specific patterns
            sitemap: Sitemap handling strategy ('only', 'include', 'skip')
            include_subdomains: Whether to include URLs from subdomains in the mapping
            limit: Maximum number of URLs to discover
            timeout: Timeout in seconds for the mapping operation
            integration: Integration identifier for custom processing
            location: Geographic location configuration for mapping
            ctx: MCP context for logging and progress reporting
            
        Returns:
            MapData: Comprehensive list of discovered URLs with metadata
            
        Raises:
            ToolError: If mapping fails or configuration is invalid
        """
        await ctx.info(f"Starting URL mapping for website: {url}")

        try:
            # Get the Firecrawl client
            client = get_firecrawl_client()

            # Validate URL format
            if not url.strip():
                raise ToolError("URL cannot be empty")

            if not (url.startswith("http://") or url.startswith("https://")):
                raise ToolError("URL must start with http:// or https://")

            # Validate sitemap parameter
            valid_sitemap_values = ["only", "include", "skip"]
            if sitemap and sitemap not in valid_sitemap_values:
                raise ToolError(f"Invalid sitemap value '{sitemap}'. Must be one of: {', '.join(valid_sitemap_values)}")

            # Validate timeout
            if timeout and (timeout < 1 or timeout > 300):
                raise ToolError("Timeout must be between 1 and 300 seconds")

            # Validate limit
            if limit and (limit < 1 or limit > 10000):
                raise ToolError("Limit must be between 1 and 10,000 URLs")

            # Report initial progress
            await ctx.report_progress(10, 100)
            await ctx.info(f"Validated URL, starting mapping with sitemap strategy: {sitemap or 'include'}")

            # Create mapping options
            map_options = None
            if any([search, sitemap, include_subdomains, limit, timeout, integration, location]):
                map_options = MapOptions(
                    search=search,
                    sitemap=sitemap or "include",
                    include_subdomains=include_subdomains,
                    limit=limit,
                    timeout=timeout,
                    integration=integration,
                    location=location
                )

            # Report progress
            await ctx.report_progress(30, 100)
            await ctx.info("Starting URL discovery and mapping")

            # Perform the mapping
            map_data = client.map(url=url, options=map_options)

            # Report completion
            await ctx.report_progress(100, 100)

            # Count discovered URLs and provide summary
            url_count = len(map_data.links) if map_data.links else 0
            await ctx.info(f"Successfully mapped website: discovered {url_count} URLs")

            # Log detailed results
            logger.info(
                f"Mapping completed for {url}: "
                f"discovered={url_count} URLs, "
                f"sitemap_strategy={sitemap or 'include'}, "
                f"search_filter={search is not None}, "
                f"include_subdomains={include_subdomains}, "
                f"limit={limit}"
            )

            # Provide breakdown of URL types if available
            if map_data.links:
                urls_with_titles = sum(1 for link in map_data.links if link.title)
                urls_with_descriptions = sum(1 for link in map_data.links if link.description)

                if urls_with_titles > 0 or urls_with_descriptions > 0:
                    await ctx.info(
                        f"URL metadata: {urls_with_titles} with titles, "
                        f"{urls_with_descriptions} with descriptions"
                    )

            return map_data

        except FirecrawlError as e:
            error_msg = f"Firecrawl API error during URL mapping: {e}"
            await ctx.error(error_msg)
            raise handle_firecrawl_error(e, "map")

        except Exception as e:
            error_msg = f"Unexpected error during URL mapping: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    return ["map"]


# Tool exports for registration
__all__ = [
    "register_map_tools"
]
