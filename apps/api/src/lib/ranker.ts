import { embed } from "ai";
import { configDotenv } from "dotenv";
import { getEmbeddingModel } from "./generic-ai";
import { CostTracking } from "./cost-tracking";
import { calculateEmbeddingCost } from "./extract/usage/llm-cost";

configDotenv();

async function getEmbedding(
  text: string,
  metadata: { teamId: string; extractId?: string },
  costTracking?: CostTracking,
) {
  // Determine provider based on MODEL_EMBEDDING_NAME
  const modelName = process.env.MODEL_EMBEDDING_NAME;
  const provider =
    modelName && modelName.startsWith("sentence-transformers/")
      ? ("tei" as const)
      : undefined;

  const finalModelName = provider
    ? modelName || "sentence-transformers/all-MiniLM-L6-v2"
    : "text-embedding-3-small";

  const { embedding } = await embed({
    model: provider
      ? getEmbeddingModel(finalModelName, provider)
      : getEmbeddingModel(finalModelName),
    value: text,
    experimental_telemetry: {
      isEnabled: true,
      metadata: {
        ...(metadata.extractId
          ? {
              langfuseTraceId: "extract:" + metadata.extractId,
              extractId: metadata.extractId,
            }
          : {}),
        teamId: metadata.teamId,
      },
    },
  });

  // Track embedding costs if cost tracking is provided
  if (costTracking) {
    const cost = calculateEmbeddingCost(finalModelName, text);

    costTracking.addCall({
      type: "other",
      metadata: {
        module: "ranker",
        method: "getEmbedding",
      },
      model: finalModelName,
      cost: cost,
      tokens: {
        input: Math.ceil(text.length * 0.5), // Approximate token count
        output: 0, // Embeddings don't have output tokens
      },
    });
  }

  return embedding;
}

const cosineSimilarity = (vec1: number[], vec2: number[]): number => {
  const dotProduct = vec1.reduce((sum, val, i) => sum + val * vec2[i], 0);
  const magnitude1 = Math.sqrt(vec1.reduce((sum, val) => sum + val * val, 0));
  const magnitude2 = Math.sqrt(vec2.reduce((sum, val) => sum + val * val, 0));
  if (magnitude1 === 0 || magnitude2 === 0) return 0;
  return dotProduct / (magnitude1 * magnitude2);
};

// Function to convert text to vector
const textToVector = (searchQuery: string, text: string): number[] => {
  const words = searchQuery.toLowerCase().split(/\W+/);
  return words.map(word => {
    const count = (text.toLowerCase().match(new RegExp(word, "g")) || [])
      .length;
    return count / text.length;
  });
};

async function performRanking(
  linksWithContext: string[],
  links: string[],
  searchQuery: string,
  metadata: { teamId: string; extractId?: string },
  costTracking?: CostTracking,
) {
  try {
    // Handle invalid inputs
    if (!searchQuery || !linksWithContext.length || !links.length) {
      return [];
    }

    // Sanitize search query by removing null characters
    const sanitizedQuery = searchQuery;

    // Generate embeddings for the search query
    const queryEmbedding = await getEmbedding(
      sanitizedQuery,
      metadata,
      costTracking,
    );

    // Generate embeddings for each link and calculate similarity in parallel
    const linksAndScores = await Promise.all(
      linksWithContext.map((linkWithContext, index) =>
        getEmbedding(linkWithContext, metadata, costTracking)
          .then(linkEmbedding => {
            const score = cosineSimilarity(queryEmbedding, linkEmbedding);
            return {
              link: links[index],
              linkWithContext,
              score,
              originalIndex: index,
            };
          })
          .catch(() => ({
            link: links[index],
            linkWithContext,
            score: 0,
            originalIndex: index,
          })),
      ),
    );

    // Sort links based on similarity scores while preserving original order for equal scores
    linksAndScores.sort((a, b) => {
      const scoreDiff = b.score - a.score;
      return scoreDiff === 0 ? a.originalIndex - b.originalIndex : scoreDiff;
    });

    return linksAndScores;
  } catch (error) {
    console.error(`Error performing semantic search: ${error}`);
    return [];
  }
}

export { performRanking };
