/**
 * Utility functions for environment variable handling
 */

/**
 * Parse environment variable as float with default fallback
 */
export function parseEnvFloat(envVar: string, defaultValue: number): number {
  const value = process.env[envVar];
  if (!value) return defaultValue;

  const parsed = parseFloat(value);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

/**
 * Parse environment variable as integer with default fallback
 */
export function parseEnvInt(envVar: string, defaultValue: number): number {
  const value = process.env[envVar];
  if (!value) return defaultValue;

  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

/**
 * Parse environment variable as boolean with default fallback
 */
export function parseEnvBoolean(
  envVar: string,
  defaultValue: boolean,
): boolean {
  const value = process.env[envVar];
  if (!value) return defaultValue;

  return value.toLowerCase() === "true";
}

/**
 * Get required environment variable or throw error
 */
export function requireEnv(envVar: string): string {
  const value = process.env[envVar];
  if (!value) {
    throw new Error(`Required environment variable ${envVar} is not set`);
  }
  return value;
}
