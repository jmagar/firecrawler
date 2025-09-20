/**
 * Enhanced markdown cleanup for removing common navigation and boilerplate text
 * that persists after HTML-based filtering
 */

export interface CleanupOptions {
  removeNavigation?: boolean;
  removeSearchHints?: boolean;
  removeTableOfContents?: boolean;
  removePagination?: boolean;
  removeLanguageSelectors?: boolean;
  customPatterns?: RegExp[];
}

const DEFAULT_OPTIONS: CleanupOptions = {
  removeNavigation: true,
  removeSearchHints: true,
  removeTableOfContents: true,
  removePagination: true,
  removeLanguageSelectors: true,
};

/**
 * Common navigation patterns found in documentation sites
 */
const NAVIGATION_PATTERNS = [
  // Skip to content variations
  /\[Skip to [Cc]ontent\]\(#[^\)]*\)/gi,

  // Search UI elements
  /Search\.{3,}/gi,
  /Search\s*…/gi,
  /Type to search/gi,
  /Search the docs?/gi,
  /Search documentation/gi,

  // Keyboard shortcuts
  /Ctrl\s*\+?\s*K/gi,
  /⌘\s*K/gi,
  /Press\s+.*\s+to\s+search/gi,

  // Navigation elements
  /^\s*Navigation\s*$/gm,
  /^\s*Main Navigation\s*$/gm,
  /^\s*Site Navigation\s*$/gm,

  // Table of contents
  /^\s*On this page:?\s*$/gm,
  /^\s*Table of [Cc]ontents:?\s*$/gm,
  /^\s*Contents:?\s*$/gm,
  /^\s*In this article:?\s*$/gm,

  // Pagination
  /^\s*(<\s*)?Previous\s*$/gm,
  /^\s*Next\s*(>\s*)?$/gm,
  /^\s*←\s*Previous\s*$/gm,
  /^\s*Next\s*→\s*$/gm,
  /\[Previous\]\([^\)]*\)/gi,
  /\[Next\]\([^\)]*\)/gi,

  // Language selectors
  /^\s*Select language\s*$/gm,
  /^\s*Choose language\s*$/gm,
  /^\s*Language:\s*$/gm,

  // Common UI elements
  /^\s*Close\s*$/gm,
  /^\s*Open menu\s*$/gm,
  /^\s*Toggle navigation\s*$/gm,
  /^\s*Menu\s*$/gm,

  // Documentation site patterns
  /^\s*Docs\s*$/gm,
  /^\s*Documentation\s*$/gm,
  /^\s*API Reference\s*$/gm,
  /^\s*Getting Started\s*$/gm,
  /^\s*Quick Start\s*$/gm,

  // Social/sharing
  /^\s*Share\s*$/gm,
  /^\s*Tweet\s*$/gm,
  /^\s*Share on Twitter\s*$/gm,

  // Version selectors
  /^\s*v\d+\.\d+\.\d+\s*$/gm,
  /^\s*Version:?\s*$/gm,
  /^\s*Select version\s*$/gm,
];

/**
 * Patterns for removing entire navigation blocks
 */
const BLOCK_PATTERNS = [
  // Navigation lists (like "Home > Docs > API")
  /^(\s*\*\s*)?(Home|Documentation|Docs|API|Reference|Guide|Tutorial)(\s*[>\|\/]\s*(Home|Documentation|Docs|API|Reference|Guide|Tutorial))+\s*$/gm,

  // Breadcrumb patterns
  /^\s*\[?Home\]?\s*[›>\/]\s*.+$/gm,

  // Empty navigation sections
  /^#{1,6}\s*(Navigation|Menu|Contents?|On this page)\s*\n\s*$/gm,
];

/**
 * Clean up markdown content by removing navigation and boilerplate text
 */
export function cleanMarkdownContent(
  markdown: string,
  options: CleanupOptions = DEFAULT_OPTIONS,
): string {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  let cleaned = markdown;

  // Remove navigation patterns
  if (opts.removeNavigation) {
    for (const pattern of NAVIGATION_PATTERNS) {
      cleaned = cleaned.replace(pattern, "");
    }

    for (const pattern of BLOCK_PATTERNS) {
      cleaned = cleaned.replace(pattern, "");
    }
  }

  // Apply custom patterns
  if (opts.customPatterns && opts.customPatterns.length > 0) {
    for (const pattern of opts.customPatterns) {
      cleaned = cleaned.replace(pattern, "");
    }
  }

  // Clean up multiple consecutive newlines left after removals
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");

  // Remove leading/trailing whitespace
  cleaned = cleaned.trim();

  return cleaned;
}

/**
 * Analyze markdown content for remaining navigation elements
 * Useful for debugging and finding patterns that need to be added
 */
export function detectRemainingNavigation(markdown: string): string[] {
  const suspiciousPatterns = [
    /Search\.\.\./gi,
    /Ctrl\s*K/gi,
    /On this page/gi,
    /Previous.*Next/gi,
    /Navigation/gi,
    /Table of contents/gi,
    /Select language/gi,
    /Toggle.*menu/gi,
    /^#{1,6}\s*$/gm, // Empty headers
    /^\*\s*$/gm, // Empty list items
  ];

  const found: string[] = [];

  for (const pattern of suspiciousPatterns) {
    const matches = markdown.match(pattern);
    if (matches) {
      found.push(...matches);
    }
  }

  return [...new Set(found)]; // Remove duplicates
}

/**
 * Check if markdown content likely contains significant navigation elements
 */
export function hasNavigationContent(markdown: string): boolean {
  const navigationScore = detectRemainingNavigation(markdown).length;
  return navigationScore > 2; // Threshold can be adjusted
}
