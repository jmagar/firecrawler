import { hasFormatOfType } from "./format-utils";
import { FormatObject } from "../controllers/v2/types";

/**
 * Checks if embeddings should be generated based on configuration and format options
 * Centralized logic to avoid duplication across multiple files
 */
export function shouldGenerateEmbeddings(formats?: FormatObject[]): boolean {
  const enableVectorStorage = isVectorStorageEnabled();

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
  return process.env.ENABLE_VECTOR_STORAGE !== "false";
}

/**
 * Gets the configured vector dimension with validation
 */
export function getVectorDimension(): number {
  const vectorDimension = process.env.VECTOR_DIMENSION;
  if (!vectorDimension) {
    throw new Error(
      "VECTOR_DIMENSION environment variable is required. Set it to match your embedding model's output dimension (e.g., 1024 for Qwen/Qwen2.5-0.5B-Instruct, 384 for all-MiniLM-L6-v2).",
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
  // OpenAI models - dimensions from OpenAI documentation
  "text-embedding-ada-002": 1536,
  "text-embedding-3-small": 1536,
  "text-embedding-3-large": 3072,

  // Sentence Transformers models - dimensions verified from HuggingFace model cards
  "sentence-transformers/all-MiniLM-L6-v2": 384,
  "sentence-transformers/all-MiniLM-L12-v2": 384,

  // BGE models - dimensions verified from HuggingFace model cards
  "BAAI/bge-m3": 1024,
  "BAAI/bge-large-en-v1.5": 1024,
  "BAAI/bge-base-en-v1.5": 768,
  "BAAI/bge-small-en-v1.5": 384,

  // Nomic models - dimensions verified from HuggingFace model cards
  "nomic-ai/nomic-embed-text-v1": 768,
  "nomic-ai/nomic-embed-text-v1.5": 768,

  // GTE models - dimensions verified from HuggingFace model cards
  "thenlper/gte-large": 1024,
  "thenlper/gte-base": 768,
  "thenlper/gte-small": 384,

  // Qwen models - dimensions verified from HuggingFace model cards
  "Qwen/Qwen3-Embedding-0.6B": 1024,
  "Qwen/Qwen2.5-0.5B-Instruct": 1024,
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
    const knownDimension =
      KNOWN_MODEL_DIMENSIONS[modelName] ??
      KNOWN_MODEL_DIMENSIONS[modelName.toLowerCase?.() ?? modelName];
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

  // If MODEL_EMBEDDING_NAME is not set, select a sensible default based on available creds
  if (!modelName) {
    if (!openaiKey && !teiUrl) {
      throw new Error(
        "Either MODEL_EMBEDDING_NAME or one of OPENAI_API_KEY/TEI_URL must be set.",
      );
    }
    // Prefer OpenAI when its key is present; otherwise TEI
  }

  // Determine provider based on MODEL_EMBEDDING_NAME
  const rawName = modelName?.trim();
  const normalizedModelName =
    rawName && rawName.length > 0 ? rawName : undefined;

  // Explicitly detect OpenAI models by their naming pattern
  const isOpenAIModel =
    normalizedModelName?.startsWith("text-embedding-") ?? false;

  // Default provider inference when model name is absent:
  let provider: "tei" | undefined =
    !modelName && teiUrl && !openaiKey ? "tei" : undefined;

  if (normalizedModelName) {
    if (isOpenAIModel) {
      // OpenAI model - provider remains undefined for OpenAI
      provider = undefined;
    } else {
      // Non-OpenAI model
      if (teiUrl) {
        provider = "tei";
      } else {
        const hintDim =
          (normalizedModelName &&
            KNOWN_MODEL_DIMENSIONS[normalizedModelName]) ||
          "<your model dimension>";
        throw new Error(
          `Non-OpenAI embedding model '${normalizedModelName}' requires TEI_URL to be configured.\n\nFor TEI (self-hosted):\nTEI_URL=http://your-tei-service:8080\nMODEL_EMBEDDING_NAME=${normalizedModelName}\nVECTOR_DIMENSION=${hintDim}\n\nAlternatively, use an OpenAI model:\nOPENAI_API_KEY=your_key_here\nMODEL_EMBEDDING_NAME=text-embedding-3-small\nVECTOR_DIMENSION=1536`,
        );
      }
    }
  }

  // Use configured model or fall back to appropriate defaults
  let finalModelName: string;
  if (normalizedModelName) {
    finalModelName = normalizedModelName;
  } else {
    // Default selection based on provider availability
    if (provider === "tei") {
      finalModelName = "Qwen/Qwen3-Embedding-0.6B";
    } else {
      finalModelName = "Qwen/Qwen3-Embedding-0.6B";
    }
  }

  return { modelName: finalModelName, provider };
}
