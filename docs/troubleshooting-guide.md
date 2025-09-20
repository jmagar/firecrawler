# Firecrawl Troubleshooting Guide

## Overview

This guide covers common issues encountered when working with Firecrawl's crawling, vector storage, and language filtering systems.

## Database Issues

### Vector Storage Problems

#### Symptom: No embeddings generated despite successful crawl
**Diagnosis**:
```sql
-- Check if vectors exist but embeddings are missing
SELECT 
  COUNT(*) as total_records,
  COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings
FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'your-domain.com';
```

**Common Causes**:
1. TEI (Text Embeddings Inference) service not running
2. Embedding model not loaded
3. Content too short/long for embedding generation

**Solutions**:
```bash
# Check TEI service status
curl http://localhost:8080/health

# Restart TEI service
docker-compose restart text-embeddings-inference

# Check embedding model configuration
grep -r "EMBEDDING_MODEL" /home/jmagar/compose/firecrawl/apps/api/.env*
```

#### Symptom: Database connection errors
**Diagnosis**:
```bash
# Test PostgreSQL connection
psql postgresql://user:pass@localhost:5432/nuq -c "SELECT 1;"

# Check service status
docker-compose ps postgres
```

**Solutions**:
- Verify database credentials in `.env` files
- Ensure PostgreSQL container is running
- Check network connectivity between services

### Queue Processing Issues

#### Symptom: Crawl jobs stuck in queue
**Diagnosis**:
```sql
-- Check queue status
SELECT 
  status,
  COUNT(*) as job_count
FROM nuq.queue_scrape 
GROUP BY status;

-- Find oldest pending jobs
SELECT 
  created_at,
  data->>'url' as url,
  status
FROM nuq.queue_scrape 
WHERE status = 'pending'
ORDER BY created_at ASC
LIMIT 10;
```

**Solutions**:
```bash
# Restart queue workers
docker-compose restart firecrawl-worker

# Check worker logs
docker-compose logs -f firecrawl-worker

# Monitor Bull dashboard
# Navigate to: http://localhost:3002/admin/@/queues/
```

## Crawling Issues

### Language Filtering Problems

#### Symptom: Foreign content still being crawled despite filters
**Diagnosis**:
```bash
# Check real-time crawl logs
docker-compose logs -f firecrawl-api | grep -E '/(de|es|fr|it)/'

# Verify engine configuration
grep -E "PLAYWRIGHT|FIRE_ENGINE" /home/jmagar/compose/firecrawl/apps/api/.env
```

**Root Causes & Solutions**:

1. **Playwright Engine Limitation**:
```bash
# Look for this warning in logs:
# "The engine used does not support the following features: location"

# Solution: Use URL exclusion patterns instead
curl -X POST http://localhost:3002/v2/crawl \
  -d '{"excludePaths": ["^/de/.*", "^/es/.*"]}'
```

2. **Incorrect API Version**:
```json
// ❌ Wrong: V1 syntax in V2 endpoint
{"crawlerOptions": {"excludes": ["de/"]}}

// ✅ Correct: V2 syntax
{"excludePaths": ["^/de/.*"]}
```

3. **Regex Pattern Issues**:
```json
// ❌ Wrong: Missing anchors
{"excludePaths": ["de"]}  // Matches "index.de" 

// ✅ Correct: Proper regex
{"excludePaths": ["^/de/.*"]}  // Matches "/de/anything"
```

#### Symptom: "Unrecognized key in body" error
**Cause**: Parameter mismatch between API versions

**Solutions**:
```bash
# Check API endpoint version
curl -X POST http://localhost:3002/v1/crawl  # V1 syntax
curl -X POST http://localhost:3002/v2/crawl  # V2 syntax

# Use correct parameter structure for each version
```

### Rate Limiting and Performance Issues

#### Symptom: Crawl timeouts or slow performance
**Diagnosis**:
```sql
-- Check crawl completion rates
SELECT 
  status,
  COUNT(*) as job_count,
  AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_time_seconds
FROM nuq.queue_scrape 
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY status;
```

**Solutions**:
1. **Reduce concurrency**:
```env
# In .env file
CRAWL_CONCURRENCY=2  # Reduce from default 5
```

2. **Optimize scrape options**:
```json
{
  "scrapeOptions": {
    "formats": ["markdown"],  // Remove "embeddings" if not needed
    "timeout": 30000         // Increase timeout
  }
}
```

3. **Use crawl limits**:
```json
{"limit": 100}  // Prevent runaway crawls
```

## API Issues

### Authentication Problems

#### Symptom: "Unauthorized" errors
**Diagnosis**:
```bash
# Test API key
curl -H "Authorization: Bearer fc-your-api-key" \
  http://localhost:3002/v2/crawl/test-id

# Check API key configuration
grep API_KEY /home/jmagar/compose/firecrawl/apps/api/.env*
```

**Solutions**:
- Verify API key format (should start with `fc-`)
- Check `.env` files for correct API key configuration
- Restart API service after configuration changes

### Request Format Issues

#### Symptom: Invalid request body errors
**Common Patterns**:

1. **Content-Type Headers**:
```bash
# ❌ Wrong: Missing content type
curl -X POST -d '{"url": "..."}' http://localhost:3002/v2/crawl

# ✅ Correct: With proper headers  
curl -X POST -H "Content-Type: application/json" \
  -d '{"url": "..."}' http://localhost:3002/v2/crawl
```

2. **JSON Syntax**:
```bash
# Use jq to validate JSON before sending
echo '{"url": "https://example.com"}' | jq '.'
```

## Vector Search Issues

### Embedding Generation Problems

#### Symptom: Search returns no results despite content existing
**Diagnosis**:
```sql
-- Check embedding quality
SELECT 
  metadata->>'url' as url,
  CASE 
    WHEN embedding IS NULL THEN 'No embedding'
    WHEN array_length(embedding, 1) < 100 THEN 'Short embedding'
    ELSE 'Normal embedding'
  END as embedding_status
FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'your-domain.com'
LIMIT 10;
```

**Solutions**:
1. **Restart embedding service**:
```bash
docker-compose restart text-embeddings-inference
```

2. **Check model loading**:
```bash
# Check TEI logs for model loading
docker-compose logs text-embeddings-inference | grep -i "model"
```

3. **Regenerate embeddings**:
```sql
-- Mark records for re-embedding
UPDATE nuq.document_vectors 
SET embedding = NULL 
WHERE metadata->>'domain' = 'problematic-domain.com';
```

### Search Performance Issues

#### Symptom: Slow vector search queries
**Diagnosis**:
```sql
-- Check database size and indexes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE tablename LIKE '%vector%';

-- Check for proper indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'document_vectors';
```

**Solutions**:
1. **Create vector indexes**:
```sql
-- Create HNSW index for vector similarity
CREATE INDEX IF NOT EXISTS idx_document_vectors_embedding 
ON nuq.document_vectors 
USING hnsw (embedding vector_cosine_ops);
```

2. **Cleanup old data**:
See [Database Cleanup Guide](./database-cleanup-guide.md)

## Service Integration Issues

### Bull Queue Dashboard Access

#### Symptom: Cannot access queue dashboard
**Diagnosis**:
```bash
# Check if Bull dashboard is enabled
curl http://localhost:3002/admin/@/queues/

# Check service configuration
grep -r "BULL_DASHBOARD" /home/jmagar/compose/firecrawl/apps/api/
```

**Solution**:
```env
# Enable Bull dashboard in .env
BULL_DASHBOARD_ENABLED=true
BULL_DASHBOARD_USERNAME=admin
BULL_DASHBOARD_PASSWORD=your-password
```

### TEI Integration Issues

#### Symptom: Embedding service connection errors
**Diagnosis**:
```bash
# Test TEI service directly
curl -X POST http://localhost:8080/embed \
  -H "Content-Type: application/json" \
  -d '{"inputs": "test text"}'

# Check service logs
docker-compose logs text-embeddings-inference
```

**Solutions**:
1. **Service startup order**:
```yaml
# In docker-compose.yaml
depends_on:
  - text-embeddings-inference
```

2. **Network configuration**:
```bash
# Ensure services can communicate
docker network ls
docker network inspect firecrawl_default
```

## Log Analysis and Debugging

### Key Log Locations
```bash
# API service logs
docker-compose logs -f firecrawl-api

# Worker logs  
docker-compose logs -f firecrawl-worker

# Database logs
docker-compose logs -f postgres

# TEI service logs
docker-compose logs -f text-embeddings-inference
```

### Common Log Patterns

#### Successful Operations
```
INFO: Crawl completed successfully - ID: abc123
INFO: Embedding generated for URL: https://example.com
INFO: Vector stored successfully
```

#### Error Patterns
```
ERROR: Failed to connect to embedding service
WARNING: The engine used does not support the following features: location
ERROR: Timeout waiting for scrape completion
```

### Debug Mode Activation
```env
# In .env file
LOG_LEVEL=debug
DEBUG_MODE=true
```

## Recovery Procedures

### Service Recovery
```bash
# Full service restart
docker-compose down
docker-compose up -d

# Individual service restart
docker-compose restart firecrawl-api
docker-compose restart firecrawl-worker
```

### Database Recovery
```sql
-- Check database health
SELECT version();
SELECT * FROM pg_stat_activity WHERE state = 'active';

-- Recovery from backup (if available)
-- Restore specific tables or entire database as needed
```

### Configuration Reset
```bash
# Backup current configuration
cp apps/api/.env apps/api/.env.backup

# Reset to example configuration
cp apps/api/.env.example apps/api/.env

# Restore custom settings as needed
```

## Monitoring and Prevention

### Health Check Endpoints
```bash
# API health
curl http://localhost:3002/health

# TEI health
curl http://localhost:8080/health

# Database connection test
psql postgresql://user:pass@localhost:5432/nuq -c "SELECT 1;"
```

### Automated Monitoring Setup
```bash
#!/bin/bash
# monitoring.sh - Run every 5 minutes via cron

# Check API health
if ! curl -f http://localhost:3002/health > /dev/null 2>&1; then
  echo "API health check failed" | mail -s "Firecrawl Alert" admin@example.com
fi

# Check queue processing
STUCK_JOBS=$(psql -t -c "SELECT COUNT(*) FROM nuq.queue_scrape WHERE status='pending' AND created_at < NOW() - INTERVAL '30 minutes'")
if [[ $STUCK_JOBS -gt 0 ]]; then
  echo "$STUCK_JOBS jobs stuck in queue" | mail -s "Firecrawl Queue Alert" admin@example.com
fi
```

This troubleshooting guide should be used alongside the other documentation files for comprehensive Firecrawl operations and maintenance.