"""
Performance metrics and timing tests for the Firecrawler MCP server.

This module tests the timing middleware components, including basic timing,
detailed timing, performance metrics collection, and statistics tracking
using FastMCP in-memory testing patterns.
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from firecrawl_mcp.core.config import MCPConfig
from firecrawl_mcp.core.exceptions import MCPError, MCPTimeoutError
from firecrawl_mcp.middleware.timing import (
    DetailedTimingMiddleware,
    PerformanceMetric,
    PerformanceStats,
    TimingMiddleware,
    create_timing_middleware,
)



class TestPerformanceMetric:
    """Test PerformanceMetric class functionality."""

    def test_performance_metric_creation(self):
        """Test creating a performance metric."""
        start_time = time.perf_counter()
        end_time = start_time + 0.1
        duration_ms = (end_time - start_time) * 1000

        metric = PerformanceMetric(
            operation="test_operation",
            method="test_method",
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=True,
            client_info="test_client"
        )

        assert metric.operation == "test_operation"
        assert metric.method == "test_method"
        assert metric.success is True
        assert metric.error_type is None
        assert metric.client_info == "test_client"
        assert metric.duration_ms == duration_ms

    def test_performance_metric_with_error(self):
        """Test creating a performance metric with error information."""
        start_time = time.perf_counter()
        end_time = start_time + 0.05
        duration_ms = (end_time - start_time) * 1000

        metric = PerformanceMetric(
            operation="failing_operation",
            method="test_method",
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=False,
            error_type="ValueError",
            error_message="Test error message"
        )

        assert metric.success is False
        assert metric.error_type == "ValueError"
        assert metric.error_message == "Test error message"

    def test_timestamp_property(self):
        """Test the timestamp property returns ISO format."""
        start_time = time.perf_counter()
        metric = PerformanceMetric(
            operation="test",
            method="test",
            start_time=start_time,
            end_time=start_time + 0.1,
            duration_ms=100,
            success=True
        )

        timestamp = metric.timestamp
        assert isinstance(timestamp, str)
        # Should be ISO format with timezone
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp


class TestPerformanceStats:
    """Test PerformanceStats class functionality."""

    def test_performance_stats_initialization(self):
        """Test performance stats initialization."""
        stats = PerformanceStats("test_operation")

        assert stats.operation == "test_operation"
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.total_duration_ms == 0.0
        assert stats.min_duration_ms == float('inf')
        assert stats.max_duration_ms == 0.0
        assert len(stats.recent_durations) == 0

    def test_add_successful_measurement(self):
        """Test adding successful measurements."""
        stats = PerformanceStats("test_operation")

        stats.add_measurement(100.0, True)
        stats.add_measurement(150.0, True)

        assert stats.total_requests == 2
        assert stats.successful_requests == 2
        assert stats.failed_requests == 0
        assert stats.total_duration_ms == 250.0
        assert stats.min_duration_ms == 100.0
        assert stats.max_duration_ms == 150.0
        assert stats.success_rate == 100.0
        assert stats.average_duration_ms == 125.0

    def test_add_failed_measurement(self):
        """Test adding failed measurements."""
        stats = PerformanceStats("test_operation")

        stats.add_measurement(200.0, False)
        stats.add_measurement(300.0, True)

        assert stats.total_requests == 2
        assert stats.successful_requests == 1
        assert stats.failed_requests == 1
        assert stats.success_rate == 50.0

    def test_p95_calculation(self):
        """Test 95th percentile calculation."""
        stats = PerformanceStats("test_operation")

        # Add 100 measurements
        for i in range(100):
            stats.add_measurement(float(i), True)

        p95 = stats.p95_duration_ms
        # 95th percentile of 0-99 should be around 94-95
        assert 90 <= p95 <= 99

    def test_to_dict_conversion(self):
        """Test converting stats to dictionary."""
        stats = PerformanceStats("test_operation")
        stats.add_measurement(100.0, True)
        stats.add_measurement(200.0, False)

        result = stats.to_dict()

        assert result["operation"] == "test_operation"
        assert result["total_requests"] == 2
        assert result["successful_requests"] == 1
        assert result["failed_requests"] == 1
        assert result["success_rate"] == 50.0
        assert result["average_duration_ms"] == 150.0
        assert result["min_duration_ms"] == 100.0
        assert result["max_duration_ms"] == 200.0


class TestTimingMiddleware:
    """Test TimingMiddleware functionality."""

    @pytest.fixture
    def timing_middleware(self):
        """Create a timing middleware instance for testing."""
        return TimingMiddleware(
            log_slow_requests=True,
            slow_request_threshold_ms=100.0,
            enable_stats=True
        )

    async def test_successful_request_timing(self, timing_middleware):
        """Test timing a successful request."""
        async def mock_handler():
            await asyncio.sleep(0.01)  # 10ms delay
            return "success"

        context = {"method": "test_method", "client_info": "test_client"}

        result = await timing_middleware.process_request(
            "test_operation",
            mock_handler,
            context
        )

        assert result == "success"

        # Check that metrics were collected
        stats = timing_middleware.get_stats()
        assert "test_operation" in stats
        assert stats["test_operation"]["total_requests"] == 1
        assert stats["test_operation"]["successful_requests"] == 1
        assert stats["test_operation"]["failed_requests"] == 0

    async def test_failed_request_timing(self, timing_middleware):
        """Test timing a failed request."""
        async def mock_handler():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        context = {"method": "test_method"}

        with pytest.raises(ValueError, match="Test error"):
            await timing_middleware.process_request(
                "test_operation",
                mock_handler,
                context
            )

        # Check that error was recorded
        stats = timing_middleware.get_stats()
        assert "test_operation" in stats
        assert stats["test_operation"]["total_requests"] == 1
        assert stats["test_operation"]["successful_requests"] == 0
        assert stats["test_operation"]["failed_requests"] == 1

    async def test_slow_request_logging(self, timing_middleware):
        """Test that slow requests are logged appropriately."""
        async def slow_handler():
            await asyncio.sleep(0.15)  # 150ms delay (above threshold)
            return "slow_result"

        with patch.object(timing_middleware.logger, 'warning') as mock_warning:
            result = await timing_middleware.process_request(
                "slow_operation",
                slow_handler
            )

        assert result == "slow_result"
        # Should have logged a slow request warning
        mock_warning.assert_called_once()
        assert "SLOW REQUEST" in mock_warning.call_args[0][0]

    def test_time_operation_decorator(self, timing_middleware):
        """Test the time_operation decorator."""
        @timing_middleware.time_operation("decorated_op")
        async def decorated_function(value: str):
            await asyncio.sleep(0.01)
            return f"processed_{value}"

        async def run_test():
            result = await decorated_function("test")
            assert result == "processed_test"

            stats = timing_middleware.get_stats()
            assert "decorated_op" in stats
            assert stats["decorated_op"]["total_requests"] == 1

        asyncio.run(run_test())

    def test_get_recent_metrics(self, timing_middleware):
        """Test retrieving recent metrics."""
        # Process several operations
        async def run_operations():
            for i in range(5):
                await timing_middleware.process_request(
                    f"operation_{i}",
                    lambda: asyncio.create_task(asyncio.sleep(0.001))
                )

        asyncio.run(run_operations())

        recent = timing_middleware.get_recent_metrics(limit=3)
        assert len(recent) == 3

        # Check metric structure
        metric = recent[0]
        assert "operation" in metric
        assert "method" in metric
        assert "duration_ms" in metric
        assert "success" in metric
        assert "timestamp" in metric

    def test_reset_stats(self, timing_middleware):
        """Test resetting statistics."""
        # Add some stats first
        async def add_stats():
            await timing_middleware.process_request(
                "test_op",
                lambda: asyncio.create_task(asyncio.sleep(0.001))
            )

        asyncio.run(add_stats())

        # Verify stats exist
        stats = timing_middleware.get_stats()
        assert len(stats) > 0

        # Reset and verify empty
        timing_middleware.reset_stats()
        stats = timing_middleware.get_stats()
        assert len(stats) == 0

        recent = timing_middleware.get_recent_metrics()
        assert len(recent) == 0


class TestDetailedTimingMiddleware:
    """Test DetailedTimingMiddleware functionality."""

    @pytest.fixture
    def detailed_middleware(self):
        """Create a detailed timing middleware instance."""
        return DetailedTimingMiddleware(
            enable_stats=True,
            track_tool_performance=True,
            track_resource_performance=True,
            track_prompt_performance=True
        )

    async def test_tool_timing(self, detailed_middleware):
        """Test tool-specific timing."""
        async def mock_tool():
            await asyncio.sleep(0.01)
            return {"result": "tool_output"}

        result = await detailed_middleware.process_tool(
            "test_tool",
            mock_tool,
            {"param": "value"}
        )

        assert result == {"result": "tool_output"}

        # Check detailed stats
        stats = detailed_middleware.get_detailed_stats()
        assert "tools" in stats
        assert "test_tool" in stats["tools"]
        assert stats["tools"]["test_tool"]["total_requests"] == 1

    async def test_resource_timing(self, detailed_middleware):
        """Test resource-specific timing."""
        async def mock_resource():
            await asyncio.sleep(0.005)
            return {"config": "value"}

        result = await detailed_middleware.process_resource(
            "config://test",
            mock_resource
        )

        assert result == {"config": "value"}

        stats = detailed_middleware.get_detailed_stats()
        assert "resources" in stats
        assert "config://test" in stats["resources"]

    async def test_prompt_timing(self, detailed_middleware):
        """Test prompt-specific timing."""
        async def mock_prompt():
            await asyncio.sleep(0.008)
            return "Generated prompt text"

        result = await detailed_middleware.process_prompt(
            "extraction_prompt",
            mock_prompt
        )

        assert result == "Generated prompt text"

        stats = detailed_middleware.get_detailed_stats()
        assert "prompts" in stats
        assert "extraction_prompt" in stats["prompts"]

    async def test_failed_tool_timing(self, detailed_middleware):
        """Test timing for failed tool execution."""
        async def failing_tool():
            await asyncio.sleep(0.01)
            raise MCPError("Tool execution failed")

        with pytest.raises(MCPError):
            await detailed_middleware.process_tool("failing_tool", failing_tool)

        stats = detailed_middleware.get_detailed_stats()
        tool_stats = stats["tools"]["failing_tool"]
        assert tool_stats["total_requests"] == 1
        assert tool_stats["failed_requests"] == 1
        assert tool_stats["success_rate"] == 0.0

    def test_tracking_disabled(self):
        """Test middleware with tracking disabled."""
        middleware = DetailedTimingMiddleware(
            track_tool_performance=False,
            track_resource_performance=False,
            track_prompt_performance=False
        )

        async def mock_handler():
            return "result"

        async def run_test():
            # These should not collect stats
            await middleware.process_tool("tool", mock_handler)
            await middleware.process_resource("resource", mock_handler)
            await middleware.process_prompt("prompt", mock_handler)

            stats = middleware.get_detailed_stats()
            assert len(stats["tools"]) == 0
            assert len(stats["resources"]) == 0
            assert len(stats["prompts"]) == 0

        asyncio.run(run_test())

    def test_reset_detailed_stats(self, detailed_middleware):
        """Test resetting detailed statistics."""
        async def add_stats():
            await detailed_middleware.process_tool("tool", lambda: asyncio.create_task(asyncio.sleep(0.001)))
            await detailed_middleware.process_resource("resource", lambda: asyncio.create_task(asyncio.sleep(0.001)))
            await detailed_middleware.process_prompt("prompt", lambda: asyncio.create_task(asyncio.sleep(0.001)))

        asyncio.run(add_stats())

        # Verify stats exist
        stats = detailed_middleware.get_detailed_stats()
        assert len(stats["tools"]) > 0
        assert len(stats["resources"]) > 0
        assert len(stats["prompts"]) > 0

        # Reset and verify empty
        detailed_middleware.reset_stats()
        stats = detailed_middleware.get_detailed_stats()
        assert len(stats["tools"]) == 0
        assert len(stats["resources"]) == 0
        assert len(stats["prompts"]) == 0


class TestTimingMiddlewareFactory:
    """Test timing middleware factory functions."""

    def test_create_basic_timing_middleware(self):
        """Test creating basic timing middleware from config."""
        config = MCPConfig()
        config.enable_metrics = True
        config.debug_mode = False

        middleware = create_timing_middleware(config)

        assert isinstance(middleware, TimingMiddleware)
        assert not isinstance(middleware, DetailedTimingMiddleware)
        assert middleware.enable_stats is True
        assert middleware.log_slow_requests is True

    def test_create_detailed_timing_middleware(self):
        """Test creating detailed timing middleware from config."""
        config = MCPConfig()
        config.enable_metrics = True
        config.debug_mode = True

        middleware = create_timing_middleware(config)

        assert isinstance(middleware, DetailedTimingMiddleware)
        assert middleware.enable_stats is True
        assert middleware.track_tool_performance is True
        assert middleware.track_resource_performance is True
        assert middleware.track_prompt_performance is True

    def test_create_minimal_timing_middleware(self):
        """Test creating minimal timing middleware."""
        config = MCPConfig()
        config.enable_metrics = False
        config.debug_mode = False

        middleware = create_timing_middleware(config)

        assert isinstance(middleware, TimingMiddleware)
        assert middleware.enable_stats is False
        assert middleware.log_slow_requests is False


class TestTimingIntegration:
    """Test timing middleware integration scenarios."""

    async def test_concurrent_operations(self):
        """Test timing middleware with concurrent operations."""
        middleware = TimingMiddleware(enable_stats=True)

        async def operation(op_name: str, delay: float):
            async def handler():
                await asyncio.sleep(delay)
                return f"result_{op_name}"

            return await middleware.process_request(op_name, handler)

        # Run concurrent operations
        tasks = [
            operation("fast_op", 0.01),
            operation("medium_op", 0.05),
            operation("slow_op", 0.1)
        ]

        results = await asyncio.gather(*tasks)

        assert results == ["result_fast_op", "result_medium_op", "result_slow_op"]

        # Check that all operations were tracked
        stats = middleware.get_stats()
        assert len(stats) == 3
        assert "fast_op" in stats
        assert "medium_op" in stats
        assert "slow_op" in stats

    async def test_memory_usage_with_many_metrics(self):
        """Test that middleware doesn't accumulate too much memory."""
        middleware = TimingMiddleware(enable_stats=True)

        # Process many operations
        for i in range(1000):
            await middleware.process_request(
                "batch_operation",
                lambda: asyncio.create_task(asyncio.sleep(0.001))
            )

        # Recent metrics should be limited
        recent = middleware.get_recent_metrics()
        assert len(recent) <= 1000  # Should be capped by maxlen

        # Stats should still aggregate properly
        stats = middleware.get_stats()
        assert stats["batch_operation"]["total_requests"] == 1000

    async def test_error_handling_in_timing(self):
        """Test error handling doesn't interfere with timing."""
        middleware = TimingMiddleware(enable_stats=True)

        async def error_handler():
            await asyncio.sleep(0.01)
            raise MCPTimeoutError("Operation timed out")

        start_time = time.perf_counter()

        with pytest.raises(MCPTimeoutError):
            await middleware.process_request("timeout_op", error_handler)

        end_time = time.perf_counter()
        duration = (end_time - start_time) * 1000

        # Should have recorded the timing even for failed operation
        stats = middleware.get_stats()
        assert "timeout_op" in stats
        assert stats["timeout_op"]["failed_requests"] == 1

        # Duration should be reasonable (around 10ms + overhead)
        assert 5 <= stats["timeout_op"]["average_duration_ms"] <= 50
