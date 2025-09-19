import { Response } from "express";
import { v4 as uuidv4 } from "uuid";
import {
  CrawlRequest,
  crawlRequestSchema,
  CrawlResponse,
  RequestWithAuth,
  toV0CrawlerOptions,
} from "./types";
import { crawlToCrawler, saveCrawl, StoredCrawl } from "../../lib/crawl-redis";
import { _addScrapeJobToBullMQ } from "../../services/queue-jobs";
import { logger as _logger } from "../../lib/logger";
import { generateCrawlerOptionsFromPrompt } from "../../scraper/scrapeURL/transformers/llmExtract";
import { CostTracking } from "../../lib/cost-tracking";
import { checkPermissions } from "../../lib/permissions";
import { getLanguageExcludePatterns } from "../../lib/language-filter.js";
// Memoize language patterns to avoid recomputing on every request
const __languageExcludeCache = new Map<string, string[]>();

export async function crawlController(
  req: RequestWithAuth<{}, CrawlResponse, CrawlRequest>,
  res: Response<CrawlResponse>,
) {
  const preNormalizedBody = req.body;
  req.body = crawlRequestSchema.parse(req.body);

  const permissions = checkPermissions(req.body, req.acuc?.flags);
  if (permissions.error) {
    return res.status(403).json({
      success: false,
      error: permissions.error,
    });
  }

  const zeroDataRetention =
    req.acuc?.flags?.forceZDR || req.body.zeroDataRetention;

  const id = uuidv4();
  const logger = _logger.child({
    crawlId: id,
    module: "api/v2",
    method: "crawlController",
    teamId: req.auth.team_id,
    zeroDataRetention,
  });

  logger.debug("Crawl " + id + " starting", {
    request: req.body,
    originalRequest: preNormalizedBody,
    account: req.account,
  });

  let { remainingCredits } = req.account!;
  const useDbAuthentication = process.env.USE_DB_AUTHENTICATION === "true";
  if (!useDbAuthentication) {
    remainingCredits = Infinity;
  }

  const crawlerOptions = {
    ...req.body,
    url: undefined,
    scrapeOptions: undefined,
    prompt: undefined,
  };
  const scrapeOptions = req.body.scrapeOptions;

  let promptGeneratedOptions = {};
  if (req.body.prompt) {
    try {
      const costTracking = new CostTracking();
      const { extract } = await generateCrawlerOptionsFromPrompt(
        req.body.prompt,
        logger,
        costTracking,
        { teamId: req.auth.team_id, crawlId: id },
      );
      promptGeneratedOptions = extract || {};
      logger.debug("Generated crawler options from prompt", {
        prompt: req.body.prompt,
        generatedOptions: promptGeneratedOptions,
      });
      logger.debug(JSON.stringify(promptGeneratedOptions, null, 2));
    } catch (error) {
      logger.error("Failed to generate crawler options from prompt", {
        error: error.message,
        prompt: req.body.prompt,
      });
      return res.status(400).json({
        success: false,
        error:
          "Failed to process natural language prompt. Please try rephrasing or use explicit crawler options.",
      });
    }
  }

  // Merge behavior:
  // - Start with parsed crawlerOptions (which contains schema defaults)
  // - Overlay promptGeneratedOptions ONLY for fields the user did not explicitly provide
  //   in the original request (preNormalizedBody) or provided as null/undefined.
  // This prevents empty defaults like [] from overwriting meaningful prompt-generated values.
  const finalCrawlerOptions: any = { ...crawlerOptions };
  for (const [key, value] of Object.entries(promptGeneratedOptions)) {
    const userProvided = Object.prototype.hasOwnProperty.call(
      preNormalizedBody,
      key,
    );
    if (
      !userProvided ||
      preNormalizedBody[key] === undefined ||
      preNormalizedBody[key] === null
    ) {
      finalCrawlerOptions[key] = value;
    }
  }

  // Apply automatic language filtering if DEFAULT_CRAWL_LANGUAGE is set
  const defaultLanguageRaw = process.env.DEFAULT_CRAWL_LANGUAGE;
  const defaultLanguage = defaultLanguageRaw?.trim().toLowerCase() || undefined;
  let __langPatternSet: Set<string> | null = null;
  if (defaultLanguage && defaultLanguage !== "all") {
    try {
      const languageExcludePatterns =
        __languageExcludeCache.get(defaultLanguage) ||
        getLanguageExcludePatterns(defaultLanguage);
      if (!__languageExcludeCache.has(defaultLanguage)) {
        __languageExcludeCache.set(defaultLanguage, languageExcludePatterns);
      }
      if (languageExcludePatterns.length > 0) {
        // Store generated patterns to avoid recompiling during validation
        __langPatternSet = new Set(languageExcludePatterns);
        const existingExcludePaths = finalCrawlerOptions.excludePaths || [];
        // merge then deduplicate while preserving order
        const merged = [...existingExcludePaths, ...languageExcludePatterns];
        const deduped = Array.from(new Set(merged));
        finalCrawlerOptions.excludePaths = deduped;
        const duplicatesRemoved = merged.length - deduped.length;
        if (
          !finalCrawlerOptions.regexOnFullURL &&
          languageExcludePatterns.some(p => p.startsWith("^(?:https?:)?//"))
        ) {
          finalCrawlerOptions.regexOnFullURL = true;
          logger.debug(
            "Enabled regexOnFullURL due to language patterns containing full URLs",
          );
        }
        logger.info("Applied automatic language filtering", {
          allowedLanguage: defaultLanguage,
          languageFilterSource: "env_default",
          existingExcludePatternsCount: existingExcludePaths.length,
          addedExcludePatternsCount: languageExcludePatterns.length,
          totalExcludePatterns: finalCrawlerOptions.excludePaths.length,
          duplicatesRemoved,
          regexOnFullURL: finalCrawlerOptions.regexOnFullURL === true,
        });
      }
    } catch (error) {
      logger.warn("Failed to apply language filtering", {
        defaultLanguage,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  if (Array.isArray(finalCrawlerOptions.includePaths)) {
    for (const x of finalCrawlerOptions.includePaths) {
      try {
        new RegExp(x);
      } catch (e) {
        return res.status(400).json({ success: false, error: e.message });
      }
    }
  }

  if (Array.isArray(finalCrawlerOptions.excludePaths)) {
    for (const x of finalCrawlerOptions.excludePaths) {
      // Skip validation for auto-generated language patterns since they're already validated internally
      if (__langPatternSet?.has(x)) continue;
      try {
        new RegExp(x);
      } catch (e) {
        return res.status(400).json({ success: false, error: e.message });
      }
    }
  }

  const originalLimit = finalCrawlerOptions.limit;
  finalCrawlerOptions.limit = Math.min(
    remainingCredits,
    finalCrawlerOptions.limit,
  );
  logger.debug("Determined limit: " + finalCrawlerOptions.limit, {
    remainingCredits,
    bodyLimit: originalLimit,
    originalBodyLimit: preNormalizedBody.limit,
  });

  const sc: StoredCrawl = {
    originUrl: req.body.url,
    crawlerOptions: toV0CrawlerOptions(finalCrawlerOptions),
    scrapeOptions,
    internalOptions: {
      disableSmartWaitCache: true,
      teamId: req.auth.team_id,
      saveScrapeResultToGCS: process.env.GCS_FIRE_ENGINE_BUCKET_NAME
        ? true
        : false,
      zeroDataRetention,
    },
    team_id: req.auth.team_id,
    createdAt: Date.now(),
    maxConcurrency:
      req.body.maxConcurrency !== undefined
        ? req.acuc?.concurrency !== undefined
          ? Math.min(req.body.maxConcurrency, req.acuc.concurrency)
          : req.body.maxConcurrency
        : undefined,
    zeroDataRetention,
  };

  const crawler = crawlToCrawler(id, sc, req.acuc?.flags ?? null);

  try {
    sc.robots = await crawler.getRobotsTxt(scrapeOptions.skipTlsVerification);
    const robotsCrawlDelay = crawler.getRobotsCrawlDelay();
    if (robotsCrawlDelay !== null && !sc.crawlerOptions.delay) {
      sc.crawlerOptions.delay = robotsCrawlDelay;
    }
  } catch (e) {
    logger.debug("Failed to get robots.txt (this is probably fine!)", {
      error: e,
    });
  }

  await saveCrawl(id, sc);

  await _addScrapeJobToBullMQ(
    {
      url: req.body.url,
      mode: "kickoff" as const,
      team_id: req.auth.team_id,
      crawlerOptions: finalCrawlerOptions,
      scrapeOptions: sc.scrapeOptions,
      internalOptions: sc.internalOptions,
      origin: req.body.origin,
      integration: req.body.integration,
      crawl_id: id,
      webhook: req.body.webhook,
      v1: true,
      zeroDataRetention: zeroDataRetention || false,
      apiKeyId: req.acuc?.api_key_id ?? null,
    },
    crypto.randomUUID(),
  );

  const protocol = process.env.ENV === "local" ? req.protocol : "https";

  return res.status(200).json({
    success: true,
    id,
    url: `${protocol}://${req.get("host")}/v2/crawl/${id}`,
    ...(req.body.prompt && {
      promptGeneratedOptions: promptGeneratedOptions,
      finalCrawlerOptions: finalCrawlerOptions,
    }),
  });
}
