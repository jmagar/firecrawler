# Firecrawl Database Architecture

## Overview

Firecrawl maintains a dual storage architecture with two primary data stores for crawled content, both using PostgreSQL with JSONB for flexible schema storage.

## Primary Data Stores

### 1. Vector Embeddings Storage
**Table**: `nuq.document_vectors`
- **Purpose**: Stores processed embeddings for semantic search
- **Key Fields**:
  - `metadata` (JSONB): Contains `domain`, `url`, and other crawl metadata
  - Vector embeddings for AI-powered search
- **Access Pattern**: Used by vector search API endpoints
- **Related Code**: `/home/jmagar/compose/firecrawl/apps/api/src/services/vector-storage.ts`

### 2. Original Content Storage  
**Table**: `nuq.queue_scrape`
- **Purpose**: Stores original scraped content and job queue data
- **Key Fields**:
  - `data` (JSONB): Contains original scraped content with URL at `data->>'url'`
- **Access Pattern**: Used by queue worker processing system
- **Related Code**: Queue worker processing system

## Data Flow Architecture

```
Web Page → Scraper → nuq.queue_scrape → Processing → nuq.document_vectors
                         ↓                              ↓
                   Original Content              Vector Embeddings
```

## JSONB Schema Patterns

### Vector Storage Metadata Structure
```sql
metadata: {
  "domain": "docs.anthropic.com",
  "url": "https://docs.anthropic.com/en/docs/overview",
  "language": "en",
  -- other metadata fields
}
```

### Queue Storage Data Structure
```sql
data: {
  "url": "https://docs.anthropic.com/en/docs/overview",
  "content": "...",
  -- other scraped data fields
}
```

## Database Operations

### Querying Vector Storage
```sql
-- Find by domain
SELECT * FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'docs.anthropic.com';

-- Language-based filtering
SELECT * FROM nuq.document_vectors 
WHERE metadata->>'language' = 'en';

-- URL pattern matching
SELECT * FROM nuq.document_vectors 
WHERE metadata->>'url' ~ '^https://example\.com/en/';
```

### Querying Queue Storage
```sql
-- Find by URL pattern
SELECT * FROM nuq.queue_scrape 
WHERE data->>'url' ~ '^https://docs\.anthropic\.com/en/';

-- Count by domain
SELECT COUNT(*) FROM nuq.queue_scrape 
WHERE data->>'url' LIKE 'https://docs.anthropic.com%';
```

## Performance Considerations

### Indexing Strategy
- JSONB fields benefit from GIN indexes for efficient querying
- URL pattern matching uses regex operations which can be expensive
- Consider partial indexes for frequently queried domains

### Storage Efficiency
- Both tables can grow large with extensive crawling
- Regular cleanup of unwanted content improves query performance
- Foreign language content removal can significantly reduce storage requirements

## Integration with TEI + pgvector

### Vector Search Setup
- Uses Qwen/Qwen3-Embedding-0.6B model via TEI (Text Embeddings Inference)
- pgvector extension provides vector similarity search capabilities
- Vector embeddings stored alongside metadata for comprehensive search

### Configuration Files
- **TEI Setup**: `/home/jmagar/compose/firecrawl/docs/TEI_PGVECTOR_SETUP.md`
- **Database Config**: Standard PostgreSQL with JSONB and vector extensions

## Maintenance Operations

### Data Cleanup
See [Database Cleanup Guide](./database-cleanup-guide.md) for detailed procedures on removing unwanted content while preserving data integrity.

### Monitoring
- Monitor table sizes: `SELECT pg_size_pretty(pg_total_relation_size('nuq.document_vectors'));`
- Track queue processing: Monitor `nuq.queue_scrape` for processing backlogs
- Vector storage health: Check embedding generation and storage consistency