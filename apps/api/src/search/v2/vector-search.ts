import { embed } from "ai";
import { logger as _logger } from "../../lib/logger";
import type { Logger } from "winston";
import { getEmbeddingModel } from "../../lib/generic-ai";
import { calculateEmbeddingCost } from "../../lib/extract/usage/llm-cost";
import { CostTracking } from "../../lib/cost-tracking";
import {
  searchSimilarVectors,
  VectorSearchOptions,
  VectorSearchResult,
} from "../../services/vector-storage";
import {
  VectorSearchRequest,
  VectorSearchResponse,
  VectorSearchResult as APIVectorSearchResult,
} from "../../controllers/v2/types";

interface VectorSearchServiceOptions {
  logger?: Logger;
  costTracking?: CostTracking;
  teamId: string;
}

interface VectorSearchTiming {
  queryEmbeddingMs: number;
  vectorSearchMs: number;
  totalMs: number;
}

/**
 * Generates query embeddings using the configured TEI provider
 */
async function generateQueryEmbedding(
  query: string,
  options: VectorSearchServiceOptions,
): Promise<number[]> {
  const { logger = _logger, costTracking, teamId } = options;
  const start = Date.now();

  try {
    // Determine provider based on MODEL_EMBEDDING_NAME
    const modelName = process.env.MODEL_EMBEDDING_NAME;
    const provider =
      modelName && modelName.startsWith("sentence-transformers/")
        ? ("tei" as const)
        : undefined;

    const finalModelName = provider
      ? modelName || "sentence-transformers/all-MiniLM-L6-v2"
      : "text-embedding-3-small";

    logger.debug("Generating query embedding", {
      module: "vector_search/metrics",
      method: "generateQueryEmbedding",
      provider,
      model: finalModelName,
      queryLength: query.length,
    });

    const { embedding } = await embed({
      model: provider
        ? getEmbeddingModel(finalModelName, provider)
        : getEmbeddingModel(finalModelName),
      value: query,
      experimental_telemetry: {
        isEnabled: true,
        metadata: {
          teamId,
          module: "vector_search",
        },
      },
    });

    // Track embedding costs if cost tracking is provided
    if (costTracking) {
      const cost = calculateEmbeddingCost(finalModelName, query);

      costTracking.addCall({
        type: "other",
        metadata: {
          module: "vector_search",
          method: "generateQueryEmbedding",
        },
        model: finalModelName,
        cost: cost,
        tokens: {
          input: Math.ceil(query.length * 0.5), // Approximate token count
          output: 0, // Embeddings don't have output tokens
        },
      });
    }

    const duration = Date.now() - start;
    logger.info("Query embedding generated successfully", {
      module: "vector_search/metrics",
      method: "generateQueryEmbedding",
      duration,
      provider,
      model: finalModelName,
      embeddingDimension: embedding.length,
    });

    return embedding;
  } catch (error) {
    const duration = Date.now() - start;
    logger.error("Failed to generate query embedding", {
      module: "vector_search",
      method: "generateQueryEmbedding",
      error: error instanceof Error ? error.message : String(error),
      duration,
      queryLength: query.length,
    });
    throw new Error(
      `Failed to generate query embedding: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

/**
 * Transforms vector search request filters to vector storage options
 */
function transformFilters(request: VectorSearchRequest): VectorSearchOptions {
  const { filters, limit, offset, threshold } = request;

  const options: VectorSearchOptions = {
    limit: limit,
    minSimilarity: threshold,
  };

  if (filters?.domain) {
    options.domain = filters.domain;
  }

  if (filters?.repository) {
    options.repositoryName = filters.repository;
  }

  if (filters?.contentType) {
    options.contentType = filters.contentType;
  }

  if (filters?.dateRange) {
    options.dateRange = {
      start: filters.dateRange.from,
      end: filters.dateRange.to,
    };
  }

  return options;
}

/**
 * Transforms vector search results to API response format
 */
function transformResults(
  results: VectorSearchResult[],
  request: VectorSearchRequest,
  offset: number,
): APIVectorSearchResult[] {
  return results.map((result, index) => {
    const apiResult: APIVectorSearchResult = {
      id: result.jobId,
      url: result.metadata.url || "",
      title: result.metadata.title,
      similarity: result.similarity,
      metadata: {
        sourceURL: result.metadata.url || "",
        scrapedAt: result.metadata.created_at || new Date().toISOString(),
        domain: result.metadata.domain,
        repositoryName: result.metadata.repository_name,
        repositoryOrg: result.metadata.repository_org,
        filePath: result.metadata.file_path,
        contentType: result.metadata.content_type,
        wordCount: result.metadata.token_count
          ? Math.floor(result.metadata.token_count * 0.75)
          : undefined, // Convert tokens to approximate words
      },
    };

    // Include content if requested
    if (request.includeContent && result.content) {
      apiResult.content = result.content;
    }

    return apiResult;
  });
}

/**
 * Main vector search service that orchestrates the entire search process
 */
export async function vectorSearch(
  request: VectorSearchRequest,
  options: VectorSearchServiceOptions,
): Promise<VectorSearchResponse> {
  const { logger = _logger } = options;
  const startTime = Date.now();
  let queryEmbeddingTime = 0;
  let vectorSearchTime = 0;

  try {
    logger.info("Starting vector search", {
      module: "vector_search",
      method: "vectorSearch",
      query: request.query,
      limit: request.limit,
      offset: request.offset,
      threshold: request.threshold,
      filters: request.filters,
      includeContent: request.includeContent,
    });

    // Step 1: Generate query embedding
    const embeddingStart = Date.now();
    const queryEmbedding = await generateQueryEmbedding(request.query, options);
    queryEmbeddingTime = Date.now() - embeddingStart;

    // Step 2: Transform filters and add pagination
    const searchOptions = transformFilters(request);

    // Implement offset by increasing limit and slicing results
    // This is a simple approach; for large offsets, a cursor-based approach would be more efficient
    if (request.offset > 0) {
      searchOptions.limit = (searchOptions.limit || 10) + request.offset;
    }

    // Step 3: Perform vector similarity search
    const searchStart = Date.now();
    const vectorResults = await searchSimilarVectors(
      queryEmbedding,
      searchOptions,
      logger,
    );
    vectorSearchTime = Date.now() - searchStart;

    // Step 4: Apply offset by slicing results
    const offsetResults =
      request.offset > 0 ? vectorResults.slice(request.offset) : vectorResults;

    // Step 5: Limit results to requested amount
    const limitedResults = offsetResults.slice(0, request.limit);

    // Step 6: Transform results to API format
    const apiResults = transformResults(
      limitedResults,
      request,
      request.offset,
    );

    const totalTime = Date.now() - startTime;
    const timing: VectorSearchTiming = {
      queryEmbeddingMs: queryEmbeddingTime,
      vectorSearchMs: vectorSearchTime,
      totalMs: totalTime,
    };

    logger.info("Vector search completed successfully", {
      module: "vector_search/metrics",
      method: "vectorSearch",
      query: request.query,
      totalResults: vectorResults.length,
      returnedResults: apiResults.length,
      limit: request.limit,
      offset: request.offset,
      threshold: request.threshold,
      timing,
    });

    // Calculate credits used (1 credit per search + 1 per result returned)
    const creditsUsed = 1 + apiResults.length;

    return {
      success: true,
      data: {
        results: apiResults,
        query: request.query,
        totalResults: vectorResults.length, // Total results before pagination
        limit: request.limit,
        offset: request.offset,
        threshold: request.threshold,
        timing,
      },
      creditsUsed,
    };
  } catch (error) {
    const totalTime = Date.now() - startTime;
    const timing: VectorSearchTiming = {
      queryEmbeddingMs: queryEmbeddingTime,
      vectorSearchMs: vectorSearchTime,
      totalMs: totalTime,
    };

    logger.error("Vector search failed", {
      module: "vector_search",
      method: "vectorSearch",
      error: error instanceof Error ? error.message : String(error),
      query: request.query,
      timing,
    });

    // Return error response
    return {
      success: false,
      error: error instanceof Error ? error.message : "Vector search failed",
    };
  }
}

/**
 * Validates vector search request parameters
 */
export function validateVectorSearchRequest(
  request: VectorSearchRequest,
): string[] {
  const errors: string[] = [];

  if (!request.query || request.query.trim().length === 0) {
    errors.push("Query cannot be empty");
  }

  if (request.query && request.query.length > 1000) {
    errors.push("Query cannot exceed 1000 characters");
  }

  if (request.limit && (request.limit < 1 || request.limit > 100)) {
    errors.push("Limit must be between 1 and 100");
  }

  if (request.offset && request.offset < 0) {
    errors.push("Offset cannot be negative");
  }

  if (request.threshold && (request.threshold < 0 || request.threshold > 1)) {
    errors.push("Threshold must be between 0 and 1");
  }

  if (request.filters?.dateRange) {
    const { from, to } = request.filters.dateRange;
    if (from && to && new Date(from) > new Date(to)) {
      errors.push("Date range 'from' cannot be after 'to'");
    }
  }

  return errors;
}

/**
 * Health check for vector search service
 */
async function vectorSearchHealthCheck(
  logger: Logger = _logger,
): Promise<boolean> {
  const start = Date.now();

  try {
    // Test embedding generation with a simple query
    const testOptions: VectorSearchServiceOptions = {
      logger,
      teamId: "health-check",
    };

    await generateQueryEmbedding("test query", testOptions);

    logger.info("Vector search health check passed", {
      module: "vector_search/metrics",
      method: "vectorSearchHealthCheck",
      duration: Date.now() - start,
    });

    return true;
  } catch (error) {
    logger.error("Vector search health check failed", {
      module: "vector_search",
      method: "vectorSearchHealthCheck",
      error: error instanceof Error ? error.message : String(error),
      duration: Date.now() - start,
    });

    return false;
  }
}
