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
} from "../../lib/embedding-utils";
import {
  searchSimilarVectors,
  VectorSearchOptions,
  VectorSearchResult as ServiceVectorSearchResult,
} from "../../services/vector-storage";
import {
  VectorSearchRequest,
  VectorSearchResponse,
  VectorSearchResult as APIVectorSearchResult,
} from "../../controllers/v2/types";
import { parseEnvFloat, parseEnvInt } from "../../lib/utils/env-utils";
import {
  VectorSearchServiceOptions,
  VectorSearchTiming,
  ThresholdSelectionResult,
  QueryEmbeddingResult,
  SearchExecutionResult,
} from "./types/vector-search.types";

// Configuration Constants
const VECTOR_SEARCH_CONFIG = {
  // Threshold floors from environment or defaults
  THRESHOLD_FLOORS: {
    LEVEL_1: parseEnvFloat("VECTOR_THRESHOLD_FLOOR_1", 0.55),
    LEVEL_2: parseEnvFloat("VECTOR_THRESHOLD_FLOOR_2", 0.4),
    LEVEL_3: parseEnvFloat("VECTOR_THRESHOLD_FLOOR_3", 0.3),
  },

  // Memory management
  MAX_THRESHOLD_HISTORY: parseEnvInt("MAX_THRESHOLD_HISTORY", 10),

  // Performance
  DEFAULT_SEARCH_LIMIT: 10,
  MAX_SEARCH_LIMIT: 100,

  // Timeouts
  SEARCH_TIMEOUT_MS: 30000,
  EMBEDDING_TIMEOUT_MS: 5000,

  // Precision
  THRESHOLD_EPSILON: Number.EPSILON * 10,
} as const;

// Helper to access threshold floors
function getThresholdFloor(level: 1 | 2 | 3): number {
  const key =
    `LEVEL_${level}` as keyof typeof VECTOR_SEARCH_CONFIG.THRESHOLD_FLOORS;
  return VECTOR_SEARCH_CONFIG.THRESHOLD_FLOORS[key];
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

  const floor1 = clampThreshold(getThresholdFloor(1));
  const floor2 = clampThreshold(getThresholdFloor(2));
  const floor3 = clampThreshold(getThresholdFloor(3));

  // Never escalate above base when base is already <= the floor
  const fallback = (delta: number, floor: number) => {
    const lowered = clampThreshold(base - delta);
    return base > floor ? Math.max(lowered, floor) : lowered;
  };

  const candidates = [
    base,
    fallback(0.1, floor1),
    fallback(0.25, floor2),
    // Ensure final floor never exceeds base; dedup below will remove if equal
    Math.min(base, floor3),
  ];
  const unique: number[] = [];

  for (const candidate of candidates) {
    const clamped = clampThreshold(candidate);
    if (
      unique.some(
        existing =>
          Math.abs(existing - clamped) < VECTOR_SEARCH_CONFIG.THRESHOLD_EPSILON,
      )
    ) {
      continue;
    }
    unique.push(clamped);
  }

  // Cap the number of fallback candidates
  const maxFallbacks = (() => {
    const envValue = process.env.VECTOR_SEARCH_MAX_FALLBACKS;
    if (!envValue) return 10; // Default
    const parsed = parseInt(envValue, 10);
    return parsed >= 1 ? parsed : 10; // Minimum 1, default on invalid
  })();

  return unique.slice(0, maxFallbacks);
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
 * Calculates quality-weighted ranking score for vector search results
 * Combines similarity score with content quality metrics for better relevance
 */
function calculateQualityWeightedScore(
  result: ServiceVectorSearchResult,
  qualityWeight: number = 0.15, // Phase 1: Conservative quality weighting
): number {
  const similarityScore = result.similarity;

  // Extract quality metrics from metadata (added by Phase 1 enhancements)
  const qualityScore = result.metadata.quality_score ?? 0.5; // Default to neutral if missing
  const contentDensity = result.metadata.content_density ?? 0.5;
  const navigationRatio = result.metadata.navigation_ratio ?? 0.3;
  const structuralQuality = result.metadata.structural_quality ?? 0.5;

  // Composite quality score with weighted factors
  const compositeQuality =
    qualityScore * 0.4 + // Overall quality (40%)
    contentDensity * 0.3 + // Content density (30%)
    structuralQuality * 0.2 + // Structural quality (20%)
    (1 - navigationRatio) * 0.1; // Low navigation ratio is good (10%)

  // Clamp composite quality to [0, 1]
  const clampedQuality = Math.min(1, Math.max(0, compositeQuality));

  // Calculate final weighted score
  // Higher similarity weight (0.85) with moderate quality influence (0.15)
  const weightedScore =
    similarityScore * (1 - qualityWeight) + clampedQuality * qualityWeight;

  return Math.min(1, Math.max(0, weightedScore));
}

/**
 * Applies quality-weighted ranking to vector search results
 * Sorts results by composite score of similarity + quality metrics
 */
function applyQualityWeightedRanking(
  results: ServiceVectorSearchResult[],
  qualityThreshold?: number,
): ServiceVectorSearchResult[] {
  // Calculate quality-weighted scores for all results
  const scoredResults = results.map(result => ({
    ...result,
    qualityWeightedScore: calculateQualityWeightedScore(result),
  }));

  // Filter by quality threshold if specified
  let filteredResults = scoredResults;
  if (qualityThreshold !== undefined && qualityThreshold > 0) {
    filteredResults = scoredResults.filter(
      result => (result.metadata.quality_score ?? 0.5) >= qualityThreshold,
    );
  }

  // Sort by quality-weighted score (descending)
  const rankedResults = filteredResults.sort(
    (a, b) => b.qualityWeightedScore - a.qualityWeightedScore,
  );

  // Remove the temporary scoring field and return
  return rankedResults.map(({ qualityWeightedScore, ...result }) => result);
}

/**
 * Transforms vector search results to API response format
 */
function transformResults(
  results: ServiceVectorSearchResult[],
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
 * Calculates optimal similarity threshold for vector search.
 *
 * Algorithm:
 * 1. Generate multiple threshold candidates based on query complexity
 * 2. Sort candidates in descending order (higher = more similar)
 * 3. Apply floor constraints to prevent too-loose matching
 * 4. Select threshold that balances precision and recall
 *
 * The multi-level floor system ensures quality results:
 * - Floor 1 (0.55): Primary threshold for high-quality matches
 * - Floor 2 (0.4): Fallback for broader search
 * - Floor 3 (0.3): Minimum acceptable similarity
 */
function selectOptimalThreshold(
  thresholdCandidates: number[],
  logger: any,
): number {
  // Sort candidates from highest to lowest (most to least similar)
  const sortedCandidates = [...thresholdCandidates].sort((a, b) => b - a);

  // Default to highest threshold (most restrictive)
  let selectedThreshold = sortedCandidates[0];

  // Apply multi-tier fallback logic if we have enough candidates
  if (sortedCandidates.length > 2) {
    // Tier 1: Try second-highest if it meets floor 1 requirement (high quality)
    if (sortedCandidates[1] >= getThresholdFloor(1)) {
      selectedThreshold = sortedCandidates[1];
    }
    // Tier 2: Try third candidate if it meets floor 2 requirement (medium quality)
    else if (sortedCandidates[2] >= getThresholdFloor(2)) {
      selectedThreshold = sortedCandidates[2];
    }
    // Tier 3: Try fourth candidate if it meets floor 3 requirement (minimum quality)
    else if (sortedCandidates[3] >= getThresholdFloor(3)) {
      selectedThreshold = sortedCandidates[3];
    }
    // If none meet floor requirements, keep the highest (most restrictive)
  }

  logger.debug("Threshold selection", {
    module: "vector_search",
    method: "selectOptimalThreshold",
    candidates: sortedCandidates,
    selected: selectedThreshold,
  });

  return selectedThreshold;
}

/**
 * Execute vector search with threshold fallback logic
 */
async function executeVectorSearchWithFallback(
  queryEmbedding: number[],
  thresholdCandidates: number[],
  searchOptions: VectorSearchOptions,
  logger: any,
): Promise<{
  results: ServiceVectorSearchResult[];
  threshold: number;
  timing: number;
}> {
  const attemptStart = Date.now();

  // Single-pass at the lowest candidate
  const minCandidate = Math.min(...thresholdCandidates);
  searchOptions.minSimilarity = minCandidate;

  const allResults = await searchSimilarVectors(
    queryEmbedding,
    searchOptions,
    logger,
  );

  const timing = Date.now() - attemptStart;

  // Pick the highest threshold that still yields results
  const sortedDesc = [...thresholdCandidates].sort((a, b) => b - a);
  let usedThreshold = minCandidate;
  let vectorResults: ServiceVectorSearchResult[] = [];

  for (const t of sortedDesc) {
    const filtered = allResults.filter(r => r.similarity >= t);
    if (filtered.length > 0) {
      usedThreshold = t;
      vectorResults = filtered;
      break;
    }
  }

  return { results: vectorResults, threshold: usedThreshold, timing };
}

/**
 * Apply pagination to search results
 */
function applyPagination(
  results: ServiceVectorSearchResult[],
  limit: number,
  offset: number,
): ServiceVectorSearchResult[] {
  const offsetResults = offset > 0 ? results.slice(offset) : results;
  return offsetResults.slice(0, limit);
}

/**
 * Log search metrics and performance data
 */
function logSearchMetrics(
  logger: any,
  request: VectorSearchRequest,
  vectorResults: ServiceVectorSearchResult[],
  apiResults: APIVectorSearchResult[],
  usedThreshold: number,
  thresholdHistory: number[],
  fallbackUsed: boolean,
  timing: VectorSearchTiming,
): void {
  logger.info("Vector search completed successfully", {
    module: "vector_search/metrics",
    method: "vectorSearch",
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
}

/**
 * Main vector search service that orchestrates the entire search process
 */
/**
 * Performs vector similarity search with automatic threshold optimization.
 *
 * This method uses embeddings to find semantically similar content, automatically
 * selecting optimal similarity thresholds based on the query and available results.
 *
 * @param request - Search configuration including query, limits, and filters
 * @param options - Service options including logger and threshold configuration
 * @returns Search results with metadata including threshold and timing
 *
 * @example
 * const results = await vectorSearch({
 *   query: "machine learning tutorials",
 *   limit: 10,
 *   includeContent: true
 * }, { logger });
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

    // Step 2: Transform filters and prepare search options
    const searchOptions = transformFilters(request);

    // Implement offset by increasing limit and slicing results
    if (request.offset > 0) {
      searchOptions.limit =
        (searchOptions.limit || VECTOR_SEARCH_CONFIG.DEFAULT_SEARCH_LIMIT) +
        request.offset;
    }

    // Step 3: Build threshold candidates and execute search
    const thresholdCandidates = buildThresholdCandidates(
      request.threshold,
      thresholdProvided,
    );

    const thresholdHistory = [...thresholdCandidates];

    logger.debug("Vector search threshold candidates", {
      module: "vector_search",
      method: "vectorSearch",
      thresholdCandidates,
      thresholdProvided,
    });

    // Execute vector search with fallback logic
    const searchResult = await executeVectorSearchWithFallback(
      queryEmbedding,
      thresholdCandidates,
      searchOptions,
      logger,
    );

    vectorSearchTime = searchResult.timing;
    let { results: vectorResults, threshold: usedThreshold } = searchResult;

    // Step 3.5: Phase 1 - Apply quality-weighted ranking
    // Extract quality threshold from filters if available (future enhancement)
    const qualityThreshold = undefined; // Will be configurable in Phase 2

    if (vectorResults.length > 0) {
      logger.debug("Applying quality-weighted ranking", {
        module: "vector_search/quality",
        method: "vectorSearch",
        originalResultsCount: vectorResults.length,
        qualityThreshold,
      });

      vectorResults = applyQualityWeightedRanking(
        vectorResults,
        qualityThreshold,
      );

      logger.debug("Quality-weighted ranking applied", {
        module: "vector_search/quality",
        method: "vectorSearch",
        rankedResultsCount: vectorResults.length,
      });
    }

    // Step 4: Apply pagination
    const paginatedResults = applyPagination(
      vectorResults,
      request.limit || VECTOR_SEARCH_CONFIG.DEFAULT_SEARCH_LIMIT,
      request.offset || 0,
    );

    // Step 5: Transform results to API format
    const apiResults = transformResults(
      paginatedResults,
      request,
      request.offset || 0,
    );

    // Step 6: Calculate timing and prepare response
    const totalTime = Date.now() - startTime;
    const timing: VectorSearchTiming = {
      queryEmbeddingMs: queryEmbeddingTime,
      vectorSearchMs: vectorSearchTime,
      totalMs: totalTime,
    };

    const THRESHOLD_COMPARISON_EPSILON = 1e-6;
    const fallbackUsed =
      thresholdHistory.length > 1 &&
      !thresholdProvided &&
      usedThreshold < thresholdHistory[0] - THRESHOLD_COMPARISON_EPSILON;

    // Step 7: Log metrics
    logSearchMetrics(
      logger,
      request,
      vectorResults,
      apiResults,
      usedThreshold,
      thresholdHistory,
      fallbackUsed,
      timing,
    );

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
