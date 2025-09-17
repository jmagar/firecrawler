"""
Scraping tools for the Firecrawl MCP server.

This module implements three core scraping tools:
- scrape: Single URL scraping with advanced options
- batch_scrape: Multiple URL scraping with parallel processing
- batch_status: Check status of batch scraping operations

All tools use FastMCP decorators, Pydantic validation, async patterns,
comprehensive error handling, and progress reporting for batch operations.
"""

import logging
from typing import Annotated

from fastmcp import Context
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


def register_scrape_tools(mcp_instance):
    """Register all scraping tools with the FastMCP server instance."""

    @mcp_instance.tool(
        name="scrape",
        description="Scrape a single URL and return the document content with configurable options for format selection, content filtering, and extraction parameters."
    )
    async def scrape(
        ctx: Context,
        url: Annotated[str, Field(
            description="URL to scrape",
            pattern=r"^https?://.*",
            min_length=1,
            max_length=2048
        )],
        scrape_options: ScrapeOptions | None = Field(
            default=None,
            description="Optional scraping configuration including format, filters, and extraction options"
        )
    ) -> Document:
        """
        Scrape a single URL and return the document content.
        
        This tool extracts content from a single webpage with configurable options
        for format selection, content filtering, and extraction parameters.
        
        Args:
            url: URL to scrape
            scrape_options: Optional scraping configuration
            ctx: MCP context for logging and progress reporting
            
        Returns:
            Document: The scraped document with content and metadata
            
        Raises:
            ToolError: If scraping fails or configuration is invalid
        """
        await ctx.info(f"Starting scrape for URL: {url}")

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

    @mcp_instance.tool(
        name="batch_scrape",
        description="Start a batch scraping job for multiple URLs with parallel processing and return a job ID for tracking progress."
    )
    async def batch_scrape(
        ctx: Context,
        urls: Annotated[list[str], Field(
            description="List of URLs to scrape",
            min_length=1,
            max_length=1000
        )],
        scrape_options: ScrapeOptions | None = Field(
            default=None,
            description="Optional scraping configuration applied to all URLs"
        ),
        webhook: str | None = Field(
            default=None,
            description="Optional webhook URL for completion notifications"
        ),
        max_concurrency: int | None = Field(
            default=None,
            description="Maximum concurrent scraping operations",
            ge=1,
            le=50
        ),
        ignore_invalid_urls: bool | None = Field(
            default=None,
            description="Whether to ignore invalid URLs and continue processing"
        )
    ) -> BatchScrapeResponse:
        """
        Start a batch scraping job for multiple URLs with parallel processing.
        
        This tool initiates asynchronous scraping of multiple URLs and returns
        a job ID for tracking progress. Use batch_status to monitor completion.
        
        Args:
            urls: List of URLs to scrape
            scrape_options: Optional scraping configuration applied to all URLs
            webhook: Optional webhook URL for completion notifications
            max_concurrency: Maximum concurrent scraping operations
            ignore_invalid_urls: Whether to ignore invalid URLs and continue processing
            ctx: MCP context for logging and progress reporting
            
        Returns:
            BatchScrapeResponse: Job information with ID and status URL
            
        Raises:
            ToolError: If batch scrape fails to start or configuration is invalid
        """
        url_count = len(urls)
        await ctx.info(f"Starting batch scrape for {url_count} URLs")

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

    @mcp_instance.tool(
        name="batch_status",
        description="Check the status of a batch scraping job and retrieve completed results with automatic pagination support."
    )
    async def batch_status(
        ctx: Context,
        job_id: Annotated[str, Field(
            description="Batch scrape job ID",
            min_length=1,
            max_length=256
        )],
        auto_paginate: bool | None = Field(
            default=True,
            description="Whether to automatically fetch all pages of results"
        ),
        max_pages: int | None = Field(
            default=None,
            description="Maximum number of pages to fetch (if auto_paginate is True)",
            ge=1,
            le=100
        ),
        max_results: int | None = Field(
            default=None,
            description="Maximum number of results to return",
            ge=1,
            le=10000
        )
    ) -> BatchScrapeJob:
        """
        Check the status of a batch scraping job and retrieve completed results.
        
        This tool monitors batch scraping progress and retrieves completed documents.
        Supports automatic pagination to fetch all results or partial retrieval
        with configurable limits.
        
        Args:
            job_id: Batch scrape job ID
            auto_paginate: Whether to automatically fetch all pages of results
            max_pages: Maximum number of pages to fetch (if auto_paginate is True)
            max_results: Maximum number of results to return
            ctx: MCP context for logging and progress reporting
            
        Returns:
            BatchScrapeJob: Job status with progress information and scraped documents
            
        Raises:
            ToolError: If status check fails or job ID is invalid
        """
        await ctx.info(f"Checking batch scrape status for job: {job_id}")

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

    return ["scrape", "batch_scrape", "batch_status"]


# Tool exports for registration
__all__ = [
    "register_scrape_tools"
]
