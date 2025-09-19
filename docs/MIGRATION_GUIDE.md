# Firecrawl Migration Guide

## Breaking Changes

### 1. Required Environment Variables

#### VECTOR_DIMENSION (Required)
**Impact**: High - Vector search will fail without this configuration

**Before**: Not required, system used implicit defaults
**After**: Must explicitly set to match your embedding model's output dimension

**Migration Steps**:
1. Determine your embedding model's output dimension:
   - OpenAI text-embedding-3-small: 1536
   - OpenAI text-embedding-3-large: 3072
   - sentence-transformers/all-MiniLM-L6-v2: 384
   - Custom models: Check your model documentation

2. Set in your environment:
   ```bash
   export VECTOR_DIMENSION=1536  # For text-embedding-3-small
   ```

3. Or add to your .env file:
   ```
   VECTOR_DIMENSION=1536
   MODEL_EMBEDDING_NAME=text-embedding-3-small
   ```

### 2. API Response Changes

#### Vector Search Metadata
**Impact**: Medium - Code using metadata.wordCount will break

**Before**:
```json
{
  "metadata": {
    "wordCount": 150
  }
}
```

**After**:
```json
{
  "metadata": {
    "approxWordCount": 150
  }
}
```

**Migration**:
```javascript
// Update all references
const count = result.metadata.approxWordCount; // was .wordCount
```

### 3. SDK Method Deprecations

#### JavaScript SDK
**Deprecated Methods**:
- `research()` → Use `deepResearch()`
- `asyncResearch()` → Use `asyncDeepResearch()`
- `researchStatus()` → Use `checkDeepResearchStatus()`

**Migration Example**:
```javascript
// Before
const result = await client.research(params);

// After
const result = await client.deepResearch(params);
```

#### Python SDK
**Deprecated Parameter**:
- `allow_backward_links` → Use `crawl_entire_domain`

**Migration Example**:
```python
# Before
client.crawl(url, allow_backward_links=True)

# After
client.crawl(url, crawl_entire_domain=True)
```

### 4. Configuration Changes

#### MCP Configuration (apps/firecrawler)
**Deprecated**: `MCPConfig` class
**Recommended**: Use environment functions directly

**Migration**:
```python
# Before
from firecrawl_mcp.core.config import MCPConfig
config = MCPConfig()

# After
from firecrawl_mcp.core.config import get_api_key, get_api_url
api_key = get_api_key()
api_url = get_api_url()
```

### 5. Error Handling

**Deprecated**: Old `MCPError` hierarchy
**Recommended**: FastMCP `ToolError`

**Migration**:
```python
# Before
from firecrawl_mcp.core.exceptions import MCPError
raise MCPError("Something failed")

# After
from fastmcp.exceptions import ToolError
raise ToolError("Something failed")
```

### 6. Configuration File Changes

#### Environment Variable Whitelisting
**Impact**: Medium - Some environment variables may no longer be accessible

**Before**: All environment variables could be accessed in configuration
**After**: Only whitelisted environment variables are accessible

**Whitelisted Variables**:
- `FIRECRAWL_*`
- `MODEL_*`
- `OPENAI_*`
- `VECTOR_*`
- `TEI_*`
- `REDIS_*`
- `PORT`
- `HOST`
- `NUM_WORKERS_PER_QUEUE`

**Migration**: Ensure your configuration only references whitelisted variables or update your environment variable names to use approved prefixes.

#### Path Traversal Prevention
**Impact**: Low - Configuration files outside the base directory are no longer accessible

**Before**: Configuration files could be loaded from any path
**After**: Configuration files are restricted to the configured base directory

**Migration**: Ensure all configuration files are within the `CONFIG_BASE_DIR` (defaults to application directory).

## Version Compatibility Matrix

| Feature | v0.x | v1.0 | Notes |
|---------|------|------|--------|
| VECTOR_DIMENSION env | Optional | Required | Must match embedding model |
| metadata.wordCount | ✓ | ✗ | Use approxWordCount |
| research() method | ✓ | Deprecated | Use deepResearch() |
| MCPConfig class | ✓ | Deprecated | Use env functions |
| Unbounded memory growth | Present | Fixed | Vector search now has limits |
| Config security | Basic | Enhanced | Whitelist + path restrictions |

## Testing Your Migration

1. **Environment Variables**:
   ```bash
   # Verify required variables
   echo $VECTOR_DIMENSION
   echo $MODEL_EMBEDDING_NAME
   ```

2. **API Compatibility**:
   ```bash
   # Test vector search endpoint
   curl -X POST your-api/v1/search \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "limit": 10}'
   ```

3. **SDK Compatibility**:
   Run your test suite with updated SDK methods

4. **Memory Usage Monitoring**:
   ```bash
   # Monitor memory usage during vector operations
   ps aux | grep your-app
   ```

## Performance Improvements

### Vector Search Memory Management
- **Fixed**: Unbounded memory growth in threshold history
- **Added**: Configurable `MAX_THRESHOLD_HISTORY` (default: 10)
- **Impact**: Better long-term stability for high-volume vector search

### Configuration File Handling
- **Fixed**: File watcher debouncing for rapid config changes
- **Added**: Configurable `CONFIG_DEBOUNCE_DELAY` (default: 1000ms)
- **Impact**: Reduced CPU usage during config updates

## Security Enhancements

### Environment Variable Whitelisting
Protects against:
- Accidental exposure of sensitive environment variables
- Configuration injection attacks
- Information disclosure vulnerabilities

### Path Traversal Prevention
Protects against:
- Directory traversal attacks in configuration loading
- Unauthorized file access
- Configuration file manipulation

## Rollback Plan

If issues occur after migration:

1. **Environment Variables**:
   ```bash
   # Restore previous environment
   unset VECTOR_DIMENSION
   # Remove other new variables
   ```

2. **SDK Downgrade**:
   ```bash
   # JavaScript
   npm install @mendable/firecrawl-js@previous-version
   
   # Python
   pip install firecrawl-py==previous-version
   ```

3. **Configuration Rollback**:
   - Restore previous configuration files
   - Revert to old environment variable names
   - Use compatibility mode (if available)

## Migration Checklist

- [ ] Set `VECTOR_DIMENSION` environment variable
- [ ] Update SDK method calls (research → deepResearch)
- [ ] Replace `metadata.wordCount` with `metadata.approxWordCount`
- [ ] Update MCP configuration to use environment functions
- [ ] Replace old error classes with FastMCP exceptions
- [ ] Verify environment variables are whitelisted
- [ ] Test vector search functionality
- [ ] Monitor memory usage patterns
- [ ] Update documentation and deployment scripts

## Common Issues and Solutions

### Issue: Vector search returns no results
**Solution**: Verify `VECTOR_DIMENSION` matches your embedding model

### Issue: SDK methods not found
**Solution**: Update to latest SDK version and use new method names

### Issue: Configuration files not loading
**Solution**: Ensure files are within `CONFIG_BASE_DIR`

### Issue: High memory usage
**Solution**: Adjust `MAX_THRESHOLD_HISTORY` and monitor vector operations

## Support

For migration assistance:
- GitHub Issues: [https://github.com/firecrawl/firecrawl/issues](https://github.com/firecrawl/firecrawl/issues)
- Documentation: [https://docs.firecrawl.dev](https://docs.firecrawl.dev)
- Community Discord: [https://discord.com/invite/gSmWdAkdwd](https://discord.com/invite/gSmWdAkdwd)

## Additional Resources

- [Configuration Guide](configuration-guide.md)
- [Vector Search Setup](TEI_PGVECTOR_SETUP.md)
- [Troubleshooting Guide](troubleshooting-guide.md)
- [API Documentation](https://docs.firecrawl.dev/api-reference)