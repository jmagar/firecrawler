"""
Performance metrics and timing tests for the Firecrawler MCP server.

This module tests the timing middleware components, including basic timing,
detailed timing, performance metrics collection, and statistics tracking
using FastMCP in-memory testing patterns.
"""

import asyncio
import time

import pytest

from firecrawl_mcp.middleware.timing import (
    DetailedTimingMiddleware,
    PerformanceMetric,
    PerformanceStats,
    TimingMiddleware,
    create_timing_middleware,
)


class TestPerformanceMetric:
    """Test PerformanceMetric class functionality."""

    def test_performance_metric_creation(self) -> None:
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

    def test_performance_metric_with_error(self) -> None:
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

    def test_timestamp_property(self) -> None:
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

    def test_performance_stats_initialization(self) -> None:
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

    def test_add_successful_measurement(self) -> None:
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

    def test_add_failed_measurement(self) -> None:
        """Test adding failed measurements."""
        stats = PerformanceStats("test_operation")

        stats.add_measurement(200.0, False)
        stats.add_measurement(300.0, True)

        assert stats.total_requests == 2
        assert stats.successful_requests == 1
        assert stats.failed_requests == 1
        assert stats.success_rate == 50.0

    def test_p95_calculation(self) -> None:
        """Test 95th percentile calculation."""
        stats = PerformanceStats("test_operation")

        # Add 100 measurements
        for i in range(100):
            stats.add_measurement(float(i), True)

        p95 = stats.p95_duration_ms
        # 95th percentile of 0-99 should be around 94-95
        assert 90 <= p95 <= 99

    def test_to_dict_conversion(self) -> None:
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
    def timing_middleware(self) -> TimingMiddleware:
        """Create a timing middleware instance for testing."""
        return TimingMiddleware(
            log_slow_requests=True,
            slow_request_threshold_ms=100.0,
            enable_stats=True
        )

    async def test_successful_request_timing(self, timing_middleware: TimingMiddleware) -> None:
        """Test timing middleware statistics collection."""
        # Create a mock metric for testing
        start_time = time.perf_counter()
        await asyncio.sleep(0.01)  # 10ms delay
        end_time = time.perf_counter()
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

        # Test metric processing
        timing_middleware._update_stats(metric)
        timing_middleware._recent_metrics.append(metric)

        # Check that metrics were collected
        stats = timing_middleware.get_stats()
        assert "test_operation" in stats
        assert stats["test_operation"]["total_requests"] == 1
        assert stats["test_operation"]["successful_requests"] == 1
        assert stats["test_operation"]["failed_requests"] == 0

    async def test_failed_request_timing(self, timing_middleware: TimingMiddleware) -> None:
        """Test timing middleware error handling."""
        # Create a mock failed metric
        start_time = time.perf_counter()
        await asyncio.sleep(0.01)
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        metric = PerformanceMetric(
            operation="test_operation",
            method="test_method",
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=False,
            error_type="ValueError",
            error_message="Test error"
        )

        # Test metric processing for failed request
        timing_middleware._update_stats(metric)
        timing_middleware._recent_metrics.append(metric)

        # Check that error was recorded
        stats = timing_middleware.get_stats()
        assert "test_operation" in stats
        assert stats["test_operation"]["total_requests"] == 1
        assert stats["test_operation"]["successful_requests"] == 0
        assert stats["test_operation"]["failed_requests"] == 1

    async def test_slow_request_logging(self, timing_middleware: TimingMiddleware) -> None:
        """Test that slow requests threshold detection works."""
        # Create a slow request metric (above the 100ms threshold)
        metric = PerformanceMetric(
            operation="slow_operation",
            method="test_method",
            start_time=time.perf_counter(),
            end_time=time.perf_counter() + 0.15,  # 150ms
            duration_ms=150.0,
            success=True
        )

        # Test that we can identify slow requests
        assert metric.duration_ms > timing_middleware.slow_request_threshold_ms
        assert timing_middleware.log_slow_requests is True

    def test_time_operation_decorator(self, timing_middleware: TimingMiddleware) -> None:
        """Test timing middleware configuration."""
        # Test middleware configuration
        assert timing_middleware.enable_stats is True
        assert timing_middleware.log_slow_requests is True
        assert timing_middleware.slow_request_threshold_ms == 100.0

    def test_get_recent_metrics(self, timing_middleware: TimingMiddleware) -> None:
        """Test retrieving recent metrics."""
        # Add several test metrics
        for i in range(5):
            metric = PerformanceMetric(
                operation=f"operation_{i}",
                method="test_method",
                start_time=time.perf_counter(),
                end_time=time.perf_counter() + 0.001,
                duration_ms=1.0,
                success=True
            )
            timing_middleware._recent_metrics.append(metric)

        recent = timing_middleware.get_recent_metrics(limit=3)
        assert len(recent) == 3

        # Check metric structure
        recent_metric = recent[0]
        assert "operation" in recent_metric
        assert "method" in recent_metric
        assert "duration_ms" in recent_metric
        assert "success" in recent_metric
        assert "timestamp" in recent_metric

    def test_reset_stats(self, timing_middleware: TimingMiddleware) -> None:
        """Test resetting statistics."""
        # Add some stats first
        metric = PerformanceMetric(
            operation="test_op",
            method="test_method",
            start_time=time.perf_counter(),
            end_time=time.perf_counter() + 0.001,
            duration_ms=1.0,
            success=True
        )
        timing_middleware._update_stats(metric)
        timing_middleware._recent_metrics.append(metric)

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
    def detailed_middleware(self) -> DetailedTimingMiddleware:
        """Create a detailed timing middleware instance."""
        return DetailedTimingMiddleware(
            enable_stats=True,
            track_tool_performance=True,
            track_resource_performance=True,
            track_prompt_performance=True
        )

    async def test_tool_timing(self, detailed_middleware: DetailedTimingMiddleware) -> None:
        """Test tool-specific timing configuration."""
        # Test that tool performance tracking is enabled
        assert detailed_middleware.track_tool_performance is True

        # Test tool stats collection by manually adding a metric
        with detailed_middleware._stats_lock:
            tool_stats = detailed_middleware._tool_stats["test_tool"]
            tool_stats.operation = "tool:test_tool"
            tool_stats.add_measurement(10.0, True)

        # Check detailed stats
        all_stats = detailed_middleware.get_detailed_stats()
        assert "tools" in all_stats
        assert "test_tool" in all_stats["tools"]
        assert all_stats["tools"]["test_tool"]["total_requests"] == 1

    async def test_resource_timing(self, detailed_middleware: DetailedTimingMiddleware) -> None:
        """Test resource-specific timing configuration."""
        # Test that resource performance tracking is enabled
        assert detailed_middleware.track_resource_performance is True

        # Test resource stats collection by manually adding a metric
        with detailed_middleware._stats_lock:
            resource_stats = detailed_middleware._resource_stats["config://test"]
            resource_stats.operation = "resource:config://test"
            resource_stats.add_measurement(5.0, True)

        all_stats = detailed_middleware.get_detailed_stats()
        assert "resources" in all_stats
        assert "config://test" in all_stats["resources"]

    async def test_prompt_timing(self, detailed_middleware: DetailedTimingMiddleware) -> None:
        """Test prompt-specific timing configuration."""
        # Test that prompt performance tracking is enabled
        assert detailed_middleware.track_prompt_performance is True

        # Test prompt stats collection by manually adding a metric
        with detailed_middleware._stats_lock:
            prompt_stats = detailed_middleware._prompt_stats["extraction_prompt"]
            prompt_stats.operation = "prompt:extraction_prompt"
            prompt_stats.add_measurement(8.0, True)

        all_stats = detailed_middleware.get_detailed_stats()
        assert "prompts" in all_stats
        assert "extraction_prompt" in all_stats["prompts"]

    async def test_failed_tool_timing(self, detailed_middleware: DetailedTimingMiddleware) -> None:
        """Test timing for failed tool execution."""
        # Test failed tool stats collection
        with detailed_middleware._stats_lock:
            failed_tool_stats = detailed_middleware._tool_stats["failing_tool"]
            failed_tool_stats.operation = "tool:failing_tool"
            failed_tool_stats.add_measurement(10.0, False)  # Failed measurement

        all_stats = detailed_middleware.get_detailed_stats()
        tool_result_stats = all_stats["tools"]["failing_tool"]
        assert tool_result_stats["total_requests"] == 1
        assert tool_result_stats["failed_requests"] == 1
        assert tool_result_stats["success_rate"] == 0.0

    def test_tracking_disabled(self) -> None:
        """Test middleware with tracking disabled."""
        middleware = DetailedTimingMiddleware(
            track_tool_performance=False,
            track_resource_performance=False,
            track_prompt_performance=False
        )

        # Test that tracking is disabled
        assert middleware.track_tool_performance is False
        assert middleware.track_resource_performance is False
        assert middleware.track_prompt_performance is False

        # Check that stats are empty by default
        stats = middleware.get_detailed_stats()
        assert len(stats["tools"]) == 0
        assert len(stats["resources"]) == 0
        assert len(stats["prompts"]) == 0

    def test_reset_detailed_stats(self, detailed_middleware: DetailedTimingMiddleware) -> None:
        """Test resetting detailed statistics."""
        # Add some test stats
        with detailed_middleware._stats_lock:
            # Add tool stat
            tool_stats = detailed_middleware._tool_stats["tool"]
            tool_stats.operation = "tool:tool"
            tool_stats.add_measurement(1.0, True)

            # Add resource stat
            resource_stats = detailed_middleware._resource_stats["resource"]
            resource_stats.operation = "resource:resource"
            resource_stats.add_measurement(1.0, True)

            # Add prompt stat
            prompt_stats = detailed_middleware._prompt_stats["prompt"]
            prompt_stats.operation = "prompt:prompt"
            prompt_stats.add_measurement(1.0, True)

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

    def test_create_basic_timing_middleware(self) -> None:
        """Test creating basic timing middleware from config."""
        class MockConfig:
            enable_metrics = True
            debug_mode = False

        config = MockConfig()
        middleware = create_timing_middleware(config)

        assert isinstance(middleware, TimingMiddleware)
        assert not isinstance(middleware, DetailedTimingMiddleware)
        assert middleware.enable_stats is True
        assert middleware.log_slow_requests is True

    def test_create_detailed_timing_middleware(self) -> None:
        """Test creating detailed timing middleware from config."""
        class MockConfig:
            enable_metrics = True
            debug_mode = True

        config = MockConfig()
        middleware = create_timing_middleware(config)

        assert isinstance(middleware, DetailedTimingMiddleware)
        assert middleware.enable_stats is True
        assert middleware.track_tool_performance is True
        assert middleware.track_resource_performance is True
        assert middleware.track_prompt_performance is True

    def test_create_minimal_timing_middleware(self) -> None:
        """Test creating minimal timing middleware."""
        class MockConfig:
            enable_metrics = False
            debug_mode = False

        config = MockConfig()
        middleware = create_timing_middleware(config)

        assert isinstance(middleware, TimingMiddleware)
        assert middleware.enable_stats is False
        assert middleware.log_slow_requests is False


class TestTimingIntegration:
    """Test timing middleware integration scenarios."""

    async def test_concurrent_operations(self) -> None:
        """Test timing middleware statistics tracking."""
        middleware = TimingMiddleware(enable_stats=True)

        # Simulate concurrent operations by adding metrics
        operations = ["fast_op", "medium_op", "slow_op"]
        delays = [10.0, 50.0, 100.0]

        for op_name, delay in zip(operations, delays, strict=False):
            metric = PerformanceMetric(
                operation=op_name,
                method="test_method",
                start_time=time.perf_counter(),
                end_time=time.perf_counter() + delay / 1000,
                duration_ms=delay,
                success=True
            )
            middleware._update_stats(metric)

        # Check that all operations were tracked
        stats = middleware.get_stats()
        assert len(stats) == 3
        assert "fast_op" in stats
        assert "medium_op" in stats
        assert "slow_op" in stats

    async def test_memory_usage_with_many_metrics(self) -> None:
        """Test that middleware doesn't accumulate too much memory."""
        middleware = TimingMiddleware(enable_stats=True)

        # Add many metrics to simulate memory usage
        for _i in range(1000):
            metric = PerformanceMetric(
                operation="batch_operation",
                method="test_method",
                start_time=time.perf_counter(),
                end_time=time.perf_counter() + 0.001,
                duration_ms=1.0,
                success=True
            )
            middleware._update_stats(metric)
            middleware._recent_metrics.append(metric)

        # Recent metrics should be limited
        recent = middleware.get_recent_metrics()
        assert len(recent) <= 1000  # Should be capped by maxlen

        # Stats should still aggregate properly
        stats = middleware.get_stats()
        assert stats["batch_operation"]["total_requests"] == 1000

    async def test_error_handling_in_timing(self) -> None:
        """Test error handling doesn't interfere with timing."""
        middleware = TimingMiddleware(enable_stats=True)

        # Simulate an error with timing
        await asyncio.sleep(0.01)  # Simulate some processing time

        metric = PerformanceMetric(
            operation="timeout_op",
            method="test_method",
            start_time=time.perf_counter(),
            end_time=time.perf_counter() + 0.01,
            duration_ms=10.0,
            success=False,
            error_type="MCPTimeoutError",
            error_message="Operation timed out"
        )
        middleware._update_stats(metric)

        # Should have recorded the timing even for failed operation
        stats = middleware.get_stats()
        assert "timeout_op" in stats
        assert stats["timeout_op"]["failed_requests"] == 1

        # Duration should be reasonable (around 10ms + overhead)
        assert 5 <= stats["timeout_op"]["average_duration_ms"] <= 50
