"""
Tests for resource access and content validation.

This module provides comprehensive testing for MCP resources including
configuration access, status information, content validation, error handling,
and integration with FastMCP resource system.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import Client, Context, FastMCP
from fastmcp.exceptions import ResourceError
from firecrawl.v2.client import FirecrawlClient

from firecrawl_mcp.core.config import MCPConfig
from firecrawl_mcp.resources.resources import (
    get_active_operations,
    get_api_status,
    get_environment_config,
    get_recent_logs,
    get_server_config,
    get_server_status,
    get_system_status,
    get_usage_statistics,
    setup_resources,
)


class TestServerConfigResource:
    """Test server configuration resource functionality."""

    @patch("firecrawl_mcp.resources.resources.load_config")
    async def test_get_server_config_success(self, mock_load_config: Mock) -> None:
        """Test successful retrieval of server configuration."""
        # Mock configuration
        mock_config = Mock(spec=MCPConfig)
        mock_config.server_name = "Test Server"
        mock_config.server_version = "1.0.0"
        mock_config.server_host = "localhost"
        mock_config.server_port = 8080
        mock_config.development_mode = True
        mock_config.firecrawl_api_url = "https://api.firecrawl.dev"
        mock_config.firecrawl_api_key = "test-key"
        mock_config.firecrawl_timeout = 30.0
        mock_config.firecrawl_max_retries = 3
        mock_config.firecrawl_backoff_factor = 0.5
        mock_config.auth_enabled = False
        mock_config.rate_limit_enabled = False
        mock_config.cache_enabled = True
        mock_config.vector_search_enabled = True
        mock_config.debug_mode = True
        mock_config.enable_metrics = True
        mock_config.enable_health_checks = True
        mock_config.log_level = "DEBUG"
        mock_config.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        mock_config.log_file = "firecrawler.log"
        mock_config.log_max_size = 10485760  # 10MB
        mock_config.log_backup_count = 5
        mock_config.rate_limit_requests_per_minute = 60
        mock_config.rate_limit_requests_per_hour = 1000
        mock_config.rate_limit_burst_size = 10
        mock_config.cache_ttl_seconds = 3600
        mock_config.cache_max_size = 1000
        mock_config.vector_search_threshold = 0.7
        mock_config.vector_search_limit = 10
        mock_config.openai_model = "gpt-4"
        mock_config.ollama_model = "llama2"
        mock_config.get_llm_provider.return_value = "openai"
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"
        mock_config.is_valid.return_value = True

        mock_load_config.return_value = mock_config

        # Mock context
        mock_ctx = AsyncMock()

        # Test the function
        result = await get_server_config(mock_ctx)

        # Verify structure and content
        assert isinstance(result, dict)
        assert "server_info" in result
        assert "api_configuration" in result
        assert "feature_flags" in result
        assert "logging_config" in result
        assert "rate_limiting" in result
        assert "llm_providers" in result
        assert "cache_settings" in result
        assert "vector_search" in result
        assert "timestamp" in result
        assert "config_valid" in result

        # Verify server info
        assert result["server_info"]["name"] == "Test Server"
        assert result["server_info"]["version"] == "1.0.0"
        assert result["server_info"]["environment"] == "development"

        # Verify API configuration
        assert result["api_configuration"]["base_url"] == "https://api.firecrawl.dev"
        assert result["api_configuration"]["has_api_key"] is True
        assert result["api_configuration"]["timeout"] == 30.0

        # Verify feature flags
        assert result["feature_flags"]["auth_enabled"] is False
        assert result["feature_flags"]["vector_search_enabled"] is True

        # Verify context logging
        mock_ctx.info.assert_called_once_with("Server configuration retrieved successfully")

    @patch("firecrawl_mcp.resources.resources.load_config")
    async def test_get_server_config_error(self, mock_load_config: Mock) -> None:
        """Test error handling in server configuration retrieval."""
        mock_load_config.side_effect = Exception("Configuration error")

        mock_ctx = AsyncMock()

        with pytest.raises(ResourceError, match="Failed to retrieve server configuration"):
            await get_server_config(mock_ctx)

        mock_ctx.error.assert_called_once()


class TestEnvironmentConfigResource:
    """Test environment configuration resource functionality."""

    @patch("firecrawl_mcp.resources.resources.load_config")
    @patch.dict(os.environ, {
        "FIRECRAWL_API_KEY": "secret-key",
        "FIRECRAWL_API_URL": "https://api.firecrawl.dev",
        "MCP_SERVER_NAME": "Test Server",
        "LOG_LEVEL": "DEBUG",
        "AUTH_ENABLED": "false",
        "OPENAI_API_KEY": "openai-secret"
    })
    async def test_get_environment_config_success(self, mock_load_config: Mock) -> None:
        """Test successful retrieval of environment configuration."""
        # Mock configuration with masking method
        mock_config = Mock(spec=MCPConfig)
        mock_config._mask_sensitive_value.side_effect = lambda x: "***masked***" if x else ""
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_load_config.return_value = mock_config

        mock_ctx = AsyncMock()

        result = await get_environment_config(mock_ctx)

        # Verify structure
        assert isinstance(result, dict)
        assert "firecrawl_api" in result
        assert "server" in result
        assert "logging" in result
        assert "authentication" in result
        assert "llm_providers" in result
        assert "metadata" in result

        # Verify that sensitive values are masked
        assert result["firecrawl_api"]["FIRECRAWL_API_KEY"] == "***masked***"
        assert result["llm_providers"]["OPENAI_API_KEY"] == "***masked***"

        # Verify that non-sensitive values are preserved
        assert result["firecrawl_api"]["FIRECRAWL_API_URL"] == "https://api.firecrawl.dev"
        assert result["server"]["MCP_SERVER_NAME"] == "Test Server"

        # Verify metadata
        assert "total_variables" in result["metadata"]
        assert "masked_count" in result["metadata"]

        mock_ctx.info.assert_called_once_with("Environment configuration retrieved successfully")

    @patch("firecrawl_mcp.resources.resources.load_config")
    async def test_get_environment_config_error(self, mock_load_config: Mock) -> None:
        """Test error handling in environment configuration retrieval."""
        mock_load_config.side_effect = Exception("Environment error")

        mock_ctx = AsyncMock()

        with pytest.raises(ResourceError, match="Failed to retrieve environment configuration"):
            await get_environment_config(mock_ctx)

        mock_ctx.error.assert_called_once()


class TestApiStatusResource:
    """Test API status resource functionality."""

    @patch("firecrawl_mcp.resources.resources.get_client")
    async def test_get_api_status_success(self, mock_get_client: Mock) -> None:
        """Test successful retrieval of API status."""
        # Mock client with connection info
        mock_client = Mock(spec=FirecrawlClient)
        mock_client.is_connected.return_value = True

        # Mock connection info
        mock_connection_info = Mock()
        mock_connection_info.api_url = "https://api.firecrawl.dev"
        mock_connection_info.api_key_masked = "fc-***masked***"
        mock_connection_info.timeout = 30.0
        mock_connection_info.max_retries = 3
        mock_connection_info.backoff_factor = 0.5
        mock_connection_info.last_error = None
        mock_client.connection_info = mock_connection_info

        # Mock validation result
        mock_client.validate_connection.return_value = {
            "status": "success",
            "connection_test": "passed",
            "remaining_credits": 1000,
            "timestamp": "2024-01-01T00:00:00Z"
        }

        # Mock credit usage
        mock_credit_usage = Mock()
        mock_credit_usage.remaining = 1000
        mock_credit_usage.total = 2000
        mock_credit_usage.used = 1000
        mock_credit_usage.plan = "pro"
        mock_client.client.get_credit_usage.return_value = mock_credit_usage

        mock_get_client.return_value = mock_client

        mock_ctx = AsyncMock()

        result = await get_api_status(mock_ctx)

        # Verify structure and content
        assert isinstance(result, dict)
        assert "connection" in result
        assert "validation" in result
        assert "credits" in result
        assert "metadata" in result

        # Verify connection info
        assert result["connection"]["status"] == "connected"
        assert result["connection"]["api_url"] == "https://api.firecrawl.dev"
        assert result["connection"]["api_key_masked"] == "fc-***masked***"

        # Verify validation info
        assert result["validation"]["status"] == "success"
        assert result["validation"]["connection_test"] == "passed"
        assert result["validation"]["remaining_credits"] == 1000

        # Verify credits info
        assert result["credits"]["remaining"] == 1000
        assert result["credits"]["total"] == 2000
        assert result["credits"]["used"] == 1000
        assert result["credits"]["plan"] == "pro"

        mock_ctx.info.assert_called_once_with("API status retrieved successfully")

    @patch("firecrawl_mcp.resources.resources.get_client")
    async def test_get_api_status_disconnected(self, mock_get_client: Mock) -> None:
        """Test API status when client is disconnected."""
        mock_client = Mock(spec=FirecrawlClient)
        mock_client.is_connected.return_value = False

        mock_connection_info = Mock()
        mock_connection_info.api_url = "https://api.firecrawl.dev"
        mock_connection_info.api_key_masked = "fc-***masked***"
        mock_connection_info.timeout = 30.0
        mock_connection_info.max_retries = 3
        mock_connection_info.backoff_factor = 0.5
        mock_connection_info.last_error = "Connection timeout"
        mock_client.connection_info = mock_connection_info

        mock_get_client.return_value = mock_client

        mock_ctx = AsyncMock()

        result = await get_api_status(mock_ctx)

        assert result["connection"]["status"] == "disconnected"
        assert result["validation"]["status"] == "not_connected"
        assert result["validation"]["error"] == "Client is not connected"

    @patch("firecrawl_mcp.resources.resources.get_client")
    async def test_get_api_status_error_fallback(self, mock_get_client: Mock) -> None:
        """Test API status error fallback behavior."""
        mock_get_client.side_effect = Exception("Client initialization failed")

        mock_ctx = AsyncMock()

        # Should not raise exception, should return error status
        result = await get_api_status(mock_ctx)

        assert result["connection"]["status"] == "error"
        assert "Client initialization failed" in result["connection"]["error"]
        assert result["validation"]["status"] == "failed"


class TestSystemStatusResource:
    """Test system status resource functionality."""

    @patch("firecrawl_mcp.resources.resources.psutil")
    @patch("firecrawl_mcp.resources.resources.platform")
    async def test_get_system_status_success(self, mock_platform: Mock, mock_psutil: Mock) -> None:
        """Test successful retrieval of system status."""
        # Mock platform information
        mock_platform.system.return_value = "Linux"
        mock_platform.release.return_value = "5.4.0"
        mock_platform.version.return_value = "#1 SMP Ubuntu"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.processor.return_value = "Intel64"
        mock_platform.python_version.return_value = "3.11.0"
        mock_platform.python_implementation.return_value = "CPython"

        # Mock psutil system information
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_percent.return_value = 25.5
        mock_psutil.getloadavg.return_value = [1.0, 1.5, 2.0]

        # Mock memory information
        mock_virtual_memory = Mock()
        mock_virtual_memory.total = 8589934592  # 8GB
        mock_virtual_memory.available = 4294967296  # 4GB
        mock_virtual_memory.used = 4294967296  # 4GB
        mock_virtual_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_virtual_memory

        # Mock disk information
        mock_disk_usage = Mock()
        mock_disk_usage.total = 107374182400  # 100GB
        mock_disk_usage.free = 53687091200   # 50GB
        mock_disk_usage.used = 53687091200   # 50GB
        mock_psutil.disk_usage.return_value = mock_disk_usage

        # Mock process information
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.name.return_value = "python"
        mock_process.status.return_value = "running"
        mock_process.create_time.return_value = 1704067200  # 2024-01-01 00:00:00
        mock_process.num_threads.return_value = 8
        mock_process.num_fds.return_value = 25
        mock_process.connections.return_value = [Mock(), Mock()]  # 2 connections
        mock_process.cpu_percent.return_value = 5.0

        # Mock memory info for process
        mock_memory_info = Mock()
        mock_memory_info.rss = 104857600  # 100MB
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.memory_percent.return_value = 1.25

        mock_psutil.Process.return_value = mock_process

        # Mock network information
        mock_psutil.net_connections.return_value = [Mock() for _ in range(10)]
        mock_psutil.net_if_addrs.return_value = {"eth0": Mock(), "lo": Mock()}

        mock_ctx = AsyncMock()

        result = await get_system_status(mock_ctx)

        # Verify structure and content
        assert isinstance(result, dict)
        assert "platform" in result
        assert "cpu" in result
        assert "memory" in result
        assert "disk" in result
        assert "process" in result
        assert "network" in result
        assert "health" in result

        # Verify platform info
        assert result["platform"]["system"] == "Linux"
        assert result["platform"]["python_version"] == "3.11.0"

        # Verify CPU info
        assert result["cpu"]["count"] == 4
        assert result["cpu"]["usage_percent"] == 25.5
        assert result["cpu"]["process_cpu_percent"] == 5.0

        # Verify memory info
        assert result["memory"]["total_gb"] == 8.0
        assert result["memory"]["available_gb"] == 4.0
        assert result["memory"]["usage_percent"] == 50.0
        assert result["memory"]["process_memory_mb"] == 100.0

        # Verify disk info
        assert result["disk"]["total_gb"] == 100.0
        assert result["disk"]["free_gb"] == 50.0
        assert result["disk"]["usage_percent"] == 50.0

        # Verify process info
        assert result["process"]["pid"] == 12345
        assert result["process"]["name"] == "python"
        assert result["process"]["status"] == "running"
        assert result["process"]["num_threads"] == 8

        # Verify health assessment
        assert result["health"]["status"] == "healthy"
        assert result["health"]["issues"] == []

        mock_ctx.info.assert_called_once_with("System status retrieved successfully")

    @patch("firecrawl_mcp.resources.resources.psutil")
    async def test_get_system_status_high_usage_warning(self, mock_psutil: Mock) -> None:
        """Test system status with high resource usage warnings."""
        # Mock high CPU usage
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_percent.return_value = 95.0  # High CPU

        # Mock high memory usage
        mock_virtual_memory = Mock()
        mock_virtual_memory.total = 8589934592
        mock_virtual_memory.available = 429496729  # Low available
        mock_virtual_memory.used = 8160437863  # High used
        mock_virtual_memory.percent = 95.0  # High percentage
        mock_psutil.virtual_memory.return_value = mock_virtual_memory

        # Mock high disk usage
        mock_disk_usage = Mock()
        mock_disk_usage.total = 107374182400
        mock_disk_usage.free = 5368709120   # Low free space
        mock_disk_usage.used = 102005473280  # High used
        mock_psutil.disk_usage.return_value = mock_disk_usage

        # Mock high thread count
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.name.return_value = "python"
        mock_process.status.return_value = "running"
        mock_process.create_time.return_value = 1704067200
        mock_process.num_threads.return_value = 150  # High thread count
        mock_process.num_fds.return_value = 25
        mock_process.connections.return_value = []
        mock_process.cpu_percent.return_value = 5.0

        mock_memory_info = Mock()
        mock_memory_info.rss = 104857600
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.memory_percent.return_value = 1.25

        mock_psutil.Process.return_value = mock_process
        mock_psutil.net_connections.return_value = []
        mock_psutil.net_if_addrs.return_value = {}

        mock_ctx = AsyncMock()

        result = await get_system_status(mock_ctx)

        # Verify warning status and issues
        assert result["health"]["status"] == "warning"
        assert "High CPU usage" in result["health"]["issues"]
        assert "High memory usage" in result["health"]["issues"]
        assert "High disk usage" in result["health"]["issues"]
        assert "High thread count" in result["health"]["issues"]

    @patch("firecrawl_mcp.resources.resources.psutil")
    async def test_get_system_status_critical_memory(self, mock_psutil: Mock) -> None:
        """Test system status with critical memory usage."""
        # Mock critical memory usage
        mock_virtual_memory = Mock()
        mock_virtual_memory.total = 8589934592
        mock_virtual_memory.available = 214748364  # Very low available
        mock_virtual_memory.used = 8375186228  # Very high used
        mock_virtual_memory.percent = 97.5  # Critical percentage
        mock_psutil.virtual_memory.return_value = mock_virtual_memory

        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_percent.return_value = 50.0

        mock_disk_usage = Mock()
        mock_disk_usage.total = 107374182400
        mock_disk_usage.free = 53687091200
        mock_disk_usage.used = 53687091200
        mock_psutil.disk_usage.return_value = mock_disk_usage

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.name.return_value = "python"
        mock_process.status.return_value = "running"
        mock_process.create_time.return_value = 1704067200
        mock_process.num_threads.return_value = 8
        mock_process.num_fds.return_value = 25
        mock_process.connections.return_value = []
        mock_process.cpu_percent.return_value = 5.0

        mock_memory_info = Mock()
        mock_memory_info.rss = 104857600
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.memory_percent.return_value = 1.25

        mock_psutil.Process.return_value = mock_process
        mock_psutil.net_connections.return_value = []
        mock_psutil.net_if_addrs.return_value = {}

        mock_ctx = AsyncMock()

        result = await get_system_status(mock_ctx)

        # Verify critical status
        assert result["health"]["status"] == "critical"
        assert "High memory usage" in result["health"]["issues"]


class TestServerStatusResource:
    """Test MCP server status resource functionality."""

    @patch("firecrawl_mcp.resources.resources.get_server")
    @patch("firecrawl_mcp.resources.resources.get_client")
    async def test_get_server_status_success(self, mock_get_client: Mock, mock_get_server: Mock) -> None:
        """Test successful retrieval of server status."""
        # Mock server
        mock_server = Mock()
        mock_server.is_ready.return_value = True
        mock_server._client_initialized = True
        mock_server._registered_tools = ["scrape", "batch_scrape", "crawl"]
        mock_server._registered_resources = ["config", "status", "logs"]
        mock_server._registered_prompts = ["extraction", "synthesis"]

        # Mock server config
        mock_config = Mock()
        mock_config.server_name = "Test Server"
        mock_config.server_version = "1.0.0"
        mock_config.server_host = "localhost"
        mock_config.server_port = 8080
        mock_config.development_mode = False
        mock_config.debug_mode = False
        mock_config.firecrawl_api_key = "test-key"
        mock_config.auth_enabled = True
        mock_config.rate_limit_enabled = True
        mock_config.cache_enabled = True
        mock_config.vector_search_enabled = True
        mock_config.enable_metrics = True
        mock_config.enable_health_checks = True
        mock_config.is_valid.return_value = True
        mock_config.has_llm_provider.return_value = True
        mock_config.get_llm_provider.return_value = "openai"
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_server.config = mock_config
        mock_get_server.return_value = mock_server

        # Mock client status
        mock_client = Mock()
        mock_client.get_status.return_value = {
            "connection_available": True,
            "client_initialized": True,
            "api_url": "https://api.firecrawl.dev",
            "last_error": None
        }
        mock_get_client.return_value = mock_client

        mock_ctx = AsyncMock()

        result = await get_server_status(mock_ctx)

        # Verify structure and content
        assert isinstance(result, dict)
        assert "server_info" in result
        assert "configuration" in result
        assert "registered_components" in result
        assert "features" in result
        assert "client_status" in result
        assert "health" in result

        # Verify server info
        assert result["server_info"]["name"] == "Test Server"
        assert result["server_info"]["ready"] is True
        assert result["server_info"]["client_initialized"] is True

        # Verify configuration
        assert result["configuration"]["valid"] is True
        assert result["configuration"]["environment"] == "production"
        assert result["configuration"]["has_api_key"] is True
        assert result["configuration"]["preferred_llm"] == "openai"

        # Verify registered components
        assert result["registered_components"]["tools"]["count"] == 3
        assert "scrape" in result["registered_components"]["tools"]["names"]
        assert result["registered_components"]["resources"]["count"] == 3
        assert result["registered_components"]["prompts"]["count"] == 2

        # Verify features
        assert result["features"]["auth_enabled"] is True
        assert result["features"]["vector_search"] is True

        # Verify client status
        assert result["client_status"]["connected"] is True
        assert result["client_status"]["initialized"] is True

        # Verify health assessment
        assert result["health"]["score"] == "4/4"
        assert result["health"]["percentage"] == 100.0
        assert result["health"]["status"] == "healthy"

        mock_ctx.info.assert_called_once_with("Server status retrieved successfully")

    @patch("firecrawl_mcp.resources.resources.get_server")
    @patch("firecrawl_mcp.resources.resources.get_client")
    async def test_get_server_status_degraded(self, mock_get_client: Mock, mock_get_server: Mock) -> None:
        """Test server status when partially degraded."""
        # Mock server with some issues
        mock_server = Mock()
        mock_server.is_ready.return_value = True
        mock_server._client_initialized = False  # Issue here
        mock_server._registered_tools = ["scrape"]
        mock_server._registered_resources = ["config"]
        mock_server._registered_prompts = []

        # Mock server config with validation issue
        mock_config = Mock()
        mock_config.server_name = "Test Server"
        mock_config.server_version = "1.0.0"
        mock_config.server_host = "localhost"
        mock_config.server_port = 8080
        mock_config.development_mode = True
        mock_config.debug_mode = False
        mock_config.firecrawl_api_key = None  # Missing API key
        mock_config.auth_enabled = False
        mock_config.rate_limit_enabled = False
        mock_config.cache_enabled = False
        mock_config.vector_search_enabled = False
        mock_config.enable_metrics = False
        mock_config.enable_health_checks = False
        mock_config.is_valid.return_value = False  # Invalid config
        mock_config.has_llm_provider.return_value = False
        mock_config.get_llm_provider.return_value = None
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_server.config = mock_config
        mock_get_server.return_value = mock_server

        # Mock client connection failure
        mock_get_client.side_effect = Exception("Client connection failed")

        mock_ctx = AsyncMock()

        result = await get_server_status(mock_ctx)

        # Verify degraded health status
        assert result["health"]["score"] == "1/4"  # Only server_ready is True
        assert result["health"]["percentage"] == 25.0
        assert result["health"]["status"] == "unhealthy"

        # Verify specific issues
        assert result["configuration"]["valid"] is False
        assert result["configuration"]["has_api_key"] is False
        assert result["client_status"]["connected"] is False
        assert "Client connection failed" in result["client_status"]["error"]


class TestUsageStatisticsResource:
    """Test usage statistics resource functionality."""

    @patch("firecrawl_mcp.resources.resources.load_config")
    async def test_get_usage_statistics_success(self, mock_load_config: Mock) -> None:
        """Test successful retrieval of usage statistics."""
        mock_config = Mock()
        mock_config.rate_limit_enabled = True
        mock_config.rate_limit_requests_per_minute = 60
        mock_config.rate_limit_requests_per_hour = 1000
        mock_config.cache_enabled = True
        mock_config.cache_max_size = 1000
        mock_config.server_version = "1.0.0"
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_load_config.return_value = mock_config

        mock_ctx = AsyncMock()

        result = await get_usage_statistics(mock_ctx)

        # Verify structure and content
        assert isinstance(result, dict)
        assert "session" in result
        assert "api_operations" in result
        assert "resource_access" in result
        assert "performance" in result
        assert "rate_limiting" in result
        assert "cache" in result
        assert "metadata" in result

        # Verify session data structure
        assert "start_time" in result["session"]
        assert "uptime_seconds" in result["session"]
        assert "requests_processed" in result["session"]

        # Verify API operations counters
        assert "scrape_requests" in result["api_operations"]
        assert "batch_scrape_requests" in result["api_operations"]
        assert "crawl_requests" in result["api_operations"]
        assert "extract_requests" in result["api_operations"]
        assert "vector_search_requests" in result["api_operations"]

        # Verify rate limiting configuration
        assert result["rate_limiting"]["enabled"] is True
        assert result["rate_limiting"]["requests_per_minute_limit"] == 60

        # Verify cache configuration
        assert result["cache"]["enabled"] is True
        assert result["cache"]["max_size"] == 1000

        # Verify metadata
        assert result["metadata"]["collection_method"] == "basic_implementation"
        assert "production deployments should integrate" in result["metadata"]["note"]

        mock_ctx.info.assert_called_once_with("Usage statistics retrieved successfully")


class TestActiveOperationsResource:
    """Test active operations resource functionality."""

    @patch("firecrawl_mcp.resources.resources.load_config")
    async def test_get_active_operations_success(self, mock_load_config: Mock) -> None:
        """Test successful retrieval of active operations."""
        mock_config = Mock()
        mock_config.development_mode = True
        mock_config.rate_limit_burst_size = 10
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_load_config.return_value = mock_config

        mock_ctx = AsyncMock()

        result = await get_active_operations(mock_ctx)

        # Verify structure and content
        assert isinstance(result, dict)
        assert "batch_operations" in result
        assert "crawl_jobs" in result
        assert "background_tasks" in result
        assert "api_requests" in result
        assert "system_tasks" in result
        assert "queue_status" in result
        assert "metadata" in result

        # Verify batch operations structure
        assert "active_count" in result["batch_operations"]
        assert "queued_count" in result["batch_operations"]
        assert "operations" in result["batch_operations"]

        # Verify crawl jobs structure
        assert "active_count" in result["crawl_jobs"]
        assert "jobs" in result["crawl_jobs"]

        # Verify queue status
        assert result["queue_status"]["healthy"] is True
        assert "processing_capacity" in result["queue_status"]

        # Verify development mode note
        assert "demo_note" in result
        assert "demonstration data" in result["demo_note"]

        mock_ctx.info.assert_called_once_with("Active operations retrieved successfully")


class TestRecentLogsResource:
    """Test recent logs resource functionality."""

    @patch("firecrawl_mcp.resources.resources.load_config")
    @patch("firecrawl_mcp.resources.resources.os.path.exists")
    async def test_get_recent_logs_no_logs_directory(self, mock_exists: Mock, mock_load_config: Mock) -> None:
        """Test recent logs when logs directory doesn't exist."""
        mock_config = Mock()
        mock_config.log_level = "INFO"
        mock_config.log_max_size = 10485760
        mock_config.log_backup_count = 5
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_load_config.return_value = mock_config
        mock_exists.return_value = False

        mock_ctx = AsyncMock()

        result = await get_recent_logs(mock_ctx)

        # Verify structure for no logs case
        assert isinstance(result, dict)
        assert "log_files" in result
        assert "recent_entries" in result
        assert "error_summary" in result
        assert "log_system_status" in result
        assert "metadata" in result

        # Verify log system status shows no logs
        assert result["log_system_status"]["main_log_exists"] is False
        assert result["log_system_status"]["middleware_log_exists"] is False

        # Verify empty recent entries
        assert result["recent_entries"]["info"] == []
        assert result["recent_entries"]["error"] == []

        mock_ctx.info.assert_called_once_with("Recent logs retrieved successfully")

    @patch("firecrawl_mcp.resources.resources.load_config")
    @patch("firecrawl_mcp.resources.resources.os.path.exists")
    @patch("firecrawl_mcp.resources.resources.os.path.getsize")
    async def test_get_recent_logs_with_log_files(self, mock_getsize: Mock, mock_exists: Mock, mock_load_config: Mock) -> None:
        """Test recent logs when log files exist."""
        mock_config = Mock()
        mock_config.log_level = "INFO"
        mock_config.log_max_size = 10485760
        mock_config.log_backup_count = 5
        mock_config.get_current_timestamp.return_value = "2024-01-01T00:00:00Z"

        mock_load_config.return_value = mock_config

        # Mock log file content
        log_content = """2024-01-01 00:00:01 - firecrawl_mcp - INFO - Server started
2024-01-01 00:00:02 - firecrawl_mcp - ERROR - Connection failed
2024-01-01 00:00:03 - firecrawl_mcp - WARNING - Rate limit approaching
2024-01-01 00:00:04 - firecrawl_mcp - CRITICAL - Critical system error
2024-01-01 00:00:05 - firecrawl_mcp - INFO - Request processed successfully
"""

        def mock_exists_side_effect(path: str) -> bool:
            return "logs" in path or "firecrawler.log" in path or "middleware.log" in path

        mock_exists.side_effect = mock_exists_side_effect
        mock_getsize.return_value = 1024  # 1KB

        # Mock reading the log file
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.readlines.return_value = log_content.split('\n')

            mock_ctx = AsyncMock()

            result = await get_recent_logs(mock_ctx)

        # Verify log system status shows logs exist
        assert result["log_system_status"]["main_log_exists"] is True
        assert result["log_system_status"]["main_log_size_mb"] == 0.0  # 1KB rounds to 0.0 MB
        assert result["log_system_status"]["middleware_log_exists"] is True

        # Verify recent entries are parsed correctly
        assert len(result["recent_entries"]["info"]) == 2
        assert len(result["recent_entries"]["error"]) == 1
        assert len(result["recent_entries"]["warning"]) == 1
        assert len(result["recent_entries"]["critical"]) == 1

        # Verify error summary
        assert result["error_summary"]["total_errors"] == 2  # ERROR + CRITICAL
        assert result["error_summary"]["unique_errors"] > 0


class TestResourceRegistration:
    """Test resource registration with FastMCP server."""

    def test_setup_resources_with_server(self) -> None:
        """Test setup of all resources with FastMCP server."""
        server = FastMCP("TestResourceServer")

        # Register resources
        setup_resources(server)

        # Note: We can't easily test the actual registration without accessing
        # internal FastMCP server state, but we can verify the function completes
        # without errors and the expected resources would be available
        assert True  # If we get here, registration completed successfully

    async def test_registered_resources_availability(self) -> None:
        """Test that registered resources are available via MCP client."""
        server = FastMCP("TestResourceServer")
        setup_resources(server)

        async with Client(server) as client:
            # List available resources
            resources = await client.list_resources()

            # Verify expected resources are registered
            resource_uris = [resource["uri"] for resource in resources]

            expected_resources = [
                "firecrawl://config/server",
                "firecrawl://config/environment",
                "firecrawl://status/api",
                "firecrawl://status/system",
                "firecrawl://status/mcp",
                "firecrawl://usage/statistics",
                "firecrawl://operations/active",
                "firecrawl://logs/recent"
            ]

            for expected_resource in expected_resources:
                assert expected_resource in resource_uris

    async def test_resource_metadata_correctness(self) -> None:
        """Test that resource metadata is correctly set."""
        server = FastMCP("TestResourceServer")
        setup_resources(server)

        async with Client(server) as client:
            resources = await client.list_resources()

            resource_dict = {resource["uri"]: resource for resource in resources}

            # Test server config resource metadata
            server_config = resource_dict["firecrawl://config/server"]
            assert server_config["name"] == "Server Configuration"
            assert "configuration" in server_config.get("tags", [])
            assert "server" in server_config.get("tags", [])
            assert server_config["mimeType"] == "application/json"

            # Test API status resource metadata
            api_status = resource_dict["firecrawl://status/api"]
            assert api_status["name"] == "API Status"
            assert "status" in api_status.get("tags", [])
            assert "api" in api_status.get("tags", [])
            assert "connectivity" in api_status.get("tags", [])

    @patch("firecrawl_mcp.resources.resources.get_server_config")
    async def test_resource_access_through_client(self, mock_get_server_config: Mock) -> None:
        """Test accessing resources through MCP client."""
        # Mock the resource function
        mock_get_server_config.return_value = {
            "server_info": {"name": "Test Server", "version": "1.0.0"},
            "timestamp": "2024-01-01T00:00:00Z"
        }

        server = FastMCP("TestResourceServer")
        setup_resources(server)

        async with Client(server) as client:
            # Access a specific resource
            resource_content = await client.read_resource("firecrawl://config/server")

            # Verify resource content
            assert isinstance(resource_content, dict)
            # The exact structure depends on FastMCP's resource response format
            # but we can verify the mock was called
            mock_get_server_config.assert_called_once()


class TestResourceErrorHandling:
    """Test error handling in resource functions."""

    @patch("firecrawl_mcp.resources.resources.load_config")
    async def test_resource_error_propagation(self, mock_load_config: Mock) -> None:
        """Test that resource errors are properly propagated."""
        mock_load_config.side_effect = Exception("Configuration load failed")

        mock_ctx = AsyncMock()

        # Test that ResourceError is raised
        with pytest.raises(ResourceError, match="Failed to retrieve server configuration"):
            await get_server_config(mock_ctx)

        # Verify error was logged
        mock_ctx.error.assert_called_once()

    @patch("firecrawl_mcp.resources.resources.get_client")
    async def test_api_status_error_handling(self, mock_get_client: Mock) -> None:
        """Test API status error handling returns error status instead of raising."""
        mock_get_client.side_effect = Exception("Client error")

        mock_ctx = AsyncMock()

        # Should not raise exception
        result = await get_api_status(mock_ctx)

        # Should return error status
        assert result["connection"]["status"] == "error"
        assert "Client error" in result["connection"]["error"]
        assert result["validation"]["status"] == "failed"

    async def test_resource_integration_error_handling(self) -> None:
        """Test error handling in resource integration with MCP server."""
        server = FastMCP("TestErrorHandlingServer")

        # Register a resource that will fail
        @server.resource("test://failing-resource")
        async def failing_resource(_ctx: Context) -> None:
            raise Exception("Resource processing failed")

        async with Client(server) as client:
            # Attempt to access the failing resource
            with pytest.raises(Exception, match="Resource processing failed"):
                await client.read_resource("test://failing-resource")
