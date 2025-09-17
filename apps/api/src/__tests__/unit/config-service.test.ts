import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  jest,
} from "@jest/globals";
import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import ConfigService from "../../services/config-service";

// Mock fs and path modules
jest.mock("fs");
jest.mock("path");
jest.mock("js-yaml");
jest.mock("../../lib/logger", () => ({
  logger: {
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  },
}));

const mockFs = fs as jest.Mocked<typeof fs>;
const mockPath = path as jest.Mocked<typeof path>;
const mockYaml = yaml as jest.Mocked<typeof yaml>;

describe("ConfigService", () => {
  let configService: Awaited<typeof ConfigService>;
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(async () => {
    // Reset singleton
    (ConfigService as any).instance = undefined;

    // Store original env
    originalEnv = { ...process.env };

    // Reset mocks
    jest.clearAllMocks();

    // Mock path methods
    mockPath.join.mockImplementation((...args) => args.join("/"));

    // Default fs mocks
    mockFs.existsSync.mockReturnValue(true);
    mockFs.statSync.mockReturnValue({
      mtime: new Date("2024-01-01T00:00:00.000Z"),
    } as fs.Stats);
    mockFs.readFileSync.mockReturnValue("test: value");
    mockFs.watchFile.mockImplementation(() => ({}) as any);
    mockFs.unwatchFile.mockImplementation(() => {});

    // Default yaml mock
    mockYaml.load.mockReturnValue({ test: "value" });

    // Mock process.cwd
    jest.spyOn(process, "cwd").mockReturnValue("/app");
  });

  afterEach(() => {
    // Restore environment
    process.env = originalEnv;

    // Cleanup service
    if (configService) {
      configService.shutdown();
    }

    jest.restoreAllMocks();
  });

  describe("Singleton Pattern", () => {
    it("should return the same instance on multiple calls", async () => {
      const instance1 = await ConfigService;
      const instance2 = await ConfigService;

      expect(instance1).toBe(instance2);
    });

    it("should initialize singleton only once", async () => {
      const instance1 = await ConfigService;
      const instance2 = await ConfigService;

      // Should only create one instance
      expect(instance1).toBe(instance2);
    });
  });

  describe("Configuration Path Discovery", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should use FIRECRAWL_CONFIG_PATH when provided and file exists", async () => {
      process.env.FIRECRAWL_CONFIG_PATH = "/custom/config.yaml";
      mockFs.existsSync.mockImplementation(
        path => path === "/custom/config.yaml",
      );

      // Reset singleton to test path discovery
      (ConfigService as any).instance = undefined;
      const service = await ConfigService;

      await service.getConfiguration();

      expect(mockFs.readFileSync).toHaveBeenCalledWith(
        "/custom/config.yaml",
        "utf8",
      );
    });

    it("should fallback to default paths when FIRECRAWL_CONFIG_PATH doesn't exist", async () => {
      process.env.FIRECRAWL_CONFIG_PATH = "/nonexistent/config.yaml";
      mockFs.existsSync.mockImplementation(
        path => path === "/app/defaults.yaml",
      );

      (ConfigService as any).instance = undefined;
      const service = await ConfigService;

      await service.getConfiguration();

      expect(mockFs.readFileSync).toHaveBeenCalledWith(
        "/app/defaults.yaml",
        "utf8",
      );
    });

    it("should check multiple default paths in order", async () => {
      const expectedPaths = [
        "/app/defaults.yaml",
        "/app/config/defaults.yaml",
        "/app/../../defaults.yaml",
      ];

      // Mock first path exists
      mockFs.existsSync.mockImplementation(path => path === expectedPaths[0]);

      (ConfigService as any).instance = undefined;
      const service = await ConfigService;

      await service.getConfiguration();

      expect(mockFs.readFileSync).toHaveBeenCalledWith(
        expectedPaths[0],
        "utf8",
      );
    });
  });

  describe("YAML File Loading", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should load and parse valid YAML file", async () => {
      const yamlContent = "scraping:\n  timeout: 30000\n  mobile: false";
      const expectedConfig = { scraping: { timeout: 30000, mobile: false } };

      mockFs.readFileSync.mockReturnValue(yamlContent);
      mockYaml.load.mockReturnValue(expectedConfig);

      const config = await configService.getConfiguration();

      expect(mockFs.readFileSync).toHaveBeenCalledWith(
        "/app/defaults.yaml",
        "utf8",
      );
      expect(mockYaml.load).toHaveBeenCalledWith(yamlContent);
      expect(config).toEqual(expectedConfig);
    });

    it("should return empty config when file doesn't exist", async () => {
      mockFs.existsSync.mockReturnValue(false);

      const config = await configService.getConfiguration();

      expect(config).toEqual({});
      expect(mockFs.readFileSync).not.toHaveBeenCalled();
    });

    it("should handle YAML parsing errors gracefully", async () => {
      mockYaml.load.mockImplementation(() => {
        throw new Error("Invalid YAML syntax");
      });

      const config = await configService.getConfiguration();

      expect(config).toEqual({});
    });

    it("should handle file read errors gracefully", async () => {
      mockFs.readFileSync.mockImplementation(() => {
        throw new Error("Permission denied");
      });

      const config = await configService.getConfiguration();

      expect(config).toEqual({});
    });

    it("should handle invalid YAML content types", async () => {
      mockYaml.load.mockReturnValue(null);

      const config = await configService.getConfiguration();

      expect(config).toEqual({});
    });

    it("should handle non-object YAML content", async () => {
      mockYaml.load.mockReturnValue("string content");

      const config = await configService.getConfiguration();

      expect(config).toEqual({});
    });
  });

  describe("Environment Variable Substitution", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should substitute environment variables with default values", async () => {
      process.env.TEST_VAR = "test_value";

      const yamlConfig = {
        scraping: {
          timeout: "${TEST_VAR:-30000}",
          mobile: "${MOBILE_VAR:-false}",
        },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const config = await configService.getConfiguration();

      expect(config.scraping.timeout).toBe("test_value");
      expect(config.scraping.mobile).toBe("false");
    });

    it("should use default values when environment variables don't exist", async () => {
      const yamlConfig = {
        scraping: {
          timeout: "${NONEXISTENT_VAR:-30000}",
          mobile: "${ANOTHER_NONEXISTENT:-true}",
        },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const config = await configService.getConfiguration();

      expect(config.scraping.timeout).toBe("30000");
      expect(config.scraping.mobile).toBe("true");
    });

    it("should handle environment variables without default values", async () => {
      process.env.TEST_VAR = "test_value";

      const yamlConfig = {
        scraping: {
          timeout: "${TEST_VAR}",
          mobile: "${NONEXISTENT_VAR}",
        },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const config = await configService.getConfiguration();

      expect(config.scraping.timeout).toBe("test_value");
      expect(config.scraping.mobile).toBe("${NONEXISTENT_VAR}"); // Returns original
    });

    it("should substitute variables in nested objects", async () => {
      process.env.DB_HOST = "localhost";
      process.env.DB_PORT = "5432";

      const yamlConfig = {
        database: {
          connection: {
            host: "${DB_HOST:-127.0.0.1}",
            port: "${DB_PORT:-3306}",
            nested: {
              value: "${DB_HOST}",
            },
          },
        },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const config = await configService.getConfiguration();

      expect(config.database.connection.host).toBe("localhost");
      expect(config.database.connection.port).toBe("5432");
      expect(config.database.connection.nested.value).toBe("localhost");
    });

    it("should substitute variables in arrays", async () => {
      process.env.LANG1 = "en";
      process.env.LANG2 = "es";

      const yamlConfig = {
        language: {
          includeLangs: ["${LANG1}", "${LANG2:-fr}"],
        },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const config = await configService.getConfiguration();

      expect(config.language.includeLangs).toEqual(["en", "es"]);
    });

    it("should handle mixed content with and without variables", async () => {
      process.env.TIMEOUT = "45000";

      const yamlConfig = {
        scraping: {
          timeout: "${TIMEOUT}",
          mobile: false,
          formats: ["markdown", "html"],
          proxy: "${PROXY:-auto}",
        },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const config = await configService.getConfiguration();

      expect(config.scraping.timeout).toBe("45000");
      expect(config.scraping.mobile).toBe(false);
      expect(config.scraping.formats).toEqual(["markdown", "html"]);
      expect(config.scraping.proxy).toBe("auto");
    });
  });

  describe("JSON Override Support", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should apply JSON override when FIRECRAWL_CONFIG_OVERRIDE is provided", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };
      const jsonOverride = { scraping: { timeout: 60000, mobile: true } };

      mockYaml.load.mockReturnValue(yamlConfig);
      process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify(jsonOverride);

      const config = await configService.getConfiguration();

      expect(config.scraping.timeout).toBe(60000);
      expect(config.scraping.mobile).toBe(true);
    });

    it("should deep merge JSON override with YAML config", async () => {
      const yamlConfig = {
        scraping: { timeout: 30000, mobile: false },
        crawling: { limit: 1000 },
      };
      const jsonOverride = {
        scraping: { timeout: 60000 },
        search: { limit: 10 },
      };

      mockYaml.load.mockReturnValue(yamlConfig);
      process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify(jsonOverride);

      const config = await configService.getConfiguration();

      expect(config.scraping.timeout).toBe(60000);
      expect(config.scraping.mobile).toBe(false); // Preserved from YAML
      expect(config.crawling.limit).toBe(1000); // Preserved from YAML
      expect(config.search.limit).toBe(10); // From JSON override
    });

    it("should handle invalid JSON override gracefully", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };

      mockYaml.load.mockReturnValue(yamlConfig);
      process.env.FIRECRAWL_CONFIG_OVERRIDE = "invalid json";

      const config = await configService.getConfiguration();

      expect(config).toEqual(yamlConfig);
    });

    it("should ignore non-object JSON override", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };

      mockYaml.load.mockReturnValue(yamlConfig);
      process.env.FIRECRAWL_CONFIG_OVERRIDE = '"string value"';

      const config = await configService.getConfiguration();

      expect(config).toEqual(yamlConfig);
    });

    it("should work when JSON override is provided but no YAML file exists", async () => {
      mockFs.existsSync.mockReturnValue(false);

      const jsonOverride = { scraping: { timeout: 60000 } };
      process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify(jsonOverride);

      const config = await configService.getConfiguration();

      expect(config).toEqual(jsonOverride);
    });
  });

  describe("Configuration Precedence", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should apply precedence: JSON override > YAML file", async () => {
      const yamlConfig = {
        scraping: { timeout: 30000, mobile: false },
        crawling: { limit: 1000 },
      };
      const jsonOverride = {
        scraping: { timeout: 60000 },
      };

      mockYaml.load.mockReturnValue(yamlConfig);
      process.env.FIRECRAWL_CONFIG_OVERRIDE = JSON.stringify(jsonOverride);

      const config = await configService.getConfiguration();

      // JSON override wins for timeout
      expect(config.scraping.timeout).toBe(60000);
      // YAML preserved for mobile
      expect(config.scraping.mobile).toBe(false);
      // YAML preserved for crawling
      expect(config.crawling.limit).toBe(1000);
    });
  });

  describe("Time-based Caching", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should cache configuration and avoid file reads within TTL", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };
      mockYaml.load.mockReturnValue(yamlConfig);

      // First call should read file
      await configService.getConfiguration();
      expect(mockFs.readFileSync).toHaveBeenCalledTimes(1);

      // Second call within TTL should use cache
      await configService.getConfiguration();
      expect(mockFs.readFileSync).toHaveBeenCalledTimes(1); // Still 1
    });

    it("should invalidate cache when file is modified", async () => {
      const yamlConfig1 = { scraping: { timeout: 30000 } };
      const yamlConfig2 = { scraping: { timeout: 60000 } };

      // First call
      mockYaml.load.mockReturnValue(yamlConfig1);
      mockFs.statSync.mockReturnValue({
        mtime: new Date("2024-01-01T00:00:00.000Z"),
      } as fs.Stats);

      const config1 = await configService.getConfiguration();
      expect(config1.scraping.timeout).toBe(30000);

      // Simulate file modification
      mockYaml.load.mockReturnValue(yamlConfig2);
      mockFs.statSync.mockReturnValue({
        mtime: new Date("2024-01-01T00:01:00.000Z"), // 1 minute later
      } as fs.Stats);

      const config2 = await configService.getConfiguration();
      expect(config2.scraping.timeout).toBe(60000);
    });

    it("should allow manual cache clearing", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };
      mockYaml.load.mockReturnValue(yamlConfig);

      // Load config
      await configService.getConfiguration();
      expect(mockFs.readFileSync).toHaveBeenCalledTimes(1);

      // Clear cache
      configService.clearCache();

      // Next call should read file again
      await configService.getConfiguration();
      expect(mockFs.readFileSync).toHaveBeenCalledTimes(2);
    });
  });

  describe("File Watching and Auto-reload", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should setup file watcher for existing config file", async () => {
      await configService.getConfiguration();

      expect(mockFs.watchFile).toHaveBeenCalledWith(
        "/app/defaults.yaml",
        { interval: 1000 },
        expect.any(Function),
      );
    });

    it("should not setup file watcher when config file doesn't exist", async () => {
      mockFs.existsSync.mockReturnValue(false);

      await configService.getConfiguration();

      expect(mockFs.watchFile).not.toHaveBeenCalled();
    });

    it("should handle file watcher setup errors gracefully", async () => {
      mockFs.watchFile.mockImplementation(() => {
        throw new Error("Watch failed");
      });

      // Should not throw
      await expect(configService.getConfiguration()).resolves.toBeDefined();
    });

    it("should cleanup file watcher on shutdown", () => {
      configService.shutdown();

      expect(mockFs.unwatchFile).toHaveBeenCalledWith("/app/defaults.yaml");
    });
  });

  describe("Route-specific Configuration", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should extract route-specific configuration", async () => {
      const yamlConfig = {
        global: { timeout: 30000 },
        scraping: { mobile: false },
        crawling: { limit: 1000 },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const scrapeConfig = await configService.getConfigForRoute("scraping");
      const crawlConfig = await configService.getConfigForRoute("crawling");

      expect(scrapeConfig).toEqual({
        timeout: 30000,
        mobile: false,
      });
      expect(crawlConfig).toEqual({
        timeout: 30000,
        limit: 1000,
      });
    });

    it("should return global config for unknown routes", async () => {
      const yamlConfig = {
        global: { timeout: 30000 },
        defaults: { mobile: false },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const unknownConfig = await configService.getConfigForRoute("unknown");

      expect(unknownConfig).toEqual({
        timeout: 30000,
        mobile: false,
      });
    });

    it("should merge global and route-specific configs properly", async () => {
      const yamlConfig = {
        global: { timeout: 30000, mobile: false },
        scraping: { timeout: 60000, proxy: "auto" },
      };

      mockYaml.load.mockReturnValue(yamlConfig);

      const scrapeConfig = await configService.getConfigForRoute("scraping");

      expect(scrapeConfig).toEqual({
        timeout: 60000, // Route-specific overrides global
        mobile: false, // Global preserved
        proxy: "auto", // Route-specific added
      });
    });
  });

  describe("Error Handling and Recovery", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should recover from file system errors", async () => {
      // First call succeeds
      const yamlConfig = { scraping: { timeout: 30000 } };
      mockYaml.load.mockReturnValue(yamlConfig);

      const config1 = await configService.getConfiguration();
      expect(config1).toEqual(yamlConfig);

      // Second call fails
      mockFs.readFileSync.mockImplementation(() => {
        throw new Error("File system error");
      });

      // Should clear cache and return empty config
      configService.clearCache();
      const config2 = await configService.getConfiguration();
      expect(config2).toEqual({});
    });

    it("should handle concurrent access safely", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };
      mockYaml.load.mockReturnValue(yamlConfig);

      // Simulate concurrent calls
      const promises = Array(10)
        .fill(null)
        .map(() => configService.getConfiguration());
      const results = await Promise.all(promises);

      // All should return the same config
      results.forEach(result => {
        expect(result).toEqual(yamlConfig);
      });

      // File should only be read once due to caching and mutex
      expect(mockFs.readFileSync).toHaveBeenCalledTimes(1);
    });

    it("should handle shutdown gracefully", () => {
      // Should not throw even if called multiple times
      expect(() => {
        configService.shutdown();
        configService.shutdown();
      }).not.toThrow();
    });
  });

  describe("Thread Safety and Concurrency", () => {
    beforeEach(async () => {
      configService = await ConfigService;
    });

    it("should handle multiple simultaneous getInstance calls", async () => {
      // Reset singleton
      (ConfigService as any).instance = undefined;

      // Create multiple promises
      const promises = Array(5)
        .fill(null)
        .map(() => ConfigService);
      const instances = await Promise.all(promises);

      // All should be the same instance
      instances.forEach(instance => {
        expect(instance).toBe(instances[0]);
      });
    });

    it("should handle cache invalidation during concurrent reads", async () => {
      const yamlConfig = { scraping: { timeout: 30000 } };
      mockYaml.load.mockReturnValue(yamlConfig);

      // Start multiple reads
      const promise1 = configService.getConfiguration();

      // Clear cache while read is happening
      configService.clearCache();

      const promise2 = configService.getConfiguration();

      const [config1, config2] = await Promise.all([promise1, promise2]);

      expect(config1).toEqual(yamlConfig);
      expect(config2).toEqual(yamlConfig);
    });
  });
});
