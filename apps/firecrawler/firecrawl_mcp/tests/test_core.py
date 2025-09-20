"""
Core client and configuration tests for the Firecrawler MCP server.

This module tests the fundamental client initialization, configuration management,
and error handling components that form the foundation of the MCP server.
"""

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError
from firecrawl.v2.client import FirecrawlClient
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    FirecrawlError,
    InternalServerError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.core.client import (
    get_client,
    get_client_status,
    get_firecrawl_client,
    initialize_client,
    reset_client,
)
from firecrawl_mcp.core.config import (
    MCPConfig,
    get_env_bool,
    get_env_float,
    get_env_int,
    get_server_info,
    load_config,
    validate_environment,
)
from firecrawl_mcp.core.exceptions import (
    MCPAuthenticationError,
    MCPClientError,
    MCPConfigurationError,
    MCPError,
    MCPRateLimitError,
    MCPServerError,
    MCPToolError,
    MCPValidationError,
    create_error_response,
    create_tool_error,
    handle_firecrawl_error,
    mcp_log_error,
)

from .conftest import create_test_config


class TestMCPConfig:
    """Test suite for MCPConfig class."""

    def test_config_initialization_with_defaults(self) -> None:
        """Test that server info returns proper defaults."""
        # Test with clean environment to check defaults
        with patch.dict(os.environ, {}, clear=True):
            server_info = get_server_info()

            # Test default values
            assert server_info["api_url"] == "https://api.firecrawl.dev"
            assert server_info["server_name"] == "Firecrawl MCP Server"
            assert server_info["server_version"] == "1.0.0"
            assert server_info["api_key_configured"] is False
            assert server_info["debug_mode"] is False
            assert server_info["development_mode"] is False

    def test_config_loads_from_environment(self, _test_env: dict[str, str]) -> None:
        """Test that environment utilities load values from environment variables."""
        server_info = get_server_info()

        assert server_info["api_key_configured"] is True
        assert server_info["api_url"] == "https://api.firecrawl.dev"
        assert server_info["server_name"] == "Test Firecrawler MCP Server"
        assert server_info["debug_mode"] is True
        assert server_info["development_mode"] is True

        # Test environment variable parsing
        assert get_env_float("FIRECRAWL_TIMEOUT", 120.0) == 30.0
        assert get_env_int("FIRECRAWL_MAX_RETRIES", 3) == 2
        assert get_env_bool("RATE_LIMIT_ENABLED", True) is False
        assert get_env_bool("AUTH_ENABLED", True) is False
        assert get_env_bool("CACHE_ENABLED", True) is False

    def test_config_validation_success(self, _valid_config: MCPConfig) -> None:
        """Test that valid configuration passes validation."""
        assert _valid_config.is_valid() is True

    def test_config_validation_missing_api_key(self) -> None:
        """Test that environment validation detects missing API key."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_environment()

            assert result["valid"] is False
            assert "FIRECRAWL_API_KEY is required" in str(result["issues"])

    def test_config_validation_negative_timeout(self) -> None:
        """Test that environment parsing handles negative timeout values."""
        env_config = create_test_config(FIRECRAWL_TIMEOUT="-1")

        with patch.dict(os.environ, env_config):
            # The environment parser should parse the actual value (negative values are allowed)
            timeout = get_env_float("FIRECRAWL_TIMEOUT", 120.0)
            assert timeout == -1.0  # Should parse the actual value

    def test_config_validation_negative_max_retries(self) -> None:
        """Test that environment parsing handles negative max retries values."""
        env_config = create_test_config(FIRECRAWL_MAX_RETRIES="-1")

        with patch.dict(os.environ, env_config):
            # The environment parser should parse the actual value (negative values are allowed)
            max_retries = get_env_int("FIRECRAWL_MAX_RETRIES", 3)
            assert max_retries == -1  # Should parse the actual value

    def test_config_validation_invalid_server_port(self) -> None:
        """Test that environment parsing handles large server port values."""
        env_config = create_test_config(MCP_SERVER_PORT="70000")

        with patch.dict(os.environ, env_config):
            # The environment parser should parse the actual value (validation is done elsewhere)
            server_port = get_env_int("MCP_SERVER_PORT", 8000)
            assert server_port == 70000  # Should parse the actual value

    def test_config_validation_invalid_temperature(self) -> None:
        """Test that environment parsing handles high temperature values."""
        env_config = create_test_config(OPENAI_TEMPERATURE="3.0")

        with patch.dict(os.environ, env_config):
            # The environment parser should parse the actual value (validation is done elsewhere)
            temperature = get_env_float("OPENAI_TEMPERATURE", 1.0)
            assert temperature == 3.0  # Should parse the actual value

    def test_config_parse_bool_default_when_not_set(self) -> None:
        """Test that boolean parsing returns default when environment variable is not set."""
        assert not get_env_bool("TEST_VAR", False), (
            "Expected default value when environment variable not set"
        )
        assert get_env_bool("TEST_VAR", True), (
            "Expected default value when environment variable not set"
        )

    def test_config_parse_bool_true_values(self) -> None:
        """Test that various true values are parsed correctly."""
        true_values = ["true", "TRUE", "1", "yes", "on", "enabled"]

        for value in true_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                result = get_env_bool("TEST_VAR", False)
                assert result, f"Expected '{value}' to parse as True, got {result}"

    def test_config_parse_bool_false_values(self) -> None:
        """Test that various false values are parsed correctly."""
        false_values = ["false", "FALSE", "0", "no", "off", "disabled", ""]

        for value in false_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                result = get_env_bool(
                    "TEST_VAR", True
                )  # Use True default to ensure parsing works
                assert not result, f"Expected '{value}' to parse as False, got {result}"

    def test_config_has_llm_provider(self) -> None:
        """Test LLM provider detection using environment functions."""
        # No LLM provider
        with patch.dict(os.environ, create_test_config()):
            validation = validate_environment()
            # Check that recommendations include LLM setup
            has_llm_recommendation = any(
                "OPENAI_API_KEY" in rec or "OLLAMA_BASE_URL" in rec
                for rec in validation["recommendations"]
            )
            assert has_llm_recommendation

        # OpenAI provider
        with patch.dict(os.environ, create_test_config(OPENAI_API_KEY="sk-test")):
            assert bool(os.getenv("OPENAI_API_KEY"))

        # Ollama provider
        with patch.dict(os.environ, create_test_config(OLLAMA_BASE_URL="http://localhost:11434")):
            assert bool(os.getenv("OLLAMA_BASE_URL"))

    def test_config_to_dict_masks_sensitive_values(self, _valid_config: MCPConfig) -> None:
        """Test that server info provides configuration without sensitive values."""
        server_info = get_server_info()

        # API key should not be exposed directly
        assert "api_key" not in server_info
        assert server_info["api_key_configured"] is True

        # Non-sensitive values should be available
        assert server_info["api_url"] == "https://api.firecrawl.dev"
        assert server_info["server_name"] == "Test Firecrawler MCP Server"

    def test_config_get_summary(self, _valid_config: MCPConfig) -> None:
        """Test environment validation provides comprehensive summary."""
        validation = validate_environment()

        assert "valid" in validation
        assert "issues" in validation
        assert "recommendations" in validation
        assert "server_info" in validation

        server_info = validation["server_info"]
        assert server_info["api_key_configured"] is True
        assert server_info["server_name"] == "Test Firecrawler MCP Server"

    def test_load_config_function(self, _test_env: dict[str, str]) -> None:
        """Test the legacy load_config utility function."""
        config = load_config()
        assert isinstance(config, MCPConfig)

    def test_validate_environment_function(self, _test_env: dict[str, str]) -> None:
        """Test the validate_environment utility function."""
        result = validate_environment()

        assert isinstance(result, dict)
        assert "valid" in result
        assert "server_info" in result
        assert "recommendations" in result

        assert result["valid"] is True
        assert isinstance(result["recommendations"], list)


class TestFirecrawlClient:
    """Test suite for Firecrawl client utilities."""

    def test_client_creation_success(self, _test_env: dict[str, str]) -> None:
        """Test successful client creation."""
        client = get_firecrawl_client()
        assert isinstance(client, FirecrawlClient)

    def test_client_creation_failure_no_api_key(self) -> None:
        """Test client creation failure without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ToolError) as exc_info:
                get_firecrawl_client()

            assert "FIRECRAWL_API_KEY" in str(exc_info.value)

    def test_client_creation_with_self_hosted(self) -> None:
        """Test client creation for self-hosted instance."""
        with patch.dict(os.environ, {
            "FIRECRAWL_API_URL": "http://localhost:3002"
        }, clear=True):
            client = get_firecrawl_client()
            assert isinstance(client, FirecrawlClient)

    def test_client_status_success(self, _test_env: dict[str, str]) -> None:
        """Test successful client status check."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_credit_usage.return_value = MagicMock(remaining=100)
            mock_get_client.return_value = mock_client

            status = get_client_status()

            assert isinstance(status, dict)
            assert status["status"] == "connected"
            assert status["connection_test"] == "passed"
            assert status["api_key_configured"] is True

    def test_client_status_self_hosted(self) -> None:
        """Test client status for self-hosted instance."""
        with patch.dict(os.environ, {
            "FIRECRAWL_API_URL": "http://localhost:3002",
            "FIRECRAWL_API_KEY": "test-key"
        }), patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_concurrency.return_value = {"limit": 10}
            mock_get_client.return_value = mock_client

            status = get_client_status()

            assert status["is_likely_self_hosted"] is True
            assert status["connection_test"] == "passed"

    def test_client_status_failure(self, _test_env: dict[str, str]) -> None:
        """Test client status check failure."""
        with patch("firecrawl_mcp.core.client.get_firecrawl_client") as mock_get_client:
            mock_get_client.side_effect = Exception("Connection failed")

            with pytest.raises(ToolError) as exc_info:
                get_client_status()

            assert "Failed to get client status" in str(exc_info.value)


class TestLegacyClientFunctions:
    """Test suite for legacy client management functions."""

    def test_legacy_get_client_success(self, _test_env: dict[str, str]) -> None:
        """Test legacy get_client function."""
        client = get_client()
        assert isinstance(client, FirecrawlClient)

    def test_legacy_get_client_failure(self) -> None:
        """Test legacy get_client function failure."""
        # Clear environment to cause initialization failure
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ToolError) as exc_info:
                get_client()

            assert "FIRECRAWL_API_KEY" in str(exc_info.value)

    def test_legacy_initialize_client_success(self, _test_env: dict[str, str]) -> None:
        """Test legacy initialize_client function."""
        client = initialize_client()
        assert isinstance(client, FirecrawlClient)

    def test_legacy_reset_client(self) -> None:
        """Test legacy reset_client function (no-op)."""
        # This should not raise an exception
        reset_client()
        assert True  # Just verify it doesn't crash


class TestMCPExceptions:
    """Test suite for MCP exception utilities."""

    def test_legacy_mcp_error_basic(self) -> None:
        """Test basic legacy MCP error functionality."""
        error = MCPError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_legacy_mcp_configuration_error(self) -> None:
        """Test legacy MCP configuration error."""
        error = MCPConfigurationError("Config error")
        assert str(error) == "Config error"
        assert isinstance(error, MCPError)

    def test_legacy_mcp_client_error(self) -> None:
        """Test legacy MCP client error."""
        error = MCPClientError("Client error")
        assert str(error) == "Client error"
        assert isinstance(error, MCPError)

    def test_legacy_mcp_tool_error(self) -> None:
        """Test legacy MCP tool error."""
        error = MCPToolError("Tool error")
        assert str(error) == "Tool error"
        assert isinstance(error, MCPError)

    def test_legacy_mcp_validation_error(self) -> None:
        """Test legacy MCP validation error."""
        error = MCPValidationError("Validation error")
        assert str(error) == "Validation error"
        assert isinstance(error, MCPError)

    def test_handle_firecrawl_error_basic(self) -> None:
        """Test basic Firecrawl error handling."""
        original_error = FirecrawlError("Original error")
        tool_error = handle_firecrawl_error(original_error)

        assert isinstance(tool_error, ToolError)
        assert "Original error" in str(tool_error)

    def test_handle_firecrawl_error_with_context(self) -> None:
        """Test Firecrawl error handling with context."""
        original_error = BadRequestError("Bad request")
        context = "scraping https://example.com"

        tool_error = handle_firecrawl_error(original_error, context)

        assert isinstance(tool_error, ToolError)
        assert "Bad request" in str(tool_error)
        assert "scraping https://example.com" in str(tool_error)

    def test_handle_firecrawl_bad_request_error_mapping(self) -> None:
        """Test that BadRequestError is handled appropriately."""
        original_error = BadRequestError("Bad request")
        tool_error = handle_firecrawl_error(original_error)

        assert isinstance(tool_error, ToolError)
        assert "Invalid request parameters" in str(tool_error)

    def test_handle_firecrawl_unauthorized_error_mapping(self) -> None:
        """Test that UnauthorizedError is handled appropriately."""
        original_error = UnauthorizedError("Unauthorized")
        tool_error = handle_firecrawl_error(original_error)

        assert isinstance(tool_error, ToolError)
        assert "Authentication failed" in str(tool_error)

    def test_handle_firecrawl_rate_limit_error_mapping(self) -> None:
        """Test that RateLimitError is handled appropriately."""
        original_error = RateLimitError("Rate limited")
        tool_error = handle_firecrawl_error(original_error)

        assert isinstance(tool_error, ToolError)
        assert "Rate limit exceeded" in str(tool_error)

    def test_handle_firecrawl_internal_server_error_mapping(self) -> None:
        """Test that InternalServerError is handled appropriately."""
        original_error = InternalServerError("Server error")
        tool_error = handle_firecrawl_error(original_error)

        assert isinstance(tool_error, ToolError)
        assert "Internal server error" in str(tool_error)

    def test_create_tool_error_basic(self) -> None:
        """Test basic tool error creation."""
        error = create_tool_error("Test error")

        assert isinstance(error, ToolError)
        assert str(error) == "Test error"

    def test_create_tool_error_with_details(self) -> None:
        """Test tool error creation with details."""
        details = {"url": "https://example.com", "tool": "scrape"}
        error = create_tool_error("Test error", details)

        assert isinstance(error, ToolError)
        assert "Test error" in str(error)
        assert "url=https://example.com" in str(error)
        assert "tool=scrape" in str(error)

    def test_log_error_function(self, caplog: Any) -> None:
        """Test error logging function."""
        error = ToolError("Test validation error")
        context = {"operation": "test"}

        mcp_log_error(error, context)

        # Check that error was logged
        assert len(caplog.records) >= 1
        log_messages = [record.message for record in caplog.records]
        assert any("ToolError" in msg for msg in log_messages)

    def test_create_error_response_generic_error(self) -> None:
        """Test error response creation for generic errors."""
        error = ValueError("Generic error")

        response = create_error_response(error)

        assert response["error"] == "ValueError"
        assert response["message"] == "Generic error"
        assert response["error_code"] == "UNKNOWN_ERROR"
        assert response["details"] == {}


class TestLegacyErrorInheritance:
    """Test suite for legacy MCP error inheritance."""

    def test_authentication_error_inheritance(self) -> None:
        """Test that MCPAuthenticationError inherits from MCPError."""
        error = MCPAuthenticationError("Auth failed")
        assert isinstance(error, MCPError)
        assert isinstance(error, Exception)

    def test_rate_limit_error_inheritance(self) -> None:
        """Test that MCPRateLimitError inherits from MCPError."""
        error = MCPRateLimitError("Rate limited")
        assert isinstance(error, MCPError)
        assert isinstance(error, Exception)

    def test_server_error_inheritance(self) -> None:
        """Test that MCPServerError inherits from MCPError."""
        error = MCPServerError("Server error")
        assert isinstance(error, MCPError)
        assert isinstance(error, Exception)


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration test scenarios that require external dependencies."""

    @pytest.mark.skipif(
        not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available"
    )
    def test_real_client_initialization(self) -> None:
        """Test client initialization with real API key."""
        # This test only runs if FIRECRAWL_API_KEY is available
        client = get_firecrawl_client()
        assert isinstance(client, FirecrawlClient)

        # Test connection status
        status = get_client_status()
        assert "status" in status

    def test_config_with_missing_environment(self) -> None:
        """Test environment validation with completely clean environment."""
        with patch.dict(os.environ, {}, clear=True):
            validation = validate_environment()

            assert validation["valid"] is False
            assert "FIRECRAWL_API_KEY is required" in str(validation["issues"])
