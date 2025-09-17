/**
 * Unit tests for vector search HTTP client integration
 * Tests request payload preparation, error handling, and edge cases
 */
import { describe, test, expect, jest, beforeEach } from "@jest/globals";
import { HttpClient } from "../utils/httpClient";
import { throwForBadResponse, normalizeAxiosError } from "../utils/errorHandler";
import { VectorSearchRequest, VectorSearchResponse, VectorSearchResult, VectorSearchFilters } from "../types";
import type { AxiosResponse, AxiosError } from "axios";

// Mock the HTTP client
jest.mock("../utils/httpClient");
jest.mock("../utils/errorHandler");

// Mock axios module
jest.mock("axios", () => ({
  create: jest.fn(() => ({
    request: jest.fn(),
  })),
  isAxiosError: jest.fn(),
}));

const MockedHttpClient = HttpClient as jest.MockedClass<typeof HttpClient>;
const mockedThrowForBadResponse = throwForBadResponse as jest.MockedFunction<typeof throwForBadResponse>;
const mockedNormalizeAxiosError = normalizeAxiosError as jest.MockedFunction<typeof normalizeAxiosError>;

// Sample function to test - simulating the vector search method pattern
async function vectorSearch(http: HttpClient, request: VectorSearchRequest): Promise<VectorSearchResponse> {
  // Input validation
  if (!request.query || !request.query.trim()) {
    throw new Error("Query cannot be empty");
  }
  if (request.limit != null && (request.limit <= 0 || request.limit > 100)) {
    throw new Error("Limit must be between 1 and 100");
  }
  if (request.offset != null && request.offset < 0) {
    throw new Error("Offset must be non-negative");
  }
  if (request.threshold != null && (request.threshold < 0 || request.threshold > 1)) {
    throw new Error("Threshold must be between 0 and 1");
  }

  // Payload preparation
  const payload: Record<string, unknown> = {
    query: request.query.trim(),
  };
  
  if (request.limit != null) payload.limit = request.limit;
  if (request.offset != null) payload.offset = request.offset;
  if (request.threshold != null) payload.threshold = request.threshold;
  if (request.includeContent != null) payload.includeContent = request.includeContent;
  if (request.filters) payload.filters = request.filters;
  if (request.origin && request.origin.trim()) payload.origin = request.origin.trim();
  if (request.integration && request.integration.trim()) payload.integration = request.integration.trim();

  try {
    // HTTP request
    const res = await http.post<VectorSearchResponse>("/v2/vector-search", payload);
    
    // Response handling
    if (res.status !== 200 || !res.data?.success) {
      throwForBadResponse(res, "vector-search");
    }
    
    return res.data;
  } catch (err: any) {
    // Error handling
    if (err?.isAxiosError) return normalizeAxiosError(err, "vector-search");
    throw err;
  }
}

describe("Vector Search HTTP Client Integration", () => {
  let mockHttpClient: jest.Mocked<HttpClient>;

  beforeEach(() => {
    jest.clearAllMocks();
    mockHttpClient = {
      post: jest.fn(),
      get: jest.fn(),
      delete: jest.fn(),
      prepareHeaders: jest.fn(),
      getApiUrl: jest.fn(),
      getApiKey: jest.fn(),
    } as any;
  });

  describe("Request Payload Preparation", () => {
    test("prepares minimal request payload with only query", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "test query",
            totalResults: 0,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 50,
              vectorSearchMs: 100,
              totalMs: 150,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await vectorSearch(mockHttpClient, request);

      expect(mockHttpClient.post).toHaveBeenCalledWith("/v2/vector-search", {
        query: "test query",
      });
    });

    test("prepares comprehensive request payload with all parameters", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "comprehensive query",
            totalResults: 0,
            limit: 20,
            offset: 10,
            threshold: 0.8,
            timing: {
              queryEmbeddingMs: 75,
              vectorSearchMs: 200,
              totalMs: 275,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const filters: VectorSearchFilters = {
        domain: "example.com",
        repository: "test-repo",
        repositoryOrg: "test-org",
        contentType: "readme",
        dateRange: {
          from: "2024-01-01",
          to: "2024-12-31",
        },
      };

      const request: VectorSearchRequest = {
        query: "comprehensive query",
        limit: 20,
        offset: 10,
        threshold: 0.8,
        includeContent: true,
        filters,
        origin: "test-origin",
        integration: "test-integration",
      };

      await vectorSearch(mockHttpClient, request);

      expect(mockHttpClient.post).toHaveBeenCalledWith("/v2/vector-search", {
        query: "comprehensive query",
        limit: 20,
        offset: 10,
        threshold: 0.8,
        includeContent: true,
        filters,
        origin: "test-origin",
        integration: "test-integration",
      });
    });

    test("trims whitespace from query, origin, and integration", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "trimmed query",
            totalResults: 0,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 30,
              vectorSearchMs: 80,
              totalMs: 110,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "  trimmed query  ",
        origin: "  test-origin  ",
        integration: "  test-integration  ",
      };

      await vectorSearch(mockHttpClient, request);

      expect(mockHttpClient.post).toHaveBeenCalledWith("/v2/vector-search", {
        query: "trimmed query",
        origin: "test-origin",
        integration: "test-integration",
      });
    });

    test("excludes undefined and null optional parameters", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "minimal query",
            totalResults: 0,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 25,
              vectorSearchMs: 60,
              totalMs: 85,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "minimal query",
        limit: undefined,
        offset: undefined,
        threshold: undefined,
        includeContent: undefined,
        filters: undefined,
        origin: undefined,
        integration: undefined,
      };

      await vectorSearch(mockHttpClient, request);

      expect(mockHttpClient.post).toHaveBeenCalledWith("/v2/vector-search", {
        query: "minimal query",
      });
    });
  });

  describe("Input Validation", () => {
    test("throws error for empty query", async () => {
      const request: VectorSearchRequest = {
        query: "",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Query cannot be empty");
    });

    test("throws error for whitespace-only query", async () => {
      const request: VectorSearchRequest = {
        query: "   ",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Query cannot be empty");
    });

    test("throws error for invalid limit values", async () => {
      const request1: VectorSearchRequest = {
        query: "test",
        limit: 0,
      };

      const request2: VectorSearchRequest = {
        query: "test",
        limit: 101,
      };

      const request3: VectorSearchRequest = {
        query: "test",
        limit: -5,
      };

      await expect(vectorSearch(mockHttpClient, request1)).rejects.toThrow("Limit must be between 1 and 100");
      await expect(vectorSearch(mockHttpClient, request2)).rejects.toThrow("Limit must be between 1 and 100");
      await expect(vectorSearch(mockHttpClient, request3)).rejects.toThrow("Limit must be between 1 and 100");
    });

    test("throws error for negative offset", async () => {
      const request: VectorSearchRequest = {
        query: "test",
        offset: -1,
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Offset must be non-negative");
    });

    test("throws error for invalid threshold values", async () => {
      const request1: VectorSearchRequest = {
        query: "test",
        threshold: -0.1,
      };

      const request2: VectorSearchRequest = {
        query: "test",
        threshold: 1.1,
      };

      await expect(vectorSearch(mockHttpClient, request1)).rejects.toThrow("Threshold must be between 0 and 1");
      await expect(vectorSearch(mockHttpClient, request2)).rejects.toThrow("Threshold must be between 0 and 1");
    });

    test("accepts valid boundary values", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "test",
            totalResults: 0,
            limit: 1,
            offset: 0,
            threshold: 0,
            timing: {
              queryEmbeddingMs: 20,
              vectorSearchMs: 50,
              totalMs: 70,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const validRequests: VectorSearchRequest[] = [
        { query: "test", limit: 1 },
        { query: "test", limit: 100 },
        { query: "test", offset: 0 },
        { query: "test", threshold: 0 },
        { query: "test", threshold: 1 },
      ];

      for (const request of validRequests) {
        await expect(vectorSearch(mockHttpClient, request)).resolves.toBeDefined();
      }
    });
  });

  describe("HTTP Response Handling", () => {
    test("handles successful response with results", async () => {
      const mockResults: VectorSearchResult[] = [
        {
          id: "result1",
          url: "https://example.com/doc1",
          title: "Test Document 1",
          content: "This is test content",
          similarity: 0.95,
          metadata: {
            sourceURL: "https://example.com/doc1",
            scrapedAt: "2024-01-01T00:00:00Z",
            domain: "example.com",
            repositoryName: "test-repo",
            repositoryOrg: "test-org",
            language: "en",
            contentType: "readme",
            wordCount: 150,
            lastModified: "2023-12-31T23:59:59Z",
          },
        },
        {
          id: "result2",
          url: "https://example.com/doc2",
          title: "Test Document 2",
          similarity: 0.88,
          metadata: {
            sourceURL: "https://example.com/doc2",
            scrapedAt: "2024-01-01T00:00:00Z",
            domain: "example.com",
            wordCount: 200,
          },
        },
      ];

      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: mockResults,
            query: "test query",
            totalResults: 2,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 45,
              vectorSearchMs: 120,
              totalMs: 165,
            },
          },
          creditsUsed: 3,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "test query",
      };

      const result = await vectorSearch(mockHttpClient, request);

      expect(result).toEqual(mockResponse.data);
      expect(result.data?.results).toHaveLength(2);
      expect(result.data?.results[0].similarity).toBe(0.95);
      expect(result.data?.timing.totalMs).toBe(165);
    });

    test("handles successful response with no results", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "no matches query",
            totalResults: 0,
            limit: 10,
            offset: 0,
            threshold: 0.9,
            timing: {
              queryEmbeddingMs: 30,
              vectorSearchMs: 50,
              totalMs: 80,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "no matches query",
        threshold: 0.9,
      };

      const result = await vectorSearch(mockHttpClient, request);

      expect(result).toEqual(mockResponse.data);
      expect(result.data?.results).toHaveLength(0);
      expect(result.data?.totalResults).toBe(0);
    });

    test("calls throwForBadResponse for unsuccessful response status", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 400,
        data: {
          success: false,
          error: "Bad request",
        },
        statusText: "Bad Request",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);
      mockedThrowForBadResponse.mockImplementation(() => {
        throw new Error("Bad request");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Bad request");
      expect(mockedThrowForBadResponse).toHaveBeenCalledWith(mockResponse, "vector-search");
    });

    test("calls throwForBadResponse for unsuccessful response data", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: false,
          error: "Vector storage disabled",
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);
      mockedThrowForBadResponse.mockImplementation(() => {
        throw new Error("Vector storage disabled");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Vector storage disabled");
      expect(mockedThrowForBadResponse).toHaveBeenCalledWith(mockResponse, "vector-search");
    });
  });

  describe("Error Handling", () => {
    test("calls normalizeAxiosError for axios errors", async () => {
      const axiosError: any = {
        isAxiosError: true,
        message: "Network Error",
        code: "ECONNREFUSED",
        response: {
          status: 500,
          data: { error: "Internal server error" },
        },
      };

      mockHttpClient.post.mockRejectedValue(axiosError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("Network Error");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Network Error");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(axiosError, "vector-search");
    });

    test("re-throws non-axios errors directly", async () => {
      const customError = new Error("Custom error");
      
      mockHttpClient.post.mockRejectedValue(customError);

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Custom error");
      expect(mockedNormalizeAxiosError).not.toHaveBeenCalled();
    });

    test("handles timeout errors", async () => {
      const timeoutError: any = {
        isAxiosError: true,
        code: "ECONNABORTED",
        message: "timeout of 60000ms exceeded",
      };

      mockHttpClient.post.mockRejectedValue(timeoutError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("Request timeout");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Request timeout");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(timeoutError, "vector-search");
    });

    test("handles rate limit errors", async () => {
      const rateLimitError: any = {
        isAxiosError: true,
        response: {
          status: 429,
          data: { error: "Rate limit exceeded" },
        },
      };

      mockHttpClient.post.mockRejectedValue(rateLimitError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("Rate limit exceeded");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Rate limit exceeded");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(rateLimitError, "vector-search");
    });

    test("handles authentication errors", async () => {
      const authError: any = {
        isAxiosError: true,
        response: {
          status: 401,
          data: { error: "Invalid API key" },
        },
      };

      mockHttpClient.post.mockRejectedValue(authError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("Invalid API key");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Invalid API key");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(authError, "vector-search");
    });
  });

  describe("Edge Cases and Network Failures", () => {
    test("handles malformed response data", async () => {
      const mockResponse: AxiosResponse = {
        status: 200,
        data: null,
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);
      mockedThrowForBadResponse.mockImplementation(() => {
        throw new Error("Invalid response format");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Invalid response format");
      expect(mockedThrowForBadResponse).toHaveBeenCalledWith(mockResponse, "vector-search");
    });

    test("handles empty response body", async () => {
      const mockResponse: AxiosResponse = {
        status: 200,
        data: undefined,
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);
      mockedThrowForBadResponse.mockImplementation(() => {
        throw new Error("Empty response");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Empty response");
      expect(mockedThrowForBadResponse).toHaveBeenCalledWith(mockResponse, "vector-search");
    });

    test("handles connection refused errors", async () => {
      const connectionError: any = {
        isAxiosError: true,
        code: "ECONNREFUSED",
        message: "connect ECONNREFUSED 127.0.0.1:3000",
      };

      mockHttpClient.post.mockRejectedValue(connectionError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("Connection refused");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Connection refused");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(connectionError, "vector-search");
    });

    test("handles DNS resolution errors", async () => {
      const dnsError: any = {
        isAxiosError: true,
        code: "ENOTFOUND",
        message: "getaddrinfo ENOTFOUND invalid-domain.com",
      };

      mockHttpClient.post.mockRejectedValue(dnsError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("DNS resolution failed");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("DNS resolution failed");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(dnsError, "vector-search");
    });

    test("handles server errors with vector storage issues", async () => {
      const serverError: any = {
        isAxiosError: true,
        response: {
          status: 500,
          data: { 
            error: "Vector storage service unavailable",
            details: "TEI service connection failed",
          },
        },
      };

      mockHttpClient.post.mockRejectedValue(serverError);
      mockedNormalizeAxiosError.mockImplementation(() => {
        throw new Error("Vector storage service unavailable");
      });

      const request: VectorSearchRequest = {
        query: "test query",
      };

      await expect(vectorSearch(mockHttpClient, request)).rejects.toThrow("Vector storage service unavailable");
      expect(mockedNormalizeAxiosError).toHaveBeenCalledWith(serverError, "vector-search");
    });
  });

  describe("Authentication and Headers", () => {
    test("uses correct endpoint path", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "test",
            totalResults: 0,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 20,
              vectorSearchMs: 40,
              totalMs: 60,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "test",
      };

      await vectorSearch(mockHttpClient, request);

      expect(mockHttpClient.post).toHaveBeenCalledWith(
        "/v2/vector-search",
        expect.any(Object)
      );
    });

    test("HTTP client automatically handles authentication headers", async () => {
      // The HttpClient itself handles authentication headers in its constructor
      // This test verifies that the method doesn't interfere with that
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [],
            query: "test",
            totalResults: 0,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 15,
              vectorSearchMs: 35,
              totalMs: 50,
            },
          },
          creditsUsed: 1,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "test",
      };

      await vectorSearch(mockHttpClient, request);

      // Verify no additional headers are being passed
      expect(mockHttpClient.post).toHaveBeenCalledWith(
        "/v2/vector-search",
        expect.any(Object)
        // Third parameter (headers) should be undefined since auth is handled by HttpClient
      );
    });
  });

  describe("Type Safety and Response Parsing", () => {
    test("properly types response data structure", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [
              {
                id: "test-id",
                url: "https://example.com",
                title: "Test Title",
                content: "Test content",
                similarity: 0.95,
                metadata: {
                  sourceURL: "https://example.com",
                  scrapedAt: "2024-01-01T00:00:00Z",
                  domain: "example.com",
                  wordCount: 100,
                },
              },
            ],
            query: "test query",
            totalResults: 1,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 25,
              vectorSearchMs: 75,
              totalMs: 100,
            },
          },
          creditsUsed: 2,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "test query",
      };

      const result = await vectorSearch(mockHttpClient, request);

      // TypeScript should properly infer types
      expect(result.success).toBe(true);
      expect(result.data?.results).toBeDefined();
      expect(result.data?.results[0].similarity).toBe(0.95);
      expect(result.data?.timing.totalMs).toBe(100);
      expect(result.creditsUsed).toBe(2);
    });

    test("handles response with optional fields missing", async () => {
      const mockResponse: AxiosResponse<VectorSearchResponse> = {
        status: 200,
        data: {
          success: true,
          data: {
            results: [
              {
                id: "minimal-result",
                url: "https://example.com/minimal",
                similarity: 0.8,
                metadata: {
                  sourceURL: "https://example.com/minimal",
                  scrapedAt: "2024-01-01T00:00:00Z",
                },
                // title and content are optional
              },
            ],
            query: "minimal query",
            totalResults: 1,
            limit: 10,
            offset: 0,
            threshold: 0.7,
            timing: {
              queryEmbeddingMs: 20,
              vectorSearchMs: 60,
              totalMs: 80,
            },
          },
          creditsUsed: 2,
        },
        statusText: "OK",
        headers: {},
        config: {} as any,
      };

      mockHttpClient.post.mockResolvedValue(mockResponse);

      const request: VectorSearchRequest = {
        query: "minimal query",
      };

      const result = await vectorSearch(mockHttpClient, request);

      expect(result.data?.results[0].title).toBeUndefined();
      expect(result.data?.results[0].content).toBeUndefined();
      expect(result.data?.results[0].url).toBe("https://example.com/minimal");
      expect(result.data?.results[0].similarity).toBe(0.8);
    });
  });
});