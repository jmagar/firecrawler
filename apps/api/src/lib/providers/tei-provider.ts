import type { EmbeddingModel } from "ai";

export interface TEIConfig {
  baseURL: string;
  apiKey?: string;
  timeout?: number;
}

export interface TEIEmbeddingResponse {
  embeddings: number[][];
}

export interface TEIProvider {
  embedding: (modelId: string) => EmbeddingModel<string>;
}

/**
 * Creates a TEI (Text Embeddings Inference) provider for the AI SDK
 * Implements HTTP-based communication with TEI endpoints
 */
export function createTEI(config: TEIConfig): TEIProvider {
  const { baseURL, apiKey, timeout = 30000 } = config;

  if (!baseURL) {
    throw new Error("TEI baseURL is required");
  }

  return {
    embedding: (modelId: string) => ({
      specificationVersion: "v1",
      modelId,
      provider: "tei",
      maxEmbeddingsPerCall: 100, // TEI supports batch processing
      supportsParallelCalls: true,

      async doEmbed({ values, abortSignal }) {
        const url = `${baseURL}/embed`;
        
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };

        if (apiKey) {
          headers["Authorization"] = `Bearer ${apiKey}`;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        // Combine external abort signal with timeout
        if (abortSignal) {
          abortSignal.addEventListener("abort", () => controller.abort());
        }

        try {
          const response = await fetch(url, {
            method: "POST",
            headers,
            body: JSON.stringify({
              inputs: values,
            }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (!response.ok) {
            const errorText = await response.text().catch(() => "Unknown error");
            throw new Error(
              `TEI embedding request failed: ${response.status} ${response.statusText} - ${errorText}`
            );
          }

          const data = await response.json();

          // TEI returns embeddings directly as number[][], not wrapped in an object
          const embeddings = Array.isArray(data) ? data : data.embeddings;

          if (!embeddings || !Array.isArray(embeddings)) {
            throw new Error("Invalid response format from TEI: missing or invalid embeddings array");
          }

          if (embeddings.length !== values.length) {
            throw new Error(
              `TEI returned ${embeddings.length} embeddings but expected ${values.length}`
            );
          }

          return {
            embeddings: embeddings,
            usage: {
              tokens: values.reduce((sum, value) => sum + value.length, 0), // Rough token estimate
            },
          };
        } catch (error) {
          clearTimeout(timeoutId);
          
          if (error instanceof Error) {
            if (error.name === "AbortError") {
              throw new Error("TEI embedding request timeout");
            }
            throw error;
          }
          
          throw new Error(`TEI embedding request failed: ${String(error)}`);
        }
      },
    }),
  };
}