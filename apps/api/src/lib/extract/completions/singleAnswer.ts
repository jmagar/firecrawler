import { logger } from "../../../lib/logger";
import {
  generateCompletions,
  GenerateCompletionsOptions,
} from "../../../scraper/scrapeURL/transformers/llmExtract";
import { buildDocument } from "../build-document";
import { Document, TokenUsage } from "../../../controllers/v1/types";
import { getModel } from "../../../lib/generic-ai";
import { extractData } from "../../../scraper/scrapeURL/lib/extractSmartScrape";

export async function singleAnswerCompletion({
  singleAnswerDocs,
  rSchema,
  links,
  prompt,
  systemPrompt,
  useAgent
}: {
  singleAnswerDocs: Document[];
  rSchema: any;
  links: string[];
  prompt: string;
  systemPrompt: string;
  useAgent: boolean;
}): Promise<{
  extract: any;
  tokenUsage: TokenUsage;
  sources: string[];
  smartScrapeCallCount: number;
  smartScrapeCost: number;
  otherCallCount: number;
  otherCost: number;
}> {
  const docsPrompt = `Today is: ` + new Date().toISOString() + `.\n` + prompt;
  const generationOptions: GenerateCompletionsOptions = {
    logger: logger.child({ module: "extract", method: "generateCompletions" }),
    options: {
      mode: "llm",
      systemPrompt:
        (systemPrompt ? `${systemPrompt}\n` : "") +
        "Always prioritize using the provided content to answer the question. Do not make up an answer. Do not hallucinate. In case you can't find the information and the string is required, instead of 'N/A' or 'Not speficied', return an empty string: '', if it's not a string and you can't find the information, return null. Be concise and follow the schema always if provided.",
        prompt: docsPrompt,
        schema: rSchema,
      },
      markdown: `${singleAnswerDocs.map((x, i) => `[START_PAGE (ID: ${i})]` + buildDocument(x)).join("\n")} [END_PAGE]\n`,
      isExtractEndpoint: true,
      model: getModel("gemini-2.0-flash", "google"),
    };

  const { extractedDataArray, warning, smartScrapeCost, otherCost, smartScrapeCallCount, otherCallCount } = await extractData({
    extractOptions: generationOptions,
    urls: singleAnswerDocs.map(doc => doc.metadata.url || doc.metadata.sourceURL || ""),
    useAgent,
  });

  const completion = {
    extract: extractedDataArray,
    tokenUsage: {
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0,
      model: "gemini-2.0-flash",
    },
    sources: singleAnswerDocs.map(
      (doc) => doc.metadata.url || doc.metadata.sourceURL || "",
    ),
  };

  // const completion = await generateCompletions({
  //   logger: logger.child({ module: "extract", method: "generateCompletions" }),
  //   options: {
  //     mode: "llm",
  //     systemPrompt:
  //       (systemPrompt ? `${systemPrompt}\n` : "") +
  //       "Always prioritize using the provided content to answer the question. Do not make up an answer. Do not hallucinate. In case you can't find the information and the string is required, instead of 'N/A' or 'Not speficied', return an empty string: '', if it's not a string and you can't find the information, return null. Be concise and follow the schema always if provided.",
  //     prompt: "Today is: " + new Date().toISOString() + "\n" + prompt,
  //     schema: rSchema,
  //   },
  //   markdown: singleAnswerDocs.map((x) => buildDocument(x)).join("\n"),
  //   isExtractEndpoint: true,
  //   model: getModel("gemini-2.0-flash", "google"),
  // });
  // await fs.writeFile(
  //   `logs/singleAnswer-${crypto.randomUUID()}.json`,
  //   JSON.stringify(completion, null, 2),
  // );
  return {
    extract: completion.extract,
    tokenUsage: completion.tokenUsage,
    sources: singleAnswerDocs.map(
      (doc) => doc.metadata.url || doc.metadata.sourceURL || "",
    ),
    smartScrapeCost,
    otherCost,
    smartScrapeCallCount,
    otherCallCount,
  };
}
