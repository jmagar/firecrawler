import {
  extractGitHubMetadata,
  classifyContentType,
  extractDocumentMetadata,
} from "../../lib/metadata-extraction";
import { describe, it, expect } from "@jest/globals";

describe("GitHub Metadata Extraction", () => {
  describe("extractGitHubMetadata", () => {
    describe("Edge URL parsing", () => {
      test.each([
        {
          description: "should handle extensionless files in blob URLs",
          url: "https://github.com/org/repo/blob/main/LICENSE",
          expected: {
            file_path: "LICENSE",
            repository_org: "org",
            repository_name: "repo",
            branch_version: "main",
            is_raw_file: false,
            file_extension: undefined,
          },
        },
        {
          description: "should handle Makefile in blob URLs",
          url: "https://github.com/microsoft/typescript/blob/main/Makefile",
          expected: {
            file_path: "Makefile",
            repository_org: "microsoft",
            repository_name: "typescript",
            branch_version: "main",
            is_raw_file: false,
            file_extension: undefined,
          },
        },
        {
          description: "should handle GitHub repo root URLs without file_path",
          url: "https://github.com/facebook/react",
          expected: {
            file_path: undefined,
            repository_org: "facebook",
            repository_name: "react",
            branch_version: undefined,
            is_raw_file: false,
            file_extension: undefined,
          },
        },
        {
          description: "should handle raw.githubusercontent.com URLs",
          url: "https://raw.githubusercontent.com/vercel/next.js/canary/package.json",
          expected: {
            file_path: "package.json",
            repository_org: "vercel",
            repository_name: "next.js",
            branch_version: "canary",
            is_raw_file: true,
            file_extension: "json",
          },
        },
        {
          description:
            "should handle raw.githubusercontent.com URLs with extensionless files",
          url: "https://raw.githubusercontent.com/torvalds/linux/master/Kconfig",
          expected: {
            file_path: "Kconfig",
            repository_org: "torvalds",
            repository_name: "linux",
            branch_version: "master",
            is_raw_file: true,
            file_extension: undefined,
          },
        },
        {
          description: "should handle nested directory paths in blob URLs",
          url: "https://github.com/nodejs/node/blob/main/lib/internal/bootstrap/node.js",
          expected: {
            file_path: "lib/internal/bootstrap/node.js",
            repository_org: "nodejs",
            repository_name: "node",
            branch_version: "main",
            is_raw_file: false,
            file_extension: "js",
          },
        },
        {
          description: "should handle github.com raw paths",
          url: "https://github.com/org/repo/raw/main/path/to/file.txt",
          expected: {
            file_path: "to/file.txt",
            repository_org: "org",
            repository_name: "repo",
            branch_version: "main/path",
            is_raw_file: false,
            file_extension: "txt",
          },
        },
        {
          description: "should handle URL-encoded characters in paths",
          url: "https://github.com/org/repo/blob/main/file%20with%20spaces.md",
          expected: {
            file_path: "file with spaces.md",
            repository_org: "org",
            repository_name: "repo",
            branch_version: "main",
            is_raw_file: false,
            file_extension: "md",
          },
        },
      ])("$description", ({ url, expected }) => {
        const result = extractGitHubMetadata(url);
        expect(result?.file_path).toBe(expected.file_path);
        expect(result?.repository_org).toBe(expected.repository_org);
        expect(result?.repository_name).toBe(expected.repository_name);
        expect(result?.branch_version).toBe(expected.branch_version);
        expect(result?.is_raw_file).toBe(expected.is_raw_file);
        expect(result?.file_extension).toBe(expected.file_extension);
      });

      it("should return null for non-GitHub URLs", () => {
        const result = extractGitHubMetadata("https://example.com/some/path");
        expect(result).toBeNull();
      });
    });
  });

  describe("Content Classification", () => {
    describe("Content-based classifications", () => {
      it("should classify installation guides", () => {
        const content = `
          # Installation
          
          To install this package, run:
          
          npm install my-package
          
          Or with pip:
          
          pip install my-package
        `;

        // URL filename pattern takes precedence over /docs/ path
        const result = classifyContentType(
          "https://example.com/docs/install",
          content,
        );
        expect(result.content_type).toBe("installation_guide");
        expect(result.confidence).toBe(0.85);
        expect(result.indicators).toContain("filename_installation");
        expect(result.indicators).toContain("content_installation_indicators");
      });

      it("should classify installation guides with neutral URL", () => {
        const content = `
          # Installation
          
          To install this package, run:
          
          npm install my-package
          
          Or with pip:
          
          pip install my-package
        `;

        // Neutral URL allows content-based classification
        const result = classifyContentType(
          "https://example.com/install",
          content,
        );
        expect(result.content_type).toBe("installation_guide");
        expect(result.confidence).toBe(0.85);
        expect(result.indicators).toContain("filename_installation");
        expect(result.indicators).toContain("content_installation_indicators");
      });

      it("should classify changelog content", () => {
        const content = `
          # Changelog
          
          ## Version 2.0.0
          
          ### Changes
          - Added new features
          - Fixed bugs
          
          ## Version 1.9.0
          
          Release notes for version 1.9.0
        `;

        const result = classifyContentType(
          "https://example.com/changelog",
          content,
        );
        expect(result.content_type).toBe("changelog");
        expect(result.confidence).toBeGreaterThan(0.7);
        expect(result.indicators).toContain("content_changelog_indicators");
      });

      it("should classify tutorial content", () => {
        const content = `
          # Getting Started Tutorial
          
          Welcome to this walkthrough!
          
          ## Step 1
          First, let's set up the project.
          
          ## Step 2  
          Now we'll configure the settings.
        `;

        const result = classifyContentType(
          "https://example.com/tutorial",
          content,
        );
        expect(result.content_type).toBe("tutorial");
        expect(result.confidence).toBeGreaterThan(0.7);
        expect(result.indicators).toContain("content_tutorial_indicators");
      });

      it("should classify API documentation content", () => {
        const content = `
          # API Reference
          
          ## Endpoints
          
          ### GET /api/users
          
          HTTP method: GET
          
          Request/Response format:
          - Request: application/json
          - Response: array of user objects
        `;

        const result = classifyContentType(
          "https://example.com/api/docs",
          content,
        );
        expect(result.content_type).toBe("api_documentation");
        expect(result.confidence).toBeGreaterThan(0.7);
        expect(result.indicators).toContain("content_api_indicators");
      });

      it("should handle mixed content indicators", () => {
        const content = `
          # Installation and API Tutorial
          
          ## Step 1: Install
          npm install my-package
          
          ## Step 2: API Usage
          Here's the API endpoint you'll use.
        `;

        const result = classifyContentType(
          "https://example.com/docs/",
          content,
        );
        // URL classification takes precedence, but content adds indicators
        expect(result.content_type).toBe("documentation");
        expect(result.indicators).toContain("documentation_pattern");
        expect(result.indicators).toContain("content_installation_indicators");
        expect(result.indicators.length).toBeGreaterThan(1);
      });
    });

    describe("URL-based classifications", () => {
      it("should classify README files", () => {
        const result = classifyContentType(
          "https://github.com/org/repo/blob/main/README.md",
        );
        expect(result.content_type).toBe("readme");
        expect(result.confidence).toBe(0.95);
        expect(result.indicators).toContain("filename_readme");
      });

      it("should classify extensionless README files", () => {
        const result = classifyContentType(
          "https://github.com/org/repo/blob/main/readme",
        );
        expect(result.content_type).toBe("readme");
        expect(result.confidence).toBe(0.95);
        expect(result.indicators).toContain("filename_readme");
      });

      it("should classify configuration files", () => {
        const result = classifyContentType(
          "https://github.com/org/repo/blob/main/package.json",
        );
        expect(result.content_type).toBe("configuration");
        expect(result.confidence).toBe(0.9);
        expect(result.indicators).toContain("config_file_extension");
      });

      it("should classify code files", () => {
        const result = classifyContentType(
          "https://github.com/org/repo/blob/main/src/index.ts",
        );
        expect(result.content_type).toBe("code");
        expect(result.confidence).toBe(0.9);
        expect(result.indicators).toContain("code_file_extension");
      });
    });
  });

  describe("extractDocumentMetadata integration", () => {
    it("should extract complete metadata for GitHub LICENSE file", () => {
      const url =
        "https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt";
      const content = "MIT License\n\nCopyright (c) Microsoft Corporation.";

      const result = extractDocumentMetadata(url, content, "MIT License");

      expect(result.title).toBe("MIT License");
      expect(result.github?.repository_org).toBe("microsoft");
      expect(result.github?.repository_name).toBe("TypeScript");
      expect(result.github?.file_path).toBe("LICENSE.txt");
      expect(result.github?.is_raw_file).toBe(false);
      expect(result.domain_metadata.is_documentation_site).toBe(true);
      expect(result.domain_metadata.documentation_type).toBe("github");
      expect(result.word_count).toBeGreaterThan(0);
    });

    it("should extract metadata for raw GitHub file", () => {
      const url = "https://raw.githubusercontent.com/nodejs/node/main/Makefile";
      const content = "# Node.js Makefile\nall:\n\tmake build";

      const result = extractDocumentMetadata(url, content);

      expect(result.github?.repository_org).toBe("nodejs");
      expect(result.github?.repository_name).toBe("node");
      expect(result.github?.file_path).toBe("Makefile");
      expect(result.github?.is_raw_file).toBe(true);
      expect(result.github?.file_extension).toBeUndefined();
      expect(result.file_metadata?.is_code_file).toBe(true); // Makefile is detected as code
    });

    it("should extract metadata for GitHub repo root", () => {
      const url = "https://github.com/facebook/react";
      const content =
        "# React\nA JavaScript library for building user interfaces.";

      const result = extractDocumentMetadata(url, content, "React");

      expect(result.title).toBe("React");
      expect(result.github?.repository_org).toBe("facebook");
      expect(result.github?.repository_name).toBe("react");
      // extractDocumentMetadata fills in file_path from URL fallback for repo root
      expect(result.github?.file_path).toBe("react");
      expect(result.github?.is_raw_file).toBe(false);
      expect(result.domain_metadata.documentation_type).toBe("github");
      // File metadata gets extracted from URL fallback (last segment = "react")
      expect(result.file_metadata?.is_code_file).toBe(false);
    });
  });
});
