import { z } from "zod";
import { countries } from "./validate-country";
import { logger } from "./logger";
import { SecurityAuditLogger } from "./security/audit-logger";

const SPECIAL_COUNTRIES = ["us-generic", "us-whitelist"];
const COUNTRY_CODES = new Set([
  ...Object.keys(countries).map(code => code.toUpperCase()),
  ...SPECIAL_COUNTRIES.map(code => code.toLowerCase()),
]);

// Allowed environment variables whitelist for security
const ALLOWED_ENV_VARS = new Set([
  "FIRECRAWL_API_URL",
  "PORT",
  "REDIS_HOST",
  "REDIS_PORT",
  "REDIS_PASSWORD",
  "DATABASE_URL",
  "VECTOR_DIMENSION",
  "MODEL_EMBEDDING_NAME",
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "SUPABASE_URL",
  "SUPABASE_ANON_KEY",
  "BULL_AUTH_KEY",
  "LOGTAIL_KEY",
  "PLAYWRIGHT_MICROSERVICE_URL",
  "LLAMAPARSE_API_KEY",
  "SERP_API_KEY",
  "SCRAPING_BEE_API_KEY",
  "FIRE_ENGINE_BETA_URL",
  "HYPERBOLIC_API_KEY",
  "OPENROUTER_API_KEY",
  "TOGETHER_API_KEY",
  "OLLAMA_BASE_URL",
  "FLY_MACHINE_VERSION",
  "POSTHOG_API_KEY",
  "POSTHOG_HOST",
  "SLACK_WEBHOOK_URL",
  "ENV",
  "NODE_ENV",
  "NUM_WORKERS_PER_QUEUE",
  "REDIS_RATE_LIMIT_URL",
  "USE_DB_AUTHENTICATION",
  "SUPABASE_SERVICE_TOKEN",
  "STRIPE_PRICE_ID",
  "STRIPE_WEBHOOK_SECRET",
  "WEBHOOK_URL",
  "WORKERS_URL",
  "WORKERS_TOKEN",
  "SCRAPE_DO_API_KEY",
  "BRIGHTDATA_PASSWORD",
  "BRIGHTDATA_USERNAME",
  "LLAMAINDEX_LOGGING_ENABLED",
  "TEST_API_KEY",
  "SELF_HOSTED_WEBHOOK_URL",
  "FIRECRAWL_CONFIG_PATH",
  "FIRECRAWL_CONFIG_OVERRIDE",
  // Test environment variables used in tests
  "TEST_VAR",
  "TIMEOUT_VAR",
  "MOBILE_VAR",
  "ENABLE_FEATURE",
  "DISABLE_FEATURE",
  "INVALID_NUMBER",
  "MISSING_VAR",
  "NONEXISTENT_VAR",
  "ANOTHER_VAR",
  "UNDEFINED_VAR",
  "VAR",
  "TEST_SUITE_SELF_HOSTED",
  "IDMUX_URL",
  "CONFIG_DEBOUNCE_DELAY",
]);

const strictMessage =
  "Unrecognized key in YAML configuration -- please review the configuration documentation";

// Environment variable substitution schema
const envVarPattern = /\$\{([A-Z_][A-Z0-9_]*)(:-([^}]*))?\}/g;
const envVarPatternSingle = /^\$\{([A-Z_][A-Z0-9_]*)(:-([^}]*))?\}$/;

const envVarString = z
  .string()
  .refine(
    val => {
      if (!val.includes("${")) return true;
      const opens = (val.match(/\$\{/g) || []).length;
      const matches = Array.from(val.matchAll(envVarPattern)).length;
      return opens === matches;
    },
    { message: "Invalid environment variable syntax. Use ${VAR:-default}" },
  )
  .transform(val => {
    if (!val.includes("${")) return val;
    return val.replace(envVarPattern, (_match, varName, _all, defaultValue) => {
      // Security: Check if environment variable is whitelisted
      if (!ALLOWED_ENV_VARS.has(varName)) {
        logger.warn("Attempted to access unauthorized environment variable", {
          variable: varName,
          module: "config-validator",
          method: "envVarString.transform",
        });
        SecurityAuditLogger.logUnauthorizedAccess("ENV_ACCESS", {
          variable: varName,
          context: "config-validator.envVarString.transform",
        });
        return defaultValue || "";
      }

      const envValue = process.env[varName];

      // Log sensitive variable access
      SecurityAuditLogger.logEnvAccess(
        varName,
        "config-validator.envVarString.transform",
      );
      if (
        varName.includes("KEY") ||
        varName.includes("SECRET") ||
        varName.includes("TOKEN") ||
        varName.includes("PASSWORD")
      ) {
        logger.info("Sensitive environment variable accessed", {
          variable: varName,
          redacted: "[REDACTED]",
          module: "config-validator",
          method: "envVarString.transform",
        });
      } else {
        logger.debug("Environment variable accessed", {
          variable: varName,
          module: "config-validator",
          method: "envVarString.transform",
        });
      }

      return envValue !== undefined ? envValue : defaultValue || "";
    });
  });

const envVarNumber = z.union([
  z.number(),
  envVarString.pipe(z.coerce.number()),
]);

const envVarBoolean = z.union([
  z.boolean(),
  envVarString.pipe(z.coerce.boolean()),
]);

const envVarArray = z.union([
  z.string().array(),
  envVarString.transform(val =>
    val
      .split(",")
      .map(s => s.trim())
      .filter(s => s.length > 0),
  ),
]);

// Location configuration schema
const locationConfigSchema = z
  .object({
    country: z
      .string()
      .refine(
        country =>
          COUNTRY_CODES.has(country.toUpperCase()) ||
          COUNTRY_CODES.has(country.toLowerCase()),
        {
          message:
            "Invalid country code. Must be a valid ISO 3166-1 alpha-2 code or special country.",
        },
      )
      .optional(),
    languages: envVarArray.optional(),
  })
  .strict()
  .optional();

// Scraping configuration schema (based on baseScrapeOptions)
const scrapingConfigSchema = z
  .object({
    formats: z
      .array(
        z.enum([
          "markdown",
          "html",
          "rawHtml",
          "links",
          "images",
          "summary",
          "embeddings",
          "json",
          "changeTracking",
          "screenshot",
          "attributes",
        ]),
      )
      .optional(),
    headers: z.record(z.string(), envVarString).optional(),
    includeTags: envVarArray.optional(),
    excludeTags: envVarArray.optional(),
    onlyMainContent: envVarBoolean.optional(),
    timeout: envVarNumber.optional(),
    waitFor: envVarNumber.optional(),
    mobile: envVarBoolean.optional(),
    skipTlsVerification: envVarBoolean.optional(),
    removeBase64Images: envVarBoolean.optional(),
    fastMode: envVarBoolean.optional(),
    blockAds: envVarBoolean.optional(),
    proxy: z
      .union([
        z.enum(["basic", "stealth", "auto"]),
        envVarString.pipe(z.enum(["basic", "stealth", "auto"])),
      ])
      .optional(),
    maxAge: envVarNumber.optional(),
    storeInCache: envVarBoolean.optional(),
  })
  .strict()
  .optional();

// Language configuration schema
const languageConfigSchema = z
  .object({
    includeLangs: envVarArray.optional(),
    excludeLangs: envVarArray.optional(),
    location: locationConfigSchema,
  })
  .strict()
  .optional();

// Crawling configuration schema (based on crawlerOptions)
const crawlingConfigSchema = z
  .object({
    includePaths: envVarArray.optional(),
    excludePaths: envVarArray.optional(),
    maxDiscoveryDepth: envVarNumber.optional(),
    limit: envVarNumber.optional(),
    allowExternalLinks: envVarBoolean.optional(),
    allowSubdomains: envVarBoolean.optional(),
    ignoreRobotsTxt: envVarBoolean.optional(),
    sitemap: z
      .union([
        z.enum(["skip", "include", "only"]),
        envVarString.pipe(z.enum(["skip", "include", "only"])),
      ])
      .optional(),
    deduplicateSimilarURLs: envVarBoolean.optional(),
    ignoreQueryParameters: envVarBoolean.optional(),
    regexOnFullURL: envVarBoolean.optional(),
    delay: envVarNumber.optional(),
  })
  .strict()
  .optional();

// Search configuration schema
const searchConfigSchema = z
  .object({
    limit: envVarNumber.optional(),
    lang: envVarString.optional(),
    country: envVarString
      .refine(
        country =>
          !country ||
          COUNTRY_CODES.has(country.toUpperCase()) ||
          COUNTRY_CODES.has(country.toLowerCase()),
        {
          message:
            "Invalid country code. Must be a valid ISO 3166-1 alpha-2 code or special country.",
        },
      )
      .optional(),
    sources: envVarArray.optional(),
    timeout: envVarNumber.optional(),
    ignoreInvalidURLs: envVarBoolean.optional(),
  })
  .strict()
  .optional();

// Embeddings configuration schema
const embeddingsConfigSchema = z
  .object({
    enabled: envVarBoolean.optional(),
    model: envVarString.optional(),
    provider: envVarString.optional(),
    teiUrl: envVarString.optional(),
    dimension: envVarNumber.optional(),
    maxContentLength: envVarNumber.optional(),
    minSimilarityThreshold: envVarNumber.optional(),
  })
  .strict()
  .optional();

// Features configuration schema
const featuresConfigSchema = z
  .object({
    vectorStorage: envVarBoolean.optional(),
    useDbAuthentication: envVarBoolean.optional(),
    ipWhitelist: envVarBoolean.optional(),
    zeroDataRetention: envVarBoolean.optional(),
  })
  .strict()
  .optional();

// Main YAML configuration schema
export const yamlConfigSchema = z
  .object({
    scraping: scrapingConfigSchema,
    language: languageConfigSchema,
    crawling: crawlingConfigSchema,
    search: searchConfigSchema,
    embeddings: embeddingsConfigSchema,
    features: featuresConfigSchema,
  })
  .strict();

// Configuration type definitions
export type YamlConfig = z.infer<typeof yamlConfigSchema>;
export type ScrapingConfig = z.infer<typeof scrapingConfigSchema>;
export type LanguageConfig = z.infer<typeof languageConfigSchema>;
export type CrawlingConfig = z.infer<typeof crawlingConfigSchema>;
export type SearchConfig = z.infer<typeof searchConfigSchema>;
export type EmbeddingsConfig = z.infer<typeof embeddingsConfigSchema>;
export type FeaturesConfig = z.infer<typeof featuresConfigSchema>;

// Environment variable validation helpers
export function validateEnvVarSyntax(value: string): boolean {
  // If it contains } but not ${, it's malformed
  if (value.includes("}") && !value.includes("${")) return false;
  // If it doesn't contain ${, it's a regular string (valid)
  if (!value.includes("${")) return true;
  // If it contains ${, it must be exactly one valid env var pattern
  return envVarPatternSingle.test(value);
}

export function resolveEnvVars(value: any): any {
  if (typeof value === "string") {
    if (!value.includes("${")) return value;
    return value.replace(
      envVarPattern,
      (_match, varName, _all, defaultValue) => {
        // Security: Check if environment variable is whitelisted
        if (!ALLOWED_ENV_VARS.has(varName)) {
          logger.warn("Attempted to access unauthorized environment variable", {
            variable: varName,
            module: "config-validator",
            method: "resolveEnvVars",
          });
          SecurityAuditLogger.logUnauthorizedAccess("ENV_ACCESS", {
            variable: varName,
            context: "config-validator.resolveEnvVars",
          });
          return defaultValue || "";
        }

        const envValue = process.env[varName];

        // Log sensitive variable access
        SecurityAuditLogger.logEnvAccess(
          varName,
          "config-validator.resolveEnvVars",
        );
        if (
          varName.includes("KEY") ||
          varName.includes("SECRET") ||
          varName.includes("TOKEN") ||
          varName.includes("PASSWORD")
        ) {
          logger.info("Sensitive environment variable accessed", {
            variable: varName,
            redacted: "[REDACTED]",
            module: "config-validator",
            method: "resolveEnvVars",
          });
        } else {
          logger.debug("Environment variable accessed", {
            variable: varName,
            module: "config-validator",
            method: "resolveEnvVars",
          });
        }

        return envValue !== undefined ? envValue : defaultValue || "";
      },
    );
  }

  if (Array.isArray(value)) {
    return value.map(resolveEnvVars);
  }

  if (value && typeof value === "object") {
    const resolved: any = {};
    for (const [key, val] of Object.entries(value)) {
      resolved[key] = resolveEnvVars(val);
    }
    return resolved;
  }

  return value;
}

// Configuration validation function
export function validateYamlConfig(config: any): {
  success: boolean;
  data?: YamlConfig;
  error?: string;
  details?: Array<{ path: string; message: string }>;
} {
  try {
    const result = yamlConfigSchema.safeParse(config);
    if (result.success) {
      return { success: true, data: result.data };
    } else {
      const details = result.error.errors.map(err => ({
        path: err.path.join("."),
        message: err.message,
      }));
      const errorMessage = details
        .map(detail => `${detail.path}: ${detail.message}`)
        .join("; ");
      return { success: false, error: errorMessage, details };
    }
  } catch (error) {
    return {
      success: false,
      error: `Validation error: ${error instanceof Error ? error.message : "Unknown error"}`,
    };
  }
}

// Route-specific configuration extraction functions
export function extractScrapeConfig(config: YamlConfig): any {
  const scrapeConfig: any = {};

  if (config.scraping) {
    Object.assign(scrapeConfig, config.scraping);
  }

  if (config.language?.location) {
    scrapeConfig.location = config.language.location;
  }

  return scrapeConfig;
}

export function extractCrawlConfig(config: YamlConfig): any {
  const crawlConfig: any = {};

  if (config.crawling) {
    Object.assign(crawlConfig, config.crawling);
  }

  return crawlConfig;
}

export function extractSearchConfig(config: YamlConfig): any {
  const searchConfig: any = {};

  if (config.search) {
    Object.assign(searchConfig, config.search);
  }

  if (config.language?.location) {
    if (
      searchConfig.country === undefined &&
      config.language.location.country
    ) {
      searchConfig.country = config.language.location.country;
    }
    const langs = config.language.location.languages;
    if (
      searchConfig.lang === undefined &&
      Array.isArray(langs) &&
      langs.length > 0
    ) {
      searchConfig.lang = langs[0];
    }
  }

  return searchConfig;
}

export function extractEmbeddingsConfig(config: YamlConfig): any {
  return config.embeddings || {};
}

export function extractFeaturesConfig(config: YamlConfig): any {
  return config.features || {};
}
