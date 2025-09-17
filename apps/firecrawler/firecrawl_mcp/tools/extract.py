"""
AI-powered structured data extraction tool for the Firecrawl MCP server.

This module implements the extract tool for AI-powered structured data extraction
from URLs using LLM integration with schema validation, system prompts, and
comprehensive error handling.
"""

import logging
from typing import Annotated, Any

from fastmcp import Context
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import AgentOptions, ExtractResponse, ScrapeOptions
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)


def register_extract_tools(mcp_instance):
    """Register extract tool with the FastMCP server instance."""

    @mcp_instance.tool(
        name="extract",
        description="Extract structured data from URLs using AI/LLM with customizable prompts and schemas for precise data extraction."
    )
    async def extract(
        ctx: Context,
        urls: Annotated[list[str], Field(
            description="List of URLs to extract data from",
            min_length=1,
            max_length=100
        )],
        prompt: str | None = Field(
            default=None,
            description="Extraction prompt describing what data to extract",
            max_length=10000
        ),
        schema: dict[str, Any] | None = Field(
            default=None,
            description="JSON schema defining the structure of extracted data"
        ),
        system_prompt: str | None = Field(
            default=None,
            description="System prompt to guide the AI's extraction behavior",
            max_length=5000
        ),
        allow_external_links: bool | None = Field(
            default=None,
            description="Whether to allow following external links during extraction"
        ),
        enable_web_search: bool | None = Field(
            default=None,
            description="Whether to enable web search to supplement extraction"
        ),
        show_sources: bool | None = Field(
            default=None,
            description="Whether to include source information in the response"
        ),
        scrape_options: ScrapeOptions | None = Field(
            default=None,
            description="Optional scraping configuration for content retrieval"
        ),
        ignore_invalid_urls: bool | None = Field(
            default=None,
            description="Whether to ignore invalid URLs and continue processing"
        ),
        integration: str | None = Field(
            default=None,
            description="Integration identifier for custom processing",
            max_length=100
        ),
        agent: AgentOptions | None = Field(
            default=None,
            description="AI agent configuration for extraction processing"
        )
    ) -> ExtractResponse:
        """
        Extract structured data from URLs using AI/LLM integration.
        
        This tool uses advanced AI to extract structured data from web pages
        based on provided prompts and schemas. Supports custom system prompts,
        schema validation, and comprehensive extraction options.
        
        Args:
            urls: List of URLs to extract data from
            prompt: Extraction prompt describing what data to extract
            schema: JSON schema defining the structure of extracted data
            system_prompt: System prompt to guide the AI's extraction behavior
            allow_external_links: Whether to allow following external links during extraction
            enable_web_search: Whether to enable web search to supplement extraction
            show_sources: Whether to include source information in the response
            scrape_options: Optional scraping configuration for content retrieval
            ignore_invalid_urls: Whether to ignore invalid URLs and continue processing
            integration: Integration identifier for custom processing
            agent: AI agent configuration for extraction processing
            ctx: MCP context for logging and progress reporting
            
        Returns:
            ExtractResponse: The extraction job response with structured data or job ID
            
        Raises:
            ToolError: If extraction fails or configuration is invalid
        """
        url_count = len(urls)
        await ctx.info(f"Starting AI extraction for {url_count} URLs")

        try:
            # Get the Firecrawl client
            client = get_firecrawl_client()

            # Validate URLs
            if not urls:
                raise ToolError("URLs list cannot be empty")

            if len(urls) > 100:
                raise ToolError("Too many URLs (maximum 100 per extraction)")

            # Validate individual URLs
            invalid_urls = []
            for i, url in enumerate(urls):
                if not url or not isinstance(url, str) or not url.strip():
                    invalid_urls.append(f"URL {i}: empty or invalid")
                elif not (url.startswith("http://") or url.startswith("https://")):
                    invalid_urls.append(f"URL {i}: must start with http:// or https://")

            if invalid_urls and not ignore_invalid_urls:
                raise ToolError(f"Invalid URLs found: {', '.join(invalid_urls[:5])}")

            # Validate extraction parameters
            if not prompt and not schema:
                raise ToolError("Either prompt or schema must be provided for extraction")

            # Report initial progress
            await ctx.report_progress(10, 100)
            await ctx.info(f"Validated {url_count} URLs, starting extraction")

            # Perform the extraction
            extraction_response = client.extract(
                urls=urls,
                prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                allow_external_links=allow_external_links,
                enable_web_search=enable_web_search,
                show_sources=show_sources,
                scrape_options=scrape_options,
                ignore_invalid_urls=ignore_invalid_urls,
                integration=integration,
                agent=agent
            )

            # Report completion based on response status
            if hasattr(extraction_response, 'status'):
                if extraction_response.status == "completed":
                    await ctx.report_progress(100, 100)
                    await ctx.info(f"Extraction completed successfully for {url_count} URLs")
                elif extraction_response.status == "failed":
                    await ctx.report_progress(100, 100)
                    await ctx.warning("Extraction failed for some URLs")
                elif extraction_response.status == "processing":
                    await ctx.report_progress(50, 100)
                    await ctx.info("Extraction job started, use extract_status to check progress")
                else:
                    await ctx.report_progress(100, 100)
                    await ctx.info(f"Extraction job in status: {extraction_response.status}")
            else:
                await ctx.report_progress(100, 100)
                await ctx.info(f"Extraction completed for {url_count} URLs")

            # Log success
            logger.info(
                f"Extraction completed for {url_count} URLs, "
                f"job_id: {getattr(extraction_response, 'id', 'immediate')}, "
                f"status: {getattr(extraction_response, 'status', 'completed')}"
            )

            return extraction_response

        except FirecrawlError as e:
            error_msg = f"Firecrawl API error during extraction: {e}"
            await ctx.error(error_msg)
            raise handle_firecrawl_error(e, "extract")

        except Exception as e:
            error_msg = f"Unexpected error during extraction: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    @mcp_instance.tool(
        name="extract_status",
        description="Check the status of an AI extraction job and retrieve results when completed."
    )
    async def extract_status(
        ctx: Context,
        job_id: Annotated[str, Field(
            description="Extraction job ID",
            min_length=1,
            max_length=256
        )]
    ) -> ExtractResponse:
        """
        Check the status of an AI extraction job and retrieve results.
        
        This tool monitors extraction job progress and retrieves extracted
        structured data when the job is completed.
        
        Args:
            job_id: Extraction job ID
            ctx: MCP context for logging and progress reporting
            
        Returns:
            ExtractResponse: Job status with extracted data if completed
            
        Raises:
            ToolError: If status check fails or job ID is invalid
        """
        await ctx.info(f"Checking extraction status for job: {job_id}")

        try:
            # Get the Firecrawl client
            client = get_firecrawl_client()

            # Validate job ID
            if not job_id.strip():
                raise ToolError("Job ID cannot be empty")

            # Report initial progress
            await ctx.report_progress(20, 100)

            # Get extraction status
            await ctx.info("Fetching job status and results")
            extraction_job = client.get_extract_status(job_id=job_id)

            # Report progress based on job completion
            if hasattr(extraction_job, 'status'):
                if extraction_job.status == "completed":
                    await ctx.report_progress(100, 100)
                    await ctx.info("Extraction job completed successfully")
                elif extraction_job.status == "failed":
                    await ctx.report_progress(100, 100)
                    await ctx.warning(f"Extraction job failed: {getattr(extraction_job, 'error', 'Unknown error')}")
                elif extraction_job.status == "cancelled":
                    await ctx.report_progress(100, 100)
                    await ctx.warning("Extraction job was cancelled")
                else:  # processing
                    await ctx.report_progress(50, 100)
                    await ctx.info("Extraction job still processing")
            else:
                await ctx.report_progress(100, 100)
                await ctx.info("Extraction status retrieved")

            # Log comprehensive status
            logger.info(
                f"Extraction status for job {job_id}: "
                f"status={getattr(extraction_job, 'status', 'unknown')}, "
                f"has_data={hasattr(extraction_job, 'data') and extraction_job.data is not None}"
            )

            return extraction_job

        except FirecrawlError as e:
            error_msg = f"Firecrawl API error during extraction status check: {e}"
            await ctx.error(error_msg)
            raise handle_firecrawl_error(e, "extract_status")

        except Exception as e:
            error_msg = f"Unexpected error during extraction status check: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    return ["extract", "extract_status"]


# Tool exports for registration
__all__ = [
    "register_extract_tools"
]
