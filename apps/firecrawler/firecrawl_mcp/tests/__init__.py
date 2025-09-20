"""
Testing package for comprehensive test coverage.

This package provides testing infrastructure using FastMCP's in-memory
testing patterns for fast, deterministic tests:

- Pytest configuration and shared fixtures
- Core client and configuration tests
- Middleware testing with performance validation
- Tools testing with real API integration (gated by environment)
- Component testing for prompts and resources
- Error scenario coverage and validation

Tests use async with Client(server) pattern for in-memory testing
without network overhead, completing under 1 second for unit tests.
Integration tests are gated with environment variables for CI/CD.
"""

# Test utilities and fixtures will be imported here once implemented
__all__ = [
    # "fixtures",
    # "test_helpers",
    # "mock_data",
    # "integration_helpers",
]
