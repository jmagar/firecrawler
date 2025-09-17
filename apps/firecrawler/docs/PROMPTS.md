# Firecrawler MCP Prompts Documentation

This document describes the Model Context Protocol (MCP) prompts available in the Firecrawler server. Prompts provide AI assistants with reusable, parameterized templates for LLM interactions during content extraction and processing operations.

## Overview

Firecrawler MCP prompts enable:

- **Structured Data Extraction**: Templates for extracting specific data types
- **Content Analysis**: Prompts for analyzing and categorizing content
- **Data Validation**: Templates for validating extracted information
- **Custom Processing**: Customizable prompts for specific use cases

All prompts support parameterization and can be combined with JSON schemas for structured output validation.

## Available Prompts

### Data Extraction Prompts

#### `firecrawler://prompts/extract/product-info`
Extract product information from e-commerce pages.

**Parameters**:
- `fields` (array): Specific fields to extract (default: ["name", "price", "description"])
- `currency` (string): Expected currency format (default: "USD")
- `includeImages` (boolean): Include image URLs (default: false)

**Template**:
```
Extract product information from the following webpage content. Focus on accuracy and only extract explicitly stated information.

Required fields: {fields}
Currency format: {currency}
Include images: {includeImages}

Return the information in a structured JSON format with the following schema:
- name: Product name (string)
- price: Numerical price value (number)
- description: Product description (string)
- availability: Stock status (boolean)
- images: Array of image URLs (array, if includeImages is true)

Content:
{content}
```

**Usage Example**:
```json
{
  "name": "get_prompt",
  "arguments": {
    "name": "firecrawler://prompts/extract/product-info",
    "arguments": {
      "fields": ["name", "price", "description", "availability"],
      "currency": "EUR",
      "includeImages": true
    }
  }
}
```

#### `firecrawler://prompts/extract/contact-info`
Extract contact information from business websites.

**Parameters**:
- `types` (array): Contact types to extract (default: ["email", "phone", "address"])
- `format` (string): Address format preference (default: "structured")
- `validateEmails` (boolean): Validate email format (default: true)

**Template**:
```
Extract contact information from the following webpage content. Be precise and only extract explicitly mentioned contact details.

Contact types to extract: {types}
Address format: {format}
Validate emails: {validateEmails}

Return structured JSON with:
- email: Valid email address (string)
- phone: Phone number with country code (string)
- address: Physical address (string or object based on format)
- website: Official website URL (string)
- socialMedia: Social media profiles (object)

Content:
{content}
```

#### `firecrawler://prompts/extract/event-details`
Extract event information from event pages.

**Parameters**:
- `timeZone` (string): Expected timezone (default: "UTC")
- `includeRecurring` (boolean): Include recurring event info (default: false)
- `extractSpeakers` (boolean): Extract speaker information (default: true)

**Template**:
```
Extract event details from the following content. Focus on dates, times, location, and key event information.

Timezone: {timeZone}
Include recurring info: {includeRecurring}
Extract speakers: {extractSpeakers}

Return JSON with:
- title: Event title (string)
- date: Event date in ISO format (string)
- time: Event time (string)
- location: Event location (string)
- description: Event description (string)
- speakers: Array of speaker names (array, if extractSpeakers is true)
- registrationUrl: Registration link (string)
- recurring: Recurrence pattern (object, if includeRecurring is true)

Content:
{content}
```

#### `firecrawler://prompts/extract/article-metadata`
Extract metadata from news articles and blog posts.

**Parameters**:
- `includeKeywords` (boolean): Extract keywords/tags (default: true)
- `extractSentiment` (boolean): Analyze sentiment (default: false)
- `wordCountLimit` (integer): Maximum words for summary (default: 150)

**Template**:
```
Extract article metadata from the following content. Focus on journalistic elements and content structure.

Include keywords: {includeKeywords}
Extract sentiment: {extractSentiment}
Summary word limit: {wordCountLimit}

Return JSON with:
- title: Article title (string)
- author: Author name(s) (string or array)
- publishDate: Publication date in ISO format (string)
- category: Article category (string)
- summary: Brief summary (string, max {wordCountLimit} words)
- keywords: Relevant keywords (array, if includeKeywords is true)
- sentiment: Overall sentiment (string, if extractSentiment is true)
- wordCount: Approximate word count (number)

Content:
{content}
```

### Content Analysis Prompts

#### `firecrawler://prompts/analysis/content-categorization`
Categorize content into predefined categories.

**Parameters**:
- `categories` (array): Available categories (required)
- `confidence` (boolean): Include confidence scores (default: false)
- `multiLabel` (boolean): Allow multiple categories (default: false)

**Template**:
```
Categorize the following content into one or more of the provided categories. Analyze the content thoroughly to determine the most appropriate classification.

Available categories: {categories}
Include confidence: {confidence}
Multiple categories allowed: {multiLabel}

Return JSON with:
- primaryCategory: Main category (string)
- secondaryCategories: Additional categories (array, if multiLabel is true)
- confidence: Confidence score 0-1 (number, if confidence is true)
- reasoning: Brief explanation for categorization (string)

Content:
{content}
```

#### `firecrawler://prompts/analysis/language-detection`
Detect the primary language(s) of content.

**Parameters**:
- `detectMultiple` (boolean): Detect multiple languages (default: false)
- `includeDialects` (boolean): Include dialect information (default: false)

**Template**:
```
Detect the primary language of the following content. Analyze text patterns, character sets, and linguistic features.

Detect multiple languages: {detectMultiple}
Include dialects: {includeDialects}

Return JSON with:
- primaryLanguage: ISO 639-1 language code (string)
- languages: All detected languages with confidence (array, if detectMultiple is true)
- dialect: Specific dialect information (string, if includeDialects is true)
- confidence: Detection confidence 0-1 (number)

Content:
{content}
```

#### `firecrawler://prompts/analysis/content-quality`
Assess content quality and readability.

**Parameters**:
- `metrics` (array): Quality metrics to assess (default: ["readability", "accuracy", "completeness"])
- `target_audience` (string): Target audience level (default: "general")

**Template**:
```
Assess the quality of the following content based on the specified metrics. Provide objective analysis and scoring.

Quality metrics: {metrics}
Target audience: {target_audience}

Return JSON with:
- overallScore: Overall quality score 0-10 (number)
- readabilityScore: Readability assessment 0-10 (number)
- accuracyScore: Information accuracy 0-10 (number)
- completenessScore: Content completeness 0-10 (number)
- recommendations: Improvement suggestions (array)
- targetAudienceMatch: Audience appropriateness 0-10 (number)

Content:
{content}
```

### Data Validation Prompts

#### `firecrawler://prompts/validation/schema-compliance`
Validate extracted data against expected schema.

**Parameters**:
- `schema` (object): JSON schema for validation (required)
- `strictMode` (boolean): Strict schema compliance (default: true)
- `reportMissing` (boolean): Report missing required fields (default: true)

**Template**:
```
Validate the following extracted data against the provided schema. Check for compliance, data types, and required fields.

Schema: {schema}
Strict mode: {strictMode}
Report missing fields: {reportMissing}

Return JSON with:
- isValid: Schema compliance status (boolean)
- errors: Validation errors (array)
- warnings: Non-critical issues (array)
- missingFields: Required fields not found (array, if reportMissing is true)
- correctedData: Schema-compliant version of data (object)

Data to validate:
{data}
```

#### `firecrawler://prompts/validation/data-consistency`
Check consistency across multiple data points.

**Parameters**:
- `fields` (array): Fields to check for consistency (required)
- `tolerance` (string): Tolerance level for inconsistencies (default: "medium")

**Template**:
```
Check data consistency across the provided data points. Look for contradictions, inconsistencies, and anomalies.

Fields to check: {fields}
Tolerance level: {tolerance}

Return JSON with:
- consistencyScore: Overall consistency 0-10 (number)
- inconsistencies: Found inconsistencies (array)
- recommendations: Data cleaning suggestions (array)
- reliabilityScore: Data reliability assessment 0-10 (number)

Data points:
{data}
```

### Custom Processing Prompts

#### `firecrawler://prompts/custom/summarization`
Generate summaries with customizable parameters.

**Parameters**:
- `length` (string): Summary length (default: "medium", options: "short", "medium", "long")
- `style` (string): Writing style (default: "neutral", options: "neutral", "formal", "casual")
- `focus` (array): Aspects to emphasize (default: ["main_points"])

**Template**:
```
Create a summary of the following content with the specified parameters. Maintain accuracy while condensing information.

Summary length: {length}
Writing style: {style}
Focus areas: {focus}

Length guidelines:
- Short: 1-2 sentences
- Medium: 1-2 paragraphs
- Long: 3-4 paragraphs

Return JSON with:
- summary: Generated summary (string)
- keyPoints: Main points extracted (array)
- wordCount: Summary word count (number)
- originalLength: Original content word count (number)
- compressionRatio: Reduction percentage (number)

Content:
{content}
```

#### `firecrawler://prompts/custom/translation`
Translate content with context preservation.

**Parameters**:
- `targetLanguage` (string): Target language code (required)
- `preserveFormatting` (boolean): Maintain original formatting (default: true)
- `culturalAdaptation` (boolean): Adapt cultural references (default: false)

**Template**:
```
Translate the following content to {targetLanguage}. Maintain meaning, context, and tone while ensuring natural expression in the target language.

Target language: {targetLanguage}
Preserve formatting: {preserveFormatting}
Cultural adaptation: {culturalAdaptation}

Return JSON with:
- translatedText: Translated content (string)
- originalLanguage: Detected source language (string)
- confidence: Translation confidence 0-1 (number)
- notes: Translation notes or cultural adaptations (array)

Content to translate:
{content}
```

## Prompt Usage Patterns

### Basic Prompt Usage

```json
{
  "name": "get_prompt",
  "arguments": {
    "name": "firecrawler://prompts/extract/product-info",
    "arguments": {
      "fields": ["name", "price", "description"],
      "currency": "USD"
    }
  }
}
```

### Combining with Extract Tool

```json
{
  "name": "extract",
  "arguments": {
    "urls": ["https://store.example.com/product/123"],
    "prompt": "firecrawler://prompts/extract/product-info",
    "promptArgs": {
      "fields": ["name", "price", "description", "availability"],
      "currency": "EUR",
      "includeImages": true
    },
    "schema": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "price": {"type": "number"},
        "description": {"type": "string"},
        "availability": {"type": "boolean"}
      }
    }
  }
}
```

### Custom Prompt Creation

```json
{
  "name": "create_prompt",
  "arguments": {
    "name": "custom-extraction",
    "template": "Extract {fields} from the content. Format: {format}. Content: {content}",
    "parameters": {
      "fields": {"type": "array", "required": true},
      "format": {"type": "string", "default": "json"}
    }
  }
}
```

## Prompt Customization

### Parameter Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text parameter | `"USD"`, `"formal"` |
| `boolean` | True/false flag | `true`, `false` |
| `integer` | Numeric value | `150`, `5` |
| `array` | List of values | `["email", "phone"]` |
| `object` | Structured data | `{"min": 0, "max": 10}` |

### Default Values

All parameters support default values for easier usage:

```json
{
  "parameter_name": {
    "type": "string",
    "default": "default_value",
    "required": false
  }
}
```

### Validation Rules

Parameters can include validation constraints:

```json
{
  "word_limit": {
    "type": "integer",
    "default": 150,
    "minimum": 50,
    "maximum": 500
  },
  "language": {
    "type": "string",
    "enum": ["en", "es", "fr", "de"],
    "default": "en"
  }
}
```

## Best Practices

### Prompt Selection

1. **Specific Over Generic**: Use specialized prompts for better results
2. **Parameter Tuning**: Adjust parameters based on content type and requirements
3. **Schema Integration**: Combine prompts with JSON schemas for structured output
4. **Testing Iterations**: Test prompts with sample content before bulk operations

### Performance Optimization

1. **Parameter Caching**: Cache commonly used parameter combinations
2. **Template Optimization**: Use efficient template structures
3. **Batch Processing**: Apply the same prompt to multiple content pieces
4. **Result Validation**: Validate prompt outputs for consistency

### Error Handling

1. **Parameter Validation**: Validate parameters before prompt execution
2. **Fallback Prompts**: Have simpler prompts as fallbacks
3. **Output Validation**: Check prompt outputs against expected formats
4. **Error Recovery**: Handle LLM errors gracefully with retry logic

### Custom Prompt Development

1. **Clear Instructions**: Write explicit, unambiguous prompt text
2. **Parameter Design**: Design flexible, reusable parameters
3. **Output Format**: Specify clear output format requirements
4. **Testing Coverage**: Test with diverse content types

## Prompt Templates

### Template Syntax

Prompts use standard template syntax with parameter substitution:

```
Extract {field_name} from the content.
Format the output as {output_format}.
Include {include_fields} and exclude {exclude_fields}.

Content:
{content}
```

### Conditional Blocks

Templates support conditional content based on parameters:

```
Extract information from the content.
{#if include_metadata}
Include metadata such as author, date, and source.
{/if}
{#if validate_data}
Validate all extracted data for accuracy.
{/if}

Content:
{content}
```

### Loops and Arrays

Process array parameters in templates:

```
Extract the following fields: 
{#each fields as field}
- {field}
{/each}

Apply these constraints:
{#each constraints as constraint}
- {constraint.type}: {constraint.value}
{/each}
```

## Integration Examples

### With Vector Search

```json
{
  "name": "firerag",
  "arguments": {
    "query": "product pricing information",
    "responseMode": "synthesized",
    "synthesisPrompt": "firecrawler://prompts/extract/product-info",
    "synthesisArgs": {
      "fields": ["name", "price"],
      "currency": "USD"
    }
  }
}
```

### With Batch Processing

```python
# Python example for batch extraction with prompts
batch_urls = ["url1", "url2", "url3"]
prompt_config = {
    "name": "firecrawler://prompts/extract/article-metadata",
    "arguments": {
        "includeKeywords": True,
        "wordCountLimit": 100
    }
}

for url in batch_urls:
    extract_result = await client.call_tool("extract", {
        "urls": [url],
        "prompt": prompt_config["name"],
        "promptArgs": prompt_config["arguments"]
    })
```

### With Custom Validation

```json
{
  "name": "extract",
  "arguments": {
    "urls": ["https://example.com"],
    "prompt": "firecrawler://prompts/extract/contact-info",
    "validationPrompt": "firecrawler://prompts/validation/schema-compliance",
    "validationArgs": {
      "schema": {
        "type": "object",
        "properties": {
          "email": {"type": "string", "format": "email"},
          "phone": {"type": "string", "pattern": "^\\+?[1-9]\\d{1,14}$"}
        }
      }
    }
  }
}
```

## Troubleshooting

### Common Issues

**Parameter Errors**:
- Check parameter types and required fields
- Verify parameter names match template variables
- Ensure array parameters are properly formatted

**Template Rendering Errors**:
- Validate template syntax
- Check for missing parameter values
- Verify conditional logic

**Output Format Issues**:
- Ensure LLM understands output requirements
- Validate JSON schema compatibility
- Check for conflicting instructions

**Performance Issues**:
- Optimize prompt complexity
- Reduce parameter overhead
- Cache frequent parameter combinations

For additional support and advanced customization, see the [main documentation](../README.md) and the FastMCP prompts guide at `docs/fastmcp/prompts.md`.