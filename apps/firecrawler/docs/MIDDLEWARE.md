# Middleware Implementation and Customization Guide

Firecrawler MCP server implements a comprehensive middleware system for request processing, performance monitoring, logging, rate limiting, and error handling. This guide covers middleware architecture, implementation patterns, and customization approaches.

## Architecture Overview

The middleware system follows FastMCP patterns with a pipeline-based architecture. Middleware components execute in sequence, providing cross-cutting functionality across all MCP operations.

### Middleware Chain Execution

```
Request → Timing → Logging → Rate Limiting → Error Handling → Tool/Resource → Response
```

Each middleware can:
- Inspect and modify incoming requests
- Execute business logic before/after handlers
- Transform responses and handle errors
- Maintain state and metrics across requests

## Core Middleware Components

### 1. Timing Middleware (`timing.py`)

Performance monitoring and metrics collection for all MCP operations.

**Features:**
- Request duration tracking with millisecond precision
- Operation-specific timing (tools, resources, prompts)
- Performance threshold alerting
- Metrics aggregation and reporting

**Implementation Pattern:**
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
import time

class TimingMiddleware(Middleware):
    async def on_request(self, context: MiddlewareContext, call_next):
        start_time = time.perf_counter()
        
        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000
            context.logger.info(f"Request {context.method} completed in {duration_ms:.2f}ms")
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            context.logger.error(f"Request {context.method} failed after {duration_ms:.2f}ms: {e}")
            raise
```

**Configuration:**
- `performance_threshold_ms`: Alert threshold for slow operations
- `detailed_timing`: Enable per-operation timing
- `metrics_aggregation`: Collect timing statistics

### 2. Logging Middleware (`logging.py`)

Comprehensive request/response logging with structured output and file rotation.

**Features:**
- Request/response logging with configurable detail levels
- Rotating file handlers (5MB, 1 backup)
- Structured logging with JSON output support
- Error-specific logging with stack traces

**Log Files:**
- `logs/firecrawler.log`: Primary application log
- `logs/middleware.log`: Middleware-specific operations

**Implementation Pattern:**
```python
class LoggingMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        self.logger.info(
            f"Processing {context.method}",
            extra={
                "method": context.method,
                "source": context.source,
                "timestamp": context.timestamp.isoformat()
            }
        )
        
        try:
            result = await call_next(context)
            self.logger.info(f"Completed {context.method}")
            return result
        except Exception as e:
            self.logger.error(f"Failed {context.method}: {e}", exc_info=True)
            raise
```

### 3. Rate Limiting Middleware (`rate_limit.py`)

Token bucket rate limiting following Firecrawl API patterns with client tracking.

**Features:**
- Per-client rate limiting with token bucket algorithm
- Configurable request rates and burst capacity
- Automatic backoff and retry handling
- API quota monitoring and warnings

**Implementation Pattern:**
```python
from collections import defaultdict
from fastmcp.exceptions import ToolError
import time

class RateLimitMiddleware(Middleware):
    def __init__(self, requests_per_minute: int = 60, burst_capacity: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_capacity = burst_capacity
        self.client_buckets = defaultdict(lambda: {"tokens": burst_capacity, "last_refill": time.time()})
    
    async def on_request(self, context: MiddlewareContext, call_next):
        client_id = self._get_client_id(context)
        
        if not self._consume_token(client_id):
            raise ToolError("Rate limit exceeded. Please retry later.")
        
        return await call_next(context)
```

**Configuration:**
- `requests_per_minute`: Base rate limit per client
- `burst_capacity`: Maximum burst requests allowed
- `client_identification`: Method for identifying clients

### 4. Error Handling Middleware (`error_handling.py`)

Standardized error processing and response formatting for consistent MCP error responses.

**Features:**
- Exception mapping to MCP error codes
- Error aggregation and reporting
- Automatic retry for transient failures
- Structured error responses with context

**Implementation Pattern:**
```python
from fastmcp.exceptions import ToolError, ResourceError
import logging

class ErrorHandlingMiddleware(Middleware):
    def __init__(self):
        self.logger = logging.getLogger("error_handler")
        self.error_counts = defaultdict(int)
    
    async def on_message(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)
        except Exception as error:
            error_key = f"{type(error).__name__}:{context.method}"
            self.error_counts[error_key] += 1
            
            self.logger.error(
                f"Error in {context.method}",
                extra={
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "method": context.method,
                    "count": self.error_counts[error_key]
                },
                exc_info=True
            )
            
            # Transform to appropriate MCP error
            if isinstance(error, (ConnectionError, TimeoutError)):
                raise ToolError(f"Service temporarily unavailable: {error}")
            
            raise
```

## Middleware Configuration

### Server Integration

Middleware is registered with the FastMCP server in execution order:

```python
from fastmcp import FastMCP
from firecrawl_mcp.middleware import (
    TimingMiddleware,
    LoggingMiddleware, 
    RateLimitMiddleware,
    ErrorHandlingMiddleware
)

def create_server():
    mcp = FastMCP("Firecrawler")
    
    # Add middleware in execution order
    mcp.add_middleware(ErrorHandlingMiddleware())
    mcp.add_middleware(RateLimitMiddleware(requests_per_minute=120))
    mcp.add_middleware(TimingMiddleware())
    mcp.add_middleware(LoggingMiddleware())
    
    return mcp
```

### Environment Configuration

Middleware behavior is configured through environment variables:

```bash
# Rate Limiting
FIRECRAWLER_RATE_LIMIT_REQUESTS=120
FIRECRAWLER_RATE_LIMIT_BURST=20

# Logging
FIRECRAWLER_LOG_LEVEL=INFO
FIRECRAWLER_LOG_FORMAT=structured

# Performance
FIRECRAWLER_PERFORMANCE_THRESHOLD_MS=5000
FIRECRAWLER_DETAILED_TIMING=true

# Error Handling
FIRECRAWLER_RETRY_ATTEMPTS=3
FIRECRAWLER_ERROR_REPORTING=true
```

## Custom Middleware Development

### Creating Custom Middleware

Extend the FastMCP `Middleware` base class and implement relevant hooks:

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext

class CustomAuthMiddleware(Middleware):
    def __init__(self, required_token: str):
        self.required_token = required_token
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Check tool-specific authorization
        tool_name = context.message.name
        
        if tool_name in ["admin_config", "delete_data"]:
            # Verify admin privileges
            if not self._has_admin_access(context):
                raise ToolError("Access denied: admin privileges required")
        
        return await call_next(context)
    
    def _has_admin_access(self, context: MiddlewareContext) -> bool:
        # Implementation specific to your auth system
        auth_header = getattr(context, 'auth_header', None)
        return auth_header == f"Bearer {self.required_token}"
```

### Middleware Hooks

Available hooks for targeting specific operations:

- `on_message`: All MCP messages (requests and notifications)
- `on_request`: MCP requests expecting responses
- `on_notification`: Fire-and-forget notifications
- `on_call_tool`: Tool execution operations
- `on_read_resource`: Resource access operations
- `on_get_prompt`: Prompt retrieval operations
- `on_list_*`: Component listing operations

### State Management

Share state between middleware and tools using FastMCP Context:

```python
class StateTrackingMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Set state for tool access
        if context.fastmcp_context:
            context.fastmcp_context.set_state("request_id", str(uuid.uuid4()))
            context.fastmcp_context.set_state("start_time", time.time())
        
        result = await call_next(context)
        
        # Tools can access this state via context.get_state()
        return result
```

## Performance Optimization

### Middleware Efficiency

- Minimize processing overhead on request path
- Use async patterns throughout middleware chain
- Cache configuration and computed values
- Implement efficient algorithms for rate limiting and metrics

### Resource Management

```python
class ResourceAwareMiddleware(Middleware):
    def __init__(self):
        self.connection_pool = aiohttp.ClientSession()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection_pool.close()
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Use connection pool for external requests
        # Proper cleanup handled in __aexit__
        return await call_next(context)
```

## Monitoring and Observability

### Metrics Collection

Middleware provides comprehensive metrics for monitoring:

```python
# Performance metrics
request_duration_histogram
error_rate_counter
rate_limit_violations_counter

# Business metrics  
tools_executed_counter
resources_accessed_counter
api_quota_utilization_gauge
```

### Health Checks

Middleware components expose health status:

```python
class HealthCheckMiddleware(Middleware):
    def get_health_status(self) -> dict:
        return {
            "timing": {"status": "healthy", "avg_duration_ms": 45.2},
            "rate_limiting": {"status": "healthy", "violations_last_hour": 0},
            "logging": {"status": "healthy", "log_files_writable": True},
            "error_handling": {"status": "healthy", "error_rate_5min": 0.1}
        }
```

## Troubleshooting

### Common Issues

**High Request Latency:**
- Check timing middleware for performance bottlenecks
- Review rate limiting configuration
- Optimize middleware chain order

**Rate Limit Violations:**
- Adjust `requests_per_minute` and `burst_capacity`
- Implement client identification improvements
- Add retry logic with exponential backoff

**Log File Issues:**
- Verify `logs/` directory permissions
- Check disk space for log rotation
- Validate log level configuration

**Error Handling Problems:**
- Review error mapping configuration
- Check exception propagation chain
- Validate MCP error response format

### Debug Mode

Enable debug logging for detailed middleware operation traces:

```bash
export FIRECRAWLER_LOG_LEVEL=DEBUG
export FIRECRAWLER_MIDDLEWARE_DEBUG=true
```

This provides detailed logs of middleware execution, timing, and state transitions for troubleshooting complex issues.