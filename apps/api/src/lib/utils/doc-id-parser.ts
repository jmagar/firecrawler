/**
 * Parses a document ID from a document URL by extracting the last path segment.
 *
 * This function performs the following operations:
 * 1. Strips query parameters and fragments from the URL
 * 2. Extracts the last non-empty path segment
 * 3. Returns the segment as-is (preserves URL encoding for compatibility with GCS)
 * 4. Returns empty string if no valid segment exists or on any error
 *
 * Note: URL encoding is preserved in the returned value to maintain compatibility
 * with Google Cloud Storage and other systems that expect encoded document IDs.
 *
 * @param url - The document URL to parse (e.g., "https://storage.googleapis.com/bucket/path/file.json?sig=xyz")
 * @returns The extracted document ID (e.g., "file.json"), or empty string if extraction fails
 *
 * @example
 * ```typescript
 * parseDocIdFromDocUrl("https://storage.googleapis.com/bucket/a/b/c.json?sig=abc") // Returns "c.json"
 * parseDocIdFromDocUrl("https://example.com/encoded%20file.json") // Returns "encoded%20file.json"
 * parseDocIdFromDocUrl("gs://bucket/a/b/c.json#fragment") // Returns "c.json"
 * parseDocIdFromDocUrl("malformed-url") // Returns ""
 * parseDocIdFromDocUrl("https://example.com/") // Returns ""
 * ```
 */
export function parseDocIdFromDocUrl(url: string): string {
  try {
    // Parse URL to handle query parameters and fragments properly
    const urlObj = new URL(url);
    const pathname = urlObj.pathname;

    // Check if pathname ends with "/" - indicates directory, not file
    if (pathname === "/" || pathname.endsWith("/")) {
      return "";
    }

    const parts = pathname.split("/").filter(Boolean);

    if (parts.length === 0) {
      return "";
    }

    const lastSegment = parts[parts.length - 1];

    // Return the segment as-is to preserve URL encoding for GCS compatibility
    return lastSegment;
  } catch {
    // If URL parsing fails, check if it looks like a valid URL pattern
    // Only proceed with fallback if the string contains protocol-like pattern or slashes
    if (!url.includes("://") && !url.includes("/")) {
      return "";
    }

    try {
      const parts = url.split("/").filter(Boolean);
      if (parts.length === 0) {
        return "";
      }

      let lastSegment = parts[parts.length - 1];

      // Remove query parameters and fragments manually
      lastSegment = lastSegment.split("?")[0];
      lastSegment = lastSegment.split("#")[0];

      if (!lastSegment) {
        return "";
      }

      // Return the segment as-is to preserve URL encoding for GCS compatibility
      return lastSegment;
    } catch {
      return "";
    }
  }
}
