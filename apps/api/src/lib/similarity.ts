/**
 * Centralized configuration for similarity threshold handling
 */

/**
 * Gets the default minimum similarity threshold from environment variable
 * @returns A number between 0 and 1, defaults to 0.7 if invalid or not set
 */
export function getDefaultMinSimilarityThreshold(): number {
  const raw = process.env.MIN_SIMILARITY_THRESHOLD;
  const parsed = raw ? parseFloat(raw) : NaN;

  if (Number.isFinite(parsed) && parsed >= 0 && parsed <= 1) {
    return parsed;
  }

  return 0.7;
}

/**
 * The default minimum similarity threshold value
 * This constant is computed once when the module is loaded
 */
export const DEFAULT_MIN_SIMILARITY_THRESHOLD =
  getDefaultMinSimilarityThreshold();
