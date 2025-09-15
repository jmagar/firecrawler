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

export function calculateThinkingCost(costTracking: CostTracking): number {
  return Math.ceil(costTracking.toJSON().totalCost * 20000);
}

export function calculateFinalResultCost(data: any): number {
  return Math.floor(
    JSON.stringify(data).length / tokenPerCharacter + baseTokenCost,
  );
}

export function estimateTotalCost(tokenUsage: TokenUsage[]): number {
  return tokenUsage.reduce((total, usage) => {
    return total + estimateCost(usage);
  }, 0);
}

export function calculateEmbeddingCost(
  modelName: string,
  inputText: string,
): number {
  try {
    const pricing = modelPrices[modelName] as ModelPricing;

    if (!pricing) {
      logger.error(`No pricing information found for embedding model: ${modelName}`);
      return 0;
    }

    if (pricing.mode !== "embedding") {
      logger.error(`Model ${modelName} is not an embedding model`);
      return 0;
    }

    // For TEI models (which are typically free/local), return 0
    if (pricing.litellm_provider === "tei") {
      return 0;
    }

    // Calculate cost based on input length
    // Approximate token count using character/token ratio
    const approximateTokens = Math.ceil(inputText.length * tokenPerCharacter);
    
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
    logger.error(`Error calculating embedding cost: ${error}`);
    return 0;
  }
}

function estimateCost(tokenUsage: TokenUsage): number {
  let totalCost = 0;
  try {
    let model = tokenUsage.model ?? (process.env.MODEL_NAME || "gpt-4o-mini");
    const pricing = modelPrices[model] as ModelPricing;

    if (!pricing) {
      logger.error(`No pricing information found for model: ${model}`);
      return 0;
    }

    if (pricing.mode !== "chat") {
      logger.error(`Model ${model} is not a chat model`);
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
    logger.error(`Error estimating cost: ${error}`);
    return totalCost;
  }
}
