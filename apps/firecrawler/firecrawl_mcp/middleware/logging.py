"""
Request/response logging middleware with rotating files for the Firecrawler MCP server.

This module provides comprehensive logging middleware that captures request/response
data with rotating file support, structured logging, and configurable payload handling
following FastMCP patterns.
"""

import json
import logging
import logging.handlers
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from ..core.exceptions import MCPError

logger = logging.getLogger(__name__)


class RotatingFileHandler:
    """
    Custom rotating file handler for MCP logs with automatic directory creation.
    """

    def __init__(
        self,
        filename: str,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        encoding: str = 'utf-8'
    ):
        """
        Initialize rotating file handler.
        
        Args:
            filename: Path to log file
            max_bytes: Maximum file size before rotation
            backup_count: Number of backup files to keep
            encoding: File encoding
        """
        self.base_filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding

        # Ensure directory exists
        log_dir = Path(filename).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Set up rotating handler
        self.handler = logging.handlers.RotatingFileHandler(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding
        )

        # Configure formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.handler.setFormatter(formatter)

    def write(self, message: str) -> None:
        """Write message to log file."""
        # Create a temporary logger for this handler
        temp_logger = logging.getLogger(f"mcp_log_{id(self)}")
        temp_logger.setLevel(logging.INFO)

        # Remove any existing handlers to avoid duplicates
        temp_logger.handlers.clear()
        temp_logger.addHandler(self.handler)
        temp_logger.propagate = False

        # Log the message
        temp_logger.info(message)

    def close(self) -> None:
        """Close the file handler."""
        self.handler.close()


class LoggingMiddleware(Middleware):
    """
    Human-readable logging middleware with optional payload logging.
    
    Provides comprehensive request/response logging with configurable detail levels,
    payload logging, and automatic file rotation.
    """

    def __init__(
        self,
        logger_name: str | None = None,
        include_payloads: bool = False,
        max_payload_length: int = 1000,
        log_file: str | None = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        log_errors_only: bool = False,
        mask_sensitive_data: bool = True
    ):
        """
        Initialize logging middleware.
        
        Args:
            logger_name: Custom logger name
            include_payloads: Whether to include request/response payloads
            max_payload_length: Maximum payload length to log
            log_file: Path to log file for file logging
            max_file_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            log_errors_only: Whether to log only errors and warnings
            mask_sensitive_data: Whether to mask sensitive data in logs
        """
        self.logger = logging.getLogger(logger_name or f"{__name__}.request_logger")
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length
        self.log_errors_only = log_errors_only
        self.mask_sensitive_data = mask_sensitive_data

        # Set up file logging if specified
        self.file_handler = None
        if log_file:
            self.file_handler = RotatingFileHandler(
                filename=log_file,
                max_bytes=max_file_size,
                backup_count=backup_count
            )

        # Sensitive field patterns to mask
        self.sensitive_patterns = {
            'api_key', 'token', 'password', 'secret', 'auth', 'authorization',
            'firecrawl_api_key', 'openai_api_key', 'auth_token'
        }

    async def on_message(self, context: MiddlewareContext, call_next):
        """Log all MCP messages."""
        start_time = time.time()
        request_id = self._generate_request_id(context)

        # Log incoming request
        if not self.log_errors_only:
            await self._log_request(context, request_id)

        try:
            result = await call_next(context)

            # Log successful response
            if not self.log_errors_only:
                duration_ms = (time.time() - start_time) * 1000
                await self._log_response(context, result, request_id, duration_ms, success=True)

            return result

        except Exception as error:
            # Always log errors
            duration_ms = (time.time() - start_time) * 1000
            await self._log_error(context, error, request_id, duration_ms)
            raise

    def _generate_request_id(self, context: MiddlewareContext) -> str:
        """Generate unique request ID for correlation."""
        timestamp = int(time.time() * 1000)
        method_hash = hash(context.method) % 10000
        return f"req_{timestamp}_{method_hash:04d}"

    async def _log_request(self, context: MiddlewareContext, request_id: str) -> None:
        """Log incoming request."""
        message_parts = [
            f"[{request_id}]",
            f"REQUEST {context.method}",
            f"from {context.source}"
        ]

        if context.type:
            message_parts.append(f"type={context.type}")

        log_message = " ".join(message_parts)

        # Add payload if enabled
        if self.include_payloads and hasattr(context, 'message'):
            payload = self._format_payload(context.message)
            if payload:
                log_message += f"\nPayload: {payload}"

        await self._write_log_mcp(context, log_message, level="info")

    async def _log_response(
        self,
        context: MiddlewareContext,
        result: Any,
        request_id: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """Log response."""
        status = "SUCCESS" if success else "FAILED"

        message_parts = [
            f"[{request_id}]",
            f"RESPONSE {context.method}",
            status,
            f"in {duration_ms:.2f}ms"
        ]

        log_message = " ".join(message_parts)

        # Add response payload if enabled
        if self.include_payloads and result is not None:
            payload = self._format_payload(result)
            if payload:
                log_message += f"\nResponse: {payload}"

        log_level = "info" if success else "error"
        await self._write_log_mcp(context, log_message, level=log_level)

    async def _log_error(
        self,
        context: MiddlewareContext,
        error: Exception,
        request_id: str,
        duration_ms: float
    ) -> None:
        """Log error details."""
        error_type = type(error).__name__

        message_parts = [
            f"[{request_id}]",
            f"ERROR {context.method}",
            f"{error_type}: {error!s}",
            f"after {duration_ms:.2f}ms"
        ]

        log_message = " ".join(message_parts)

        # Add stack trace for server errors
        if isinstance(error, MCPError) and hasattr(error, 'details'):
            if error.details:
                details = self._mask_sensitive_dict(error.details) if self.mask_sensitive_data else error.details
                log_message += f"\nError details: {json.dumps(details, indent=2)}"

        # Add traceback for debugging
        log_message += f"\nTraceback:\n{traceback.format_exc()}"

        await self._write_log_mcp(context, log_message, level="error")

    def _format_payload(self, payload: Any) -> str | None:
        """Format payload for logging with length limits."""
        try:
            if payload is None:
                return None

            # Convert to JSON string
            if hasattr(payload, '__dict__'):
                payload_dict = payload.__dict__
            elif isinstance(payload, dict):
                payload_dict = payload
            else:
                payload_dict = {"data": str(payload)}

            # Mask sensitive data
            if self.mask_sensitive_data:
                payload_dict = self._mask_sensitive_dict(payload_dict)

            # Convert to JSON
            payload_str = json.dumps(payload_dict, indent=2, default=str)

            # Truncate if too long
            if len(payload_str) > self.max_payload_length:
                truncated = payload_str[:self.max_payload_length]
                payload_str = f"{truncated}... [truncated, total length: {len(payload_str)}]"

            return payload_str

        except Exception as e:
            return f"[Error formatting payload: {e}]"

    def _mask_sensitive_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive data in dictionary."""
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            key_lower = key.lower()

            # Check if key contains sensitive patterns
            if any(pattern in key_lower for pattern in self.sensitive_patterns):
                if value:
                    masked[key] = self._mask_value(str(value))
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_dict(value)
            elif isinstance(value, list):
                masked[key] = [
                    self._mask_sensitive_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value

        return masked

    def _mask_value(self, value: str) -> str:
        """Mask a sensitive value."""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    async def _write_log_mcp(self, context: MiddlewareContext, message: str, level: str = "info") -> None:
        """Write log message to MCP context and optionally to file."""
        # Log to MCP context for client visibility
        if context.fastmcp_context:
            if level == "debug":
                await context.fastmcp_context.debug(message)
            elif level == "info":
                await context.fastmcp_context.info(message)
            elif level == "warning":
                await context.fastmcp_context.warning(message)
            elif level == "error":
                await context.fastmcp_context.error(message)

        # Also log to file if file handler is configured for local debugging
        if self.file_handler:
            timestamp = datetime.now(UTC).isoformat()
            file_message = f"{timestamp} - {level.upper()} - {message}"
            self.file_handler.write(file_message)

    def close(self) -> None:
        """Clean up resources."""
        if self.file_handler:
            self.file_handler.close()


class StructuredLoggingMiddleware(Middleware):
    """
    JSON-structured logging middleware for log aggregation tools.
    
    Provides machine-readable JSON logs suitable for ingestion by log aggregation
    and monitoring systems like ELK stack, Splunk, or cloud logging services.
    """

    def __init__(
        self,
        logger_name: str | None = None,
        include_payloads: bool = False,
        max_payload_length: int = 1000,
        log_file: str | None = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        mask_sensitive_data: bool = True,
        extra_fields: dict[str, Any] | None = None
    ):
        """
        Initialize structured logging middleware.
        
        Args:
            logger_name: Custom logger name
            include_payloads: Whether to include payloads in logs
            max_payload_length: Maximum payload length
            log_file: Path to JSON log file
            max_file_size: Maximum file size before rotation
            backup_count: Number of backup files
            mask_sensitive_data: Whether to mask sensitive data
            extra_fields: Additional fields to include in all log entries
        """
        self.logger = logging.getLogger(logger_name or f"{__name__}.structured_logger")
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length
        self.mask_sensitive_data = mask_sensitive_data
        self.extra_fields = extra_fields or {}

        # Set up file logging
        self.file_handler = None
        if log_file:
            self.file_handler = RotatingFileHandler(
                filename=log_file,
                max_bytes=max_file_size,
                backup_count=backup_count
            )

        # Sensitive field patterns
        self.sensitive_patterns = {
            'api_key', 'token', 'password', 'secret', 'auth', 'authorization',
            'firecrawl_api_key', 'openai_api_key', 'auth_token'
        }

    async def on_message(self, context: MiddlewareContext, call_next):
        """Log messages in structured JSON format."""
        start_time = time.time()
        request_id = self._generate_request_id()

        # Create base log entry
        base_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "method": context.method,
            "source": context.source,
            "type": context.type,
            **self.extra_fields
        }

        # Log request
        request_entry = {
            **base_entry,
            "event": "request",
        }

        if self.include_payloads and hasattr(context, 'message'):
            payload = self._process_payload(context.message)
            if payload:
                request_entry["request_payload"] = payload

        await self._write_structured_log_mcp(context, request_entry)

        try:
            result = await call_next(context)

            # Log successful response
            duration_ms = (time.time() - start_time) * 1000
            response_entry = {
                **base_entry,
                "event": "response",
                "status": "success",
                "duration_ms": round(duration_ms, 2)
            }

            if self.include_payloads and result is not None:
                payload = self._process_payload(result)
                if payload:
                    response_entry["response_payload"] = payload

            await self._write_structured_log_mcp(context, response_entry)
            return result

        except Exception as error:
            # Log error response
            duration_ms = (time.time() - start_time) * 1000
            error_entry = {
                **base_entry,
                "event": "error",
                "status": "failed",
                "duration_ms": round(duration_ms, 2),
                "error_type": type(error).__name__,
                "error_message": str(error)
            }

            # Add error details for MCP errors
            if isinstance(error, MCPError):
                error_details = error.to_dict()
                if self.mask_sensitive_data:
                    error_details = self._mask_sensitive_dict(error_details)
                error_entry["error_details"] = error_details

            await self._write_structured_log_mcp(context, error_entry)
            raise

    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())

    def _process_payload(self, payload: Any) -> dict[str, Any] | None:
        """Process payload for structured logging."""
        try:
            if payload is None:
                return None

            # Convert to dictionary
            if hasattr(payload, '__dict__'):
                payload_dict = payload.__dict__
            elif isinstance(payload, dict):
                payload_dict = payload.copy()
            else:
                payload_dict = {"data": payload}

            # Mask sensitive data
            if self.mask_sensitive_data:
                payload_dict = self._mask_sensitive_dict(payload_dict)

            # Truncate large payloads
            payload_str = json.dumps(payload_dict, default=str)
            if len(payload_str) > self.max_payload_length:
                payload_dict["_truncated"] = True
                payload_dict["_original_length"] = len(payload_str)
                # Keep truncating until under limit
                while len(json.dumps(payload_dict, default=str)) > self.max_payload_length:
                    if isinstance(payload_dict.get("data"), str):
                        payload_dict["data"] = payload_dict["data"][:self.max_payload_length // 2]
                    else:
                        break

            return payload_dict

        except Exception as e:
            return {"error": f"Failed to process payload: {e}"}

    def _mask_sensitive_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive data in dictionary."""
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            key_lower = key.lower()

            if any(pattern in key_lower for pattern in self.sensitive_patterns):
                if value:
                    masked[key] = "***MASKED***"
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_dict(value)
            elif isinstance(value, list):
                masked[key] = [
                    self._mask_sensitive_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value

        return masked

    async def _write_structured_log_mcp(self, context: MiddlewareContext, log_entry: dict[str, Any]) -> None:
        """Write structured log entry to MCP context and optionally to file."""
        # Convert to JSON string
        log_line = json.dumps(log_entry, separators=(',', ':'), default=str)

        # Log to MCP context for client visibility
        if context.fastmcp_context:
            # Determine log level based on event type
            event = log_entry.get("event", "info")
            if event == "error":
                await context.fastmcp_context.error(log_line)
            elif event == "warning":
                await context.fastmcp_context.warning(log_line)
            else:
                await context.fastmcp_context.info(log_line)

        # Write to file if configured for local debugging
        if self.file_handler:
            self.file_handler.write(log_line)

    def close(self) -> None:
        """Clean up resources."""
        if self.file_handler:
            self.file_handler.close()


# Factory function removed - use direct instantiation with FastMCP
# Example:
# mcp.add_middleware(LoggingMiddleware(include_payloads=True, log_file="logs/mcp.log"))
# mcp.add_middleware(StructuredLoggingMiddleware(mask_sensitive_data=True))
