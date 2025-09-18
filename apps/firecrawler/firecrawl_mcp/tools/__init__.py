"""
MCP Tools package for Firecrawl operations.

This package contains all the MCP tools that expose Firecrawl functionality:
- scrape: Single URL scraping with advanced options
- batch_scrape: Multiple URL scraping with parallel processing  
- batch_status: Check status of batch operations
- crawl: Website crawling with unified status checking
- extract: AI-powered structured data extraction with unified status checking
- map: Website URL discovery and mapping
- firesearch: Web search with optional content extraction
- firerag: Vector database semantic search without additional LLM synthesis

Each tool follows FastMCP patterns with proper validation, error handling,
and progress reporting.
"""

# Import implemented tools
from .crawl import register_crawl_tools
from .extract import register_extract_tools
from .firerag import register_firerag_tools
from .firesearch import register_firesearch_tools
from .map import register_map_tools
from .scrape import register_scrape_tools

__all__ = [
    "register_crawl_tools",
    "register_extract_tools",
    "register_firerag_tools",
    "register_firesearch_tools",
    "register_map_tools",
    "register_scrape_tools",
]
