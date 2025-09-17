/**
 * Metadata Extraction Utilities for HuggingFace TEI + pgvector Integration
 *
 * Extracts technical documentation metadata from URLs and content for vector storage.
 * Designed for integration with both transformer pipeline and vector storage service.
 */

interface GitHubRepositoryMetadata {
  repository_org: string;
  repository_name: string;
  file_path?: string;
  branch_version?: string;
  is_raw_file: boolean;
  file_extension?: string;
}

interface ContentTypeClassification {
  content_type: string;
  confidence: number;
  indicators: string[];
}

interface DomainMetadata {
  domain: string;
  subdomain?: string;
  is_documentation_site: boolean;
  documentation_type?: "github" | "docs" | "api" | "wiki" | "blog" | "tutorial";
}

interface DocumentMetadata {
  title?: string;
  domain: string;
  word_count: number;
  github?: GitHubRepositoryMetadata;
  content_classification: ContentTypeClassification;
  domain_metadata: DomainMetadata;
  file_metadata?: {
    extension?: string;
    is_code_file: boolean;
    programming_language?: string;
  };
}

/**
 * Extracts GitHub repository information from URL
 */
function extractGitHubMetadata(url: string): GitHubRepositoryMetadata | null {
  try {
    const urlObj = new URL(url);

    // Only process GitHub URLs
    if (
      urlObj.hostname !== "github.com" &&
      urlObj.hostname !== "raw.githubusercontent.com"
    ) {
      return null;
    }

    // GitHub URL patterns:
    // https://github.com/{org}/{repo}
    // https://github.com/{org}/{repo}/blob/{branch}/{file_path}
    // https://github.com/{org}/{repo}/tree/{branch}/{directory_path}
    // https://raw.githubusercontent.com/{org}/{repo}/{branch}/{file_path}

    if (urlObj.hostname === "raw.githubusercontent.com") {
      const pathParts = urlObj.pathname
        .split("/")
        .filter(Boolean)
        .map(p => {
          try {
            return decodeURIComponent(p);
          } catch {
            return p;
          }
        });
      if (pathParts.length >= 3) {
        const [org, repo, branch, ...fileParts] = pathParts;
        const filePath = fileParts.length ? fileParts.join("/") : undefined;
        const fileExtension =
          filePath && filePath.includes(".")
            ? filePath.split(".").pop()?.toLowerCase()
            : undefined;

        return {
          repository_org: org,
          repository_name: repo,
          file_path: filePath,
          branch_version: branch,
          is_raw_file: true,
          file_extension: fileExtension,
        };
      }
    } else {
      const pathParts = urlObj.pathname
        .split("/")
        .filter(Boolean)
        .map(p => {
          try {
            return decodeURIComponent(p);
          } catch {
            return p;
          }
        });
      if (pathParts.length >= 2) {
        const [org, repo, ...remainingParts] = pathParts;

        let filePath: string | undefined;
        let branchVersion: string | undefined;
        let fileExtension: string | undefined;

        // Check for blob or tree paths
        if (
          remainingParts.length >= 2 &&
          (remainingParts[0] === "blob" || remainingParts[0] === "tree")
        ) {
          branchVersion = remainingParts[1];
          if (remainingParts.length > 2) {
            filePath = remainingParts.slice(2).join("/");
            if (filePath.includes(".")) {
              fileExtension = filePath.split(".").pop()?.toLowerCase();
            }
          }
        }

        return {
          repository_org: org,
          repository_name: repo,
          file_path: filePath,
          branch_version: branchVersion,
          is_raw_file: false,
          file_extension: fileExtension,
        };
      }
    }
  } catch (error) {
    // Invalid URL, return null
    return null;
  }

  return null;
}

/**
 * Detects content type based on URL patterns and content analysis
 */
function classifyContentType(
  url: string,
  content?: string,
): ContentTypeClassification {
  const indicators: string[] = [];
  let contentType = "general";
  let confidence = 0.5;

  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname.toLowerCase();
    const filename = (() => {
      const parts = pathname.split("/").filter(Boolean);
      return parts.length ? parts[parts.length - 1] : "";
    })();

    // README detection
    if (filename.match(/^readme\.(md|txt|rst)$/i) || filename === "readme") {
      contentType = "readme";
      confidence = 0.95;
      indicators.push("filename_readme");
    }
    // API documentation patterns
    else if (
      pathname.includes("/api/") ||
      pathname.includes("/docs/api") ||
      pathname.includes("/reference/") ||
      /\bapi\b/i.test(filename)
    ) {
      contentType = "api_documentation";
      confidence = 0.8;
      indicators.push("url_api_pattern");
    }
    // Tutorial patterns
    else if (
      pathname.includes("/tutorial") ||
      pathname.includes("/guide") ||
      pathname.includes("/getting-started") ||
      pathname.includes("/quickstart")
    ) {
      contentType = "tutorial";
      confidence = 0.8;
      indicators.push("url_tutorial_pattern");
    }
    // Configuration files
    else if (filename.match(/\.(json|yaml|yml|toml|ini|conf|config)$/i)) {
      contentType = "configuration";
      confidence = 0.9;
      indicators.push("config_file_extension");
    }
    // Code files
    else if (
      filename.match(
        /\.(js|jsx|mjs|cjs|ts|tsx|mts|cts|py|ipynb|java|cpp|cxx|cc|c|hpp|go|rs|rb|php|swift|kt|scala|sh|bash|zsh|fish|ps1|cs|dart|r|sql|html|css|scss|less|vue|svelte)$/i,
      )
    ) {
      contentType = "code";
      confidence = 0.9;
      indicators.push("code_file_extension");
    }
    // Documentation files
    else if (
      filename.match(/\.(md|rst|txt)$/i) ||
      pathname.includes("/docs/")
    ) {
      contentType = "documentation";
      confidence = 0.7;
      indicators.push("documentation_pattern");
    }

    // Content-based detection if content is provided
    if (content) {
      const lowerContent = content.toLowerCase();

      // API documentation indicators
      if (
        lowerContent.includes("api endpoint") ||
        lowerContent.includes("api reference") ||
        lowerContent.includes("http method") ||
        lowerContent.includes("request/response")
      ) {
        if (contentType === "general") {
          contentType = "api_documentation";
          confidence = 0.7;
        } else if (contentType === "api_documentation") {
          confidence = Math.min(confidence + 0.1, 0.95);
        }
        indicators.push("content_api_indicators");
      }

      // Tutorial indicators
      if (
        lowerContent.includes("step 1") ||
        lowerContent.includes("getting started") ||
        lowerContent.includes("tutorial") ||
        lowerContent.includes("walkthrough")
      ) {
        if (contentType === "general") {
          contentType = "tutorial";
          confidence = 0.7;
        } else if (contentType === "tutorial") {
          confidence = Math.min(confidence + 0.1, 0.95);
        }
        indicators.push("content_tutorial_indicators");
      }

      // Installation/setup documentation
      if (
        lowerContent.includes("install") ||
        lowerContent.includes("setup") ||
        lowerContent.includes("npm install") ||
        lowerContent.includes("pip install")
      ) {
        if (contentType === "general") {
          contentType = "installation_guide";
          confidence = 0.7;
        }
        indicators.push("content_installation_indicators");
      }

      // Changelog detection
      if (
        lowerContent.includes("changelog") ||
        lowerContent.includes("release notes") ||
        (lowerContent.includes("version") && lowerContent.includes("changes"))
      ) {
        if (contentType === "general" || confidence < 0.75) {
          contentType = "changelog";
          confidence = Math.max(confidence, 0.8);
        } else {
          confidence = Math.min(confidence + 0.05, 0.95);
        }
        indicators.push("content_changelog_indicators");
      }
    }
  } catch (error) {
    // Invalid URL, use fallback detection
    contentType = "general";
    confidence = 0.3;
  }

  return {
    content_type: contentType,
    confidence,
    indicators,
  };
}

/**
 * Extracts domain and subdomain information with documentation site detection
 */
function extractDomainMetadata(url: string): DomainMetadata {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.toLowerCase();
    const parts = hostname.split(".");

    let domain = hostname;
    let subdomain: string | undefined;

    // Extract main domain and subdomain
    if (parts.length >= 3) {
      // For domains like docs.example.com or api.github.com
      subdomain = parts.slice(0, -2).join(".");
      domain = parts.slice(-2).join(".");
    } else if (parts.length === 2) {
      domain = hostname;
    }

    // Detect if this is a documentation site
    let isDocumentationSite = false;
    let documentationType: DomainMetadata["documentation_type"];

    // GitHub detection
    if (domain === "github.com" || hostname === "raw.githubusercontent.com") {
      isDocumentationSite = true;
      documentationType = "github";
    }
    // Common documentation subdomains
    else if (
      subdomain &&
      ["docs", "documentation", "api", "dev", "developers"].includes(subdomain)
    ) {
      isDocumentationSite = true;
      if (subdomain === "api") documentationType = "api";
      else if (subdomain === "docs" || subdomain === "documentation")
        documentationType = "docs";
      else documentationType = "docs";
    }
    // Wiki sites
    else if (hostname.includes("wiki") || subdomain?.includes("wiki")) {
      isDocumentationSite = true;
      documentationType = "wiki";
    }
    // Blog platforms
    else if (
      ["medium.com", "dev.to", "hashnode.com"].includes(domain) ||
      subdomain === "blog" ||
      subdomain?.startsWith("blog.")
    ) {
      isDocumentationSite = true;
      documentationType = "blog";
    }
    // Documentation hosting services
    else if (
      ["readthedocs.io", "gitbook.io", "notion.so", "gitiles.com"].some(
        service => hostname === service || hostname.endsWith("." + service),
      )
    ) {
      isDocumentationSite = true;
      documentationType = "docs";
    }
    // GitHub Pages
    else if (hostname.endsWith(".github.io")) {
      isDocumentationSite = true;
      documentationType = "docs";
    }

    return {
      domain,
      subdomain,
      is_documentation_site: isDocumentationSite,
      documentation_type: documentationType,
    };
  } catch (error) {
    // Invalid URL, return basic info
    return {
      domain: url,
      is_documentation_site: false,
    };
  }
}

/**
 * Determines programming language from file extension and content
 */
function detectProgrammingLanguage(
  filePath?: string,
  content?: string,
): string | undefined {
  if (!filePath && !content) return undefined;

  // Extension-based detection
  if (filePath) {
    const extension = filePath.split(".").pop()?.toLowerCase();
    const extensionMap: Record<string, string> = {
      js: "javascript",
      jsx: "javascript",
      mjs: "javascript",
      cjs: "javascript",
      ts: "typescript",
      tsx: "typescript",
      mts: "typescript",
      cts: "typescript",
      py: "python",
      ipynb: "python",
      java: "java",
      cpp: "cpp",
      cxx: "cpp",
      cc: "cpp",
      c: "c",
      hpp: "cpp",
      go: "go",
      rs: "rust",
      rb: "ruby",
      php: "php",
      swift: "swift",
      kt: "kotlin",
      scala: "scala",
      sh: "bash",
      bash: "bash",
      zsh: "zsh",
      fish: "fish",
      ps1: "powershell",
      cs: "csharp",
      dart: "dart",
      r: "r",
      sql: "sql",
      html: "html",
      css: "css",
      scss: "scss",
      less: "less",
      vue: "vue",
      svelte: "svelte",
    };

    if (extension && extensionMap[extension]) {
      return extensionMap[extension];
    }
  }

  // Content-based detection (basic patterns)
  if (content) {
    const lowerContent = content.toLowerCase();

    if (lowerContent.includes("def ") && lowerContent.includes("import "))
      return "python";
    if (lowerContent.includes("interface ") && lowerContent.includes("type "))
      return "typescript";
    if (lowerContent.includes("function ") && lowerContent.includes("const "))
      return "javascript";
    if (
      lowerContent.includes("using system") &&
      lowerContent.includes("namespace ")
    )
      return "csharp";
    if (
      lowerContent.includes("public class") &&
      lowerContent.includes("static void")
    )
      return "java";
    if (lowerContent.includes("#include") && lowerContent.includes("int main"))
      return "c";
    if (lowerContent.includes("func ") && lowerContent.includes("package "))
      return "go";
    if (lowerContent.includes("fn ") && lowerContent.includes("let "))
      return "rust";
  }

  return undefined;
}

/**
 * Counts words in content (excluding code blocks and HTML)
 * Uses Intl.Segmenter for better CJK language support when available
 */
function countWords(content: string): number {
  if (!content) return 0;
  const withoutCodeBlocks = content
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`[^`]*`/g, "");
  const withoutHtml = withoutCodeBlocks.replace(/<[^>]*>/g, "");

  if ((Intl as any).Segmenter) {
    const seg = new (Intl as any).Segmenter(undefined, { granularity: "word" });
    let count = 0;
    for (const { isWordLike } of seg.segment(withoutHtml) as any)
      if (isWordLike) count++;
    return count;
  }

  return withoutHtml
    .split(/\s+/)
    .filter(w => w.length > 0 && !/^[^\w]*$/.test(w)).length;
}

/**
 * Determines if a file is a code file based on extension and content
 */
function isCodeFile(filePath?: string, content?: string): boolean {
  if (!filePath && !content) return false;

  // Check by extension
  if (filePath) {
    const extension = filePath.split(".").pop()?.toLowerCase();
    const codeExtensions = [
      "js",
      "jsx",
      "mjs",
      "cjs",
      "ts",
      "tsx",
      "mts",
      "cts",
      "py",
      "ipynb",
      "java",
      "cpp",
      "cxx",
      "cc",
      "c",
      "h",
      "hpp",
      "go",
      "rs",
      "rb",
      "php",
      "swift",
      "kt",
      "scala",
      "sh",
      "bash",
      "zsh",
      "fish",
      "ps1",
      "cs",
      "dart",
      "r",
      "sql",
      "html",
      "css",
      "scss",
      "less",
      "vue",
      "svelte",
      "elm",
      "ex",
      "exs",
      "clj",
      "cljs",
      "fs",
      "fsx",
      "hs",
      "lhs",
      "ml",
      "mli",
    ];

    if (extension && codeExtensions.includes(extension)) {
      return true;
    }
  }

  // Check by content patterns
  if (content) {
    const codePatterns = [
      /function\s+\w+\s*\(/,
      /def\s+\w+\s*\(/,
      /class\s+\w+/,
      /import\s+.+/,
      /#include\s*<.+>/,
      /package\s+\w+/,
      /const\s+\w+\s*=/,
      /let\s+\w+\s*=/,
      /var\s+\w+\s*=/,
    ];

    const hasCodePatterns = codePatterns.some(pattern => pattern.test(content));
    if (hasCodePatterns) return true;
  }

  return false;
}

/**
 * Main function to extract all metadata from URL and content
 */
export function extractDocumentMetadata(
  url: string,
  content?: string,
  title?: string,
): DocumentMetadata {
  const githubMetadata = extractGitHubMetadata(url);
  const contentClassification = classifyContentType(url, content);
  const domainMetadata = extractDomainMetadata(url);
  const wordCount = content ? countWords(content) : 0;

  let fileMetadata: DocumentMetadata["file_metadata"];

  // Extract file metadata if we have path information
  const filePathFromUrl = (() => {
    try {
      const { pathname } = new URL(url);
      const parts = pathname.split("/").filter(Boolean);
      return parts.length ? parts[parts.length - 1] : undefined;
    } catch {
      return undefined;
    }
  })();
  const filePath = githubMetadata?.file_path || filePathFromUrl;
  if (filePath) {
    const isCode = isCodeFile(filePath, content);
    const programmingLanguage = detectProgrammingLanguage(filePath, content);
    const extension =
      filePath && filePath.includes(".")
        ? filePath.split(".").pop()?.toLowerCase()
        : undefined;

    fileMetadata = {
      extension,
      is_code_file: isCode,
      programming_language: programmingLanguage,
    };
  }

  return {
    title,
    domain: domainMetadata.domain,
    word_count: wordCount,
    github: githubMetadata || undefined,
    content_classification: contentClassification,
    domain_metadata: domainMetadata,
    file_metadata: fileMetadata,
  };
}

/**
 * Utility function to format metadata for vector storage
 */
export function formatMetadataForStorage(
  metadata: DocumentMetadata,
): Record<string, string | number | boolean | undefined> {
  return {
    title: metadata.title,
    domain: metadata.domain,
    word_count: metadata.word_count,
    repository_name: metadata.github?.repository_name,
    repository_org: metadata.github?.repository_org,
    file_path: metadata.github?.file_path,
    branch_version: metadata.github?.branch_version,
    content_type: metadata.content_classification.content_type,
    is_documentation_site: metadata.domain_metadata.is_documentation_site,
    documentation_type: metadata.domain_metadata.documentation_type,
    is_code_file: metadata.file_metadata?.is_code_file || false,
    programming_language: metadata.file_metadata?.programming_language,
  };
}
