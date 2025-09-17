# Firecrawler MCP Tools Documentation

This document provides comprehensive documentation for all tools available in the Firecrawler MCP server. Each tool is designed for specific web scraping, crawling, and data extraction use cases.

## Tool Overview

The Firecrawler MCP server exposes 9 tools organized into functional categories:

### Core Scraping Tools
- [`scrape`](#scrape-tool) - Single URL content extraction
- [`batch_scrape`](#batch-scrape-tool) - Multiple URL batch processing
- [`batch_status`](#batch-status-tool) - Batch operation monitoring

### Crawling Tools  
- [`crawl`](#crawl-tool) - Asynchronous website crawling
- [`crawl_status`](#crawl-status-tool) - Crawl progress monitoring

### Content Processing Tools
- [`extract`](#extract-tool) - AI-powered structured data extraction
- [`map`](#map-tool) - Website URL discovery and mapping

### Search Tools
- [`firesearch`](#firesearch-tool) - Web search with content extraction
- [`firerag`](#firerag-tool) - Vector search and RAG question answering

---

## Scrape Tool

Extract content from a single URL with advanced scraping options.

### When to Use
- **Best for**: Single page content extraction when you know the exact URL
- **Not recommended for**: Multiple pages (use `batch_scrape`), unknown URLs (use `firesearch`), structured data (use `extract`)

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Target URL to scrape |
| `formats` | array | No | Output formats: `["markdown", "html", "rawHtml", "screenshot", "links"]` |
| `onlyMainContent` | boolean | No | Extract only main content, excluding navigation/ads |
| `waitFor` | integer | No | Milliseconds to wait after page load (default: 0) |
| `timeout` | integer | No | Request timeout in milliseconds (default: 30000) |
| `mobile` | boolean | No | Use mobile user agent (default: false) |
| `includeTags` | array | No | HTML tags to include in extraction |
| `excludeTags` | array | No | HTML tags to exclude from extraction |
| `skipTlsVerification` | boolean | No | Skip TLS certificate verification (default: false) |
| `headers` | object | No | Custom HTTP headers |

### Examples

#### Basic Content Extraction
```json
{
  "name": "scrape",
  "arguments": {
    "url": "https://example.com/article",
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

#### Advanced Options
```json
{
  "name": "scrape", 
  "arguments": {
    "url": "https://dynamic-site.com",
    "formats": ["markdown", "links"],
    "waitFor": 2000,
    "timeout": 45000,
    "includeTags": ["article", "main", "section"],
    "excludeTags": ["nav", "footer", "aside"],
    "headers": {
      "User-Agent": "Custom Bot 1.0"
    }
  }
}
```

#### Mobile Scraping
```json
{
  "name": "scrape",
  "arguments": {
    "url": "https://mobile-optimized.com",
    "mobile": true,
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

### Response Format
```json
{
  "content": [
    {
      "type": "text",
      "text": "# Article Title\n\nArticle content in markdown format..."
    }
  ],
  "isError": false
}
```

### Error Handling
- **Invalid URL**: Returns validation error
- **Timeout**: Returns timeout error with retry suggestion  
- **Rate Limited**: Automatic retry with exponential backoff
- **Access Denied**: Returns 403/401 error details

---

## Batch Scrape Tool

Efficiently scrape multiple URLs with built-in rate limiting and parallel processing.

### When to Use
- **Best for**: Multiple known URLs that need content extraction
- **Not recommended for**: Single URL (use `scrape`), URL discovery (use `map` first)

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | array | Yes | Array of URLs to scrape (max 100 recommended) |
| `options` | object | No | Scraping options applied to all URLs |

#### Options Object
All parameters from the `scrape` tool can be used in the `options` object.

### Examples

#### Basic Batch Scraping
```json
{
  "name": "batch_scrape",
  "arguments": {
    "urls": [
      "https://blog.example.com/post-1",
      "https://blog.example.com/post-2", 
      "https://blog.example.com/post-3"
    ],
    "options": {
      "formats": ["markdown"],
      "onlyMainContent": true,
      "timeout": 30000
    }
  }
}
```

#### Advanced Batch Options
```json
{
  "name": "batch_scrape",
  "arguments": {
    "urls": [
      "https://news.site.com/article-1",
      "https://news.site.com/article-2"
    ],
    "options": {
      "formats": ["markdown", "links"],
      "waitFor": 1000,
      "includeTags": ["article", "main"],
      "excludeTags": ["nav", "footer", "sidebar"]
    }
  }
}
```

### Response Format
```json
{
  "content": [
    {
      "type": "text", 
      "text": "Batch operation queued with ID: batch_abc123. Use batch_status to check progress."
    }
  ],
  "isError": false
}
```

### Batch Processing
- Operations are processed asynchronously
- Returns immediately with batch ID for status tracking
- Parallel processing with rate limiting
- Progress reporting via `batch_status`

---

## Batch Status Tool

Monitor the progress and results of batch scraping operations.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Batch operation ID returned by `batch_scrape` |

### Examples

```json
{
  "name": "batch_status",
  "arguments": {
    "id": "batch_abc123"
  }
}
```

### Response Format

#### In Progress
```json
{
  "content": [
    {
      "type": "text",
      "text": "Batch operation batch_abc123: 2/5 completed (40%)"
    }
  ],
  "isError": false
}
```

#### Completed
```json
{
  "content": [
    {
      "type": "text",
      "text": "Batch operation completed. Results:\n\n[Scraped content from all URLs...]"
    }
  ],
  "isError": false
}
```

#### Failed
```json
{
  "content": [
    {
      "type": "text", 
      "text": "Batch operation failed: Rate limit exceeded"
    }
  ],
  "isError": true
}
```

---

## Crawl Tool

Start an asynchronous crawl job to extract content from multiple pages of a website.

### When to Use
- **Best for**: Comprehensive website content extraction, blog archives, documentation sites
- **Not recommended for**: Single pages (use `scrape`), when token limits are a concern (use `map` + `batch_scrape`)

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Starting URL pattern (supports wildcards) |
| `maxDepth` | integer | No | Maximum crawl depth (default: 2, max: 10) |
| `limit` | integer | No | Maximum pages to crawl (default: 100, max: 1000) |
| `allowExternalLinks` | boolean | No | Follow external links (default: false) |
| `deduplicateSimilarURLs` | boolean | No | Remove similar URLs (default: true) |
| `excludePaths` | array | No | URL patterns to exclude |
| `includePaths` | array | No | URL patterns to include |
| `formats` | array | No | Output formats (default: ["markdown"]) |
| `onlyMainContent` | boolean | No | Extract only main content (default: true) |

### Examples

#### Blog Crawling
```json
{
  "name": "crawl",
  "arguments": {
    "url": "https://blog.example.com/*",
    "maxDepth": 2,
    "limit": 50,
    "allowExternalLinks": false,
    "includePaths": ["/posts/*", "/articles/*"],
    "excludePaths": ["/admin/*", "/private/*"]
  }
}
```

#### Documentation Site Crawling
```json
{
  "name": "crawl",
  "arguments": {
    "url": "https://docs.example.com",
    "maxDepth": 3,
    "limit": 200,
    "deduplicateSimilarURLs": true,
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

#### Shallow Site Exploration
```json
{
  "name": "crawl", 
  "arguments": {
    "url": "https://company.com",
    "maxDepth": 1,
    "limit": 20,
    "excludePaths": ["/contact", "/privacy", "/terms"]
  }
}
```

### Response Format
```json
{
  "content": [
    {
      "type": "text",
      "text": "Started crawl for: https://blog.example.com/* with job ID: 550e8400-e29b-41d4-a716-446655440000. Use crawl_status to check progress."
    }
  ],
  "isError": false
}
```

### Crawl Considerations
- **Large Responses**: Crawl results can be very large and may exceed token limits
- **Rate Limiting**: Respects robots.txt and implements polite crawling
- **Progress Tracking**: Use `crawl_status` for real-time progress monitoring
- **Depth Strategy**: Start with shallow depths (1-2) to assess content volume

---

## Crawl Status Tool

Monitor crawl job progress and retrieve results.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | string | Yes | Crawl job ID returned by `crawl` tool |

### Examples

```json
{
  "name": "crawl_status",
  "arguments": {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Response Format

#### In Progress
```json
{
  "content": [
    {
      "type": "text",
      "text": "Crawl job 550e8400-e29b-41d4-a716-446655440000: 15/50 pages completed (30%). Current: https://blog.example.com/post-15"
    }
  ],
  "isError": false
}
```

#### Completed
```json
{
  "content": [
    {
      "type": "text",
      "text": "Crawl completed. Found 47 pages.\n\n# Page 1: Homepage\n[Content...]\n\n# Page 2: About\n[Content...]"
    }
  ],
  "isError": false
}
```

#### Failed
```json
{
  "content": [
    {
      "type": "text",
      "text": "Crawl job failed: Access denied to target domain"
    }
  ],
  "isError": true
}
```

---

## Extract Tool

Use AI to extract structured information from web pages with schema validation.

### When to Use
- **Best for**: Extracting specific structured data (prices, names, details)
- **Not recommended for**: Full page content (use `scrape`), unstructured data

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | array | Yes | URLs to extract information from |
| `prompt` | string | Yes | Custom extraction prompt for the LLM |
| `systemPrompt` | string | No | System prompt to guide the LLM |
| `schema` | object | No | JSON schema for structured data validation |
| `allowExternalLinks` | boolean | No | Allow extraction from external links |
| `enableWebSearch` | boolean | No | Enable web search for additional context |
| `includeSubdomains` | boolean | No | Include subdomains in extraction |

### Examples

#### Product Information Extraction
```json
{
  "name": "extract",
  "arguments": {
    "urls": ["https://store.example.com/product/123"],
    "prompt": "Extract product information including name, price, description, and availability",
    "schema": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "price": {"type": "number"},
        "description": {"type": "string"},
        "available": {"type": "boolean"},
        "category": {"type": "string"}
      },
      "required": ["name", "price"]
    }
  }
}
```

#### Contact Information Extraction
```json
{
  "name": "extract",
  "arguments": {
    "urls": [
      "https://company1.com/contact",
      "https://company2.com/about"
    ],
    "prompt": "Extract contact information including email, phone, and address",
    "systemPrompt": "You are a helpful assistant that extracts contact details from web pages. Be accurate and only extract explicitly stated information.",
    "schema": {
      "type": "object", 
      "properties": {
        "email": {"type": "string", "format": "email"},
        "phone": {"type": "string"},
        "address": {"type": "string"},
        "website": {"type": "string", "format": "uri"}
      }
    }
  }
}
```

#### Event Details Extraction
```json
{
  "name": "extract",
  "arguments": {
    "urls": ["https://events.example.com/conference-2024"],
    "prompt": "Extract event details including date, time, location, and speakers",
    "schema": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "date": {"type": "string", "format": "date"},
        "time": {"type": "string"},
        "location": {"type": "string"},
        "speakers": {
          "type": "array",
          "items": {"type": "string"}
        },
        "description": {"type": "string"}
      }
    }
  }
}
```

### Response Format
```json
{
  "content": [
    {
      "type": "text",
      "text": {
        "name": "Premium Widget",
        "price": 99.99,
        "description": "High-quality widget with advanced features",
        "available": true,
        "category": "Electronics"
      }
    }
  ],
  "isError": false
}
```

### LLM Configuration
- **Cloud API**: Uses Firecrawl's managed LLM service
- **Self-Hosted**: Uses your configured LLM instance
- **Model Selection**: Automatically optimized for extraction tasks
- **Token Limits**: Handles large pages with intelligent chunking

---

## Map Tool

Discover and map all indexed URLs on a website for exploration planning.

### When to Use
- **Best for**: URL discovery before targeted scraping, site structure analysis
- **Not recommended for**: Content extraction (use `scrape` after mapping), known URLs

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Website URL to map |
| `includePaths` | array | No | URL patterns to include |
| `excludePaths` | array | No | URL patterns to exclude |
| `includeSubdomains` | boolean | No | Include subdomains (default: false) |

### Examples

#### Basic Website Mapping
```json
{
  "name": "map",
  "arguments": {
    "url": "https://example.com"
  }
}
```

#### Filtered Mapping
```json
{
  "name": "map",
  "arguments": {
    "url": "https://blog.example.com",
    "includePaths": ["/posts/*", "/articles/*"],
    "excludePaths": ["/admin/*", "/private/*", "/api/*"]
  }
}
```

#### Subdomain Mapping
```json
{
  "name": "map",
  "arguments": {
    "url": "https://example.com",
    "includeSubdomains": true,
    "excludePaths": ["/cdn/*", "/static/*"]
  }
}
```

### Response Format
```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 47 URLs:\n\n- https://example.com/\n- https://example.com/about\n- https://example.com/contact\n- https://example.com/blog/post-1\n- https://example.com/blog/post-2\n..."
    }
  ],
  "isError": false
}
```

### Usage Patterns
1. **Map First**: Use `map` to discover URLs
2. **Filter Results**: Identify relevant URLs from the map
3. **Targeted Scraping**: Use `batch_scrape` on selected URLs
4. **Content Processing**: Apply `extract` for structured data

---

## Firesearch Tool

Search the web and optionally extract content from search results.

### When to Use
- **Best for**: Finding information across multiple websites, research queries
- **Not recommended for**: Known websites (use `scrape`/`crawl`), comprehensive site coverage

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query string |
| `limit` | integer | No | Maximum search results (default: 10, max: 100) |
| `lang` | string | No | Language code (e.g., "en", "es", "fr") |
| `country` | string | No | Country code (e.g., "us", "uk", "ca") |
| `scrapeOptions` | object | No | Options for scraping search results |

#### Scrape Options
All parameters from the `scrape` tool can be used in `scrapeOptions`.

### Examples

#### Basic Web Search
```json
{
  "name": "firesearch",
  "arguments": {
    "query": "latest AI research papers 2024",
    "limit": 5,
    "lang": "en"
  }
}
```

#### Search with Content Extraction
```json
{
  "name": "firesearch",
  "arguments": {
    "query": "best practices web scraping ethics",
    "limit": 10,
    "scrapeOptions": {
      "formats": ["markdown"],
      "onlyMainContent": true,
      "timeout": 30000
    }
  }
}
```

#### Localized Search
```json
{
  "name": "firesearch",
  "arguments": {
    "query": "restaurants near me",
    "limit": 15,
    "lang": "en",
    "country": "us",
    "scrapeOptions": {
      "formats": ["markdown"],
      "includeTags": ["article", "main"]
    }
  }
}
```

#### Technical Research
```json
{
  "name": "firesearch",
  "arguments": {
    "query": "Python FastAPI async performance optimization",
    "limit": 8,
    "scrapeOptions": {
      "formats": ["markdown", "links"],
      "onlyMainContent": true,
      "excludeTags": ["nav", "footer", "sidebar"]
    }
  }
}
```

### Response Format

#### Without Scraping
```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 5 search results:\n\n1. AI Research Papers 2024 - arxiv.org\n2. Latest AI Developments - nature.com\n3. Machine Learning Advances - mit.edu\n..."
    }
  ],
  "isError": false
}
```

#### With Content Scraping
```json
{
  "content": [
    {
      "type": "text", 
      "text": "Found 5 search results with content:\n\n# Result 1: AI Research Papers 2024\nURL: https://arxiv.org/list/cs.AI/recent\n\n## Recent Submissions\n[Full scraped content...]\n\n---\n\n# Result 2: Latest AI Developments\n[Content continues...]"
    }
  ],
  "isError": false
}
```

### Search Optimization
- **Query Quality**: Use specific, descriptive search terms
- **Result Limits**: Balance comprehensiveness with response size
- **Language/Country**: Improve result relevance with localization
- **Content Extraction**: Only scrape when content analysis is needed

---

## Firerag Tool

Perform vector search and RAG-style question answering using your vector database.

### When to Use
- **Best for**: Question answering from previously scraped content, semantic search
- **Not recommended for**: Fresh web data (use `firesearch`), when vector DB is empty

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Question or search query |
| `limit` | integer | No | Maximum results to return (default: 5) |
| `filters` | object | No | Metadata filters for search refinement |
| `responseMode` | string | No | "raw" or "synthesized" (default: "synthesized") |
| `llmModel` | string | No | LLM model for synthesis (when available) |
| `includeMetadata` | boolean | No | Include source metadata in response |

#### Filter Options
- `domain` - Filter by website domain
- `contentType` - Filter by content type
- `dateRange` - Filter by date range
- `language` - Filter by content language
- `repository` - Filter by repository (for code content)

### Examples

#### Basic Question Answering
```json
{
  "name": "firerag",
  "arguments": {
    "query": "What are the key features of Firecrawl?",
    "limit": 5,
    "responseMode": "synthesized"
  }
}
```

#### Domain-Filtered Search
```json
{
  "name": "firerag",
  "arguments": {
    "query": "API authentication methods",
    "limit": 8,
    "filters": {
      "domain": "docs.firecrawl.dev"
    },
    "responseMode": "synthesized",
    "includeMetadata": true
  }
}
```

#### Raw Chunk Retrieval
```json
{
  "name": "firerag",
  "arguments": {
    "query": "installation instructions",
    "limit": 10,
    "responseMode": "raw",
    "filters": {
      "contentType": "documentation"
    }
  }
}
```

#### Date-Filtered Research
```json
{
  "name": "firerag",
  "arguments": {
    "query": "recent security vulnerabilities",
    "limit": 15,
    "filters": {
      "dateRange": {
        "start": "2024-01-01",
        "end": "2024-12-31"
      }
    },
    "responseMode": "synthesized"
  }
}
```

#### Repository Code Search
```json
{
  "name": "firerag",
  "arguments": {
    "query": "async function implementation examples",
    "limit": 12,
    "filters": {
      "repository": "firecrawl",
      "contentType": "code"
    },
    "responseMode": "raw"
  }
}
```

### Response Format

#### Synthesized Mode
```json
{
  "content": [
    {
      "type": "text",
      "text": "Based on the documentation, Firecrawl's key features include:\n\n1. **Web Scraping**: Extract content from single URLs or batch process multiple pages\n2. **Website Crawling**: Deep crawl websites with configurable depth and limits\n3. **AI Extraction**: Use LLMs to extract structured data with schema validation\n4. **Vector Search**: Semantic search capabilities with metadata filtering\n\nSources: docs.firecrawl.dev/features, docs.firecrawl.dev/api-reference"
    }
  ],
  "isError": false
}
```

#### Raw Mode
```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 5 relevant chunks:\n\n**Chunk 1** (Score: 0.89)\nSource: docs.firecrawl.dev/features\nFirecrawl provides powerful web scraping and crawling capabilities...\n\n**Chunk 2** (Score: 0.85)\nSource: docs.firecrawl.dev/api-reference\nThe API supports both synchronous and asynchronous operations...\n\n[Additional chunks...]"
    }
  ],
  "isError": false
}
```

### Vector Search Configuration
- **Embedding Model**: Uses TEI (Text Embeddings Inference) for vector generation
- **Similarity Search**: Cosine similarity with configurable thresholds
- **Metadata Filtering**: Rich filtering on domains, dates, content types
- **LLM Integration**: OpenAI or Ollama for response synthesis

---

## Best Practices

### Tool Selection Guidelines

1. **Single Page Content**: Use `scrape`
2. **Multiple Known URLs**: Use `batch_scrape` 
3. **Website Exploration**: Use `map` then `batch_scrape`
4. **Comprehensive Coverage**: Use `crawl` (watch token limits)
5. **Structured Data**: Use `extract` with schemas
6. **Web Research**: Use `firesearch`
7. **Knowledge Base Queries**: Use `firerag`

### Performance Optimization

1. **Batch Operations**: Prefer `batch_scrape` over multiple `scrape` calls
2. **Content Filtering**: Use `onlyMainContent`, `includeTags`, `excludeTags`
3. **Timeout Management**: Set appropriate timeouts for dynamic content
4. **Rate Limiting**: Monitor logs for rate limit warnings
5. **Memory Management**: Limit crawl depth and batch sizes

### Error Handling Patterns

1. **Check Tool Response**: Always verify `isError` field
2. **Monitor Progress**: Use status tools for long operations
3. **Implement Retries**: Handle transient failures gracefully
4. **Log Analysis**: Review logs for debugging information
5. **Resource Monitoring**: Track credit usage and API limits

### Common Anti-Patterns

1. **Over-crawling**: Using `crawl` with excessive depth/limits
2. **Wrong Tool Selection**: Using `crawl` for known URLs
3. **Ignoring Rate Limits**: Not implementing backoff strategies
4. **Large Batches**: Sending too many URLs in batch operations
5. **Missing Validation**: Not validating URLs before processing

---

## Error Reference

### Common Error Types

#### Validation Errors
- Invalid URL format
- Missing required parameters
- Invalid parameter values
- Schema validation failures

#### Network Errors  
- Connection timeouts
- DNS resolution failures
- SSL/TLS verification errors
- Network connectivity issues

#### API Errors
- Rate limit exceeded
- Authentication failures
- Credit/quota exhausted
- Service unavailable

#### Content Errors
- Page not found (404)
- Access denied (403)
- Redirect loops
- Content parsing failures

### Error Response Format
```json
{
  "content": [
    {
      "type": "text",
      "text": "Error: Rate limit exceeded. Retrying in 30 seconds..."
    }
  ],
  "isError": true
}
```

### Troubleshooting Guide

1. **Validation Errors**: Check parameter types and formats
2. **Network Errors**: Verify connectivity and URL accessibility
3. **Rate Limits**: Implement delays and reduce concurrency
4. **Authentication**: Verify API key configuration
5. **Content Issues**: Check URL accessibility in browser

For detailed troubleshooting, see the [main README](../README.md#troubleshooting) and check the application logs in the `logs/` directory.