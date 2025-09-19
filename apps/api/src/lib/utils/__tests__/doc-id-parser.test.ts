import { parseDocIdFromDocUrl } from "../doc-id-parser";

describe("parseDocIdFromDocUrl", () => {
  describe("Google Cloud Storage URLs", () => {
    it("should extract doc ID from GCS URL with query parameters", () => {
      const url =
        "https://storage.googleapis.com/bucket/a/b/c.json?sig=abc123&exp=123456";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });

    it("should extract doc ID from GCS URL without query parameters", () => {
      const url = "https://storage.googleapis.com/bucket/path/to/document.pdf";
      expect(parseDocIdFromDocUrl(url)).toBe("document.pdf");
    });

    it("should extract doc ID from nested GCS path", () => {
      const url =
        "https://storage.googleapis.com/my-bucket/deep/nested/path/file.html";
      expect(parseDocIdFromDocUrl(url)).toBe("file.html");
    });
  });

  describe("Regular URLs", () => {
    it("should extract doc ID from simple URL", () => {
      const url = "https://example.com/c.json";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });

    it("should extract doc ID from URL with path", () => {
      const url = "https://example.com/api/v1/documents/report.pdf";
      expect(parseDocIdFromDocUrl(url)).toBe("report.pdf");
    });

    it("should handle URL with both query and fragment", () => {
      const url =
        "https://example.com/files/doc.txt?version=1&format=raw#section1";
      expect(parseDocIdFromDocUrl(url)).toBe("doc.txt");
    });

    it("should handle URLs with redundant slashes", () => {
      const url = "https://example.com//a//b///c.json";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });

    it("should extract doc ID from file:// URL", () => {
      const url = "file:///var/tmp/report.txt";
      expect(parseDocIdFromDocUrl(url)).toBe("report.txt");
    });
  });

  describe("GS (Google Storage) URLs", () => {
    it("should extract doc ID from gs:// URL", () => {
      const url = "gs://bucket/a/b/c.json";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });

    it("should extract doc ID from gs:// URL with fragment", () => {
      const url = "gs://bucket/a/b/c.json#fragment";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });

    it("should extract doc ID from gs:// URL with query parameters", () => {
      const url = "gs://bucket/a/b/c.json?sig=abc";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });
  });

  describe("URL encoding", () => {
    it("should preserve URL-encoded filename", () => {
      const url = "https://example.com/encoded%20file.json";
      expect(parseDocIdFromDocUrl(url)).toBe("encoded%20file.json");
    });

    it("should preserve complex URL-encoded filename", () => {
      const url = "https://example.com/My%20Document%20%281%29.pdf";
      expect(parseDocIdFromDocUrl(url)).toBe("My%20Document%20%281%29.pdf");
    });

    it("should preserve URL encoding with query parameters", () => {
      const url =
        "https://storage.googleapis.com/bucket/path/file%20with%20spaces.html?sig=xyz";
      expect(parseDocIdFromDocUrl(url)).toBe("file%20with%20spaces.html");
    });

    it("should handle malformed URL encoding gracefully", () => {
      const url = "https://example.com/malformed%encoding.txt";
      expect(parseDocIdFromDocUrl(url)).toBe("malformed%encoding.txt");
    });
  });

  describe("Edge cases", () => {
    it("should return empty string for malformed URL", () => {
      const url = "malformed";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should return empty string for URL ending with slash", () => {
      const url = "https://example.com/";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should return empty string for URL with only path separator", () => {
      const url = "https://example.com/path/";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should return empty string for root URL", () => {
      const url = "https://example.com";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should handle empty string input", () => {
      const url = "";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should handle URL with only query parameters", () => {
      const url = "https://example.com/?query=value";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should handle URL with only fragment", () => {
      const url = "https://example.com/#fragment";
      expect(parseDocIdFromDocUrl(url)).toBe("");
    });

    it("should handle relative path-like strings", () => {
      const url = "a/b/c.json";
      expect(parseDocIdFromDocUrl(url)).toBe("c.json");
    });
  });

  describe("Real-world examples", () => {
    it("should handle typical Firebase storage URL", () => {
      const url =
        "https://firebasestorage.googleapis.com/v0/b/bucket/o/documents%2Freport.pdf?alt=media&token=abc123";
      expect(parseDocIdFromDocUrl(url)).toBe("documents%2Freport.pdf");
    });

    it("should handle typical S3-like URL", () => {
      const url =
        "https://mybucket.s3.amazonaws.com/folder/subfolder/document.docx";
      expect(parseDocIdFromDocUrl(url)).toBe("document.docx");
    });

    it("should handle CDN URL with version", () => {
      const url = "https://cdn.example.com/assets/v2.1/styles.css?v=20230901";
      expect(parseDocIdFromDocUrl(url)).toBe("styles.css");
    });
  });
});
