import {
  describe,
  it,
  expect,
  jest,
  beforeEach,
  afterEach,
} from "@jest/globals";
import { Response, NextFunction } from "express";
import { RequestWithAuth } from "../../controllers/v1/types";

// Create a mock configuration service
const mockGetConfiguration = jest.fn() as jest.MockedFunction<
  (teamId: string) => Promise<any>
>;

// Mock ConfigService before any imports
jest.mock("../../services/config-service", () => ({
  __esModule: true,
  default: Promise.resolve({
    getConfiguration: mockGetConfiguration,
  }),
}));

// Mock logger
jest.mock("../../lib/logger", () => ({
  logger: {
    debug: jest.fn(),
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
  },
}));

// Mock Redis dependencies to prevent actual connections
jest.mock("../../services/redis", () => ({
  redisEvictConnection: {
    set: jest.fn(),
    get: jest.fn(),
    expire: jest.fn(),
    pttl: jest.fn(),
  },
}));

jest.mock("../../services/rate-limiter", () => ({
  redisRateLimitClient: {
    set: jest.fn(),
    get: jest.fn(),
  },
}));

jest.mock("../../services/redlock", () => ({}));

jest.mock("../../controllers/auth", () => ({
  authenticateUser: jest.fn(),
}));

// Import middleware after mocks
import { yamlConfigDefaultsMiddleware } from "../../routes/shared";

describe("yamlConfigDefaultsMiddleware", () => {
  let mockRequest: {
    path: string;
    body?: any;
    auth: { team_id: string };
    yamlConfigMetadata?: any;
  };
  let mockResponse: Partial<Response>;
  let mockNext: jest.MockedFunction<NextFunction>;

  // Helper function to call middleware and wait for async operations
  async function callMiddleware() {
    await yamlConfigDefaultsMiddleware(
      mockRequest as any,
      mockResponse as Response,
      mockNext,
    );
    // Add a small delay to ensure async operations complete
    await new Promise(resolve => setTimeout(resolve, 50));
  }

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetConfiguration.mockResolvedValue({});

    mockRequest = {
      path: "/v2/scrape",
      body: {},
      auth: { team_id: "test-team-123" },
    };

    mockResponse = {
      headersSent: false,
    };

    mockNext = jest.fn() as unknown as jest.MockedFunction<NextFunction>;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe("Route Type Extraction", () => {
    it("should correctly identify scrape route type", async () => {
      mockRequest.path = "/v2/scrape";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("scrape");
      expect(mockNext).toHaveBeenCalled();
    });

    it("should correctly identify crawl route type", async () => {
      mockRequest.path = "/v2/crawl";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("crawl");
    });

    it("should correctly identify search route type", async () => {
      mockRequest.path = "/v2/search";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("search");
    });

    it("should correctly identify extract route type", async () => {
      mockRequest.path = "/v2/extract";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("extract");
    });

    it("should map batch-scrape to scrape route type", async () => {
      mockRequest.path = "/v2/batch-scrape";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("scrape");
    });

    it("should handle unrecognized route types", async () => {
      mockRequest.path = "/v2/unknown-endpoint";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("unknown");
      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(false);
      expect(mockNext).toHaveBeenCalled();
    });

    it("should handle paths without version prefix", async () => {
      mockRequest.path = "/scrape";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("scrape");
    });

    it("should handle v1 API paths", async () => {
      mockRequest.path = "/v1/scrape";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.routeType).toBe("scrape");
    });
  });

  describe("Configuration Loading", () => {
    it("should successfully load configuration from ConfigService", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
          onlyMainContent: true,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockGetConfiguration).toHaveBeenCalled();
      expect(mockNext).toHaveBeenCalled();
    });

    it("should handle gracefully when ConfigService is unavailable", async () => {
      mockGetConfiguration.mockRejectedValue(
        new Error("ConfigService unavailable"),
      );

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.error).toBe(
        "ConfigService unavailable",
      );
      expect(mockNext).toHaveBeenCalled();
    });

    it("should skip when configuration is empty", async () => {
      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(false);
      expect(mockNext).toHaveBeenCalled();
    });

    it("should skip when configuration is null", async () => {
      mockGetConfiguration.mockResolvedValue(null as any);

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(false);
      expect(mockNext).toHaveBeenCalled();
    });
  });

  describe("Deep Merge Behavior", () => {
    it("should merge simple configuration values", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
          onlyMainContent: true,
        },
      };

      mockRequest.body = {
        url: "https://example.com",
        formats: ["markdown"],
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body).toEqual({
        url: "https://example.com",
        formats: ["markdown"],
        timeout: 30000,
        onlyMainContent: true,
      });
      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(true);
    });

    it("should ensure YAML configuration overrides request parameters", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
          onlyMainContent: true,
        },
      };

      mockRequest.body = {
        url: "https://example.com",
        timeout: 60000, // Should be overridden by config
        mobile: false,
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.timeout).toBe(30000); // Config value wins
      expect(mockRequest.body.onlyMainContent).toBe(true); // Config value applied
      expect(mockRequest.body.url).toBe("https://example.com"); // Request value preserved when not in config
      expect(mockRequest.body.mobile).toBe(false); // Request value preserved when not in config
    });

    it("should handle deep merging of nested objects", async () => {
      const mockConfig = {
        scraping: {
          location: {
            country: "US",
            languages: ["en"],
          },
          headers: {
            "User-Agent": "Firecrawl",
            Accept: "text/html",
          },
        },
      };

      mockRequest.body = {
        location: {
          country: "CA", // Will be overridden by config
          city: "Toronto", // Will be preserved (not in config)
        },
        headers: {
          Accept: "application/json", // Will be overridden by config
          Authorization: "Bearer token", // Will be preserved (not in config)
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.location).toEqual({
        country: "US", // Config wins
        city: "Toronto", // Request preserved when not in config
        languages: ["en"], // Config applied
      });

      expect(mockRequest.body.headers).toEqual({
        "User-Agent": "Firecrawl", // Config applied
        Accept: "text/html", // Config wins
        Authorization: "Bearer token", // Request preserved when not in config
      });
    });

    it("should handle array values correctly", async () => {
      const mockConfig = {
        scraping: {
          formats: ["markdown", "html"],
          includeTags: ["p", "div"],
        },
      };

      mockRequest.body = {
        formats: ["json"], // Will be overridden by config
        excludeTags: ["script"], // Will be preserved (not in config)
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.formats).toEqual(["markdown", "html"]); // Config wins
      expect(mockRequest.body.includeTags).toEqual(["p", "div"]); // Config applied
      expect(mockRequest.body.excludeTags).toEqual(["script"]); // Request preserved
    });

    it("should handle null and undefined values correctly", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
          mobile: false,
          headers: { "User-Agent": "Test" },
        },
      };

      mockRequest.body = {
        timeout: null, // Should be ignored (null)
        mobile: undefined, // Should be ignored (undefined)
        waitFor: 0, // Should be preserved (0 is valid)
        headers: null, // Should be ignored (null)
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.timeout).toBe(30000); // Config value (null ignored)
      expect(mockRequest.body.mobile).toBe(false); // Config value (undefined ignored)
      expect(mockRequest.body.waitFor).toBe(0); // Request value preserved
      expect(mockRequest.body.headers).toEqual({ "User-Agent": "Test" }); // Config value (null ignored)
    });
  });

  describe("Error Handling", () => {
    it("should handle invalid YAML configuration gracefully", async () => {
      mockGetConfiguration.mockResolvedValue("invalid-config" as any);

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.error).toBe(
        "Configuration is not a valid object",
      );
      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(false);
      expect(mockNext).toHaveBeenCalled();
    });

    it("should continue processing when ConfigService throws error", async () => {
      const error = new Error("Configuration loading failed");
      mockGetConfiguration.mockRejectedValue(error);

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.error).toBe(
        "Configuration loading failed",
      );
      expect(mockNext).toHaveBeenCalled();
    });

    it("should handle non-Error exceptions", async () => {
      mockGetConfiguration.mockRejectedValue("String error");

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.error).toBe("String error");
      expect(mockNext).toHaveBeenCalled();
    });

    it("should not break middleware chain on configuration errors", async () => {
      mockGetConfiguration.mockRejectedValue(new Error("Test error"));

      await callMiddleware();

      expect(mockNext).toHaveBeenCalledTimes(1);
      expect(mockNext).toHaveBeenCalledWith(); // Called without error argument
    });
  });

  describe("YAML Configuration Precedence", () => {
    it("should allow YAML configuration to override request parameters", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
          mobile: true,
          formats: ["markdown"],
          headers: {
            "User-Agent": "Config-Agent",
            Accept: "text/html",
          },
        },
      };

      mockRequest.body = {
        url: "https://example.com",
        timeout: 45000,
        mobile: false,
        formats: ["json", "html"],
        headers: {
          Authorization: "Bearer xyz",
          Accept: "application/json",
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      // YAML configuration should override conflicting request parameters
      expect(mockRequest.body.url).toBe("https://example.com"); // No conflict, preserved
      expect(mockRequest.body.timeout).toBe(30000); // Config overrides request
      expect(mockRequest.body.mobile).toBe(true); // Config overrides request
      expect(mockRequest.body.formats).toEqual(["markdown"]); // Config overrides request
      expect(mockRequest.body.headers.Authorization).toBe("Bearer xyz"); // No conflict, preserved
      expect(mockRequest.body.headers.Accept).toBe("text/html"); // Config overrides request
      expect(mockRequest.body.headers["User-Agent"]).toBe("Config-Agent"); // Config applied
    });

    it("should apply YAML defaults when request parameters are missing", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
          mobile: false,
          onlyMainContent: true,
        },
      };

      mockRequest.body = {
        url: "https://example.com",
        // Missing timeout, mobile, onlyMainContent
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.url).toBe("https://example.com"); // Preserved
      expect(mockRequest.body.timeout).toBe(30000); // Applied from config
      expect(mockRequest.body.mobile).toBe(false); // Applied from config
      expect(mockRequest.body.onlyMainContent).toBe(true); // Applied from config
    });

    it("should handle mixed precedence in nested objects", async () => {
      const mockConfig = {
        scraping: {
          location: {
            country: "US",
            languages: ["en", "es"],
          },
        },
      };

      mockRequest.body = {
        location: {
          country: "CA", // Will be overridden by config
          // Missing languages - will be applied from config
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.location.country).toBe("US"); // Config wins
      expect(mockRequest.body.location.languages).toEqual(["en", "es"]); // Config applied
    });
  });

  describe("Route-Specific Configuration", () => {
    it("should apply scraping configuration for scrape routes", async () => {
      mockRequest.path = "/v2/scrape";

      const mockConfig = {
        scraping: {
          timeout: 30000,
          onlyMainContent: true,
        },
        language: {
          location: {
            country: "us",
            languages: ["en"],
          },
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.timeout).toBe(30000);
      expect(mockRequest.body.onlyMainContent).toBe(true);
      expect(mockRequest.body.location).toEqual({
        country: "us",
        languages: ["en"],
      });
    });

    it("should apply crawling configuration for crawl routes", async () => {
      mockRequest.path = "/v2/crawl";

      const mockConfig = {
        crawling: {
          limit: 100,
          maxDepth: 5,
          allowExternalLinks: false,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.limit).toBe(100);
      expect(mockRequest.body.maxDepth).toBe(5);
      expect(mockRequest.body.allowExternalLinks).toBe(false);
    });

    it("should apply search configuration with language settings for search routes", async () => {
      mockRequest.path = "/v2/search";

      const mockConfig = {
        search: {
          limit: 10,
          timeout: 60000,
        },
        language: {
          location: {
            country: "ca",
            languages: ["fr"],
          },
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.limit).toBe(10);
      expect(mockRequest.body.timeout).toBe(60000);
      expect(mockRequest.body.country).toBe("ca"); // Mapped from language.location
      expect(mockRequest.body.lang).toBe("fr"); // Mapped from language.location.languages[0]
    });

    it("should apply extraction configuration for extract routes", async () => {
      mockRequest.path = "/v2/extract";

      const mockConfig = {
        extraction: {
          maxTokens: 5000,
          temperature: 0.1,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.maxTokens).toBe(5000);
      expect(mockRequest.body.temperature).toBe(0.1);
    });

    it("should not apply configuration for unrecognized routes", async () => {
      mockRequest.path = "/v2/unknown";

      const mockConfig = {
        scraping: {
          timeout: 30000,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body.timeout).toBeUndefined();
      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(false);
    });
  });

  describe("Metadata and Debugging", () => {
    it("should add configuration metadata to request object", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata).toEqual({
        routeType: "scrape",
        configApplied: true,
        configSource: "yaml",
      });
    });

    it("should capture debugging information in metadata", async () => {
      mockRequest.path = "/v2/unknown-route";

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata).toEqual({
        routeType: "unknown",
        configApplied: false,
      });
    });

    it("should record errors in metadata", async () => {
      mockGetConfiguration.mockRejectedValue(new Error("Test error"));

      await callMiddleware();

      expect(mockRequest.yamlConfigMetadata?.error).toBe("Test error");
      expect(mockRequest.yamlConfigMetadata?.configApplied).toBe(false);
    });

    it("should initialize request body if missing", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
        },
      };

      mockRequest.body = undefined;
      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockRequest.body).toEqual({
        timeout: 30000,
      });
    });
  });

  describe("Middleware Chain Integration", () => {
    it("should call next() in all success scenarios", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      expect(mockNext).toHaveBeenCalledTimes(1);
      expect(mockNext).toHaveBeenCalledWith(); // No error passed
    });

    it("should call next() even when configuration loading fails", async () => {
      mockGetConfiguration.mockRejectedValue(new Error("Failed"));

      await callMiddleware();

      expect(mockNext).toHaveBeenCalledTimes(1);
      expect(mockNext).toHaveBeenCalledWith(); // No error passed - graceful handling
    });

    it("should not modify response object", async () => {
      const mockConfig = {
        scraping: {
          timeout: 30000,
        },
      };

      mockGetConfiguration.mockResolvedValue(mockConfig);

      await callMiddleware();

      // Response should remain unchanged
      expect(mockResponse.headersSent).toBe(false);
    });

    it("should handle async operations correctly", async () => {
      let configResolved = false;

      mockGetConfiguration.mockImplementation(async () => {
        await new Promise(resolve => setTimeout(resolve, 10));
        configResolved = true;
        return { scraping: { timeout: 30000 } };
      });

      await callMiddleware();

      expect(configResolved).toBe(true);
      expect(mockNext).toHaveBeenCalled();
    });
  });
});
