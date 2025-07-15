import koffi, { KoffiFunction } from "koffi";
import { join } from "path";
import { stat } from "fs/promises";
import { platform } from "os";
import type { DenialReason } from "../scraper/WebScraper/crawler";

// TODO: add a timeout to the Rust transformer
const rustExecutablePath = join(
  process.cwd(),
  "sharedLibs/crawler/target/release/",
  platform() === "darwin" ? "libcrawler.dylib" : "libcrawler.so"
);

export type FilterLinksCall = {
  links: string[],
  limit: number | undefined,
  max_depth: number,
  base_url: string,
  initial_url: string,
  regex_on_full_url: boolean,
  excludes: string[],
  includes: string[],
  allow_backward_crawling: boolean,
  ignore_robots_txt: boolean,
  robots_txt: string,
}

export type FilterLinksResult = {
  links: string[],
  denial_reasons: Map<string, keyof typeof DenialReason>,
}

class RustCrawler {
  private static instance: RustCrawler;
  private _freeString: KoffiFunction;
  private _filterLinks: KoffiFunction;

  private constructor() {
    const lib = koffi.load(rustExecutablePath);
    this._freeString = lib.func("free_string", "void", ["string"]);
    const cstn = "CString:" + crypto.randomUUID();
    const freedResultString = koffi.disposable(cstn, "string", this._freeString);
    this._filterLinks = lib.func("filter_links", freedResultString, ["string"]);
  }

  public static async getInstance(): Promise<RustCrawler> {
    if (!RustCrawler.instance) {
      try {
        await stat(rustExecutablePath);
      } catch (_) {
        throw Error("Rust crawler shared library not found");
      }
      RustCrawler.instance = new RustCrawler();
    }
    return RustCrawler.instance;
  }

  public async filterLinks(call: FilterLinksCall): Promise<FilterLinksResult> {
    return new Promise<FilterLinksResult>((resolve, reject) => {
      this._filterLinks.async(JSON.stringify(call), (err: Error, res: string) => {
        if (err) {
          reject(err);
        } else {
          if (res.startsWith("RUSTFC:ERROR:")) {
            return reject(new Error(res.split("RUSTFC:ERROR:")[1]));
          }

          if (res === "RUSTFC:ERROR") {
            return reject(new Error("Something went wrong on the Rust side."));
          }

          try {
            const raw = JSON.parse(res);
            const result: FilterLinksResult = {
              links: raw.links,
              denial_reasons: new Map(Object.entries(raw.denial_reasons)),
            }
            resolve(result);
          } catch (e) {
            reject(e);
          }
        }
      });
    });
  }
}

export async function filterLinks(
  call: FilterLinksCall,
): Promise<FilterLinksResult> {
    console.log(call);
    const converter = await RustCrawler.getInstance();
    return await converter.filterLinks(call);
}
