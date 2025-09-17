"""
Crawling tools for the Firecrawler MCP server.

This module implements crawling tools with job ID management, progress reporting,
status checking, and proper error handling for long-running operations.
"""

import logging
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import (
    CrawlJob,
    CrawlRequest,
    CrawlResponse,
    PaginationConfig,
    ScrapeOptions,
)
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)




def _validate_crawl_parameters(
    url: str,
    exclude_paths: list[str] | None = None,
    include_paths: list[str] | None = None,
    max_concurrency: int | None = None
) -> None:
    """
    Validate crawl parameters for common issues.
    
    Args:
        url: The URL to validate
        exclude_paths: URL patterns to exclude
        include_paths: URL patterns to include  
        max_concurrency: Maximum concurrent requests
        
    Raises:
        ToolError: If validation fails
    """
    try:
        # Validate URL format
        if not url.startswith(("http://", "https://")):
            raise ToolError("URL must start with http:// or https://")

        # Validate regex patterns
        import re
        for field_name, patterns in [
            ("exclude_paths", exclude_paths),
            ("include_paths", include_paths)
        ]:
            if patterns:
                for i, pattern in enumerate(patterns):
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        raise ToolError(f"Invalid regex pattern in {field_name}[{i}]: {pattern} - {e}")

        # Validate concurrency limits
        if max_concurrency and max_concurrency > 50:
            raise ToolError("max_concurrency cannot exceed 50")

        logger.debug(f"Crawl parameters validated successfully for URL: {url}")

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Parameter validation failed: {e}")


def _convert_to_crawl_request(
    url: str,
    prompt: str | None = None,
    exclude_paths: list[str] | None = None,
    include_paths: list[str] | None = None,
    max_discovery_depth: int | None = None,
    sitemap: Literal["skip", "include"] = "include",
    ignore_query_parameters: bool = False,
    limit: int | None = None,
    crawl_entire_domain: bool = False,
    allow_external_links: bool = False,
    allow_subdomains: bool = False,
    delay: int | None = None,
    max_concurrency: int | None = None,
    webhook: str | None = None,
    scrape_options: dict[str, Any] | None = None,
    zero_data_retention: bool = False,
    integration: str | None = None
) -> CrawlRequest:
    """
    Convert MCP parameters to Firecrawl CrawlRequest.
    
    Returns:
        CrawlRequest: The Firecrawl SDK request object
    """
    try:
        # Handle scrape options conversion
        scrape_options_obj = None
        if scrape_options:
            scrape_options_obj = ScrapeOptions(**scrape_options)

        return CrawlRequest(
            url=url,
            prompt=prompt,
            exclude_paths=exclude_paths,
            include_paths=include_paths,
            max_discovery_depth=max_discovery_depth,
            sitemap=sitemap,
            ignore_query_parameters=ignore_query_parameters,
            limit=limit,
            crawl_entire_domain=crawl_entire_domain,
            allow_external_links=allow_external_links,
            allow_subdomains=allow_subdomains,
            delay=delay,
            max_concurrency=max_concurrency,
            webhook=webhook,
            scrape_options=scrape_options_obj,
            zero_data_retention=zero_data_retention,
            integration=integration
        )
    except Exception as e:
        raise ToolError(f"Failed to convert parameters to CrawlRequest: {e}")




def register_crawl_tools(mcp: FastMCP) -> None:
    """Register crawling tools with the FastMCP server."""

    @mcp.tool(
        name="crawl",
        description="Start crawling a website to extract content from multiple pages",
        annotations={
            "title": "Website Crawler",
            "destructiveHint": False,
            "openWorldHint": True
        }
    )
    async def crawl(
        ctx: Context,
        url: Annotated[str, Field(
            description="The URL to crawl",
            pattern=r"^https?://.*"
        )],
        prompt: Annotated[str | None, Field(
            description="Natural language prompt for AI-guided crawling",
            max_length=2000
        )] = None,
        exclude_paths: Annotated[list[str] | None, Field(
            description="URL patterns to exclude from crawling (regex patterns)",
            max_length=100
        )] = None,
        include_paths: Annotated[list[str] | None, Field(
            description="URL patterns to include in crawling (regex patterns)",
            max_length=100
        )] = None,
        max_discovery_depth: Annotated[int | None, Field(
            description="Maximum depth for URL discovery",
            ge=0,
            le=10
        )] = None,
        sitemap: Annotated[Literal["skip", "include"], Field(
            description="Whether to use sitemap for URL discovery"
        )] = "include",
        ignore_query_parameters: Annotated[bool, Field(
            description="Whether to ignore URL query parameters when filtering"
        )] = False,
        limit: Annotated[int | None, Field(
            description="Maximum number of pages to crawl",
            ge=1,
            le=10000
        )] = None,
        crawl_entire_domain: Annotated[bool, Field(
            description="Whether to crawl the entire domain"
        )] = False,
        allow_external_links: Annotated[bool, Field(
            description="Whether to follow external links"
        )] = False,
        allow_subdomains: Annotated[bool, Field(
            description="Whether to include subdomains"
        )] = False,
        delay: Annotated[int | None, Field(
            description="Delay between requests in milliseconds",
            ge=0,
            le=30000
        )] = None,
        max_concurrency: Annotated[int | None, Field(
            description="Maximum concurrent requests",
            ge=1,
            le=50
        )] = None,
        webhook: Annotated[str | None, Field(
            description="Webhook URL for progress notifications",
            pattern=r"^https?://.*"
        )] = None,
        scrape_options: Annotated[dict[str, Any] | None, Field(
            description="Additional scraping options"
        )] = None,
        zero_data_retention: Annotated[bool, Field(
            description="Whether to enable zero data retention mode"
        )] = False,
        integration: Annotated[str | None, Field(
            description="Integration identifier",
            max_length=100
        )] = None
    ) -> CrawlResponse:
        """
        Start a website crawl job to extract content from multiple pages.
        
        This tool initiates a crawl job that will discover and scrape multiple pages
        from a website. The crawl runs asynchronously and returns a job ID that can
        be used to check status and retrieve results.
        
        Args:
            ctx: MCP context for logging and progress reporting
            url: The URL to crawl
            prompt: Natural language prompt for AI-guided crawling
            exclude_paths: URL patterns to exclude from crawling
            include_paths: URL patterns to include in crawling
            max_discovery_depth: Maximum depth for URL discovery
            sitemap: Whether to use sitemap for URL discovery
            ignore_query_parameters: Whether to ignore URL query parameters
            limit: Maximum number of pages to crawl
            crawl_entire_domain: Whether to crawl the entire domain
            allow_external_links: Whether to follow external links
            allow_subdomains: Whether to include subdomains
            delay: Delay between requests in milliseconds
            max_concurrency: Maximum concurrent requests
            webhook: Webhook URL for progress notifications
            scrape_options: Additional scraping options
            zero_data_retention: Whether to enable zero data retention mode
            integration: Integration identifier
            
        Returns:
            CrawlResponse: Information about the started crawl job
            
        Raises:
            ToolError: If the crawl cannot be started
        """
        try:
            await ctx.info(f"Starting crawl for URL: {url}")

            # Validate parameters
            _validate_crawl_parameters(url, exclude_paths, include_paths, max_concurrency)

            # Get Firecrawl client
            firecrawl_client = get_firecrawl_client()

            # Convert to Firecrawl request format
            crawl_request = _convert_to_crawl_request(
                url=url,
                prompt=prompt,
                exclude_paths=exclude_paths,
                include_paths=include_paths,
                max_discovery_depth=max_discovery_depth,
                sitemap=sitemap,
                ignore_query_parameters=ignore_query_parameters,
                limit=limit,
                crawl_entire_domain=crawl_entire_domain,
                allow_external_links=allow_external_links,
                allow_subdomains=allow_subdomains,
                delay=delay,
                max_concurrency=max_concurrency,
                webhook=webhook,
                scrape_options=scrape_options,
                zero_data_retention=zero_data_retention,
                integration=integration
            )

            await ctx.info("Submitting crawl request to Firecrawl API")

            # Start the crawl
            crawl_response: CrawlResponse = firecrawl_client.client.crawl.start_crawl(crawl_request)

            await ctx.info(f"Crawl started successfully with job ID: {crawl_response.id}")

            return crawl_response

        except FirecrawlError as e:
            error_context = {
                "tool": "crawl",
                "url": url,
                "limit": limit
            }
            mcp_error = handle_firecrawl_error(e, error_context)
            await ctx.error(f"Firecrawl API error during crawl: {mcp_error}")
            raise ToolError(str(mcp_error))

        except ToolError:
            raise

        except Exception as e:
            error_msg = f"Unexpected error during crawl: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    @mcp.tool(
        name="crawl_status",
        description="Check the status of a crawl job and retrieve results",
        annotations={
            "title": "Crawl Status Checker",
            "readOnlyHint": True,
            "openWorldHint": True
        }
    )
    async def crawl_status(
        ctx: Context,
        job_id: Annotated[str, Field(
            description="The crawl job ID to check status for",
            pattern=r"^[a-f0-9\-]{36}$"
        )],
        auto_paginate: Annotated[bool, Field(
            description="Whether to automatically fetch all pages of results"
        )] = True,
        max_pages: Annotated[int | None, Field(
            description="Maximum number of pages to fetch (if auto_paginate is True)",
            ge=1,
            le=100
        )] = None,
        max_results: Annotated[int | None, Field(
            description="Maximum number of results to return",
            ge=1,
            le=10000
        )] = None,
        max_wait_time: Annotated[int | None, Field(
            description="Maximum time to wait for pagination in seconds",
            ge=1,
            le=300
        )] = None
    ) -> CrawlJob:
        """
        Check the status of a crawl job and retrieve available results.
        
        This tool checks the progress of a running or completed crawl job and
        returns the current status along with any scraped content that is available.
        
        Args:
            ctx: MCP context for logging and progress reporting
            job_id: The crawl job ID to check status for
            auto_paginate: Whether to automatically fetch all pages of results
            max_pages: Maximum number of pages to fetch
            max_results: Maximum number of results to return
            max_wait_time: Maximum time to wait for pagination
            
        Returns:
            CrawlJob: Current status and available results
            
        Raises:
            ToolError: If the status cannot be retrieved
        """
        try:
            await ctx.info(f"Checking status for crawl job: {job_id}")

            # Get Firecrawl client
            firecrawl_client = get_firecrawl_client()

            # Set up pagination configuration
            pagination_config = None
            if not auto_paginate or max_pages or max_results or max_wait_time:
                pagination_config = PaginationConfig(
                    auto_paginate=auto_paginate,
                    max_pages=max_pages,
                    max_results=max_results,
                    max_wait_time=max_wait_time
                )

            await ctx.info("Fetching crawl status from Firecrawl API")

            # Report initial progress
            await ctx.report_progress(progress=1, total=3)

            # Get crawl status
            crawl_job: CrawlJob = firecrawl_client.client.crawl.get_crawl_status(
                job_id,
                pagination_config
            )

            await ctx.report_progress(progress=2, total=3)

            await ctx.info(f"Status: {crawl_job.status}, Progress: {crawl_job.completed}/{crawl_job.total}")

            await ctx.report_progress(progress=3, total=3)

            # Log completion
            if crawl_job.status == "completed":
                await ctx.info(f"Crawl completed successfully. Retrieved {len(crawl_job.data)} documents.")
            elif crawl_job.status == "failed":
                await ctx.warning(f"Crawl failed. {crawl_job.completed} documents were crawled before failure.")
            else:
                await ctx.info(f"Crawl in progress. {crawl_job.completed}/{crawl_job.total} pages crawled.")

            return crawl_job

        except FirecrawlError as e:
            error_context = {
                "tool": "crawl_status",
                "job_id": job_id
            }
            mcp_error = handle_firecrawl_error(e, error_context)
            await ctx.error(f"Firecrawl API error during crawl status check: {mcp_error}")
            raise ToolError(str(mcp_error))

        except ToolError:
            raise

        except Exception as e:
            error_msg = f"Unexpected error checking crawl status: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e


# Export the registration function
__all__ = ["register_crawl_tools"]
