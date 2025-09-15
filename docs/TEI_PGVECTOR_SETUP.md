# TEI + pgvector Integration Setup Guide

## Overview
This guide explains how to set up Firecrawl with Text Embeddings Inference (TEI) and PostgreSQL pgvector for local embedding generation and vector storage.

## Prerequisites
- Docker and Docker Compose
- PostgreSQL with pgvector extension
- TEI service (or compatible embedding service)
- At least 8GB RAM recommended

## Architecture
```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Firecrawl │────▶│     TEI     │────▶│  PostgreSQL  │
│     API     │     │   Service   │     │  + pgvector  │
└─────────────┘     └─────────────┘     └──────────────┘
```

## Configuration

### 1. Environment Variables
Add these to your `.env` file:

```bash
# Vector Storage Configuration
ENABLE_VECTOR_STORAGE=true
NUQ_DATABASE_URL=postgresql://postgres:password@nuq-postgres:5432/postgres

# TEI Configuration  
TEI_URL=http://tei-service:8080
MODEL_EMBEDDING_NAME=Qwen/Qwen3-Embedding-0.6B  # Or your preferred model
VECTOR_DIMENSION=1024  # Must match your model's output dimension

# Optional configurations
MIN_SIMILARITY_THRESHOLD=0.5
MAX_EMBEDDING_CONTENT_LENGTH=5000
```

### 2. Docker Compose Setup
The `docker-compose.yaml` includes a PostgreSQL service with pgvector:

```yaml
services:
  nuq-postgres:
    build: ./apps/nuq-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### 3. Database Migrations
Migrations are automatically applied on container startup:
- `001_add_vector_support.sql` - Enables pgvector extension
- `002_create_document_vectors.sql` - Creates vector storage table

## Supported Embedding Models

### TEI-Compatible Models
- `Qwen/Qwen3-Embedding-0.6B` (1024 dimensions)
- `sentence-transformers/*` models
- `BAAI/bge-*` models
- `intfloat/e5-*` models

### OpenAI Models (Alternative)
- `text-embedding-ada-002` (1536 dimensions)
- `text-embedding-3-small` (1536 dimensions)
- `text-embedding-3-large` (3072 dimensions)

## API Endpoints

### 1. Crawl with Embeddings
```bash
curl -X POST http://localhost:3002/v1/crawl \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "url": "https://example.com",
    "formats": ["markdown", "embeddings"],
    "crawlerOptions": {
      "excludePaths": ["/de/", "/fr/"]
    }
  }'
```

### 2. Vector Search
```bash
curl -X POST http://localhost:3002/v2/vector-search \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "query": "your search query",
    "limit": 10,
    "filters": {
      "domain": "example.com"
    }
  }'
```

### 3. Scrape with Embeddings
```bash
curl -X POST http://localhost:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "url": "https://example.com/page",
    "formats": ["markdown", "embeddings"]
  }'
```

## Database Schema

### document_vectors Table
```sql
CREATE TABLE nuq.document_vectors (
    job_id VARCHAR(255) PRIMARY KEY,
    content_vector vector(1024),  -- Adjust dimension to match your model
    metadata jsonb,
    content text,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_document_vectors_similarity 
  ON nuq.document_vectors 
  USING hnsw (content_vector vector_cosine_ops);

CREATE INDEX idx_document_vectors_metadata 
  ON nuq.document_vectors 
  USING gin (metadata);
```

### Metadata Structure
```json
{
  "url": "https://example.com/page",
  "title": "Page Title",
  "domain": "example.com",
  "language": "en",
  "description": "Page description",
  "content_type": "article",
  "token_count": 1500,
  "created_at": "2024-01-01T00:00:00.000Z"
}
```

## Running TEI Service

### Using Docker
```bash
docker run -p 8080:80 \
  -v $PWD/models:/data \
  --name tei \
  ghcr.io/huggingface/text-embeddings-inference:cpu-1.5 \
  --model-id Qwen/Qwen3-Embedding-0.6B \
  --port 80 \
  --max-batch-tokens 8192
```

### GPU Support
```bash
docker run --gpus all -p 8080:80 \
  -v $PWD/models:/data \
  ghcr.io/huggingface/text-embeddings-inference:1.5 \
  --model-id Qwen/Qwen3-Embedding-0.6B
```

## Deployment

### 1. Build and Start Services
```bash
# Build all services
docker compose build

# Start services
docker compose up -d

# Check service health
docker compose ps
```

### 2. Verify Installation
```bash
# Check vector storage is enabled
curl http://localhost:3002/v2/health

# Test embedding generation
curl -X POST http://localhost:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "url": "https://example.com",
    "formats": ["embeddings"]
  }'
```

### 3. Monitor Vector Storage
```sql
-- Check vector count
SELECT COUNT(*) FROM nuq.document_vectors;

-- Check storage by domain
SELECT 
  metadata->>'domain' as domain,
  COUNT(*) as vectors
FROM nuq.document_vectors
GROUP BY metadata->>'domain';

-- Check storage size
SELECT 
  pg_size_pretty(pg_total_relation_size('nuq.document_vectors')) as size;
```

## Performance Optimization

### 1. HNSW Index Parameters
```sql
-- Adjust for better recall/performance trade-off
CREATE INDEX idx_vectors_hnsw 
  ON nuq.document_vectors 
  USING hnsw (content_vector vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

### 2. Query Optimization
```sql
-- Use proper limits and filters
SELECT * FROM nuq.document_vectors
WHERE metadata->>'domain' = 'example.com'
  AND content_vector <=> $1 < 0.5
ORDER BY content_vector <=> $1
LIMIT 10;
```

### 3. Batch Processing
- Use batch endpoints for multiple URLs
- Configure `MAX_BATCH_SIZE` for optimal throughput
- Monitor memory usage with large batches

## Troubleshooting

### Common Issues

1. **TEI Connection Errors**
   - Verify TEI service is running: `curl http://your-tei-service:8080/health`
   - Check network connectivity between services
   - Ensure correct TEI_URL in environment

2. **Vector Dimension Mismatch**
   - Ensure VECTOR_DIMENSION matches your model output
   - Check model documentation for correct dimensions
   - Rebuild database if dimension changes

3. **High Memory Usage**
   - Reduce batch sizes
   - Limit concurrent crawl jobs
   - Monitor with `docker stats`

4. **Slow Vector Search**
   - Rebuild HNSW index with optimized parameters
   - Add appropriate filters to reduce search space
   - Consider using approximate search for large datasets

### Debug Commands
```bash
# Check logs
docker compose logs -f api
docker compose logs -f nuq-postgres

# Test TEI directly
curl -X POST http://your-tei-service:8080/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"inputs": ["test text"]}'

# Check database connection
docker compose exec nuq-postgres psql -U postgres -c "\l"
```

## Security Considerations

1. **API Keys**: Always use authentication for production deployments
2. **Network Security**: Use proper network isolation for database
3. **Resource Limits**: Set appropriate Docker resource limits
4. **Data Privacy**: Consider data retention policies for stored vectors
5. **Access Control**: Implement proper access controls for vector search

## Migration from OpenAI

To migrate from OpenAI embeddings to TEI:

1. Update environment variables:
   ```bash
   # Comment out or remove
   # OPENAI_API_KEY=your-api-key-here
   
   # Add TEI configuration
   TEI_URL=http://tei-service:8080
   MODEL_EMBEDDING_NAME=Qwen/Qwen3-Embedding-0.6B
   ```

2. Rebuild vector storage with new dimensions if needed
3. Re-crawl content to generate new embeddings

## Cost Comparison

| Provider | Model | Dimensions | Cost/1M tokens | Self-hosted |
|----------|-------|------------|----------------|-------------|
| OpenAI | ada-002 | 1536 | $0.10 | No |
| TEI | Qwen3-0.6B | 1024 | $0.00 | Yes |
| TEI | BGE-large | 1024 | $0.00 | Yes |

## Additional Resources

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [TEI Documentation](https://huggingface.co/docs/text-embeddings-inference)
- [Firecrawl API Documentation](https://docs.firecrawl.dev)