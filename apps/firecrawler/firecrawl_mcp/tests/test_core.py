"""
Core client and configuration tests for the Firecrawler MCP server.

This module tests the fundamental client initialization, configuration management,
and error handling components that form the foundation of the MCP server.
"""

import os
from unittest.mock import patch

import pytest
from firecrawl.v2.utils.error_handler import (
    BadRequestError,
    FirecrawlError,
    InternalServerError,
    RateLimitError,
    UnauthorizedError,
)

from firecrawl_mcp.core.client import (
    ClientConnectionInfo,
    FirecrawlMCPClient,
    get_client,
    initialize_client,
    reset_client,
)
from firecrawl_mcp.core.config import MCPConfig, load_config, validate_environment
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
    handle_firecrawl_error,
    mcp_log_error,
)

from .conftest import create_test_config


class TestMCPConfig:
    """Test suite for MCPConfig class."""

    def test_config_initialization_with_defaults(self):
        """Test that configuration initializes with proper defaults."""
        # Provide minimal required config but let other values use defaults
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "test-key"}, clear=True):
            config = MCPConfig()

            # Test default values
            assert config.firecrawl_api_url == "https://api.firecrawl.dev"
            assert config.firecrawl_timeout == 120.0
            assert config.firecrawl_max_retries == 3
            assert config.firecrawl_backoff_factor == 0.5
            assert config.server_name == "Firecrawler MCP Server"
            assert config.server_version == "1.0.0"
            assert config.log_level == "INFO"
            assert config.rate_limit_enabled is True
            assert config.auth_enabled is False
            assert config.cache_enabled is True
            assert config.vector_search_enabled is True
            assert config.debug_mode is False

    def test_config_loads_from_environment(self, test_env):
        """Test that configuration loads values from environment variables."""
        config = MCPConfig()

        assert config.firecrawl_api_key == "fc-test-key-1234567890abcdef"
        assert config.firecrawl_api_url == "https://api.firecrawl.dev"
        assert config.firecrawl_timeout == 30.0
        assert config.firecrawl_max_retries == 2
        assert config.server_name == "Test Firecrawler MCP Server"
        assert config.log_level == "DEBUG"
        assert config.rate_limit_enabled is False
        assert config.auth_enabled is False
        assert config.cache_enabled is False
        assert config.development_mode is True
        assert config.debug_mode is True

    def test_config_validation_success(self, valid_config):
        """Test that valid configuration passes validation."""
        assert valid_config.is_valid() is True

    def test_config_validation_missing_api_key(self):
        """Test that configuration validation fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                MCPConfig()

            assert "FIRECRAWL_API_KEY is required" in str(exc_info.value)

    def test_config_validation_negative_timeout(self):
        """Test that configuration validation fails with negative timeout."""
        env_config = create_test_config(FIRECRAWL_TIMEOUT="-1")

        with patch.dict(os.environ, env_config):
            with pytest.raises(ValueError) as exc_info:
                MCPConfig()

            assert "FIRECRAWL_TIMEOUT must be positive" in str(exc_info.value), f"Expected timeout validation error, got: {exc_info.value}"

    def test_config_validation_negative_max_retries(self):
        """Test that configuration validation fails with negative max retries."""
        env_config = create_test_config(FIRECRAWL_MAX_RETRIES="-1")

        with patch.dict(os.environ, env_config):
            with pytest.raises(ValueError) as exc_info:
                MCPConfig()

            assert "FIRECRAWL_MAX_RETRIES must be non-negative" in str(exc_info.value), f"Expected max retries validation error, got: {exc_info.value}"

    def test_config_validation_invalid_server_port(self):
        """Test that configuration validation fails with invalid server port."""
        env_config = create_test_config(MCP_SERVER_PORT="70000")

        with patch.dict(os.environ, env_config):
            with pytest.raises(ValueError) as exc_info:
                MCPConfig()

            assert "MCP_SERVER_PORT must be between 1 and 65535" in str(exc_info.value), f"Expected server port validation error, got: {exc_info.value}"

    def test_config_validation_invalid_temperature(self):
        """Test that configuration validation fails with invalid OpenAI temperature."""
        env_config = create_test_config(OPENAI_TEMPERATURE="3.0")

        with patch.dict(os.environ, env_config):
            with pytest.raises(ValueError) as exc_info:
                MCPConfig()

            assert "OPENAI_TEMPERATURE must be between 0 and 2" in str(exc_info.value), f"Expected temperature validation error, got: {exc_info.value}"

    def test_config_parse_bool_default_when_not_set(self):
        """Test that boolean parsing returns default when environment variable is not set."""
        assert MCPConfig._parse_bool("TEST_VAR", False) == False, "Expected default value when environment variable not set"
        assert MCPConfig._parse_bool("TEST_VAR", True) == True, "Expected default value when environment variable not set"

    def test_config_parse_bool_true_values(self):
        """Test that various true values are parsed correctly."""
        true_values = ["true", "TRUE", "1", "yes", "on", "enabled"]

        for value in true_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                result = MCPConfig._parse_bool("TEST_VAR", False)
                assert result == True, f"Expected '{value}' to parse as True, got {result}"

    def test_config_parse_bool_false_values(self):
        """Test that various false values are parsed correctly."""
        false_values = ["false", "FALSE", "0", "no", "off", "disabled", ""]

        for value in false_values:
            with patch.dict(os.environ, {"TEST_VAR": value}):
                result = MCPConfig._parse_bool("TEST_VAR", True)  # Use True default to ensure parsing works
                assert result == False, f"Expected '{value}' to parse as False, got {result}"

    def test_config_has_llm_provider(self):
        """Test LLM provider detection."""
        # No LLM provider
        with patch.dict(os.environ, create_test_config()):
            config = MCPConfig()
            assert config.has_llm_provider() is False
            assert config.get_llm_provider() is None

        # OpenAI provider
        with patch.dict(os.environ, create_test_config(OPENAI_API_KEY="sk-test")):
            config = MCPConfig()
            assert config.has_llm_provider() is True
            assert config.get_llm_provider() == "openai"

        # Ollama provider
        with patch.dict(os.environ, create_test_config(OLLAMA_BASE_URL="http://localhost:11434")):
            config = MCPConfig()
            assert config.has_llm_provider() is True
            assert config.get_llm_provider() == "ollama"

    def test_config_to_dict_masks_sensitive_values(self, valid_config):
        """Test that sensitive values are masked in dictionary output."""
        config_dict = valid_config.to_dict()

        # API key should be masked
        assert config_dict["firecrawl_api_key"] == "fc-t...cdef"

        # Non-sensitive values should not be masked
        assert config_dict["firecrawl_api_url"] == "https://api.firecrawl.dev"
        assert config_dict["server_name"] == "Test Firecrawler MCP Server"

    def test_config_get_summary(self, valid_config):
        """Test configuration summary generation."""
        summary = valid_config.get_summary()

        assert "server_name" in summary
        assert "server_version" in summary
        assert "api_url" in summary
        assert "has_api_key" in summary
        assert "timestamp" in summary

        assert summary["has_api_key"] is True
        assert summary["server_name"] == "Test Firecrawler MCP Server"

    def test_load_config_function(self, test_env):
        """Test the load_config utility function."""
        config = load_config()

        assert isinstance(config, MCPConfig)
        assert config.firecrawl_api_key == "fc-test-key-1234567890abcdef"

    def test_validate_environment_function(self, test_env):
        """Test the validate_environment utility function."""
        result = validate_environment()

        assert isinstance(result, dict)
        assert "valid" in result
        assert "summary" in result
        assert "recommendations" in result

        assert result["valid"] is True
        assert isinstance(result["recommendations"], list)


class TestFirecrawlMCPClient:
    """Test suite for FirecrawlMCPClient class."""

    def test_client_initialization_success(self, valid_config, mock_successful_client_validation):
        """Test successful client initialization."""
        client = FirecrawlMCPClient(valid_config)

        assert client.is_connected() is True
        assert client.config == valid_config

        connection_info = client.connection_info
        assert isinstance(connection_info, ClientConnectionInfo)
        assert connection_info.is_connected is True
        assert connection_info.api_key_masked == "fc-t...cdef"

    def test_client_initialization_failure_no_api_key(self, invalid_config):
        """Test client initialization failure without API key."""
        with pytest.raises(MCPConfigurationError) as exc_info:
            FirecrawlMCPClient(invalid_config)

        assert "FIRECRAWL_API_KEY is required" in str(exc_info.value)

    def test_client_initialization_failure_client_error(self, valid_config):
        """Test client initialization failure due to client error."""
        with patch("firecrawl_mcp.core.client.FirecrawlClient") as mock_client_class:
            mock_client_class.side_effect = FirecrawlError("Connection failed")

            with pytest.raises(MCPClientError) as exc_info:
                FirecrawlMCPClient(valid_config)

            assert "Failed to initialize Firecrawl client" in str(exc_info.value)

    def test_client_property_access(self, valid_config, mock_successful_client_validation):
        """Test client property access."""
        mcp_client = FirecrawlMCPClient(valid_config)

        # Test client property
        client = mcp_client.client
        assert client is not None

        # Test config property
        assert mcp_client.config == valid_config

    def test_client_property_access_when_not_initialized(self, valid_config):
        """Test client property access when not initialized."""
        mcp_client = FirecrawlMCPClient.__new__(FirecrawlMCPClient)
        mcp_client._config = valid_config
        mcp_client._client = None
        mcp_client._connection_info = None

        with pytest.raises(MCPClientError) as exc_info:
            _ = mcp_client.client

        assert "Firecrawl client is not initialized" in str(exc_info.value)

    def test_validate_connection_success(self, valid_config, mock_successful_client_validation):
        """Test successful connection validation."""
        client = FirecrawlMCPClient(valid_config)

        result = client.validate_connection()

        assert isinstance(result, dict)
        assert result["status"] == "connected"
        assert result["connection_test"] == "passed"
        assert "timestamp" in result

    def test_validate_connection_failure(self, valid_config, mock_failed_client_validation):
        """Test connection validation failure."""
        client = FirecrawlMCPClient(valid_config)

        with pytest.raises(MCPClientError) as exc_info:
            client.validate_connection()

        assert "Connection validation failed" in str(exc_info.value)

    def test_refresh_client(self, valid_config, mock_successful_client_validation):
        """Test client refresh functionality."""
        client = FirecrawlMCPClient(valid_config)
        original_client_id = id(client._client)

        client.refresh_client()

        # Client should be refreshed (new instance)
        new_client_id = id(client._client)
        assert new_client_id != original_client_id
        assert client.is_connected() is True

    def test_get_status(self, valid_config, mock_successful_client_validation):
        """Test client status retrieval."""
        client = FirecrawlMCPClient(valid_config)

        status = client.get_status()

        assert isinstance(status, dict)
        assert status["client_initialized"] is True
        assert status["connection_available"] is True
        assert status["config_valid"] is True
        assert "timestamp" in status
        assert "api_url" in status

    def test_mask_api_key(self):
        """Test API key masking functionality."""
        # Empty key
        assert FirecrawlMCPClient._mask_api_key("") == "<not set>"

        # Short key
        assert FirecrawlMCPClient._mask_api_key("abc") == "***"

        # Normal key
        assert FirecrawlMCPClient._mask_api_key("fc-1234567890abcdef") == "fc-1...cdef"


class TestGlobalClientManagement:
    """Test suite for global client management functions."""

    def test_get_client_success(self, test_env, mock_successful_client_validation):
        """Test successful global client retrieval."""
        client = get_client()

        assert isinstance(client, FirecrawlMCPClient)
        assert client.is_connected() is True

        # Second call should return same instance
        client2 = get_client()
        assert client is client2

    def test_get_client_failure(self):
        """Test global client retrieval failure."""
        # Clear environment to cause initialization failure
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MCPClientError) as exc_info:
                get_client()

            assert "Failed to initialize global client" in str(exc_info.value)

    def test_initialize_client_success(self, valid_config, mock_successful_client_validation):
        """Test successful client initialization."""
        client = initialize_client(valid_config)

        assert isinstance(client, FirecrawlMCPClient)
        assert client.config == valid_config

        # Global client should be updated
        global_client = get_client()
        assert global_client is client

    def test_initialize_client_failure(self, invalid_config):
        """Test client initialization failure."""
        with pytest.raises(MCPClientError) as exc_info:
            initialize_client(invalid_config)

        assert "Client initialization failed" in str(exc_info.value)

    def test_reset_client(self, test_env, mock_successful_client_validation):
        """Test client reset functionality."""
        # Initialize client
        client1 = get_client()

        # Reset client
        reset_client()

        # Get new client
        client2 = get_client()

        # Should be different instances
        assert client1 is not client2


class TestMCPExceptions:
    """Test suite for MCP exception classes."""

    def test_mcp_error_basic(self):
        """Test basic MCP error functionality."""
        error = MCPError("Test error", error_code="TEST_ERROR")

        assert str(error) == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {}

        error_dict = error.to_dict()
        assert error_dict["error"] == "MCPError"
        assert error_dict["message"] == "Test error"
        assert error_dict["error_code"] == "TEST_ERROR"

    def test_mcp_configuration_error(self):
        """Test MCP configuration error."""
        error = MCPConfigurationError(
            "Config error",
            missing_config="API_KEY",
            invalid_values={"timeout": -1}
        )

        assert error.error_code == "CONFIGURATION_ERROR"
        assert error.details["missing_config"] == "API_KEY"
        assert error.details["invalid_values"]["timeout"] == -1

    def test_mcp_client_error(self):
        """Test MCP client error."""
        error = MCPClientError(
            "Client error",
            client_state="disconnected",
            connection_info={"url": "https://api.firecrawl.dev"}
        )

        assert error.error_code == "CLIENT_ERROR"
        assert error.details["client_state"] == "disconnected"

    def test_mcp_tool_error(self):
        """Test MCP tool error."""
        error = MCPToolError(
            "Tool error",
            tool_name="scrape",
            tool_parameters={"url": "https://example.com"},
            execution_stage="validation"
        )

        assert error.error_code == "TOOL_ERROR"
        assert error.details["tool_name"] == "scrape"
        assert error.details["execution_stage"] == "validation"

    def test_mcp_validation_error(self):
        """Test MCP validation error."""
        error = MCPValidationError(
            "Validation error",
            validation_errors={"url": "Invalid URL format"},
            invalid_field="url",
            expected_type="string"
        )

        assert error.error_code == "VALIDATION_ERROR"
        assert error.details["invalid_field"] == "url"
        assert error.details["expected_type"] == "string"

    def test_handle_firecrawl_error_basic(self):
        """Test basic Firecrawl error handling."""
        original_error = FirecrawlError("Original error")

        mcp_error = handle_firecrawl_error(original_error)

        assert isinstance(mcp_error, MCPError)
        assert "Original error" in str(mcp_error)
        assert mcp_error.details["original_error"] == "FirecrawlError"

    def test_handle_firecrawl_error_with_context(self):
        """Test Firecrawl error handling with context."""
        original_error = BadRequestError("Bad request")
        context = {"tool": "scrape", "url": "https://example.com"}

        mcp_error = handle_firecrawl_error(original_error, context)

        assert isinstance(mcp_error, MCPValidationError)
        assert "tool=scrape" in str(mcp_error)
        assert mcp_error.details["tool"] == "scrape"

    def test_handle_firecrawl_bad_request_error_mapping(self):
        """Test that BadRequestError is mapped to MCPValidationError."""
        original_error = BadRequestError("Bad request")
        mcp_error = handle_firecrawl_error(original_error)

        assert isinstance(mcp_error, MCPValidationError), f"Expected MCPValidationError, got {type(mcp_error).__name__}"

    def test_handle_firecrawl_unauthorized_error_mapping(self):
        """Test that UnauthorizedError is mapped to MCPAuthenticationError."""
        original_error = UnauthorizedError("Unauthorized")
        mcp_error = handle_firecrawl_error(original_error)

        assert isinstance(mcp_error, MCPAuthenticationError), f"Expected MCPAuthenticationError, got {type(mcp_error).__name__}"

    def test_handle_firecrawl_rate_limit_error_mapping(self):
        """Test that RateLimitError is mapped to MCPRateLimitError."""
        original_error = RateLimitError("Rate limited")
        mcp_error = handle_firecrawl_error(original_error)

        assert isinstance(mcp_error, MCPRateLimitError), f"Expected MCPRateLimitError, got {type(mcp_error).__name__}"

    def test_handle_firecrawl_internal_server_error_mapping(self):
        """Test that InternalServerError is mapped to MCPServerError."""
        original_error = InternalServerError("Server error")
        mcp_error = handle_firecrawl_error(original_error)

        assert isinstance(mcp_error, MCPServerError), f"Expected MCPServerError, got {type(mcp_error).__name__}"

    def test_log_error_function(self, caplog):
        """Test error logging function."""
        error = MCPValidationError("Test validation error")
        context = {"operation": "test"}

        mcp_log_error(error, context)

        # Check that error was logged
        assert len(caplog.records) == 1
        assert "MCPValidationError" in caplog.records[0].message
        assert "operation=test" in caplog.records[0].message

    def test_create_error_response_mcp_error(self):
        """Test error response creation for MCP errors."""
        error = MCPToolError("Tool error", tool_name="test_tool")

        response = create_error_response(error)

        assert response["error"] == "MCPToolError"
        assert response["message"] == "Tool error"
        assert response["error_code"] == "TOOL_ERROR"
        assert response["details"]["tool_name"] == "test_tool"

    def test_create_error_response_generic_error(self):
        """Test error response creation for generic errors."""
        error = ValueError("Generic error")

        response = create_error_response(error)

        assert response["error"] == "ValueError"
        assert response["message"] == "Generic error"
        assert response["error_code"] == "UNKNOWN_ERROR"
        assert response["details"] == {}


class TestErrorInheritance:
    """Test suite for MCP error inheritance and compatibility."""

    def test_authentication_error_inheritance(self):
        """Test that MCPAuthenticationError inherits from both UnauthorizedError and MCPError."""
        error = MCPAuthenticationError("Auth failed")

        assert isinstance(error, UnauthorizedError)
        assert isinstance(error, MCPError)
        assert error.status_code == 401

    def test_rate_limit_error_inheritance(self):
        """Test that MCPRateLimitError inherits from both RateLimitError and MCPError."""
        error = MCPRateLimitError("Rate limited", limit=100, current_usage=150)

        assert isinstance(error, RateLimitError)
        assert isinstance(error, MCPError)
        assert error.status_code == 429
        assert error.details["limit"] == 100

    def test_server_error_inheritance(self):
        """Test that MCPServerError inherits from both InternalServerError and MCPError."""
        error = MCPServerError("Server error", component="database")

        assert isinstance(error, InternalServerError)
        assert isinstance(error, MCPError)
        assert error.status_code == 500
        assert error.details["component"] == "database"


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration test scenarios that require external dependencies."""

    @pytest.mark.skipif(not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not available")
    def test_real_client_initialization(self):
        """Test client initialization with real API key."""
        # This test only runs if FIRECRAWL_API_KEY is available
        config = MCPConfig()
        client = FirecrawlMCPClient(config)

        assert client.is_connected() is True

        # Test connection validation
        result = client.validate_connection()
        assert result["status"] == "connected"

    def test_config_with_missing_environment(self):
        """Test configuration behavior with completely clean environment."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                MCPConfig()

            assert "Configuration validation failed" in str(exc_info.value)
            assert "FIRECRAWL_API_KEY is required" in str(exc_info.value)
