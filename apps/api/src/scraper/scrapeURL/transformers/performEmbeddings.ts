import { embed } from "ai";
import { Document } from "../../../controllers/v2/types";
import { Meta } from "..";
import { logger } from "../../../lib/logger";
import { getEmbeddingModel } from "../../../lib/generic-ai";
import { hasFormatOfType } from "../../../lib/format-utils";
import { storeDocumentVector } from "../../../services/vector-storage";
import { extractDocumentMetadata, formatMetadataForStorage } from "../../../lib/metadata-extraction";
import { calculateEmbeddingCost } from "../../../lib/extract/usage/llm-cost";

export class EmbeddingGenerationError extends Error {
  public embeddings: boolean = true;
  
  constructor(message: string, public originalError?: Error) {
    super(`Embedding generation failed: ${message}`);
    this.name = "EmbeddingGenerationError";
  }
}

/**
 * Generates embeddings for document content and stores them in vector database
 * following the established AI transformer patterns from performLLMExtract.ts
 */
export async function performEmbeddings(
  meta: Meta,
  document: Document,
): Promise<Document> {
  // Check if embeddings format is requested
  const hasEmbeddings = hasFormatOfType(meta.options.formats, "embeddings");
  if (!hasEmbeddings) {
    return document;
  }

  const start = Date.now();
  const _logger = meta.logger.child({
    method: "performEmbeddings",
    jobId: meta.id,
  });

  try {
    // Check for required content
    const content = document.markdown || document.html || document.rawHtml;
    if (!content || content.trim().length === 0) {
      _logger.warn("No content available for embedding generation", {
        hasMarkdown: !!document.markdown,
        hasHtml: !!document.html,
        hasRawHtml: !!document.rawHtml,
      });
      
      // Don't fail the entire scrape - just skip embeddings
      document.warning = "No content available for embedding generation." + 
        (document.warning ? " " + document.warning : "");
      return document;
    }

    // Check if vector storage is enabled
    const enableVectorStorage = process.env.ENABLE_VECTOR_STORAGE === "true";
    if (!enableVectorStorage) {
      _logger.debug("Vector storage disabled, skipping embedding generation");
      document.warning = "Vector storage is disabled." + 
        (document.warning ? " " + document.warning : "");
      return document;
    }

    // Determine embedding model and provider
    const modelName = process.env.MODEL_EMBEDDING_NAME;
    const provider = modelName && (
      modelName.startsWith("sentence-transformers/") || 
      modelName.startsWith("Qwen/") ||
      modelName.startsWith("BAAI/") ||
      modelName.startsWith("intfloat/")
    ) ? "tei" as const : undefined;
    
    const finalModelName = provider 
      ? modelName || "sentence-transformers/all-MiniLM-L6-v2"
      : "text-embedding-3-small";

    _logger.info("Generating embeddings", {
      model: finalModelName,
      provider: provider || "openai",
      contentLength: content.length,
      contentType: typeof content,
    });

    // Truncate content if it's too long (embedding models have token limits)
    const maxContentLength = parseInt(process.env.MAX_EMBEDDING_CONTENT_LENGTH || "50000", 10);
    const truncatedContent = content.length > maxContentLength 
      ? content.substring(0, maxContentLength)
      : content;

    if (content.length > maxContentLength) {
      _logger.warn("Content truncated for embedding generation", {
        originalLength: content.length,
        truncatedLength: truncatedContent.length,
        maxLength: maxContentLength,
      });
      
      document.warning = `Content was truncated to ${maxContentLength} characters for embedding generation.` + 
        (document.warning ? " " + document.warning : "");
    }

    // Generate embedding using AI SDK
    const embeddingStart = Date.now();
    const { embedding } = await embed({
      model: provider 
        ? getEmbeddingModel(finalModelName, provider)
        : getEmbeddingModel(finalModelName),
      value: truncatedContent,
      experimental_telemetry: {
        isEnabled: true,
        functionId: "performEmbeddings",
        metadata: {
          teamId: meta.internalOptions.teamId,
          scrapeId: meta.id,
          langfuseTraceId: "scrape:" + meta.id,
        },
      },
    });

    const embeddingDuration = Date.now() - embeddingStart;
    _logger.info("Embedding generated successfully", {
      duration: embeddingDuration,
      vectorDimension: embedding.length,
      model: finalModelName,
    });

    // Track embedding costs
    if (meta.costTracking) {
      const cost = calculateEmbeddingCost(finalModelName, truncatedContent);
      
      meta.costTracking.addCall({
        type: "other",
        metadata: {
          module: "scrapeURL",
          method: "performEmbeddings",
          model: finalModelName,
          provider: provider || "openai",
        },
        model: finalModelName,
        cost: cost,
        tokens: {
          input: Math.ceil(truncatedContent.length * 0.5), // Approximate token count
          output: 0, // Embeddings don't have output tokens
        },
      });

      _logger.debug("Embedding cost tracked", {
        cost: cost,
        estimatedTokens: Math.ceil(truncatedContent.length * 0.5),
      });
    }

    // Extract metadata for vector storage
    const documentMetadata = extractDocumentMetadata(
      document.url || document.metadata?.url || "",
      truncatedContent,
      document.title || document.metadata?.title
    );

    // Store vector in PostgreSQL if enabled
    try {
      const vectorStorageStart = Date.now();
      await storeDocumentVector(meta.id, embedding, document, _logger);
      const vectorStorageDuration = Date.now() - vectorStorageStart;

      _logger.info("Vector stored successfully", {
        duration: vectorStorageDuration,
        vectorDimension: embedding.length,
        metadata: formatMetadataForStorage(documentMetadata),
      });
    } catch (vectorError) {
      // Vector storage failure shouldn't break the scraping process
      _logger.error("Failed to store vector, continuing without vector storage", {
        error: vectorError instanceof Error ? vectorError.message : String(vectorError),
        vectorDimension: embedding.length,
      });
      
      document.warning = "Vector storage failed but embedding was generated." + 
        (document.warning ? " " + document.warning : "");
    }

    // Add embedding metadata to document (but don't include the actual vector)
    // The vector is stored in the database and retrieved via vector search APIs
    const embeddingMetadata = {
      generated: true,
      model: finalModelName,
      provider: provider || "openai",
      dimension: embedding.length,
      contentLength: truncatedContent.length,
      generatedAt: new Date().toISOString(),
      metadata: formatMetadataForStorage(documentMetadata),
    };

    // Add to document metadata
    document.metadata = {
      ...document.metadata,
      embeddings: embeddingMetadata,
    };

    _logger.info("Embedding generation completed successfully", {
      totalDuration: Date.now() - start,
      model: finalModelName,
      vectorDimension: embedding.length,
      vectorStored: true,
    });

    return document;

  } catch (error) {
    const duration = Date.now() - start;
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    _logger.error("Embedding generation failed", {
      error: errorMessage,
      duration,
      stack: error instanceof Error ? error.stack : undefined,
    });

    // Following the pattern from other AI transformers - don't fail the entire scrape
    // Just add a warning and continue
    document.warning = `Embedding generation failed: ${errorMessage}` + 
      (document.warning ? " " + document.warning : "");

    // For debugging purposes, you might want to throw in development
    if (process.env.NODE_ENV === "development") {
      throw new EmbeddingGenerationError(errorMessage, error instanceof Error ? error : undefined);
    }

    return document;
  }
}