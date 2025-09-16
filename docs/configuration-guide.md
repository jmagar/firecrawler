# Firecrawl YAML Configuration Guide

## Overview

Firecrawl's YAML configuration system allows self-hosted users to set default values for API requests, reducing the need to specify the same parameters repeatedly. This guide provides comprehensive information on setting up, configuring, and troubleshooting YAML-based configuration for your Firecrawl deployment.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration File Setup](#configuration-file-setup)
3. [Docker Integration](#docker-integration)
4. [Environment Variable Substitution](#environment-variable-substitution)
5. [Configuration Sections](#configuration-sections)
6. [Configuration Precedence](#configuration-precedence)
7. [Migration from Environment Variables](#migration-from-environment-variables)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Examples](#examples)

## Quick Start

1. **Copy the example configuration**:
   ```bash
   cp defaults.example.yaml defaults.yaml
   ```

2. **Edit your configuration**:
   ```bash
   nano defaults.yaml
   ```

3. **For Docker deployments**, mount the configuration file:
   ```bash
   docker run -v ./defaults.yaml:/app/defaults.yaml firecrawl/firecrawl
   ```

4. **Start Firecrawl** - your defaults will be applied automatically to all API requests.

## Configuration File Setup

### File Location Options

Firecrawl will automatically discover your configuration file in these locations (in order of priority):

1. `./defaults.yaml` (project root)
2. `./config/defaults.yaml` (config subdirectory)
3. Custom path via `FIRECRAWL_CONFIG_PATH` environment variable

### Basic File Structure

```yaml
# Firecrawl Configuration
scraping:
  # Default scraping options
  formats:
    - type: markdown
    - type: links
  onlyMainContent: true
  timeout: 30000

crawling:
  # Default crawling options
  limit: 1000
  maxDiscoveryDepth: 3

search:
  # Default search options
  limit: 5
  lang: en

embeddings:
  # Vector storage options
  enabled: false

features:
  # Feature flags
  vectorStorage: false
```

## Docker Integration

### Volume Mounting

Mount your configuration file into the container:

```bash
# Single file mount
docker run -v ./defaults.yaml:/app/defaults.yaml firecrawl/firecrawl

# Directory mount (recommended for multiple config files)
docker run -v ./config:/app/config firecrawl/firecrawl
```

### Docker Compose

Add volume mounts to your `docker-compose.yml`:

```yaml
version: '3.8'
services:
  firecrawl-api:
    build: .
    volumes:
      - ./defaults.yaml:/app/defaults.yaml
      # or for directory mounting:
      - ./config:/app/config
    environment:
      - FIRECRAWL_CONFIG_PATH=/app/defaults.yaml  # optional: specify custom path
```

### Configuration Path Environment Variable

Specify a custom configuration file path:

```bash
# In your .env file
FIRECRAWL_CONFIG_PATH=/app/config/my-config.yaml

# Or in Docker run command
docker run -e FIRECRAWL_CONFIG_PATH=/app/config/defaults.yaml \
           -v ./my-config.yaml:/app/config/defaults.yaml \
           firecrawl/firecrawl
```

## Environment Variable Substitution

### Syntax

Use `${VARIABLE_NAME}` or `${VARIABLE_NAME:-default_value}` syntax in any YAML value:

```yaml
scraping:
  timeout: ${SCRAPE_TIMEOUT:-30000}
  proxy: ${PROXY_MODE:-auto}
  
features:
  vectorStorage: ${ENABLE_VECTOR_STORAGE:-false}
  
embeddings:
  provider: ${EMBEDDING_PROVIDER:-tei}
  model: ${EMBEDDING_MODEL:-Qwen/Qwen3-Embedding-0.6B}
```

### Supported Data Types

Environment variable substitution works with all YAML data types:

```yaml
# String values
api_key: "${OPENAI_API_KEY:-your-default-key}"
base_url: "${API_BASE_URL:-https://api.openai.com}"

# Numeric values
timeout: "${REQUEST_TIMEOUT:-30000}"
limit: "${MAX_RESULTS:-100}"

# Boolean values
enabled: "${FEATURE_ENABLED:-true}"
debug_mode: "${DEBUG:-false}"

# Note: Arrays cannot use environment variables directly, but array elements can
formats:
  - type: markdown
  - type: "${ADDITIONAL_FORMAT:-links}"
```

### Environment Variable Examples

Set up environment variables for sensitive data:

```bash
# In your .env file
export OPENAI_API_KEY="sk-your-api-key"
export ENABLE_VECTOR_STORAGE="true"
export SCRAPE_TIMEOUT="45000"
export PROXY_MODE="stealth"

# Or in Docker
docker run -e OPENAI_API_KEY="sk-your-key" \
           -e ENABLE_VECTOR_STORAGE="true" \
           -v ./defaults.yaml:/app/defaults.yaml \
           firecrawl/firecrawl
```

## Configuration Sections

### Scraping Configuration

Default options for `/scrape` and `/batch-scrape` endpoints:

```yaml
scraping:
  # Output formats to extract
  formats:
    - type: markdown
    - type: links
    - type: html
    # - type: screenshot
    # - type: embeddings
  
  # Content extraction options
  onlyMainContent: true
  removeBase64Images: true
  
  # Request settings
  timeout: 30000
  waitFor: 0
  
  # Browser options
  mobile: false
  fastMode: false
  
  # Security options
  skipTlsVerification: true
  blockAds: true
  proxy: auto
  
  # Cache settings
  maxAge: 3600
  storeInCache: true
  
  # Geographic location
  location:
    country: us-generic
    languages: [en]
  
  # Custom headers (optional)
  # headers:
  #   User-Agent: "Firecrawl/1.0"
  #   Authorization: "Bearer ${API_TOKEN}"
  
  # Content selection (optional)
  # includeTags: ["article", "main"]
  # excludeTags: ["nav", "footer"]
```

### Crawling Configuration

Default options for `/crawl` endpoint:

```yaml
crawling:
  # Discovery limits
  maxDiscoveryDepth: 10
  limit: 10000
  
  # URL filtering
  # includePaths:
  #   - "/docs/*"
  #   - "/api/*"
  # excludePaths:
  #   - "/admin/*"
  #   - "*.pdf"
  
  # Crawling behavior
  allowExternalLinks: false
  allowSubdomains: false
  ignoreRobotsTxt: false
  
  # Content optimization
  sitemap: include
  deduplicateSimilarURLs: true
  ignoreQueryParameters: false
  regexOnFullURL: false
  
  # Performance (optional)
  # delay: 1000  # milliseconds between requests
```

### Search Configuration

Default options for `/search` endpoint:

```yaml
search:
  # Result limits
  limit: 5
  timeout: 60000
  
  # Geographic settings
  lang: en
  country: us
  
  # Search sources
  sources:
    - web
  
  # Content handling
  ignoreInvalidURLs: false
```

### Language Configuration

Language filtering and geographic settings:

```yaml
language:
  # Language filtering
  includeLangs:
    - en
  # excludeLangs:
  #   - es
  #   - fr
  
  # Location settings
  location:
    country: us-generic
    languages:
      - en
```

### Embeddings Configuration

Vector embeddings and semantic search settings:

```yaml
embeddings:
  # Enable/disable embeddings
  enabled: ${ENABLE_VECTOR_STORAGE:-false}
  
  # Model configuration  
  model: ${EMBEDDING_MODEL:-Qwen/Qwen3-Embedding-0.6B}
  provider: ${EMBEDDING_PROVIDER:-tei}
  dimension: 1024
  
  # Content processing
  maxContentLength: 8000
  minSimilarityThreshold: 0.7
```

### Features Configuration

Feature flags and system behavior:

```yaml
features:
  # Core features
  vectorStorage: ${ENABLE_VECTOR_STORAGE:-false}
  useDbAuthentication: ${USE_DB_AUTHENTICATION:-false}
  
  # Security features
  ipWhitelist: false
  zeroDataRetention: false
```

## Configuration Precedence

Configuration values are applied in this priority order (highest to lowest):

1. **YAML configuration file** - Values from your `defaults.yaml` take precedence
2. **Environment variable overrides** - `FIRECRAWL_CONFIG_OVERRIDE` JSON
3. **Environment variables** - Existing environment variable behavior
4. **Request parameters** - Values passed in API requests
5. **Built-in schema defaults** - Fallback values from Zod schemas

### Environment Variable Override

Override specific configuration values using JSON:

```bash
# Override multiple configuration sections
export FIRECRAWL_CONFIG_OVERRIDE='{
  "scraping": {
    "timeout": 60000,
    "onlyMainContent": false
  },
  "crawling": {
    "limit": 500
  }
}'
```

### Example Precedence Resolution

Given this configuration:

```yaml
# defaults.yaml
scraping:
  timeout: 30000
  onlyMainContent: true
```

```bash
# Environment variables
export SCRAPE_TIMEOUT=45000
export FIRECRAWL_CONFIG_OVERRIDE='{"scraping":{"timeout":60000}}'
```

```json
// API request
{
  "url": "https://example.com",
  "timeout": 75000
}
```

**Final resolved configuration:**
- `timeout: 30000` (from YAML config - highest priority)
- `onlyMainContent: true` (from YAML config)

## Migration from Environment Variables

### Automated Migration

Use the auto-generation script to create YAML from existing environment variables:

```bash
# Generate defaults.yaml from current environment
npm run generate-config

# Or specify output file
npm run generate-config -- --output my-config.yaml

# Validate generated configuration
npm run validate-config defaults.yaml
```

### Manual Migration Guide

Common environment variable mappings:

| Environment Variable | YAML Path | Example |
|---------------------|-----------|---------|
| `SCRAPE_TIMEOUT` | `scraping.timeout` | `30000` |
| `ENABLE_VECTOR_STORAGE` | `features.vectorStorage` | `true` |
| `OPENAI_API_KEY` | Use env substitution | `${OPENAI_API_KEY}` |
| `PROXY_MODE` | `scraping.proxy` | `auto` |
| `BLOCK_ADS` | `scraping.blockAds` | `true` |

### Migration Example

**Before (environment variables):**
```bash
export SCRAPE_TIMEOUT=45000
export ENABLE_VECTOR_STORAGE=true
export PROXY_MODE=stealth
export CRAWL_LIMIT=500
```

**After (YAML configuration):**
```yaml
scraping:
  timeout: ${SCRAPE_TIMEOUT:-30000}
  proxy: ${PROXY_MODE:-auto}

crawling:
  limit: ${CRAWL_LIMIT:-1000}

features:
  vectorStorage: ${ENABLE_VECTOR_STORAGE:-false}
```

## Best Practices

### Security Considerations

1. **Never commit API keys** to version control:
   ```yaml
   # Good: Use environment variables
   embeddings:
     provider: openai
     apiKey: ${OPENAI_API_KEY}
   
   # Bad: Hardcoded secrets
   embeddings:
     provider: openai
     apiKey: sk-actual-api-key  # DON'T DO THIS
   ```

2. **Use restrictive file permissions**:
   ```bash
   chmod 600 defaults.yaml  # Read/write for owner only
   ```

3. **Separate sensitive configs**:
   ```yaml
   # defaults.yaml (safe to commit)
   scraping:
     timeout: 30000
     proxy: ${PROXY_MODE:-auto}
   
   # secrets.yaml (not committed)
   # Include via environment variable substitution
   ```

### Performance Optimization

1. **Use appropriate timeouts**:
   ```yaml
   scraping:
     timeout: 30000  # 30 seconds for most sites
     # timeout: 60000  # 60 seconds for slow sites
   ```

2. **Optimize crawling limits**:
   ```yaml
   crawling:
     limit: 1000          # Reasonable default
     maxDiscoveryDepth: 3 # Prevent excessive depth
     delay: 1000          # Be respectful to target sites
   ```

3. **Configure caching**:
   ```yaml
   scraping:
     storeInCache: true
     maxAge: 3600  # 1 hour cache
   ```

### Configuration Management

1. **Use descriptive comments**:
   ```yaml
   scraping:
     # Timeout for individual page scraping (milliseconds)
     timeout: 30000
     
     # Use mobile viewport for responsive sites
     mobile: false
   ```

2. **Organize by feature**:
   ```yaml
   # === Core Scraping ===
   scraping:
     formats: [...]
   
   # === Advanced Features ===
   embeddings:
     enabled: true
   ```

3. **Validate configuration regularly**:
   ```bash
   # Add to CI/CD pipeline
   npm run validate-config defaults.yaml
   ```

## Troubleshooting

### Common Issues

#### 1. Configuration File Not Found

**Symptoms:**
- Firecrawl starts with default values only
- No configuration-related log messages

**Solutions:**
```bash
# Check file exists in expected location
ls -la defaults.yaml

# Verify file permissions
ls -la defaults.yaml
# Should show read permissions for the user running Firecrawl

# Check custom path environment variable
echo $FIRECRAWL_CONFIG_PATH

# Verify Docker volume mounting
docker inspect <container_name> | grep -A 10 Mounts
```

#### 2. YAML Syntax Errors

**Symptoms:**
```
[YYYY-MM-DDTHH:MM:SS.SSS] WARN - Invalid YAML configuration, falling back to defaults
```

**Solutions:**
```bash
# Validate YAML syntax
npm run validate-config defaults.yaml

# Or use online YAML validator
# Check for common issues:
# - Incorrect indentation (use spaces, not tabs)
# - Missing colons
# - Unquoted strings with special characters
```

**Common YAML mistakes:**
```yaml
# Wrong: Mixed spaces and tabs
scraping:
    timeout: 30000  # tab used here
  onlyMainContent: true  # spaces used here

# Correct: Consistent spacing
scraping:
  timeout: 30000
  onlyMainContent: true

# Wrong: Missing quotes for special values
proxy: auto:basic  # colon needs quoting

# Correct: Quoted special values
proxy: "auto:basic"
```

#### 3. Environment Variable Substitution Issues

**Symptoms:**
- Configuration contains literal `${VAR}` strings
- Expected environment values not applied

**Solutions:**
```bash
# Verify environment variable is set
echo $SCRAPE_TIMEOUT

# Check variable name matches exactly (case-sensitive)
env | grep SCRAPE

# Test default value syntax
# Wrong: ${VAR:default}
# Correct: ${VAR:-default}
```

#### 4. Configuration Not Applied to Requests

**Symptoms:**
- API requests use built-in defaults instead of YAML values
- Request parameters seem to ignore configuration

**Diagnostic steps:**
```bash
# Check application logs for configuration loading
docker logs firecrawl-api | grep -i config

# Verify middleware is active (look for defaultsMiddleware logs)
docker logs firecrawl-api | grep -i defaults

# Test with minimal request to verify defaults are applied
curl -X POST http://localhost:3002/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com"}'
```

#### 5. Docker Volume Mounting Issues

**Symptoms:**
- Configuration file appears empty inside container
- Permission denied errors

**Solutions:**
```bash
# Check file exists on host
ls -la ./defaults.yaml

# Verify mount path in container
docker exec -it <container> ls -la /app/defaults.yaml

# Check file content inside container
docker exec -it <container> cat /app/defaults.yaml

# Fix permission issues
chmod 644 defaults.yaml  # Ensure readable by container user

# Use absolute paths for volumes
docker run -v $(pwd)/defaults.yaml:/app/defaults.yaml firecrawl/firecrawl
```

### Debugging Configuration Loading

Enable debug logging to trace configuration loading:

```bash
# Set debug environment variable
export DEBUG=config:*

# Or in Docker
docker run -e DEBUG=config:* \
           -v ./defaults.yaml:/app/defaults.yaml \
           firecrawl/firecrawl
```

### Validation Tools

#### Configuration Validation Script

```bash
# Validate configuration file
npm run validate-config defaults.yaml

# Expected output for valid config:
# ✓ YAML syntax is valid
# ✓ Schema validation passed
# ✓ Environment variable substitution syntax is correct
# Configuration is valid!

# Example error output:
# ✗ YAML syntax error at line 15: bad indentation
# ✗ Schema validation failed: 'timeout' must be a number
# ✗ Invalid environment variable syntax: ${VAR:default} should be ${VAR:-default}
```

#### Manual Validation Steps

1. **YAML syntax validation**:
   ```bash
   # Using Python
   python -c "import yaml; yaml.safe_load(open('defaults.yaml'))"
   
   # Using Node.js
   node -e "const yaml = require('js-yaml'); yaml.load(require('fs').readFileSync('defaults.yaml', 'utf8'))"
   ```

2. **Environment variable testing**:
   ```bash
   # Test environment variable resolution
   export TEST_VAR=123
   echo "${TEST_VAR:-456}"  # Should output: 123
   
   unset TEST_VAR
   echo "${TEST_VAR:-456}"  # Should output: 456
   ```

3. **Schema validation**:
   ```bash
   # Check against API schema
   curl -X POST http://localhost:3002/v2/scrape \
     -H 'Content-Type: application/json' \
     -d '{"url": "https://httpbin.org/delay/1"}' \
     --fail-with-body
   ```

### Performance Monitoring

Monitor configuration impact on performance:

```bash
# Check configuration loading time
docker logs firecrawl-api | grep "Configuration loaded"

# Monitor request processing with configuration
docker logs firecrawl-api | grep "Defaults applied"

# Check for configuration reload events
docker logs firecrawl-api | grep "Configuration reloaded"
```

## Examples

### Basic Setup Example

```yaml
# defaults.yaml - Basic configuration for documentation scraping
scraping:
  formats:
    - type: markdown
    - type: links
  onlyMainContent: true
  timeout: 30000
  blockAds: true

crawling:
  limit: 500
  maxDiscoveryDepth: 3
  excludePaths:
    - "/api/*"
    - "*.pdf"

language:
  includeLangs: [en]
  location:
    country: us-generic
    languages: [en]
```

### Production Configuration Example

```yaml
# defaults.yaml - Production setup with vector storage
scraping:
  formats:
    - type: markdown
    - type: embeddings
  onlyMainContent: true
  timeout: ${SCRAPE_TIMEOUT:-45000}
  proxy: ${PROXY_MODE:-stealth}
  headers:
    User-Agent: "${USER_AGENT:-Firecrawl/1.0 (+https://firecrawl.dev)}"

crawling:
  limit: ${CRAWL_LIMIT:-2000}
  maxDiscoveryDepth: ${CRAWL_DEPTH:-5}
  allowSubdomains: ${ALLOW_SUBDOMAINS:-false}
  deduplicateSimilarURLs: true
  delay: ${CRAWL_DELAY:-2000}

embeddings:
  enabled: ${ENABLE_VECTOR_STORAGE:-true}
  provider: ${EMBEDDING_PROVIDER:-tei}
  model: ${EMBEDDING_MODEL:-Qwen/Qwen3-Embedding-0.6B}
  maxContentLength: ${MAX_CONTENT_LENGTH:-8000}

features:
  vectorStorage: ${ENABLE_VECTOR_STORAGE:-true}
  useDbAuthentication: ${USE_DB_AUTHENTICATION:-true}
  zeroDataRetention: ${ZERO_DATA_RETENTION:-false}
```

### Docker Compose Example

```yaml
# docker-compose.yml
version: '3.8'
services:
  firecrawl-api:
    build: .
    ports:
      - "3002:3002"
    volumes:
      - ./defaults.yaml:/app/defaults.yaml
      - ./config:/app/config  # Optional: mount entire config directory
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ENABLE_VECTOR_STORAGE=true
      - SCRAPE_TIMEOUT=45000
      - FIRECRAWL_CONFIG_PATH=/app/defaults.yaml
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=nuq
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
```

### Kubernetes ConfigMap Example

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: firecrawl-config
data:
  defaults.yaml: |
    scraping:
      formats:
        - type: markdown
        - type: embeddings
      timeout: 30000
      onlyMainContent: true
    
    crawling:
      limit: 1000
      maxDiscoveryDepth: 3
    
    features:
      vectorStorage: true

---
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: firecrawl-api
spec:
  template:
    spec:
      containers:
      - name: firecrawl-api
        image: firecrawl/firecrawl:latest
        volumeMounts:
        - name: config-volume
          mountPath: /app/defaults.yaml
          subPath: defaults.yaml
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: firecrawl-secrets
              key: openai-api-key
      volumes:
      - name: config-volume
        configMap:
          name: firecrawl-config
```

### Environment-Specific Configurations

```yaml
# config/development.yaml
scraping:
  timeout: 15000  # Shorter timeout for development
  fastMode: true
  storeInCache: false

crawling:
  limit: 100      # Smaller limits for testing
  maxDiscoveryDepth: 2

features:
  vectorStorage: false  # Disable expensive features in dev
```

```yaml
# config/production.yaml  
scraping:
  timeout: 60000  # Longer timeout for production reliability
  fastMode: false
  storeInCache: true
  maxAge: 7200    # 2-hour cache

crawling:
  limit: 10000    # Production-scale limits
  maxDiscoveryDepth: 10
  delay: 1000     # Be respectful to target sites

features:
  vectorStorage: true
  useDbAuthentication: true
```

---

## Additional Resources

- [API Reference Documentation](https://docs.firecrawl.dev/api-reference)
- [Self-Hosting Guide](../SELF_HOST.md)
- [Example Configuration File](../defaults.example.yaml)
- [Troubleshooting Guide](./troubleshooting-guide.md)
- [Environment Variables Reference](../apps/api/.env.example)

For more help, join our [Discord community](https://discord.gg/gSmWdAkdwd) or [open an issue](https://github.com/firecrawl/firecrawl/issues/new/choose) on GitHub.