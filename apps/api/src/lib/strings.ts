import { isSelfHosted } from "./deployment";

export const BLOCKLISTED_URL_MESSAGE = isSelfHosted()
  ? "This website is no longer supported. Please check your server configuration and logs for more details."
  : "This website is no longer supported, please reach out to help@firecrawl.com for more info on how to activate it on your account.";

/**
 * Normalizes a language string by trimming whitespace, replacing underscores with hyphens, and converting to lowercase.
 * Useful for case-insensitive language comparisons.
 */
export function normalizeLanguage(value: string | undefined): string {
  return (
    value?.trim().replace(/\s+/g, " ").replace(/_/g, "-").toLowerCase() || ""
  );
}
