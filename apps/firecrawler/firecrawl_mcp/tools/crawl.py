"""
Unified crawling tool for the Firecrawler MCP server.

This module implements a single unified crawling tool with intelligent mode detection:
- Crawl initiation: When url parameter is provided
- Status checking: When job_id parameter is provided

The tool uses FastMCP decorators, comprehensive annotations, job ID management,
progress reporting, and proper error handling for long-running operations.
"""

import logging
from typing import Annotated, Any, Literal, Union

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


async def _handle_crawl_start(
    ctx: Context,
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
) -> CrawlResponse:
    """
    Handle crawl initiation mode.
    
    Args:
        ctx: MCP context for logging
        url: The URL to crawl
        [other parameters as per original crawl function]
        
    Returns:
        CrawlResponse: Information about the started crawl job
        
    Raises:
        ToolError: If the crawl cannot be started
    """
    await ctx.info(f"Crawl initiation mode: Starting crawl for URL: {url}")

    try:
        # Validate parameters
        _validate_crawl_parameters(url, exclude_paths, include_paths, max_concurrency)

        # Get Firecrawl client
        firecrawl_client = get_firecrawl_client()

        await ctx.info("Submitting crawl request to Firecrawl API")

        # Start the crawl
        # Convert sitemap strategy to ignore_sitemap boolean  
        ignore_sitemap = sitemap == "skip" if sitemap else False
        
        crawl_response: CrawlResponse = firecrawl_client.start_crawl(
            url=url,
            prompt=prompt,
            exclude_paths=exclude_paths,
            include_paths=include_paths,
            max_discovery_depth=max_discovery_depth,
            ignore_sitemap=ignore_sitemap,
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


async def _handle_crawl_status(
    ctx: Context,
    job_id: str,
    auto_paginate: bool = True,
    max_pages: int | None = None,
    max_results: int | None = None,
    max_wait_time: int | None = None
) -> CrawlJob:
    """
    Handle crawl status checking mode.
    
    Args:
        ctx: MCP context for logging
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
    await ctx.info(f"Status checking mode: Checking status for crawl job: {job_id}")

    try:
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
        crawl_job: CrawlJob = firecrawl_client.get_crawl_status(
            job_id,
            pagination_config=pagination_config
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

        # Return the full crawl_job object, not just summary
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


def register_crawl_tools(mcp: FastMCP) -> None:
    """Register unified crawling tool with the FastMCP server."""

    @mcp.tool(
        name="crawl",
        description="Start website crawling or check crawl job status with automatic mode detection",
        annotations={
            "title": "Website Crawler",
            "readOnlyHint": False,      # Can initiate crawl jobs
            "destructiveHint": False,   # Safe - only extracts content
            "openWorldHint": True,      # Accesses external websites
            "idempotentHint": False     # Results may vary between calls
        }
    )
    async def crawl(
        ctx: Context,
        # Mode detection parameters
        url: Annotated[str | None, Field(
            description="Website URL to crawl (for starting new crawl job)",
            pattern=r"^https?://.*"
        )] = None,
        job_id: Annotated[str | None, Field(
            description="Crawl job ID for status checking (36-char UUID format)",
            pattern=r"^[a-f0-9\-]{36}$"
        )] = None,
        
        # Crawl initiation parameters (ignored for status checking)
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
        )] = None,
        
        # Status checking parameters (ignored for crawl initiation)
        auto_paginate: Annotated[bool, Field(
            description="Automatically fetch all result pages"
        )] = True,
        max_pages: Annotated[int | None, Field(
            description="Maximum result pages to fetch", ge=1, le=100
        )] = None,
        max_results: Annotated[int | None, Field(
            description="Maximum results to return", ge=1, le=10000
        )] = None,
        max_wait_time: Annotated[int | None, Field(
            description="Maximum wait time for pagination", ge=1, le=300
        )] = None
    ) -> Union[CrawlResponse, CrawlJob]:
        """
        Start website crawling or check crawl job status with automatic mode detection.
        
        This unified tool automatically detects the operation mode based on parameters:
        - If job_id provided: Status checking mode for existing crawl jobs
        - If url provided: Crawl initiation mode to start new crawl job
        
        Args:
            ctx: MCP context for logging and progress reporting
            url: Website URL to crawl (for starting new crawl job)
            job_id: Crawl job ID for status checking
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
            auto_paginate: Automatically fetch all result pages
            max_pages: Maximum result pages to fetch
            max_results: Maximum results to return
            max_wait_time: Maximum wait time for pagination
            
        Returns:
            Union[CrawlResponse, CrawlJob]: CrawlResponse for crawl initiation, 
                CrawlJob for status checking
            
        Raises:
            ToolError: If operation fails or configuration is invalid
        """
        try:
            # Mode detection and parameter validation
            if job_id and url:
                raise ToolError("Cannot provide both 'job_id' and 'url' - choose either crawling or status checking")
            
            if not job_id and not url:
                raise ToolError("Either 'url' (to start crawl) or 'job_id' (to check status) must be provided")
            
            # Route to appropriate handler based on mode detection
            if job_id:
                # Status checking mode
                if any([prompt, exclude_paths, include_paths, limit, webhook]):
                    await ctx.warning("Ignoring crawl parameters in status checking mode")
                return await _handle_crawl_status(ctx, job_id, auto_paginate, max_pages, max_results, max_wait_time)
                
            elif url:
                # Crawl initiation mode
                if any([max_pages, max_results, max_wait_time]):
                    await ctx.warning("Ignoring status checking parameters in crawl initiation mode")
                return await _handle_crawl_start(
                    ctx, url, prompt, exclude_paths, include_paths, max_discovery_depth,
                    sitemap, ignore_query_parameters, limit, crawl_entire_domain,
                    allow_external_links, allow_subdomains, delay, max_concurrency,
                    webhook, scrape_options, zero_data_retention, integration
                )
            else:
                raise ToolError("Invalid parameter combination")
                
        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error in unified crawl tool: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e



# Export the registration function
__all__ = ["register_crawl_tools"]
