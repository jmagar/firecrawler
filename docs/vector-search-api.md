# Vector Search API Documentation

## Overview

The Firecrawl Vector Search API enables semantic search across your crawled content using text embeddings. Search through thousands of documents using natural language queries and get ranked results based on semantic similarity.

**Endpoint**: `POST /v2/vector-search`  
**Authentication**: Bearer token required  
**Rate Limit**: 100 requests/minute (default)  
**Billing**: 1 credit base + 1 credit per result returned

## Quick Start

### Basic Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "How to implement authentication in React applications?",
    "limit": 5
  }'
```

### Filtered Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "database optimization techniques",
    "limit": 10,
    "threshold": 0.8,
    "filters": {
      "domain": "docs.example.com",
      "contentType": "tutorial"
    }
  }'
```

## API Reference

### Request Schema

```typescript
interface VectorSearchRequest {
  query: string;                    // Required: 1-1000 characters
  limit?: number;                   // Optional: 1-100, default 10
  offset?: number;                  // Optional: ≥0, default 0
  threshold?: number;               // Optional: 0-1, default 0.7
  includeContent?: boolean;         // Optional: default true
  filters?: {
    domain?: string;
    repository?: string;
    repositoryOrg?: string;
    contentType?: "readme" | "api-docs" | "tutorial" | "configuration" | "code" | "other";
    dateRange?: {
      from?: string;                // ISO 8601 format
      to?: string;                  // ISO 8601 format
    };
  };
  origin?: string;                  // Optional: default "api"
  integration?: string;             // Optional: integration identifier
}
```

### Response Schema

```typescript
interface VectorSearchResponse {
  success: boolean;
  data: {
    results: VectorSearchResult[];
    query: string;
    totalResults: number;
    limit: number;
    offset: number;
    threshold: number;
    timing: {
      queryEmbeddingMs: number;
      vectorSearchMs: number;
      totalMs: number;
    };
  };
  creditsUsed: number;
  warning?: string;
}

interface VectorSearchResult {
  id: string;
  url: string;
  title?: string;
  content?: string;
  similarity: number;               // 0-1, higher = more similar
  metadata: {
    sourceURL: string;
    scrapedAt: string;
    domain?: string;
    repositoryName?: string;
    repositoryOrg?: string;
    filePath?: string;
    branchVersion?: string;
    contentType?: string;
    wordCount?: number;
    [key: string]: any;
  };
}
```

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Natural language search query (1-1000 characters) |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | 10 | Maximum results to return (1-100) |
| `offset` | number | 0 | Number of results to skip for pagination |
| `threshold` | number | 0.7 | Minimum similarity threshold (0-1, higher = more similar) |
| `includeContent` | boolean | true | Whether to include full page content in results |

### Filters

| Filter | Type | Description |
|--------|------|-------------|
| `domain` | string | Filter by specific domain (e.g., "docs.anthropic.com") |
| `repository` | string | Filter by GitHub repository name |
| `repositoryOrg` | string | Filter by GitHub organization |
| `contentType` | enum | Filter by content type: "readme", "api-docs", "tutorial", "configuration", "code", "other" |
| `dateRange` | object | Filter by scrape date range with `from` and `to` in ISO 8601 format |

## Examples

### 1. Simple Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "machine learning best practices"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "id": "doc_123",
        "url": "https://docs.example.com/ml-guide",
        "title": "Machine Learning Best Practices",
        "content": "When implementing machine learning...",
        "similarity": 0.92,
        "metadata": {
          "sourceURL": "https://docs.example.com/ml-guide",
          "scrapedAt": "2024-01-15T10:30:00.000Z",
          "domain": "docs.example.com",
          "contentType": "tutorial",
          "wordCount": 2500
        }
      }
    ],
    "query": "machine learning best practices",
    "totalResults": 1,
    "limit": 10,
    "offset": 0,
    "threshold": 0.7,
    "timing": {
      "queryEmbeddingMs": 45,
      "vectorSearchMs": 120,
      "totalMs": 165
    }
  },
  "creditsUsed": 2
}
```

### 2. Paginated Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "API authentication",
    "limit": 5,
    "offset": 10,
    "threshold": 0.75
  }'
```

### 3. Domain-Filtered Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "deployment strategies",
    "filters": {
      "domain": "docs.kubernetes.io",
      "contentType": "tutorial"
    }
  }'
```

### 4. Repository Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "component lifecycle",
    "filters": {
      "repositoryOrg": "facebook",
      "repository": "react"
    }
  }'
```

### 5. Date Range Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "security vulnerabilities",
    "filters": {
      "dateRange": {
        "from": "2024-01-01T00:00:00.000Z",
        "to": "2024-02-01T00:00:00.000Z"
      }
    }
  }'
```

### 6. Content-Only Search
```bash
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "error handling patterns",
    "includeContent": false,
    "limit": 20
  }'
```

## Authentication

Vector search requires a valid Firecrawl API key passed as a Bearer token:

```bash
-H "Authorization: Bearer fc-your-api-key"
```

## Rate Limiting

Vector search is subject to rate limiting based on your plan:
- **Search Mode**: 100 requests/minute (default)
- Rate limits apply per team/API key
- Exceeding limits returns HTTP 429

## Billing

Vector search uses a credit-based billing system:
- **Base cost**: 1 credit per search request
- **Result cost**: 1 credit per result returned
- **Example**: Search returning 5 results = 6 credits total

## Prerequisites

Before using vector search, ensure:

1. **Vector storage is enabled**: `ENABLE_VECTOR_STORAGE=true`
2. **Content has been crawled with embeddings**: Use `"formats": ["embeddings"]` during crawling
3. **TEI service is running**: Text embedding service must be accessible

### Crawling Content for Vector Search

```bash
# Crawl with embeddings enabled
curl -X POST https://api.firecrawl.dev/v1/crawl \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "url": "https://docs.example.com",
    "formats": ["markdown", "embeddings"],
    "crawlerOptions": {
      "limit": 100
    }
  }'
```

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "success": false,
  "error": "Invalid request parameters",
  "details": [
    {
      "code": "too_small",
      "minimum": 1,
      "type": "string",
      "inclusive": true,
      "message": "String must contain at least 1 character(s)",
      "path": ["query"]
    }
  ]
}
```

#### 401 Unauthorized
```json
{
  "success": false,
  "error": "Unauthorized"
}
```

#### 429 Rate Limited
```json
{
  "success": false,
  "error": "Rate limit exceeded"
}
```

#### 500 Internal Server Error
```json
{
  "success": false,
  "error": "Vector search failed",
  "code": "VECTOR_SEARCH_ERROR"
}
```

### Error Handling Best Practices

1. **Always check the `success` field** before processing results
2. **Handle rate limiting** with exponential backoff
3. **Validate request parameters** before sending
4. **Monitor credit usage** to avoid unexpected costs

```javascript
// Example error handling
async function searchVectors(query, options = {}) {
  try {
    const response = await fetch('/v2/vector-search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({ query, ...options })
    });

    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error);
    }
    
    return data.data.results;
  } catch (error) {
    if (error.status === 429) {
      // Implement retry with backoff
      await new Promise(resolve => setTimeout(resolve, 1000));
      return searchVectors(query, options);
    }
    throw error;
  }
}
```

## SDKs and Integration

### JavaScript/TypeScript

```javascript
import FirecrawlApp from '@mendable/firecrawl-js';

const app = new FirecrawlApp({ apiKey: 'fc-your-api-key' });

// Perform vector search
const searchResults = await app.vectorSearch({
  query: "Next.js routing best practices",
  limit: 10,
  filters: {
    domain: "nextjs.org"
  }
});

console.log(`Found ${searchResults.totalResults} results`);
searchResults.results.forEach(result => {
  console.log(`${result.title}: ${result.similarity}`);
});
```

### Python

```python
from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key='fc-your-api-key')

# Perform vector search
search_results = app.vector_search(
    query="Django authentication methods",
    limit=5,
    filters={
        "domain": "docs.djangoproject.com",
        "content_type": "tutorial"
    }
)

print(f"Found {search_results['totalResults']} results")
for result in search_results['results']:
    print(f"{result['title']}: {result['similarity']:.2f}")
```

### Rust

```rust
use firecrawl::FirecrawlApp;
use serde_json::json;

let app = FirecrawlApp::new("fc-your-api-key");

let search_params = json!({
    "query": "Rust async programming patterns",
    "limit": 10,
    "filters": {
        "domain": "doc.rust-lang.org"
    }
});

let results = app.vector_search(search_params).await?;
println!("Found {} results", results["totalResults"]);
```

## Performance Optimization

### Query Optimization

1. **Use specific queries**: "React hooks useEffect cleanup" vs "React"
2. **Appropriate thresholds**: Higher thresholds (0.8+) for precise matches
3. **Limit results**: Only request what you need to reduce cost and latency
4. **Use filters**: Domain/contentType filters significantly improve speed

### Similarity Thresholds

| Threshold | Use Case | Quality |
|-----------|----------|---------|
| 0.9-1.0 | Exact matches | Very high precision |
| 0.8-0.9 | Highly relevant | High precision |
| 0.7-0.8 | Relevant results | Balanced precision/recall |
| 0.6-0.7 | Broader search | Lower precision, higher recall |
| <0.6 | Exploratory search | Lower quality results |

### Pagination Best Practices

```bash
# Get first page
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "database indexing",
    "limit": 20,
    "offset": 0
  }'

# Get second page  
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{
    "query": "database indexing",
    "limit": 20,
    "offset": 20
  }'
```

## Troubleshooting

### Common Issues

#### No Results Returned
- **Check threshold**: Lower the threshold value (try 0.5)
- **Verify content exists**: Ensure documents were crawled with embeddings
- **Broaden query**: Use more general terms
- **Remove filters**: Temporarily remove filters to test

#### Slow Response Times
- **Reduce limit**: Lower the number of results requested
- **Add filters**: Use domain or contentType filters
- **Check service health**: Verify TEI service is responsive

#### High Credit Usage
- **Optimize limit**: Only request needed results
- **Use precise queries**: Avoid broad searches that return many results
- **Implement caching**: Cache frequent searches client-side

### Debug Commands

```bash
# Check vector storage health
curl https://api.firecrawl.dev/v2/health

# Test with minimal query
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{"query": "test", "limit": 1}'

# Check available content
curl -X POST https://api.firecrawl.dev/v2/vector-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fc-your-api-key" \
  -d '{"query": "the", "limit": 5, "threshold": 0.1}'
```

## Production Deployment

### Configuration Requirements

Essential environment variables:
```bash
# Vector storage
ENABLE_VECTOR_STORAGE=true
NUQ_DATABASE_URL=postgresql://user:pass@postgres:5432/nuq

# TEI service
TEI_URL=http://tei-service:8080
MODEL_EMBEDDING_NAME=Qwen/Qwen3-Embedding-0.6B
VECTOR_DIMENSION=1024

# Performance
MIN_SIMILARITY_THRESHOLD=0.5
MAX_EMBEDDING_CONTENT_LENGTH=5000
```

### Monitoring

Key metrics to monitor:
- **Query latency**: Track `timing.totalMs` in responses
- **Credit usage**: Monitor `creditsUsed` per request
- **Error rates**: Track failed requests by error type
- **Search quality**: Monitor result relevance and user satisfaction

### Scaling Considerations

1. **Database Performance**: 
   - Monitor PostgreSQL performance
   - Optimize HNSW index parameters
   - Consider read replicas for high-volume searches

2. **TEI Service**:
   - Scale horizontally with multiple TEI instances
   - Use GPU instances for better performance
   - Implement load balancing

3. **API Capacity**:
   - Monitor rate limits and adjust as needed
   - Implement request queuing for burst traffic
   - Cache frequent searches

## Security

### Data Privacy
- Vector search is **not compatible** with Zero Data Retention (ZDR)
- Search queries and results are logged for performance monitoring
- Implement appropriate access controls for sensitive content

### Access Control
- Use team-specific API keys for proper isolation
- Implement IP allowlisting if required
- Monitor API key usage for suspicious activity

### Content Security
- Filter out sensitive content during crawling
- Use domain filters to restrict search scope
- Regularly audit stored vector content

## Migration and Maintenance

### From Other Search Solutions

To migrate from traditional keyword search:
1. **Crawl content with embeddings**: Add `"embeddings"` to formats
2. **Test query patterns**: Compare semantic vs keyword results
3. **Adjust thresholds**: Fine-tune for your content quality
4. **Train users**: Semantic search works differently than keyword search

### Maintenance Tasks

#### Regular Cleanup
```sql
-- Remove old vectors (90+ days)
DELETE FROM nuq.document_vectors 
WHERE created_at < NOW() - INTERVAL '90 days';

-- Rebuild index periodically
REINDEX INDEX idx_document_vectors_similarity;
```

#### Performance Monitoring
```sql
-- Check vector storage size
SELECT pg_size_pretty(pg_total_relation_size('nuq.document_vectors')) as size;

-- Monitor search performance
SELECT 
  metadata->>'domain' as domain,
  COUNT(*) as vector_count,
  AVG(pg_column_size(content_vector)) as avg_vector_size
FROM nuq.document_vectors 
GROUP BY metadata->>'domain'
ORDER BY vector_count DESC;
```

## API Changelog

### Version 2.0
- Initial release of vector search API
- Support for semantic search with embeddings
- Domain and content type filtering
- Pagination and similarity thresholds

---

For setup and configuration instructions, see [TEI PGVector Setup Guide](./TEI_PGVECTOR_SETUP.md).

For troubleshooting common issues, see [Troubleshooting Guide](./troubleshooting-guide.md).