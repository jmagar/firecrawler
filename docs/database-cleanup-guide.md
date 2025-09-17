# Database Cleanup Guide

## Overview

This guide provides procedures for cleaning unwanted content from Firecrawl's dual storage architecture while maintaining data integrity and performance.

## Prerequisites

- PostgreSQL access with appropriate permissions
- Understanding of Firecrawl's dual storage architecture
- Backup procedures in place for production environments

## Common Cleanup Scenarios

### 1. Foreign Language Content Removal

#### Identify Foreign Content
```sql
-- Check vector storage for foreign language URLs
SELECT 
  metadata->>'domain' as domain,
  COUNT(*) as total_records,
  COUNT(CASE WHEN metadata->>'url' ~ '/en/' THEN 1 END) as english_records,
  COUNT(CASE WHEN metadata->>'url' !~ '/en/' THEN 1 END) as foreign_records
FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'docs.anthropic.com'
GROUP BY metadata->>'domain';

-- Check queue storage for foreign language URLs  
SELECT 
  COUNT(*) as total_records,
  COUNT(CASE WHEN data->>'url' ~ '/en/' THEN 1 END) as english_records,
  COUNT(CASE WHEN data->>'url' !~ '/en/' THEN 1 END) as foreign_records
FROM nuq.queue_scrape 
WHERE data->>'url' LIKE 'https://docs.anthropic.com%';
```

#### Remove Foreign Content
```sql
-- Vector storage cleanup (Anthropic docs example)
DELETE FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'docs.anthropic.com' 
  AND metadata->>'url' ~ '^https://docs\.anthropic\.com/(de|es|fr|it|pt|ru|zh-TW|zh|ja|ko|ar|id|zh-CN)/';

-- Queue storage cleanup (Anthropic docs example)  
DELETE FROM nuq.queue_scrape 
WHERE data->>'url' ~ '^https://docs\.anthropic\.com/(de|es|fr|it|pt|ru|zh-TW|zh|ja|ko|ar|id|zh-CN)/';
```

#### Language Code Reference
Common foreign language path patterns:
- `de` - German
- `es` - Spanish  
- `fr` - French
- `it` - Italian
- `pt` - Portuguese
- `ru` - Russian
- `zh-TW` - Traditional Chinese
- `zh` / `zh-CN` - Simplified Chinese
- `ja` - Japanese
- `ko` - Korean
- `ar` - Arabic
- `id` - Indonesian

### 2. Domain-Specific Cleanup

#### Remove Entire Domain
```sql
-- Remove all content from specific domain (vector storage)
DELETE FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'unwanted-domain.com';

-- Remove all content from specific domain (queue storage)
DELETE FROM nuq.queue_scrape 
WHERE data->>'url' LIKE 'https://unwanted-domain.com%';
```

#### Remove Specific URL Patterns
```sql
-- Remove specific URL patterns (vector storage)
DELETE FROM nuq.document_vectors 
WHERE metadata->>'url' ~ '^https://example\.com/deprecated/';

-- Remove specific URL patterns (queue storage)  
DELETE FROM nuq.queue_scrape 
WHERE data->>'url' ~ '^https://example\.com/deprecated/';
```

## Verification Procedures

### Pre-Cleanup Analysis
```sql
-- Count records by domain and language pattern
SELECT 
  metadata->>'domain' as domain,
  CASE 
    WHEN metadata->>'url' ~ '/en/' THEN 'English'
    ELSE 'Foreign'
  END as language_type,
  COUNT(*) as record_count
FROM nuq.document_vectors 
GROUP BY metadata->>'domain', language_type
ORDER BY domain, language_type;
```

### Post-Cleanup Verification
```sql
-- Verify cleanup results (vector storage)
SELECT 
  metadata->>'domain' as domain,
  COUNT(*) as remaining_records,
  MIN(metadata->>'url') as sample_url
FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'docs.anthropic.com'
GROUP BY metadata->>'domain';

-- Verify cleanup results (queue storage)
SELECT 
  COUNT(*) as remaining_records,
  MIN(data->>'url') as sample_url
FROM nuq.queue_scrape 
WHERE data->>'url' LIKE 'https://docs.anthropic.com%';
```

## Performance Impact Analysis

### Storage Savings Calculation
```sql
-- Calculate cleanup impact
WITH cleanup_stats AS (
  SELECT 
    'Vector Storage' as store_type,
    COUNT(*) as records_before,
    0 as records_after  -- Update with actual post-cleanup count
  FROM nuq.document_vectors 
  WHERE metadata->>'domain' = 'docs.anthropic.com'
  
  UNION ALL
  
  SELECT 
    'Queue Storage' as store_type,
    COUNT(*) as records_before,
    0 as records_after  -- Update with actual post-cleanup count
  FROM nuq.queue_scrape 
  WHERE data->>'url' LIKE 'https://docs.anthropic.com%'
)
SELECT 
  store_type,
  records_before,
  records_after,
  (records_before - records_after) as records_removed,
  ROUND(((records_before - records_after)::float / records_before * 100), 2) as percent_reduction
FROM cleanup_stats;
```

### Query Performance Impact
- Smaller result sets improve vector search response times
- Reduced storage requirements improve backup and maintenance operations
- Foreign language content removal eliminates search result noise

## Best Practices

### 1. Always Test First
```sql
-- Use SELECT before DELETE to verify target records
SELECT COUNT(*) FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'docs.anthropic.com' 
  AND metadata->>'url' ~ '^https://docs\.anthropic\.com/(de|es|fr)/';
```

### 2. Backup Critical Data
```sql
-- Create backup table before major cleanup
CREATE TABLE nuq.document_vectors_backup AS 
SELECT * FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'target-domain.com';
```

### 3. Monitor Both Storage Systems
- Always clean both `nuq.document_vectors` and `nuq.queue_scrape`
- Verify consistency between vector and queue storage
- Check for orphaned records after cleanup

### 4. Gradual Cleanup for Large Datasets
```sql
-- Process cleanup in batches for large datasets
DELETE FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'large-domain.com' 
  AND metadata->>'url' ~ 'unwanted-pattern'
LIMIT 1000;
```

## Recovery Procedures

### Restore from Backup
```sql
-- Restore specific domain from backup
INSERT INTO nuq.document_vectors 
SELECT * FROM nuq.document_vectors_backup 
WHERE metadata->>'domain' = 'restored-domain.com';
```

### Partial Recovery
```sql
-- Restore only specific URL patterns
INSERT INTO nuq.document_vectors 
SELECT * FROM nuq.document_vectors_backup 
WHERE metadata->>'url' ~ 'specific-pattern-to-restore';
```

## Automation Considerations

### Scheduled Cleanup
- Consider automating foreign language content cleanup for regularly updated sites
- Implement monitoring to detect foreign content accumulation
- Use configuration files to define language filtering rules per domain

### Integration with Crawling Process
- See [Language Filtering Guide](./language-filtering-guide.md) for prevention strategies
- Configure URL exclusion patterns to prevent foreign content collection
- Implement post-crawl validation to catch filtering failures