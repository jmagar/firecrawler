/**
 * Metadata Extraction Utilities for HuggingFace TEI + pgvector Integration
 *
 * Extracts technical documentation metadata from URLs and content for vector storage.
 * Designed for integration with both transformer pipeline and vector storage service.
 */

import { parse as parseDomain } from "tldts";

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
  quality_metrics?: ContentQualityMetrics; // Phase 1 addition
}

/**
 * Content quality scoring interfaces for Phase 1 noise reduction
 */
interface ContentQualityMetrics {
  overall_score: number; // 0-1 scale, higher = better quality
  content_density: number; // content words per total words
  navigation_ratio: number; // navigation elements to content ratio
  noise_indicators: string[]; // detected noise patterns
  readability_score?: number; // Flesch reading ease (optional)
  structural_quality: number; // HTML structure quality score
}

interface ContentDensityAnalysis {
  total_words: number;
  content_words: number;
  navigation_words: number;
  density_score: number; // 0-1 scale
  quality_indicators: {
    has_main_content: boolean;
    has_headings: boolean;
    paragraph_density: number;
    link_density: number;
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
        .filter(Boolean)
        .map(p => {
          try {
            return decodeURIComponent(p);
          } catch {
            return p;
          }
        });
      if (pathParts.length >= 4) {
        const [org, repo, branch, ...fileParts] = pathParts;
        const filePath = fileParts.join("/");
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
      return null;
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

        // Check for blob, tree, or raw paths
        if (
          remainingParts.length >= 2 &&
          (remainingParts[0] === "blob" ||
            remainingParts[0] === "tree" ||
            remainingParts[0] === "raw")
        ) {
          const afterMarker = remainingParts.slice(1);
          const idx = afterMarker.findIndex(seg => /\.[a-z0-9]+$/i.test(seg));
          if (idx >= 0) {
            branchVersion = afterMarker.slice(0, idx).join("/");
            filePath = afterMarker.slice(idx).join("/");
            fileExtension = filePath.split(".").pop()?.toLowerCase();
          } else if (
            (remainingParts[0] === "blob" || remainingParts[0] === "raw") &&
            afterMarker.length >= 2
          ) {
            // Handle extensionless files under /blob|raw/:ref/...
            branchVersion = afterMarker[0];
            filePath = afterMarker.slice(1).join("/");
          } else {
            // tree URLs without a file-like segment
            branchVersion = afterMarker.join("/");
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
    const filename = (() => {
      const parts = pathname.split("/").filter(Boolean);
      return parts.length ? parts[parts.length - 1] : "";
    })();

    // README detection
    if (
      filename.match(/^readme\.(md|mdx|txt|rst|adoc|org|textile)$/i) ||
      filename === "readme"
    ) {
      contentType = "readme";
      confidence = 0.95;
      indicators.push("filename_readme");
    }
    // Changelog detection
    else if (/^change(s|log)(\.|$)|^changelog(\.|$)/i.test(filename)) {
      contentType = "changelog";
      confidence = 0.95;
      indicators.push("filename_changelog");
    }
    // Installation guide detection
    else if (
      /^install(\.|$)|^installation(\.|$)|^getting[-_]started(\.|$)/i.test(
        filename,
      )
    ) {
      contentType = "installation_guide";
      confidence = 0.85;
      indicators.push("filename_installation");
    }
    // API documentation patterns
    else if (
      pathname.includes("/api/") ||
      pathname.includes("/docs/api") ||
      pathname.includes("/api-reference") ||
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
      pathname.includes("/guides") ||
      pathname.includes("/getting-started") ||
      pathname.includes("/quickstart")
    ) {
      contentType = "tutorial";
      confidence = 0.8;
      indicators.push("url_tutorial_pattern");
    }
    // Configuration files
    else if (
      filename.match(
        /\.(json|yaml|yml|toml|ini|conf|config|env|properties|cfg)$/i,
      ) ||
      filename === ".env"
    ) {
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
      pathname.includes("/docs/") ||
      pathname.endsWith("/docs")
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

    // Use tldts for proper domain parsing, including multi-level TLDs
    const parsed = parseDomain(hostname);
    const domain = parsed.domain || hostname;
    const subdomain = parsed.subdomain || undefined;

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
      subdomain
        .split(".")
        .some(seg =>
          ["docs", "documentation", "api", "dev", "developers"].includes(seg),
        )
    ) {
      isDocumentationSite = true;
      const segs = subdomain.split(".");
      if (segs.includes("api")) documentationType = "api";
      else if (segs.some(s => s === "docs" || s === "documentation"))
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
      (subdomain && subdomain.split(".").includes("blog"))
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

  // Basename / extension-based detection
  if (filePath) {
    const base = filePath.split("/").pop()!;
    // Common extensionless tech files
    if (/^dockerfile(\..+)?$/i.test(base)) return "dockerfile";
    if (/^makefile$/i.test(base)) return "makefile";
    if (
      /^gemfile$/i.test(base) ||
      /^podfile$/i.test(base) ||
      /^brewfile$/i.test(base)
    )
      return "ruby";

    const extension = base.includes(".")
      ? base.split(".").pop()!.toLowerCase()
      : undefined;
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
      h: "c",
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

    // Common extensionless files by content
    if (
      /^from\s+\w+/im.test(content) ||
      /^\s*#\s*syntax\s*=.*docker/i.test(content)
    )
      return "dockerfile";
    if (/^(\w+)\s*:\s*(.+)?\n(\t| {2,})/m.test(content)) return "makefile";
    if (/^#!\/usr\/bin\/env\s+(bash|sh|zsh|fish)/m.test(content)) return "bash";

    if (lowerContent.includes("def ") && lowerContent.includes("import "))
      return "python";
    if (
      /\binterface\s+\w+/.test(lowerContent) ||
      /\btype\s+\w+\s*=/.test(lowerContent) ||
      /\benum\s+\w+/.test(lowerContent)
    )
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

  if (
    typeof Intl !== "undefined" &&
    "Segmenter" in Intl &&
    typeof (Intl as any).Segmenter === "function"
  ) {
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
 * Analyzes content density and quality metrics for noise reduction
 */
function analyzeContentDensity(
  content: string,
  rawHtml?: string,
): ContentDensityAnalysis {
  if (!content) {
    return {
      total_words: 0,
      content_words: 0,
      navigation_words: 0,
      density_score: 0,
      quality_indicators: {
        has_main_content: false,
        has_headings: false,
        paragraph_density: 0,
        link_density: 0,
      },
    };
  }

  const totalWords = countWords(content);

  // Detect navigation patterns from markdown-cleanup
  const navigationPatterns = [
    /\bSkip to [Cc]ontent\b/gi,
    /\bSearch\.{3,}\b/gi,
    /\bCtrl\s*\+?\s*K\b/gi,
    /\bNavigation\b/gi,
    /\bTable of [Cc]ontents\b/gi,
    /\bPrevious\s*\|\s*Next\b/gi,
    /\bSelect language\b/gi,
    /\bToggle navigation\b/gi,
    /\bMenu\b/gi,
  ];

  let navigationWords = 0;
  for (const pattern of navigationPatterns) {
    const matches = content.match(pattern);
    if (matches) {
      navigationWords += matches.reduce(
        (sum, match) => sum + countWords(match),
        0,
      );
    }
  }

  const contentWords = Math.max(0, totalWords - navigationWords);
  const densityScore = totalWords > 0 ? contentWords / totalWords : 0;

  // Quality indicators
  const hasHeadings = /^#{1,6}\s+.+$/m.test(content);
  const hasMainContent = content.length > 200 && densityScore > 0.3;

  // Calculate paragraph density (paragraphs vs total content)
  const paragraphCount = (content.match(/\n\s*\n/g) || []).length + 1;
  const paragraphDensity =
    totalWords > 0 ? paragraphCount / (totalWords / 50) : 0; // ~50 words per paragraph ideal

  // Calculate link density
  const linkMatches = (content.match(/\[([^\]]+)\]\([^)]+\)/g) ||
    []) as string[];
  const linkWords = linkMatches.reduce((sum, link) => {
    const linkText = link.match(/\[([^\]]+)\]/)?.[1] || "";
    return sum + countWords(linkText);
  }, 0);
  const linkDensity = contentWords > 0 ? linkWords / contentWords : 0;

  return {
    total_words: totalWords,
    content_words: contentWords,
    navigation_words: navigationWords,
    density_score: Math.min(1, Math.max(0, densityScore)),
    quality_indicators: {
      has_main_content: hasMainContent,
      has_headings: hasHeadings,
      paragraph_density: Math.min(1, Math.max(0, paragraphDensity)),
      link_density: Math.min(1, Math.max(0, linkDensity)),
    },
  };
}

/**
 * Calculates overall content quality score based on multiple factors
 */
function calculateContentQuality(
  content: string,
  url: string,
  rawHtml?: string,
): ContentQualityMetrics {
  const densityAnalysis = analyzeContentDensity(content, rawHtml);
  const noiseIndicators: string[] = [];

  // Base quality from content density
  let qualityScore = densityAnalysis.density_score;

  // Boost for good structural indicators
  if (densityAnalysis.quality_indicators.has_main_content) {
    qualityScore += 0.2;
    noiseIndicators.push("has_main_content");
  }

  if (densityAnalysis.quality_indicators.has_headings) {
    qualityScore += 0.1;
  }

  // Penalize high link density (likely navigation/spam)
  if (densityAnalysis.quality_indicators.link_density > 0.3) {
    qualityScore -= 0.15;
    noiseIndicators.push("high_link_density");
  }

  // Penalize low paragraph density (likely fragmented content)
  if (densityAnalysis.quality_indicators.paragraph_density < 0.1) {
    qualityScore -= 0.1;
    noiseIndicators.push("low_paragraph_density");
  }

  // Navigation ratio scoring
  const navigationRatio =
    densityAnalysis.total_words > 0
      ? densityAnalysis.navigation_words / densityAnalysis.total_words
      : 0;

  if (navigationRatio > 0.2) {
    qualityScore -= 0.2;
    noiseIndicators.push("high_navigation_ratio");
  }

  // Structural quality based on content organization
  let structuralQuality = 0.5; // baseline

  if (densityAnalysis.quality_indicators.has_headings) structuralQuality += 0.2;
  if (densityAnalysis.quality_indicators.has_main_content)
    structuralQuality += 0.2;
  if (densityAnalysis.quality_indicators.paragraph_density > 0.2)
    structuralQuality += 0.1;

  // Domain-based quality adjustments
  try {
    const urlObj = new URL(url);
    if (
      urlObj.hostname.includes("docs") ||
      urlObj.hostname.includes("documentation")
    ) {
      qualityScore += 0.05; // Documentation sites typically have better content
    }
  } catch {
    // Invalid URL, no adjustment
  }

  // Clamp final score
  qualityScore = Math.min(1, Math.max(0, qualityScore));
  structuralQuality = Math.min(1, Math.max(0, structuralQuality));

  return {
    overall_score: qualityScore,
    content_density: densityAnalysis.density_score,
    navigation_ratio: navigationRatio,
    noise_indicators: noiseIndicators,
    structural_quality: structuralQuality,
  };
}

/**
 * Determines if a file is a code file based on extension and content
 */
function isCodeFile(filePath?: string, content?: string): boolean {
  if (!filePath && !content) return false;

  // Check by extension and extensionless tech files
  if (filePath) {
    const base = filePath.split("/").pop()!;
    // Check for extensionless tech files
    if (/^dockerfile(\..*)?$/i.test(base) || /^makefile$/i.test(base))
      return true;

    const extension = base.includes(".")
      ? base.split(".").pop()!.toLowerCase()
      : undefined;
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

    const hasCodePatterns =
      /^#!\/usr\/bin\/env\s+(bash|sh|zsh|fish|node|python3?)/m.test(content) ||
      codePatterns.some(pattern => pattern.test(content));
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
  rawHtml?: string, // Added for quality analysis
): DocumentMetadata {
  const githubMetadata = extractGitHubMetadata(url);
  const contentClassification = classifyContentType(url, content);
  const domainMetadata = extractDomainMetadata(url);
  const wordCount = content ? countWords(content) : 0;

  // Phase 1: Calculate content quality metrics
  const qualityMetrics = content
    ? calculateContentQuality(content, url, rawHtml)
    : undefined;

  let fileMetadata: DocumentMetadata["file_metadata"];

  // Extract file metadata if we have path information
  const filePathFromUrl = (() => {
    try {
      const urlObj = new URL(url);
      const { pathname, hostname } = urlObj;
      const parts = pathname.split("/").filter(Boolean);

      // Enhanced GitHub URL fallback - preserve directory context
      if (
        (hostname === "github.com" ||
          hostname === "raw.githubusercontent.com") &&
        parts.length >= 2
      ) {
        const [org, repo, ...remainingParts] = parts;

        // For raw.githubusercontent.com URLs: org/repo/branch/path...
        if (
          hostname === "raw.githubusercontent.com" &&
          remainingParts.length >= 2
        ) {
          const [branch, ...fileParts] = remainingParts;
          return fileParts.join("/");
        }

        // For github.com URLs with blob/tree/raw: org/repo/blob|tree|raw/branch/path...
        if (
          remainingParts.length >= 3 &&
          (remainingParts[0] === "blob" ||
            remainingParts[0] === "tree" ||
            remainingParts[0] === "raw")
        ) {
          const [marker, branch, ...fileParts] = remainingParts;
          return fileParts.join("/");
        }
      }

      // Fallback to last segment for non-GitHub or simple URLs
      return parts.length ? parts[parts.length - 1] : undefined;
    } catch {
      return undefined;
    }
  })();
  const filePath = githubMetadata?.file_path || filePathFromUrl;
  const effectiveGithub = githubMetadata
    ? {
        ...githubMetadata,
        file_path: githubMetadata.file_path ?? filePathFromUrl,
      }
    : undefined;
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
    github: effectiveGithub,
    content_classification: contentClassification,
    domain_metadata: domainMetadata,
    file_metadata: fileMetadata,
    quality_metrics: qualityMetrics, // Phase 1 addition
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

    // Phase 1: Content quality metrics for improved ranking
    quality_score: metadata.quality_metrics?.overall_score,
    content_density: metadata.quality_metrics?.content_density,
    navigation_ratio: metadata.quality_metrics?.navigation_ratio,
    structural_quality: metadata.quality_metrics?.structural_quality,
  };
}
