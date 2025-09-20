"""
FastMCP-aligned resources implementation for Firecrawler MCP server.

This module provides comprehensive MCP resources following FastMCP patterns exactly:
- Direct @mcp.resource decoration (no wrapper functions)
- Simple error handling with direct exception raising
- Resource templates for dynamic URI access
- Basic caching for expensive operations
- Clean, maintainable architecture aligned with FastMCP documentation

Resources expose server configuration, status information, logs, and operational data
to MCP clients using proper FastMCP patterns and best practices.
"""

import logging
import os
import platform
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import psutil
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ResourceError

from ..core.client import get_firecrawl_client
from ..core.config import get_env_bool, get_env_int
from ..core.exceptions import MCPClientError

logger = logging.getLogger(__name__)


def _get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value with fallback to environment variable."""
    # Map attribute names to environment variable names
    env_map = {
        "server_name": "MCP_SERVER_NAME",
        "server_version": "MCP_SERVER_VERSION",
        "server_host": "MCP_SERVER_HOST",
        "server_port": "MCP_SERVER_PORT",
        "development_mode": "DEVELOPMENT_MODE",
        "firecrawl_api_url": "FIRECRAWL_API_URL",
        "firecrawl_api_key": "FIRECRAWL_API_KEY",
        "firecrawl_timeout": "FIRECRAWL_TIMEOUT",
        "firecrawl_max_retries": "FIRECRAWL_MAX_RETRIES",
        "firecrawl_backoff_factor": "FIRECRAWL_BACKOFF_FACTOR",
        "auth_enabled": "AUTH_ENABLED",
        "rate_limit_enabled": "RATE_LIMIT_ENABLED",
        "cache_enabled": "CACHE_ENABLED",
        "vector_search_enabled": "VECTOR_SEARCH_ENABLED",
        "debug_mode": "DEBUG_MODE",
        "enable_metrics": "ENABLE_METRICS",
        "enable_health_checks": "ENABLE_HEALTH_CHECKS",
        "log_level": "LOG_LEVEL",
        "log_format": "LOG_FORMAT",
        "log_file": "LOG_FILE",
        "log_max_size": "LOG_MAX_SIZE",
        "log_backup_count": "LOG_BACKUP_COUNT",
        "rate_limit_requests_per_minute": "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "rate_limit_requests_per_hour": "RATE_LIMIT_REQUESTS_PER_HOUR",
        "rate_limit_burst_size": "RATE_LIMIT_BURST_SIZE",
        "openai_model": "OPENAI_MODEL",
        "ollama_model": "OLLAMA_MODEL",
        "cache_ttl_seconds": "CACHE_TTL_SECONDS",
        "cache_max_size": "CACHE_MAX_SIZE",
        "vector_search_threshold": "VECTOR_SEARCH_THRESHOLD",
        "vector_search_limit": "VECTOR_SEARCH_LIMIT",
    }

    env_key = env_map.get(key)
    if not env_key:
        return default

    # Define defaults for various config values
    defaults = {
        "server_name": "Firecrawl MCP Server",
        "server_version": "1.0.0",
        "server_host": "localhost",
        "server_port": "8080",
        "development_mode": False,
        "firecrawl_api_url": "https://api.firecrawl.dev",
        "firecrawl_timeout": 30,
        "firecrawl_max_retries": 3,
        "firecrawl_backoff_factor": 2.0,
        "auth_enabled": False,
        "rate_limit_enabled": False,
        "cache_enabled": False,
        "vector_search_enabled": False,
        "debug_mode": False,
        "enable_metrics": False,
        "enable_health_checks": True,
        "log_level": "INFO",
        "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "log_file": "firecrawler.log",
        "log_max_size": 10 * 1024 * 1024,  # 10MB
        "log_backup_count": 5,
        "rate_limit_requests_per_minute": 60,
        "rate_limit_requests_per_hour": 1000,
        "rate_limit_burst_size": 10,
        "openai_model": "gpt-3.5-turbo",
        "ollama_model": "llama2",
        "cache_ttl_seconds": 3600,
        "cache_max_size": 1000,
        "vector_search_threshold": 0.7,
        "vector_search_limit": 10,
    }

    config_default = defaults.get(key, default)

    # Handle boolean values
    if key in ["development_mode", "auth_enabled", "rate_limit_enabled", "cache_enabled",
               "vector_search_enabled", "debug_mode", "enable_metrics", "enable_health_checks"]:
        return get_env_bool(env_key, bool(config_default))

    # Handle integer values
    if key in ["firecrawl_timeout", "firecrawl_max_retries", "log_max_size", "log_backup_count",
               "rate_limit_requests_per_minute", "rate_limit_requests_per_hour", "rate_limit_burst_size",
               "cache_ttl_seconds", "cache_max_size", "vector_search_limit"]:
        return get_env_int(env_key, config_default if isinstance(config_default, int) else 0)

    # Handle float values
    if key in ["firecrawl_backoff_factor", "vector_search_threshold"]:
        value = os.getenv(env_key)
        if value is not None:
            try:
                return float(value)
            except ValueError:
                pass
        return config_default

    # String values
    return os.getenv(env_key, config_default)


def _mask_sensitive_value(value: str) -> str:
    """Mask sensitive values for display."""
    if not value or len(value) <= 8:
        return "*" * len(value) if value else ""
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _get_llm_provider() -> str:
    """Get the preferred LLM provider."""
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    elif os.getenv("OLLAMA_BASE_URL"):
        return "ollama"
    return "none"


def _has_llm_provider() -> bool:
    """Check if any LLM provider is configured."""
    return bool(os.getenv("OPENAI_API_KEY")) or bool(os.getenv("OLLAMA_BASE_URL"))


def _get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


def _is_config_valid() -> bool:
    """Check if configuration is valid."""
    return bool(os.getenv("FIRECRAWL_API_KEY"))


# Cache for expensive operations (simple in-memory cache)
@lru_cache(maxsize=128)
def _get_cached_system_info() -> dict[str, Any]:
    """Get cached system information that doesn't change frequently."""
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        }
    }


# Resource functions that will be registered during setup
async def get_server_config(ctx: Context) -> dict[str, Any]:
    """Get comprehensive server configuration information."""
    server_config = {
        "server_info": {
            "name": _get_config_value("server_name"),
            "version": _get_config_value("server_version"),
            "host": _get_config_value("server_host"),
            "port": _get_config_value("server_port"),
            "environment": "development" if _get_config_value("development_mode") else "production",
        },
        "api_configuration": {
            "base_url": _get_config_value("firecrawl_api_url"),
            "has_api_key": bool(_get_config_value("firecrawl_api_key")),
            "timeout": _get_config_value("firecrawl_timeout"),
            "max_retries": _get_config_value("firecrawl_max_retries"),
            "backoff_factor": _get_config_value("firecrawl_backoff_factor"),
        },
        "feature_flags": {
            "auth_enabled": _get_config_value("auth_enabled"),
            "rate_limit_enabled": _get_config_value("rate_limit_enabled"),
            "cache_enabled": _get_config_value("cache_enabled"),
            "vector_search_enabled": _get_config_value("vector_search_enabled"),
            "debug_mode": _get_config_value("debug_mode"),
            "metrics_enabled": _get_config_value("enable_metrics"),
            "health_checks_enabled": _get_config_value("enable_health_checks"),
        },
        "logging_config": {
            "level": _get_config_value("log_level"),
            "format": _get_config_value("log_format"),
            "file": _get_config_value("log_file"),
            "max_size_mb": _get_config_value("log_max_size") // (1024 * 1024),
            "backup_count": _get_config_value("log_backup_count"),
        },
        "rate_limiting": {
            "enabled": _get_config_value("rate_limit_enabled"),
            "requests_per_minute": _get_config_value("rate_limit_requests_per_minute"),
            "requests_per_hour": _get_config_value("rate_limit_requests_per_hour"),
            "burst_size": _get_config_value("rate_limit_burst_size"),
        },
        "llm_providers": {
            "available": [
                provider
                for provider in ["openai", "ollama"]
                if os.getenv(f"{provider.upper()}_API_KEY" if provider == "openai" else f"{provider.upper()}_BASE_URL")
            ],
            "preferred": _get_llm_provider(),
            "openai_model": _get_config_value("openai_model"),
            "ollama_model": _get_config_value("ollama_model"),
        },
        "cache_settings": {
            "enabled": _get_config_value("cache_enabled"),
            "ttl_seconds": _get_config_value("cache_ttl_seconds"),
            "max_size": _get_config_value("cache_max_size"),
        },
        "vector_search": {
            "enabled": _get_config_value("vector_search_enabled"),
            "threshold": _get_config_value("vector_search_threshold"),
            "default_limit": _get_config_value("vector_search_limit"),
        },
        "timestamp": _get_current_timestamp(),
        "config_valid": _is_config_valid(),
    }

    await ctx.info("Server configuration retrieved successfully")
    return server_config


async def get_environment_config(ctx: Context) -> dict[str, Any]:
    """Get environment variable configuration with sensitive values masked."""
    # Define environment variables to include
    env_vars = {
        # Firecrawl Configuration
        "FIRECRAWL_API_KEY": _mask_sensitive_value(os.getenv("FIRECRAWL_API_KEY", "")),
        "FIRECRAWL_API_URL": os.getenv("FIRECRAWL_API_URL", ""),
        "FIRECRAWL_TIMEOUT": os.getenv("FIRECRAWL_TIMEOUT", ""),
        "FIRECRAWL_MAX_RETRIES": os.getenv("FIRECRAWL_MAX_RETRIES", ""),
        "FIRECRAWL_BACKOFF_FACTOR": os.getenv("FIRECRAWL_BACKOFF_FACTOR", ""),
        # Server Configuration
        "MCP_SERVER_NAME": os.getenv("MCP_SERVER_NAME", ""),
        "MCP_SERVER_VERSION": os.getenv("MCP_SERVER_VERSION", ""),
        "MCP_SERVER_HOST": os.getenv("MCP_SERVER_HOST", ""),
        "MCP_SERVER_PORT": os.getenv("MCP_SERVER_PORT", ""),
        # Logging
        "LOG_LEVEL": os.getenv("LOG_LEVEL", ""),
        "LOG_FORMAT": os.getenv("LOG_FORMAT", ""),
        "LOG_FILE": os.getenv("LOG_FILE", ""),
        # Authentication
        "AUTH_ENABLED": os.getenv("AUTH_ENABLED", ""),
        "AUTH_TOKEN": _mask_sensitive_value(os.getenv("AUTH_TOKEN", "")),
        "AUTH_API_KEYS": "<masked>" if os.getenv("AUTH_API_KEYS") else "",
        # Rate Limiting
        "RATE_LIMIT_ENABLED": os.getenv("RATE_LIMIT_ENABLED", ""),
        "RATE_LIMIT_REQUESTS_PER_MINUTE": os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", ""),
        "RATE_LIMIT_REQUESTS_PER_HOUR": os.getenv("RATE_LIMIT_REQUESTS_PER_HOUR", ""),
        # Cache Configuration
        "CACHE_ENABLED": os.getenv("CACHE_ENABLED", ""),
        "CACHE_TTL_SECONDS": os.getenv("CACHE_TTL_SECONDS", ""),
        "CACHE_MAX_SIZE": os.getenv("CACHE_MAX_SIZE", ""),
        # Vector Search
        "VECTOR_SEARCH_ENABLED": os.getenv("VECTOR_SEARCH_ENABLED", ""),
        "VECTOR_SEARCH_THRESHOLD": os.getenv("VECTOR_SEARCH_THRESHOLD", ""),
        # LLM Providers
        "OPENAI_API_KEY": _mask_sensitive_value(os.getenv("OPENAI_API_KEY", "")),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", ""),
        "OPENAI_MAX_TOKENS": os.getenv("OPENAI_MAX_TOKENS", ""),
        "OPENAI_TEMPERATURE": os.getenv("OPENAI_TEMPERATURE", ""),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", ""),
        "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL", ""),
        # Development
        "DEBUG_MODE": os.getenv("DEBUG_MODE", ""),
        "DEVELOPMENT_MODE": os.getenv("DEVELOPMENT_MODE", ""),
        "ENABLE_METRICS": os.getenv("ENABLE_METRICS", ""),
        "ENABLE_HEALTH_CHECKS": os.getenv("ENABLE_HEALTH_CHECKS", ""),
    }

    # Filter out empty values and organize by category
    environment_config = {
        "firecrawl_api": {
            key: value for key, value in env_vars.items() if key.startswith("FIRECRAWL_") and value
        },
        "server": {
            key: value for key, value in env_vars.items() if key.startswith("MCP_SERVER_") and value
        },
        "logging": {
            key: value for key, value in env_vars.items() if key.startswith("LOG_") and value
        },
        "authentication": {
            key: value for key, value in env_vars.items() if key.startswith("AUTH_") and value
        },
        "rate_limiting": {
            key: value for key, value in env_vars.items() if key.startswith("RATE_LIMIT_") and value
        },
        "cache": {
            key: value for key, value in env_vars.items() if key.startswith("CACHE_") and value
        },
        "vector_search": {
            key: value
            for key, value in env_vars.items()
            if key.startswith("VECTOR_SEARCH_") and value
        },
        "llm_providers": {
            key: value
            for key, value in env_vars.items()
            if (key.startswith("OPENAI_") or key.startswith("OLLAMA_")) and value
        },
        "development": {
            key: value
            for key, value in env_vars.items()
            if key in ["DEBUG_MODE", "DEVELOPMENT_MODE", "ENABLE_METRICS", "ENABLE_HEALTH_CHECKS"]
            and value
        },
        "metadata": {
            "total_variables": len([v for v in env_vars.values() if v]),
            "masked_count": len([v for v in env_vars.values() if "*" in str(v)]),
            "timestamp": _get_current_timestamp(),
        },
    }

    await ctx.info("Environment configuration retrieved successfully")
    return environment_config


async def get_api_status(ctx: Context) -> dict[str, Any]:
    """Get comprehensive Firecrawl API status information."""
    client = get_firecrawl_client()

    # Basic connection information
    connection_info = client.connection_info
    api_status = {
        "connection": {
            "status": "connected" if client.is_connected() else "disconnected",
            "api_url": connection_info.api_url,
            "api_key_masked": connection_info.api_key_masked,
            "timeout": connection_info.timeout,
            "max_retries": connection_info.max_retries,
            "backoff_factor": connection_info.backoff_factor,
            "last_error": connection_info.last_error,
        }
    }

    # Attempt validation if connected
    if client.is_connected():
        try:
            validation_result = client.validate_connection()
            api_status.update(
                {
                    "validation": {
                        "status": validation_result.get("status", "unknown"),
                        "connection_test": validation_result.get("connection_test", "unknown"),
                        "remaining_credits": validation_result.get("remaining_credits", "unknown"),
                        "last_validated": validation_result.get("timestamp", "unknown"),
                    }
                }
            )

            # Try to get additional API information
            try:
                credit_usage = client.client.get_credit_usage()
                api_status["credits"] = {
                    "remaining": getattr(credit_usage, "remaining", "unknown"),
                    "total": getattr(credit_usage, "total", "unknown"),
                    "used": getattr(credit_usage, "used", "unknown"),
                    "plan": getattr(credit_usage, "plan", "unknown"),
                }
            except Exception as credit_error:
                api_status["credits"] = {"error": str(credit_error), "status": "unavailable"}

        except MCPClientError as validation_error:
            api_status["validation"] = {
                "status": "failed",
                "error": str(validation_error),
                "connection_test": "failed",
            }
    else:
        api_status["validation"] = {
            "status": "not_connected",
            "error": "Client is not connected",
            "connection_test": "skipped",
        }

    # Add metadata
    api_status["metadata"] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "check_type": "comprehensive",
        "client_initialized": client._client is not None,
    }

    await ctx.info("API status retrieved successfully")
    return api_status


async def get_system_status(ctx: Context) -> dict[str, Any]:
    """Get comprehensive system status and health information."""
    # Get current process info
    process = psutil.Process()

    # Use cached system info that doesn't change frequently
    cached_info = _get_cached_system_info()

    # System information with real-time metrics
    system_info = {
        **cached_info,
        "cpu": {
            "count": psutil.cpu_count(),
            "usage_percent": psutil.cpu_percent(interval=1),
            "load_average": list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else None,
            "process_cpu_percent": process.cpu_percent(),
        },
        "memory": {
            "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
            "usage_percent": psutil.virtual_memory().percent,
            "process_memory_mb": round(process.memory_info().rss / (1024**2), 2),
            "process_memory_percent": process.memory_percent(),
        },
        "disk": {
            "total_gb": round(psutil.disk_usage("/").total / (1024**3), 2),
            "free_gb": round(psutil.disk_usage("/").free / (1024**3), 2),
            "used_gb": round(psutil.disk_usage("/").used / (1024**3), 2),
            "usage_percent": round(
                (psutil.disk_usage("/").used / psutil.disk_usage("/").total) * 100, 2
            ),
        },
        "process": {
            "pid": process.pid,
            "name": process.name(),
            "status": process.status(),
            "create_time": datetime.fromtimestamp(process.create_time(), tz=UTC).isoformat(),
            "num_threads": process.num_threads(),
            "num_fds": process.num_fds() if hasattr(process, "num_fds") else None,
            "connections": len(process.connections()) if hasattr(process, "connections") else None,
        },
        "network": {
            "connections": len(psutil.net_connections())
            if hasattr(psutil, "net_connections")
            else None,
            "interfaces": list(psutil.net_if_addrs().keys())
            if hasattr(psutil, "net_if_addrs")
            else [],
        },
    }

    # Health indicators
    health_status = "healthy"
    health_issues = []

    # Check for potential issues
    if system_info["cpu"]["usage_percent"] > 90:
        health_issues.append("High CPU usage")
        health_status = "warning"

    if system_info["memory"]["usage_percent"] > 90:
        health_issues.append("High memory usage")
        health_status = "warning"

    if system_info["disk"]["usage_percent"] > 90:
        health_issues.append("High disk usage")
        health_status = "warning"

    if system_info["process"]["num_threads"] > 100:
        health_issues.append("High thread count")
        health_status = "warning"

    # Critical issues
    if system_info["memory"]["usage_percent"] > 95:
        health_status = "critical"

    system_info["health"] = {
        "status": health_status,
        "issues": health_issues,
        "uptime_seconds": round(time.time() - process.create_time(), 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    await ctx.info("System status retrieved successfully")
    return system_info


async def get_server_status(ctx: Context) -> dict[str, Any]:
    """Get comprehensive MCP server status information."""
    server_status = {
        "server_info": {
            "name": _get_config_value("server_name"),
            "version": _get_config_value("server_version"),
            "host": _get_config_value("server_host"),
            "port": _get_config_value("server_port"),
            "ready": True,  # Simplified - server is ready if function is called
            "client_initialized": True,  # Simplified
        },
        "configuration": {
            "valid": _is_config_valid(),
            "environment": "development" if _get_config_value("development_mode") else "production",
            "debug_mode": _get_config_value("debug_mode"),
            "has_api_key": bool(_get_config_value("firecrawl_api_key")),
            "has_llm_provider": _has_llm_provider(),
            "preferred_llm": _get_llm_provider(),
        },
        "registered_components": {
            "tools": {
                "count": 0,  # Simplified - would need FastMCP instance access
                "names": [],
            },
            "resources": {
                "count": 0,  # Simplified - would need FastMCP instance access
                "names": [],
            },
            "prompts": {
                "count": 0,  # Simplified - would need FastMCP instance access
                "names": [],
            },
        },
        "features": {
            "auth_enabled": _get_config_value("auth_enabled"),
            "rate_limiting": _get_config_value("rate_limit_enabled"),
            "caching": _get_config_value("cache_enabled"),
            "vector_search": _get_config_value("vector_search_enabled"),
            "metrics": _get_config_value("enable_metrics"),
            "health_checks": _get_config_value("enable_health_checks"),
        },
        "client_status": {"connected": False, "error": None},
    }

    # Try to get client status
    try:
        client = get_firecrawl_client()
        client_status = client.get_status()
        server_status["client_status"] = {
            "connected": client_status.get("connection_available", False),
            "initialized": client_status.get("client_initialized", False),
            "api_url": client_status.get("api_url", "unknown"),
            "last_error": client_status.get("last_error"),
        }
    except Exception as client_error:
        server_status["client_status"] = {"connected": False, "error": str(client_error)}

    # Overall health assessment
    health_score = 0
    health_checks = {
        "server_ready": True,  # Simplified
        "config_valid": _is_config_valid(),
        "client_connected": server_status["client_status"]["connected"],
        "has_api_key": bool(_get_config_value("firecrawl_api_key")),
    }

    health_score = sum(health_checks.values())
    total_checks = len(health_checks)

    server_status["health"] = {
        "score": f"{health_score}/{total_checks}",
        "percentage": round((health_score / total_checks) * 100, 2),
        "status": "healthy"
        if health_score == total_checks
        else "degraded"
        if health_score >= total_checks * 0.5
        else "unhealthy",
        "checks": health_checks,
        "timestamp": _get_current_timestamp(),
    }

    await ctx.info("Server status retrieved successfully")
    return server_status


async def get_usage_statistics(ctx: Context) -> dict[str, Any]:
    """Get usage statistics and performance metrics."""

    # Basic usage statistics (placeholder implementation)
    # In production, this would integrate with metrics collection systems
    usage_stats = {
        "session": {
            "start_time": datetime.now(UTC).isoformat(),
            "uptime_seconds": 0,  # Would be calculated from actual start time
            "requests_processed": 0,  # Would come from metrics system
            "errors_encountered": 0,  # Would come from error tracking
            "average_response_time_ms": 0,  # Would come from timing middleware
        },
        "api_operations": {
            "scrape_requests": 0,
            "batch_scrape_requests": 0,
            "crawl_requests": 0,
            "extract_requests": 0,
            "map_requests": 0,
            "search_requests": 0,
            "vector_search_requests": 0,
        },
        "resource_access": {
            "config_requests": 0,
            "status_requests": 0,
            "health_checks": 0,
            "total_resource_requests": 0,
        },
        "performance": {
            "average_response_time_ms": 0,
            "fastest_response_ms": 0,
            "slowest_response_ms": 0,
            "timeout_count": 0,
            "retry_count": 0,
        },
        "rate_limiting": {
            "enabled": _get_config_value("rate_limit_enabled"),
            "requests_per_minute_limit": _get_config_value("rate_limit_requests_per_minute"),
            "requests_per_hour_limit": _get_config_value("rate_limit_requests_per_hour"),
            "current_minute_count": 0,
            "current_hour_count": 0,
            "rate_limited_requests": 0,
        },
        "cache": {
            "enabled": _get_config_value("cache_enabled"),
            "hit_count": 0,
            "miss_count": 0,
            "hit_ratio": 0.0,
            "eviction_count": 0,
            "current_size": 0,
            "max_size": _get_config_value("cache_max_size"),
        },
    }

    # Add metadata
    usage_stats["metadata"] = {
        "collection_method": "basic_implementation",
        "note": "This is a basic usage statistics implementation. Production deployments should integrate with proper metrics collection systems like Prometheus, StatsD, or custom analytics.",
        "timestamp": _get_current_timestamp(),
        "session_id": "static",  # Would be unique per session
        "version": _get_config_value("server_version"),
    }

    await ctx.info("Usage statistics retrieved successfully")
    return usage_stats


async def get_active_operations(ctx: Context) -> dict[str, Any]:
    """Get information about currently active operations."""

    # Basic active operations tracking (placeholder implementation)
    # In production, this would integrate with job queue systems
    active_operations: dict[str, Any] = {
        "batch_operations": {
            "active_count": 0,
            "queued_count": 0,
            "completed_today": 0,
            "failed_today": 0,
            "operations": [],  # List of active batch operations
        },
        "crawl_jobs": {
            "active_count": 0,
            "queued_count": 0,
            "completed_today": 0,
            "failed_today": 0,
            "jobs": [],  # List of active crawl jobs
        },
        "background_tasks": {
            "active_count": 0,
            "task_types": {},  # Count by task type
            "tasks": [],  # List of active background tasks
        },
        "api_requests": {
            "in_progress": 0,
            "queued": 0,
            "concurrent_limit": _get_config_value("rate_limit_burst_size"),
            "average_duration_ms": 0,
        },
        "system_tasks": {
            "health_checks": 0,
            "log_rotation": 0,
            "cache_cleanup": 0,
            "metrics_collection": 0,
        },
    }

    # Mock some data for demonstration (in production this would be real data)
    if _get_config_value("development_mode"):
        active_operations["demo_note"] = (
            "This is demonstration data. In production, this would show real active operations from job tracking systems."
        )

    # Add queue status information
    active_operations["queue_status"] = {
        "healthy": True,
        "processing_capacity": "normal",
        "estimated_wait_time_seconds": 0,
        "backlog_size": 0,
    }

    # Add metadata
    active_operations["metadata"] = {
        "collection_method": "basic_implementation",
        "note": "This is a basic active operations tracking implementation. Production deployments should integrate with proper job queue systems like Celery, RQ, or cloud job services.",
        "timestamp": _get_current_timestamp(),
        "refresh_interval_seconds": 30,
        "last_updated": _get_current_timestamp(),
    }

    await ctx.info("Active operations retrieved successfully")
    return active_operations


async def get_recent_logs(ctx: Context) -> dict[str, Any]:
    """Get recent log entries and error summaries."""

    # Initialize log data structure
    log_data: dict[str, Any] = {
        "log_files": {"main_log": None, "middleware_log": None, "error_log": None},
        "recent_entries": {"info": [], "warning": [], "error": [], "critical": []},
        "error_summary": {
            "total_errors": 0,
            "unique_errors": 0,
            "most_common_errors": [],
            "recent_error_trend": "stable",
        },
        "log_system_status": {
            "main_log_exists": False,
            "main_log_size_mb": 0,
            "middleware_log_exists": False,
            "middleware_log_size_mb": 0,
            "log_rotation_working": True,
            "disk_space_available": True,
        },
    }

    # Check for log files in the logs directory
    logs_dir = Path(__file__).parent.parent.parent / "logs"

    if logs_dir.exists():
        # Check main log file
        main_log_path = logs_dir / "firecrawler.log"
        if main_log_path.exists():
            log_data["log_system_status"]["main_log_exists"] = True
            log_data["log_system_status"]["main_log_size_mb"] = round(
                main_log_path.stat().st_size / (1024 * 1024), 2
            )
            log_data["log_files"]["main_log"] = str(main_log_path)

            # Read recent entries from main log (last 50 lines)
            try:
                with main_log_path.open(encoding="utf-8") as f:
                    lines = f.readlines()[-50:]  # Last 50 lines

                for raw_line in lines:
                    line = raw_line.strip()
                    if not line:
                        continue

                    # Basic log level detection
                    if " - ERROR - " in line:
                        log_data["recent_entries"]["error"].append(line)
                    elif " - WARNING - " in line:
                        log_data["recent_entries"]["warning"].append(line)
                    elif " - CRITICAL - " in line:
                        log_data["recent_entries"]["critical"].append(line)
                    elif " - INFO - " in line:
                        log_data["recent_entries"]["info"].append(
                            line[-200:]
                        )  # Truncate long info messages

            except Exception as read_error:
                log_data["log_files"]["main_log_error"] = str(read_error)

        # Check middleware log file
        middleware_log_path = logs_dir / "middleware.log"
        if middleware_log_path.exists():
            log_data["log_system_status"]["middleware_log_exists"] = True
            log_data["log_system_status"]["middleware_log_size_mb"] = round(
                middleware_log_path.stat().st_size / (1024 * 1024), 2
            )
            log_data["log_files"]["middleware_log"] = str(middleware_log_path)

    # Calculate error summary
    log_data["error_summary"]["total_errors"] = len(log_data["recent_entries"]["error"]) + len(
        log_data["recent_entries"]["critical"]
    )

    # Extract unique error patterns (basic implementation)
    error_messages = log_data["recent_entries"]["error"] + log_data["recent_entries"]["critical"]
    error_patterns: dict[str, int] = {}
    for error_msg in error_messages:
        # Extract error message after " - ERROR - " or " - CRITICAL - "
        if " - ERROR - " in error_msg:
            msg = error_msg.split(" - ERROR - ", 1)[1]
        elif " - CRITICAL - " in error_msg:
            msg = error_msg.split(" - CRITICAL - ", 1)[1]
        else:
            msg = error_msg

        # Take first 100 chars as pattern
        pattern = msg[:100] + "..." if len(msg) > 100 else msg
        error_patterns[pattern] = error_patterns.get(pattern, 0) + 1

    log_data["error_summary"]["unique_errors"] = len(error_patterns)
    log_data["error_summary"]["most_common_errors"] = [
        {"pattern": pattern, "count": count}
        for pattern, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Check disk space for logs directory
    if logs_dir.exists():
        try:
            statvfs = os.statvfs(str(logs_dir))
            free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
            log_data["log_system_status"]["disk_space_available"] = (
                free_space_gb > 1.0
            )  # At least 1GB free
            log_data["log_system_status"]["free_space_gb"] = round(free_space_gb, 2)
        except Exception:
            log_data["log_system_status"]["disk_space_available"] = None

    # Add metadata
    log_data["metadata"] = {
        "logs_directory": str(logs_dir),
        "log_level": _get_config_value("log_level"),
        "log_rotation_enabled": True,
        "max_log_size_mb": _get_config_value("log_max_size") // (1024 * 1024),
        "backup_count": _get_config_value("log_backup_count"),
        "timestamp": _get_current_timestamp(),
        "entries_limit": "Last 50 lines per log file",
    }

    await ctx.info("Recent logs retrieved successfully")
    return log_data


# Resource template functions
async def get_logs_by_level(level: str, ctx: Context) -> dict[str, Any]:
    """Get log entries filtered by specific log level."""
    if level.lower() not in ["info", "warning", "error", "critical"]:
        raise ResourceError(
            f"Invalid log level: {level}. Must be one of: info, warning, error, critical"
        )

    logs_dir = Path(__file__).parent.parent.parent / "logs"

    filtered_logs: dict[str, Any] = {
        "level": level.lower(),
        "entries": [],
        "count": 0,
        "metadata": {
            "timestamp": _get_current_timestamp(),
            "filter_applied": level.lower(),
            "source": "main log file",
        },
    }

    # Check for main log file
    main_log_path = logs_dir / "firecrawler.log"
    if main_log_path.exists():
        try:
            with main_log_path.open(encoding="utf-8") as f:
                lines = f.readlines()[-100:]  # Last 100 lines

            target_level = f" - {level.upper()} - "
            for raw_line in lines:
                line = raw_line.strip()
                if line and target_level in line:
                    filtered_logs["entries"].append(line)

            filtered_logs["count"] = len(filtered_logs["entries"])

        except Exception as read_error:
            raise ResourceError(f"Failed to read log file: {read_error}") from read_error
    else:
        filtered_logs["error"] = "Log file not found"

    await ctx.info(f"Filtered logs retrieved for level: {level}")
    return filtered_logs


async def get_component_status(component: str, ctx: Context) -> dict[str, Any]:
    """Get status for a specific server component."""
    component = component.lower()

    if component == "api":
        return await get_api_status(ctx)
    elif component == "system":
        return await get_system_status(ctx)
    elif component == "mcp":
        return await get_server_status(ctx)
    elif component == "cache":
        cache_status = {
            "component": "cache",
            "enabled": _get_config_value("cache_enabled"),
            "settings": {
                "ttl_seconds": _get_config_value("cache_ttl_seconds"),
                "max_size": _get_config_value("cache_max_size"),
            },
            "status": "enabled" if _get_config_value("cache_enabled") else "disabled",
            "timestamp": _get_current_timestamp(),
        }
        await ctx.info("Cache component status retrieved")
        return cache_status
    elif component == "auth":
        auth_status = {
            "component": "auth",
            "enabled": _get_config_value("auth_enabled"),
            "has_token": bool(os.getenv("AUTH_TOKEN")),
            "has_api_keys": bool(os.getenv("AUTH_API_KEYS")),
            "status": "enabled" if _get_config_value("auth_enabled") else "disabled",
            "timestamp": _get_current_timestamp(),
        }
        await ctx.info("Auth component status retrieved")
        return auth_status
    else:
        raise ResourceError(
            f"Unknown component: {component}. Available components: api, system, mcp, cache, auth"
        )


async def get_config_section(section: str, ctx: Context) -> dict[str, Any]:
    """Get specific configuration section."""
    section = section.lower()

    if section == "server":
        config_section = {
            "section": "server",
            "data": {
                "name": _get_config_value("server_name"),
                "version": _get_config_value("server_version"),
                "host": _get_config_value("server_host"),
                "port": _get_config_value("server_port"),
                "environment": "development" if _get_config_value("development_mode") else "production",
            },
            "timestamp": _get_current_timestamp(),
        }
    elif section == "api":
        config_section = {
            "section": "api",
            "data": {
                "base_url": _get_config_value("firecrawl_api_url"),
                "has_api_key": bool(_get_config_value("firecrawl_api_key")),
                "timeout": _get_config_value("firecrawl_timeout"),
                "max_retries": _get_config_value("firecrawl_max_retries"),
                "backoff_factor": _get_config_value("firecrawl_backoff_factor"),
            },
            "timestamp": _get_current_timestamp(),
        }
    elif section == "logging":
        config_section = {
            "section": "logging",
            "data": {
                "level": _get_config_value("log_level"),
                "format": _get_config_value("log_format"),
                "file": _get_config_value("log_file"),
                "max_size_mb": _get_config_value("log_max_size") // (1024 * 1024),
                "backup_count": _get_config_value("log_backup_count"),
            },
            "timestamp": _get_current_timestamp(),
        }
    elif section == "features":
        config_section = {
            "section": "features",
            "data": {
                "auth_enabled": _get_config_value("auth_enabled"),
                "rate_limit_enabled": _get_config_value("rate_limit_enabled"),
                "cache_enabled": _get_config_value("cache_enabled"),
                "vector_search_enabled": _get_config_value("vector_search_enabled"),
                "debug_mode": _get_config_value("debug_mode"),
                "metrics_enabled": _get_config_value("enable_metrics"),
                "health_checks_enabled": _get_config_value("enable_health_checks"),
            },
            "timestamp": _get_current_timestamp(),
        }
    elif section == "security":
        config_section = {
            "section": "security",
            "data": {
                "auth_enabled": _get_config_value("auth_enabled"),
                "rate_limiting": {
                    "enabled": _get_config_value("rate_limit_enabled"),
                    "requests_per_minute": _get_config_value("rate_limit_requests_per_minute"),
                    "requests_per_hour": _get_config_value("rate_limit_requests_per_hour"),
                    "burst_size": _get_config_value("rate_limit_burst_size"),
                },
                "has_auth_token": bool(os.getenv("AUTH_TOKEN")),
                "has_api_keys": bool(os.getenv("AUTH_API_KEYS")),
            },
            "timestamp": _get_current_timestamp(),
        }
    else:
        raise ResourceError(
            f"Unknown config section: {section}. Available sections: server, api, logging, features, security"
        )

    await ctx.info(f"Configuration section '{section}' retrieved successfully")
    return config_section


# Setup function to register all resources with FastMCP patterns
def setup_resources(server_mcp: FastMCP) -> None:
    """
    Setup all FastMCP resources using direct decoration patterns.

    This function registers all resources following FastMCP best practices with
    the provided server instance.

    Args:
        server_mcp: The FastMCP server instance to register resources with
    """
    # Static resources with FastMCP patterns
    server_mcp.resource(
        "firecrawl://config/server",
        name="Server Configuration",
        description="Current server configuration including environment variables, logging, and feature flags",
        mime_type="application/json",
        tags={"configuration", "server"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )(get_server_config)

    server_mcp.resource(
        "firecrawl://config/environment",
        name="Environment Variables",
        description="Environment variables and their masked values for configuration validation",
        mime_type="application/json",
        tags={"configuration", "environment"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )(get_environment_config)

    server_mcp.resource(
        "firecrawl://status/api",
        name="API Status",
        description="Firecrawl API connectivity status, authentication validation, and endpoint health",
        mime_type="application/json",
        tags={"status", "api", "connectivity"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,  # Status can change
        },
    )(get_api_status)

    server_mcp.resource(
        "firecrawl://status/system",
        name="System Status",
        description="Server system health including CPU, memory, disk usage, and Python runtime information",
        mime_type="application/json",
        tags={"status", "system", "health"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,  # System metrics change
        },
    )(get_system_status)

    server_mcp.resource(
        "firecrawl://status/mcp",
        name="Server Status",
        description="MCP server status including registered components, configuration validity, and readiness",
        mime_type="application/json",
        tags={"status", "server", "mcp"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,  # Server status can change
        },
    )(get_server_status)

    server_mcp.resource(
        "firecrawl://usage/statistics",
        name="Usage Statistics",
        description="Server usage statistics including operation counts and performance metrics",
        mime_type="application/json",
        tags={"usage", "statistics", "metrics"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,  # Statistics change over time
        },
    )(get_usage_statistics)

    server_mcp.resource(
        "firecrawl://operations/active",
        name="Active Operations",
        description="Currently active operations including batch jobs, crawls, and background tasks",
        mime_type="application/json",
        tags={"operations", "jobs", "active"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,  # Active operations change frequently
        },
    )(get_active_operations)

    server_mcp.resource(
        "firecrawl://logs/recent",
        name="Recent Logs",
        description="Recent log entries and error summaries for troubleshooting",
        mime_type="application/json",
        tags={"logs", "debugging", "errors"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False,  # Logs change frequently
        },
    )(get_recent_logs)

    # Resource templates with FastMCP patterns
    server_mcp.resource(
        "firecrawl://logs/{level}",
        name="Filtered Logs",
        description="Log entries filtered by specific log level (info, warning, error, critical)",
        mime_type="application/json",
        tags={"logs", "filtering", "debugging"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )(get_logs_by_level)

    server_mcp.resource(
        "firecrawl://status/{component}",
        name="Component Status",
        description="Status information for specific server component (api, system, mcp, cache, auth)",
        mime_type="application/json",
        tags={"status", "components"},
        annotations={"readOnlyHint": True, "idempotentHint": False},
    )(get_component_status)

    server_mcp.resource(
        "firecrawl://config/{section}",
        name="Configuration Section",
        description="Specific configuration section (server, api, logging, features, security)",
        mime_type="application/json",
        tags={"configuration", "sections"},
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )(get_config_section)

    logger.info("FastMCP-aligned resources setup completed successfully")


# Clean module interface
__all__ = [
    "get_active_operations",
    "get_api_status",
    "get_component_status",
    "get_config_section",
    "get_environment_config",
    "get_logs_by_level",
    "get_recent_logs",
    "get_server_config",
    "get_server_status",
    "get_system_status",
    "get_usage_statistics",
    "setup_resources",
]
