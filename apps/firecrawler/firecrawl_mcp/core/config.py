"""
FastMCP-compatible environment utilities.

This module provides simple environment variable access following FastMCP patterns,
replacing the complex dataclass configuration system.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Parse a boolean environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Boolean value from environment or default
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on", "enabled")


def get_env_int(key: str, default: int) -> int:
    """
    Parse an integer environment variable with fallback.
    
    Args:
        key: Environment variable name
        default: Default value if not set or invalid
        
    Returns:
        Integer value from environment or default
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid {key} value: {value}, using default: {default}")
        return default


def get_env_float(key: str, default: float) -> float:
    """
    Parse a float environment variable with fallback.
    
    Args:
        key: Environment variable name
        default: Default value if not set or invalid
        
    Returns:
        Float value from environment or default
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        return float(value)
    except ValueError:
        logger.warning(f"Invalid {key} value: {value}, using default: {default}")
        return default


def get_server_info() -> dict[str, Any]:
    """
    Get basic server information from environment.
    
    Returns:
        Dict with server name, version, and configuration status
    """
    return {
        "server_name": os.getenv("MCP_SERVER_NAME", "Firecrawl MCP Server"),
        "server_version": os.getenv("MCP_SERVER_VERSION", "1.0.0"),
        "api_url": os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev"),
        "api_key_configured": bool(os.getenv("FIRECRAWL_API_KEY")),
        "debug_mode": get_env_bool("DEBUG_MODE"),
        "development_mode": get_env_bool("DEVELOPMENT_MODE"),
    }


def validate_environment() -> dict[str, Any]:
    """
    Validate essential environment configuration.
    
    Returns:
        Dict containing validation results and recommendations
    """
    issues = []
    recommendations = []
    
    # Check required configuration
    if not os.getenv("FIRECRAWL_API_KEY"):
        issues.append("FIRECRAWL_API_KEY is required but not set")
        recommendations.append("Set FIRECRAWL_API_KEY environment variable")
    
    # Check optional but useful configuration
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OLLAMA_BASE_URL"):
        recommendations.append("Consider setting OPENAI_API_KEY or OLLAMA_BASE_URL for LLM features")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "recommendations": recommendations,
        "server_info": get_server_info()
    }


# Backward compatibility functions - these will be deprecated
class MCPConfig:
    """
    DEPRECATED: Legacy config class for backward compatibility.
    
    Use environment functions directly instead of this class.
    """
    
    def __init__(self):
        logger.warning("MCPConfig is deprecated, use environment functions directly")
        
    def is_valid(self) -> bool:
        return validate_environment()["valid"]
        
    def get_current_timestamp(self) -> str:
        from datetime import datetime, UTC
        return datetime.now(UTC).isoformat()


def load_config():
    """
    DEPRECATED: Load configuration.
    
    Use validate_environment() or direct environment access instead.
    """
    logger.warning("load_config() is deprecated, use validate_environment() instead")
    return MCPConfig()
