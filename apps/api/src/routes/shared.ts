import { NextFunction, Request, Response } from "express";
// import { crawlStatusController } from "../../src/controllers/v1/crawl-status";
import {
  isAgentExtractModelValid,
  RequestWithAuth,
  RequestWithMaybeAuth,
  RequestWithMaybeACUC,
} from "../controllers/v1/types";
import { RateLimiterMode } from "../types";
import { authenticateUser } from "../controllers/auth";
import { createIdempotencyKey } from "../services/idempotency/create";
import { validateIdempotencyKey } from "../services/idempotency/validate";
import { checkTeamCredits } from "../services/billing/credit_billing";
import { isUrlBlocked } from "../scraper/WebScraper/utils/blocklist";
import { logger } from "../lib/logger";
import { BLOCKLISTED_URL_MESSAGE } from "../lib/strings";
import { addDomainFrequencyJob } from "../services";
import * as geoip from "geoip-country";
import { isSelfHosted } from "../lib/deployment";
import ConfigService from "../services/config-service";

export function checkCreditsMiddleware(
  _minimum?: number,
): (req: RequestWithAuth, res: Response, next: NextFunction) => void {
  return (req, res, next) => {
    let minimum = _minimum;
    (async () => {
      if (!minimum && req.body) {
        minimum = Number(
          (req.body as any)?.limit ?? (req.body as any)?.urls?.length ?? 1,
        );
        if (isNaN(minimum) || !isFinite(minimum) || minimum <= 0) {
          minimum = undefined;
        }
      }
      const { success, remainingCredits, chunk } = await checkTeamCredits(
        req.acuc ?? null,
        req.auth.team_id,
        minimum ?? 1,
      );
      if (chunk) {
        req.acuc = chunk;
      }
      req.account = { remainingCredits };
      if (!success) {
        if (
          !minimum &&
          req.body &&
          (req.body as any).limit !== undefined &&
          remainingCredits > 0
        ) {
          logger.warn("Adjusting limit to remaining credits", {
            teamId: req.auth.team_id,
            remainingCredits,
            request: req.body,
          });
          (req.body as any).limit = remainingCredits;
          return next();
        }

        const currencyName = req.acuc?.is_extract ? "tokens" : "credits";
        logger.error(
          `Insufficient ${currencyName}: ${JSON.stringify({ team_id: req.auth.team_id, minimum, remainingCredits })}`,
          {
            teamId: req.auth.team_id,
            minimum,
            remainingCredits,
            request: req.body,
            path: req.path,
          },
        );
        if (
          !res.headersSent &&
          req.auth.team_id !== "8c528896-7882-4587-a4b6-768b721b0b53"
        ) {
          return res.status(402).json({
            success: false,
            error:
              "Insufficient " +
              currencyName +
              " to perform this request. For more " +
              currencyName +
              ", you can upgrade your plan at " +
              (currencyName === "credits"
                ? "https://firecrawl.dev/pricing or try changing the request limit to a lower value"
                : "https://www.firecrawl.dev/extract#pricing") +
              ".",
          });
        }
      }
      next();
    })().catch(err => next(err));
  };
}

export function authMiddleware(
  rateLimiterMode: RateLimiterMode,
): (req: RequestWithMaybeAuth, res: Response, next: NextFunction) => void {
  return (req, res, next) => {
    (async () => {
      let currentRateLimiterMode = rateLimiterMode;
      if (
        currentRateLimiterMode === RateLimiterMode.Extract &&
        isAgentExtractModelValid((req.body as any)?.agent?.model)
      ) {
        currentRateLimiterMode = RateLimiterMode.ExtractAgentPreview;
      }

      // Track domain frequency regardless of caching
      try {
        // Use the URL from the request body if available
        const urlToTrack = (req.body as any)?.url;
        if (urlToTrack) {
          await addDomainFrequencyJob(urlToTrack);
        }
      } catch (error) {
        // Log error without meta.logger since it's not available in this context
        logger.warn("Failed to track domain frequency", { error });
      }

      // if (currentRateLimiterMode === RateLimiterMode.Scrape && isAgentExtractModelValid((req.body as any)?.agent?.model)) {
      //   currentRateLimiterMode = RateLimiterMode.ScrapeAgentPreview;
      // }

      const auth = await authenticateUser(req, res, currentRateLimiterMode);

      if (!auth.success) {
        if (!res.headersSent) {
          return res
            .status(auth.status)
            .json({ success: false, error: auth.error });
        } else {
          return;
        }
      }

      const { team_id, chunk } = auth;

      req.auth = { team_id };
      req.acuc = chunk ?? undefined;
      if (chunk) {
        req.account = {
          remainingCredits: chunk.price_should_be_graceful
            ? chunk.remaining_credits + chunk.price_credits
            : chunk.remaining_credits,
        };
      }
      next();
    })().catch(err => next(err));
  };
}

export function idempotencyMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
) {
  (async () => {
    if (req.headers["x-idempotency-key"]) {
      const isIdempotencyValid = await validateIdempotencyKey(req);
      if (!isIdempotencyValid) {
        if (!res.headersSent) {
          return res
            .status(409)
            .json({ success: false, error: "Idempotency key already used" });
        }
      }
      createIdempotencyKey(req);
    }
    next();
  })().catch(err => next(err));
}
export function blocklistMiddleware(
  req: RequestWithMaybeACUC<any, any, any>,
  res: Response,
  next: NextFunction,
) {
  if (
    typeof req.body.url === "string" &&
    isUrlBlocked(req.body.url, req.acuc?.flags ?? null)
  ) {
    if (!res.headersSent) {
      return res.status(403).json({
        success: false,
        error: BLOCKLISTED_URL_MESSAGE,
      });
    }
  }
  next();
}

export function countryCheck(
  req: RequestWithAuth<any, any, any>,
  res: Response,
  next: NextFunction,
) {
  const couldBeRestricted =
    req.body &&
    (req.body.actions ||
      (req.body.headers &&
        typeof req.body.headers === "object" &&
        Object.keys(req.body.headers).length > 0) ||
      req.body.agent ||
      req.body.jsonOptions?.agent ||
      req.body.extract?.agent ||
      req.body.scrapeOptions?.actions ||
      (req.body.scrapeOptions?.headers &&
        typeof req.body.scrapeOptions.headers === "object" &&
        Object.keys(req.body.scrapeOptions.headers).length > 0) ||
      req.body.scrapeOptions?.agent ||
      req.body.scrapeOptions?.jsonOptions?.agent ||
      req.body.scrapeOptions?.extract?.agent);

  if (!couldBeRestricted) {
    return next();
  }

  if (!req.ip) {
    logger.warn("IP address not found, unable to check country");
    return next();
  }

  const country = geoip.lookup(req.ip);
  if (!country || !country.country) {
    logger.warn("IP address country data not found", { ip: req.ip });
    return next();
  }

  const restricted = process.env.RESTRICTED_COUNTRIES?.split(",") ?? [];
  if (restricted.includes(country.country)) {
    logger.warn("Denied access to restricted country", {
      ip: req.ip,
      country: country.country,
      teamId: req.auth.team_id,
    });
    return res.status(403).json({
      success: false,
      error: isSelfHosted()
        ? "Use of headers, actions, and the FIRE-1 agent is not allowed by default in your country. Please check your server configuration."
        : "Use of headers, actions, and the FIRE-1 agent is not allowed by default in your country. Please contact us at help@firecrawl.com",
    });
  }

  next();
}

export function wrap(
  controller: (req: Request, res: Response) => Promise<any>,
): (req: Request, res: Response, next: NextFunction) => any {
  return (req, res, next) => {
    controller(req, res).catch(err => next(err));
  };
}

interface YamlConfigMetadata {
  routeType: string;
  configApplied: boolean;
  configSource?: string;
  error?: string;
}

declare global {
  namespace Express {
    interface Request {
      yamlConfigMetadata?: YamlConfigMetadata;
    }
  }
}

/**
 * Deep merge objects with YAML configuration taking highest priority
 */
function deepMergeWithPriority(
  requestBody: Record<string, any>,
  yamlDefaults: Record<string, any>,
): Record<string, any> {
  const result = { ...requestBody };

  for (const [key, value] of Object.entries(yamlDefaults)) {
    if (value !== null && value !== undefined) {
      if (
        typeof value === "object" &&
        !Array.isArray(value) &&
        value !== null
      ) {
        if (
          typeof result[key] === "object" &&
          !Array.isArray(result[key]) &&
          result[key] !== null
        ) {
          result[key] = deepMergeWithPriority(result[key], value);
        } else {
          result[key] = { ...value };
        }
      } else {
        result[key] = value;
      }
    }
  }

  return result;
}

/**
 * Extract route type from request path for configuration loading
 */
function extractRouteType(path: string): string | null {
  // Normalize path by removing version prefix and extracting endpoint
  const pathSegments = path.split("/").filter(segment => segment.length > 0);

  // Skip version prefix (v1, v2, etc.)
  const endpointIndex = pathSegments.findIndex(
    segment => !segment.match(/^v\d+$/),
  );
  if (endpointIndex === -1) return null;

  const endpoint = pathSegments[endpointIndex];

  // Map endpoints to route types
  switch (endpoint) {
    case "scrape":
      return "scrape";
    case "crawl":
      return "crawl";
    case "search":
      return "search";
    case "vector-search":
      return "vector-search";
    case "extract":
      return "extract";
    case "batch-scrape":
      return "scrape"; // batch-scrape uses same config as scrape
    default:
      return null;
  }
}

/**
 * Extract route-specific configuration from YAML config object
 */
function extractRouteConfig(
  config: Record<string, any>,
  routeType: string,
): Record<string, any> {
  const routeDefaults: Record<string, any> = {};

  // Extract route-specific configuration based on route type
  switch (routeType) {
    case "scrape":
      if (config.scraping) {
        Object.assign(routeDefaults, config.scraping);
      }
      // Apply language location settings to scrape config
      if (config.language?.location) {
        routeDefaults.location = config.language.location;
      }
      break;

    case "crawl":
      if (config.crawling) {
        Object.assign(routeDefaults, config.crawling);
      }
      break;

    case "search":
      if (config.search) {
        Object.assign(routeDefaults, config.search);
      }
      // Apply language settings to search config
      if (config.language) {
        if (config.language.location?.country) {
          routeDefaults.country = config.language.location.country;
        }
        if (config.language.location?.languages?.[0]) {
          routeDefaults.lang = config.language.location.languages[0];
        }
      }
      if (config.embeddings?.minSimilarityThreshold !== undefined) {
        routeDefaults.threshold = config.embeddings.minSimilarityThreshold;
      }
      break;
    case "vector-search":
      if (config.embeddings?.minSimilarityThreshold !== undefined) {
        routeDefaults.threshold = config.embeddings.minSimilarityThreshold;
      }
      if (config.search?.limit !== undefined) {
        routeDefaults.limit = config.search.limit;
      }
      break;

    case "extract":
      // Extract configuration could be added here in the future
      if (config.extraction) {
        Object.assign(routeDefaults, config.extraction);
      }
      break;

    default:
      // No specific configuration for this route type
      break;
  }

  return routeDefaults;
}

/**
 * Apply YAML configuration defaults to request body
 */
export function yamlConfigDefaultsMiddleware(
  req: RequestWithAuth<any, any, any>,
  res: Response,
  next: NextFunction,
) {
  (async () => {
    const routeIdentifier = req.originalUrl || req.baseUrl || req.path;
    const routeType = extractRouteType(routeIdentifier);

    // Initialize metadata for debugging
    req.yamlConfigMetadata = {
      routeType: routeType || "unknown",
      configApplied: false,
    };

    // Skip if we can't determine route type
    if (!routeType || routeType === "vector-search") {
      logger.info(`YAML defaults skipped for route (${routeIdentifier})`, {
        module: "yaml-config-defaults-middleware",
        method: "yamlConfigDefaultsMiddleware",
        path: req.path,
        baseUrl: req.baseUrl,
        originalUrl: req.originalUrl,
      });
      return next();
    }

    try {
      const configService = await ConfigService;
      const rawConfig = await configService.getConfiguration();

      // Skip if no configuration available
      if (!rawConfig || Object.keys(rawConfig).length === 0) {
        return next();
      }

      // Basic validation - ensure config is an object
      if (typeof rawConfig !== "object" || rawConfig === null) {
        logger.warn(
          "Invalid YAML configuration format, skipping defaults application",
          {
            module: "yaml-config-defaults-middleware",
            method: "yamlConfigDefaultsMiddleware",
            routeType,
            teamId: req.auth.team_id,
            configType: typeof rawConfig,
          },
        );
        req.yamlConfigMetadata.error = "Configuration is not a valid object";
        return next();
      }

      // Extract route-specific defaults
      const routeDefaults = extractRouteConfig(rawConfig, routeType);

      logger.info(
        `Evaluated YAML defaults for route ${routeType} (${routeIdentifier})`,
        {
          module: "yaml-config-defaults-middleware",
          method: "yamlConfigDefaultsMiddleware",
          routeType,
          routeIdentifier,
          appliedKeys: Object.keys(routeDefaults),
        },
      );

      // Apply defaults if any exist
      if (Object.keys(routeDefaults).length > 0) {
        // Ensure request body exists
        if (!req.body) {
          req.body = {};
        }

        // Deep merge with YAML configuration taking priority
        req.body = deepMergeWithPriority(req.body, routeDefaults);

        req.yamlConfigMetadata.configApplied = true;
        req.yamlConfigMetadata.configSource = "yaml";

        logger.info(`Applied YAML configuration defaults for ${routeType}`, {
          module: "yaml-config-defaults-middleware",
          method: "yamlConfigDefaultsMiddleware",
          routeType,
          teamId: req.auth.team_id,
          appliedDefaults: Object.keys(routeDefaults),
          defaultsCount: Object.keys(routeDefaults).length,
          mergedKeys: Object.keys(req.body),
        });
      }

      next();
    } catch (error) {
      // Log error but don't break request processing
      logger.warn(
        "Failed to load YAML configuration, continuing without defaults",
        {
          module: "yaml-config-defaults-middleware",
          method: "yamlConfigDefaultsMiddleware",
          routeType,
          teamId: req.auth.team_id,
          error: error instanceof Error ? error.message : String(error),
        },
      );

      req.yamlConfigMetadata.error =
        error instanceof Error ? error.message : String(error);
      next();
    }
  })().catch(err => next(err));
}
