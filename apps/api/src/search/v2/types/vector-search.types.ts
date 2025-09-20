/**
 * Type definitions for vector search functionality
 */

export interface VectorSearchServiceOptions {
  logger?: any;
  costTracking?: any;
  teamId: string;
  thresholdProvided?: boolean;
}

export interface VectorSearchTiming {
  queryEmbeddingMs: number;
  vectorSearchMs: number;
  totalMs: number;
}

export interface ThresholdSelectionResult {
  threshold: number;
  candidates: number[];
  fallbackUsed: boolean;
}

export interface QueryEmbeddingResult {
  embedding: number[];
  duration: number;
  model: string;
  provider?: string;
}

export interface SearchExecutionResult {
  results: any[];
  threshold: number;
  timing: number;
}

export interface TransformedSearchResult {
  id: string;
  url: string;
  title: string;
  similarity: number;
  content?: string;
  metadata: {
    sourceURL: string;
    scrapedAt: string;
    domain?: string;
    repositoryName?: string;
    repositoryOrg?: string;
    filePath?: string;
    contentType?: string;
    approxWordCount?: number;
  };
}
