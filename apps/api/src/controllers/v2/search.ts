import { Response } from "express";
import {
  Document,
  RequestWithAuth,
  SearchRequest,
  SearchResponse,
  searchRequestSchema,
  ScrapeOptions,
  TeamFlags,
} from "./types";
import { billTeam } from "../../services/billing/credit_billing";
import { v4 as uuidv4 } from "uuid";
import { addScrapeJob, waitForJob } from "../../services/queue-jobs";
import { logJob } from "../../services/logging/log_job";
import { getJobPriority } from "../../lib/job-priority";
import { Mode } from "../../types";
import { getScrapeQueue } from "../../services/queue-service";
import { search } from "../../search/v2";
import { isUrlBlocked } from "../../scraper/WebScraper/utils/blocklist";
import * as Sentry from "@sentry/node";
import { BLOCKLISTED_URL_MESSAGE } from "../../lib/strings";
import { logger as _logger } from "../../lib/logger";
import type { Logger } from "winston";
import { CostTracking } from "../../lib/extract/extraction-service";
import { calculateCreditsToBeBilled } from "../../lib/scrape-billing";
import { supabase_service } from "../../services/supabase";
import { SearchResult, SearchV2Response } from "../../lib/entities";
import { ScrapeJobTimeoutError } from "../../lib/error";
import { z } from "zod";
import { buildSearchQuery, getCategoryFromUrl, CategoryOption } from "../../lib/search-query-builder";

interface DocumentWithCostTracking {
  document: Document;
  costTracking: ReturnType<typeof CostTracking.prototype.toJSON>;
}

interface ScrapeJobInput {
  url: string;
  title: string;
  description: string;
}

function prepareScrapeJobInputs(searchResponse: SearchV2Response): {
  web: ScrapeJobInput[];
  news: ScrapeJobInput[];
  images: ScrapeJobInput[];
} {
  const inputs = {
    web: [] as ScrapeJobInput[],
    news: [] as ScrapeJobInput[],
    images: [] as ScrapeJobInput[],
  };

  // Prepare web inputs
  if (searchResponse.web) {
    inputs.web = searchResponse.web.map(item => ({
      url: item.url,
      title: item.title,
      description: item.description,
    }));
  }

  // Prepare news inputs (only those with URLs)
  if (searchResponse.news) {
    inputs.news = searchResponse.news
      .filter(item => item.url)
      .map(item => ({
        url: item.url!,
        title: item.title || "",
        description: item.snippet || "",
      }));
  }

  // Prepare image inputs (only those with URLs)
  if (searchResponse.images) {
    inputs.images = searchResponse.images
      .filter(item => item.url)
      .map(item => ({
        url: item.url!,
        title: item.title || "",
        description: "", // Images don't have descriptions/snippets
      }));
  }

  return inputs;
}

async function startScrapeJob(
  searchResult: { url: string; title: string; description: string },
  options: {
    teamId: string;
    origin: string;
    timeout: number;
    scrapeOptions: ScrapeOptions;
  },
  logger: Logger,
  flags: TeamFlags,
  directToBullMQ: boolean = false,
  isSearchPreview: boolean = false,
): Promise<string> {
  const jobId = uuidv4();
  const jobPriority = await getJobPriority({
    team_id: options.teamId,
    basePriority: 10,
  });

  const zeroDataRetention = flags?.forceZDR ?? false;

  if (isUrlBlocked(searchResult.url, flags)) {
    throw new Error("Could not scrape url: " + BLOCKLISTED_URL_MESSAGE);
  }
  
  logger.info("Adding scrape job", {
    scrapeId: jobId,
    url: searchResult.url,
    teamId: options.teamId,
    origin: options.origin,
    zeroDataRetention,
  });
  
  await addScrapeJob(
    {
      url: searchResult.url,
      mode: "single_urls" as Mode,
      team_id: options.teamId,
      scrapeOptions: {
        ...options.scrapeOptions,
        maxAge: 3 * 24 * 60 * 60 * 1000, // 3 days
      },
      internalOptions: { teamId: options.teamId, bypassBilling: true, zeroDataRetention },
      origin: options.origin,
      is_scrape: true,
      startTime: Date.now(),
      zeroDataRetention,
    },
    {},
    jobId,
    jobPriority,
    directToBullMQ,
  );
  
  return jobId;
}

async function scrapeSearchResult(
  searchResult: { url: string; title: string; description: string },
  options: {
    teamId: string;
    origin: string;
    timeout: number;
    scrapeOptions: ScrapeOptions;
  },
  logger: Logger,
  flags: TeamFlags,
  directToBullMQ: boolean = false,
  isSearchPreview: boolean = false,
): Promise<DocumentWithCostTracking> {
  const jobId = uuidv4();
  const jobPriority = await getJobPriority({
    team_id: options.teamId,
    basePriority: 10,
  });
  
  const costTracking = new CostTracking();

  const zeroDataRetention = flags?.forceZDR ?? false;

  try {
    if (isUrlBlocked(searchResult.url, flags)) {
      throw new Error("Could not scrape url: " + BLOCKLISTED_URL_MESSAGE);
    }
    logger.info("Adding scrape job", {
      scrapeId: jobId,
      url: searchResult.url,
      teamId: options.teamId,
      origin: options.origin,
      zeroDataRetention,
    });
    await addScrapeJob(
      {
        url: searchResult.url,
        mode: "single_urls" as Mode,
        team_id: options.teamId,
        scrapeOptions: {
          ...options.scrapeOptions,
          maxAge: 3 * 24 * 60 * 60 * 1000, // 3 days
        },
        internalOptions: { teamId: options.teamId, bypassBilling: true, zeroDataRetention },
        origin: options.origin,
        is_scrape: true,
        startTime: Date.now(),
        zeroDataRetention,
      },
      {},
      jobId,
      jobPriority,
      directToBullMQ,
    );

    const doc: Document = await waitForJob(jobId, options.timeout);
    
    logger.info("Scrape job completed", {
      scrapeId: jobId,
      url: searchResult.url,
      teamId: options.teamId,
      origin: options.origin,
    });
    await getScrapeQueue().remove(jobId);

    const document = {
      title: searchResult.title,
      description: searchResult.description,
      url: searchResult.url,
      ...doc,
    };

    let costTracking: ReturnType<typeof CostTracking.prototype.toJSON>;
    if (process.env.USE_DB_AUTHENTICATION === "true") {
      const { data: costTrackingResponse, error: costTrackingError } = await supabase_service.from("firecrawl_jobs")
        .select("cost_tracking")
        .eq("job_id", jobId);
      
      if (costTrackingError) {
        logger.error("Error getting cost tracking", { error: costTrackingError });
        throw costTrackingError;
      }
      
      costTracking = costTrackingResponse?.[0]?.cost_tracking;
    } else {
      costTracking = new CostTracking().toJSON();
    }

    return {
      document,
      costTracking,
    };
  } catch (error) {
    logger.error(`Error in scrapeSearchResult: ${error}`, {
      scrapeId: jobId,
      url: searchResult.url,
      teamId: options.teamId,
    });

    let statusCode = 0;
    if (error?.message?.includes("Could not scrape url")) {
      statusCode = 403;
    }
    
    const document: Document = {
      title: searchResult.title,
      description: searchResult.description,
      url: searchResult.url,
      metadata: {
        statusCode,
        error: error.message,
        proxyUsed: "basic",
      },
    };

    return {
      document,
      costTracking: new CostTracking().toJSON(),
    };
  }
}

export async function searchController(
  req: RequestWithAuth<{}, SearchResponse, SearchRequest>,
  res: Response<SearchResponse>,
) {
  const jobId = uuidv4();
  let logger = _logger.child({
    jobId,
    teamId: req.auth.team_id,
    module: "api/v2",
    method: "searchController",
    zeroDataRetention: req.acuc?.flags?.forceZDR,
  });

  if (req.acuc?.flags?.forceZDR) {
    return res.status(400).json({ success: false, error: "Your team has zero data retention enabled. This is not supported on search. Please contact support@firecrawl.com to unblock this feature." });
  }

  const startTime = new Date().getTime();
  const isSearchPreview = process.env.SEARCH_PREVIEW_TOKEN !== undefined && process.env.SEARCH_PREVIEW_TOKEN === req.body.__searchPreviewToken;
  
  let credits_billed = 0;

  try {
    req.body = searchRequestSchema.parse(req.body);

    logger = logger.child({
      query: req.body.query,
      origin: req.body.origin,
    });

    let limit = req.body.limit;

    // Buffer results by 50% to account for filtered URLs
    const num_results_buffer = Math.floor(limit * 2);

    logger.info("Searching for results");

    // Extract unique types from sources for the search function
    // After transformation, sources is always an array of objects
    const searchTypes = [...new Set(req.body.sources.map((s: any) => s.type))];

    // Build search query with category filters
    const { query: searchQuery, categoryMap } = buildSearchQuery(
      req.body.query,
      req.body.categories as CategoryOption[]
    );

    const searchResponse = await search({
      query: searchQuery,
      logger,
      advanced: false,
      num_results: num_results_buffer,
      tbs: req.body.tbs,
      filter: req.body.filter,
      lang: req.body.lang,
      country: req.body.country,
      location: req.body.location,
      type: searchTypes,
    }) as SearchV2Response;

    // Apply URL filtering if needed
    if (req.body.ignoreInvalidURLs && searchResponse.web) {
      searchResponse.web = searchResponse.web.filter(
        (result) => !isUrlBlocked(result.url, req.acuc?.flags ?? null),
      );
    }

    // Add category labels to web results
    if (searchResponse.web && searchResponse.web.length > 0) {
      searchResponse.web = searchResponse.web.map(result => ({
        ...result,
        category: getCategoryFromUrl(result.url, categoryMap),
      }));
    }
    
    // Add category labels to news results  
    if (searchResponse.news && searchResponse.news.length > 0) {
      searchResponse.news = searchResponse.news.map(result => ({
        ...result,
        category: result.url ? getCategoryFromUrl(result.url, categoryMap) : undefined,
      }));
    }

    // Apply limit to each result type separately
    let totalResultsCount = 0;
    
    // Apply limit to web results
    if (searchResponse.web && searchResponse.web.length > 0) {
      if (searchResponse.web.length > limit) {
        searchResponse.web = searchResponse.web.slice(0, limit);
      }
      totalResultsCount += searchResponse.web.length;
    }
    
    // Apply limit to images
    if (searchResponse.images && searchResponse.images.length > 0) {
      if (searchResponse.images.length > limit) {
        searchResponse.images = searchResponse.images.slice(0, limit);
      }
      totalResultsCount += searchResponse.images.length;
    }
    
    // Apply limit to news
    if (searchResponse.news && searchResponse.news.length > 0) {
      if (searchResponse.news.length > limit) {
        searchResponse.news = searchResponse.news.slice(0, limit);
      }
      totalResultsCount += searchResponse.news.length;
    }
    
    // Check if scraping is requested
    const shouldScrape = req.body.scrapeOptions.formats && req.body.scrapeOptions.formats.length > 0;
    const isAsyncScraping = req.body.asyncScraping && shouldScrape;
    
    if (!shouldScrape) {
      // No scraping - just count results for billing
      credits_billed = totalResultsCount;
    } else {
      // Common setup for both async and sync scraping
      logger.info(`Starting ${isAsyncScraping ? 'async' : 'sync'} search scraping`);
      
      // Prepare all scrape job inputs
      const scrapeInputs = prepareScrapeJobInputs(searchResponse);
      
      // Create common options
      const scrapeOptions = {
        teamId: req.auth.team_id,
        origin: req.body.origin,
        timeout: req.body.timeout,
        scrapeOptions: req.body.scrapeOptions,
      };
      
      const directToBullMQ = (req.acuc?.price_credits ?? 0) <= 3000;
      
      // Create all promises based on mode (async vs sync)
      const allPromises = [
        ...scrapeInputs.web.map(input => 
          isAsyncScraping
            ? startScrapeJob(input, scrapeOptions, logger, req.acuc?.flags ?? null, directToBullMQ, isSearchPreview)
            : scrapeSearchResult(input, scrapeOptions, logger, req.acuc?.flags ?? null, directToBullMQ, isSearchPreview)
        ),
        ...scrapeInputs.news.map(input =>
          isAsyncScraping
            ? startScrapeJob(input, scrapeOptions, logger, req.acuc?.flags ?? null, directToBullMQ, isSearchPreview)
            : scrapeSearchResult(input, scrapeOptions, logger, req.acuc?.flags ?? null, directToBullMQ, isSearchPreview)
        ),
        ...scrapeInputs.images.map(input =>
          isAsyncScraping
            ? startScrapeJob(input, scrapeOptions, logger, req.acuc?.flags ?? null, directToBullMQ, isSearchPreview)
            : scrapeSearchResult(input, scrapeOptions, logger, req.acuc?.flags ?? null, directToBullMQ, isSearchPreview)
        ),
      ];
      
      // Execute all operations in parallel
      const results = await Promise.all(allPromises);
      
      if (isAsyncScraping) {
        // Async mode: organize job IDs and return immediately
        const allJobIds = results as string[];
        const scrapeIds: { web?: string[]; news?: string[]; images?: string[] } = {};
        let currentIndex = 0;
        
        if (scrapeInputs.web.length > 0) {
          scrapeIds.web = allJobIds.slice(currentIndex, currentIndex + scrapeInputs.web.length);
          currentIndex += scrapeInputs.web.length;
        }
        
        if (scrapeInputs.news.length > 0) {
          scrapeIds.news = allJobIds.slice(currentIndex, currentIndex + scrapeInputs.news.length);
          currentIndex += scrapeInputs.news.length;
        }
        
        if (scrapeInputs.images.length > 0) {
          scrapeIds.images = allJobIds.slice(currentIndex, currentIndex + scrapeInputs.images.length);
        }
        
        credits_billed = allJobIds.length;
        
        // Bill team for async scraping
        if (!isSearchPreview) {
          billTeam(req.auth.team_id, req.acuc?.sub_id, credits_billed).catch((error) => {
            logger.error(`Failed to bill team ${req.auth.team_id} for ${credits_billed} credits: ${error}`);
          });
        }

        const endTime = new Date().getTime();
        const timeTakenInSeconds = (endTime - startTime) / 1000;

        logger.info("Logging job (async scraping)", {
          num_docs: credits_billed,
          time_taken: timeTakenInSeconds,
          scrapeIds,
        });

        logJob(
          {
            job_id: jobId,
            success: true,
            num_docs: (searchResponse.web?.length ?? 0) + (searchResponse.images?.length ?? 0) + (searchResponse.news?.length ?? 0),
            docs: [searchResponse],
            time_taken: timeTakenInSeconds,
            team_id: req.auth.team_id,
            mode: "search",
            url: req.body.query,
            scrapeOptions: req.body.scrapeOptions,
            crawlerOptions: {
              ...req.body,
              query: undefined,
              scrapeOptions: undefined,
            },
            origin: req.body.origin,
            integration: req.body.integration,
            credits_billed,
            zeroDataRetention: false,
          },
          false,
          isSearchPreview,
        );

        return res.status(200).json({
          success: true,
          data: searchResponse,
          scrapeIds,
          creditsUsed: credits_billed,
        });
      } else {
        // Sync mode: process scraped documents
        const allDocsWithCostTracking = results as DocumentWithCostTracking[];
        const scrapedResponse: SearchV2Response = {};
        let currentIndex = 0;
        
        // Process web results
        if (scrapeInputs.web.length > 0) {
          const webDocs = allDocsWithCostTracking.slice(currentIndex, currentIndex + scrapeInputs.web.length);
          scrapedResponse.web = searchResponse.web!.map((item, index) => {
            const doc = webDocs[index].document;
            return {
              url: doc.url || item.url,
              title: doc.title || item.title,
              description: doc.description || item.description,
              position: item.position,
              category: item.category,
              markdown: doc.markdown,
              html: doc.html,
              rawHtml: doc.rawHtml,
              links: doc.links,
              screenshot: doc.screenshot,
              summary: doc.summary,
              metadata: doc.metadata,
            };
          });
          currentIndex += scrapeInputs.web.length;
        }
        
        // Process news results
        if (scrapeInputs.news.length > 0) {
          const newsDocs = allDocsWithCostTracking.slice(currentIndex, currentIndex + scrapeInputs.news.length);
          const newsDocsMap = new Map(
            newsDocs.map((docWithCost, index) => [
              scrapeInputs.news[index].url,
              docWithCost.document
            ])
          );
          
          scrapedResponse.news = searchResponse.news!.map(item => {
            const doc = item.url ? newsDocsMap.get(item.url) : undefined;
            return {
              ...item,
              category: item.category,
              markdown: doc?.markdown,
              html: doc?.html,
              rawHtml: doc?.rawHtml,
              summary: doc?.summary,
              metadata: doc?.metadata,
            };
          });
          currentIndex += scrapeInputs.news.length;
        }
        
        // Process image results
        if (scrapeInputs.images.length > 0) {
          const imageDocs = allDocsWithCostTracking.slice(currentIndex, currentIndex + scrapeInputs.images.length);
          const imageDocsMap = new Map(
            imageDocs.map((docWithCost, index) => [
              scrapeInputs.images[index].url,
              docWithCost.document
            ])
          );
          
          scrapedResponse.images = searchResponse.images!.map(item => {
            const doc = item.url ? imageDocsMap.get(item.url) : undefined;
            return {
              ...item,
              markdown: doc?.markdown,
              html: doc?.html,
              rawHtml: doc?.rawHtml,
              summary: doc?.summary,
              metadata: doc?.metadata,
            };
          });
        }
        
        // Calculate credits
        const creditPromises = allDocsWithCostTracking.map(async (docWithCost) => {
          return await calculateCreditsToBeBilled(
            req.body.scrapeOptions,
            { teamId: req.auth.team_id, bypassBilling: true, zeroDataRetention: false },
            docWithCost.document, 
            docWithCost.costTracking,
            req.acuc?.flags ?? null,
          );
        });
        
        try {
          const individualCredits = await Promise.all(creditPromises);
          credits_billed = individualCredits.reduce((sum, credit) => sum + credit, 0);
        } catch (error) {
          logger.error("Error calculating credits for billing", { error });
          credits_billed = totalResultsCount;
        }
        
        // Update response with scraped data
        Object.assign(searchResponse, scrapedResponse);
      }
    }

    // Bill team once for all successful results (only for sync scraping, async already billed above)
    if (!isSearchPreview && shouldScrape && !isAsyncScraping) {
      billTeam(req.auth.team_id, req.acuc?.sub_id, credits_billed).catch((error) => {
        logger.error(`Failed to bill team ${req.auth.team_id} for ${credits_billed} credits: ${error}`);
      });
    }

    const endTime = new Date().getTime();
    const timeTakenInSeconds = (endTime - startTime) / 1000;

    logger.info("Logging job", {
      num_docs: credits_billed,
      time_taken: timeTakenInSeconds,
    });

    logJob(
      {
        job_id: jobId,
        success: true,
        num_docs: (searchResponse.web?.length ?? 0) + (searchResponse.images?.length ?? 0) + (searchResponse.news?.length ?? 0),
        docs: [searchResponse],
        time_taken: timeTakenInSeconds,
        team_id: req.auth.team_id,
        mode: "search",
        url: req.body.query,
        scrapeOptions: req.body.scrapeOptions,
        crawlerOptions: {
          ...req.body,
          query: undefined,
          scrapeOptions: undefined,
        },
        origin: req.body.origin,
        integration: req.body.integration,
        credits_billed,
        zeroDataRetention: false, // not supported
      },
      false,
      isSearchPreview,
    );

    // For sync scraping or no scraping, don't include scrapeIds
    // Return response based on mode
    const response: any = {
      success: true,
      data: searchResponse,
      creditsUsed: credits_billed,
    };
    
    return res.status(200).json(response);
  } catch (error) {
    if (error instanceof z.ZodError) {
      logger.warn("Invalid request body", { error: error.errors });
      return res.status(400).json({
        success: false,
        error: "Invalid request body",
        details: error.errors,
      });
    }
    
    if (error instanceof ScrapeJobTimeoutError) {
      return res.status(408).json({
        success: false,
        code: error.code,
        error: error.message,
      });
    }

    Sentry.captureException(error);
    logger.error("Unhandled error occurred in search", { error });
    return res.status(500).json({
      success: false,
      error: error.message,
    });
  }
}
