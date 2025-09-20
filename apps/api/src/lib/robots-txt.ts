import robotsParser, { Robot } from "robots-parser";
import { Logger } from "winston";
import { ScrapeOptions, scrapeOptions } from "../controllers/v2/types";
import { scrapeURL } from "../scraper/scrapeURL";
import { Engine } from "../scraper/scrapeURL/engines";
import { CostTracking } from "./cost-tracking";
import { scrapeTimeout } from "./scrapeTimeout";

const useFireEngine =
  process.env.FIRE_ENGINE_BETA_URL !== "" &&
  process.env.FIRE_ENGINE_BETA_URL !== undefined;

// Cache configuration
const CACHE_TTL = 3600000; // 1 hour in milliseconds
const MAX_CACHE_SIZE = 1000; // Maximum number of cached entries

interface CachedRobotsTxt {
  content: string;
  url: string;
  timestamp: number;
}

// Simple LRU cache implementation
class LRUCache<K, V> {
  private cache = new Map<K, V>();
  private maxSize: number;

  constructor(maxSize: number) {
    this.maxSize = maxSize;
  }

  get(key: K): V | undefined {
    const value = this.cache.get(key);
    if (value !== undefined) {
      // Move to end (most recently used)
      this.cache.delete(key);
      this.cache.set(key, value);
    }
    return value;
  }

  set(key: K, value: V): void {
    if (this.cache.has(key)) {
      // Update existing entry
      this.cache.delete(key);
    } else if (this.cache.size >= this.maxSize) {
      // Remove least recently used (first entry)
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    this.cache.set(key, value);
  }

  delete(key: K): boolean {
    return this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }

  get size(): number {
    return this.cache.size;
  }

  entries(): IterableIterator<[K, V]> {
    return this.cache.entries();
  }

  keys(): IterableIterator<K> {
    return this.cache.keys();
  }
}

// In-memory cache for robots.txt content with LRU eviction
const robotsCache = new LRUCache<string, CachedRobotsTxt>(MAX_CACHE_SIZE);

// Cleanup expired entries periodically
const cleanupTimer = setInterval(() => {
  const now = Date.now();
  for (const [domain, cached] of robotsCache.entries()) {
    if (now - cached.timestamp > CACHE_TTL) {
      robotsCache.delete(domain);
    }
  }
}, CACHE_TTL); // Run cleanup every hour

// Prevent timer from keeping the process alive
cleanupTimer.unref?.();

interface RobotsTxtChecker {
  robotsTxtUrl: string;
  robotsTxt: string;
  robots: Robot;
}

export async function fetchRobotsTxt(
  {
    url,
    zeroDataRetention,
    location,
  }: {
    url: string;
    zeroDataRetention: boolean;
    location?: ScrapeOptions["location"];
  },
  scrapeId: string,
  logger: Logger,
  abort?: AbortSignal,
): Promise<{ content: string; url: string }> {
  const urlObj = new URL(url);
  const domain = `${urlObj.protocol}//${urlObj.host}`;
  const robotsTxtUrl = `${domain}/robots.txt`;

  // Check cache first
  const cached = robotsCache.get(domain);
  if (cached) {
    const now = Date.now();
    if (now - cached.timestamp <= CACHE_TTL) {
      logger.debug(`Using cached robots.txt for ${domain}`);
      return { content: cached.content, url: cached.url };
    } else {
      // Remove expired entry
      robotsCache.delete(domain);
    }
  }

  const shouldPrioritizeFireEngine = location && useFireEngine;

  const forceEngine: Engine[] = [
    ...(shouldPrioritizeFireEngine
      ? [
          "fire-engine;tlsclient" as const,
          "fire-engine;tlsclient;stealth" as const,
        ]
      : []),
    "fetch",
    ...(!shouldPrioritizeFireEngine && useFireEngine
      ? [
          "fire-engine;tlsclient" as const,
          "fire-engine;tlsclient;stealth" as const,
        ]
      : []),
  ];

  let content: string = "";
  const response = await scrapeURL(
    "robots-txt;" + scrapeId,
    robotsTxtUrl,
    scrapeOptions.parse({
      formats: ["rawHtml"],
      timeout: scrapeTimeout("robots-txt"),
      ...(location ? { location } : {}),
    }),
    {
      forceEngine,
      v0DisableJsDom: true,
      externalAbort: abort
        ? {
            signal: abort,
            tier: "external",
            throwable() {
              return new Error("Robots.txt fetch aborted");
            },
          }
        : undefined,
      teamId: "robots-txt",
      zeroDataRetention,
    },
    new CostTracking(),
  );

  if (
    response.success &&
    response.document.metadata.statusCode >= 200 &&
    response.document.metadata.statusCode < 300
  ) {
    content = response.document.rawHtml!;
    const finalUrl = response.document.metadata.url || robotsTxtUrl;

    // Cache successful fetch
    robotsCache.set(domain, {
      content,
      url: finalUrl,
      timestamp: Date.now(),
    });

    logger.debug(`Cached robots.txt for ${domain}`);

    return { content, url: finalUrl };
  } else {
    logger.error(`Request failed for robots.txt fetch`, {
      method: "fetchRobotsTxt",
      robotsTxtUrl,
      error: response.success
        ? response.document.metadata.statusCode
        : response.error,
    });
    return { content: "", url: robotsTxtUrl };
  }
}

export function createRobotsChecker(
  url: string,
  robotsTxt: string,
): RobotsTxtChecker {
  const urlObj = new URL(url);
  const robotsTxtUrl = `${urlObj.protocol}//${urlObj.host}/robots.txt`;
  const robots = robotsParser(robotsTxtUrl, robotsTxt);
  return {
    robotsTxtUrl,
    robotsTxt,
    robots,
  };
}

export function isUrlAllowedByRobots(
  url: string,
  robots: Robot | null,
  userAgents: string[] = ["FireCrawlAgent", "FirecrawlAgent"],
): boolean {
  if (!robots) return true;

  for (const userAgent of userAgents) {
    let isAllowed = robots.isAllowed(url, userAgent);

    // Handle null/undefined responses - default to true (allowed)
    if (isAllowed == null) {
      isAllowed = true;
    }

    // Also check with trailing slash if URL doesn't have one
    // This catches cases like "Disallow: /path/" when user requests "/path"
    if (isAllowed && !url.endsWith("/")) {
      const urlWithSlash = url + "/";
      let isAllowedWithSlash = robots.isAllowed(urlWithSlash, userAgent);

      if (isAllowedWithSlash == null) {
        isAllowedWithSlash = true;
      }

      // If the trailing slash version is explicitly disallowed, block it
      if (isAllowedWithSlash === false) {
        isAllowed = false;
      }
    }

    if (isAllowed) {
      //   console.log("isAllowed: true, " + userAgent);
      return true;
    }
  }

  return false;
}

/**
 * Clears the robots.txt cache. Useful for testing or cache invalidation.
 */
export function clearRobotsCache(): void {
  robotsCache.clear();
}

/**
 * Gets cache statistics for monitoring purposes.
 */
export function getRobotsCacheStats(): { size: number; domains: string[] } {
  return {
    size: robotsCache.size,
    domains: Array.from(robotsCache.keys()),
  };
}
