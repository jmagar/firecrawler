import { z } from "zod";
import { protocolIncluded, checkUrl } from "../lib/validateUrl";

/**
 * Shared URL schema used across API versions
 */
export const url = z.preprocess(
  x => {
    if (typeof x !== "string") return x;
    const s = x.trim();
    return protocolIncluded(s) ? s : `http://${s}`;

    // transforming the query parameters is breaking certain sites, so we're not doing it - mogery
    // try {
    //   const urlObj = new URL(x as string);
    //   if (urlObj.search) {
    //     const searchParams = new URLSearchParams(urlObj.search.substring(1));
    //     return `${urlObj.origin}${urlObj.pathname}?${searchParams.toString()}`;
    //   }
    // } catch (e) {
    // }
  },
  z
    .string()
    .url()
    .regex(/^https?:\/\//i, "URL uses unsupported protocol")
    .refine(x => {
      try {
        checkUrl(x as string);
        return true;
      } catch (_) {
        return false;
      }
    }, "Invalid URL"),
  // .refine((x) => !isUrlBlocked(x as string), BLOCKLISTED_URL_MESSAGE),
);

/**
 * Shared schema for LLMs text generation requests
 */
export const generateLLMsTextRequestSchema = z.object({
  url: url.describe("The URL to generate text from"),
  maxUrls: z
    .number()
    .int()
    .min(1)
    .max(5000)
    .default(10)
    .describe("Maximum number of URLs to process"),
  showFullText: z
    .boolean()
    .default(false)
    .describe("Whether to show the full LLMs-full.txt in the response"),
  cache: z
    .boolean()
    .default(true)
    .describe("Whether to use cached content if available"),
  __experimental_stream: z.boolean().optional(),
});

export type GenerateLLMsTextRequest = z.infer<
  typeof generateLLMsTextRequestSchema
>;
