# Middleware Development Guide

This directory implements FastMCP middleware components for request processing, performance monitoring, logging, rate limiting, and error handling.

## Implementation Patterns

### FastMCP Middleware Structure
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError
import time

class TimingMiddleware(Middleware):
    """Track request processing time and performance metrics."""
    
    def __init__(self, log_slow_requests: bool = True, slow_request_threshold_ms: float = 1000.0):
        self.log_slow_requests = log_slow_requests
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def on_request(self, context: MiddlewareContext, call_next):
        """FastMCP hook for timing all requests."""
        start_time = time.perf_counter()
        
        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log using FastMCP context for client visibility
            if context.fastmcp_context:
                if self.log_slow_requests and duration_ms > self.slow_request_threshold_ms:
                    await context.fastmcp_context.warning(f"SLOW REQUEST: {context.method} completed in {duration_ms:.2f}ms")
                else:
                    await context.fastmcp_context.debug(f"{context.method} completed in {duration_ms:.2f}ms")
            
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            if context.fastmcp_context:
                await context.fastmcp_context.error(f"{context.method} failed after {duration_ms:.2f}ms: {e}")
            raise
```

## Middleware Components

### timing.py
- **PerformanceTracker**: Monitors request/response timing
- **MetricsCollector**: Aggregates performance statistics
- **ThresholdAlerting**: Warns on slow operations
- **PerformanceLogger**: Detailed timing logs for analysis

### logging.py
- **RequestLogger**: Logs all incoming requests with parameters
- **ResponseLogger**: Logs operation results and outcomes
- **ErrorLogger**: Detailed error logging with stack traces
- **RotatingFileHandler**: Manages log file rotation and cleanup

### rate_limit.py
- **RateLimiter**: Token bucket implementation following Firecrawl API patterns
- **ClientTracker**: Per-client rate limit tracking
- **BackoffManager**: Exponential backoff for rate limit violations
- **QuotaMonitor**: API quota and credit usage tracking

### error_handling.py
- **ErrorProcessor**: Standardizes error response formatting
- **ExceptionMapper**: Maps internal exceptions to MCP errors
- **RetryLogic**: Automatic retry for transient failures
- **ErrorReporter**: Error aggregation and reporting

## Best Practices

### Context Injection
- Use FastMCP MiddlewareContext for middleware operations
- Access FastMCP context through `context.fastmcp_context`
- Use `await context.fastmcp_context.info()`, `debug()`, `warning()`, `error()` for client-visible logging
- Store request metadata in context for downstream middleware access
- Access request details via `context.method`, `context.source`, `context.message`

### Error Propagation
- Catch and wrap exceptions appropriately
- Preserve original error context and stack traces
- Return structured error responses to MCP clients
- Log errors with appropriate severity levels

### Performance Optimization
- Minimize middleware overhead on request path
- Use async patterns throughout middleware chain
- Implement efficient rate limiting algorithms
- Cache configuration and computed values

### Resource Management
- Close file handles and connections properly
- Implement proper cleanup in middleware teardown
- Monitor memory usage in long-running operations
- Use connection pooling for external services

## Integration Patterns

### Middleware Chain Order
1. **Timing**: First to capture complete request duration
2. **Logging**: Early logging of incoming requests
3. **Rate Limiting**: Check limits before processing
4. **Error Handling**: Last to catch all exceptions

### Configuration Integration
```python
from fastmcp.server.middleware import Middleware, MiddlewareContext
from firecrawl_mcp.middleware.timing import TimingMiddleware
from firecrawl_mcp.middleware.logging import LoggingMiddleware
from firecrawl_mcp.middleware.rate_limit import RateLimitingMiddleware
from firecrawl_mcp.middleware.error_handling import ErrorHandlingMiddleware

# Configure and register middleware with FastMCP server
def setup_middleware(mcp: FastMCP):
    """Configure middleware based on environment settings."""
    
    # Add middleware in proper order
    mcp.add_middleware(TimingMiddleware(
        log_slow_requests=True,
        slow_request_threshold_ms=1000.0
    ))
    
    mcp.add_middleware(LoggingMiddleware(
        include_payloads=False,
        log_errors_only=False
    ))
    
    mcp.add_middleware(RateLimitingMiddleware(
        requests_per_minute=100,
        burst_size=10
    ))
    
    mcp.add_middleware(ErrorHandlingMiddleware(
        mask_sensitive_data=True,
        include_traceback=True
    ))
```

### Tool Integration
- Tools access middleware state through context
- Middleware provides performance hints to tools
- Rate limiting affects tool execution priority
- Error handling provides consistent tool error responses

## Logging Configuration

### File Rotation
- Primary log: `logs/firecrawler.log` (5MB, 1 backup)
- Middleware log: `logs/middleware.log` (5MB, 1 backup)
- Error-specific logs in structured format
- Performance metrics in separate log stream

### Log Levels
- **DEBUG**: Detailed middleware operation traces
- **INFO**: Request/response summaries and performance
- **WARNING**: Rate limit approaches and performance degradation
- **ERROR**: Failures, exceptions, and service issues

### Structured Logging
```python
# Using FastMCP context for structured logging to clients
if context.fastmcp_context:
    await context.fastmcp_context.info(
        "Request processed",
        extra={
            "tool": "scrape",
            "duration_ms": 150,
            "status": "success",
            "url": "https://example.com"
        }
    )

# Or using StructuredLoggingMiddleware for JSON logs
class CustomStructuredMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "method": context.method,
            "source": context.source,
            "event": "request_start"
        }
        
        if context.fastmcp_context:
            await context.fastmcp_context.info(json.dumps(log_entry))
        
        return await call_next(context)
```

## Performance Monitoring
- Track request latency percentiles
- Monitor memory and CPU usage
- Alert on error rate thresholds
- Report API quota utilization