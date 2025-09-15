# Firecrawl API Configuration Examples

## Overview

This document provides practical API configuration examples for common Firecrawl use cases, with focus on language filtering, performance optimization, and proper parameter usage.

## V2 API Examples (Recommended)

### Basic English-Only Crawl
```bash
curl -X POST http://localhost:3002/v2/crawl \
  -H "Authorization: Bearer fc-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.anthropic.com/",
    "excludePaths": [
      "^/de/.*",
      "^/es/.*",
      "^/fr/.*",
      "^/it/.*",
      "^/pt/.*",
      "^/ru/.*",
      "^/zh/.*",
      "^/ja/.*",
      "^/ko/.*"
    ],
    "limit": 500,
    "scrapeOptions": {
      "formats": ["markdown", "embeddings"]
    }
  }'
```

### Documentation Site with Comprehensive Language Filtering
```json
{
  "url": "https://docs.example.com/",
  "excludePaths": [
    "^/[a-z]{2}/.*",           
    "^/[a-z]{2}-[A-Z]{2}/.*",  
    "^/docs/(?!en).*",         
    "^/help/(?!english).*",    
    ".*\\?lang=(?!en).*"       
  ],
  "includePaths": [
    "^/en/.*",                 
    "^/docs/en/.*",            
    "^/api-reference/.*"       
  ],
  "limit": 1000,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "timeout": 60000
  }
}
```

### E-commerce Site with Regional Exclusions
```json
{
  "url": "https://shop.example.com/",
  "excludePaths": [
    "^/(de|fr|es|it|nl|pl|pt|ru|zh|ja|ko)/.*",
    "^/regions/(?!us).*",
    "^/store/(?!en).*",
    "^/checkout/.*\\?locale=(?!en).*"
  ],
  "includePaths": [
    "^/en/.*",
    "^/us/.*",
    "^/products/.*",
    "^/category/.*"
  ],
  "limit": 2000,
  "scrapeOptions": {
    "formats": ["markdown"],
    "excludeElementsCssSelector": "nav, footer, .sidebar, .ads",
    "onlyMainContent": true
  }
}
```

### Large Site with Performance Optimization
```json
{
  "url": "https://large-docs.example.com/",
  "excludePaths": [
    "^/archive/.*",
    "^/deprecated/.*",
    "^/v[0-9]+/.*",
    "^/[a-z]{2}/.*"
  ],
  "includePaths": [
    "^/docs/current/.*",
    "^/api/latest/.*",
    "^/guides/.*"
  ],
  "limit": 500,
  "scrapeOptions": {
    "formats": ["markdown"],
    "timeout": 30000,
    "waitFor": 2000,
    "onlyMainContent": true
  }
}
```

## V1 API Examples (Legacy Support)

### Basic V1 Crawl with Exclusions
```bash
curl -X POST http://localhost:3002/v1/crawl \
  -H "Authorization: Bearer fc-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.anthropic.com/",
    "crawlerOptions": {
      "excludes": [
        "de/",
        "es/", 
        "fr/",
        "it/"
      ]
    },
    "scrapeOptions": {
      "formats": ["markdown", "embeddings"]
    }
  }'
```

### V1 with Fire Engine Location Support
```json
{
  "url": "https://international-site.com/",
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "location": {
      "country": "US",
      "languages": ["en-US"]
    }
  },
  "crawlerOptions": {
    "limit": 1000
  }
}
```

## Specialized Configuration Patterns

### Multi-Language Site with Specific Language Selection
```json
{
  "url": "https://multi-lang-docs.com/",
  "excludePaths": [
    "^/(?!en|api|shared).*"
  ],
  "includePaths": [
    "^/en/.*",
    "^/api/.*",
    "^/shared/.*"
  ],
  "limit": 800,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "onlyMainContent": true
  }
}
```

### Academic/Research Site with Content Type Filtering
```json
{
  "url": "https://research.university.edu/",
  "excludePaths": [
    "^/[a-z]{2}/.*",
    "^/papers/draft/.*",
    "^/admin/.*",
    "^/login.*"
  ],
  "includePaths": [
    "^/papers/published/.*",
    "^/documentation/.*",
    "^/resources/.*"
  ],
  "limit": 1500,
  "scrapeOptions": {
    "formats": ["markdown"],
    "includeTags": ["h1", "h2", "h3", "p", "pre", "code"],
    "onlyMainContent": true,
    "timeout": 90000
  }
}
```

### API Documentation with Version Control
```json
{
  "url": "https://api-docs.example.com/",
  "excludePaths": [
    "^/v[0-2]/.*",
    "^/beta/.*",
    "^/[a-z]{2}/.*"
  ],
  "includePaths": [
    "^/v3/.*",
    "^/latest/.*",
    "^/reference/.*"
  ],
  "limit": 600,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "includeTags": ["h1", "h2", "h3", "h4", "p", "pre", "code", "table"],
    "excludeElementsCssSelector": ".sidebar-nav, .version-selector"
  }
}
```

## Testing and Validation Configurations

### Small Test Crawl for Pattern Validation
```json
{
  "url": "https://docs.example.com/",
  "excludePaths": [
    "^/de/.*",
    "^/es/.*"
  ],
  "limit": 5,
  "scrapeOptions": {
    "formats": ["markdown"]
  }
}
```

### Comprehensive Site Analysis (Large Limit)
```json
{
  "url": "https://comprehensive-site.com/",
  "excludePaths": [
    "^/[a-z]{2}/.*",
    "^/archive/.*"
  ],
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "onlyMainContent": true,
    "timeout": 45000
  }
}
```

## Error Handling and Retry Configurations

### Robust Configuration for Unreliable Sites
```json
{
  "url": "https://slow-site.example.com/",
  "excludePaths": [
    "^/[a-z]{2}/.*"
  ],
  "limit": 200,
  "scrapeOptions": {
    "formats": ["markdown"],
    "timeout": 120000,
    "waitFor": 5000,
    "retries": 3,
    "onlyMainContent": true
  }
}
```

### High-Performance Configuration for Fast Sites
```json
{
  "url": "https://fast-docs.example.com/",
  "excludePaths": [
    "^/[a-z]{2}/.*"
  ],
  "limit": 1000,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "timeout": 15000,
    "waitFor": 1000,
    "onlyMainContent": true
  }
}
```

## Response Handling Examples

### Check Crawl Status
```bash
# Get crawl status
CRAWL_ID="your-crawl-id"
curl -H "Authorization: Bearer fc-your-api-key" \
  "http://localhost:3002/v2/crawl/$CRAWL_ID"
```

### Monitor Crawl Progress
```bash
#!/bin/bash
CRAWL_ID=$1
API_KEY=$2

while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $API_KEY" \
    "http://localhost:3002/v2/crawl/$CRAWL_ID" | \
    jq -r '.status')
  
  echo "Status: $STATUS"
  
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    break
  fi
  
  sleep 10
done
```

## Advanced Pattern Examples

### Complex Regex Patterns for URL Filtering

#### Exclude Multiple Language Patterns
```json
{
  "excludePaths": [
    "^/(?:de|es|fr|it|pt|ru|zh(?:-CN|-TW)?|ja|ko|ar|id)/.*",
    "^/docs/(?:v[0-2]|legacy|old)/.*",
    "^/help/(?!en).*",
    ".*\\?(?:lang|locale)=(?!en|us).*"
  ]
}
```

#### Include Only Specific Sections
```json
{
  "includePaths": [
    "^/(?:en|api|docs/latest|guides|tutorials)/.*",
    "^/reference/(?:api|sdk)/.*",
    "^/$"
  ]
}
```

#### Complex Conditional Patterns
```json
{
  "excludePaths": [
    "^/community/(?!announcements).*",
    "^/blog/(?!technical).*",
    "^/user/(?!documentation).*"
  ],
  "includePaths": [
    "^/documentation/.*",
    "^/api/.*",
    "^/community/announcements/.*"
  ]
}
```

## Environment-Specific Configurations

### Development Environment
```json
{
  "url": "https://dev-docs.example.com/",
  "limit": 50,
  "scrapeOptions": {
    "formats": ["markdown"],
    "timeout": 30000
  }
}
```

### Staging Environment
```json
{
  "url": "https://staging-docs.example.com/",
  "limit": 200,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "timeout": 60000,
    "waitFor": 2000
  }
}
```

### Production Environment
```json
{
  "url": "https://docs.example.com/",
  "excludePaths": [
    "^/[a-z]{2}/.*"
  ],
  "limit": 1000,
  "scrapeOptions": {
    "formats": ["markdown", "embeddings"],
    "timeout": 45000,
    "waitFor": 2000,
    "onlyMainContent": true,
    "retries": 2
  }
}
```

## Best Practices Summary

### Parameter Guidelines
1. **Always use regex anchors**: `^` and `.*` for precise matching
2. **Test with small limits first**: Validate patterns before full crawls
3. **Choose appropriate formats**: Only request what you need
4. **Set reasonable timeouts**: Balance speed vs. reliability
5. **Use inclusion patterns**: More explicit than exclusion for complex sites

### Performance Optimization
1. **Limit concurrent operations**: Use reasonable `limit` values
2. **Optimize scrape options**: Remove unnecessary format requirements
3. **Filter at URL level**: More efficient than content filtering
4. **Use `onlyMainContent`**: Reduces noise and improves processing speed

### Error Prevention
1. **Validate JSON syntax**: Use tools like `jq` before sending
2. **Match API version**: V1 vs V2 parameter structures
3. **Test authentication**: Verify API keys before complex operations
4. **Monitor logs**: Check for engine compatibility warnings