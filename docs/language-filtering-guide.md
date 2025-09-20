# Language Filtering Guide

## Overview

This guide provides comprehensive strategies for filtering foreign language content in Firecrawl crawling operations, covering both prevention (during crawling) and cleanup (post-crawling) approaches.

## Key Finding: Engine Dependencies

**Critical**: Language filtering capabilities depend on the scraping engine used:
- **Playwright Engine**: Does NOT support `location` parameters (default for self-hosted)
- **Fire Engine**: Supports geolocation-based filtering (cloud/enterprise)

## Prevention Strategies (Recommended)

### 1. URL-Based Filtering (V2 API) - Primary Solution

**Works with**: All engines (Playwright, Fire Engine)
**Effectiveness**: 80-95% depending on site URL structure

#### Basic Implementation
```json
{
  "url": "https://docs.anthropic.com/",
  "excludePaths": [
    "^/de/.*",
    "^/es/.*", 
    "^/fr/.*",
    "^/it/.*",
    "^/pt/.*",
    "^/ru/.*",
    "^/zh-TW/.*",
    "^/zh/.*",
    "^/ja/.*",
    "^/ko/.*",
    "^/ar/.*",
    "^/id/.*",
    "^/zh-CN/.*"
  ],
  "limit": 500,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"]
  }
}
```

#### Advanced URL Patterns
```json
{
  "excludePaths": [
    "^/[a-z]{2}/.*",           // Exclude all 2-letter language codes
    "^/[a-z]{2}-[A-Z]{2}/.*",  // Exclude locale codes (en-US, fr-FR)
    "^/docs/[^e].*",           // Exclude docs paths not starting with 'e'
    ".*\\?lang=(?!en).*"       // Exclude non-English query parameters
  ]
}
```

### 2. Fire Engine Configuration (Long-term Solution)

**Setup Requirements**:
```env
# In .env file
FIRE_ENGINE_BETA_URL=<your-fire-engine-endpoint>
```

**API Usage** (once Fire Engine is configured):
```json
{
  "url": "https://docs.anthropic.com/",
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "location": {
      "country": "US",
      "languages": ["en-US"]
    }
  }
}
```

## API Reference

### V2 API Structure (Recommended)
**Endpoint**: `/v2/crawl`
**File**: `/home/jmagar/compose/firecrawl/apps/api/src/controllers/v2/types.ts`

```typescript
interface CrawlRequest {
  url: string;
  excludePaths?: string[];    // Regex patterns for URL exclusion
  includePaths?: string[];    // Regex patterns for URL inclusion
  limit?: number;
  scrapeOptions?: {
    formats: string[];
    location?: {              // Only works with Fire Engine
      country: string;
      languages: string[];
    };
  };
}
```

### V1 API Structure (Legacy)
**Endpoint**: `/v1/crawl`

```typescript
interface V1CrawlRequest {
  url: string;
  crawlerOptions?: {
    excludes?: string[];      // Simple string patterns
  };
  scrapeOptions?: {
    formats: string[];
    location?: {
      country: string;
      languages: string[];
    };
  };
}
```

## Engine Detection and Troubleshooting

### Identify Current Engine
**Check Configuration**:
```bash
# Look for engine configuration
grep -r "PLAYWRIGHT_MICROSERVICE_URL\|FIRE_ENGINE" /home/jmagar/compose/firecrawl/apps/api/.env*
```

**Common Configurations**:
```env
# Playwright (Self-hosted default)
PLAYWRIGHT_MICROSERVICE_URL=http://playwright-service:3000/scrape
FIRE_ENGINE_BETA_URL=  # Empty

# Fire Engine (Cloud/Enterprise)  
FIRE_ENGINE_BETA_URL=https://your-fire-engine.com
```

### Engine Capability Matrix

| Feature | Playwright | Fire Engine |
|---------|------------|-------------|
| URL Exclusion | ✅ | ✅ |
| Location Filtering | ❌ | ✅ |
| Language Parameters | ❌ | ✅ |
| Custom Headers | ✅ | ✅ |
| JavaScript Rendering | ✅ | ✅ |

## Common URL Patterns by Platform

### Documentation Sites
```json
// GitBook/Docs platforms
"excludePaths": ["^/v/[^e].*", "^/[a-z]{2}/.*"]

// Confluence  
"excludePaths": ["^/display/[^E].*", "^/spaces/[^e].*"]

// Custom docs
"excludePaths": ["^/docs/(?!en).*", "^/help/(?!english).*"]
```

### E-commerce/Marketing Sites
```json
// Regional subdomains (handle at crawler level)
"excludePaths": ["^/[a-z]{2}-[a-z]{2}/.*", "^/(de|fr|es|it)/.*"]

// International sections
"excludePaths": ["^/global/(?!us).*", "^/regions/(?!america).*"]
```

## Testing and Validation

### Pre-Crawl Validation
```bash
# Test crawl with small limit to verify filtering
curl -X POST http://localhost:3002/v2/crawl \
  -H 'Authorization: Bearer fc-your-api-key' \
  -d '{
    "url": "https://docs.anthropic.com/",
    "excludePaths": ["^/de/.*", "^/es/.*"],
    "limit": 10,
    "scrapeOptions": {"formats": ["markdown"]}
  }'
```

### Real-time Monitoring
```bash
# Monitor crawl logs for foreign URLs
tail -f /var/log/firecrawl/crawler.log | grep -E '/(de|es|fr|it)/'

# Check Bull dashboard for crawl progress
# Navigate to: http://localhost:3002/admin/@/queues/
```

### Post-Crawl Verification
```sql
-- Check language distribution in results
SELECT 
  CASE 
    WHEN metadata->>'url' ~ '/en/' THEN 'English'
    WHEN metadata->>'url' ~ '/(de|es|fr|it|pt|ru|zh|ja|ko|ar|id)/' THEN 'Foreign'
    ELSE 'Unknown'
  END as language_category,
  COUNT(*) as page_count,
  ROUND(COUNT(*)::float / SUM(COUNT(*)) OVER() * 100, 1) as percentage
FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'your-target-domain.com'
GROUP BY language_category;
```

## Error Handling and Common Issues

### "Unrecognized key in body" Error
**Cause**: Using V1 API parameters in V2 endpoint or vice versa
**Solution**: Match parameter structure to API version

```json
// ❌ Wrong: V1 structure in V2 call
{"crawlerOptions": {"excludes": ["pattern"]}}

// ✅ Correct: V2 structure
{"excludePaths": ["^pattern.*"]}
```

### "Engine does not support location" Warning
**Cause**: Playwright engine receiving `location` parameters
**Solutions**:
1. Remove `location` parameters and use `excludePaths` instead
2. Configure Fire Engine for geolocation support
3. Accept warning and rely on URL-based filtering

### Incomplete Filtering
**Cause**: Complex or inconsistent URL patterns on target site
**Debugging**:
```sql
-- Analyze actual URL patterns in crawled data
SELECT 
  substring(metadata->>'url' from '^https://[^/]+(/[^/]+)?') as url_pattern,
  COUNT(*) as occurrence_count
FROM nuq.document_vectors 
WHERE metadata->>'domain' = 'target-domain.com'
GROUP BY url_pattern 
ORDER BY occurrence_count DESC;
```

## Performance Considerations

### Crawl Efficiency
- URL exclusion is processed before page fetching (efficient)
- Regex patterns are evaluated for every discovered URL
- Complex patterns can slow URL discovery phase

### Storage Impact
- Effective filtering reduces storage requirements by 70-90%
- Improves vector search quality and response times  
- Reduces processing overhead for embeddings generation

### Optimal Configuration
```json
{
  "limit": 500,              // Reasonable limit for most use cases
  "excludePaths": [          // Start with common patterns
    "^/de/.*", "^/es/.*", "^/fr/.*"
  ],
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"]  // Only what you need
  }
}
```

## Integration with Cleanup Procedures

### Hybrid Approach (Recommended)
1. **Primary**: URL-based filtering during crawl (80-95% effective)
2. **Secondary**: Post-crawl cleanup for missed content (see [Database Cleanup Guide](./database-cleanup-guide.md))
3. **Monitoring**: Regular validation of filtering effectiveness

### Automated Workflows
```bash
#!/bin/bash
# Example monitoring script
CRAWL_ID=$1
DOMAIN=$2

# Wait for crawl completion
while [[ $(curl -s "http://localhost:3002/v2/crawl/$CRAWL_ID" | jq -r '.status') != "completed" ]]; do
  sleep 30
done

# Validate language filtering
FOREIGN_COUNT=$(psql -t -c "SELECT COUNT(*) FROM nuq.document_vectors WHERE metadata->>'domain'='$DOMAIN' AND metadata->>'url' ~ '/(de|es|fr)/'")

if [[ $FOREIGN_COUNT -gt 0 ]]; then
  echo "Warning: $FOREIGN_COUNT foreign language pages detected"
  # Trigger cleanup procedure
fi
```

## Migration from V1 to V2

### Parameter Mapping
```json
// V1 Structure
{
  "crawlerOptions": {
    "excludes": ["de/", "es/", "fr/"]
  }
}

// V2 Structure  
{
  "excludePaths": [
    "^/de/.*",
    "^/es/.*", 
    "^/fr/.*"
  ]
}
```

### Benefits of V2
- More powerful regex-based exclusion patterns
- Better performance with complex filtering rules
- Improved error handling and validation
- Consistent parameter structure across endpoints