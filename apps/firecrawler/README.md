# Firecrawler MCP Server

A production-ready Model Context Protocol (MCP) server that provides AI assistants with comprehensive web scraping, crawling, content extraction, and vector search capabilities through Firecrawl's infrastructure.

## Overview

The Firecrawler MCP Server exposes 9 powerful tools for web data collection and processing:

- **Scraping**: Single-page and batch content extraction
- **Crawling**: Deep website exploration with progress tracking
- **Content Processing**: AI-powered structured data extraction and URL mapping
- **Search**: Web search with optional content extraction
- **Vector Search**: Semantic search and RAG-style question answering

Built with FastMCP 2.12.2+ and the Firecrawl Python SDK, the server includes comprehensive middleware for logging, rate limiting, performance monitoring, and error handling.

## Features

### Core Tools
- `scrape` - Extract content from single URLs
- `batch_scrape` - Efficiently scrape multiple URLs with progress tracking
- `batch_status` - Monitor batch operation progress
- `crawl` - Asynchronous website crawling with job management
- `crawl_status` - Real-time crawl progress monitoring
- `extract` - AI-powered structured data extraction with schema validation
- `map` - Discover and map website URLs
- `firesearch` - Web search with optional content scraping
- `firerag` - Vector database RAG-style question answering

### Advanced Features
- **Middleware Stack**: Timing, logging, rate limiting, and error handling
- **Progress Reporting**: Real-time updates for long-running operations
- **Vector Search**: Semantic search with metadata filtering and LLM synthesis
- **Configuration Management**: Environment-based configuration with validation
- **Comprehensive Testing**: In-memory FastMCP testing patterns

## Quick Start

### Prerequisites

- Python 3.11+
- uv package manager
- Firecrawl API access (cloud or self-hosted)

### Installation

1. **Clone and navigate to the project**:
   ```bash
   cd apps/firecrawler
   ```

2. **Install dependencies with uv**:
   ```bash
   uv pip install -e .
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the server**:
   ```bash
   # Development
   fastmcp dev firecrawl_mcp.server

   # Production
   fastmcp run firecrawl_mcp.server
   ```

### Environment Variables

#### Required
- `FIRECRAWL_API_KEY` - Your Firecrawl API key (required for cloud API)

#### Optional  
- `FIRECRAWL_API_BASE_URL` - Self-hosted Firecrawl API URL
- `FIRECRAWLER_HOST` - MCP server host (default: localhost)
- `FIRECRAWLER_PORT` - MCP server port (default: 8000)
- `FIRECRAWLER_LOG_LEVEL` - Logging level (default: INFO)
- `FIRECRAWLER_TRANSPORT` - Transport method (default: streamable-http)

## Usage Examples

### Single Page Scraping
```python
# Extract content from a single URL
{
  "name": "scrape",
  "arguments": {
    "url": "https://example.com",
    "formats": ["markdown"],
    "onlyMainContent": true,
    "waitFor": 1000
  }
}
```

### Batch Operations
```python
# Scrape multiple URLs efficiently
{
  "name": "batch_scrape", 
  "arguments": {
    "urls": ["https://example1.com", "https://example2.com"],
    "options": {
      "formats": ["markdown"],
      "onlyMainContent": true
    }
  }
}

# Check batch progress
{
  "name": "batch_status",
  "arguments": {
    "id": "batch_12345"
  }
}
```

### Website Crawling
```python
# Start a website crawl
{
  "name": "crawl",
  "arguments": {
    "url": "https://example.com/blog/*",
    "maxDepth": 2,
    "limit": 100,
    "allowExternalLinks": false
  }
}

# Monitor crawl progress
{
  "name": "crawl_status",
  "arguments": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Structured Data Extraction
```python
# Extract structured data with AI
{
  "name": "extract",
  "arguments": {
    "urls": ["https://example.com/product"],
    "prompt": "Extract product information",
    "schema": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "price": {"type": "number"},
        "description": {"type": "string"}
      }
    }
  }
}
```

### Web Search
```python
# Search the web with content extraction
{
  "name": "firesearch",
  "arguments": {
    "query": "latest AI research 2024",
    "limit": 5,
    "scrapeOptions": {
      "formats": ["markdown"],
      "onlyMainContent": true
    }
  }
}
```

### Vector Search (RAG)
```python
# Semantic search with AI synthesis
{
  "name": "firerag",
  "arguments": {
    "query": "What are the key features of Firecrawl?",
    "limit": 5,
    "filters": {
      "domain": "firecrawl.dev"
    },
    "responseMode": "synthesized"
  }
}
```

## Architecture

### Project Structure
```
firecrawler/
├── firecrawl_mcp/
│   ├── core/          # Client and configuration management
│   ├── tools/         # MCP tool implementations  
│   ├── middleware/    # Request processing middleware
│   ├── services/      # Business logic services
│   ├── prompts/       # LLM prompt templates
│   ├── resources/     # MCP resources (config, status)
│   └── tests/         # Comprehensive test suite
├── docs/              # Documentation
├── logs/              # Application logs (gitignored)
└── .cache/            # Tool caches (gitignored)
```

### Key Components

- **Core**: Centralized Firecrawl SDK client management and configuration
- **Tools**: FastMCP-decorated tool implementations with validation
- **Middleware**: Request timing, logging, rate limiting, and error handling
- **Services**: Reusable business logic for complex operations
- **Testing**: In-memory FastMCP testing with real API integration

## Development

### Setup Development Environment

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest firecrawl_mcp/tests/

# Run specific test categories
pytest firecrawl_mcp/tests/test_scrape.py -v
pytest firecrawl_mcp/tests/test_middleware/ -v
```

### Testing

The project uses FastMCP's in-memory testing patterns for deterministic, fast tests:

```python
from fastmcp.testing import Client
from firecrawl_mcp.server import server

async def test_scrape_tool():
    async with Client(server) as client:
        result = await client.call_tool("scrape", {
            "url": "https://example.com"
        })
        assert not result.is_error
```

### Code Quality

- **Ruff**: Linting and formatting
- **MyPy**: Type checking
- **Pre-commit**: Automated code quality checks
- **Pytest**: Comprehensive testing with real API integration

## Configuration

### FastMCP Configuration (fastmcp.json)
```json
{
  "servers": {
    "firecrawler": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "firecrawl_mcp.server"],
      "transport": "streamable-http",
      "host": "localhost",
      "port": 8000,
      "env": {
        "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"
      }
    }
  }
}
```

### Logging Configuration

Logs are written to the `logs/` directory with automatic rotation:
- `firecrawler.log` - Main application logs (5MB, 1 backup)
- `middleware.log` - Request/response middleware logs (5MB, 1 backup)

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Deployment

### Production Deployment

1. **Configure environment variables**:
   ```bash
   export FIRECRAWL_API_KEY="your-api-key"
   export FIRECRAWLER_HOST="0.0.0.0"
   export FIRECRAWLER_PORT="8000"
   export FIRECRAWLER_LOG_LEVEL="INFO"
   ```

2. **Run the server**:
   ```bash
   fastmcp run firecrawl_mcp.server
   ```

3. **Monitor logs**:
   ```bash
   tail -f logs/firecrawler.log
   ```

### Self-Hosted Firecrawl

For self-hosted Firecrawl instances:

```bash
export FIRECRAWL_API_BASE_URL="http://your-firecrawl-instance:3002"
# FIRECRAWL_API_KEY may be optional depending on your setup
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv
RUN uv pip install -e .

EXPOSE 8000

CMD ["fastmcp", "run", "firecrawl_mcp.server"]
```

## Performance and Limits

### Rate Limiting
- Follows Firecrawl API rate limits
- Automatic backoff and retry logic
- Configurable rate limit middleware

### Memory Management
- Streaming responses for large datasets
- Connection pooling for HTTP requests
- Efficient batch processing

### Monitoring
- Performance timing middleware
- Credit usage tracking
- Operation status logging
- Error rate monitoring

## Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-feature`
3. **Install development dependencies**: `uv pip install -e ".[dev]"`
4. **Make changes and add tests**
5. **Run tests**: `pytest`
6. **Run quality checks**: `pre-commit run --all-files`
7. **Submit a pull request**

### Development Guidelines

- Follow existing code patterns and conventions
- Add comprehensive tests for new features
- Update documentation for API changes
- Use type hints throughout
- Follow FastMCP best practices

## Troubleshooting

### Common Issues

**Connection Errors**:
- Verify `FIRECRAWL_API_KEY` is set correctly
- Check `FIRECRAWL_API_BASE_URL` for self-hosted instances
- Ensure network connectivity to Firecrawl API

**Rate Limiting**:
- Monitor logs for rate limit warnings
- Reduce concurrent operations
- Implement appropriate delays between requests

**Memory Issues**:
- Limit batch sizes for large operations
- Use streaming options where available
- Monitor crawl depth and page limits

**Tool Errors**:
- Check tool parameter validation
- Verify URL accessibility
- Review error logs for detailed messages

### Log Analysis

```bash
# View recent errors
grep "ERROR" logs/firecrawler.log | tail -20

# Monitor real-time activity
tail -f logs/firecrawler.log | grep -E "(INFO|WARNING|ERROR)"

# Check middleware performance
grep "TIMING" logs/middleware.log | tail -10
```

## Documentation

- [Tools Documentation](docs/TOOLS.md) - Detailed tool specifications and examples
- [Resources Documentation](docs/RESOURCES.md) - MCP resources usage
- [Prompts Documentation](docs/PROMPTS.md) - LLM prompt templates
- [MCP Server Guide](docs/MCP_SERVER.md) - Server deployment and configuration
- [Middleware Guide](docs/MIDDLEWARE.md) - Middleware implementation details
- [Testing Guide](docs/TESTING.md) - Testing framework and best practices

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: GitHub Issues
- **Documentation**: `/docs` directory
- **Firecrawl API**: [Firecrawl Documentation](https://docs.firecrawl.dev)
- **FastMCP Framework**: [FastMCP Documentation](https://gofastmcp.com)