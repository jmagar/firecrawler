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
    validate_url,
    sanitize_filename,
    format_file_size,
    truncate_text,
    extract_domain,
    get_file_extension,
    get_client,
    get_config,
)

# Export utility functions
__all__ = [
    "validate_url",
    "sanitize_filename", 
    "format_file_size",
    "truncate_text",
    "extract_domain",
    "get_file_extension",
    "get_client",
    "get_config",
]
