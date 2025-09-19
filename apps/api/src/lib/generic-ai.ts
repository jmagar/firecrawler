import { createOpenAI } from "@ai-sdk/openai";
import { createOllama } from "ollama-ai-provider";
import { anthropic } from "@ai-sdk/anthropic";
import { groq } from "@ai-sdk/groq";
import { google } from "@ai-sdk/google";
import { createOpenRouter } from "@openrouter/ai-sdk-provider";
import { fireworks } from "@ai-sdk/fireworks";
import { deepinfra } from "@ai-sdk/deepinfra";
import { createVertex } from "@ai-sdk/google-vertex";
import { createTEI } from "./providers/tei-provider";

type Provider =
  | "openai"
  | "ollama"
  | "anthropic"
  | "groq"
  | "google"
  | "openrouter"
  | "fireworks"
  | "deepinfra"
  | "vertex"
  | "tei";

type TextProvider = Exclude<Provider, "tei">;
type EmbeddingProvider = "tei" | "openai" | "ollama";
const defaultEmbeddingProvider: EmbeddingProvider = process.env.TEI_URL
  ? "tei"
  : process.env.OLLAMA_BASE_URL
    ? "ollama"
    : "openai";

const defaultTextProvider: TextProvider = process.env.OLLAMA_BASE_URL
  ? "ollama"
  : "openai";

const providerList: Record<Provider, any> = {
  openai: createOpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    baseURL: process.env.OPENAI_BASE_URL,
  }), //OPENAI_API_KEY
  ollama: createOllama({
    baseURL: process.env.OLLAMA_BASE_URL,
  }),
  anthropic, //ANTHROPIC_API_KEY
  groq, //GROQ_API_KEY
  google, //GOOGLE_GENERATIVE_AI_API_KEY
  openrouter: createOpenRouter({
    apiKey: process.env.OPENROUTER_API_KEY,
  }),
  fireworks, //FIREWORKS_API_KEY
  deepinfra, //DEEPINFRA_API_KEY
  vertex: createVertex({
    project: process.env.VERTEX_PROJECT || "firecrawl",
    //https://github.com/vercel/ai/issues/6644 bug
    baseURL: `https://aiplatform.googleapis.com/v1/projects/${process.env.VERTEX_PROJECT || "firecrawl"}/locations/${process.env.VERTEX_LOCATION || "global"}/publishers/google`,
    location: process.env.VERTEX_LOCATION || "global",
    googleAuthOptions: process.env.VERTEX_CREDENTIALS
      ? {
          credentials: JSON.parse(
            Buffer.from(process.env.VERTEX_CREDENTIALS!, "base64").toString(
              "utf8",
            ),
          ),
        }
      : {
          keyFile: "./gke-key.json",
        },
  }),
  tei: createTEI({
    baseURL: process.env.TEI_URL || "http://localhost:8080",
    apiKey: process.env.TEI_API_KEY,
  }),
};

export function getModel(
  name: string,
  provider: TextProvider = defaultTextProvider,
) {
  return process.env.MODEL_NAME
    ? providerList[provider](process.env.MODEL_NAME)
    : providerList[provider](name);
}

export function getEmbeddingModel(
  name: string,
  provider: EmbeddingProvider = defaultEmbeddingProvider,
) {
  if (typeof (providerList as any)[provider]?.embedding !== "function") {
    throw new Error(`Embeddings not supported for provider: ${provider}`);
  }
  return process.env.MODEL_EMBEDDING_NAME
    ? providerList[provider].embedding(process.env.MODEL_EMBEDDING_NAME)
    : providerList[provider].embedding(name);
}
