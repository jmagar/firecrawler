#!/usr/bin/env python3
"""
Test to verify the combined extract tool works correctly with both modes.
"""

import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from firecrawl.v2.types import ExtractResponse

async def test_extract_modes():
    """Test that the combined extract tool handles both modes correctly."""
    print("=" * 60)
    print("Testing Combined Extract Tool - Dual Mode Functionality")
    print("=" * 60)
    
    from firecrawl_mcp.tools.extract import extract
    from fastmcp import Context
    
    # Create mock context
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.report_progress = AsyncMock()
    
    print("\n=== Test 1: Extraction Mode ===")
    
    # Mock the Firecrawl client for extraction mode
    with patch("firecrawl_mcp.tools.extract.get_firecrawl_client") as mock_get_client:
        mock_extract_response = ExtractResponse(
            id="extract-job-123",
            status="completed",
            credits_used=5,
            data=[{
                "url": "https://example.com",
                "extracted_data": {"title": "Example"}
            }]
        )
        
        mock_client = Mock()
        mock_client.extract.return_value = mock_extract_response
        mock_get_client.return_value = mock_client
        
        # Test extraction mode (urls provided)
        try:
            result = await extract(
                ctx=ctx,
                urls=["https://example.com"],
                prompt="Extract the title"
            )
            
            assert hasattr(result, 'id'), "Extraction should return ExtractResponse with id"
            assert result.id == "extract-job-123", f"Expected job ID extract-job-123, got {result.id}"
            print("✓ Extraction mode works correctly - returns ExtractResponse")
            
        except Exception as e:
            print(f"✗ Extraction mode failed: {e}")
            return False
    
    print("\n=== Test 2: Status Checking Mode ===")
    
    # Mock the Firecrawl client for status mode
    with patch("firecrawl_mcp.tools.extract.get_firecrawl_client") as mock_get_client:
        mock_status_response = ExtractResponse(
            id="extract-job-456",
            status="completed",
            credits_used=10,
            expires_at="2024-12-31T23:59:59Z",
            data=[{"extracted": "data"}]  # This data should NOT be returned
        )
        
        mock_client = Mock()
        mock_client.get_extract_status.return_value = mock_status_response
        mock_get_client.return_value = mock_client
        
        # Test status mode (job_id provided)
        try:
            result = await extract(
                ctx=ctx,
                job_id="extract-job-456"
            )
            
            assert isinstance(result, dict), "Status mode should return dict"
            assert result.get('job_id') == "extract-job-456", f"Expected job ID in response"
            assert 'data' not in result, "Status mode should NOT return data field"
            assert 'summary' in result, "Status mode should include summary"
            print(f"✓ Status mode works correctly - returns status summary only")
            print(f"  Response keys: {list(result.keys())}")
            
        except Exception as e:
            print(f"✗ Status mode failed: {e}")
            return False
    
    print("\n=== Test 3: Mode Validation ===")
    
    # Test providing both parameters
    try:
        with patch("firecrawl_mcp.tools.extract.get_firecrawl_client"):
            result = await extract(
                ctx=ctx,
                urls=["https://example.com"],
                job_id="some-job-id"
            )
        print("✗ Should have raised error for both parameters")
        return False
    except Exception as e:
        if "Cannot provide both" in str(e):
            print("✓ Correctly rejects both urls and job_id")
        else:
            print(f"✗ Wrong error for both parameters: {e}")
            return False
    
    # Test providing neither parameter
    try:
        with patch("firecrawl_mcp.tools.extract.get_firecrawl_client"):
            result = await extract(ctx=ctx)
        print("✗ Should have raised error for no parameters")
        return False
    except Exception as e:
        if "Either 'urls'" in str(e) or "must be provided" in str(e):
            print("✓ Correctly rejects when neither parameter provided")
        else:
            print(f"✗ Wrong error for no parameters: {e}")
            return False
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("Combined extract tool correctly handles both modes.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_extract_modes())
    exit(0 if success else 1)