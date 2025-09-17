### Firecrawler MCP Server - Product Requirements Document
This document outlines the requirements and tools for setting up a Firecrawl MCP server using the FastMCP framework. The server will leverage Firecrawl's web crawling and scraping capabilities, along with LLM-powered data extraction. 

We've also upgraded Firecrawl's Postgres DB with pgvector support, and are generating embeddings for all scraped/crawled content via Huggingface Text Embeddings Inference server.

We've modified the Firecrawl Python SDK and added vector search capabilities. This allows for advanced semantic search and retrieval capabilities.

We will be using Python FastMCP(https://gofastmcp.com) along with the Firecrawl Python SDK for integration (@/home/jmagar/compose/firecrawl/apps/python-sdk).

### Environment Setup
- Python 3.11+
- Use `uv` for package management/virtualenv
- Python FastMCP 2.12.2+
- Use the local Firecrawl Python SDK from `@apps/python-sdk`
- Ruff for linting and formatting
- Mypy for type checking
- Pytest for testing
- Pre-commit hooks for code quality
  - Run ruff + mypy on commit (no tests)
- Ruff, mypy, and pytest should be configured via `pyproject.toml`
    - Their caches/artifacts should be gitignored
    - Their caches/artifacts should be stored in `.cache/`
- Environment Variables:
  - `FIRECRAWL_API_KEY` - Your Firecrawl API key (required for cloud API, optional for self-hosted)
  - `FIRECRAWL_API_BASE_URL` - URL to your self-hosted Firecrawl API (required for self-hosted, unnecessary for cloud API)
  - `FIRECRAWLER_HOST` - MCP server host (default: localhost if not set)
  - `FIRECRAWLER_PORT` - MCP server port (default: 8000 if not set)
  - `FIRECRAWLER_LOG_LEVEL` - Logging level (default: INFO)
  - `FIRECRAWLER_TRANSPORT` - Transport method (default: steamable-http)

### Project Structure
Located in apps/
```
firecrawler/
├── .cache/
│   ├── mypy/
│   ├── pytest/
│   └── ruff/
├── logs/ - ALL LOGS HERE. GITIGNORE THIS FOLDER. NO LOGS ELSEWHERE.
│   ├── firecrawler.log (5MB rotating log file, 1 backup)
│   └── middleware.log (5MB rotating log file, 1 backup)
├── docs/
│   ├── fastmcp/
│   │   ├── server.md
│   │   ├── self-hosted.md
│   │   ├── running-server.md
│   │   ├── server-configuration.md
│   │   ├── decorating-methods.md
│   │   ├── tools.md
│   │   ├── prompts.md
│   │   ├── resources.md
│   │   ├── context.md
│   │   ├── logging.md
│   │   ├── progress.md
│   │   ├── tests.md
│   │   ├── cli.md
│   │   └── middleware.md
│   ├── TOOLS.md
│   ├── RESOURCES.md
│   ├── PROMPTS.md
│   ├── MCP_SERVER.md
│   ├── MIDDLEWARE.md
│   └── TESTING.md
├── firecrawl_mcp/
│   ├── tools/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   ├── crawl.py (crawl_status should be in here too)
│   │   ├── extract.py
│   │   ├── map.py
│   │   ├── scrape.py (batch_scrape + batch_status should be in here too)
│   │   ├── firesearch.py
│   │   └── firerag.py
│   ├── prompts/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   └── prompts.py
│   ├── resources/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   └── resources.py
│   ├── core/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   └── *** SDK Client goes here? ***
│   ├── middleware/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   ├── timing.py
│   │   ├── logging.py
│   │   ├── rate_limit.py
│   │   └── error_handling.py
│   ├── services/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   └── *** business for tools/prompts/resources goes here? ***
│   ├── tests/
│   │   ├── CLAUDE.md
│   │   ├── __init__.py
│   │   ├── test_resources.py
│   │   ├── test_prompts.py
│   │   ├── test_timing.py
│   │   ├── test_logging.py
│   │   ├── test_rate_limit.py
│   │   ├── test_error_handling.py
│   │   ├── test_core.py
│   │   ├── test_crawl.py
│   │   ├── test_crawl_status.py
│   │   ├── test_extract.py
│   │   ├── test_map.py
│   │   ├── test_scrape.py
│   │   ├── test_batch_scrape.py
│   │   ├── test_batch_status.py
│   │   ├── test_firesearch.py
│   │   └── test_firerag.py
│   ├── __init__.py
│   ├── server.py
├── fastmcp.json
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── uv.lock
├── .env
├── .env.example
├── .gitignore
└── .pre-commit-config.yaml
```

### MCP Server Requirements:
- Self-hosted - https://gofastmcp.com/servers/server.md & https://gofastmcp.com/deployment/self-hosted.md
- Steamable-HTTP transport - https://gofastmcp.com/deployment/running-server.md
- fastmcp.json - https://gofastmcp.com/deployment/server-configuration.md
- FastMCP decorator methods - https://gofastmcp.com/patterns/decorating-methods.md
- Tools (listed below) - https://gofastmcp.com/servers/tools.md
- Prompts - https://gofastmcp.com/servers/prompts.md
- Resources - https://gofastmcp.com/servers/resources.md
- Context - https://gofastmcp.com/servers/context.md
- Logging - https://gofastmcp.com/servers/logging.md
- Progress Reporting - https://gofastmcp.com/servers/progress.md
- Middleware - https://gofastmcp.com/servers/middleware.md
    - Timing
    - Logging
    - Rate Limiting
    - Error Handling
- Tests - https://gofastmcp.com/development/tests.md
    - Use In-Memory tests
    - Do not mock external deps, they should be REAL TESTS
    - Follow FastMCP testing patterns exactly
- Misc Info - https://gofastmcp.com/patterns/cli.md


## Tools
The MCP server will expose the following tools for web scraping, crawling, mapping, data extraction, and vector search. Each tool is designed for specific use cases and has its own set of best practices.

### Scrape Tool (`scrape`)

Scrape content from a single URL with advanced options.

**Best for:**
- Single page content extraction, when you know exactly which page contains the information.

**Not recommended for:**
- Extracting content from multiple pages (use batch_scrape for known URLs, or map + batch_scrape to discover URLs first, or crawl for full page content)
- When you're unsure which page contains the information (use search)
- When you need structured data (use extract)

**Common mistakes:**
- Using scrape for a list of URLs (use batch_scrape instead).

**Prompt Example:**
> "Get the content of the page at https://example.com."

**Usage Example:**
```json
{
  "name": "scrape",
  "arguments": {
    "url": "https://example.com",
    "formats": ["markdown"],
    "onlyMainContent": true,
    "waitFor": 1000,
    "timeout": 30000,
    "mobile": false,
    "includeTags": ["article", "main"],
    "excludeTags": ["nav", "footer"],
    "skipTlsVerification": false
  }
}
```

**Returns:**
- Markdown, HTML, or other formats as specified.

### Batch Scrape Tool (`batch_scrape`)

Scrape multiple URLs efficiently with built-in rate limiting and parallel processing.

**Best for:**
- Retrieving content from multiple pages, when you know exactly which pages to scrape.

**Not recommended for:**
- Discovering URLs (use map first if you don't know the URLs)
- Scraping a single page (use scrape)

**Common mistakes:**
- Using batch_scrape with too many URLs at once (may hit rate limits or token overflow)

**Prompt Example:**
> "Get the content of these three blog posts: [url1, url2, url3]."

**Usage Example:**
```json
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
```

**Returns:**
- Response includes operation ID for status checking:

```json
{
  "content": [
    {
      "type": "text",
      "text": "Batch operation queued with ID: batch_1. Use batch_status to check progress."
    }
  ],
  "isError": false
}
```

### Crawl Tool (`crawl`)

Starts an asynchronous crawl job on a website and extract content from all pages.

**Best for:**
- Extracting content from multiple related pages, when you need comprehensive coverage.

**Not recommended for:**
- Extracting content from a single page (use scrape)
- When token limits are a concern (use map + batch_scrape)
- When you need fast results (crawling can be slow)

**Warning:** Crawl responses can be very large and may exceed token limits. Limit the crawl depth and number of pages, or use map + batch_scrape for better control.

**Common mistakes:**
- Setting limit or maxDepth too high (causes token overflow)
- Using crawl for a single page (use scrape instead)

**Prompt Example:**
> "Get all blog posts from the first two levels of example.com/blog."

**Usage Example:**
```json
{
  "name": "crawl",
  "arguments": {
    "url": "https://example.com/blog/*",
    "maxDepth": 2,
    "limit": 100,
    "allowExternalLinks": false,
    "deduplicateSimilarURLs": true
  }
}
```

**Returns:**
- Response includes operation ID for status checking:

```json
{
  "content": [
    {
      "type": "text",
      "text": "Started crawl for: https://example.com/* with job ID: 550e8400-e29b-41d4-a716-446655440000. Use crawl_status to check progress."
    }
  ],
  "isError": false
}
```

### Map Tool (`map`)

Map a website to discover all indexed URLs on the site.

**Best for:**
- Discovering URLs on a website before deciding what to scrape
- Finding specific sections of a website

**Not recommended for:**
- When you already know which specific URL you need (use scrape or batch_scrape)
- When you need the content of the pages (use scrape after mapping)

**Common mistakes:**
- Using crawl to discover URLs instead of map

**Prompt Example:**
> "List all URLs on example.com."

**Usage Example:**
```json
{
  "name": "map",
  "arguments": {
    "url": "https://example.com"
  }
}
```

**Returns:**
- Array of URLs found on the site

### Extract Tool (`extract`)

Extract structured information from web pages using LLM capabilities. Supports both cloud AI and self-hosted LLM extraction.

**Best for:**
- Extracting specific structured data like prices, names, details.

**Not recommended for:**
- When you need the full content of a page (use scrape)
- When you're not looking for specific structured data

**Arguments:**
- `urls`: Array of URLs to extract information from
- `prompt`: Custom prompt for the LLM extraction
- `systemPrompt`: System prompt to guide the LLM
- `schema`: JSON schema for structured data extraction
- `allowExternalLinks`: Allow extraction from external links
- `enableWebSearch`: Enable web search for additional context
- `includeSubdomains`: Include subdomains in extraction

When using a self-hosted instance, the extraction will use your configured LLM. For cloud API, it uses Firecrawl's managed LLM service.
**Prompt Example:**
> "Extract the product name, price, and description from these product pages."

**Usage Example:**
```json
{
  "name": "extract",
  "arguments": {
    "urls": ["https://example.com/page1", "https://example.com/page2"],
    "prompt": "Extract product information including name, price, and description",
    "systemPrompt": "You are a helpful assistant that extracts product information",
    "schema": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "price": { "type": "number" },
        "description": { "type": "string" }
      },
      "required": ["name", "price"]
    },
    "allowExternalLinks": false,
    "enableWebSearch": false,
    "includeSubdomains": false
  }
}
```

**Returns:**
- Extracted structured data as defined by your schema

```json
{
  "content": [
    {
      "type": "text",
      "text": {
        "name": "Example Product",
        "price": 99.99,
        "description": "This is an example product description"
      }
    }
  ],
  "isError": false
}
```

### Check Crawl Status (`crawl_status`)

Check the status of a crawl job.

```json
{
  "name": "crawl_status",
  "arguments": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 5. Firesearch Tool (`firesearch`)

Search the web and optionally extract content from search results.

**Best for:**
- Finding specific information across multiple websites, when you don't know which website has the information.
- When you need the most relevant content for a query

**Not recommended for:**
- When you already know which website to scrape (use scrape)
- When you need comprehensive coverage of a single website (use map or crawl)

**Common mistakes:**
- Using crawl or map for open-ended questions (use search instead)

**Usage Example:**
```json
{
  "name": "firesearch",
  "arguments": {
    "query": "latest AI research papers 2023",
    "limit": 5,
    "lang": "en",
    "country": "us",
    "scrapeOptions": {
      "formats": ["markdown"],
      "onlyMainContent": true
    }
  }
}
```

**Returns:**
- Array of search results (with optional scraped content)

**Prompt Example:**
> "Find the latest research papers on AI published in 2023."


### Firerag Tool (`firerag`)
Perform RAG-style question answering using your vector database.
**Best for:**
- Answering specific questions using your scraped content
- When you need context-aware responses
**Not recommended for:**
- When you need raw data (use search or scrape)
**Common mistakes:**
- Using firerag without having relevant data in your vector DB
**Usage Example:**

**Prompt Example:**
> "What are the key features of Firecrawl?"


### Check Batch Status (`batch_status`)

Check the status of a batch operation.

```json
{
  "name": "batch_status",
  "arguments": {
    "id": "batch_1"
  }
}
```


## Logging System

The server should include comprehensive logging:

- Operation status and progress
- Performance metrics
- Credit usage monitoring
- Rate limit tracking
- Error conditions

Example log messages:

```
[INFO] Firecrawl MCP Server initialized successfully
[INFO] Starting scrape for URL: https://example.com
[INFO] Batch operation queued with ID: batch_1
[WARNING] Credit usage has reached warning threshold
[ERROR] Rate limit exceeded, retrying in 2s...
```

## Error Handling

The server should provide robust error handling:

- Automatic retries for transient errors
- Rate limit handling with backoff
- Detailed error messages
- Credit usage warnings
- Network resilience

Example error response:

```json
{
  "content": [
    {
      "type": "text",
      "text": "Error: Rate limit exceeded. Retrying in 2 seconds..."
    }
  ],
  "isError": true
}
```