import { Pool } from "pg";
import { logger } from "../lib/logger";
import { Document } from "../controllers/v2/types";

// Use existing NuQ database connection
const nuqPool = new Pool({
  connectionString: process.env.NUQ_DATABASE_URL,
  application_name: "vector_storage",
});

nuqPool.on("error", err =>
  logger.error("Error in Vector Storage idle client", { err, module: "vector_storage" }),
);

// Vector storage configuration
const VECTOR_DIMENSION = parseInt(process.env.VECTOR_DIMENSION || "384", 10);
const ENABLE_VECTOR_STORAGE = process.env.ENABLE_VECTOR_STORAGE === "true";
const MIN_SIMILARITY_THRESHOLD = parseFloat(process.env.MIN_SIMILARITY_THRESHOLD || "0.7");

// Types for vector operations
export interface VectorMetadata {
  title?: string;
  url?: string;
  domain?: string;
  repository_name?: string;
  repository_org?: string;
  file_path?: string;
  content_type?: string;
  language?: string;
  created_at?: string;
  token_count?: number;
  description?: string;
}

export interface VectorSearchOptions {
  limit?: number;
  minSimilarity?: number;
  domain?: string;
  repositoryName?: string;
  contentType?: string;
  dateRange?: {
    start?: string;
    end?: string;
  };
}

export interface VectorSearchResult {
  jobId: string;
  similarity: number;
  metadata: VectorMetadata;
  content: string;
  document?: Document;
}

export interface VectorStorageStats {
  totalVectors: number;
  avgSimilarity: number;
  uniqueDomains: number;
  uniqueRepositories: number;
}

/**
 * Extracts GitHub repository information from URL
 */
export function extractGitHubInfo(url: string): {
  org?: string;
  repo?: string;
  filePath?: string;
} {
  const githubMatch = url.match(/github\.com\/([^\/]+)\/([^\/]+)(?:\/(?:blob|tree)\/[^\/]+\/(.*)?)?/);
  if (!githubMatch) return {};

  const [, org, repo, filePath] = githubMatch;
  return {
    org: org || undefined,
    repo: repo?.replace(/\.git$/, "") || undefined,
    filePath: filePath || undefined,
  };
}

/**
 * Detects content type from URL and title
 */
export function detectContentType(url: string, title?: string, content?: string): string {
  const urlLower = url.toLowerCase();
  const titleLower = title?.toLowerCase() || "";
  const contentLower = content?.substring(0, 1000).toLowerCase() || "";

  // API documentation
  if (
    urlLower.includes("/api/") ||
    urlLower.includes("/docs/api") ||
    titleLower.includes("api") ||
    contentLower.includes("endpoint") ||
    contentLower.includes("api reference")
  ) {
    return "api_docs";
  }

  // README files
  if (
    urlLower.includes("readme") ||
    titleLower.includes("readme") ||
    urlLower.endsWith("/") && titleLower.includes("readme")
  ) {
    return "readme";
  }

  // Tutorial/Guide content
  if (
    urlLower.includes("tutorial") ||
    urlLower.includes("guide") ||
    urlLower.includes("getting-started") ||
    titleLower.includes("tutorial") ||
    titleLower.includes("guide") ||
    titleLower.includes("getting started")
  ) {
    return "tutorial";
  }

  // Configuration/Setup
  if (
    urlLower.includes("config") ||
    urlLower.includes("setup") ||
    urlLower.includes("install") ||
    titleLower.includes("config") ||
    titleLower.includes("setup") ||
    titleLower.includes("install")
  ) {
    return "configuration";
  }

  // Blog posts
  if (
    urlLower.includes("/blog/") ||
    urlLower.includes("/post/") ||
    urlLower.includes("/articles/")
  ) {
    return "blog";
  }

  // Documentation (default for docs sites)
  if (urlLower.includes("/docs/") || urlLower.includes("documentation")) {
    return "documentation";
  }

  return "general";
}

/**
 * Extracts domain from URL
 */
export function extractDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "unknown";
  }
}

/**
 * Generates metadata from document
 */
export function generateMetadata(document: Document): VectorMetadata {
  const url = document.url || document.metadata?.url || "";
  const domain = extractDomain(url);
  const githubInfo = extractGitHubInfo(url);
  const contentType = detectContentType(
    url, 
    document.title || document.metadata?.title,
    document.markdown
  );

  // Estimate token count (rough approximation: 4 characters per token)
  const content = document.markdown || document.html || "";
  const tokenCount = Math.ceil(content.length / 4);

  return {
    title: document.title || document.metadata?.title,
    url,
    domain,
    repository_name: githubInfo.repo,
    repository_org: githubInfo.org,
    file_path: githubInfo.filePath,
    content_type: contentType,
    language: document.metadata?.language,
    created_at: new Date().toISOString(),
    token_count: tokenCount,
    description: document.description || document.metadata?.description,
  };
}

/**
 * Stores document embedding with metadata in PostgreSQL
 */
export async function storeDocumentVector(
  jobId: string,
  embedding: number[],
  document: Document,
  _logger = logger,
): Promise<boolean> {
  if (!ENABLE_VECTOR_STORAGE) {
    _logger.debug("Vector storage disabled, skipping", { 
      module: "vector_storage", 
      jobId 
    });
    return true;
  }

  if (!embedding || embedding.length !== VECTOR_DIMENSION) {
    throw new Error(`Invalid embedding dimension: expected ${VECTOR_DIMENSION}, got ${embedding?.length || 0}`);
  }

  const start = Date.now();
  const metadata = generateMetadata(document);
  const content = document.markdown || document.html || "";

  try {
    const query = `
      INSERT INTO nuq.document_vectors (
        job_id, 
        content_vector, 
        metadata, 
        content, 
        created_at
      ) VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (job_id) 
      DO UPDATE SET 
        content_vector = EXCLUDED.content_vector,
        metadata = EXCLUDED.metadata,
        content = EXCLUDED.content,
        created_at = EXCLUDED.created_at
    `;

    await nuqPool.query(query, [
      jobId,
      `[${embedding.join(",")}]`, // Convert array to vector format
      JSON.stringify(metadata),
      content.substring(0, 50000), // Limit content size
      metadata.created_at,
    ]);

    _logger.info("Vector stored successfully", {
      module: "vector_storage/metrics",
      method: "storeDocumentVector",
      duration: Date.now() - start,
      jobId,
      vectorDimension: embedding.length,
      contentLength: content.length,
      domain: metadata.domain,
      contentType: metadata.content_type,
    });

    return true;
  } catch (error) {
    _logger.error("Failed to store document vector", {
      module: "vector_storage",
      method: "storeDocumentVector",
      error: error instanceof Error ? error.message : String(error),
      jobId,
      duration: Date.now() - start,
    });
    throw error;
  }
}

/**
 * Searches for similar vectors using cosine similarity
 */
export async function searchSimilarVectors(
  queryEmbedding: number[],
  options: VectorSearchOptions = {},
  _logger = logger,
): Promise<VectorSearchResult[]> {
  if (!ENABLE_VECTOR_STORAGE) {
    _logger.debug("Vector storage disabled, returning empty results", { 
      module: "vector_storage" 
    });
    return [];
  }

  if (!queryEmbedding || queryEmbedding.length !== VECTOR_DIMENSION) {
    throw new Error(`Invalid query embedding dimension: expected ${VECTOR_DIMENSION}, got ${queryEmbedding?.length || 0}`);
  }

  const start = Date.now();
  const {
    limit = 10,
    minSimilarity = MIN_SIMILARITY_THRESHOLD,
    domain,
    repositoryName,
    contentType,
    dateRange,
  } = options;

  try {
    // Build dynamic WHERE clause for filtering
    const conditions: string[] = [];
    const params: any[] = [`[${queryEmbedding.join(",")}]`, minSimilarity, limit];
    let paramIndex = 4;

    if (domain) {
      conditions.push(`(metadata->>'domain') = $${paramIndex}`);
      params.push(domain);
      paramIndex++;
    }

    if (repositoryName) {
      conditions.push(`(metadata->>'repository_name') = $${paramIndex}`);
      params.push(repositoryName);
      paramIndex++;
    }

    if (contentType) {
      conditions.push(`(metadata->>'content_type') = $${paramIndex}`);
      params.push(contentType);
      paramIndex++;
    }

    if (dateRange?.start) {
      conditions.push(`(metadata->>'created_at')::timestamp >= $${paramIndex}::timestamp`);
      params.push(dateRange.start);
      paramIndex++;
    }

    if (dateRange?.end) {
      conditions.push(`(metadata->>'created_at')::timestamp <= $${paramIndex}::timestamp`);
      params.push(dateRange.end);
      paramIndex++;
    }

    const whereClause = conditions.length > 0 ? `AND ${conditions.join(" AND ")}` : "";

    const query = `
      SELECT 
        job_id,
        1 - (content_vector <=> $1::vector) as similarity,
        metadata,
        content
      FROM nuq.document_vectors
      WHERE (1 - (content_vector <=> $1::vector)) >= $2
      ${whereClause}
      ORDER BY content_vector <=> $1::vector
      LIMIT $3
    `;

    const result = await nuqPool.query(query, params);

    const searchResults: VectorSearchResult[] = result.rows.map(row => ({
      jobId: row.job_id,
      similarity: parseFloat(row.similarity.toFixed(4)),
      metadata: row.metadata as VectorMetadata,
      content: row.content,
    }));

    _logger.info("Vector search completed", {
      module: "vector_storage/metrics",
      method: "searchSimilarVectors",
      duration: Date.now() - start,
      resultsCount: searchResults.length,
      minSimilarity,
      filters: { domain, repositoryName, contentType, dateRange },
    });

    return searchResults;
  } catch (error) {
    _logger.error("Failed to search similar vectors", {
      module: "vector_storage",
      method: "searchSimilarVectors",
      error: error instanceof Error ? error.message : String(error),
      duration: Date.now() - start,
    });
    throw error;
  }
}

/**
 * Retrieves vector storage statistics
 */
export async function getVectorStorageStats(_logger = logger): Promise<VectorStorageStats> {
  const start = Date.now();

  try {
    const query = `
      SELECT 
        COUNT(*) as total_vectors,
        COUNT(DISTINCT (metadata->>'domain')) as unique_domains,
        COUNT(DISTINCT (metadata->>'repository_name')) as unique_repositories
      FROM nuq.document_vectors
      WHERE metadata->>'repository_name' IS NOT NULL
    `;

    const result = await nuqPool.query(query);
    const row = result.rows[0];

    const stats: VectorStorageStats = {
      totalVectors: parseInt(row.total_vectors, 10),
      avgSimilarity: 0, // Would need a reference query to calculate
      uniqueDomains: parseInt(row.unique_domains, 10),
      uniqueRepositories: parseInt(row.unique_repositories, 10),
    };

    _logger.info("Vector storage stats retrieved", {
      module: "vector_storage/metrics",
      method: "getVectorStorageStats",
      duration: Date.now() - start,
      stats,
    });

    return stats;
  } catch (error) {
    _logger.error("Failed to retrieve vector storage stats", {
      module: "vector_storage",
      method: "getVectorStorageStats",
      error: error instanceof Error ? error.message : String(error),
      duration: Date.now() - start,
    });
    throw error;
  }
}

/**
 * Deletes a document vector by job ID
 */
export async function deleteDocumentVector(
  jobId: string,
  _logger = logger,
): Promise<boolean> {
  const start = Date.now();

  try {
    const query = `DELETE FROM nuq.document_vectors WHERE job_id = $1`;
    const result = await nuqPool.query(query, [jobId]);

    const deleted = (result.rowCount || 0) > 0;

    _logger.info("Vector deletion completed", {
      module: "vector_storage/metrics",
      method: "deleteDocumentVector",
      duration: Date.now() - start,
      jobId,
      deleted,
    });

    return deleted;
  } catch (error) {
    _logger.error("Failed to delete document vector", {
      module: "vector_storage",
      method: "deleteDocumentVector",
      error: error instanceof Error ? error.message : String(error),
      jobId,
      duration: Date.now() - start,
    });
    throw error;
  }
}

/**
 * Health check for vector storage service
 */
export async function vectorStorageHealthCheck(): Promise<boolean> {
  const start = Date.now();
  try {
    // Check if table exists and is accessible
    await nuqPool.query("SELECT 1 FROM nuq.document_vectors LIMIT 1");
    
    logger.info("Vector storage health check passed", {
      module: "vector_storage/metrics",
      method: "vectorStorageHealthCheck",
      duration: Date.now() - start,
    });
    
    return true;
  } catch (error) {
    logger.error("Vector storage health check failed", {
      module: "vector_storage",
      method: "vectorStorageHealthCheck",
      error: error instanceof Error ? error.message : String(error),
      duration: Date.now() - start,
    });
    return false;
  }
}

/**
 * Batch delete vectors older than specified days
 */
export async function cleanupOldVectors(
  retentionDays: number = 30,
  _logger = logger,
): Promise<number> {
  const start = Date.now();

  try {
    const query = `
      DELETE FROM nuq.document_vectors 
      WHERE (metadata->>'created_at')::timestamp < now() - interval '${retentionDays} days'
    `;

    const result = await nuqPool.query(query);
    const deletedCount = result.rowCount || 0;

    _logger.info("Vector cleanup completed", {
      module: "vector_storage/metrics",
      method: "cleanupOldVectors",
      duration: Date.now() - start,
      retentionDays,
      deletedCount,
    });

    return deletedCount;
  } catch (error) {
    _logger.error("Failed to cleanup old vectors", {
      module: "vector_storage",
      method: "cleanupOldVectors",
      error: error instanceof Error ? error.message : String(error),
      duration: Date.now() - start,
    });
    throw error;
  }
}

/**
 * Graceful shutdown for vector storage service
 */
export async function vectorStorageShutdown(): Promise<void> {
  logger.info("Shutting down vector storage service", { module: "vector_storage" });
  await nuqPool.end();
}