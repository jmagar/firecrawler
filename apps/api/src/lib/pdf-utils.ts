import { z } from "zod";

const pdfParserWithOptions = z
  .object({
    type: z.literal("pdf"),
    maxPages: z.number().int().positive().finite().max(10000).optional(),
  })
  .strict();

const parsersSchema = z
  .array(z.union([z.literal("pdf"), pdfParserWithOptions]))
  .default(["pdf"]);

type Parsers = z.infer<typeof parsersSchema>;

export function shouldParsePDF(parsers?: Parsers): boolean {
  if (!parsers) return true;
  return parsers.some(parser => {
    if (parser === "pdf") return true;
    if (typeof parser === "object" && parser !== null && "type" in parser) {
      return parser.type === "pdf";
    }
    return false;
  });
}

export function getPDFMaxPages(parsers?: Parsers): number | undefined {
  if (!parsers) return undefined;
  const pdfParser = parsers.find(parser => {
    return (
      typeof parser === "object" && parser !== null && parser.type === "pdf"
    );
  });
  if (pdfParser && typeof pdfParser === "object") {
    return pdfParser.maxPages;
  }
  return undefined;
}
