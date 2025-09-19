#!/usr/bin/env node
import "dotenv/config";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import { logger } from "../lib/logger";

interface CliArgs {
  output?: string;
  help?: boolean;
}

// Simple type definitions for YAML config (without importing from config-validator to avoid circular dependencies)
interface YamlConfig {
  scraping?: Record<string, any>;
  crawling?: Record<string, any>;
  search?: Record<string, any>;
  embeddings?: Record<string, any>;
  language?: Record<string, any>;
  features?: Record<string, any>;
}

interface EnvironmentMapping {
  [key: string]: {
    section: keyof YamlConfig;
    field: string;
    type: "string" | "number" | "boolean" | "array";
    comment?: string;
  };
}

// Mapping of environment variables to YAML configuration sections
const ENV_MAPPINGS: EnvironmentMapping = {
  // Scraping configuration
  BLOCK_MEDIA: {
    section: "scraping",
    field: "blockMedia",
    type: "boolean",
    comment: "Block media (audio/video) content",
  },
  PROXY_SERVER: {
    section: "scraping",
    field: "proxy",
    type: "string",
    comment: "Proxy server configuration",
  },
  ENABLE_VECTOR_STORAGE: {
    section: "features",
    field: "vectorStorage",
    type: "boolean",
    comment: "Enable vector storage for embeddings",
  },
  USE_DB_AUTHENTICATION: {
    section: "features",
    field: "useDbAuthentication",
    type: "boolean",
    comment: "Enable database authentication",
  },
  DEFAULT_CRAWL_LANGUAGE: {
    section: "language",
    field: "includeLangs",
    type: "array",
    comment: "Default language filtering for crawl operations",
  },
  MODEL_EMBEDDING_NAME: {
    section: "embeddings",
    field: "model",
    type: "string",
    comment: "Embedding model to use",
  },
  VECTOR_DIMENSION: {
    section: "embeddings",
    field: "dimension",
    type: "number",
    comment: "Vector dimension for embeddings",
  },
  MAX_EMBEDDING_CONTENT_LENGTH: {
    section: "embeddings",
    field: "maxContentLength",
    type: "number",
    comment: "Maximum content length for embedding generation",
  },
  MIN_SIMILARITY_THRESHOLD: {
    section: "embeddings",
    field: "minSimilarityThreshold",
    type: "number",
    comment: "Minimum similarity threshold for vector search",
  },
  TEI_URL: {
    section: "embeddings",
    field: "teiUrl",
    type: "string",
    comment: "TEI service base URL",
  },
  EMBEDDINGS_PROVIDER: {
    section: "embeddings",
    field: "provider",
    type: "string",
    comment: "Embedding provider (openai or tei)",
  },
};

// Default timeout values based on common patterns
const DEFAULT_VALUES = {
  scraping: {
    timeout: 30000,
    waitFor: 0,
    onlyMainContent: false,
    mobile: false,
    fastMode: false,
    removeBase64Images: true,
    skipTlsVerification: false,
    storeInCache: true,
    formats: ["markdown"],
  },
  crawling: {
    limit: 10000,
    maxDepth: 10,
    allowExternalLinks: false,
    allowSubdomains: false,
    ignoreRobotsTxt: false,
    sitemap: "include" as const,
    deduplicateSimilarURLs: true,
    ignoreQueryParameters: false,
  },
  search: {
    limit: 5,
    lang: "en",
    country: "us",
    sources: ["web"],
    timeout: 60000,
    ignoreInvalidURLs: false,
  },
  embeddings: {
    enabled: false,
    model: "Qwen/Qwen2.5-0.5B-Instruct",
    provider: "tei",
    dimension: 1024,
    maxContentLength: 8000,
    minSimilarityThreshold: 0.7,
  },
  language: {
    location: {
      country: "us-generic",
      languages: ["en"],
    },
  },
  features: {
    vectorStorage: false,
    useDbAuthentication: false,
    ipWhitelist: false,
    zeroDataRetention: false,
  },
};

function parseArguments(): CliArgs {
  const args: CliArgs = {};
  const argv = process.argv.slice(2);

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];

    if (arg === "--help" || arg === "-h") {
      args.help = true;
    } else if (arg === "--output" || arg === "-o") {
      const nextArg = argv[i + 1];
      if (!nextArg || nextArg.startsWith("-")) {
        throw new Error("--output flag requires a file path");
      }
      args.output = nextArg;
      i++; // Skip next argument as it's the output path
    } else if (arg.startsWith("--output=")) {
      args.output = arg.split("=")[1];
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return args;
}

function showHelp(): void {
  console.log(`
Firecrawl YAML Configuration Generator

USAGE:
  npm run generate-config                    # Output to stdout
  npm run generate-config -- --output FILE  # Write to file
  npm run generate-config -- --help         # Show this help

OPTIONS:
  -o, --output FILE    Write configuration to specified file
  -h, --help          Show this help message

DESCRIPTION:
  Generates a defaults.yaml configuration file based on your current
  environment variables. This helps migrate from environment variable
  configuration to YAML-based configuration.

EXAMPLES:
  npm run generate-config -- --output defaults.yaml
  npm run generate-config | grep -v "^#" > minimal.yaml

ENVIRONMENT VARIABLES:
  The following environment variables will be mapped to YAML configuration:
  
  Scraping:
    BLOCK_MEDIA              -> scraping.blockMedia
    PROXY_SERVER             -> scraping.proxy
    
  Features:
    ENABLE_VECTOR_STORAGE    -> features.vectorStorage
    USE_DB_AUTHENTICATION    -> features.useDbAuthentication
    
  Language:
    DEFAULT_CRAWL_LANGUAGE   -> language.includeLangs
    
  Embeddings:
    MODEL_EMBEDDING_NAME     -> embeddings.model
    EMBEDDINGS_PROVIDER      -> embeddings.provider
    TEI_URL                  -> embeddings.teiUrl
    VECTOR_DIMENSION         -> embeddings.dimension
    MAX_EMBEDDING_CONTENT_LENGTH -> embeddings.maxContentLength
    MIN_SIMILARITY_THRESHOLD -> embeddings.minSimilarityThreshold

MIGRATION:
  1. Run: npm run generate-config -- --output defaults.yaml
  2. Review and customize the generated configuration
  3. Place the file in your project root
  4. Restart Firecrawl to use the new configuration
  
  The YAML configuration will supplement your environment variables,
  not replace them. Environment variables will continue to work as before.
`);
}

function convertValue(
  value: string,
  type: "string" | "number" | "boolean" | "array",
): any {
  switch (type) {
    case "boolean":
      return value.toLowerCase() === "true";
    case "number": {
      const num = Number(value);
      if (isNaN(num)) {
        throw new Error(`Invalid number value: ${value}`);
      }
      return num;
    }
    case "array": {
      if (value === "all" || value === "") {
        return [];
      }
      return value
        .split(",")
        .map(s => s.trim())
        .filter(s => s.length > 0);
    }
    case "string":
    default:
      return value;
  }
}

function generateConfigFromEnvironment(): YamlConfig {
  const config: YamlConfig = {};
  const sectionsWithValues = new Set<keyof YamlConfig>();

  // Process environment variable mappings
  for (const [envVar, mapping] of Object.entries(ENV_MAPPINGS)) {
    const envValue = process.env[envVar];

    if (envValue !== undefined && envValue !== "") {
      if (!config[mapping.section]) {
        config[mapping.section] = {} as any;
      }

      const section = config[mapping.section] as any;

      try {
        // Always convert environment values to proper types
        section[mapping.field] = convertValue(envValue, mapping.type);

        sectionsWithValues.add(mapping.section);
      } catch (error) {
        logger.warn(`Failed to convert environment variable ${envVar}`, {
          module: "generate-config",
          error: error instanceof Error ? error.message : String(error),
          value: envValue,
        });
      }
    }
  }

  // Add default values for sections that have some configured values
  sectionsWithValues.forEach(section => {
    if (section in DEFAULT_VALUES) {
      const defaults = DEFAULT_VALUES[section as keyof typeof DEFAULT_VALUES];
      const currentSection = config[section] as any;

      // Only add defaults for fields that aren't already set
      for (const [key, value] of Object.entries(defaults)) {
        if (!(key in currentSection)) {
          currentSection[key] = value;
        }
      }
    }
  });

  return config;
}

function generateYamlComments(): string {
  return `# Firecrawl Default Configuration
# 
# This file was auto-generated from your current environment variables.
# Place this file as 'defaults.yaml' in your project root to set default
# values for API requests. YAML configuration takes precedence over request parameters.
#
# Configuration precedence (highest to lowest):
# FIRECRAWL_CONFIG_OVERRIDE > YAML (with env substitutions) > request params > defaults
#
# Environment variable substitution:
# - Use \${VAR_NAME} to substitute environment variables
# - Use \${VAR_NAME:-default_value} to provide defaults
#
# Docker usage:
# docker run -v ./defaults.yaml:/app/defaults.yaml firecrawl
#
# For more information, see the documentation at:
# https://github.com/mendableai/firecrawl
#

`;
}

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function addSectionComments(yamlStr: string): string {
  const sectionComments = {
    "scraping:":
      "# Scraping defaults - applied to /scrape and /crawl endpoints",
    "crawling:": "# Crawling defaults - applied to /crawl endpoint only",
    "search:": "# Search defaults - applied to /search endpoint only",
    "embeddings:": "# Embeddings configuration - for vector storage features",
    "language:": "# Language and location defaults - applied across endpoints",
    "features:": "# Feature flags and system configuration",
  };

  let result = yamlStr;

  for (const [sectionKey, comment] of Object.entries(sectionComments)) {
    result = result.replace(
      new RegExp(`^${escapeRegExp(sectionKey)}`, "m"),
      `${comment}\n${sectionKey}`,
    );
  }

  return result;
}

function addFieldComments(yamlStr: string): string {
  const fieldComments: Record<string, string> = {};

  // Build field comment mappings from ENV_MAPPINGS
  for (const [envVar, mapping] of Object.entries(ENV_MAPPINGS)) {
    if (mapping.comment) {
      const fieldKey = `${mapping.field}:`;
      fieldComments[fieldKey] = `  # ${mapping.comment} (from ${envVar})`;
    }
  }

  // Add general field comments
  const generalComments = {
    "timeout:": "  # Request timeout in milliseconds",
    "waitFor:": "  # Wait time before scraping (milliseconds)",
    "formats:":
      "  # Output formats: markdown, html, rawHtml, links, screenshot, embeddings",
    "onlyMainContent:":
      "  # Extract only main content, ignore navigation/sidebars",
    "mobile:": "  # Use mobile user agent for scraping",
    "fastMode:": "  # Enable fast mode (may reduce content quality)",
    "removeBase64Images:": "  # Remove base64 encoded images from output",
    "skipTlsVerification:": "  # Skip TLS certificate verification",
    "storeInCache:": "  # Cache scraped content for faster repeated requests",
    "blockMedia:": "  # Block media (audio/video) content",
    "teiUrl:": "  # TEI service base URL",
    "proxy:": "  # Proxy configuration (auto, none, or proxy URL)",
    "limit:": "  # Maximum number of pages to crawl",
    "maxDepth:": "  # Maximum crawl depth from starting URL",
    "allowExternalLinks:": "  # Follow links to external domains",
    "allowSubdomains:": "  # Follow links to subdomains",
    "ignoreRobotsTxt:": "  # Ignore robots.txt restrictions",
    "sitemap:": "  # Use sitemap for crawling (include, exclude, auto)",
    "deduplicateSimilarURLs:": "  # Remove similar/duplicate URLs",
    "ignoreQueryParameters:":
      "  # Ignore URL query parameters for deduplication",
    "lang:": "  # Search language code (en, es, fr, etc.)",
    "country:": "  # Search country code (us, uk, ca, etc.)",
    "sources:": "  # Search sources: web, images, news",
    "ignoreInvalidURLs:": "  # Skip URLs that return errors",
    "enabled:": "  # Enable automatic embedding generation",
    "model:": "  # Embedding model name",
    "provider:": "  # Embedding provider (openai, tei)",
    "dimension:": "  # Vector dimension (must match model)",
    "maxContentLength:": "  # Maximum content length for embeddings",
    "minSimilarityThreshold:": "  # Minimum similarity for search results",
    "includeLangs:": "  # Languages to include in crawling",
    "excludeLangs:": "  # Languages to exclude from crawling",
    "languages:": "  # Preferred languages for content",
    "vectorStorage:": "  # Enable vector storage with pgvector",
    "useDbAuthentication:": "  # Use database for API key authentication",
    "ipWhitelist:": "  # Enable IP whitelisting",
    "zeroDataRetention:": "  # Enable zero data retention mode",
  };

  Object.assign(fieldComments, generalComments);

  let result = yamlStr;

  for (const [fieldKey, comment] of Object.entries(fieldComments)) {
    const regex = new RegExp(`^(\\s*)${escapeRegExp(fieldKey)}`, "gm");
    result = result.replace(regex, `$1${comment}\n$1${fieldKey}`);
  }

  return result;
}

async function generateConfig(): Promise<string> {
  try {
    // Generate configuration from environment
    const config = generateConfigFromEnvironment();

    // Simple validation - just check that we have some configuration
    if (Object.keys(config).length === 0) {
      logger.warn("No environment variables found to generate configuration", {
        module: "generate-config",
      });
    }

    // Convert to YAML
    let yamlStr = yaml.dump(config, {
      indent: 2,
      lineWidth: 100,
      noRefs: true,
      sortKeys: false,
    });

    // Add comments
    yamlStr = addSectionComments(yamlStr);
    yamlStr = addFieldComments(yamlStr);

    // Add header comments
    const headerComments = generateYamlComments();
    yamlStr = headerComments + yamlStr;

    // Add migration guidance at the end
    yamlStr += `
# Migration from Environment Variables:
# 
# This configuration was generated from the following environment variables:
${Object.entries(ENV_MAPPINGS)
  .filter(([envVar]) => process.env[envVar] !== undefined)
  .map(
    ([envVar, mapping]) =>
      `#   ${envVar} -> ${mapping.section}.${mapping.field}`,
  )
  .join("\n")}
#
# Environment variables will continue to work alongside this configuration.
# To fully migrate, you can remove the environment variables after verifying
# that this configuration works as expected.
`;

    return yamlStr;
  } catch (error) {
    throw new Error(
      `Failed to generate configuration: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

async function main(): Promise<void> {
  try {
    const args = parseArguments();

    if (args.help) {
      showHelp();
      process.exit(0);
    }

    logger.debug("Generating YAML configuration from environment variables", {
      module: "generate-config",
      outputFile: args.output || "stdout",
    });

    const yamlConfig = await generateConfig();

    if (args.output) {
      // Ensure directory exists
      const outputDir = path.dirname(args.output);
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
      }

      // Write to file
      fs.writeFileSync(args.output, yamlConfig, "utf8");

      logger.info(`Configuration written successfully`, {
        module: "generate-config",
        outputFile: args.output,
        size: yamlConfig.length,
      });

      console.log(`✅ Configuration generated successfully: ${args.output}`);
      console.log("");
      console.log("Next steps:");
      console.log("1. Review the generated configuration");
      console.log('2. Place the file as "defaults.yaml" in your project root');
      console.log("3. Restart Firecrawl to load the new configuration");
      console.log("");
      console.log(
        "The generated configuration includes comments explaining each option.",
      );
      console.log(
        "Environment variables will continue to work alongside this configuration.",
      );
    } else {
      // Output to stdout
      console.log(yamlConfig);
    }
  } catch (error) {
    if (error instanceof Error && error.message.includes("Unknown argument")) {
      console.error(`❌ ${error.message}`);
      console.error("");
      console.error("Use --help for usage information.");
      process.exit(1);
    }

    logger.error("Failed to generate configuration", {
      module: "generate-config",
      error: error instanceof Error ? error.message : String(error),
    });

    console.error(
      `❌ Error: ${error instanceof Error ? error.message : String(error)}`,
    );
    process.exit(1);
  }
}

// Run the script if called directly
if (require.main === module) {
  main().catch(error => {
    console.error("Unexpected error:", error);
    process.exit(1);
  });
}

export {
  generateConfigFromEnvironment,
  generateConfig,
  ENV_MAPPINGS,
  DEFAULT_VALUES,
};
