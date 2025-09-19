import { embed } from "ai";
import { logger as _logger } from "../../lib/logger";
import type { Logger } from "winston";
import { getEmbeddingModel } from "../../lib/generic-ai";
import { calculateEmbeddingCost } from "../../lib/extract/usage/llm-cost";
import { CostTracking } from "../../lib/cost-tracking";
import { DEFAULT_MIN_SIMILARITY_THRESHOLD } from "../../lib/similarity";
import {
  API_TO_INTERNAL_CONTENT_TYPE,
  INTERNAL_TO_API_CONTENT_TYPE,
} from "../../shared/content-types";
import {
  validateEmbeddingDimension,
  validateModelConfiguration,
  getVectorDimension,
  KNOWN_MODEL_DIMENSIONS,
} from "../../lib/embedding-utils";
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
  thresholdProvided?: boolean;
}

interface VectorSearchTiming {
  queryEmbeddingMs: number;
  vectorSearchMs: number;
  totalMs: number;
}

function clampThreshold(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function buildThresholdCandidates(
  requestThreshold: number | undefined | null,
  thresholdProvided?: boolean,
): number[] {
  if (
    thresholdProvided &&
    typeof requestThreshold === "number" &&
    Number.isFinite(requestThreshold)
  ) {
    return [clampThreshold(requestThreshold)];
  }

  const base = clampThreshold(
    typeof requestThreshold === "number" && Number.isFinite(requestThreshold)
      ? requestThreshold
      : DEFAULT_MIN_SIMILARITY_THRESHOLD,
  );

  // Parse configurable threshold floors from environment variables
  const parseEnvFloat = (envVar: string, defaultValue: number): number => {
    const value = process.env[envVar];
    if (!value) return defaultValue;
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : defaultValue;
  };

  const thresholdFloor1 = parseEnvFloat("VECTOR_THRESHOLD_FLOOR_1", 0.55);
  const thresholdFloor2 = parseEnvFloat("VECTOR_THRESHOLD_FLOOR_2", 0.4);
  const thresholdFloor3 = parseEnvFloat("VECTOR_THRESHOLD_FLOOR_3", 0.3);

  const candidates = [
    base,
    Math.max(base - 0.1, thresholdFloor1),
    Math.max(base - 0.25, thresholdFloor2),
    thresholdFloor3,
  ];

  // Use a more reliable epsilon for floating-point comparison
  // Number.EPSILON * 10 provides better precision than hardcoded values
  const THRESHOLD_EPSILON = Number.EPSILON * 10;
  const unique: number[] = [];

  for (const candidate of candidates) {
    const clamped = clampThreshold(candidate);
    if (
      unique.some(existing => Math.abs(existing - clamped) < THRESHOLD_EPSILON)
    ) {
      continue;
    }
    unique.push(clamped);
  }

  return unique;
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

  // Read once per call inside try to keep error handling consistent
  let configuredVectorDimension: number;
  try {
    configuredVectorDimension = getVectorDimension();
    // Validate model configuration early and get resolved model name and provider
    const { modelName: finalModelName, provider } =
      validateModelConfiguration();

    logger.debug("Generating query embedding", {
      module: "vector_search/metrics",
      method: "generateQueryEmbedding",
      provider,
      model: finalModelName,
      queryLength: query.length,
      configuredVectorDimension,
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

    // Validate embedding dimension immediately after generation
    validateEmbeddingDimension(embedding, finalModelName, provider);

    // Track embedding costs if cost tracking is provided
    if (costTracking) {
      // Estimate embedding cost for the query
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
      configuredVectorDimension,
      dimensionValidated: true,
    });

    return embedding;
  } catch (error) {
    const duration = Date.now() - start;
    // Task 3: Log detailed error locally
    logger.error("Failed to generate query embedding", {
      module: "vector_search",
      method: "generateQueryEmbedding",
      error: error instanceof Error ? error.message : String(error),
      duration,
      queryLength: query.length,
    });
    // Task 3: Throw generic error without internal details
    throw new Error("Failed to generate query embedding");
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

  if (filters?.repositoryOrg) {
    options.repositoryOrg = filters.repositoryOrg;
  }

  if (filters?.contentType) {
    // Map API content type to internal content type
    options.contentType =
      API_TO_INTERNAL_CONTENT_TYPE[filters.contentType] || filters.contentType;
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
        scrapedAt: result.metadata.created_at || "",
        domain: result.metadata.domain,
        repositoryName: result.metadata.repository_name,
        repositoryOrg: result.metadata.repository_org,
        filePath: result.metadata.file_path,
        contentType: result.metadata.content_type
          ? INTERNAL_TO_API_CONTENT_TYPE[result.metadata.content_type] ||
            result.metadata.content_type
          : undefined,
        approxWordCount: result.metadata.token_count
          ? Math.floor(result.metadata.token_count * 0.75)
          : undefined, // Approximate words = floor(token_count * 0.75)
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
  const { logger = _logger, thresholdProvided } = options;
  const startTime = Date.now();
  let queryEmbeddingTime = 0;
  let vectorSearchTime = 0;

  try {
    logger.info("Starting vector search", {
      module: "vector_search",
      method: "vectorSearch",
      // Do not log raw queries
      queryLength: request.query?.length,
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
    const thresholdCandidates = buildThresholdCandidates(
      request.threshold,
      thresholdProvided,
    );
    const thresholdHistory: number[] = [];
    let usedThreshold = thresholdCandidates[thresholdCandidates.length - 1];

    logger.debug("Vector search threshold candidates", {
      module: "vector_search",
      method: "vectorSearch",
      thresholdCandidates,
      thresholdProvided,
    });
    let vectorResults: VectorSearchResult[] = [];

    // Record all candidates considered
    thresholdHistory.push(...thresholdCandidates);
    // Single-pass at the lowest candidate
    const minCandidate = Math.min(...thresholdCandidates);
    searchOptions.minSimilarity = minCandidate;
    const attemptStart = Date.now();
    const allResults = await searchSimilarVectors(
      queryEmbedding,
      searchOptions,
      logger,
    );
    vectorSearchTime += Date.now() - attemptStart;
    // Pick the highest threshold that still yields results
    const sortedDesc = [...thresholdCandidates].sort((a, b) => b - a);
    usedThreshold = minCandidate;
    for (const t of sortedDesc) {
      const filtered = allResults.filter(r => r.similarity >= t);
      if (filtered.length > 0) {
        usedThreshold = t;
        vectorResults = filtered;
        break;
      }
    }
    // If no results at any threshold, keep empty vectorResults and usedThreshold=minCandidate

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

    const fallbackUsed =
      thresholdHistory.length > 1 &&
      !thresholdProvided &&
      (vectorResults.length > 0 || usedThreshold !== thresholdHistory[0]);

    logger.info("Vector search completed successfully", {
      module: "vector_search/metrics",
      method: "vectorSearch",
      // Do not log raw queries
      queryLength: request.query?.length,
      totalResults: vectorResults.length,
      returnedResults: apiResults.length,
      limit: request.limit,
      offset: request.offset,
      threshold: usedThreshold,
      thresholdHistory,
      fallbackUsed,
      timing,
    });

    // Calculate credits used (1 credit per search + 1 per result returned)
    const creditsUsed = 1 + apiResults.length;

    const warning = fallbackUsed
      ? `Vector search returned no results at similarity ≥ ${
          thresholdHistory.length > 0 ? thresholdHistory[0].toFixed(2) : "N/A"
        }, so retried with a lower threshold (${usedThreshold.toFixed(2)}).`
      : undefined;

    return {
      success: true,
      data: {
        results: apiResults,
        query: request.query,
        totalResults: vectorResults.length, // Total results before pagination
        limit: request.limit,
        offset: request.offset,
        threshold: usedThreshold,
        thresholdHistory,
        timing,
      },
      creditsUsed,
      warning,
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
      // Do not log raw queries
      queryLength: request.query?.length,
      timing,
    });

    // Return error response
    return {
      success: false,
      error: "Vector search failed",
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

  if (
    request.limit !== undefined &&
    request.limit !== null &&
    (!Number.isInteger(request.limit) ||
      request.limit < 1 ||
      request.limit > 100)
  ) {
    errors.push("Limit must be between 1 and 100");
  }

  if (
    request.offset !== undefined &&
    request.offset !== null &&
    (!Number.isInteger(request.offset) || request.offset < 0)
  ) {
    errors.push("Offset cannot be negative");
  }

  if (
    request.threshold !== undefined &&
    request.threshold !== null &&
    (!Number.isFinite(request.threshold) ||
      request.threshold < 0 ||
      request.threshold > 1)
  ) {
    errors.push("Threshold must be between 0 and 1");
  }

  if (request.filters?.dateRange) {
    const { from, to } = request.filters.dateRange;
    const fromTime = from ? Date.parse(from) : NaN;
    const toTime = to ? Date.parse(to) : NaN;
    if ((from && Number.isNaN(fromTime)) || (to && Number.isNaN(toTime))) {
      errors.push("Date range 'from'/'to' must be valid ISO-8601 dates");
    }
    if (
      Number.isFinite(fromTime) &&
      Number.isFinite(toTime) &&
      fromTime > toTime
    ) {
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
    // Validate configuration first
    const { modelName, provider } = validateModelConfiguration();
    const configuredDimension = getVectorDimension();

    // Test embedding generation with a simple query
    const testOptions: VectorSearchServiceOptions = {
      logger,
      teamId: "health-check",
    };

    const embedding = await generateQueryEmbedding("test query", testOptions);

    logger.info("Vector search health check passed", {
      module: "vector_search/metrics",
      method: "vectorSearchHealthCheck",
      duration: Date.now() - start,
      modelName,
      provider,
      configuredDimension,
      actualDimension: embedding.length,
      dimensionMatch: embedding.length === configuredDimension,
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
