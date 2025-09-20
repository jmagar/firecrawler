"""
FastMCP-compatible Firecrawl client utilities.

This module provides Context-based client access following FastMCP patterns,
replacing the previous global singleton approach.
"""

import logging
import os
from typing import Any

from fastmcp.exceptions import ToolError
from firecrawl.v2.client import FirecrawlClient
from firecrawl.v2.utils.error_handler import FirecrawlError

logger = logging.getLogger(__name__)


def get_firecrawl_client() -> FirecrawlClient:
    """
    Create a Firecrawl client using environment variables.

    Uses FastMCP's environment variable pattern instead of global singletons.
    This function creates a new client each time it's called, following
    FastMCP's stateless patterns.

    Returns:
        FirecrawlClient: Configured Firecrawl client

    Raises:
        ToolError: If client cannot be created or configuration is invalid
    """
    try:
        # Get configuration from environment variables
        api_key = os.getenv("FIRECRAWL_API_KEY")
        api_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")

        # Check if this is a self-hosted instance (no API key required)
        is_self_hosted = not api_url.startswith("https://api.firecrawl.dev")

        if not api_key and not is_self_hosted:
            raise ToolError(
                "FIRECRAWL_API_KEY environment variable is required for cloud API. "
                "Please configure your API key or use FIRECRAWL_API_URL for self-hosted instances."
            )

        # Parse optional numeric configuration
        timeout = None
        max_retries = 3
        backoff_factor = 0.5

        try:
            if timeout_str := os.getenv("FIRECRAWL_TIMEOUT"):
                timeout = float(timeout_str)
        except ValueError:
            logger.warning(f"Invalid FIRECRAWL_TIMEOUT value: {timeout_str}, using default")

        try:
            if retries_str := os.getenv("FIRECRAWL_MAX_RETRIES"):
                max_retries = int(retries_str)
        except ValueError:
            logger.warning(f"Invalid FIRECRAWL_MAX_RETRIES value: {retries_str}, using default")

        try:
            if backoff_str := os.getenv("FIRECRAWL_BACKOFF_FACTOR"):
                backoff_factor = float(backoff_str)
        except ValueError:
            logger.warning(f"Invalid FIRECRAWL_BACKOFF_FACTOR value: {backoff_str}, using default")

        # Create and return client
        # For self-hosted instances, use a dummy API key if none provided
        if is_self_hosted and not api_key:
            api_key = "dummy-key-for-self-hosted"

        client = FirecrawlClient(
            api_key=api_key,
            api_url=api_url,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )

        logger.debug(f"Created Firecrawl client for {api_url}")
        return client

    except FirecrawlError as e:
        error_msg = f"Failed to create Firecrawl client: {e}"
        logger.error(error_msg)
        raise ToolError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error creating Firecrawl client: {e}"
        logger.error(error_msg)
        raise ToolError(error_msg) from e


def get_client_status() -> dict[str, Any]:
    """
    Get Firecrawl client connection status with self-hosted support.

    Uses different health check approaches based on the target API:
    - Cloud instances: Use credit usage check
    - Self-hosted instances: Use alternative connectivity tests

    Returns:
        Dict containing connection status and configuration info

    Raises:
        ToolError: If status check fails
    """
    try:
        client = get_firecrawl_client()

        # Determine if this is likely a self-hosted instance
        # Check both FIRECRAWL_API_URL and FIRECRAWL_BASE_API (for compatibility)
        api_url = os.getenv("FIRECRAWL_API_URL") or os.getenv(
            "FIRECRAWL_BASE_API", "https://api.firecrawl.dev"
        )
        # Handle potential None case even though we have a fallback
        if api_url is None:
            api_url = "https://api.firecrawl.dev"
        is_likely_self_hosted = not api_url.startswith("https://api.firecrawl.dev")

        # Initialize result values
        connection_test = "failed"
        remaining_credits = "unknown"

        if is_likely_self_hosted:
            # For self-hosted instances, try alternative health checks
            try:
                # Approach 1: Try concurrency check (lighter than credit usage)
                client.get_concurrency()
                connection_test = "passed"
                logger.debug("Self-hosted health check passed via concurrency endpoint")
            except Exception as concurrency_error:
                logger.debug(f"Concurrency check failed: {concurrency_error}")

                # Approach 2: Try a validation check with invalid data
                # This should fail with a validation error, not auth error
                try:
                    client.scrape("invalid-url")
                except Exception as scrape_error:
                    error_str = str(scrape_error).lower()
                    if any(
                        term in error_str for term in ["invalid url", "validation", "bad request"]
                    ):
                        connection_test = "passed"
                        logger.debug("Self-hosted health check passed via validation test")
                    else:
                        connection_test = f"failed: {scrape_error}"
                        logger.warning(f"Self-hosted health check failed: {scrape_error}")
        else:
            # For cloud instances, use credit usage check
            try:
                credit_usage = client.get_credit_usage()
                remaining_credits = getattr(credit_usage, "remaining", "unknown")
                connection_test = "passed"
                logger.debug("Cloud health check passed via credit usage")
            except Exception as credit_error:
                connection_test = f"failed: {credit_error}"
                logger.warning(f"Cloud health check failed: {credit_error}")

        return {
            "status": "connected" if connection_test == "passed" else "error",
            "api_url": api_url,
            "api_key_configured": bool(os.getenv("FIRECRAWL_API_KEY")),
            "is_likely_self_hosted": is_likely_self_hosted,
            "remaining_credits": remaining_credits,
            "connection_test": connection_test,
        }

    except Exception as e:
        logger.error(f"Client status check failed: {e}")
        raise ToolError(f"Failed to get client status: {e}") from e


# Backward compatibility functions - these will be deprecated
def get_client() -> FirecrawlClient:
    """
    DEPRECATED: Get Firecrawl client using old pattern.

    This function exists for backward compatibility but should be replaced
    with get_firecrawl_client() in new code.
    """
    logger.warning("get_client() is deprecated, use get_firecrawl_client() instead")
    return get_firecrawl_client()


def initialize_client(config: dict[str, Any] | None = None) -> FirecrawlClient:  # noqa: ARG001
    """
    DEPRECATED: Initialize client with config.

    This function exists for backward compatibility but should be replaced
    with direct calls to get_firecrawl_client() in new code.
    """
    logger.warning("initialize_client() is deprecated, use get_firecrawl_client() instead")
    return get_firecrawl_client()


def reset_client() -> None:
    """
    DEPRECATED: Reset global client.

    No-op function for backward compatibility. The new stateless approach
    doesn't require client reset.
    """
    logger.warning("reset_client() is deprecated and has no effect in stateless mode")
    pass
