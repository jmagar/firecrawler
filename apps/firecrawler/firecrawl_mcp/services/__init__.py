"""
Utilities package for FastMCP tool implementation.

This package provides simple utility functions for implementing Firecrawl
functionality using FastMCP's decorator-based patterns. Instead of complex
service hierarchies, FastMCP emphasizes:

- Simple @tool decorated functions
- Context parameter injection for dependencies
- Direct business logic implementation in tools
- Middleware for cross-cutting concerns (logging, timing, error handling)

See CLAUDE.md for comprehensive guidance on FastMCP patterns.
"""

from .base import (
    extract_domain,
    format_file_size,
    get_file_extension,
    get_server_info,
    sanitize_filename,
    truncate_text,
    validate_url,
)

# Export utility functions
__all__ = [
    "extract_domain",
    "format_file_size",
    "get_file_extension",
    "get_server_info",
    "sanitize_filename",
    "truncate_text",
    "validate_url",
]
