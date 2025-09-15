# Firecrawl MCP Vector Search - Requirements Document

## Overview

Add vector search capability to the existing Firecrawl MCP server by implementing vector search support in the JavaScript SDK and creating a new MCP tool that leverages this functionality.

## Goals

**Primary Objective**: Enable MCP clients (Claude, Cursor, etc.) to perform semantic vector search across previously crawled and indexed documents through the Firecrawl MCP server.

**Secondary Objectives**: 
- Maintain consistency with existing MCP server patterns
- Provide graceful error handling and user guidance
- Enable future expansion of vector search capabilities

## User Flow

### Happy Path
1. **User initiates search**: MCP client calls `firecrawl_vector_search` tool with a natural language query
2. **MCP server processes**: Validates parameters, calls Firecrawl JS SDK vector search method
3. **SDK makes API call**: Sends request to `/v2/vector-search` endpoint with query and filters
4. **API performs search**: Generates embedding for query, performs similarity search in vector database
5. **Results returned**: API returns structured results with similarity scores and metadata
6. **Response formatted**: MCP server formats results for display and returns structured content
7. **User sees results**: Both human-readable summary and machine-readable structured data

### Error Scenarios
- **No vector storage enabled**: Clear error message with troubleshooting steps
- **No embedded content**: Guidance to crawl content with embeddings first
- **TEI service unavailable**: Instructions to check embedding service
- **Invalid query**: Validation error with requirements

## Technical Implementation

### Phase 1: JavaScript SDK Enhancement

**Location**: `apps/js-sdk/firecrawl/src/v2/`

**Files to modify/create**:

1. **`types.ts`** - Add type definitions (~50 lines):
   ```typescript
   export interface VectorSearchRequest {
     query: string;
     limit?: number;
     offset?: number; 
     threshold?: number;
     includeContent?: boolean;
     filters?: VectorSearchFilters;
     origin?: string;
     integration?: string;
   }

   export interface VectorSearchFilters {
     domain?: string;
     repository?: string;
   }

   export interface VectorSearchResponse {
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
   ```

2. **`methods/vector-search.ts`** - New method file (~40 lines):
   - Input validation (non-empty query)
   - Payload preparation with defaults
   - HTTP POST to `/v2/vector-search`
   - Error handling following existing patterns

3. **`client.ts`** - Add method to FirecrawlClient (~3 lines):
   ```typescript
   async vectorSearch(request: VectorSearchRequest): Promise<VectorSearchResponse> {
     return vectorSearch(this.http, request);
   }
   ```

### Phase 2: MCP Server Integration

**Location**: `/home/jmagar/code/firecrawler/firecrawl-mcp-server/src/index.ts`

**Changes**: Add `firecrawl_vector_search` tool (~80 lines)

**Implementation details**:
- **Zod schema**: Parameter validation for query, limit, offset, threshold, filters
- **Tool execution**: Call SDK vector search method with validated parameters  
- **Response formatting**: Dual format (summary + raw JSON) handled by FastMCP
- **Error handling**: Contextual troubleshooting guidance based on error type

**Tool interface**:
```typescript
const vectorSearchParamsSchema = z.object({
  query: z.string().min(1).max(1000).describe('Natural language search query'),
  limit: z.number().int().min(1).max(100).optional().default(10),
  offset: z.number().int().min(0).optional().default(0),
  threshold: z.number().min(0).max(1).optional().default(0.7),
  includeContent: z.boolean().optional().default(true),
  filters: z.object({
    domain: z.string().optional(),
    repository: z.string().optional()
  }).optional()
});
```

### Phase 3: Testing

**Scope**: Minimal integration testing focusing on happy path

**Test coverage**:
- MCP server tool responds correctly to valid vector search requests
- Results are properly formatted with both summary and structured data
- Basic error handling works (invalid query, missing parameters)

**Assumptions**:
- Existing embedded test data is available in test environment
- Vector storage and TEI services are configured and running
- Focus on integration rather than comprehensive unit testing

## Response Format

### User-facing Summary
```markdown
**Query:** "React authentication best practices"
**Results:** 5 of 23 total
**Search Time:** 245ms (embedding: 89ms, search: 156ms)
**Credits Used:** 2

### Result 1: React Auth Guide (similarity: 0.892)
**URL:** https://docs.react.dev/learn/auth
**Domain:** docs.react.dev | **Type:** tutorial | **Words:** ~1,250

Best practices for implementing authentication in React applications...
```

### Structured Data
FastMCP automatically generates structured content from the returned JSON object, providing machine-readable access to:
- Search results array with metadata
- Performance metrics
- Query parameters
- Total result counts

## Error Handling Strategy

**Graceful failure with contextual guidance**:

- **Vector storage disabled**: Instructions to enable `ENABLE_VECTOR_STORAGE=true`
- **TEI connection failed**: Steps to check TEI service status and connectivity
- **No results found**: Suggestions to adjust threshold, broaden query, or check filters
- **Unauthorized**: API key validation and account credit verification
- **Generic errors**: General troubleshooting steps with error details

## Constraints and Assumptions

### Technical Constraints
- Must work with current FastMCP version (1.0.2) - no upgrades required
- TypeScript/Node.js implementation following existing patterns
- Minimal new dependencies
- Compatible with existing Firecrawl API vector search implementation

### Business Constraints  
- Focus on essential filters initially (defer advanced filters for future releases)
- Breaking changes allowed for MCP tool interface if necessary
- Don't modify existing MCP tools (separate from any v1→v2 SDK migrations)

### Implementation Assumptions
- Firecrawl API `/v2/vector-search` endpoint is stable and feature-complete
- Vector storage (PostgreSQL + pgvector) is properly configured in target environments
- TEI service is available for embedding generation
- MCP clients can handle both traditional text and structured content responses

## Success Criteria

### Functional Requirements
- [x] MCP clients can discover and call `firecrawl_vector_search` tool
- [x] Tool accepts natural language queries with optional filters
- [x] Returns semantically relevant results with similarity scores
- [x] Provides both human-readable and machine-readable response formats
- [x] Handles errors gracefully with helpful troubleshooting guidance

### Technical Requirements  
- [x] Follows existing SDK method patterns for consistency
- [x] Uses proper TypeScript types throughout implementation
- [x] Leverages FastMCP's automatic structured content generation
- [x] Maintains compatibility with existing MCP server functionality
- [x] Includes basic integration tests for happy path scenarios

### User Experience Requirements
- [x] Clear, actionable error messages when prerequisites aren't met
- [x] Response format suitable for both human review and programmatic use
- [x] Performance metrics visible to help users understand search costs
- [x] Intuitive parameter names and sensible defaults

## Future Enhancements

**Deferred for later implementation**:
- Advanced filters: `repositoryOrg`, `contentType`, `dateRange`
- Pagination helpers and result streaming
- Query suggestion/completion based on indexed content
- Batch vector search for multiple queries
- Custom embedding models and similarity metrics

## Risks and Mitigations

### Technical Risks
- **API changes**: Vector search API is relatively new - monitor for breaking changes
- **Performance**: Large result sets may impact MCP client responsiveness
- **Dependencies**: FastMCP compatibility with future MCP spec updates

### Mitigation Strategies
- Implement comprehensive error handling to surface API issues quickly
- Use pagination defaults to limit initial result set sizes
- Pin FastMCP version until testing confirms compatibility with updates
- Design interfaces to allow easy expansion of parameters and response fields