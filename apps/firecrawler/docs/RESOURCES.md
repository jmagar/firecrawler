# Firecrawler MCP Resources Documentation

This document describes the Model Context Protocol (MCP) resources exposed by the Firecrawler server. Resources provide AI assistants with read-only access to server configuration, operational status, and usage information.

## Overview

Firecrawler MCP resources provide contextual information about:

- **Server Configuration**: Environment settings, API endpoints, and feature flags
- **Operational Status**: Service health, connectivity, and performance metrics
- **Usage Statistics**: Credit consumption, rate limiting, and operation history
- **Capability Information**: Available tools, supported formats, and limits

Resources are automatically updated and provide real-time insight into the server's operational state.

## Available Resources

### Configuration Resources

#### `firecrawler://config/server`
Server configuration and environment settings.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "host": "localhost",
  "port": 8000,
  "transport": "streamable-http",
  "logLevel": "INFO",
  "version": "1.0.0",
  "environment": "production"
}
```

#### `firecrawler://config/firecrawl`
Firecrawl API configuration and endpoints.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "apiBaseUrl": "https://api.firecrawl.dev",
  "version": "v2",
  "authenticationMethod": "api_key",
  "isConfigured": true,
  "selfHosted": false
}
```

#### `firecrawler://config/features`
Available features and capability flags.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "vectorSearch": {
    "enabled": true,
    "provider": "tei",
    "embeddingModel": "BAAI/bge-base-en-v1.5",
    "dimensions": 1024
  },
  "llmExtraction": {
    "enabled": true,
    "provider": "openai",
    "models": ["gpt-4", "gpt-3.5-turbo"]
  },
  "middleware": {
    "timing": true,
    "logging": true,
    "rateLimiting": true,
    "errorHandling": true
  }
}
```

### Status Resources

#### `firecrawler://status/health`
Overall server health and service connectivity.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime": 86400,
  "services": {
    "firecrawl_api": {
      "status": "connected",
      "lastCheck": "2024-01-15T10:29:55Z",
      "responseTime": 125
    },
    "vector_database": {
      "status": "connected", 
      "lastCheck": "2024-01-15T10:29:58Z",
      "responseTime": 45
    },
    "redis_cache": {
      "status": "connected",
      "lastCheck": "2024-01-15T10:29:59Z",
      "responseTime": 12
    }
  }
}
```

#### `firecrawler://status/performance`
Performance metrics and operational statistics.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "metrics": {
    "totalRequests": 1247,
    "averageResponseTime": 850,
    "successRate": 98.2,
    "errorRate": 1.8
  },
  "currentLoad": {
    "activeScrapes": 5,
    "activeCrawls": 2,
    "queuedOperations": 12
  },
  "resourceUsage": {
    "memoryUsage": 67.5,
    "cpuUsage": 23.1,
    "diskUsage": 45.8
  }
}
```

#### `firecrawler://status/rate-limits`
Current rate limiting status and thresholds.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "rateLimits": {
    "scrape": {
      "limit": 100,
      "remaining": 87,
      "resetTime": "2024-01-15T11:00:00Z"
    },
    "crawl": {
      "limit": 10,
      "remaining": 8,
      "resetTime": "2024-01-15T11:00:00Z"
    },
    "extract": {
      "limit": 50,
      "remaining": 42,
      "resetTime": "2024-01-15T11:00:00Z"
    }
  },
  "globalStatus": "within_limits"
}
```

### Usage Resources

#### `firecrawler://usage/credits`
Credit consumption and billing information.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "credits": {
    "remaining": 8750,
    "total": 10000,
    "consumed": 1250,
    "consumptionRate": "12.5%"
  },
  "billing": {
    "plan": "professional",
    "billingPeriod": "monthly",
    "nextRenewal": "2024-02-01T00:00:00Z"
  },
  "usage": {
    "scrapes": 847,
    "crawls": 23,
    "extractions": 156,
    "searches": 78
  }
}
```

#### `firecrawler://usage/operations`
Recent operation history and statistics.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "today": {
    "scrapes": 45,
    "crawls": 3,
    "extractions": 12,
    "searches": 8,
    "totalOperations": 68
  },
  "thisWeek": {
    "scrapes": 324,
    "crawls": 18,
    "extractions": 89,
    "searches": 45,
    "totalOperations": 476
  },
  "recentOperations": [
    {
      "type": "scrape",
      "url": "https://example.com",
      "timestamp": "2024-01-15T10:25:00Z",
      "status": "completed",
      "duration": 1250
    },
    {
      "type": "crawl",
      "url": "https://docs.example.com/*",
      "timestamp": "2024-01-15T10:20:00Z", 
      "status": "in_progress",
      "progress": "45%"
    }
  ]
}
```

### Capability Resources

#### `firecrawler://capabilities/tools`
Available tools and their specifications.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "tools": [
    {
      "name": "scrape",
      "description": "Extract content from a single URL",
      "parameters": {
        "url": {"type": "string", "required": true},
        "formats": {"type": "array", "default": ["markdown"]},
        "timeout": {"type": "integer", "default": 30000}
      }
    },
    {
      "name": "batch_scrape", 
      "description": "Scrape multiple URLs efficiently",
      "parameters": {
        "urls": {"type": "array", "required": true},
        "options": {"type": "object", "required": false}
      }
    },
    {
      "name": "crawl",
      "description": "Crawl a website and extract content from multiple pages",
      "parameters": {
        "url": {"type": "string", "required": true},
        "maxDepth": {"type": "integer", "default": 2},
        "limit": {"type": "integer", "default": 100}
      }
    }
  ],
  "totalTools": 9
}
```

#### `firecrawler://capabilities/formats`
Supported output formats and content types.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "outputFormats": [
    {
      "name": "markdown",
      "description": "Clean markdown representation",
      "mimeType": "text/markdown",
      "supported": true
    },
    {
      "name": "html", 
      "description": "Structured HTML content",
      "mimeType": "text/html",
      "supported": true
    },
    {
      "name": "screenshot",
      "description": "Page screenshot capture",
      "mimeType": "image/png",
      "supported": true
    },
    {
      "name": "links",
      "description": "Extracted links from page",
      "mimeType": "application/json",
      "supported": true
    }
  ],
  "contentTypes": [
    "text/html",
    "application/pdf",
    "text/plain",
    "application/json"
  ]
}
```

#### `firecrawler://capabilities/limits`
Operational limits and constraints.

**Content Type**: `application/json`

**Example Response**:
```json
{
  "limits": {
    "maxBatchSize": 100,
    "maxCrawlDepth": 10,
    "maxCrawlPages": 1000,
    "maxResponseSize": "50MB",
    "maxTimeout": 300000,
    "maxConcurrentOperations": 10
  },
  "quotas": {
    "dailyOperations": 1000,
    "monthlyCredits": 10000,
    "rateLimitPerMinute": 60
  },
  "restrictions": {
    "allowedDomains": "*",
    "blockedDomains": [],
    "requiresAuthentication": true
  }
}
```

## Resource Access Patterns

### Client Resource Reading

```typescript
// Example of accessing resources from an MCP client
const config = await client.readResource("firecrawler://config/server");
const health = await client.readResource("firecrawler://status/health");
const credits = await client.readResource("firecrawler://usage/credits");
```

### Resource Subscription

Resources support subscription for real-time updates:

```typescript
// Subscribe to resource changes
await client.subscribeToResource("firecrawler://status/health");
await client.subscribeToResource("firecrawler://usage/credits");

// Handle resource updates
client.on("resource_updated", (resource) => {
  console.log(`Resource ${resource.uri} updated:`, resource.content);
});
```

### Conditional Access

Some resources may have conditional availability:

- **Credit Information**: Only available when using cloud API
- **Vector Database Status**: Only available when vector search is enabled
- **Performance Metrics**: May require specific logging levels

## Resource Update Frequency

| Resource Category | Update Frequency | Trigger |
|-------------------|------------------|---------|
| Configuration | On startup/config change | Manual/restart |
| Health Status | Every 30 seconds | Automated |
| Performance Metrics | Every 60 seconds | Automated |
| Rate Limits | Real-time | Per request |
| Credit Usage | Real-time | Per operation |
| Operation History | Real-time | Per completion |

## Usage Examples

### Monitoring Server Health

```json
{
  "name": "read_resource",
  "arguments": {
    "uri": "firecrawler://status/health"
  }
}
```

Use this to check if all services are operational before performing bulk operations.

### Checking Credit Balance

```json
{
  "name": "read_resource", 
  "arguments": {
    "uri": "firecrawler://usage/credits"
  }
}
```

Monitor credit consumption to avoid service interruptions.

### Reviewing Rate Limits

```json
{
  "name": "read_resource",
  "arguments": {
    "uri": "firecrawler://status/rate-limits" 
  }
}
```

Check current rate limit status before starting intensive operations.

### Understanding Tool Capabilities

```json
{
  "name": "read_resource",
  "arguments": {
    "uri": "firecrawler://capabilities/tools"
  }
}
```

Dynamically discover available tools and their parameters.

### Checking Operation Limits

```json
{
  "name": "read_resource",
  "arguments": {
    "uri": "firecrawler://capabilities/limits"
  }
}
```

Understand operational constraints for planning bulk operations.

## Best Practices

### Resource Monitoring

1. **Health Checks**: Regularly monitor `status/health` for service issues
2. **Credit Monitoring**: Check `usage/credits` to prevent service interruption
3. **Rate Limit Awareness**: Monitor `status/rate-limits` during high-volume operations
4. **Performance Tracking**: Review `status/performance` for optimization opportunities

### Resource Caching

1. **Configuration**: Cache configuration resources as they change infrequently
2. **Capabilities**: Cache tool and format capabilities for client optimization
3. **Status Information**: Use fresh reads for real-time status data
4. **Usage Data**: Balance freshness with performance for usage statistics

### Error Handling

1. **Resource Unavailability**: Handle cases where resources may be temporarily unavailable
2. **Permission Errors**: Some resources may require specific authentication levels
3. **Stale Data**: Implement fallbacks for when real-time data is unavailable
4. **Network Issues**: Cache critical configuration data for offline operation

### Performance Optimization

1. **Selective Reading**: Only read resources when needed
2. **Batch Operations**: Group related resource reads when possible
3. **Subscription Management**: Unsubscribe from unused resource updates
4. **Update Throttling**: Avoid excessive polling of frequently updated resources

## Resource Schema Definitions

### Configuration Schema
```json
{
  "type": "object",
  "properties": {
    "server": {
      "type": "object",
      "properties": {
        "host": {"type": "string"},
        "port": {"type": "integer"},
        "transport": {"type": "string"},
        "version": {"type": "string"}
      }
    },
    "features": {
      "type": "object", 
      "properties": {
        "vectorSearch": {"type": "object"},
        "llmExtraction": {"type": "object"},
        "middleware": {"type": "object"}
      }
    }
  }
}
```

### Status Schema
```json
{
  "type": "object",
  "properties": {
    "health": {
      "type": "object",
      "properties": {
        "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
        "services": {"type": "object"},
        "timestamp": {"type": "string", "format": "date-time"}
      }
    },
    "performance": {
      "type": "object",
      "properties": {
        "metrics": {"type": "object"},
        "currentLoad": {"type": "object"},
        "resourceUsage": {"type": "object"}
      }
    }
  }
}
```

### Usage Schema
```json
{
  "type": "object",
  "properties": {
    "credits": {
      "type": "object",
      "properties": {
        "remaining": {"type": "integer"},
        "total": {"type": "integer"},
        "consumed": {"type": "integer"}
      }
    },
    "operations": {
      "type": "object",
      "properties": {
        "today": {"type": "object"},
        "thisWeek": {"type": "object"},
        "recentOperations": {"type": "array"}
      }
    }
  }
}
```

## Troubleshooting

### Common Issues

**Resource Not Found**:
- Verify the resource URI format
- Check if the feature is enabled in configuration
- Ensure proper authentication

**Stale Data**:
- Force refresh by re-reading the resource
- Check resource update frequency
- Verify network connectivity

**Permission Denied**:
- Verify API key configuration
- Check resource access permissions
- Review authentication settings

**Performance Issues**:
- Reduce resource polling frequency
- Cache static resources
- Use selective resource subscriptions

For additional support, see the [main documentation](../README.md) and check the application logs for detailed error information.