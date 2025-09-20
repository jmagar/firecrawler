"""
MCP Resources implementation for configuration and status information.

This module provides comprehensive MCP resources that expose server configuration,
API status, usage statistics, and operational information to MCP clients.
The resources follow FastMCP patterns and provide read-only access to system state.
"""

import logging
import os
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ResourceError

from ..core.client import get_firecrawl_client
from ..core.config import (
    get_env_bool,
    get_env_float,
    get_env_int,
    get_server_info,
    validate_environment,
)
from ..core.exceptions import MCPClientError, mcp_log_error

logger = logging.getLogger(__name__)


# Helper functions


def _mask_sensitive_value(value: str) -> str:
    """Mask sensitive values for display."""
    if not value or len(value) <= 8:
        return "<masked>" if value else ""
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


# Resource functions that can be registered with FastMCP server instances


async def get_server_config(ctx: Context) -> dict[str, Any]:
    """
    Get comprehensive server configuration information.

    Returns:
        Dictionary containing server configuration, environment settings,
        feature flags, and runtime parameters.
    """
    try:
        server_info = get_server_info()

        server_config = {
            "server_info": {
                "name": server_info["server_name"],
                "version": server_info["server_version"],
                "host": os.getenv("MCP_SERVER_HOST", "localhost"),
                "port": get_env_int("MCP_SERVER_PORT", 5100),
                "environment": "development" if server_info["development_mode"] else "production"
            },
            "api_configuration": {
                "base_url": server_info["api_url"],
                "has_api_key": server_info["api_key_configured"],
                "timeout": get_env_int("FIRECRAWL_TIMEOUT", 30),
                "max_retries": get_env_int("FIRECRAWL_MAX_RETRIES", 3),
                "backoff_factor": get_env_float("FIRECRAWL_BACKOFF_FACTOR", 2.0)
            },
            "feature_flags": {
                "auth_enabled": get_env_bool("AUTH_ENABLED"),
                "rate_limit_enabled": get_env_bool("RATE_LIMIT_ENABLED"),
                "cache_enabled": get_env_bool("CACHE_ENABLED"),
                "vector_search_enabled": get_env_bool("VECTOR_SEARCH_ENABLED"),
                "debug_mode": server_info["debug_mode"],
                "metrics_enabled": get_env_bool("ENABLE_METRICS"),
                "health_checks_enabled": get_env_bool("ENABLE_HEALTH_CHECKS")
            },
            "logging_config": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "format": os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
                "file": os.getenv("LOG_FILE", "firecrawler.log"),
                "max_size_mb": get_env_int("LOG_MAX_SIZE", 10485760) // (1024 * 1024),
                "backup_count": get_env_int("LOG_BACKUP_COUNT", 3)
            },
            "rate_limiting": {
                "enabled": get_env_bool("RATE_LIMIT_ENABLED"),
                "requests_per_minute": get_env_int("RATE_LIMIT_REQUESTS_PER_MINUTE", 60),
                "requests_per_hour": get_env_int("RATE_LIMIT_REQUESTS_PER_HOUR", 1000),
                "burst_size": get_env_int("RATE_LIMIT_BURST_SIZE", 10)
            },
            "llm_providers": {
                "available": [provider for provider in ["openai", "ollama"]
                            if (provider == "openai" and os.getenv("OPENAI_API_KEY")) or
                               (provider == "ollama" and os.getenv("OLLAMA_BASE_URL"))],
                "preferred": "openai" if os.getenv("OPENAI_API_KEY") else ("ollama" if os.getenv("OLLAMA_BASE_URL") else "none"),
                "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1:8b")
            },
            "cache_settings": {
                "enabled": get_env_bool("CACHE_ENABLED"),
                "ttl_seconds": get_env_int("CACHE_TTL_SECONDS", 3600),
                "max_size": get_env_int("CACHE_MAX_SIZE", 1000)
            },
            "vector_search": {
                "enabled": get_env_bool("VECTOR_SEARCH_ENABLED"),
                "threshold": get_env_float("VECTOR_SEARCH_THRESHOLD", 0.5),
                "default_limit": get_env_int("VECTOR_SEARCH_LIMIT", 10)
            },
            "timestamp": datetime.now(UTC).isoformat(),
            "config_valid": validate_environment()["valid"]
        }

        await ctx.info("Server configuration retrieved successfully")
        return server_config

    except Exception as e:
        error_msg = f"Failed to retrieve server configuration: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "server_config"})
        raise ResourceError(error_msg) from e


async def get_environment_config(ctx: Context) -> dict[str, Any]:
    """
    Get environment variable configuration with sensitive values masked.

    Returns:
        Dictionary containing environment variables relevant to Firecrawler MCP server
        with sensitive values appropriately masked for security.
    """
    try:
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
            "ENABLE_HEALTH_CHECKS": os.getenv("ENABLE_HEALTH_CHECKS", "")
        }

        # Filter out empty values and organize by category
        environment_config = {
            "firecrawl_api": {
                key: value for key, value in env_vars.items()
                if key.startswith("FIRECRAWL_") and value
            },
            "server": {
                key: value for key, value in env_vars.items()
                if key.startswith("MCP_SERVER_") and value
            },
            "logging": {
                key: value for key, value in env_vars.items()
                if key.startswith("LOG_") and value
            },
            "authentication": {
                key: value for key, value in env_vars.items()
                if key.startswith("AUTH_") and value
            },
            "rate_limiting": {
                key: value for key, value in env_vars.items()
                if key.startswith("RATE_LIMIT_") and value
            },
            "cache": {
                key: value for key, value in env_vars.items()
                if key.startswith("CACHE_") and value
            },
            "vector_search": {
                key: value for key, value in env_vars.items()
                if key.startswith("VECTOR_SEARCH_") and value
            },
            "llm_providers": {
                key: value for key, value in env_vars.items()
                if (key.startswith("OPENAI_") or key.startswith("OLLAMA_")) and value
            },
            "development": {
                key: value for key, value in env_vars.items()
                if key in ["DEBUG_MODE", "DEVELOPMENT_MODE", "ENABLE_METRICS", "ENABLE_HEALTH_CHECKS"] and value
            },
            "metadata": {
                "total_variables": len([v for v in env_vars.values() if v]),
                "masked_count": len([v for v in env_vars.values() if "*" in str(v)]),
                "timestamp": datetime.now(UTC).isoformat()
            }
        }

        await ctx.info("Environment configuration retrieved successfully")
        return environment_config

    except Exception as e:
        error_msg = f"Failed to retrieve environment configuration: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "environment_config"})
        raise ResourceError(error_msg) from e


async def get_api_status(ctx: Context) -> dict[str, Any]:
    """
    Get comprehensive Firecrawl API status information.

    Returns:
        Dictionary containing API connectivity status, authentication validation,
        credit information, and endpoint health details.
    """
    try:
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
                "last_error": connection_info.last_error
            }
        }

        # Attempt validation if connected
        if client.is_connected():
            try:
                validation_result = client.validate_connection()
                api_status.update({
                    "validation": {
                        "status": validation_result.get("status", "unknown"),
                        "connection_test": validation_result.get("connection_test", "unknown"),
                        "remaining_credits": validation_result.get("remaining_credits", "unknown"),
                        "last_validated": validation_result.get("timestamp", "unknown")
                    }
                })

                # Try to get additional API information
                try:
                    credit_usage = client.client.get_credit_usage()
                    api_status["credits"] = {
                        "remaining": getattr(credit_usage, "remaining", "unknown"),
                        "total": getattr(credit_usage, "total", "unknown"),
                        "used": getattr(credit_usage, "used", "unknown"),
                        "plan": getattr(credit_usage, "plan", "unknown")
                    }
                except Exception as credit_error:
                    api_status["credits"] = {
                        "error": str(credit_error),
                        "status": "unavailable"
                    }

            except MCPClientError as validation_error:
                api_status["validation"] = {
                    "status": "failed",
                    "error": str(validation_error),
                    "connection_test": "failed"
                }
        else:
            api_status["validation"] = {
                "status": "not_connected",
                "error": "Client is not connected",
                "connection_test": "skipped"
            }

        # Add metadata
        api_status["metadata"] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "check_type": "comprehensive",
            "client_initialized": client._client is not None
        }

        await ctx.info("API status retrieved successfully")
        return api_status

    except Exception as e:
        error_msg = f"Failed to retrieve API status: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "api_status"})

        # Return error status instead of raising exception
        return {
            "connection": {"status": "error", "error": str(e)},
            "validation": {"status": "failed", "error": str(e)},
            "metadata": {
                "timestamp": datetime.now(UTC).isoformat(),
                "check_type": "error_fallback"
            }
        }


async def get_system_status(ctx: Context) -> dict[str, Any]:
    """
    Get comprehensive system status and health information.

    Returns:
        Dictionary containing system metrics, resource usage, Python runtime
        information, and server health indicators.
    """
    try:
        # Get current process info
        process = psutil.Process()

        # System information
        system_info: dict[str, Any] = {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation()
            },
            "cpu": {
                "count": psutil.cpu_count(),
                "usage_percent": psutil.cpu_percent(interval=1),
                "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None,
                "process_cpu_percent": process.cpu_percent()
            },
            "memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                "usage_percent": psutil.virtual_memory().percent,
                "process_memory_mb": round(process.memory_info().rss / (1024**2), 2),
                "process_memory_percent": process.memory_percent()
            },
            "disk": {
                "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                "used_gb": round(psutil.disk_usage('/').used / (1024**3), 2),
                "usage_percent": round((psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100, 2)
            },
            "process": {
                "pid": process.pid,
                "name": process.name(),
                "status": process.status(),
                "create_time": datetime.fromtimestamp(process.create_time(), tz=UTC).isoformat(),
                "num_threads": process.num_threads(),
                "num_fds": process.num_fds() if hasattr(process, 'num_fds') else None,
                "connections": len(process.connections()) if hasattr(process, 'connections') else None
            },
            "network": {
                "connections": len(psutil.net_connections()) if hasattr(psutil, 'net_connections') else None,
                "interfaces": list(psutil.net_if_addrs().keys()) if hasattr(psutil, 'net_if_addrs') else []
            }
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
            "timestamp": datetime.now(UTC).isoformat()
        }

        await ctx.info("System status retrieved successfully")
        return system_info

    except Exception as e:
        error_msg = f"Failed to retrieve system status: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "system_status"})
        raise ResourceError(error_msg) from e


async def get_server_status(ctx: Context) -> dict[str, Any]:
    """
    Get comprehensive MCP server status information.

    Returns:
        Dictionary containing server status, registered components,
        configuration validity, and operational readiness.
    """
    try:
        server_info = get_server_info()
        validation_result = validate_environment()

        server_status = {
            "server_info": {
                "name": server_info["server_name"],
                "version": server_info["server_version"],
                "host": os.getenv("MCP_SERVER_HOST", "localhost"),
                "port": get_env_int("MCP_SERVER_PORT", 5100),
                "ready": True,  # Simplified - assume ready if we can get server info
                "client_initialized": True  # Simplified
            },
            "configuration": {
                "valid": validation_result["valid"],
                "environment": "development" if server_info["development_mode"] else "production",
                "debug_mode": server_info["debug_mode"],
                "has_api_key": server_info["api_key_configured"],
                "has_llm_provider": bool(os.getenv("OPENAI_API_KEY") or os.getenv("OLLAMA_BASE_URL")),
                "preferred_llm": "openai" if os.getenv("OPENAI_API_KEY") else ("ollama" if os.getenv("OLLAMA_BASE_URL") else "none")
            },
            "registered_components": {
                "tools": {
                    "count": 0,  # Simplified - not tracking in this backup version
                    "names": []
                },
                "resources": {
                    "count": 0,  # Simplified - not tracking in this backup version
                    "names": []
                },
                "prompts": {
                    "count": 0,  # Simplified - not tracking in this backup version
                    "names": []
                }
            },
            "features": {
                "auth_enabled": get_env_bool("AUTH_ENABLED"),
                "rate_limiting": get_env_bool("RATE_LIMIT_ENABLED"),
                "caching": get_env_bool("CACHE_ENABLED"),
                "vector_search": get_env_bool("VECTOR_SEARCH_ENABLED"),
                "metrics": get_env_bool("ENABLE_METRICS"),
                "health_checks": get_env_bool("ENABLE_HEALTH_CHECKS")
            },
            "client_status": {
                "connected": False,
                "error": None
            }
        }

        # Try to get client status
        try:
            client = get_firecrawl_client()
            client_status = client.get_status()
            server_status["client_status"] = {
                "connected": client_status.get("connection_available", False),
                "initialized": client_status.get("client_initialized", False),
                "api_url": client_status.get("api_url", "unknown"),
                "last_error": client_status.get("last_error")
            }
        except Exception as client_error:
            server_status["client_status"] = {
                "connected": False,
                "error": str(client_error)
            }

        # Overall health assessment
        health_score = 0
        health_checks = {
            "server_ready": True,  # Simplified - assume ready
            "config_valid": validation_result["valid"],
            "client_connected": server_status["client_status"]["connected"],
            "has_api_key": server_info["api_key_configured"]
        }

        health_score = sum(health_checks.values())
        total_checks = len(health_checks)

        server_status["health"] = {
            "score": f"{health_score}/{total_checks}",
            "percentage": round((health_score / total_checks) * 100, 2),
            "status": "healthy" if health_score == total_checks else "degraded" if health_score >= total_checks * 0.5 else "unhealthy",
            "checks": health_checks,
            "timestamp": datetime.now(UTC).isoformat()
        }

        await ctx.info("Server status retrieved successfully")
        return server_status

    except Exception as e:
        error_msg = f"Failed to retrieve server status: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "server_status"})
        raise ResourceError(error_msg) from e


async def get_usage_statistics(ctx: Context) -> dict[str, Any]:
    """
    Get usage statistics and performance metrics.

    Returns:
        Dictionary containing operation counts, performance metrics,
        and usage patterns. Note: This is a basic implementation;
        production deployments would integrate with proper metrics systems.
    """
    try:
        # Basic usage statistics (placeholder implementation)
        # In production, this would integrate with metrics collection systems
        usage_stats = {
            "session": {
                "start_time": datetime.now(UTC).isoformat(),
                "uptime_seconds": 0,  # Would be calculated from actual start time
                "requests_processed": 0,  # Would come from metrics system
                "errors_encountered": 0,  # Would come from error tracking
                "average_response_time_ms": 0  # Would come from timing middleware
            },
            "api_operations": {
                "scrape_requests": 0,
                "batch_scrape_requests": 0,
                "crawl_requests": 0,
                "extract_requests": 0,
                "map_requests": 0,
                "search_requests": 0,
                "vector_search_requests": 0
            },
            "resource_access": {
                "config_requests": 0,
                "status_requests": 0,
                "health_checks": 0,
                "total_resource_requests": 0
            },
            "performance": {
                "average_response_time_ms": 0,
                "fastest_response_ms": 0,
                "slowest_response_ms": 0,
                "timeout_count": 0,
                "retry_count": 0
            },
            "rate_limiting": {
                "enabled": get_env_bool("RATE_LIMIT_ENABLED"),
                "requests_per_minute_limit": get_env_int("RATE_LIMIT_REQUESTS_PER_MINUTE", 60),
                "requests_per_hour_limit": get_env_int("RATE_LIMIT_REQUESTS_PER_HOUR", 1000),
                "current_minute_count": 0,
                "current_hour_count": 0,
                "rate_limited_requests": 0
            },
            "cache": {
                "enabled": get_env_bool("CACHE_ENABLED"),
                "hit_count": 0,
                "miss_count": 0,
                "hit_ratio": 0.0,
                "eviction_count": 0,
                "current_size": 0,
                "max_size": get_env_int("CACHE_MAX_SIZE", 1000)
            }
        }

        # Add metadata
        usage_stats["metadata"] = {
            "collection_method": "basic_implementation",
            "note": "This is a basic usage statistics implementation. Production deployments should integrate with proper metrics collection systems like Prometheus, StatsD, or custom analytics.",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": "static",  # Would be unique per session
            "version": get_server_info()["server_version"]
        }

        await ctx.info("Usage statistics retrieved successfully")
        return usage_stats

    except Exception as e:
        error_msg = f"Failed to retrieve usage statistics: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "usage_statistics"})
        raise ResourceError(error_msg) from e


async def get_active_operations(ctx: Context) -> dict[str, Any]:
    """
    Get information about currently active operations.

    Returns:
        Dictionary containing active batch operations, crawl jobs,
        and other background tasks. Note: This is a basic implementation;
        production deployments would integrate with job tracking systems.
    """
    try:
        # Basic active operations tracking (placeholder implementation)
        # In production, this would integrate with job queue systems
        active_operations = {
            "batch_operations": {
                "active_count": 0,
                "queued_count": 0,
                "completed_today": 0,
                "failed_today": 0,
                "operations": []  # List of active batch operations
            },
            "crawl_jobs": {
                "active_count": 0,
                "queued_count": 0,
                "completed_today": 0,
                "failed_today": 0,
                "jobs": []  # List of active crawl jobs
            },
            "background_tasks": {
                "active_count": 0,
                "task_types": {},  # Count by task type
                "tasks": []  # List of active background tasks
            },
            "api_requests": {
                "in_progress": 0,
                "queued": 0,
                "concurrent_limit": get_env_int("RATE_LIMIT_BURST_SIZE", 10),
                "average_duration_ms": 0
            },
            "system_tasks": {
                "health_checks": 0,
                "log_rotation": 0,
                "cache_cleanup": 0,
                "metrics_collection": 0
            }
        }

        # Mock some data for demonstration (in production this would be real data)
        if get_env_bool("DEVELOPMENT_MODE"):
            active_operations["demo_note"] = "This is demonstration data. In production, this would show real active operations from job tracking systems."

        # Add queue status information
        active_operations["queue_status"] = {
            "healthy": True,
            "processing_capacity": "normal",
            "estimated_wait_time_seconds": 0,
            "backlog_size": 0
        }

        # Add metadata
        active_operations["metadata"] = {
            "collection_method": "basic_implementation",
            "note": "This is a basic active operations tracking implementation. Production deployments should integrate with proper job queue systems like Celery, RQ, or cloud job services.",
            "timestamp": datetime.now(UTC).isoformat(),
            "refresh_interval_seconds": 30,
            "last_updated": datetime.now(UTC).isoformat()
        }

        await ctx.info("Active operations retrieved successfully")
        return active_operations

    except Exception as e:
        error_msg = f"Failed to retrieve active operations: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "active_operations"})
        raise ResourceError(error_msg) from e


async def get_recent_logs(ctx: Context) -> dict[str, Any]:
    """
    Get recent log entries and error summaries.

    Returns:
        Dictionary containing recent log entries, error summaries,
        and logging system status for troubleshooting purposes.
    """
    try:
        # Initialize log data structure
        log_data: dict[str, Any] = {
            "log_files": {
                "main_log": None,
                "middleware_log": None,
                "error_log": None
            },
            "recent_entries": {
                "info": [],
                "warning": [],
                "error": [],
                "critical": []
            },
            "error_summary": {
                "total_errors": 0,
                "unique_errors": 0,
                "most_common_errors": [],
                "recent_error_trend": "stable"
            },
            "log_system_status": {
                "main_log_exists": False,
                "main_log_size_mb": 0,
                "middleware_log_exists": False,
                "middleware_log_size_mb": 0,
                "log_rotation_working": True,
                "disk_space_available": True
            }
        }

        # Check for log files in the logs directory
        logs_dir = Path(__file__).parent.parent.parent / "logs"

        if logs_dir.exists():
            # Check main log file
            main_log_path = logs_dir / "firecrawler.log"
            if main_log_path.exists():
                log_data["log_system_status"]["main_log_exists"] = True
                log_data["log_system_status"]["main_log_size_mb"] = round(main_log_path.stat().st_size / (1024 * 1024), 2)
                log_data["log_files"]["main_log"] = str(main_log_path)

                # Read recent entries from main log (last 50 lines)
                try:
                    with main_log_path.open(encoding='utf-8') as f:
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
                            log_data["recent_entries"]["info"].append(line[-200:])  # Truncate long info messages

                except Exception as read_error:
                    log_data["log_files"]["main_log_error"] = str(read_error)

            # Check middleware log file
            middleware_log_path = logs_dir / "middleware.log"
            if middleware_log_path.exists():
                log_data["log_system_status"]["middleware_log_exists"] = True
                log_data["log_system_status"]["middleware_log_size_mb"] = round(middleware_log_path.stat().st_size / (1024 * 1024), 2)
                log_data["log_files"]["middleware_log"] = str(middleware_log_path)

        # Calculate error summary
        log_data["error_summary"]["total_errors"] = len(log_data["recent_entries"]["error"]) + len(log_data["recent_entries"]["critical"])

        # Extract unique error patterns (basic implementation)
        error_messages = log_data["recent_entries"]["error"] + log_data["recent_entries"]["critical"]
        error_patterns: dict[str, int] = {}
        for error in error_messages:
            # Extract error message after " - ERROR - " or " - CRITICAL - "
            if " - ERROR - " in error:
                msg = error.split(" - ERROR - ", 1)[1]
            elif " - CRITICAL - " in error:
                msg = error.split(" - CRITICAL - ", 1)[1]
            else:
                msg = error

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
                log_data["log_system_status"]["disk_space_available"] = free_space_gb > 1.0  # At least 1GB free
                log_data["log_system_status"]["free_space_gb"] = round(free_space_gb, 2)
            except Exception:
                log_data["log_system_status"]["disk_space_available"] = None

        # Add metadata
        log_data["metadata"] = {
            "logs_directory": str(logs_dir),
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "log_rotation_enabled": True,
            "max_log_size_mb": get_env_int("LOG_MAX_SIZE", 10485760) // (1024 * 1024),
            "backup_count": get_env_int("LOG_BACKUP_COUNT", 3),
            "timestamp": datetime.now(UTC).isoformat(),
            "entries_limit": "Last 50 lines per log file"
        }

        await ctx.info("Recent logs retrieved successfully")
        return log_data

    except Exception as e:
        error_msg = f"Failed to retrieve recent logs: {e}"
        await ctx.error(error_msg)
        mcp_log_error(e, {"resource": "recent_logs"})
        raise ResourceError(error_msg) from e


# Resource registration helper function
def register_resources(server_mcp: FastMCP) -> None:
    """
    Register all resources with the provided FastMCP server instance.

    Args:
        server_mcp: The FastMCP server instance to register resources with
    """
    # Register each resource function with the server

    @server_mcp.resource(
        "firecrawl://config/server",
        name="Server Configuration",
        description="Current server configuration including environment variables, logging, and feature flags",
        mime_type="application/json",
        tags={"configuration", "server"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True
        }
    )
    async def _server_config(ctx: Context) -> dict[str, Any]:
        return await get_server_config(ctx)

    @server_mcp.resource(
        "firecrawl://config/environment",
        name="Environment Variables",
        description="Environment variables and their masked values for configuration validation",
        mime_type="application/json",
        tags={"configuration", "environment"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True
        }
    )
    async def _environment_config(ctx: Context) -> dict[str, Any]:
        return await get_environment_config(ctx)

    @server_mcp.resource(
        "firecrawl://status/api",
        name="API Status",
        description="Firecrawl API connectivity status, authentication validation, and endpoint health",
        mime_type="application/json",
        tags={"status", "api", "connectivity"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False  # Status can change
        }
    )
    async def _api_status(ctx: Context) -> dict[str, Any]:
        return await get_api_status(ctx)

    @server_mcp.resource(
        "firecrawl://status/system",
        name="System Status",
        description="Server system health including CPU, memory, disk usage, and Python runtime information",
        mime_type="application/json",
        tags={"status", "system", "health"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False  # System metrics change
        }
    )
    async def _system_status(ctx: Context) -> dict[str, Any]:
        return await get_system_status(ctx)

    @server_mcp.resource(
        "firecrawl://status/mcp",
        name="Server Status",
        description="MCP server status including registered components, configuration validity, and readiness",
        mime_type="application/json",
        tags={"status", "server", "mcp"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False  # Server status can change
        }
    )
    async def _server_status(ctx: Context) -> dict[str, Any]:
        return await get_server_status(ctx)

    @server_mcp.resource(
        "firecrawl://usage/statistics",
        name="Usage Statistics",
        description="Server usage statistics including operation counts and performance metrics",
        mime_type="application/json",
        tags={"usage", "statistics", "metrics"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False  # Statistics change over time
        }
    )
    async def _usage_statistics(ctx: Context) -> dict[str, Any]:
        return await get_usage_statistics(ctx)

    @server_mcp.resource(
        "firecrawl://operations/active",
        name="Active Operations",
        description="Currently active operations including batch jobs, crawls, and background tasks",
        mime_type="application/json",
        tags={"operations", "jobs", "active"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False  # Active operations change frequently
        }
    )
    async def _active_operations(ctx: Context) -> dict[str, Any]:
        return await get_active_operations(ctx)

    @server_mcp.resource(
        "firecrawl://logs/recent",
        name="Recent Logs",
        description="Recent log entries and error summaries for troubleshooting",
        mime_type="application/json",
        tags={"logs", "debugging", "errors"},
        annotations={
            "readOnlyHint": True,
            "idempotentHint": False  # Logs change frequently
        }
    )
    async def _recent_logs(ctx: Context) -> dict[str, Any]:
        return await get_recent_logs(ctx)

    logger.info("All Firecrawler MCP resources registered successfully")


# Export the resource functions for external use
__all__ = [
    "get_active_operations",
    "get_api_status",
    "get_environment_config",
    "get_recent_logs",
    "get_server_config",
    "get_server_status",
    "get_system_status",
    "get_usage_statistics",
    "register_resources"
]
