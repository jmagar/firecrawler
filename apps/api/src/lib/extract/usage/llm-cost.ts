import { TokenUsage } from "../../../controllers/v1/types";
import { logger } from "../../../lib/logger";
import { CostTracking } from "../../cost-tracking";
import { modelPrices } from "./model-prices";

interface ModelPricing {
  input_cost_per_token?: number;
  output_cost_per_token?: number;
  input_cost_per_request?: number;
  mode: string;
  output_vector_size?: number;
  litellm_provider?: string;
}
const tokenPerCharacter = 0.5;
const baseTokenCost = 300;
const MAX_PAYLOAD_BYTES = 1_000_000; // ~1MB limit to prevent JSON stringify blowups

// Language-specific token-to-character ratios
const languageTokenRatios = {
  // CJK languages (Chinese, Japanese, Korean) typically use more tokens per character
  zh: 1.2, // Chinese
  ja: 1.1, // Japanese
  ko: 1.0, // Korean
  // Latin scripts are more efficient
  en: 0.5, // English
  es: 0.5, // Spanish
  fr: 0.5, // French
  de: 0.5, // German
  it: 0.5, // Italian
  pt: 0.5, // Portuguese
  // Other scripts
  ar: 0.7, // Arabic
  ru: 0.6, // Russian (Cyrillic)
  hi: 0.8, // Hindi (Devanagari)
  th: 0.9, // Thai
} as const;

export type LanguageCode = keyof typeof languageTokenRatios;
export type TokenizerFunction = (text: string) => number;

// Language detection sample size - number of characters to analyze
const LANGUAGE_DETECT_SAMPLE_CHARS = 256;

/**
 * Simple language detection based on character scripts
 * Returns ISO 639-1 language code or undefined if unknown
 */
function detectLanguageFromText(text: string): string | undefined {
  if (!text || text.length < 10) return undefined;

  // Sample first LANGUAGE_DETECT_SAMPLE_CHARS characters for detection
  const sample = text.slice(0, LANGUAGE_DETECT_SAMPLE_CHARS);

  // Check for CJK characters
  if (/[\u4e00-\u9fff]/.test(sample)) return "zh"; // Chinese
  if (/[\u3040-\u309f\u30a0-\u30ff]/.test(sample)) return "ja"; // Japanese
  if (/[\uac00-\ud7af]/.test(sample)) return "ko"; // Korean

  // Check for other scripts
  if (/[\u0600-\u06ff]/.test(sample)) return "ar"; // Arabic
  if (/[\u0400-\u04ff]/.test(sample)) return "ru"; // Russian
  if (/[\u0900-\u097f]/.test(sample)) return "hi"; // Hindi
  if (/[\u0e00-\u0e7f]/.test(sample)) return "th"; // Thai

  // Default to English for Latin scripts
  return "en";
}

export function calculateThinkingCost(costTracking: CostTracking): number {
  return Math.ceil(costTracking.toJSON().totalCost * 20000);
}

/**
 * Estimate token count from text using language-aware heuristics or custom tokenizer
 */
function estimateTokenCount(
  text: string,
  options: {
    tokenizer?: TokenizerFunction;
    language?: string;
  } = {},
): number {
  // If a custom tokenizer is provided, use it
  if (options.tokenizer) {
    try {
      return options.tokenizer(text);
    } catch (error) {
      logger.warn("Custom tokenizer failed, falling back to heuristic", {
        error: error instanceof Error ? error.message : String(error),
        textLength: text.length,
        source: "llm-cost",
      });
    }
  }

  // Use language-specific ratio if language is provided or can be detected
  let language = options.language;
  if (!language) {
    language = detectLanguageFromText(text);
  }

  if (language) {
    const languageCode = language.toLowerCase().slice(0, 2) as LanguageCode;
    const ratio = languageTokenRatios[languageCode];
    if (ratio) {
      return Math.ceil(text.length * ratio);
    }
  }

  // Fall back to default heuristic
  return Math.ceil(text.length * tokenPerCharacter);
}

export function calculateFinalResultCost(
  data: any,
  options: {
    tokenizer?: TokenizerFunction;
    language?: string;
  } = {},
): number {
  let jsonString: string;

  try {
    // Attempt to stringify the data
    const rawJsonString = JSON.stringify(data);

    // Check if the JSON string exceeds our size limit
    if (rawJsonString.length > MAX_PAYLOAD_BYTES) {
      // Truncate to MAX_PAYLOAD_BYTES and append truncation marker
      jsonString = rawJsonString.slice(0, MAX_PAYLOAD_BYTES) + "...[truncated]";
      logger.warn(
        "Payload size exceeded limit, truncated for token estimation",
        {
          originalSize: rawJsonString.length,
          truncatedSize: jsonString.length,
          limit: MAX_PAYLOAD_BYTES,
          source: "llm-cost",
        },
      );
    } else {
      jsonString = rawJsonString;
    }
  } catch (error) {
    // Fall back to a safe string if JSON.stringify fails
    jsonString = "[payload too large]";
    logger.error(
      "Failed to stringify payload, using fallback for token estimation",
      {
        error: error instanceof Error ? error.message : String(error),
        source: "llm-cost",
      },
    );
  }

  const estimatedTokens = estimateTokenCount(jsonString, options);
  return Math.floor(estimatedTokens + baseTokenCost);
}

export function estimateTotalCost(tokenUsage: TokenUsage[]): number {
  return tokenUsage.reduce((total, usage) => {
    return total + estimateCost(usage);
  }, 0);
}

/**
 * Enhanced token estimation with language-aware heuristics
 * Exported for external use
 */
export function estimateTokens(
  text: string,
  options: {
    tokenizer?: TokenizerFunction;
    language?: string;
  } = {},
): number {
  return estimateTokenCount(text, options);
}

export function calculateEmbeddingCost(
  modelName: string,
  inputText: string,
  options: {
    tokenizer?: TokenizerFunction;
    language?: string;
  } = {},
): number {
  try {
    const pricing = modelPrices[modelName] as ModelPricing;

    if (!pricing) {
      logger.warn("No pricing information found for embedding model", {
        modelName,
        mode: "embedding",
        source: "llm-cost",
      });
      return 0;
    }

    if (pricing.mode !== "embedding") {
      logger.error("Model is not an embedding model", {
        modelName,
        actualMode: pricing.mode,
        expectedMode: "embedding",
        source: "llm-cost",
      });
      return 0;
    }

    // For TEI models (which are typically free/local), return 0
    if (pricing.litellm_provider === "tei") {
      return 0;
    }

    // Calculate cost based on input length using enhanced token estimation
    const approximateTokens = estimateTokenCount(inputText, options);

    let totalCost = 0;

    // Add per-request cost if applicable
    if (pricing.input_cost_per_request) {
      totalCost += pricing.input_cost_per_request;
    }

    // Add token-based input cost
    if (pricing.input_cost_per_token) {
      totalCost += approximateTokens * pricing.input_cost_per_token;
    }

    return Number(totalCost.toFixed(7));
  } catch (error) {
    logger.error("Error calculating embedding cost", {
      modelName,
      error: error instanceof Error ? error.message : String(error),
      source: "llm-cost",
    });
    return 0;
  }
}

function estimateCost(tokenUsage: TokenUsage): number {
  let totalCost = 0;
  try {
    let model = tokenUsage.model ?? (process.env.MODEL_NAME || "gpt-4o-mini");
    const pricing = modelPrices[model] as ModelPricing;

    if (!pricing) {
      logger.warn("No pricing information found for model", {
        model,
        mode: "chat",
        source: "llm-cost",
      });
      return 0;
    }

    if (pricing.mode !== "chat") {
      logger.error("Model is not a chat model", {
        model,
        actualMode: pricing.mode,
        expectedMode: "chat",
        source: "llm-cost",
      });
      return 0;
    }

    // Add per-request cost if applicable (Only Perplexity supports this)
    if (pricing.input_cost_per_request) {
      totalCost += pricing.input_cost_per_request;
    }

    // Add token-based costs
    if (pricing.input_cost_per_token) {
      totalCost += tokenUsage.promptTokens * pricing.input_cost_per_token;
    }

    if (pricing.output_cost_per_token) {
      totalCost += tokenUsage.completionTokens * pricing.output_cost_per_token;
    }

    return Number(totalCost.toFixed(7));
  } catch (error) {
    logger.error("Error estimating cost", {
      model: tokenUsage.model,
      error: error instanceof Error ? error.message : String(error),
      source: "llm-cost",
    });
    return totalCost;
  }
}
