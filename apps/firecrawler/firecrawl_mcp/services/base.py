"""
Simple utilities for Firecrawl MCP tools.

This module provides basic utility functions for FastMCP tool implementation.
Instead of complex service hierarchies, FastMCP emphasizes simple @tool functions
with Context parameter injection for dependencies.
"""

import logging

from ..core.config import get_config

logger = logging.getLogger(__name__)


def validate_url(url: str) -> bool:
    """
    Simple URL validation utility.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL appears valid, False otherwise
    """
    if not isinstance(url, str) or not url.strip():
        return False

    url = url.strip()
    return url.startswith(('http://', 'https://'))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe file system usage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not isinstance(filename, str):
        return "unknown_file"

    # Remove or replace dangerous characters
    import re

    # Replace spaces and special chars with underscores
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)

    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_{2,}', '_', sanitized)

    # Ensure it's not empty and doesn't start with dot
    if not sanitized or sanitized.startswith('.'):
        sanitized = f"file_{sanitized}" if sanitized else "unknown_file"

    return sanitized


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math

    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_names[i]}"


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate text to specified length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not isinstance(text, str):
        return str(text)[:max_length]

    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def extract_domain(url: str) -> str | None:
    """
    Extract domain from URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name or None if extraction fails
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower() if parsed.netloc else None
    except Exception:
        return None


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.
    
    Args:
        filename: Filename to extract extension from
        
    Returns:
        File extension (without dot) or empty string
    """
    if not isinstance(filename, str) or '.' not in filename:
        return ""

    return filename.split('.')[-1].lower()


# Re-export commonly used functions for backward compatibility
__all__ = [
    "extract_domain",
    "format_file_size",
    "get_client",  # From core.client
    "get_config",  # From core.config
    "get_file_extension",
    "sanitize_filename",
    "truncate_text",
    "validate_url",
]
