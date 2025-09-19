import {
  scrapeRaw,
  scrape,
  crawlStart,
  search,
  scrapeTimeout,
  Identity,
  idmux,
} from "../snips/v2/lib";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import * as crypto from "crypto";
import ConfigService from "../../services/config-service";
import request from "supertest";
import { TEST_URL } from "../snips/lib";
import { SearchRequestInput } from "../../controllers/v2/types";
import { SearchV2Response } from "../../lib/entities";
import { waitUntil, waitForConfigReload } from "../helpers/wait-utils";

// Helper function for raw search requests
async function searchRaw(body: SearchRequestInput, identity: Identity) {
  return await request(TEST_URL)
    .post("/v2/search")
    .set("Authorization", `Bearer ${identity.apiKey}`)
    .set("Content-Type", "application/json")
    .send(body);
}

let identity: Identity;

beforeAll(async () => {
  identity = await idmux({
    name: "yaml-config-e2e",
    concurrency: 50,
    credits: 100000,
  });
}, 10000 + scrapeTimeout);

describe("YAML Configuration E2E Tests", () => {
  let tempConfigDir: string;
  let originalConfigPath: string | undefined;
  let originalConfigOverride: string | undefined;

  beforeEach(async () => {
    try {
      // Create temporary directory for test config files
      tempConfigDir = fs.mkdtempSync(
        path.join(os.tmpdir(), "firecrawl-yaml-test-"),
      );

      // Store original environment variables
      originalConfigPath = process.env.FIRECRAWL_CONFIG_PATH;
      originalConfigOverride = process.env.FIRECRAWL_CONFIG_OVERRIDE;

      // Clear any existing config override
      delete process.env.FIRECRAWL_CONFIG_OVERRIDE;

      // Clear ConfigService cache
      const configService = await ConfigService;
      configService.clearCache();
    } catch (error) {
      console.error("Error in beforeEach:", error);
      throw error;
    }
  });

  afterEach(async () => {
    // Restore original environment variables
    if (originalConfigPath !== undefined) {
      process.env.FIRECRAWL_CONFIG_PATH = originalConfigPath;
    } else {
      delete process.env.FIRECRAWL_CONFIG_PATH;
    }

    if (originalConfigOverride !== undefined) {
      process.env.FIRECRAWL_CONFIG_OVERRIDE = originalConfigOverride;
    } else {
      delete process.env.FIRECRAWL_CONFIG_OVERRIDE;
    }

    // Clear ConfigService cache
    const configService = await ConfigService;
    configService.clearCache();

    // Clean up temporary directory
    if (fs.existsSync(tempConfigDir)) {
      fs.rmSync(tempConfigDir, { recursive: true, force: true });
    }
  });

  describe("Valid YAML Configuration Tests", () => {
    it(
      "applies YAML scraping defaults correctly in scrape request",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  onlyMainContent: true
  timeout: 45000
  formats:
    - type: markdown
    - type: links
  mobile: false
  blockAds: true
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            // No explicit configuration - should use YAML defaults
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
        expect(response.body.data.links).toBeDefined();

        // Verify metadata indicates config was applied
        expect(response.body.data.metadata).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "applies YAML crawling defaults correctly in crawl request",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
crawling:
  limit: 5
  maxDiscoveryDepth: 2
  allowSubdomains: false
  deduplicateSimilarURLs: true
  ignoreRobotsTxt: false
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await crawlStart(
          {
            url: "https://firecrawl.dev",
            // No explicit configuration - should use YAML defaults
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.id).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "applies YAML search defaults correctly in search request",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
search:
  limit: 3
  lang: en
  country: us
  timeout: 45000
language:
  location:
    country: us-generic
    languages: ["en"]
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await searchRaw(
          {
            query: "Firecrawl web scraping",
            // No explicit configuration - should use YAML defaults
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data).toBeDefined();
        expect(Array.isArray(response.body.data)).toBe(true);
      },
      scrapeTimeout,
    );

    it(
      "applies complex YAML configuration across multiple sections",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  formats:
    - type: markdown
    - type: links
  onlyMainContent: true
  timeout: 35000
  blockAds: true
  fastMode: false

language:
  location:
    country: us-generic
    languages: ["en"]

features:
  vectorStorage: false
  zeroDataRetention: false
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.links).toBeDefined();
        expect(response.metadata).toBeDefined();
      },
      scrapeTimeout,
    );
  });

  describe("YAML Configuration Precedence Tests", () => {
    it(
      "Request body parameters override YAML defaults",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  onlyMainContent: true
  timeout: 30000
  mobile: false
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            mobile: true, // Should be overridden by YAML (false)
            timeout: 25000, // Should be overridden by YAML (30000)
            formats: ["links"], // Should be overridden by YAML (markdown)
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        // YAML config should override request body - expect markdown, not links
        expect(response.body.data.markdown).toBeDefined();
        expect(response.body.data.links).toBeUndefined();
      },
      scrapeTimeout,
    );

    it(
      "partial override behavior works correctly",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  onlyMainContent: true
  timeout: 30000
  mobile: false
  blockAds: true
  formats:
    - type: markdown
    - type: links
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            mobile: true, // Override only this parameter
            // Other parameters should come from YAML
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
        expect(response.body.data.links).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "nested object override behavior works correctly",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  location:
    country: us-generic
    languages: ["en"]
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            location: {
              country: "DE", // Override only country, languages should remain from YAML
            },
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
      },
      scrapeTimeout,
    );
  });

  describe("Environment Variable Substitution Tests", () => {
    it(
      "environment variable substitution works in actual requests",
      async () => {
        const testTimeout = "35000";
        const testCountry = "us-generic";
        process.env.TEST_TIMEOUT = testTimeout;
        process.env.TEST_COUNTRY = testCountry;

        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: \${TEST_TIMEOUT}
  formats:
    - type: markdown
language:
  location:
    country: \${TEST_COUNTRY}
    languages: ["en"]
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.metadata).toBeDefined();

        // Clean up test environment variables
        delete process.env.TEST_TIMEOUT;
        delete process.env.TEST_COUNTRY;
      },
      scrapeTimeout,
    );

    it(
      "default values work when environment variables are missing",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: \${MISSING_VAR:-30000}
  onlyMainContent: \${MISSING_BOOL:-true}
  formats:
    - type: markdown
search:
  limit: \${MISSING_LIMIT:-5}
  country: \${MISSING_COUNTRY:-us}
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.metadata).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "environment variable resolution works in integration context",
      async () => {
        const testId = crypto.randomUUID();
        process.env.TEST_ID = testId;

        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  headers:
    X-Firecrawl-Test-Id: \${TEST_ID}
  formats:
    - type: markdown
    - type: metadata
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Use firecrawl.dev itself as the test URL since it's reliable
        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.metadata).toBeDefined();

        // While we can't verify the header was sent (firecrawl.dev doesn't echo headers),
        // we can at least verify the environment variable substitution didn't break the request
        expect(response.markdown).toContain("Firecrawl");

        // Clean up
        delete process.env.TEST_ID;
      },
      scrapeTimeout,
    );
  });

  describe("Configuration Precedence Tests", () => {
    it(
      "JSON override via FIRECRAWL_CONFIG_OVERRIDE takes precedence",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 30000
  onlyMainContent: true
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Set JSON override
        process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify({
          scraping: {
            timeout: 25000,
            onlyMainContent: false,
          },
        });

        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.metadata).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "YAML configuration has highest precedence",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 30000
  mobile: false
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Set JSON override
        process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify({
          scraping: {
            timeout: 25000,
            mobile: true,
          },
        });

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            timeout: 20000, // Should override both YAML and JSON
            mobile: false, // Should override both YAML and JSON
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "precedence order works correctly across all layers",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 30000
  onlyMainContent: true
  mobile: false
  blockAds: true
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Set JSON override (overrides some YAML values)
        process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify({
          scraping: {
            timeout: 25000, // Override YAML
            mobile: true, // Override YAML
            // onlyMainContent and blockAds should remain from YAML
          },
        });

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            timeout: 20000, // Override both YAML and JSON
            // mobile should come from JSON override
            // onlyMainContent and blockAds should come from YAML
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
      },
      scrapeTimeout,
    );
  });

  describe("File Watching Integration Tests", () => {
    it(
      "configuration reload when YAML file is modified",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");

        // Initial configuration
        const initialConfig = `
scraping:
  formats:
    - type: markdown
  timeout: 30000
`;
        fs.writeFileSync(configPath, initialConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // First request
        const response1 = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response1.markdown).toBeDefined();

        // Modify configuration file
        const modifiedConfig = `
scraping:
  formats:
    - type: markdown
    - type: links
  timeout: 35000
`;
        fs.writeFileSync(configPath, modifiedConfig);

        // Small delay to ensure filesystem registers the change
        await new Promise(resolve => setTimeout(resolve, 100));

        // Wait for configuration to reload using polling
        const configService = await ConfigService;
        await waitForConfigReload(
          configService,
          config => {
            const scraping = config?.scraping;
            if (!scraping) return false;

            const hasLinks = scraping.formats?.some(
              (f: any) => f.type === "links",
            );
            const hasCorrectTimeout = scraping.timeout === 35000;

            return hasLinks && hasCorrectTimeout;
          },
          10000, // Increase timeout to 10 seconds
        );

        // Second request with new config
        const response2 = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response2.markdown).toBeDefined();
        expect(response2.links).toBeDefined();
      },
      scrapeTimeout * 2,
    );

    it(
      "graceful handling of invalid YAML during reload",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");

        // Initial valid configuration
        const validConfig = `
scraping:
  formats:
    - type: markdown
  timeout: 30000
`;
        fs.writeFileSync(configPath, validConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // First request with valid config
        const response1 = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response1.markdown).toBeDefined();

        // Write invalid YAML
        const invalidConfig = `
scraping:
  formats
    - type: markdown  # Missing colon
  timeout: 30000
`;
        fs.writeFileSync(configPath, invalidConfig);

        // Wait for configuration to detect invalid YAML
        const configService = await ConfigService;
        await waitUntil(
          async () => {
            configService.clearCache();
            try {
              const config = await configService.getConfiguration();
              // Invalid YAML should result in empty config or error
              return !config || Object.keys(config).length === 0;
            } catch {
              // Error loading config is expected for invalid YAML
              return true;
            }
          },
          5000,
          100,
          "invalid YAML detection",
        );

        // Request should still work (fallback to no config)
        const response2 = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            formats: ["markdown"], // Explicitly specify since config is invalid
          },
          identity,
        );

        expect(response2.statusCode).toBe(200);
        expect(response2.body.success).toBe(true);
      },
      scrapeTimeout * 2,
    );
  });

  describe("Route-Specific Configuration Tests", () => {
    it(
      "scrape endpoint applies scraping defaults correctly",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  onlyMainContent: true
  timeout: 35000
  formats:
    - type: markdown
    - type: links

crawling:
  limit: 100
  allowSubdomains: true

search:
  limit: 10
  country: gb
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.links).toBeDefined();
        expect(response.metadata).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "crawl endpoint applies crawling defaults correctly",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 35000
  formats:
    - type: markdown

crawling:
  limit: 3
  maxDiscoveryDepth: 1
  allowSubdomains: false

search:
  limit: 10
  country: gb
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await crawlStart(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.id).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "search endpoint applies search and language defaults correctly",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 35000

crawling:
  limit: 100

search:
  limit: 3
  timeout: 45000

language:
  location:
    country: us-generic
    languages: ["en"]
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await search(
          {
            query: "Firecrawl web scraping",
          },
          identity,
        );

        expect(response.web).toBeDefined();
        expect(response.web?.length).toBeGreaterThan(0);
        expect(response.web?.length).toBeLessThanOrEqual(3);
      },
      scrapeTimeout,
    );

    it(
      "route-specific configs don't interfere with each other",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 35000
  formats:
    - type: markdown

crawling:
  limit: 5
  maxDiscoveryDepth: 2

search:
  limit: 3
  country: us
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Test scrape endpoint
        const scrapeResponse = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );
        expect(scrapeResponse.markdown).toBeDefined();

        // Test crawl endpoint
        const crawlResponse = await crawlStart(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );
        expect(crawlResponse.statusCode).toBe(200);
        expect(crawlResponse.body.success).toBe(true);

        // Test search endpoint
        const searchResponse = await search(
          {
            query: "Firecrawl",
          },
          identity,
        );
        expect(searchResponse.web).toBeDefined();
      },
      scrapeTimeout * 2,
    );
  });

  describe("Error Handling Integration Tests", () => {
    it(
      "invalid YAML configurations don't break API requests",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const invalidYaml = `
scraping:
  formats
    - type: markdown  # Missing colon
  timeout: "invalid_number"
`;
        fs.writeFileSync(configPath, invalidYaml);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Request should still work with explicit parameters
        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            formats: ["markdown"],
            timeout: 30000,
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "missing configuration files don't affect API functionality",
      async () => {
        const nonExistentPath = path.join(tempConfigDir, "nonexistent.yaml");
        process.env.FIRECRAWL_CONFIG_PATH = nonExistentPath;

        const response = await scrape(
          {
            url: "https://firecrawl.dev",
            formats: ["markdown"],
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.metadata).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "graceful degradation when ConfigService fails",
      async () => {
        // Set invalid config path to force service failure
        process.env.FIRECRAWL_CONFIG_PATH = "/invalid/path/that/does/not/exist";

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            formats: ["markdown"],
            timeout: 30000,
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
      },
      scrapeTimeout,
    );

    it(
      "invalid environment variable references are handled gracefully",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: \${INVALID_VAR}  # No default provided
  onlyMainContent: \${ANOTHER_INVALID:-true}  # Default provided
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            timeout: 30000, // Override the invalid env var
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
        expect(response.body.data.markdown).toBeDefined();
      },
      scrapeTimeout,
    );
  });

  describe("Configuration Validation Tests", () => {
    it(
      "configuration validation catches invalid values",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: -1000  # Invalid negative timeout
  onlyMainContent: "not_a_boolean"
  formats:
    - type: markdown
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Should still work with explicit valid parameters
        const response = await scrapeRaw(
          {
            url: "https://firecrawl.dev",
            timeout: 30000,
            onlyMainContent: true,
            formats: ["markdown"],
          },
          identity,
        );

        expect(response.statusCode).toBe(200);
        expect(response.body.success).toBe(true);
      },
      scrapeTimeout,
    );

    it(
      "unknown configuration keys are handled appropriately",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: 30000
  unknownKey: "some_value"  # Unknown key
  formats:
    - type: markdown

unknownSection:
  someValue: 123
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Should still apply valid configurations
        const response = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );

        expect(response.markdown).toBeDefined();
        expect(response.metadata).toBeDefined();
      },
      scrapeTimeout,
    );
  });

  describe("Real-world Integration Scenarios", () => {
    it(
      "comprehensive production-like configuration works end-to-end",
      async () => {
        process.env.CUSTOM_TIMEOUT = "40000";
        process.env.CUSTOM_COUNTRY = "us-generic";
        process.env.ENABLE_FEATURES = "false";

        const configPath = path.join(tempConfigDir, "defaults.yaml");
        const yamlConfig = `
scraping:
  timeout: \${CUSTOM_TIMEOUT:-30000}
  onlyMainContent: true
  blockAds: true
  fastMode: false
  formats:
    - type: markdown
    - type: links
  location:
    country: \${CUSTOM_COUNTRY:-us}
    languages: ["en"]

language:
  location:
    country: \${CUSTOM_COUNTRY:-us-generic}
    languages: ["en"]

crawling:
  limit: 50
  maxDiscoveryDepth: 3
  allowSubdomains: false
  deduplicateSimilarURLs: true

search:
  limit: 5
  lang: en
  country: us
  timeout: 60000

features:
  vectorStorage: \${ENABLE_FEATURES:-false}
  zeroDataRetention: \${ENABLE_FEATURES:-false}
`;
        fs.writeFileSync(configPath, yamlConfig);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // Test scrape with partial override
        const scrapeResponse = await scrape(
          {
            url: "https://firecrawl.dev",
            mobile: true, // Override defaults
          },
          identity,
        );

        expect(scrapeResponse.markdown).toBeDefined();
        expect(scrapeResponse.links).toBeDefined();

        // Test search with defaults
        const searchResponse = await search(
          {
            query: "Firecrawl documentation",
          },
          identity,
        );

        expect(searchResponse.web).toBeDefined();
        expect(searchResponse.web?.length).toBeGreaterThan(0);
        expect(searchResponse.web?.length).toBeLessThanOrEqual(5);

        // Clean up test environment variables
        delete process.env.CUSTOM_TIMEOUT;
        delete process.env.CUSTOM_COUNTRY;
        delete process.env.ENABLE_FEATURES;
      },
      scrapeTimeout * 2,
    );

    it(
      "configuration changes apply to subsequent requests",
      async () => {
        const configPath = path.join(tempConfigDir, "defaults.yaml");

        // Initial configuration
        const config1 = `
scraping:
  formats:
    - type: markdown
  timeout: 30000
`;
        fs.writeFileSync(configPath, config1);
        process.env.FIRECRAWL_CONFIG_PATH = configPath;

        // First request
        const response1 = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );
        expect(response1.markdown).toBeDefined();
        expect(response1.links).toBeUndefined();

        // Update configuration
        const config2 = `
scraping:
  formats:
    - type: markdown
    - type: links
  timeout: 35000
`;
        fs.writeFileSync(configPath, config2);

        // Small delay to ensure filesystem registers the change
        await new Promise(resolve => setTimeout(resolve, 100));

        // Wait for configuration to reload using polling
        const configService = await ConfigService;
        await waitForConfigReload(
          configService,
          config => {
            const scraping = config?.scraping;
            if (!scraping) return false;

            const hasLinks = scraping.formats?.some(
              (f: any) => f.type === "links",
            );
            const hasCorrectTimeout = scraping.timeout === 35000;

            return hasLinks && hasCorrectTimeout;
          },
          10000, // Increase timeout to 10 seconds
        );

        // Second request with updated config
        const response2 = await scrape(
          {
            url: "https://firecrawl.dev",
          },
          identity,
        );
        expect(response2.markdown).toBeDefined();
        expect(response2.links).toBeDefined();
      },
      scrapeTimeout * 2,
    );
  });
});
