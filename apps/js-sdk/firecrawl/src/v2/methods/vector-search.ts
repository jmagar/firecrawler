import { type VectorSearchRequest, type VectorSearchResponse } from "../types";
import { HttpClient } from "../utils/httpClient";
import { throwForBadResponse, normalizeAxiosError } from "../utils/errorHandler";

function prepareVectorSearchPayload(req: VectorSearchRequest): Record<string, unknown> {
  if (!req.query || !req.query.trim()) {
    throw new Error("Query cannot be empty");
  }
  if (req.limit != null && req.limit <= 0) {
    throw new Error("limit must be positive");
  }
  if (req.offset != null && req.offset < 0) {
    throw new Error("offset must be non-negative");
  }
  if (req.threshold != null && (req.threshold < 0 || req.threshold > 1)) {
    throw new Error("threshold must be between 0 and 1");
  }

  const payload: Record<string, unknown> = {
    query: req.query.trim(),
  };

  if (req.limit != null) payload.limit = req.limit;
  if (req.offset != null) payload.offset = req.offset;
  if (req.threshold != null) payload.threshold = req.threshold;
  if (req.includeContent != null) payload.includeContent = req.includeContent;
  if (req.filters != null) payload.filters = req.filters;
  if (req.origin != null && req.origin.trim()) payload.origin = req.origin.trim();
  if (req.integration != null && req.integration.trim()) payload.integration = req.integration.trim();

  return payload;
}

export async function vectorSearch(http: HttpClient, request: VectorSearchRequest): Promise<VectorSearchResponse> {
  const payload = prepareVectorSearchPayload(request);

  try {
    const res = await http.post<VectorSearchResponse>("/v2/vector-search", payload);
    if (res.status !== 200 || !res.data?.success) {
      throwForBadResponse(res, "vector search");
    }
    return res.data;
  } catch (err: any) {
    if (err?.isAxiosError) return normalizeAxiosError(err, "vector search");
    throw err;
  }
}