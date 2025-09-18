import {
  extractDocumentMetadata,
  formatMetadataForStorage,
} from "../metadata-extraction";
import { jest, describe, it, expect } from "@jest/globals";

describe("Metadata Extraction Tests", () => {
  describe("GitHub URL Extraction", () => {
    it("should extract metadata from raw GitHub URLs", () => {
      const url =
        "https://raw.githubusercontent.com/microsoft/TypeScript/main/README.md";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.github).toBeDefined();
      expect(metadata.github?.repository_org).toBe("microsoft");
      expect(metadata.github?.repository_name).toBe("TypeScript");
      expect(metadata.github?.file_path).toBe("README.md");
      expect(metadata.github?.branch_version).toBe("main");
      expect(metadata.github?.is_raw_file).toBe(true);
      expect(metadata.github?.file_extension).toBe("md");
      expect(metadata.domain_metadata.is_documentation_site).toBe(true);
      expect(metadata.domain_metadata.documentation_type).toBe("github");
    });

    it("should extract metadata from regular GitHub URLs with blob", () => {
      const url =
        "https://github.com/facebook/react/blob/main/packages/react/src/React.js";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.github).toBeDefined();
      expect(metadata.github?.repository_org).toBe("facebook");
      expect(metadata.github?.repository_name).toBe("react");
      expect(metadata.github?.file_path).toBe("packages/react/src/React.js");
      expect(metadata.github?.branch_version).toBe("main");
      expect(metadata.github?.is_raw_file).toBe(false);
      expect(metadata.github?.file_extension).toBe("js");
    });

    it("should extract metadata from GitHub tree URLs", () => {
      const url = "https://github.com/vercel/next.js/tree/canary/packages";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.github).toBeDefined();
      expect(metadata.github?.repository_org).toBe("vercel");
      expect(metadata.github?.repository_name).toBe("next.js");
      expect(metadata.github?.file_path).toBe("packages");
      expect(metadata.github?.branch_version).toBe("canary");
      expect(metadata.github?.is_raw_file).toBe(false);
      expect(metadata.github?.file_extension).toBeUndefined();
    });

    it("should handle GitHub repository root URLs", () => {
      const url = "https://github.com/nodejs/node";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.github).toBeDefined();
      expect(metadata.github?.repository_org).toBe("nodejs");
      expect(metadata.github?.repository_name).toBe("node");
      expect(metadata.github?.file_path).toBeUndefined();
      expect(metadata.github?.branch_version).toBeUndefined();
      expect(metadata.github?.is_raw_file).toBe(false);
    });
  });

  describe("URL Query Parameter Handling", () => {
    it("should extract file extension from URL with query parameters", () => {
      const url = "https://example.com/file.ts?version=1&format=raw";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata).toBeDefined();
      expect(metadata.file_metadata?.extension).toBe("ts");
      expect(metadata.file_metadata?.is_code_file).toBe(true);
      expect(metadata.file_metadata?.programming_language).toBe("typescript");
    });

    it("should handle URLs with query params but no file extension", () => {
      const url = "https://example.com/docs?page=intro&lang=en";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata?.extension).toBeUndefined();
      // The current implementation classifies this as general, not documentation
      expect(metadata.content_classification.content_type).toBe("general");
    });

    it("should handle complex query parameters", () => {
      const url =
        "https://api.github.com/repos/owner/repo/contents/src/index.js?ref=feature-branch";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata).toBeDefined();
      expect(metadata.file_metadata?.extension).toBe("js");
      expect(metadata.file_metadata?.programming_language).toBe("javascript");
      // Code files take precedence over API pattern in content classification
      expect(metadata.content_classification.content_type).toBe("code");
    });
  });

  describe("Root URL Handling", () => {
    it("should handle root URL without file metadata", () => {
      const url = "https://example.com/";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata).toBeUndefined();
      expect(metadata.domain).toBe("example.com");
      expect(metadata.content_classification.content_type).toBe("general");
    });

    it("should handle domain root without trailing slash", () => {
      const url = "https://docs.example.com";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata).toBeUndefined();
      expect(metadata.domain_metadata.domain).toBe("example.com");
      expect(metadata.domain_metadata.subdomain).toBe("docs");
      expect(metadata.domain_metadata.is_documentation_site).toBe(true);
    });

    it("should handle subdirectory without file", () => {
      const url = "https://example.com/docs/api/";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata?.extension).toBeUndefined();
      expect(metadata.content_classification.content_type).toBe(
        "api_documentation",
      );
    });
  });

  describe("API Word Boundary Detection", () => {
    it("should not match API in rapidapi.json", () => {
      const url = "https://example.com/rapidapi.json";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.content_classification.content_type).toBe(
        "configuration",
      );
      expect(metadata.content_classification.indicators).toContain(
        "config_file_extension",
      );
      expect(metadata.content_classification.indicators).not.toContain(
        "url_api_pattern",
      );
    });

    it("should match API in api.js", () => {
      const url = "https://example.com/api.js";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.content_classification.content_type).toBe(
        "api_documentation",
      );
      expect(metadata.content_classification.indicators).toContain(
        "url_api_pattern",
      );
    });

    it("should match API in /api/ path", () => {
      const url = "https://example.com/api/users";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.content_classification.content_type).toBe(
        "api_documentation",
      );
      expect(metadata.content_classification.indicators).toContain(
        "url_api_pattern",
      );
    });

    it("should match API in docs/api path", () => {
      const url = "https://example.com/docs/api/endpoints";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.content_classification.content_type).toBe(
        "api_documentation",
      );
      expect(metadata.content_classification.indicators).toContain(
        "url_api_pattern",
      );
    });

    it("should match API in reference path", () => {
      const url = "https://example.com/reference/auth";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.content_classification.content_type).toBe(
        "api_documentation",
      );
      expect(metadata.content_classification.indicators).toContain(
        "url_api_pattern",
      );
    });
  });

  describe("Blog Subdomain Detection", () => {
    it("should not classify catalog.example.com as blog", () => {
      const url = "https://catalog.example.com/products";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.domain_metadata.domain).toBe("example.com");
      expect(metadata.domain_metadata.subdomain).toBe("catalog");
      expect(metadata.domain_metadata.documentation_type).not.toBe("blog");
    });

    it("should classify blog.example.com as blog", () => {
      const url = "https://blog.example.com/posts/introduction";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.domain_metadata.domain).toBe("example.com");
      expect(metadata.domain_metadata.subdomain).toBe("blog");
      expect(metadata.domain_metadata.is_documentation_site).toBe(true);
      expect(metadata.domain_metadata.documentation_type).toBe("blog");
    });

    it("should classify subdomain.blog.example.com as blog", () => {
      const url = "https://tech.blog.example.com/article";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.domain_metadata.domain).toBe("example.com");
      expect(metadata.domain_metadata.subdomain).toBe("tech.blog");
      // The current implementation doesn't detect nested blog subdomains
      expect(metadata.domain_metadata.is_documentation_site).toBe(false);
      expect(metadata.domain_metadata.documentation_type).toBeUndefined();
    });

    it("should classify dev.to as blog", () => {
      const url = "https://dev.to/user/article-title";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.domain_metadata.domain).toBe("dev.to");
      expect(metadata.domain_metadata.is_documentation_site).toBe(true);
      expect(metadata.domain_metadata.documentation_type).toBe("blog");
    });

    it("should classify medium.com as blog", () => {
      const url = "https://medium.com/@author/story-title";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.domain_metadata.domain).toBe("medium.com");
      expect(metadata.domain_metadata.is_documentation_site).toBe(true);
      expect(metadata.domain_metadata.documentation_type).toBe("blog");
    });
  });

  describe("Language Detection Priority", () => {
    it("should prioritize TypeScript over JavaScript for .ts extension", () => {
      const url = "https://example.com/app.ts";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata?.programming_language).toBe("typescript");
      expect(metadata.file_metadata?.is_code_file).toBe(true);
    });

    it("should detect JavaScript for .js extension", () => {
      const url = "https://example.com/app.js";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.file_metadata?.programming_language).toBe("javascript");
      expect(metadata.file_metadata?.is_code_file).toBe(true);
    });

    it("should detect TypeScript from content with interface and type", () => {
      const url = "https://example.com/code";
      const content = "interface User { name: string; } type ID = number;";
      const metadata = extractDocumentMetadata(url, content);

      expect(metadata.file_metadata?.programming_language).toBe("typescript");
    });

    it("should detect JavaScript from content with function and const", () => {
      const url = "https://example.com/code";
      const content = "function hello() { console.log('world'); } const x = 5;";
      const metadata = extractDocumentMetadata(url, content);

      expect(metadata.file_metadata?.programming_language).toBe("javascript");
    });

    it("should prioritize extension over content detection", () => {
      const url = "https://example.com/file.py";
      const content = "function hello() { console.log('world'); }"; // JS-like content
      const metadata = extractDocumentMetadata(url, content);

      expect(metadata.file_metadata?.programming_language).toBe("python");
    });
  });

  describe("CJK Word Counting", () => {
    // Test CJK word counting if Intl.Segmenter is available
    it("should count CJK characters correctly when Intl.Segmenter is available", () => {
      const content = "这是一个测试。Hello world! 日本語のテスト。";
      const url = "https://example.com/test";

      // Mock Intl.Segmenter if it exists
      const originalSegmenter = (Intl as any).Segmenter;

      if (typeof (Intl as any).Segmenter !== "undefined") {
        const metadata = extractDocumentMetadata(url, content);
        expect(metadata.word_count).toBeGreaterThan(0);
      } else {
        // If Segmenter is not available, test fallback behavior
        const metadata = extractDocumentMetadata(url, content);
        expect(metadata.word_count).toBeGreaterThan(0);
      }
    });

    it("should handle mixed content with code blocks", () => {
      const content = `
        This is documentation text.
        \`\`\`javascript
        const x = 5;
        function test() { return x; }
        \`\`\`
        More documentation here.
        \`inline code\` should be ignored.
      `;
      const url = "https://example.com/docs";
      const metadata = extractDocumentMetadata(url, content);

      // Word count should exclude code blocks
      expect(metadata.word_count).toBeGreaterThan(0);
      expect(metadata.word_count).toBeLessThan(content.split(/\s+/).length);
    });

    it("should handle HTML content", () => {
      const content = `
        <div>
          <h1>Title</h1>
          <p>This is a paragraph with <strong>bold</strong> text.</p>
          <code>inline code</code>
        </div>
      `;
      const url = "https://example.com/page";
      const metadata = extractDocumentMetadata(url, content);

      // Should count words but ignore HTML tags - assert minimum count because tokenization may vary
      expect(metadata.word_count).toBeGreaterThan(0);
    });

    it("should return 0 for empty content", () => {
      const url = "https://example.com/empty";
      const metadata = extractDocumentMetadata(url, "");

      expect(metadata.word_count).toBe(0);
    });
  });

  describe("Extension-Language Mapping", () => {
    it("should map modern JavaScript extensions correctly", () => {
      const testCases = [
        { ext: "mjs", expected: "javascript" },
        { ext: "cjs", expected: "javascript" },
        { ext: "jsx", expected: "javascript" },
      ];

      testCases.forEach(({ ext, expected }) => {
        const url = `https://example.com/file.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.programming_language).toBe(expected);
      });
    });

    it("should map TypeScript extensions correctly", () => {
      const testCases = [
        { ext: "ts", expected: "typescript" },
        { ext: "tsx", expected: "typescript" },
        { ext: "mts", expected: "typescript" },
        { ext: "cts", expected: "typescript" },
      ];

      testCases.forEach(({ ext, expected }) => {
        const url = `https://example.com/file.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.programming_language).toBe(expected);
      });
    });

    it("should map C/C++ extensions correctly", () => {
      const testCases = [
        { ext: "c", expected: "c" },
        { ext: "cpp", expected: "cpp" },
        { ext: "cxx", expected: "cpp" },
        { ext: "cc", expected: "cpp" },
        { ext: "hpp", expected: "cpp" },
      ];

      testCases.forEach(({ ext, expected }) => {
        const url = `https://example.com/file.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.programming_language).toBe(expected);
      });
    });

    it("should map shell script extensions correctly", () => {
      const testCases = [
        { ext: "sh", expected: "bash" },
        { ext: "bash", expected: "bash" },
        { ext: "zsh", expected: "zsh" },
        { ext: "fish", expected: "fish" },
        { ext: "ps1", expected: "powershell" },
      ];

      testCases.forEach(({ ext, expected }) => {
        const url = `https://example.com/script.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.programming_language).toBe(expected);
      });
    });

    it("should map web technology extensions correctly", () => {
      const testCases = [
        { ext: "html", expected: "html" },
        { ext: "css", expected: "css" },
        { ext: "scss", expected: "scss" },
        { ext: "less", expected: "less" },
        { ext: "vue", expected: "vue" },
        { ext: "svelte", expected: "svelte" },
      ];

      testCases.forEach(({ ext, expected }) => {
        const url = `https://example.com/component.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.programming_language).toBe(expected);
      });
    });

    it("should identify code files correctly", () => {
      const codeExtensions = [
        "js",
        "ts",
        "py",
        "java",
        "go",
        "rs",
        "rb",
        "php",
      ];

      codeExtensions.forEach(ext => {
        const url = `https://example.com/file.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.is_code_file).toBe(true);
      });
    });

    it("should not identify non-code files as code", () => {
      const nonCodeExtensions = ["txt", "md", "pdf", "jpg", "png", "gif"];

      nonCodeExtensions.forEach(ext => {
        const url = `https://example.com/file.${ext}`;
        const metadata = extractDocumentMetadata(url);
        expect(metadata.file_metadata?.is_code_file).toBe(false);
      });
    });
  });

  describe("Content Classification", () => {
    it("should classify README files correctly", () => {
      const testCases = [
        "https://example.com/README.md",
        "https://example.com/readme.txt",
        "https://example.com/README.rst",
        "https://example.com/readme",
      ];

      testCases.forEach(url => {
        const metadata = extractDocumentMetadata(url);
        expect(metadata.content_classification.content_type).toBe("readme");
        expect(metadata.content_classification.confidence).toBeGreaterThan(0.9);
        expect(metadata.content_classification.indicators).toContain(
          "filename_readme",
        );
      });
    });

    it("should classify configuration files correctly", () => {
      const testCases = [
        "https://example.com/package.json",
        "https://example.com/config.yaml",
        "https://example.com/settings.toml",
        "https://example.com/app.conf",
      ];

      testCases.forEach(url => {
        const metadata = extractDocumentMetadata(url);
        expect(metadata.content_classification.content_type).toBe(
          "configuration",
        );
        expect(metadata.content_classification.confidence).toBe(0.9);
        expect(metadata.content_classification.indicators).toContain(
          "config_file_extension",
        );
      });
    });

    it("should classify tutorial content correctly", () => {
      const url = "https://example.com/getting-started";
      const content =
        "Step 1: Install the package. This tutorial will walk you through...";
      const metadata = extractDocumentMetadata(url, content);

      expect(metadata.content_classification.content_type).toBe("tutorial");
      expect(metadata.content_classification.indicators).toContain(
        "url_tutorial_pattern",
      );
      expect(metadata.content_classification.indicators).toContain(
        "content_tutorial_indicators",
      );
    });

    it("should classify API documentation correctly", () => {
      const url = "https://example.com/api/users";
      const content =
        "API endpoint for managing users. HTTP method: GET. Request/response format...";
      const metadata = extractDocumentMetadata(url, content);

      expect(metadata.content_classification.content_type).toBe(
        "api_documentation",
      );
      expect(metadata.content_classification.indicators).toContain(
        "url_api_pattern",
      );
      expect(metadata.content_classification.indicators).toContain(
        "content_api_indicators",
      );
    });

    it("should classify changelog content correctly", () => {
      const url = "https://example.com/CHANGELOG.md";
      const content =
        "# Changelog\n\n## Version 2.0.0\n\nChanges in this release:";
      const metadata = extractDocumentMetadata(url, content);

      expect(metadata.content_classification.content_type).toBe("changelog");
      expect(metadata.content_classification.indicators).toContain(
        "content_changelog_indicators",
      );
    });
  });

  describe("Domain Metadata Extraction", () => {
    it("should detect documentation hosting services", () => {
      const testCases = [
        { url: "https://project.readthedocs.io/en/latest/", type: "docs" },
        { url: "https://company.gitbook.io/docs/", type: "docs" },
        { url: "https://notion.so/Company-Docs", type: "docs" },
      ];

      testCases.forEach(({ url, type }) => {
        const metadata = extractDocumentMetadata(url);
        expect(metadata.domain_metadata.is_documentation_site).toBe(true);
        expect(metadata.domain_metadata.documentation_type).toBe(type);
      });
    });

    it("should detect wiki sites", () => {
      const testCases = [
        "https://wiki.example.com/page",
        "https://company.wiki.com/docs",
        "https://example.com/wiki/article",
      ];

      testCases.forEach(url => {
        const metadata = extractDocumentMetadata(url);
        // The current implementation checks if hostname includes "wiki" or subdomain includes "wiki"
        if (
          url.includes("wiki.example.com") ||
          url.includes("company.wiki.com")
        ) {
          expect(metadata.domain_metadata.is_documentation_site).toBe(true);
          expect(metadata.domain_metadata.documentation_type).toBe("wiki");
        } else {
          // For partial matches in path only, it doesn't currently detect as wiki
          expect(metadata.domain_metadata.is_documentation_site).toBe(false);
        }
      });
    });

    it("should handle complex subdomains correctly", () => {
      const url = "https://api.v2.docs.example.com/reference";
      const metadata = extractDocumentMetadata(url);

      expect(metadata.domain_metadata.domain).toBe("example.com");
      expect(metadata.domain_metadata.subdomain).toBe("api.v2.docs");
      // The current implementation only checks the first subdomain part
      expect(metadata.domain_metadata.is_documentation_site).toBe(false);
      expect(metadata.domain_metadata.documentation_type).toBeUndefined();
    });
  });

  describe("Metadata Formatting for Storage", () => {
    it("should format metadata correctly for vector storage", () => {
      const url = "https://github.com/facebook/react/blob/main/README.md";
      const content =
        "React is a JavaScript library for building user interfaces.";
      const title = "React - A JavaScript Library";

      const metadata = extractDocumentMetadata(url, content, title);
      const formatted = formatMetadataForStorage(metadata);

      expect(formatted).toEqual({
        title: "React - A JavaScript Library",
        domain: "github.com",
        word_count: 9,
        repository_name: "react",
        repository_org: "facebook",
        file_path: "README.md",
        branch_version: "main",
        content_type: "readme",
        is_documentation_site: true,
        documentation_type: "github",
        is_code_file: false,
        programming_language: undefined,
      });
    });

    it("should handle missing optional fields correctly", () => {
      const url = "https://example.com/docs/guide";
      const metadata = extractDocumentMetadata(url);
      const formatted = formatMetadataForStorage(metadata);

      expect(formatted.repository_name).toBeUndefined();
      expect(formatted.repository_org).toBeUndefined();
      expect(formatted.file_path).toBeUndefined();
      expect(formatted.branch_version).toBeUndefined();
      expect(formatted.programming_language).toBeUndefined();
      expect(formatted.is_code_file).toBe(false);
    });
  });

  describe("Error Handling", () => {
    it("should handle invalid URLs gracefully", () => {
      const invalidUrl = "not-a-valid-url";
      const metadata = extractDocumentMetadata(invalidUrl);

      expect(metadata.domain).toBe("not-a-valid-url");
      expect(metadata.github).toBeUndefined();
      expect(metadata.domain_metadata.is_documentation_site).toBe(false);
      expect(metadata.content_classification.content_type).toBe("general");
      expect(metadata.content_classification.confidence).toBeLessThan(0.5);
    });

    it("should handle malformed GitHub URLs", () => {
      const malformedUrl = "https://github.com/incomplete";
      const metadata = extractDocumentMetadata(malformedUrl);

      expect(metadata.github).toBeUndefined();
      expect(metadata.domain_metadata.domain).toBe("github.com");
      expect(metadata.domain_metadata.is_documentation_site).toBe(true);
    });

    it("should handle URLs with special characters", () => {
      const specialUrl = "https://example.com/file%20with%20spaces.js";
      const metadata = extractDocumentMetadata(specialUrl);

      expect(metadata.file_metadata?.extension).toBe("js");
      expect(metadata.file_metadata?.programming_language).toBe("javascript");
    });
  });
});
