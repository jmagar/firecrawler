import {
  cleanMarkdownContent,
  detectRemainingNavigation,
  hasNavigationContent,
} from "../markdown-cleanup";

describe("Markdown Cleanup", () => {
  describe("cleanMarkdownContent", () => {
    it("should remove search UI elements", () => {
      const input = `
# Main Content

Search...

Search the docs

Ctrl K

This is the actual content we want to keep.

Search documentation
      `;

      const result = cleanMarkdownContent(input);

      expect(result).not.toContain("Search...");
      expect(result).not.toContain("Search the docs");
      expect(result).not.toContain("Ctrl K");
      expect(result).not.toContain("Search documentation");
      expect(result).toContain("Main Content");
      expect(result).toContain("This is the actual content we want to keep.");
    });

    it("should remove navigation elements", () => {
      const input = `
Navigation

On this page

## Actual Content

Previous
Next

Table of Contents

More real content here.
      `;

      const result = cleanMarkdownContent(input);

      expect(result).not.toContain("Navigation");
      expect(result).not.toContain("On this page");
      expect(result).not.toContain("Previous");
      expect(result).not.toContain("Next");
      expect(result).not.toContain("Table of Contents");
      expect(result).toContain("Actual Content");
      expect(result).toContain("More real content here.");
    });

    it("should remove skip to content links", () => {
      const input = `
[Skip to Content](#main)
[Skip to content](#content)

# Real Content Here
      `;

      const result = cleanMarkdownContent(input);

      expect(result).not.toContain("Skip to Content");
      expect(result).not.toContain("Skip to content");
      expect(result).toContain("Real Content Here");
    });

    it("should remove pagination links", () => {
      const input = `
# Article Title

[Previous](../previous-page)
[Next](../next-page)

← Previous
Next →

Article content goes here.
      `;

      const result = cleanMarkdownContent(input);

      expect(result).not.toContain("[Previous]");
      expect(result).not.toContain("[Next]");
      expect(result).not.toContain("← Previous");
      expect(result).not.toContain("Next →");
      expect(result).toContain("Article Title");
      expect(result).toContain("Article content goes here.");
    });

    it("should clean up multiple newlines after removal", () => {
      const input = `
# Title

Navigation


Search...



Content here
      `;

      const result = cleanMarkdownContent(input);

      // Should not have more than 2 consecutive newlines
      expect(result).not.toMatch(/\n{3,}/);
      expect(result).toContain("Title");
      expect(result).toContain("Content here");
    });

    it("should apply custom patterns when provided", () => {
      const input = `
Custom pattern to remove
Keep this content
Another custom thing
      `;

      const result = cleanMarkdownContent(input, {
        customPatterns: [/Custom pattern to remove/g, /Another custom thing/g],
      });

      expect(result).not.toContain("Custom pattern to remove");
      expect(result).not.toContain("Another custom thing");
      expect(result).toContain("Keep this content");
    });
  });

  describe("detectRemainingNavigation", () => {
    it("should detect navigation patterns", () => {
      const input = `
Search...
Ctrl K
On this page
Navigation
      `;

      const detected = detectRemainingNavigation(input);

      expect(detected).toContain("Search...");
      expect(detected).toContain("Ctrl K");
      expect(detected).toContain("On this page");
      expect(detected).toContain("Navigation");
    });

    it("should return unique patterns", () => {
      const input = `
Search...
Search...
Navigation
Navigation
      `;

      const detected = detectRemainingNavigation(input);

      expect(detected).toEqual(["Search...", "Navigation"]);
    });
  });

  describe("hasNavigationContent", () => {
    it("should return true when multiple navigation elements present", () => {
      const input = `
Search...
Ctrl K
On this page
Navigation
      `;

      expect(hasNavigationContent(input)).toBe(true);
    });

    it("should return false when few or no navigation elements", () => {
      const input = `
# Regular Article

This is just normal content without navigation elements.
      `;

      expect(hasNavigationContent(input)).toBe(false);
    });
  });
});
