import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { Response, NextFunction } from "express";
import { RequestWithAuth } from "../../controllers/v1/types";

// Mock ConfigService
const mockGetConfigForRoute = jest.fn() as jest.MockedFunction<
  (route: any) => Promise<any>
>;
jest.mock("../../services/config-service", () => ({
  __esModule: true,
  default: Promise.resolve({
    getConfigForRoute: mockGetConfigForRoute,
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

// Import middleware after mocks
import { yamlConfigDefaultsMiddleware } from "../../routes/shared";

describe("Vector-Search YAML Defaults", () => {
  let mockRequest: Partial<RequestWithAuth<any, any, any>>;
  let mockResponse: Partial<Response>;
  let mockNext: jest.MockedFunction<NextFunction>;

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetConfigForRoute.mockResolvedValue({});

    mockRequest = {
      path: "/v2/vector-search",
      body: {
        query: "test query",
      },
      auth: { team_id: "test-team-123" },
    };

    mockResponse = {
      headersSent: false,
    };

    mockNext = jest.fn() as unknown as jest.MockedFunction<NextFunction>;
  });

  it("should apply embeddings configuration to vector-search route", async () => {
    const mockConfig = {
      minSimilarityThreshold: 0.85,
      limit: 20,
    };

    mockGetConfigForRoute.mockResolvedValue(mockConfig);

    await yamlConfigDefaultsMiddleware(
      mockRequest as RequestWithAuth<any, any, any>,
      mockResponse as Response,
      mockNext,
    );

    // Wait for async operations
    await new Promise(resolve => setTimeout(resolve, 50));

    expect(mockGetConfigForRoute).toHaveBeenCalledWith("embeddings");
    expect(mockRequest.body.minSimilarityThreshold).toBe(0.85);
    expect(mockRequest.body.limit).toBe(20);
    expect(mockNext).toHaveBeenCalled();
  });

  it("should not skip vector-search route", async () => {
    await yamlConfigDefaultsMiddleware(
      mockRequest as RequestWithAuth<any, any, any>,
      mockResponse as Response,
      mockNext,
    );

    // Wait for async operations
    await new Promise(resolve => setTimeout(resolve, 50));

    // Should try to load config, not skip
    expect(mockGetConfigForRoute).toHaveBeenCalledWith("embeddings");
    expect(mockNext).toHaveBeenCalled();
  });

  it("should handle when no embeddings config exists", async () => {
    mockGetConfigForRoute.mockResolvedValue({});

    await yamlConfigDefaultsMiddleware(
      mockRequest as RequestWithAuth<any, any, any>,
      mockResponse as Response,
      mockNext,
    );

    // Wait for async operations
    await new Promise(resolve => setTimeout(resolve, 50));

    expect(mockGetConfigForRoute).toHaveBeenCalledWith("embeddings");
    expect(mockRequest.body.query).toBe("test query");
    expect(mockRequest.body.threshold).toBeUndefined();
    expect(mockNext).toHaveBeenCalled();
  });
});
