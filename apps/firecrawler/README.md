# Firecrawl MCP Server

A Model Context Protocol (MCP) server that exposes Firecrawl API functionality to LLMs.

## Architecture

The MCP server is built using FastMCP and provides:
- **Tools**: Functions for scraping, crawling, and extraction
- **Resources**: Read-only access to configuration and status
- **Prompts**: Reusable templates for common tasks

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set the following environment variables:

```bash
FIRECRAWL_API_KEY=your-api-key
FIRECRAWL_API_URL=https://api.firecrawl.dev  # Optional
```

## Usage

### As MCP Server

```bash
python -m firecrawl_mcp
```

### With Claude Desktop

Add to your Claude configuration:

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "python",
      "args": ["-m", "firecrawl_mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "your-key"
      }
    }
  }
}
```

## Available Tools

### scrape
Scrape single or multiple URLs with format options.

### crawl
Crawl websites with depth control and filtering.

### extract
Extract structured data using AI.

### map
Discover and map website URLs.

### firesearch
Search the web with content extraction.

### firerag
Query vector database with semantic search.

## Development

### Testing

```bash
pytest tests/
```

### Adding New Tools

1. Create tool function in `tools/` directory
2. Follow async/Context signature pattern
3. Register with server in `__init__.py`
4. Add comprehensive error handling

## Error Handling

All tools use FastMCP exception types:
- `ToolError`: Tool execution failures
- `ResourceError`: Resource access issues

## Logging

Use Context for all logging:
```python
await ctx.info("Operation started")
await ctx.error(f"Failed: {error}")
```