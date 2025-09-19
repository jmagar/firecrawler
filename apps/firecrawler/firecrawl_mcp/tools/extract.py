"""
Unified AI-powered structured data extraction tool for the Firecrawl MCP server.

This module implements a single unified extraction tool with intelligent mode detection:
- Extraction initiation: When urls parameter is provided
- Status checking: When job_id parameter is provided

The tool uses FastMCP decorators, comprehensive annotations, job ID management,
progress reporting, and proper error handling for AI-powered data extraction.
"""

import logging
from typing import Annotated, Any, Dict, Union

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from firecrawl.v2.types import AgentOptions, ExtractResponse, ScrapeOptions  # Still import for internal use
from firecrawl.v2.utils.error_handler import FirecrawlError
from pydantic import Field

from ..core.client import get_firecrawl_client
from ..core.exceptions import handle_firecrawl_error

logger = logging.getLogger(__name__)


async def _handle_extract_start(
    ctx: Context,
    urls: list[str],
    prompt: str | None = None,
    schema: dict[str, Any] | None = None,
    system_prompt: str | None = None,
    allow_external_links: bool | None = None,
    enable_web_search: bool | None = None,
    show_sources: bool | None = None,
    scrape_options: Dict[str, Any] | None = None,
    ignore_invalid_urls: bool | None = None,
    integration: str | None = None,
    agent: AgentOptions | None = None
) -> ExtractResponse:
    """
    Handle extraction initiation mode.
    
    Args:
        ctx: MCP context for logging and progress reporting
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
        
    Returns:
        ExtractResponse: The extraction job response with structured data or job ID
        
    Raises:
        ToolError: If extraction fails or configuration is invalid
    """
    url_count = len(urls)
    await ctx.info(f"Extraction initiation mode: Starting AI extraction for {url_count} URLs")

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

        # Build extraction kwargs
        extract_kwargs = {
            'urls': urls,
            'prompt': prompt,
            'schema': schema,
            'system_prompt': system_prompt,
            'allow_external_links': allow_external_links,
            'enable_web_search': enable_web_search,
            'show_sources': show_sources,
            'ignore_invalid_urls': ignore_invalid_urls,
            'integration': integration,
            'agent': agent
        }
        
        # Handle scrape_options conversion
        if scrape_options:
            if isinstance(scrape_options, dict):
                # Convert dict to ScrapeOptions for SDK
                extract_kwargs['scrape_options'] = ScrapeOptions(**scrape_options) if scrape_options else None
            else:
                extract_kwargs['scrape_options'] = scrape_options
        
        # Remove None values
        extract_kwargs = {k: v for k, v in extract_kwargs.items() if v is not None}
        
        # Perform the extraction
        extraction_response = client.extract(**extract_kwargs)

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
                await ctx.info("Extraction job started, check status with job_id parameter")
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


async def _handle_extract_status(
    ctx: Context,
    job_id: str
) -> dict[str, Any]:
    """
    Handle extraction status checking mode - STATUS ONLY, NO DATA.
    
    This function returns only extraction progress information and brief summaries.
    It does NOT return actual extracted data. Use vector search or other tools
    to retrieve actual extracted data.
    
    Args:
        ctx: MCP context for logging and progress reporting
        job_id: Extraction job ID
        
    Returns:
        dict[str, Any]: Status information with concise summary, NO actual data
        
    Raises:
        ToolError: If status check fails or job ID is invalid
    """
    await ctx.info(f"Status checking mode: Checking extraction status for job: {job_id}")

    try:
        # Get the Firecrawl client
        client = get_firecrawl_client()

        # Validate job ID
        if not job_id.strip():
            raise ToolError("Job ID cannot be empty")

        # Report initial progress
        await ctx.report_progress(20, 100)

        # Get extraction status WITHOUT data
        await ctx.info("Fetching job status from Firecrawl API (status only, no data)")
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

        # Create status-only response with concise summary
        status_response = {
            'job_id': job_id,
            'status': getattr(extraction_job, 'status', 'unknown'),
            'credits_used': getattr(extraction_job, 'credits_used', None),
            'expires_at': getattr(extraction_job, 'expires_at', None),
            'summary': {
                'extraction_completed': getattr(extraction_job, 'status', 'unknown') == 'completed',
                'has_extracted_data': hasattr(extraction_job, 'data') and extraction_job.data is not None,
                'data_count': len(extraction_job.data) if hasattr(extraction_job, 'data') and extraction_job.data else 0,
                'error_message': getattr(extraction_job, 'error', None) if getattr(extraction_job, 'status', 'unknown') == 'failed' else None
            }
        }

        # Log comprehensive status
        logger.info(
            f"Extraction status for job {job_id}: "
            f"status={getattr(extraction_job, 'status', 'unknown')}, "
            f"has_data={hasattr(extraction_job, 'data') and extraction_job.data is not None}"
        )

        return status_response

    except FirecrawlError as e:
        error_msg = f"Firecrawl API error during extraction status check: {e}"
        await ctx.error(error_msg)
        raise handle_firecrawl_error(e, "extract_status")

    except Exception as e:
        error_msg = f"Unexpected error during extraction status check: {e}"
        await ctx.error(error_msg)
        raise ToolError(error_msg) from e


def register_extract_tools(mcp: FastMCP) -> None:
    """Register unified extraction tool with the FastMCP server."""

    @mcp.tool(
        name="extract",
        description="AI-powered data extraction from URLs or check extraction job status. Status mode returns progress only, NOT actual data.",
        annotations={
            "title": "AI Data Extractor (Status mode returns summaries only)",
            "readOnlyHint": False,      # Can initiate extraction jobs
            "destructiveHint": False,   # Safe - only extracts data
            "openWorldHint": True,      # Accesses external websites
            "idempotentHint": False,    # AI extraction may vary
            "requiresInternet": True
        }
    )
    async def extract(
        ctx: Context,
        # Mode detection parameters
        urls: Annotated[list[str] | None, Field(
            description="List of URLs to extract data from (1-100 URLs for starting extraction)",
            min_length=1,
            max_length=100
        )] = None,
        job_id: Annotated[str | None, Field(
            description="Extraction job ID for status checking",
            min_length=1,
            max_length=256
        )] = None,
        
        # Extraction configuration (only used in extraction mode)
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
        scrape_options: Dict[str, Any] | None = Field(
            default=None,
            description="Optional scraping configuration (formats, headers, timeout, etc)"
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
    ) -> Union[ExtractResponse, dict[str, Any]]:
        """
        Extract structured data from URLs or check extraction job status with automatic mode detection.
        
        This unified tool automatically detects the operation mode based on parameters:
        - If job_id provided: Status checking mode for existing extraction jobs (STATUS ONLY, NO DATA)
        - If urls provided: Extraction initiation mode to start new extraction job
        
        Args:
            ctx: MCP context for logging and progress reporting
            urls: List of URLs to extract data from (for starting new extraction)
            job_id: Extraction job ID for status checking
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
            
        Returns:
            Union[ExtractResponse, dict[str, Any]]: ExtractResponse for extraction initiation,
                status summary dict for status checking (NO actual data)
            
        Raises:
            ToolError: If operation fails or configuration is invalid
        """
        try:
            # Mode detection and parameter validation
            if job_id and urls:
                raise ToolError("Cannot provide both 'job_id' and 'urls' - choose either extraction or status checking")
            
            if not job_id and not urls:
                raise ToolError("Either 'urls' (to start extraction) or 'job_id' (to check status) must be provided")
            
            # Route to appropriate handler based on mode detection
            if job_id:
                # Status checking mode
                if any([prompt, schema, system_prompt, allow_external_links, enable_web_search, show_sources, scrape_options, ignore_invalid_urls, integration, agent]):
                    await ctx.warning("Ignoring extraction parameters in status checking mode")
                return await _handle_extract_status(ctx, job_id)
                
            elif urls:
                # Extraction initiation mode
                await ctx.info(f"Starting extraction for {len(urls)} URL(s)")
                return await _handle_extract_start(
                    ctx, urls, prompt, schema, system_prompt,
                    allow_external_links, enable_web_search, show_sources,
                    scrape_options, ignore_invalid_urls, integration, agent
                )
            else:
                raise ToolError("Invalid parameter combination")
                
        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error in unified extract tool: {e}"
            await ctx.error(error_msg)
            raise ToolError(error_msg) from e

    logger.info("Registered extract tool with dual-mode functionality")


# Tool exports for registration
__all__ = [
    "register_extract_tools"
]
