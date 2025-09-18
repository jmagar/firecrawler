"""
Unified scraping tool for the Firecrawl MCP server.

This module implements a single unified scraping tool with intelligent mode detection:
- Single URL scraping: When urls parameter is a string
- Batch URL scraping: When urls parameter is a list
- Status checking: When job_id parameter is provided

The tool uses FastMCP decorators, comprehensive annotations, Pydantic validation,
async patterns, intelligent parameter routing, and progress reporting.
"""

import logging
from typing import Annotated, List, Union

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import (
    BatchScrapeJob,
    BatchScrapeResponse,
    Document,
    PaginationConfig,
    ScrapeOptions,
)
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)


async def _handle_single_scrape(
    ctx: Context,
    url: str,
    scrape_options: ScrapeOptions | None
) -> Document:
    """
    Handle single URL scraping mode.
    
    Args:
        ctx: MCP context for logging
        url: URL to scrape
        scrape_options: Optional scraping configuration
        
    Returns:
        Document: The scraped document with content and metadata
        
    Raises:
        ToolError: If scraping fails or configuration is invalid
    """
    await ctx.info(f"Single URL scraping mode: {url}")
    
    try:
        # Get the Firecrawl client
        client = get_firecrawl_client()

        # Validate URL format
        if not url.strip():
            raise ToolError("URL cannot be empty")

        # Perform the scrape
        await ctx.info(f"Scraping URL with options: {scrape_options is not None}")
        
        # Unpack ScrapeOptions into individual keyword arguments for v2 API
        scrape_kwargs = {}
        if scrape_options:
            # Manually map ScrapeOptions fields to avoid any internal field conflicts
            field_mapping = {
                'formats': scrape_options.formats,
                'headers': scrape_options.headers,
                'include_tags': scrape_options.include_tags,
                'exclude_tags': scrape_options.exclude_tags,
                'only_main_content': scrape_options.only_main_content,
                'timeout': scrape_options.timeout,
                'wait_for': scrape_options.wait_for,
                'mobile': scrape_options.mobile,
                'parsers': scrape_options.parsers,
                'actions': scrape_options.actions,
                'location': scrape_options.location,
                'skip_tls_verification': scrape_options.skip_tls_verification,
                'remove_base64_images': scrape_options.remove_base64_images,
                'fast_mode': scrape_options.fast_mode,
                'use_mock': scrape_options.use_mock,
                'block_ads': scrape_options.block_ads,
                'proxy': scrape_options.proxy,
                'max_age': scrape_options.max_age,
                'store_in_cache': scrape_options.store_in_cache,
                'integration': scrape_options.integration,
            }
            # Only include non-None values
            scrape_kwargs = {k: v for k, v in field_mapping.items() if v is not None}
        
        # Debug: print what we're about to pass
        await ctx.info(f"DEBUG: Calling client.scrape with url='{url}' and kwargs: {list(scrape_kwargs.keys())}")
        
        document = client.scrape(url, **scrape_kwargs)

        # Log success
        await ctx.info(f"Successfully scraped URL: {url}")
        content_length = len(document.markdown or document.html or '')
        logger.info(f"Scrape completed for {url}, content length: {content_length}")

        return document

    except FirecrawlError as e:
        error_msg = f"Firecrawl API error during scrape: {e}"
        await ctx.error(error_msg)
        raise handle_firecrawl_error(e, "scrape")

    except Exception as e:
        error_msg = f"Unexpected error during scrape: {e}"
        await ctx.error(error_msg)
        raise ToolError(error_msg) from e


async def _handle_batch_scrape(
    ctx: Context,
    urls: List[str],
    scrape_options: ScrapeOptions | None,
    webhook: str | None,
    max_concurrency: int | None,
    ignore_invalid_urls: bool | None
) -> BatchScrapeResponse:
    """
    Handle batch URL scraping mode.
    
    Args:
        ctx: MCP context for logging
        urls: List of URLs to scrape
        scrape_options: Optional scraping configuration
        webhook: Optional webhook URL for completion notifications
        max_concurrency: Maximum concurrent scraping operations
        ignore_invalid_urls: Whether to ignore invalid URLs and continue
        
    Returns:
        BatchScrapeResponse: Job information with ID and status URL
        
    Raises:
        ToolError: If batch scrape fails to start or configuration is invalid
    """
    url_count = len(urls)
    await ctx.info(f"Batch scraping mode: {url_count} URLs")

    try:
        # Get the Firecrawl client
        client = get_firecrawl_client()

        # Validate URLs
        if not urls:
            raise ToolError("URLs list cannot be empty")

        if len(urls) > 1000:
            raise ToolError("Too many URLs (maximum 1000 per batch)")

        # Validate individual URLs
        invalid_urls = []
        for i, url in enumerate(urls):
            if not url or not isinstance(url, str) or not url.strip():
                invalid_urls.append(f"URL {i}: empty or invalid")
            elif not (url.startswith("http://") or url.startswith("https://")):
                invalid_urls.append(f"URL {i}: must start with http:// or https://")

        if invalid_urls and not ignore_invalid_urls:
            raise ToolError(f"Invalid URLs found: {', '.join(invalid_urls[:5])}")

        # Report progress
        await ctx.report_progress(10, 100)
        await ctx.info(f"Validated {url_count} URLs, starting batch job")

        # Start the batch scrape - v2 API takes individual params
        if scrape_options:
            batch_response = client.start_batch_scrape(
                urls,
                formats=scrape_options.formats,
                headers=scrape_options.headers,
                include_tags=scrape_options.include_tags,
                exclude_tags=scrape_options.exclude_tags,
                only_main_content=scrape_options.only_main_content,
                timeout=scrape_options.timeout,
                wait_for=scrape_options.wait_for,
                mobile=scrape_options.mobile,
                parsers=scrape_options.parsers,
                actions=scrape_options.actions,
                location=scrape_options.location,
                skip_tls_verification=scrape_options.skip_tls_verification,
                remove_base64_images=scrape_options.remove_base64_images,
                fast_mode=scrape_options.fast_mode,
                block_ads=scrape_options.block_ads,
                proxy=scrape_options.proxy,
                max_age=scrape_options.max_age,
                store_in_cache=scrape_options.store_in_cache,
                webhook=webhook,
                max_concurrency=max_concurrency,
                ignore_invalid_urls=ignore_invalid_urls
            )
        else:
            batch_response = client.start_batch_scrape(
                urls,
                webhook=webhook,
                max_concurrency=max_concurrency,
                ignore_invalid_urls=ignore_invalid_urls
            )

        # Report completion
        await ctx.report_progress(100, 100)
        await ctx.info(f"Batch scrape job started with ID: {batch_response.id}")

        logger.info(f"Batch scrape started for {url_count} URLs, job ID: {batch_response.id}")

        return batch_response

    except FirecrawlError as e:
        error_msg = f"Firecrawl API error during batch scrape start: {e}"
        await ctx.error(error_msg)
        raise handle_firecrawl_error(e, "batch_scrape")

    except Exception as e:
        error_msg = f"Unexpected error during batch scrape start: {e}"
        await ctx.error(error_msg)
        raise ToolError(error_msg) from e


async def _handle_scrape_status(
    ctx: Context,
    job_id: str,
    auto_paginate: bool,
    max_pages: int | None,
    max_results: int | None
) -> BatchScrapeJob:
    """
    Handle batch scrape status checking mode.
    
    Args:
        ctx: MCP context for logging
        job_id: Batch scrape job ID
        auto_paginate: Whether to automatically fetch all pages of results
        max_pages: Maximum number of pages to fetch
        max_results: Maximum number of results to return
        
    Returns:
        BatchScrapeJob: Job status with progress information and scraped documents
        
    Raises:
        ToolError: If status check fails or job ID is invalid
    """
    await ctx.info(f"Status checking mode: Checking batch job {job_id}")

    try:
        # Get the Firecrawl client
        client = get_firecrawl_client()

        # Validate job ID
        if not job_id.strip():
            raise ToolError("Job ID cannot be empty")

        # Create pagination config if specified
        pagination_config = None
        if not auto_paginate or max_pages or max_results:
            pagination_config = PaginationConfig(
                auto_paginate=auto_paginate or False,
                max_pages=max_pages,
                max_results=max_results
            )

        # Report initial progress
        await ctx.report_progress(20, 100)

        # Get batch scrape status
        await ctx.info("Fetching job status and results")
        batch_job = client.get_batch_scrape_status(
            job_id=job_id,
            pagination_config=pagination_config
        )

        # Report progress based on job completion
        if batch_job.status == "completed":
            await ctx.report_progress(100, 100)
            await ctx.info(f"Batch job completed: {batch_job.completed}/{batch_job.total} URLs processed")
        elif batch_job.status == "failed":
            await ctx.report_progress(100, 100)
            await ctx.warning(f"Batch job failed: {batch_job.completed}/{batch_job.total} URLs processed")
        elif batch_job.status == "cancelled":
            await ctx.report_progress(100, 100)
            await ctx.warning(f"Batch job cancelled: {batch_job.completed}/{batch_job.total} URLs processed")
        else:  # scraping
            progress = int((batch_job.completed / max(batch_job.total, 1)) * 80) + 20
            await ctx.report_progress(progress, 100)
            await ctx.info(f"Batch job in progress: {batch_job.completed}/{batch_job.total} URLs processed")

        # Log comprehensive status
        result_count = len(batch_job.data) if batch_job.data else 0
        logger.info(
            f"Batch status for job {job_id}: "
            f"status={batch_job.status}, "
            f"completed={batch_job.completed}/{batch_job.total}, "
            f"results={result_count}, "
            f"credits_used={batch_job.credits_used}"
        )

        return batch_job

    except FirecrawlError as e:
        error_msg = f"Firecrawl API error during batch status check: {e}"
        await ctx.error(error_msg)
        raise handle_firecrawl_error(e, "batch_status")

    except Exception as e:
        error_msg = f"Unexpected error during batch status check: {e}"
        await ctx.error(error_msg)
        raise ToolError(error_msg) from e


def register_scrape_tools(mcp: FastMCP) -> None:
    """Register unified scraping tool with the FastMCP server."""

    @mcp.tool(
        name="scrape",
        description="Scrape single or multiple URLs with automatic mode detection and status checking",
        annotations={
            "title": "Website Scraper",
            "readOnlyHint": False,      # Can initiate operations
            "destructiveHint": False,   # Safe - only extracts content  
            "openWorldHint": True,      # Accesses external websites
            "idempotentHint": False     # Results may vary between calls
        }
    )
    async def scrape(
        ctx: Context,
        # Mode detection parameters
        urls: Annotated[Union[str, List[str]] | None, Field(
            description="Single URL (string) or multiple URLs (list) to scrape"
        )] = None,
        job_id: Annotated[str | None, Field(
            description="Job ID for checking batch scrape status (36-char UUID format)",
            min_length=1, max_length=256
        )] = None,
        
        # Shared parameters (work in all modes)
        scrape_options: ScrapeOptions | None = Field(
            default=None,
            description="Optional scraping configuration including format, filters, and extraction options"
        ),
        
        # Batch-specific parameters (ignored for single URL and status)
        webhook: Annotated[str | None, Field(
            description="Webhook URL for batch completion notifications"
        )] = None,
        max_concurrency: Annotated[int | None, Field(
            description="Maximum concurrent scraping operations", ge=1, le=50
        )] = None,
        ignore_invalid_urls: Annotated[bool | None, Field(
            description="Continue processing if some URLs are invalid"
        )] = None,
        
        # Status checking parameters (ignored for scraping)
        auto_paginate: Annotated[bool, Field(
            description="Automatically fetch all result pages"
        )] = True,
        max_pages: Annotated[int | None, Field(
            description="Maximum result pages to fetch", ge=1, le=100
        )] = None,
        max_results: Annotated[int | None, Field(
            description="Maximum results to return", ge=1, le=10000
        )] = None
    ) -> Union[Document, BatchScrapeResponse, BatchScrapeJob]:
        """
        Scrape single or multiple URLs with automatic mode detection and status checking.
        
        This unified tool automatically detects the operation mode based on parameters:
        - If job_id provided: Status checking mode for batch operations
        - If urls is string: Single URL scraping mode
        - If urls is list: Batch URL scraping mode
        
        Args:
            ctx: MCP context for logging and progress reporting
            urls: Single URL (string) or multiple URLs (list) to scrape
            job_id: Job ID for checking batch scrape status
            scrape_options: Optional scraping configuration
            webhook: Webhook URL for batch completion notifications
            max_concurrency: Maximum concurrent scraping operations
            ignore_invalid_urls: Continue processing if some URLs are invalid
            auto_paginate: Automatically fetch all result pages
            max_pages: Maximum result pages to fetch
            max_results: Maximum results to return
            
        Returns:
            Union[Document, BatchScrapeResponse, BatchScrapeJob]: 
                Document for single URL, BatchScrapeResponse for batch start, 
                BatchScrapeJob for status checking
                
        Raises:
            ToolError: If operation fails or configuration is invalid
        """
        try:
            # Mode detection and parameter validation
            if job_id and urls:
                raise ToolError("Cannot provide both 'job_id' and 'urls' - choose either scraping or status checking")
            
            if not job_id and not urls:
                raise ToolError("Either 'urls' (for scraping) or 'job_id' (for status checking) must be provided")
            
            # Route to appropriate handler based on mode detection
            if job_id:
                # Status checking mode
                if webhook or max_concurrency or ignore_invalid_urls:
                    await ctx.warning("Ignoring scraping parameters in status checking mode")
                return await _handle_scrape_status(ctx, job_id, auto_paginate, max_pages, max_results)
                
            elif isinstance(urls, str):
                # Single URL mode
                if webhook or max_concurrency or ignore_invalid_urls or max_pages or max_results:
                    await ctx.warning("Ignoring batch/status parameters in single URL mode")
                return await _handle_single_scrape(ctx, urls, scrape_options)
                
            elif isinstance(urls, list):
                # Batch mode
                if max_pages or max_results:
                    await ctx.warning("Ignoring status checking parameters in batch scraping mode")
                return await _handle_batch_scrape(ctx, urls, scrape_options, webhook, max_concurrency, ignore_invalid_urls)
                
            else:
                raise ToolError(f"Invalid 'urls' parameter type: {type(urls)}. Must be string or list.")
                
        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error in unified scrape tool: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    return ["scrape"]


# Tool exports for registration
__all__ = [
    "register_scrape_tools"
]
