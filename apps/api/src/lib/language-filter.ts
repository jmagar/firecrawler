/**
 * Language filtering module for automatic content filtering by language
 *
 * This module provides functionality to generate URL exclusion patterns
 * based on a specified allowed language, helping to filter out content
 * in other languages during crawling operations.
 */

// Language pattern definitions for URL-based language detection
const LANGUAGE_PATTERNS = {
  // European languages
  en: ["en", "english", "eng"], // English
  es: [
    "es",
    "spanish",
    "esp",
    "es-es",
    "es-mx",
    "es-ar",
    "es-co",
    "es-cl",
    "es-pe",
    "es-ve",
  ], // Spanish
  fr: ["fr", "french", "fra", "fr-fr", "fr-ca", "fr-be", "fr-ch"], // French
  de: ["de", "german", "deu", "de-de", "de-at", "de-ch"], // German
  it: ["it", "italian", "ita", "it-it"], // Italian
  pt: ["pt", "portuguese", "por", "pt-pt", "pt-br"], // Portuguese
  ru: ["ru", "russian", "rus"], // Russian
  nl: ["nl", "dutch", "nld", "nl-nl", "nl-be"], // Dutch
  sv: ["sv", "swedish", "swe", "sv-se"], // Swedish
  no: ["no", "norwegian", "nor", "nb", "nn"], // Norwegian
  da: ["da", "danish", "dan", "da-dk"], // Danish
  fi: ["fi", "finnish", "fin", "fi-fi"], // Finnish
  pl: ["pl", "polish", "pol", "pl-pl"], // Polish
  tr: ["tr", "turkish", "tur", "tr-tr"], // Turkish
  he: ["he", "hebrew", "heb", "he-il", "iw"], // Hebrew
  uk: ["ukrainian", "ukr", "uk-ua", "ua"], // Ukrainian (avoid bare 'uk' to reduce UK false positives)
  cs: ["cs", "czech", "ces", "cze", "cs-cz"], // Czech
  hu: ["hu", "hungarian", "hun", "hu-hu"], // Hungarian

  // Asian languages
  ja: ["ja", "japanese", "jpn", "ja-jp"], // Japanese
  ko: ["ko", "korean", "kor", "ko-kr"], // Korean
  zh: ["zh", "chinese", "zho", "zh-cn", "zh-tw", "zh-hk", "cn", "tw"], // Chinese
  hi: ["hi", "hindi", "hin", "hi-in"], // Hindi
  th: ["th", "thai", "tha", "th-th"], // Thai
  vi: ["vi", "vietnamese", "vie", "vi-vn"], // Vietnamese
  id: ["id", "indonesian", "ind", "id-id"], // Indonesian
  ms: ["ms", "malay", "msa", "ms-my"], // Malay

  // Middle Eastern/African languages
  ar: ["ar", "arabic", "ara", "ar-sa", "ar-eg", "ar-ae", "ar-ma"], // Arabic
} as const;

// Common URL patterns that indicate language-specific content
// Made more specific to reduce false positives with English content
const URL_LANGUAGE_INDICATORS = [
  // Path-based patterns - more specific with word boundaries
  "/{{lang}}/", // /es/, /fr/, etc.
  "/{{lang}}-", // /es-mx/, /fr-ca/, etc.
  "/{{lang}}_", // /es_MX/, /fr_CA/, etc.

  // Subdomain patterns - only match at start of subdomain
  "^(?:https?:)?//{{lang}}\\.", // http(s)://es.example.com

  // Query parameter patterns - exact parameter matches
  "\\?lang={{lang}}$", // ?lang=es (end of URL)
  "\\?lang={{lang}}&", // ?lang=es&other=value
  "\\?lang={{lang}}(#|$)", // ?lang=es#section
  "&lang={{lang}}$", // &lang=es (end of URL)
  "&lang={{lang}}&", // &lang=es&other=value
  "&lang={{lang}}(#|$)", // &lang=es#section
  "\\?language={{lang}}$", // ?language=es
  "\\?language={{lang}}&", // ?language=es&other=value
  "\\?language={{lang}}(#|$)", // ?language=es#section
  "&language={{lang}}$", // &language=es
  "&language={{lang}}&", // &language=es&other=value
  "&language={{lang}}(#|$)", // &language=es#section
  "\\?locale={{lang}}$", // ?locale=es
  "\\?locale={{lang}}&", // ?locale=es&other=value
  "\\?locale={{lang}}(#|$)", // ?locale=es#section
  "&locale={{lang}}$", // &locale=es
  "&locale={{lang}}&", // &locale=es&other=value
  "&locale={{lang}}(#|$)", // &locale=es#section
  "\\?hl={{lang}}$", // ?hl=es
  "\\?hl={{lang}}&", // ?hl=es&other=value
  "\\?hl={{lang}}(#|$)", // ?hl=es#section
  "&hl={{lang}}$", // &hl=es
  "&hl={{lang}}&", // &hl=es&other=value
  "&hl={{lang}}(#|$)", // &hl=es#section

  // Fragment patterns
  "#{{lang}}$", // #es (end of URL)
  "#lang={{lang}}$", // #lang=es (end of URL)
] as const;

// Pattern cache to avoid recompiling RegExp objects on every URL check
const PATTERN_CACHE = new Map<string, RegExp[]>();

// Set of supported language codes for O(1) lookup performance
const SUPPORTED_LANGUAGE_SET = new Set(Object.keys(LANGUAGE_PATTERNS));

/**
 * Gets cached compiled regexes for a given allowed language
 *
 * @param allowedLanguage - The language code to allow
 * @returns Array of compiled RegExp objects for URL exclusion
 */
function getLanguageExcludeRegexes(allowedLanguage: string): RegExp[] {
  // Normalize cache key to avoid redundant entries for language variants
  const cacheKey = allowedLanguage.toLowerCase().split(/[-_]/)[0].trim();

  // Use the cache if available
  if (PATTERN_CACHE.has(cacheKey)) {
    return PATTERN_CACHE.get(cacheKey)!;
  }

  // Get patterns and compile them once
  const patterns = getLanguageExcludePatterns(allowedLanguage);
  const regexes: RegExp[] = [];

  for (const pattern of patterns) {
    try {
      // Use case-insensitive and unicode flags for better pattern matching
      const regex = new RegExp(pattern, "iu");
      regexes.push(regex);
    } catch (error) {
      // Skip invalid patterns at compile time rather than runtime
      continue;
    }
  }

  // Cache the compiled regexes using normalized key
  PATTERN_CACHE.set(cacheKey, regexes);
  return regexes;
}

/**
 * Generates URL exclusion patterns for languages other than the allowed language
 *
 * @param allowedLanguage - The language code to allow (e.g., 'en', 'es', 'fr')
 * @returns Array of regex patterns to exclude URLs containing other language indicators
 */
export function getLanguageExcludePatterns(allowedLanguage: string): string[] {
  // Normalize the allowed language to lowercase
  const normalizedAllowed = allowedLanguage.toLowerCase().trim();

  // If 'all' is specified or empty, don't filter anything
  if (!normalizedAllowed || normalizedAllowed === "all") {
    return [];
  }

  // Extract base language code from region-tagged language (e.g., 'en-US' → 'en')
  const allowedBase = normalizedAllowed.split(/[-_]/)[0].toLowerCase().trim();

  // Get all language codes except the allowed one
  const excludedLanguages = new Set<string>();

  for (const [langCode, patterns] of Object.entries(LANGUAGE_PATTERNS)) {
    if (langCode !== allowedBase) {
      // Add all patterns for this language to the exclusion set
      patterns.forEach(pattern => excludedLanguages.add(pattern));
    }
  }

  // Build regex patterns for each excluded language
  const excludePatterns = new Set<string>();

  for (const excludedLang of Array.from(excludedLanguages)) {
    // Skip if this excluded language is actually a variant of our allowed language
    // (e.g., if allowed is 'en', don't exclude 'en-us')
    if (
      excludedLang.startsWith(allowedBase + "-") ||
      excludedLang.startsWith(allowedBase + "_")
    ) {
      continue;
    }

    // Generate patterns for each URL indicator type
    for (const indicator of URL_LANGUAGE_INDICATORS) {
      const pattern = indicator.replace(
        /\{\{lang\}\}/g,
        escapeRegex(excludedLang),
      );
      excludePatterns.add(pattern);
    }
  }

  return Array.from(excludePatterns);
}

/**
 * Checks if a URL should be excluded based on language filtering patterns
 *
 * @param url - The URL to check
 * @param allowedLanguage - The allowed language code
 * @returns true if the URL should be excluded, false otherwise
 */
export function shouldExcludeUrl(
  url: string,
  allowedLanguage: string,
): boolean {
  const excludeRegexes = getLanguageExcludeRegexes(allowedLanguage);

  if (excludeRegexes.length === 0) {
    return false;
  }

  // Test URL against each cached regex
  for (const regex of excludeRegexes) {
    if (regex.test(url)) {
      return true;
    }
  }

  return false;
}

/**
 * Filters an array of URLs to exclude those that don't match the allowed language
 *
 * @param urls - Array of URLs to filter
 * @param allowedLanguage - The allowed language code
 * @returns Object with included and excluded URL arrays
 */
export function filterUrlsByLanguage(
  urls: string[],
  allowedLanguage: string,
): { included: string[]; excluded: string[] } {
  const included: string[] = [];
  const excluded: string[] = [];

  for (const url of urls) {
    if (shouldExcludeUrl(url, allowedLanguage)) {
      excluded.push(url);
    } else {
      included.push(url);
    }
  }

  return { included, excluded };
}

/**
 * Escapes special regex characters in a string
 *
 * @param str - String to escape
 * @returns Escaped string safe for use in regex
 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Gets supported language codes
 *
 * @returns Array of supported language codes
 */
export function getSupportedLanguages(): string[] {
  return Array.from(SUPPORTED_LANGUAGE_SET);
}

/**
 * Clears the language pattern cache for better cache management in tests
 *
 * @param langBase - Optional base language to clear specific entry, clears all if not provided
 */
export function clearLanguagePatternCache(langBase?: string): void {
  if (!langBase) {
    return PATTERN_CACHE.clear();
  }
  PATTERN_CACHE.delete(langBase.toLowerCase().split(/[-_]/)[0].trim());
}

/**
 * Checks if a language code is supported
 *
 * @param languageCode - Language code to check
 * @returns true if supported, false otherwise
 */
export function isLanguageSupported(languageCode: string): boolean {
  const base = languageCode.toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LANGUAGE_SET.has(base);
}
