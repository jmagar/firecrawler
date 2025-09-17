import { z } from "zod";
import { countries } from "./validate-country";

const strictMessage =
  "Unrecognized key in YAML configuration -- please review the configuration documentation";

// Environment variable substitution schema
const envVarPattern = /\$\{([A-Z_][A-Z0-9_]*)(:-([^}]*))?\}/g;

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
      const envValue = process.env[varName];
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
      .refine(country => Object.keys(countries).includes(country), {
        message:
          "Invalid country code. Must be a valid ISO 3166-1 alpha-2 code.",
      })
      .optional(),
    languages: envVarArray.optional(),
  })
  .strict(strictMessage)
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
  .strict(strictMessage)
  .optional();

// Language configuration schema
const languageConfigSchema = z
  .object({
    includeLangs: envVarArray.optional(),
    excludeLangs: envVarArray.optional(),
    location: locationConfigSchema,
  })
  .strict(strictMessage)
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
        z.enum(["skip", "include"]),
        envVarString.pipe(z.enum(["skip", "include"])),
      ])
      .optional(),
    deduplicateSimilarURLs: envVarBoolean.optional(),
    ignoreQueryParameters: envVarBoolean.optional(),
    regexOnFullURL: envVarBoolean.optional(),
    delay: envVarNumber.optional(),
  })
  .strict(strictMessage)
  .optional();

// Search configuration schema
const searchConfigSchema = z
  .object({
    limit: envVarNumber.optional(),
    lang: envVarString.optional(),
    country: envVarString
      .refine(country => !country || Object.keys(countries).includes(country), {
        message:
          "Invalid country code. Must be a valid ISO 3166-1 alpha-2 code.",
      })
      .optional(),
    sources: envVarArray.optional(),
    timeout: envVarNumber.optional(),
    ignoreInvalidURLs: envVarBoolean.optional(),
  })
  .strict(strictMessage)
  .optional();

// Embeddings configuration schema
const embeddingsConfigSchema = z
  .object({
    enabled: envVarBoolean.optional(),
    model: envVarString.optional(),
    provider: envVarString.optional(),
    dimension: envVarNumber.optional(),
    maxContentLength: envVarNumber.optional(),
    minSimilarityThreshold: envVarNumber.optional(),
  })
  .strict(strictMessage)
  .optional();

// Features configuration schema
const featuresConfigSchema = z
  .object({
    vectorStorage: envVarBoolean.optional(),
    useDbAuthentication: envVarBoolean.optional(),
    ipWhitelist: envVarBoolean.optional(),
    zeroDataRetention: envVarBoolean.optional(),
  })
  .strict(strictMessage)
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
  .strict(strictMessage);

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
  if (!value.includes("${")) return true;
  const opens = (value.match(/\$\{/g) || []).length;
  const matches = Array.from(value.matchAll(envVarPattern)).length;
  return opens === matches;
}

export function resolveEnvVars(value: any): any {
  if (typeof value === "string") {
    if (!value.includes("${")) return value;
    return value.replace(
      envVarPattern,
      (_match, varName, _all, defaultValue) => {
        const envValue = process.env[varName];
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
    if (config.language.location.country) {
      searchConfig.country = config.language.location.country;
    }
    if (config.language.location.languages) {
      searchConfig.lang = config.language.location.languages[0];
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
