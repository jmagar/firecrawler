import { hasFormatOfType } from "./format-utils";
import { FormatObject } from "../controllers/v2/types";

/**
 * Checks if embeddings should be generated based on configuration and format options
 * Centralized logic to avoid duplication across multiple files
 */
export function shouldGenerateEmbeddings(formats?: FormatObject[]): boolean {
  const enableVectorStorage = process.env.ENABLE_VECTOR_STORAGE === "true";

  if (enableVectorStorage) {
    // If ENABLE_VECTOR_STORAGE=true, always generate embeddings regardless of format
    return true;
  }

  // Otherwise, only generate if explicitly requested via embeddings format
  return formats ? hasFormatOfType(formats, "embeddings") !== undefined : false;
}

/**
 * Checks if vector storage is enabled globally
 */
export function isVectorStorageEnabled(): boolean {
  return process.env.ENABLE_VECTOR_STORAGE === "true";
}

/**
 * Gets the configured vector dimension with validation
 */
export function getVectorDimension(): number {
  const vectorDimension = process.env.VECTOR_DIMENSION;
  if (!vectorDimension) {
    throw new Error(
      "VECTOR_DIMENSION environment variable is required when vector storage is enabled. Set it to match your embedding model's output dimension (e.g., 1024 for Qwen3-Embedding-0.6B, 384 for all-MiniLM-L6-v2).",
    );
  }

  const dimension = parseInt(vectorDimension, 10);
  if (isNaN(dimension) || dimension <= 0) {
    throw new Error(
      `VECTOR_DIMENSION must be a positive integer, got: ${vectorDimension}`,
    );
  }

  return dimension;
}

/**
 * Common embedding model dimensions for reference
 */
export const KNOWN_MODEL_DIMENSIONS: Record<string, number> = {
  "text-embedding-ada-002": 1536,
  "text-embedding-3-small": 1536,
  "text-embedding-3-large": 3072,
  "sentence-transformers/all-MiniLM-L6-v2": 384,
  "sentence-transformers/all-MiniLM-L12-v2": 384,
  "BAAI/bge-base-en-v1.5": 768,
  "BAAI/bge-large-en-v1.5": 1024,
  "Qwen/Qwen3-Embedding-0.6B": 1024,
};

/**
 * Validates that the embedding dimension matches the configured VECTOR_DIMENSION
 * and provides clear remediation guidance if there's a mismatch
 */
export function validateEmbeddingDimension(
  embedding: number[],
  modelName: string,
  provider?: string,
): void {
  const configuredDimension = getVectorDimension();
  const actualDimension = embedding.length;

  if (actualDimension !== configuredDimension) {
    const knownDimension = KNOWN_MODEL_DIMENSIONS[modelName];
    const providerInfo = provider ? ` (provider: ${provider})` : "";

    let remediation = "";
    if (knownDimension) {
      remediation = `\n\nTo fix this issue, update your environment variables:\nVECTOR_DIMENSION=${knownDimension}\nMODEL_EMBEDDING_NAME=${modelName}`;
    } else {
      remediation = `\n\nTo fix this issue, update your environment variables:\nVECTOR_DIMENSION=${actualDimension}\nMODEL_EMBEDDING_NAME=${modelName}`;
    }

    throw new Error(
      `Embedding dimension mismatch: expected ${configuredDimension} but got ${actualDimension} from model '${modelName}'${providerInfo}.${remediation}\n\nNote: If you have existing vectors in storage, you may need to recreate them with the new dimension.`,
    );
  }
}

/**
 * Validates model configuration and provides guidance for missing MODEL_EMBEDDING_NAME
 */
export function validateModelConfiguration(): {
  modelName: string;
  provider?: "tei";
} {
  const modelName = process.env.MODEL_EMBEDDING_NAME;
  const teiUrl = process.env.TEI_URL;
  const openaiKey = process.env.OPENAI_API_KEY;

  // If MODEL_EMBEDDING_NAME is not set, provide guidance
  if (!modelName) {
    if (teiUrl && !openaiKey) {
      throw new Error(
        "MODEL_EMBEDDING_NAME is required when using TEI. Set it to your TEI model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2').\n\nExample configuration:\nMODEL_EMBEDDING_NAME=sentence-transformers/all-MiniLM-L6-v2\nVECTOR_DIMENSION=384\nTEI_URL=" +
          teiUrl,
      );
    } else if (!openaiKey) {
      throw new Error(
        "Either MODEL_EMBEDDING_NAME or OPENAI_API_KEY must be set.\n\nFor OpenAI (recommended for getting started):\nOPENAI_API_KEY=your_key_here\nMODEL_EMBEDDING_NAME=text-embedding-3-small\nVECTOR_DIMENSION=1536\n\nFor TEI (self-hosted, recommended):\nTEI_URL=http://your-tei-service:8080\nMODEL_EMBEDDING_NAME=Qwen/Qwen3-Embedding-0.6B\nVECTOR_DIMENSION=1024",
      );
    }
  }

  // Determine provider based on MODEL_EMBEDDING_NAME
  const rawName = modelName?.trim();
  const normalizedModelName =
    rawName && rawName.length > 0 ? rawName : undefined;
  const provider = normalizedModelName
    ?.toLowerCase()
    .startsWith("sentence-transformers/")
    ? ("tei" as const)
    : undefined;

  // Use configured model or fall back to defaults
  const finalModelName = provider
    ? normalizedModelName || "sentence-transformers/all-MiniLM-L6-v2"
    : normalizedModelName || "text-embedding-3-small";

  return { modelName: finalModelName, provider };
}
