/**
 * Metadata Extraction Utilities for HuggingFace TEI + pgvector Integration
 *
 * Extracts technical documentation metadata from URLs and content for vector storage.
 * Designed for integration with both transformer pipeline and vector storage service.
 */

export interface GitHubRepositoryMetadata {
  repository_org: string;
  repository_name: string;
  file_path?: string;
  branch_version?: string;
  is_raw_file: boolean;
  file_extension?: string;
}

export interface ContentTypeClassification {
  content_type: string;
  confidence: number;
  indicators: string[];
}

export interface DomainMetadata {
  domain: string;
  subdomain?: string;
  is_documentation_site: boolean;
  documentation_type?: "github" | "docs" | "api" | "wiki" | "blog" | "tutorial";
}

export interface DocumentMetadata {
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
export function extractGitHubMetadata(
  url: string,
): GitHubRepositoryMetadata | null {
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
        .filter(part => part.length > 0);
      if (pathParts.length >= 3) {
        const [org, repo, branch, ...fileParts] = pathParts;
        const filePath = fileParts.join("/");
        const fileExtension = filePath.includes(".")
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
        .filter(part => part.length > 0);
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
export function classifyContentType(
  url: string,
  content?: string,
): ContentTypeClassification {
  const indicators: string[] = [];
  let contentType = "general";
  let confidence = 0.5;

  try {
    const urlObj = new URL(url);
    const pathname = urlObj.pathname.toLowerCase();
    const filename = pathname.split("/").pop() || "";

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
      filename.includes("api")
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
        /\.(js|ts|py|java|cpp|c|go|rs|rb|php|html|css|scss|less)$/i,
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
        contentType = "changelog";
        confidence = 0.8;
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
export function extractDomainMetadata(url: string): DomainMetadata {
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
    if (domain === "github.com" || domain === "raw.githubusercontent.com") {
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
      subdomain?.includes("blog")
    ) {
      isDocumentationSite = true;
      documentationType = "blog";
    }
    // Documentation hosting services
    else if (
      ["readthedocs.io", "gitbook.io", "notion.so", "gitiles.com"].some(
        service => hostname.includes(service),
      )
    ) {
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
export function detectProgrammingLanguage(
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
      ts: "typescript",
      tsx: "typescript",
      py: "python",
      java: "java",
      cpp: "cpp",
      cxx: "cpp",
      cc: "cpp",
      c: "c",
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
    if (lowerContent.includes("function ") && lowerContent.includes("const "))
      return "javascript";
    if (lowerContent.includes("interface ") && lowerContent.includes("type "))
      return "typescript";
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
 */
export function countWords(content: string): number {
  if (!content) return 0;

  // Remove code blocks
  const withoutCodeBlocks = content
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`[^`]*`/g, "");

  // Remove HTML tags
  const withoutHtml = withoutCodeBlocks.replace(/<[^>]*>/g, "");

  // Split by whitespace and filter out empty strings
  const words = withoutHtml
    .split(/\s+/)
    .filter(word => word.length > 0)
    .filter(word => !/^[^\w]*$/.test(word)); // Remove strings with no word characters

  return words.length;
}

/**
 * Determines if a file is a code file based on extension and content
 */
export function isCodeFile(filePath?: string, content?: string): boolean {
  if (!filePath && !content) return false;

  // Check by extension
  if (filePath) {
    const extension = filePath.split(".").pop()?.toLowerCase();
    const codeExtensions = [
      "js",
      "jsx",
      "ts",
      "tsx",
      "py",
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
      "r",
      "sql",
      "html",
      "css",
      "scss",
      "less",
      "vue",
      "svelte",
      "dart",
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
  const filePath = githubMetadata?.file_path || url.split("/").pop();
  if (filePath) {
    const isCode = isCodeFile(filePath, content);
    const programmingLanguage = detectProgrammingLanguage(filePath, content);
    const extension = filePath.includes(".")
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
