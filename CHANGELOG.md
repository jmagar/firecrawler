# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-XX-XX

### Breaking Changes

#### Environment Variables
- **REQUIRED**: `VECTOR_DIMENSION` environment variable must be set to match your embedding model's output dimension
  - Common values: 384 (MiniLM), 768, 1024, 1536 (OpenAI small), 3072 (OpenAI large)
  - Impact: Vector search will fail without this configuration
- **REQUIRED**: `MODEL_EMBEDDING_NAME` should be explicitly set for vector search functionality

#### API Changes
- **BREAKING**: `metadata.wordCount` renamed to `metadata.approxWordCount` in vector search responses
  - Impact: Code using `result.metadata.wordCount` will break
  - Migration: Update to `result.metadata.approxWordCount`

#### SDK Deprecations
- **JavaScript SDK**:
  - Deprecated: `research()` → Use `deepResearch()`
  - Deprecated: `asyncResearch()` → Use `asyncDeepResearch()`
  - Deprecated: `researchStatus()` → Use `checkDeepResearchStatus()`
- **Python SDK**:
  - Deprecated: `allow_backward_links` parameter → Use `crawl_entire_domain`

#### MCP Configuration (apps/firecrawler)
- **DEPRECATED**: `MCPConfig` class → Use environment functions directly
- **DEPRECATED**: Old `MCPError` hierarchy → Use FastMCP `ToolError`

### Security Fixes

#### Environment Variable Security
- **Added**: Environment variable whitelisting to prevent exposure of sensitive variables
- **Whitelisted prefixes**: `FIRECRAWL_*`, `MODEL_*`, `OPENAI_*`, `VECTOR_*`, `TEI_*`, `REDIS_*`, plus `PORT`, `HOST`, `NUM_WORKERS_PER_QUEUE`
- **Impact**: Unauthorized environment variables are no longer accessible in configuration

#### Configuration Security
- **Added**: Path traversal prevention in configuration file loading
- **Added**: `CONFIG_BASE_DIR` setting to restrict configuration file access
- **Added**: Security audit logging with `SECURITY_AUDIT_LOG` option

### Performance Improvements

#### Vector Search Memory Management
- **Fixed**: Unbounded memory growth in vector search threshold history
- **Added**: `MAX_THRESHOLD_HISTORY` configuration (default: 10)
- **Impact**: Better long-term stability for high-volume vector search operations

#### Configuration File Handling
- **Fixed**: File watcher debouncing for rapid configuration changes
- **Added**: `CONFIG_DEBOUNCE_DELAY` configuration (default: 1000ms)
- **Impact**: Reduced CPU usage during frequent configuration updates

#### Vector Search Optimization
- **Added**: Configurable vector search threshold floors
- **Added**: `VECTOR_THRESHOLD_FLOOR_1`, `VECTOR_THRESHOLD_FLOOR_2`, `VECTOR_THRESHOLD_FLOOR_3` settings
- **Impact**: Better search result quality and performance tuning capabilities

### New Features

#### Enhanced Environment Configuration
- **Added**: Comprehensive environment variable documentation in `.env.example`
- **Added**: Clear separation of required vs optional variables
- **Added**: Performance and security configuration sections

#### Improved Documentation
- **Added**: Comprehensive [Migration Guide](docs/MIGRATION_GUIDE.md)
- **Added**: Breaking changes notice in README.md
- **Added**: Version compatibility matrix
- **Added**: Migration checklist and rollback procedures

#### Configuration Enhancements
- **Added**: Better default values for performance-critical settings
- **Added**: Clearer documentation for vector search configuration
- **Added**: Security-focused configuration options

### Documentation

#### Migration Documentation
- **Added**: Step-by-step migration guide for all breaking changes
- **Added**: Code examples for SDK method updates
- **Added**: Environment variable migration instructions
- **Added**: Troubleshooting guide for common migration issues

#### Configuration Documentation
- **Enhanced**: Environment variable documentation with security notes
- **Added**: Performance tuning guidelines
- **Added**: Security configuration best practices

### Development

#### Code Quality
- **Updated**: MCP components to use modern FastMCP patterns
- **Enhanced**: Error handling with proper MCP exceptions
- **Improved**: Type annotations throughout MCP codebase

#### Testing
- **Added**: Migration test scenarios
- **Enhanced**: Environment variable validation
- **Improved**: Vector search stability tests

## Migration Guide

For detailed migration instructions, see [docs/MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md).

### Quick Migration Steps

1. **Set required environment variables**:
   ```bash
   export VECTOR_DIMENSION=1536  # Match your embedding model
   export MODEL_EMBEDDING_NAME=text-embedding-3-small
   ```

2. **Update API response handling**:
   ```javascript
   // Before
   const count = result.metadata.wordCount;
   
   // After
   const count = result.metadata.approxWordCount;
   ```

3. **Update SDK method calls**:
   ```javascript
   // Before
   const result = await client.research(params);
   
   // After
   const result = await client.deepResearch(params);
   ```

4. **Update MCP configuration**:
   ```python
   # Before
   from firecrawl_mcp.core.config import MCPConfig
   
   # After
   from firecrawl_mcp.core.config import get_api_key, get_api_url
   ```

### Support

For migration assistance:
- [GitHub Issues](https://github.com/firecrawl/firecrawl/issues)
- [Documentation](https://docs.firecrawl.dev)
- [Community Discord](https://discord.com/invite/gSmWdAkdwd)

---

## [Previous Versions]

Previous version history will be maintained here for reference.