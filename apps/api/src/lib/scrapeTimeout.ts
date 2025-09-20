/**
 * Centralized timeout utility for scraping operations
 * Provides consistent timeout values across the application
 */

const DEFAULT_TIMEOUT = 30000; // 30 seconds

const TIMEOUT_MAP = {
  "robots-txt": 5000, // 5 seconds for robots.txt
  default: DEFAULT_TIMEOUT,
};

/**
 * Get the timeout value for a specific scrape operation
 * @param operation - The operation type (e.g., "robots-txt", "scrape", etc.)
 * @returns Timeout value in milliseconds
 */
export function scrapeTimeout(operation = "default") {
  return TIMEOUT_MAP[operation] ?? DEFAULT_TIMEOUT;
}
