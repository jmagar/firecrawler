import { Response } from "express";
import {
  RequestWithAuth,
  VectorSearchRequest,
  VectorSearchResponse,
  vectorSearchRequestSchema,
  ErrorResponse,
} from "./types";
import { billTeam } from "../../services/billing/credit_billing";
import { v4 as uuidv4 } from "uuid";
import { logJob } from "../../services/logging/log_job";
import {
  vectorSearch,
  validateVectorSearchRequest,
} from "../../search/v2/vector-search";
import ConfigService from "../../services/config-service";
import * as Sentry from "@sentry/node";
import { logger as _logger } from "../../lib/logger";
import type { Logger } from "winston";
import { CostTracking } from "../../lib/cost-tracking";
import { z } from "zod";
import { TransportableError, ErrorCodes } from "../../lib/error";

export async function vectorSearchController(
  req: RequestWithAuth<{}, VectorSearchResponse, VectorSearchRequest>,
  res: Response<VectorSearchResponse>,
) {
  const jobId = uuidv4();
  let logger = _logger.child({
    jobId,
    teamId: req.auth.team_id,
    module: "api/v2",
    method: "vectorSearchController",
    zeroDataRetention: req.acuc?.flags?.forceZDR,
  });

  if (req.acuc?.flags?.forceZDR) {
    return res.status(400).json({
      success: false,
      error:
        "Your team has zero data retention enabled. This is not supported on vector search. Please contact support@firecrawl.com to unblock this feature.",
    });
  }

  const startTime = new Date().getTime();
  let credits_billed = 0;

  try {
    // Validate request using Zod schema
    let thresholdProvided = Object.prototype.hasOwnProperty.call(
      req.body ?? {},
      "threshold",
    );

    req.body = vectorSearchRequestSchema.parse(req.body);

    if (!thresholdProvided) {
      try {
        const configService = await ConfigService;
        const yamlConfig = await configService.getConfiguration();
        const yamlThreshold = yamlConfig?.embeddings?.minSimilarityThreshold;
        if (typeof yamlThreshold === "number") {
          req.body.threshold = yamlThreshold;
          thresholdProvided = true;
        }
      } catch (error) {
        logger.debug("Failed to load YAML threshold override", {
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    logger = logger.child({
      query: req.body.query,
      limit: req.body.limit,
      offset: req.body.offset,
      threshold: req.body.threshold,
      origin: req.body.origin,
    });

    // Additional validation using our custom validator
    const validationErrors = validateVectorSearchRequest(req.body);
    if (validationErrors.length > 0) {
      logger.warn("Vector search request validation failed", {
        errors: validationErrors,
      });
      return res.status(400).json({
        success: false,
        error: "Invalid request parameters",
        details: validationErrors,
      });
    }

    logger.info("Starting vector search", {
      query: req.body.query,
      limit: req.body.limit,
      offset: req.body.offset,
      threshold: req.body.threshold,
      filters: req.body.filters,
      includeContent: req.body.includeContent,
    });

    // Initialize cost tracking
    const costTracking = new CostTracking();

    // Call vector search service
    const searchResponse = await vectorSearch(req.body, {
      logger,
      costTracking,
      teamId: req.auth.team_id,
      thresholdProvided,
    });

    // Handle service-level errors
    if (!searchResponse.success) {
      const errorResponse = searchResponse as ErrorResponse;
      logger.error("Vector search service returned error", {
        error: errorResponse.error,
      });

      return res.status(500).json({
        success: false,
        error: errorResponse.error || "Vector search failed",
        code: errorResponse.code,
      });
    }

    // Calculate credits billed based on search complexity and results
    // Base cost: 1 credit for the search operation
    // Additional: 1 credit per result returned (similar to search endpoint pattern)
    credits_billed = 1 + searchResponse.data.results.length;

    // Bill team for the vector search operation
    await billTeam(
      req.auth.team_id,
      req.acuc?.sub_id ?? undefined,
      credits_billed,
      req.acuc?.api_key_id ?? null,
    ).catch(error => {
      logger.error(
        `Failed to bill team ${req.acuc?.sub_id} for ${credits_billed} credits: ${error}`,
      );
    });

    const endTime = new Date().getTime();
    const timeTakenInSeconds = (endTime - startTime) / 1000;

    logger.info("Vector search completed successfully", {
      query: req.body.query,
      totalResults: searchResponse.data.totalResults,
      returnedResults: searchResponse.data.results.length,
      limit: req.body.limit,
      offset: req.body.offset,
      threshold: req.body.threshold,
      timing: searchResponse.data.timing,
      credits_billed,
      time_taken: timeTakenInSeconds,
    });

    // Log job for analytics and monitoring
    logJob(
      {
        job_id: jobId,
        success: true,
        num_docs: searchResponse.data.results.length,
        docs: [searchResponse.data], // Store search results for analytics
        time_taken: timeTakenInSeconds,
        team_id: req.auth.team_id,
        mode: "vector_search",
        url: req.body.query, // Use query as URL for logging consistency
        scrapeOptions: {}, // Empty for vector search
        crawlerOptions: {
          query: req.body.query,
          limit: req.body.limit,
          offset: req.body.offset,
          threshold: req.body.threshold,
          filters: req.body.filters,
          includeContent: req.body.includeContent,
        },
        origin: req.body.origin,
        integration: req.body.integration,
        credits_billed,
        zeroDataRetention: false, // not supported
      },
      false,
      false, // isSearchPreview
    );

    // Return successful response
    return res.status(200).json({
      success: true,
      data: searchResponse.data,
      creditsUsed: credits_billed,
    });
  } catch (error) {
    // Handle Zod validation errors
    if (error instanceof z.ZodError) {
      logger.warn("Invalid request body", { error: error.errors });
      return res.status(400).json({
        success: false,
        error: "Invalid request body",
        details: error.errors,
      });
    }

    // Handle custom application errors
    if (error instanceof TransportableError) {
      logger.warn("Vector search transportable error", {
        code: error.code,
        message: error.message,
      });
      return res.status(500).json({
        success: false,
        code: error.code,
        error: error.message,
      });
    }

    // Handle unexpected errors
    Sentry.captureException(error);
    logger.error("Unhandled error occurred in vector search", {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });

    return res.status(500).json({
      success: false,
      error: "Internal server error",
    });
  }
}
