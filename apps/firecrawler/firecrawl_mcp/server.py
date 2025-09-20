"""
Firecrawl MCP Server - FastMCP server implementation.

This module provides the main FastMCP server instance following the standard FastMCP patterns.
"""

import logging
import os
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

# Load environment variables from root .env file (single source of truth)
try:
    from dotenv import find_dotenv, load_dotenv
    # Find and load the root .env file
    root_env = find_dotenv(usecwd=False)  # Search upward from current location
    if not root_env:
        # If not found via find_dotenv, try explicit path
        root_env = Path(__file__).parent.parent.parent.parent / ".env"

    if Path(root_env).exists():
        load_dotenv(root_env)
        logging.info(f"Loaded environment from {root_env}")
    else:
        logging.warning(f"No .env file found at {root_env}")

    # Optional: Load local overrides if they exist
    local_env = Path(__file__).parent.parent / ".env.local"
    if local_env.exists():
        load_dotenv(local_env, override=True)
        logging.info(f"Loaded local overrides from {local_env}")

except ImportError:
    logging.warning("python-dotenv not available, skipping .env file loading")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create FastMCP server with basic setup
mcp = FastMCP(
    name="Firecrawl MCP Server",
    instructions="""
This server provides comprehensive web scraping, crawling, extraction, and vector search 
capabilities through the Firecrawl API. All tools support advanced configuration options 
and provide detailed progress reporting for long-running operations.

AVAILABLE CAPABILITIES:
• Single URL scraping with format options (scrape)
• Batch URL processing with parallel execution (batch_scrape, batch_status)
• Website crawling with depth control (crawl, crawl_status)
• AI-powered structured data extraction (extract)
• Website URL discovery and mapping (map)
• Web search with optional content extraction (firesearch)
• Vector database Q&A with semantic search (firerag)

TOOL SELECTION GUIDELINES:
• Use 'scrape' for single pages when you know the exact URL
• Use 'batch_scrape' for multiple known URLs
• Use 'map' first to discover URLs, then scrape/batch_scrape for content
• Use 'crawl' for comprehensive website content (be careful with limits)
• Use 'extract' when you need structured data from web pages
• Use 'firesearch' when you don't know which sites have the information
• Use 'firerag' to query your existing scraped content database

BEST PRACTICES:
• Always check operation status for batch/crawl jobs using *_status tools
• Set appropriate limits for crawl operations to avoid token overflow
• Use onlyMainContent=true to reduce noise in scraped content
• Specify output formats clearly (markdown, html, etc.)
• Handle rate limits gracefully - the server will retry automatically
    """.strip(),
)


@mcp.tool
async def health_check(ctx: Context) -> dict[str, Any]:
    """Check server health and Firecrawl API connectivity."""
    try:
        from datetime import UTC, datetime

        from firecrawl_mcp.core.client import get_client_status

        client_status = get_client_status()

        health_info = {
            "server_status": "healthy",
            "server_name": "Firecrawl MCP Server",
            "server_version": "0.1.0",
            "client_status": client_status,
            "timestamp": datetime.now(UTC).isoformat()
        }

        await ctx.info("Health check completed successfully")
        return health_info

    except Exception as e:
        error_msg = f"Health check failed: {e}"
        await ctx.error(error_msg)
        logger.error(f"Health check error: {e}")
        raise ToolError(error_msg) from e


# Register tools from modules
def _register_all_tools():
    """Register all tools on server startup."""
    try:
        from firecrawl_mcp.tools.scrape import register_scrape_tools
        register_scrape_tools(mcp)
        logger.info("Registered scraping tools")
    except ImportError as e:
        logger.warning(f"Could not register scraping tools: {e}")

    try:
        from firecrawl_mcp.tools.crawl import register_crawl_tools
        register_crawl_tools(mcp)
        logger.info("Registered crawling tools")
    except ImportError as e:
        logger.warning(f"Could not register crawling tools: {e}")

    try:
        from firecrawl_mcp.tools.extract import register_extract_tools
        register_extract_tools(mcp)
        logger.info("Registered extraction tools")
    except ImportError as e:
        logger.warning(f"Could not register extraction tools: {e}")

    try:
        from firecrawl_mcp.tools.map import register_map_tools
        register_map_tools(mcp)
        logger.info("Registered mapping tools")
    except ImportError as e:
        logger.warning(f"Could not register mapping tools: {e}")

    try:
        from firecrawl_mcp.tools.firesearch import register_firesearch_tools
        register_firesearch_tools(mcp)
        logger.info("Registered search tools")
    except ImportError as e:
        logger.warning(f"Could not register search tools: {e}")

    try:
        from firecrawl_mcp.tools.firerag import register_firerag_tools
        register_firerag_tools(mcp)
        logger.info("Registered vector search tools")
    except ImportError as e:
        logger.warning(f"Could not register vector search tools: {e}")

# Register tools when module is imported
_register_all_tools()

# Main entry point for running the server
if __name__ == "__main__":
    # Use environment variable for transport type, default to stdio for MCP
    transport = os.getenv("FIRECRAWLER_TRANSPORT", "stdio")

    try:
        if transport == "http":
            host = os.getenv("FIRECRAWLER_HOST", "0.0.0.0")
            port = int(os.getenv("FIRECRAWLER_PORT", "5100"))
            mcp.run(transport="http", host=host, port=port)
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
