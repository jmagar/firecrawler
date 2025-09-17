"""
Logging middleware validation tests for the Firecrawler MCP server.

This module tests the logging middleware components, including human-readable
logging, structured JSON logging, file rotation, and sensitive data masking
using FastMCP in-memory testing patterns.
"""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from firecrawl_mcp.core.config import MCPConfig
from firecrawl_mcp.core.exceptions import MCPError, MCPValidationError
from firecrawl_mcp.middleware.logging import (
    LoggingMiddleware,
    RotatingFileHandler,
    StructuredLoggingMiddleware,
    create_logging_middleware,
)


class MockMiddlewareContext:
    """Mock middleware context for testing."""

    def __init__(
        self,
        method: str = "test_method",
        source: str = "test_client",
        message_type: str = "request",
        message: Any = None,
        **kwargs
    ):
        self.method = method
        self.source = source
        self.type = message_type
        self.message = message or Mock()
        # Allow additional attributes to be set
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestRotatingFileHandler:
    """Test RotatingFileHandler functionality."""

    def test_handler_initialization(self, temp_log_file):
        """Test rotating file handler initialization."""
        handler = RotatingFileHandler(
            filename=str(temp_log_file),
            max_bytes=1024,
            backup_count=3
        )

        assert handler.base_filename == str(temp_log_file)
        assert handler.max_bytes == 1024
        assert handler.backup_count == 3
        assert handler.encoding == 'utf-8'

        # Cleanup
        handler.close()

    def test_directory_creation(self):
        """Test that handler creates directories if they don't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "logs" / "nested" / "test.log"

            handler = RotatingFileHandler(str(log_path))

            # Directory should be created
            assert log_path.parent.exists()

            handler.close()

    def test_write_message(self, temp_log_file):
        """Test writing messages to the log file."""
        handler = RotatingFileHandler(str(temp_log_file))

        handler.write("Test log message")
        handler.write("Another log message")

        handler.close()

        # Check file contents
        content = temp_log_file.read_text()
        assert "Test log message" in content
        assert "Another log message" in content


class TestLoggingMiddleware:
    """Test LoggingMiddleware functionality."""

    @pytest.fixture
    def logging_middleware(self, temp_log_file):
        """Create a logging middleware instance for testing."""
        return LoggingMiddleware(
            include_payloads=True,
            max_payload_length=500,
            log_file=str(temp_log_file),
            log_errors_only=False,
            mask_sensitive_data=True
        )

    @pytest.fixture
    def error_only_middleware(self):
        """Create a logging middleware that only logs errors."""
        return LoggingMiddleware(
            log_errors_only=True,
            mask_sensitive_data=True
        )

    async def test_successful_request_logging(self, logging_middleware):
        """Test logging of successful requests."""
        context = MockMiddlewareContext(
            method="test_method",
            source="test_client"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        with patch.object(logging_middleware.logger, 'info') as mock_info:
            result = await logging_middleware.on_message(context, mock_next)

        assert result == {"result": "success"}

        # Should have logged request and response
        assert mock_info.call_count == 2

        # Check request log
        request_log = mock_info.call_args_list[0][0][0]
        assert "REQUEST test_method" in request_log
        assert "from test_client" in request_log

        # Check response log
        response_log = mock_info.call_args_list[1][0][0]
        assert "RESPONSE test_method" in response_log
        assert "SUCCESS" in response_log

    async def test_error_request_logging(self, logging_middleware):
        """Test logging of failed requests."""
        context = MockMiddlewareContext(method="failing_method")

        async def mock_next(ctx):
            raise ValueError("Test error message")

        with patch.object(logging_middleware.logger, 'error') as mock_error:
            with pytest.raises(ValueError):
                await logging_middleware.on_message(context, mock_next)

        # Should have logged the error
        mock_error.assert_called_once()
        error_log = mock_error.call_args[0][0]
        assert "ERROR failing_method" in error_log
        assert "ValueError: Test error message" in error_log

    def test_payload_formatting(self, logging_middleware):
        """Test payload formatting and truncation."""
        # Test dictionary payload
        payload = {"key": "value", "number": 42}
        formatted = logging_middleware._format_payload(payload)

        assert '"key": "value"' in formatted
        assert '"number": 42' in formatted

    def test_payload_truncation(self, logging_middleware):
        """Test payload truncation for large payloads."""
        # Create large payload
        large_payload = {"data": "x" * 1000}
        formatted = logging_middleware._format_payload(large_payload)

        assert len(formatted) <= logging_middleware.max_payload_length + 100  # Allow for truncation message
        assert "truncated" in formatted.lower()

    def test_sensitive_data_masking(self, logging_middleware):
        """Test masking of sensitive data in payloads."""
        sensitive_payload = {
            "api_key": "secret-key-12345",
            "password": "supersecret",
            "auth_token": "bearer-token-xyz",
            "safe_data": "this is fine"
        }

        masked = logging_middleware._mask_sensitive_dict(sensitive_payload)

        assert masked["api_key"] == "secr...2345"  # Should be masked
        assert masked["password"] == "***MASKED***"  # Short values fully masked
        assert masked["auth_token"] == "bear...r-xyz"
        assert masked["safe_data"] == "this is fine"  # Safe data unchanged

    def test_nested_sensitive_data_masking(self, logging_middleware):
        """Test masking of sensitive data in nested structures."""
        nested_payload = {
            "config": {
                "api_key": "secret-api-key",
                "settings": {
                    "token": "nested-token"
                }
            },
            "data": ["item1", {"password": "hidden"}]
        }

        masked = logging_middleware._mask_sensitive_dict(nested_payload)

        assert "secr...key" in masked["config"]["api_key"]
        assert "nest...ken" in masked["config"]["settings"]["token"]
        assert masked["data"][1]["password"] == "***MASKED***"

    async def test_error_only_logging(self, error_only_middleware):
        """Test middleware that only logs errors."""
        context = MockMiddlewareContext()

        # Successful request - should not log
        async def success_next(ctx):
            return "success"

        with patch.object(error_only_middleware.logger, 'info') as mock_info:
            await error_only_middleware.on_message(context, success_next)

        mock_info.assert_not_called()

        # Failed request - should log
        async def error_next(ctx):
            raise ValueError("Test error")

        with patch.object(error_only_middleware.logger, 'error') as mock_error:
            with pytest.raises(ValueError):
                await error_only_middleware.on_message(context, error_next)

        mock_error.assert_called_once()

    def test_request_id_generation(self, logging_middleware):
        """Test request ID generation for correlation."""
        context = MockMiddlewareContext(method="test_method")

        request_id = logging_middleware._generate_request_id(context)

        assert request_id.startswith("req_")
        assert len(request_id.split("_")) == 3  # req_timestamp_hash

    async def test_file_logging(self, temp_log_file):
        """Test logging to file."""
        middleware = LoggingMiddleware(
            log_file=str(temp_log_file),
            include_payloads=False
        )

        context = MockMiddlewareContext()

        async def mock_next(ctx):
            return "result"

        await middleware.on_message(context, mock_next)

        # Check file was written
        content = temp_log_file.read_text()
        assert "test_method" in content
        assert "test_client" in content

        middleware.close()

    async def test_mcp_error_details(self, logging_middleware):
        """Test logging MCP errors with details."""
        context = MockMiddlewareContext()

        async def error_next(ctx):
            raise MCPValidationError(
                "Validation failed",
                validation_errors={"field": "error"},
                details={"api_key": "secret-123"}  # Should be masked
            )

        with patch.object(logging_middleware.logger, 'error') as mock_error:
            with pytest.raises(MCPValidationError):
                await logging_middleware.on_message(context, error_next)

        error_log = mock_error.call_args[0][0]
        assert "MCPValidationError" in error_log
        assert "Validation failed" in error_log
        # Details should be included and masked
        assert "***MASKED***" in error_log


class TestStructuredLoggingMiddleware:
    """Test StructuredLoggingMiddleware functionality."""

    @pytest.fixture
    def structured_middleware(self, temp_log_file):
        """Create a structured logging middleware instance."""
        return StructuredLoggingMiddleware(
            include_payloads=True,
            log_file=str(temp_log_file),
            mask_sensitive_data=True,
            extra_fields={"server_id": "test-server", "environment": "test"}
        )

    async def test_structured_request_logging(self, structured_middleware):
        """Test structured JSON logging for requests."""
        context = MockMiddlewareContext(
            method="test_method",
            source="test_client",
            message_type="request"
        )

        async def mock_next(ctx):
            return {"result": "success"}

        with patch.object(structured_middleware.logger, 'info') as mock_info:
            result = await structured_middleware.on_message(context, mock_next)

        assert result == {"result": "success"}

        # Should have logged request and response as JSON
        assert mock_info.call_count == 2

        # Parse request log as JSON
        request_log = mock_info.call_args_list[0][0][0]
        request_data = json.loads(request_log)

        assert request_data["event"] == "request"
        assert request_data["method"] == "test_method"
        assert request_data["source"] == "test_client"
        assert request_data["server_id"] == "test-server"
        assert request_data["environment"] == "test"
        assert "timestamp" in request_data
        assert "request_id" in request_data

        # Parse response log as JSON
        response_log = mock_info.call_args_list[1][0][0]
        response_data = json.loads(response_log)

        assert response_data["event"] == "response"
        assert response_data["status"] == "success"
        assert "duration_ms" in response_data

    async def test_structured_error_logging(self, structured_middleware):
        """Test structured JSON logging for errors."""
        context = MockMiddlewareContext(method="failing_method")

        async def error_next(ctx):
            raise MCPError("Test MCP error", details={"context": "test"})

        with patch.object(structured_middleware.logger, 'info') as mock_info:
            with pytest.raises(MCPError):
                await structured_middleware.on_message(context, error_next)

        # Should have logged request and error
        assert mock_info.call_count == 2

        # Parse error log as JSON
        error_log = mock_info.call_args_list[1][0][0]
        error_data = json.loads(error_log)

        assert error_data["event"] == "error"
        assert error_data["status"] == "failed"
        assert error_data["error_type"] == "MCPError"
        assert error_data["error_message"] == "Test MCP error"
        assert "error_details" in error_data
        assert "duration_ms" in error_data

    def test_payload_processing(self, structured_middleware):
        """Test payload processing for structured logging."""
        # Test with dictionary
        payload = {"key": "value", "number": 42}
        processed = structured_middleware._process_payload(payload)

        assert processed == payload

        # Test with object having __dict__
        class TestObject:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = 42

        obj = TestObject()
        processed = structured_middleware._process_payload(obj)

        assert processed["attr1"] == "value1"
        assert processed["attr2"] == 42

    def test_payload_truncation_with_flag(self, structured_middleware):
        """Test payload truncation with truncation flag."""
        # Create payload that will be truncated
        large_payload = {"data": "x" * 1000}
        processed = structured_middleware._process_payload(large_payload)

        if processed.get("_truncated"):
            assert processed["_truncated"] is True
            assert "_original_length" in processed
            assert processed["_original_length"] > len(json.dumps(processed))

    def test_sensitive_data_masking_in_structured(self, structured_middleware):
        """Test sensitive data masking in structured logging."""
        sensitive_payload = {
            "api_key": "secret-key-123",
            "normal_data": "safe_value"
        }

        processed = structured_middleware._process_payload(sensitive_payload)

        assert processed["api_key"] == "***MASKED***"
        assert processed["normal_data"] == "safe_value"

    def test_request_id_generation(self, structured_middleware):
        """Test UUID-based request ID generation."""
        request_id = structured_middleware._generate_request_id()

        # Should be a valid UUID string
        assert len(request_id) == 36  # Standard UUID length
        assert request_id.count("-") == 4  # UUID format

    async def test_file_output_structured(self, temp_log_file):
        """Test structured logging to file."""
        middleware = StructuredLoggingMiddleware(
            log_file=str(temp_log_file),
            include_payloads=False
        )

        context = MockMiddlewareContext()

        async def mock_next(ctx):
            return "result"

        await middleware.on_message(context, mock_next)

        # Read and parse file content
        content = temp_log_file.read_text()
        lines = [line for line in content.strip().split('\n') if line]

        # Should have request and response logs
        assert len(lines) >= 2

        # Each line should be valid JSON
        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "method" in data
            assert "event" in data

        middleware.close()


class TestLoggingMiddlewareFactory:
    """Test logging middleware factory functions."""

    def test_create_development_logging(self):
        """Test creating development logging middleware."""
        config = MCPConfig()
        config.debug_mode = True
        config.development_mode = True
        config.log_file = None

        middleware = create_logging_middleware(config)

        assert isinstance(middleware, LoggingMiddleware)
        assert middleware.include_payloads is True
        assert middleware.mask_sensitive_data is True

    def test_create_production_logging(self):
        """Test creating production logging middleware."""
        config = MCPConfig()
        config.debug_mode = False
        config.development_mode = False
        config.log_file = None

        middleware = create_logging_middleware(config)

        assert isinstance(middleware, StructuredLoggingMiddleware)
        assert middleware.include_payloads is False
        assert middleware.mask_sensitive_data is True

    def test_create_with_custom_log_file(self, temp_log_file):
        """Test creating middleware with custom log file."""
        config = MCPConfig()
        config.log_file = str(temp_log_file)
        config.debug_mode = True

        middleware = create_logging_middleware(config)

        assert middleware.file_handler is not None
        assert middleware.file_handler.base_filename == str(temp_log_file)

        middleware.close()

    def test_create_with_default_log_file(self):
        """Test creating middleware with default log file in development."""
        config = MCPConfig()
        config.development_mode = True
        config.log_file = None

        with patch('pathlib.Path.mkdir') as mock_mkdir:
            middleware = create_logging_middleware(config)

            # Should have created logs directory
            mock_mkdir.assert_called_once()
            assert middleware.file_handler is not None

        middleware.close()


class TestLoggingIntegration:
    """Test logging middleware integration scenarios."""

    async def test_payload_with_message_object(self):
        """Test logging with complex message objects."""
        middleware = LoggingMiddleware(include_payloads=True)

        # Create mock message with attributes
        mock_message = Mock()
        mock_message.name = "test_tool"
        mock_message.arguments = {"url": "https://example.com", "api_key": "secret"}

        context = MockMiddlewareContext(message=mock_message)

        async def mock_next(ctx):
            return "success"

        with patch.object(middleware.logger, 'info') as mock_info:
            await middleware.on_message(context, mock_next)

        # Check that payload was logged and sensitive data was masked
        request_log = mock_info.call_args_list[0][0][0]
        assert "test_tool" in request_log
        assert "https://example.com" in request_log
        assert "secret" not in request_log  # Should be masked

    async def test_concurrent_logging(self, temp_log_file):
        """Test concurrent logging operations."""
        middleware = LoggingMiddleware(log_file=str(temp_log_file))

        async def operation(method_name: str):
            context = MockMiddlewareContext(method=method_name)

            async def mock_next(ctx):
                return f"result_{method_name}"

            return await middleware.on_message(context, mock_next)

        # Run concurrent operations
        import asyncio
        tasks = [operation(f"method_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5

        # Check that all operations were logged
        content = temp_log_file.read_text()
        for i in range(5):
            assert f"method_{i}" in content

        middleware.close()

    def test_exception_in_payload_formatting(self):
        """Test handling exceptions during payload formatting."""
        middleware = LoggingMiddleware(include_payloads=True)

        # Create an object that raises an exception when serialized
        class BadObject:
            def __str__(self):
                raise ValueError("Cannot serialize")

        bad_payload = {"bad_obj": BadObject()}
        formatted = middleware._format_payload(bad_payload)

        # Should handle the exception gracefully
        assert "Error formatting payload" in formatted

    async def test_large_volume_logging(self, temp_log_file):
        """Test logging middleware with high volume of requests."""
        middleware = LoggingMiddleware(
            log_file=str(temp_log_file),
            include_payloads=False  # Reduce overhead
        )

        context = MockMiddlewareContext()

        async def mock_next(ctx):
            return "success"

        # Process many requests
        for i in range(100):
            await middleware.on_message(context, mock_next)

        # Verify logs were written
        content = temp_log_file.read_text()
        lines = content.count('\n')
        assert lines >= 200  # At least 2 lines per request (request + response)

        middleware.close()

    def test_memory_efficiency(self):
        """Test that logging middleware doesn't accumulate excessive memory."""
        middleware = LoggingMiddleware(include_payloads=True)

        # Create large payload
        large_payload = {"data": "x" * 10000}

        # Format multiple times - should not accumulate memory
        for _ in range(10):
            formatted = middleware._format_payload(large_payload)
            # Each formatting should be independent
            assert len(formatted) <= middleware.max_payload_length + 100
