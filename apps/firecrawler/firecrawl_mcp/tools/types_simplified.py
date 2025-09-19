"""
Simplified type definitions for MCP tools to reduce token usage.

These types provide the same functionality but generate much smaller schemas
by avoiding complex nested Pydantic models that bloat the MCP protocol.
"""

from typing import Any, TypedDict, Optional


class SimplifiedScrapeOptions(TypedDict, total=False):
    """Simplified scrape options - avoids complex nested schemas."""
    formats: list[str]
    headers: dict[str, str]  
    only_main_content: bool
    timeout: int
    mobile: bool
    wait_for: int


class SimplifiedCrawlOptions(TypedDict, total=False):
    """Simplified crawl options - minimal schema generation."""
    limit: int
    max_discovery_depth: int
    allow_subdomains: bool
    exclude_paths: list[str]
    include_paths: list[str]


class SimplifiedExtractOptions(TypedDict, total=False):
    """Simplified extract options."""
    prompt: str
    schema: dict[str, Any]
    enable_web_search: bool


# For backwards compatibility, we can still use the full types internally
# but expose simplified versions in tool signatures
def convert_to_full_options(simplified: dict[str, Any], option_class: type) -> Any:
    """Convert simplified options to full Pydantic models internally."""
    # This is called inside the tool implementation
    return option_class(**simplified) if simplified else None