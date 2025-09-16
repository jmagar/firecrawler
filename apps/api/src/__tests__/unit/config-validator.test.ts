import { describe, it, expect, beforeEach, afterEach } from "@jest/globals";
import {
  yamlConfigSchema,
  validateYamlConfig,
  validateEnvVarSyntax,
  resolveEnvVars,
  extractScrapeConfig,
  extractCrawlConfig,
  extractSearchConfig,
  extractEmbeddingsConfig,
  extractFeaturesConfig,
  YamlConfig,
} from "../../lib/config-validator";

describe("Config Validator", () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe("YAML Schema Validation", () => {
    it("should validate complete valid configuration", () => {
      const validConfig = {
        scraping: {
          formats: ["markdown", "html"],
          onlyMainContent: false,
          timeout: 30000,
          waitFor: 0,
          mobile: false,
          blockAds: true,
          proxy: "auto",
          removeBase64Images: true,
          skipTlsVerification: false,
          fastMode: false,
          storeInCache: true,
        },
        crawling: {
          includePaths: ["/blog/*"],
          excludePaths: ["/admin/*"],
          limit: 10000,
          maxDiscoveryDepth: 10,
          allowExternalLinks: false,
          allowSubdomains: false,
          ignoreRobotsTxt: false,
          sitemap: "include",
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
          model: "text-embedding-ada-002",
          provider: "openai",
          dimension: 1024,
          maxContentLength: 8000,
          minSimilarityThreshold: 0.7,
        },
        language: {
          includeLangs: ["en"],
          excludeLangs: ["fr"],
          location: {
            country: "us",
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

      const result = yamlConfigSchema.safeParse(validConfig);
      expect(result.success).toBe(true);
    });

    it("should validate empty configuration", () => {
      const emptyConfig = {};
      const result = yamlConfigSchema.safeParse(emptyConfig);
      expect(result.success).toBe(true);
    });

    it("should validate partial configuration", () => {
      const partialConfig = {
        scraping: {
          timeout: 45000,
          mobile: true,
        },
        search: {
          limit: 10,
        },
      };

      const result = yamlConfigSchema.safeParse(partialConfig);
      expect(result.success).toBe(true);
    });

    it("should reject unknown top-level keys", () => {
      const invalidConfig = {
        scraping: { timeout: 30000 },
        unknownSection: { value: "test" },
      };

      const result = yamlConfigSchema.safeParse(invalidConfig);
      expect(result.success).toBe(false);
      expect(result.error?.errors[0].message).toContain("Unrecognized key");
    });

    it("should reject unknown keys in sections", () => {
      const invalidConfig = {
        scraping: {
          timeout: 30000,
          unknownField: "value",
        },
      };

      const result = yamlConfigSchema.safeParse(invalidConfig);
      expect(result.success).toBe(false);
      expect(result.error?.errors[0].message).toContain("Unrecognized key");
    });

    it("should validate numeric constraints", () => {
      const invalidConfig = {
        scraping: {
          timeout: -1000, // Must be positive
          waitFor: 70000, // Must be <= 60000
        },
        search: {
          limit: 200, // Must be <= 100
        },
      };

      const result = yamlConfigSchema.safeParse(invalidConfig);
      expect(result.success).toBe(false);
      expect(result.error?.errors.length).toBeGreaterThan(0);
    });

    it("should validate array constraints", () => {
      const invalidConfig = {
        search: {
          sources: ["web", "invalid-source"], // Invalid enum value
        },
      };

      const result = yamlConfigSchema.safeParse(invalidConfig);
      expect(result.success).toBe(false);
    });

    it("should validate country codes", () => {
      const validConfig = {
        language: {
          location: {
            country: "us-generic", // Special country
          },
        },
      };

      const invalidConfig = {
        language: {
          location: {
            country: "invalid-country",
          },
        },
      };

      expect(yamlConfigSchema.safeParse(validConfig).success).toBe(true);
      expect(yamlConfigSchema.safeParse(invalidConfig).success).toBe(false);
    });
  });

  describe("Environment Variable Syntax Validation", () => {
    it("should validate correct environment variable syntax", () => {
      expect(validateEnvVarSyntax("${VAR_NAME}")).toBe(true);
      expect(validateEnvVarSyntax("${VAR_NAME:-default}")).toBe(true);
      expect(validateEnvVarSyntax("regular string")).toBe(true);
      expect(validateEnvVarSyntax("${VALID_VAR:-with spaces}")).toBe(true);
    });

    it("should reject invalid environment variable syntax", () => {
      expect(validateEnvVarSyntax("${invalid var}")).toBe(false);
      expect(validateEnvVarSyntax("${123INVALID}")).toBe(false);
      expect(validateEnvVarSyntax("${VAR")).toBe(false);
      expect(validateEnvVarSyntax("VAR}")).toBe(false);
      expect(validateEnvVarSyntax("${-INVALID}")).toBe(false);
    });

    it("should handle mixed content", () => {
      expect(validateEnvVarSyntax("prefix ${VALID_VAR} suffix")).toBe(false);
      expect(validateEnvVarSyntax("${VAR1} and ${VAR2}")).toBe(false);
    });
  });

  describe("Environment Variable Resolution", () => {
    it("should resolve environment variables with values", () => {
      process.env.TEST_VAR = "test_value";
      process.env.PORT = "8080";

      expect(resolveEnvVars("${TEST_VAR}")).toBe("test_value");
      expect(resolveEnvVars("${PORT:-3000}")).toBe("8080");
    });

    it("should use default values when variables don't exist", () => {
      delete process.env.NONEXISTENT_VAR;

      expect(resolveEnvVars("${NONEXISTENT_VAR:-default}")).toBe("default");
      expect(resolveEnvVars("${ANOTHER_VAR:-42}")).toBe("42");
    });

    it("should return empty string for undefined variables without defaults", () => {
      delete process.env.UNDEFINED_VAR;

      expect(resolveEnvVars("${UNDEFINED_VAR}")).toBe("");
    });

    it("should pass through regular strings", () => {
      expect(resolveEnvVars("regular string")).toBe("regular string");
      expect(resolveEnvVars("no variables here")).toBe("no variables here");
    });

    it("should handle whitespace in default values", () => {
      expect(resolveEnvVars("${VAR:-default with spaces}")).toBe(
        "default with spaces",
      );
      expect(resolveEnvVars("${VAR:- trimmed }")).toBe(" trimmed ");
    });
  });

  describe("Configuration Validation Function", () => {
    it("should return success for valid configuration", () => {
      const validConfig = {
        scraping: { timeout: 30000 },
        search: { limit: 5 },
      };

      const result = validateYamlConfig(validConfig);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(validConfig);
      }
    });

    it("should return detailed error for invalid configuration", () => {
      const invalidConfig = {
        scraping: { timeout: "invalid" },
        unknownSection: { value: "test" },
      };

      const result = validateYamlConfig(invalidConfig);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error).toBeDefined();
        expect(result.details).toBeDefined();
        expect(Array.isArray(result.details)).toBe(true);
        expect(result.details?.length).toBeGreaterThan(0);
      }
    });

    it("should provide path information in error details", () => {
      const invalidConfig = {
        scraping: {
          timeout: "not-a-number",
        },
      };

      const result = validateYamlConfig(invalidConfig);

      expect(result.success).toBe(false);
      if (!result.success) {
        const errorDetail = result.details?.[0];
        expect(errorDetail).toBeDefined();
        expect(errorDetail?.path).toContain("scraping");
        expect(errorDetail?.message).toBeDefined();
      }
    });

    it("should handle non-Zod errors gracefully", () => {
      const circularRef: any = {};
      circularRef.self = circularRef;

      const result = validateYamlConfig(circularRef);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error).toBeDefined();
      }
    });
  });

  describe("Environment Variable Schema Integration", () => {
    it("should validate and transform environment variable strings", () => {
      process.env.TIMEOUT_VAR = "45000";
      process.env.MOBILE_VAR = "true";

      const config = {
        scraping: {
          timeout: "${TIMEOUT_VAR:-30000}",
          mobile: "${MOBILE_VAR:-false}",
        },
      };

      const result = yamlConfigSchema.safeParse(config);
      expect(result.success).toBe(true);

      if (result.success) {
        expect(result.data.scraping?.timeout).toBe(45000);
        expect(result.data.scraping?.mobile).toBe(true);
      }
    });

    it("should handle boolean environment variables", () => {
      process.env.ENABLE_FEATURE = "true";
      process.env.DISABLE_FEATURE = "false";

      const config = {
        features: {
          vectorStorage: "${ENABLE_FEATURE}",
          ipWhitelist: "${DISABLE_FEATURE}",
        },
      };

      const result = yamlConfigSchema.safeParse(config);
      expect(result.success).toBe(true);

      if (result.success) {
        expect(result.data.features?.vectorStorage).toBe(true);
        expect(result.data.features?.ipWhitelist).toBe(false);
      }
    });

    it("should handle invalid numeric environment variables", () => {
      process.env.INVALID_NUMBER = "not-a-number";

      const config = {
        scraping: {
          timeout: "${INVALID_NUMBER}",
        },
      };

      const result = yamlConfigSchema.safeParse(config);
      expect(result.success).toBe(false);
    });

    it("should use default values for missing environment variables", () => {
      delete process.env.MISSING_VAR;

      const config = {
        scraping: {
          timeout: "${MISSING_VAR:-30000}",
          mobile: "${MISSING_VAR:-false}",
        },
      };

      const result = yamlConfigSchema.safeParse(config);
      expect(result.success).toBe(true);

      if (result.success) {
        expect(result.data.scraping?.timeout).toBe(30000);
        expect(result.data.scraping?.mobile).toBe(false);
      }
    });
  });

  describe("Route-specific Config Extraction", () => {
    const testConfig: YamlConfig = {
      scraping: {
        timeout: 30000,
        mobile: false,
        formats: ["markdown"],
      },
      crawling: {
        limit: 1000,
        maxDiscoveryDepth: 5,
      },
      search: {
        limit: 10,
        lang: "en",
      },
      embeddings: {
        enabled: true,
        model: "custom-model",
      },
      language: {
        includeLangs: ["en", "es"],
        location: {
          country: "us",
          languages: ["en"],
        },
      },
      features: {
        vectorStorage: true,
        ipWhitelist: false,
      },
    };

    describe("extractScrapeConfig", () => {
      it("should extract scraping configuration", () => {
        const result = extractScrapeConfig(testConfig);

        expect(result.timeout).toBe(30000);
        expect(result.mobile).toBe(false);
        expect(result.formats).toEqual(["markdown"]);
      });

      it("should include language location in scrape config", () => {
        const result = extractScrapeConfig(testConfig);

        expect(result.location).toEqual({
          country: "us",
          languages: ["en"],
        });
      });

      it("should handle missing scraping section", () => {
        const configWithoutScraping = { language: testConfig.language };
        const result = extractScrapeConfig(configWithoutScraping);

        expect(result.location).toEqual(testConfig.language?.location);
      });

      it("should handle empty configuration", () => {
        const result = extractScrapeConfig({});

        expect(Object.keys(result).length).toBe(0);
      });
    });

    describe("extractCrawlConfig", () => {
      it("should extract crawling configuration", () => {
        const result = extractCrawlConfig(testConfig);

        expect(result.limit).toBe(1000);
        expect(result.maxDiscoveryDepth).toBe(5);
      });

      it("should handle missing crawling section", () => {
        const configWithoutCrawling = { scraping: testConfig.scraping };
        const result = extractCrawlConfig(configWithoutCrawling);

        expect(Object.keys(result).length).toBe(0);
      });
    });

    describe("extractSearchConfig", () => {
      it("should extract search configuration", () => {
        const result = extractSearchConfig(testConfig);

        expect(result.limit).toBe(10);
        expect(result.lang).toBe("en");
      });

      it("should apply language settings to search config", () => {
        const result = extractSearchConfig(testConfig);

        expect(result.country).toBe("us");
        expect(result.lang).toBe("en"); // From language.location.languages[0]
      });

      it("should prioritize explicit search config over language config", () => {
        const configWithConflict = {
          ...testConfig,
          search: {
            ...testConfig.search,
            lang: "es", // Explicit in search
          },
        };

        const result = extractSearchConfig(configWithConflict);

        expect(result.lang).toBe("es"); // Should use explicit search value
      });

      it("should handle missing language location", () => {
        const configWithoutLocation = {
          search: { limit: 5 },
          language: { includeLangs: ["en"] },
        };

        const result = extractSearchConfig(configWithoutLocation);

        expect(result.limit).toBe(5);
        expect(result.country).toBeUndefined();
        expect(result.lang).toBeUndefined();
      });
    });

    describe("extractEmbeddingsConfig", () => {
      it("should extract embeddings configuration", () => {
        const result = extractEmbeddingsConfig(testConfig);

        expect(result.enabled).toBe(true);
        expect(result.model).toBe("custom-model");
      });

      it("should handle missing embeddings section", () => {
        const configWithoutEmbeddings = { scraping: testConfig.scraping };
        const result = extractEmbeddingsConfig(configWithoutEmbeddings);

        expect(Object.keys(result).length).toBe(0);
      });
    });

    describe("extractFeaturesConfig", () => {
      it("should extract features configuration", () => {
        const result = extractFeaturesConfig(testConfig);

        expect(result.vectorStorage).toBe(true);
        expect(result.ipWhitelist).toBe(false);
      });

      it("should handle missing features section", () => {
        const configWithoutFeatures = { scraping: testConfig.scraping };
        const result = extractFeaturesConfig(configWithoutFeatures);

        expect(Object.keys(result).length).toBe(0);
      });
    });
  });

  describe("Schema Extension Behavior", () => {
    it("should properly extend base scrape options schema", () => {
      const configWithBaseOptions = {
        scraping: {
          formats: ["markdown", "html"],
          headers: { "User-Agent": "test" },
          includeTags: ["p", "h1"],
          excludeTags: ["script"],
          onlyMainContent: true,
          timeout: 45000,
          waitFor: 2000,
          mobile: true,
          skipTlsVerification: true,
          removeBase64Images: false,
          fastMode: true,
          blockAds: false,
          storeInCache: true,
        },
      };

      const result = yamlConfigSchema.safeParse(configWithBaseOptions);
      expect(result.success).toBe(true);
    });

    it("should properly extend crawler options schema", () => {
      const configWithCrawlerOptions = {
        crawling: {
          includePaths: ["/api/*", "/docs/*"],
          excludePaths: ["/admin/*"],
          maxDiscoveryDepth: 3,
          limit: 500,
          crawlEntireDomain: false,
          allowExternalLinks: true,
          allowSubdomains: true,
          ignoreRobotsTxt: true,
          sitemap: "include",
          deduplicateSimilarURLs: false,
          ignoreQueryParameters: true,
          regexOnFullURL: true,
          delay: 1000,
        },
      };

      const result = yamlConfigSchema.safeParse(configWithCrawlerOptions);
      expect(result.success).toBe(true);
    });
  });

  describe("Error Message Quality", () => {
    it("should provide clear error messages for common mistakes", () => {
      const configWithTypos = {
        scrapping: { timeout: 30000 }, // Typo: should be "scraping"
      };

      const result = validateYamlConfig(configWithTypos);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error).toContain("Unrecognized key");
      }
    });

    it("should provide specific field path in error messages", () => {
      const configWithNestedError = {
        language: {
          location: {
            country: "invalid-country-code",
          },
        },
      };

      const result = validateYamlConfig(configWithNestedError);

      expect(result.success).toBe(false);
      if (!result.success) {
        const error = result.details?.[0];
        expect(error?.path).toBe("language.location.country");
        expect(error?.message).toContain("Invalid country code");
      }
    });
  });

  describe("Edge Cases and Boundary Conditions", () => {
    it("should handle null and undefined values appropriately", () => {
      const configWithNulls = {
        scraping: {
          timeout: null,
          mobile: undefined,
        },
      };

      const result = yamlConfigSchema.safeParse(configWithNulls);
      // Should validate since these are optional fields
      expect(result.success).toBe(true);
    });

    it("should handle boundary values correctly", () => {
      const configWithBoundaries = {
        scraping: {
          timeout: 1, // Minimum positive
          waitFor: 60000, // Maximum allowed
        },
        search: {
          limit: 100, // Maximum allowed
        },
        embeddings: {
          minSimilarityThreshold: 0, // Minimum
        },
      };

      const result = yamlConfigSchema.safeParse(configWithBoundaries);
      expect(result.success).toBe(true);
    });

    it("should reject values outside boundaries", () => {
      const configOutOfBounds = {
        scraping: {
          timeout: 0, // Must be positive
          waitFor: 70000, // Exceeds maximum
        },
        search: {
          limit: 200, // Exceeds maximum
        },
        embeddings: {
          minSimilarityThreshold: 1.5, // Exceeds maximum
        },
      };

      const result = yamlConfigSchema.safeParse(configOutOfBounds);
      expect(result.success).toBe(false);
    });

    it("should handle empty arrays and objects", () => {
      const configWithEmpties = {
        language: {
          includeLangs: [],
          excludeLangs: [],
          location: {},
        },
        crawling: {
          includePaths: [],
          excludePaths: [],
        },
      };

      const result = yamlConfigSchema.safeParse(configWithEmpties);
      expect(result.success).toBe(true);
    });
  });
});
