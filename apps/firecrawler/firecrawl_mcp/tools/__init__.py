"""
Firecrawl MCP Tools Module

This module provides MCP tool implementations for the Firecrawl API, enabling
LLMs to perform web scraping, crawling, and content extraction tasks.

Available Tools:
- scrape: Single/batch URL scraping with multiple format support
- crawl: Website crawling with depth control
- extract: AI-powered structured data extraction
- map: URL discovery and sitemap generation
- firesearch: Web search with optional content extraction
- firerag: Vector database semantic search

Each tool follows MCP patterns with Context-based logging and proper error handling.

Usage:
    Tools are automatically registered with the MCP server and can be invoked
    by LLM clients through the Model Context Protocol.
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
