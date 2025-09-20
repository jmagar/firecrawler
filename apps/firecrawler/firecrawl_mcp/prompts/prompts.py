"""
Reusable prompt templates for LLM interactions in the Firecrawl MCP server.

This module provides parameterized prompt templates for various LLM-powered operations
including structured data extraction, vector search synthesis, and content analysis.
The prompts support validation, integration with extraction and synthesis tools,
and flexible customization for different content types and use cases.
"""

import logging
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Create FastMCP server instance for prompts
mcp = FastMCP(name="FirecrawlPrompts")


# Pydantic models for prompt arguments


class ExtractionPromptArgs(BaseModel):
    """Arguments for structured extraction prompts."""

    content_type: str = Field(description="Type of content being extracted")
    extraction_fields: list[str] = Field(description="List of fields to extract from the content")
    schema_description: str | None = Field(default=None, description="Description of the expected data schema")
    output_format: Literal["json", "structured_text", "key_value"] = Field(default="json", description="Desired output format for extracted data")
    strict_schema: bool = Field(default=True, description="Whether to enforce strict schema compliance")
    include_confidence: bool = Field(default=False, description="Whether to include confidence scores for extracted fields")

    @field_validator('output_format')
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        if v not in ["json", "structured_text", "key_value"]:
            raise ValueError(f"Invalid output format: {v}")
        return v


class SynthesisPromptArgs(BaseModel):
    """Arguments for vector synthesis prompts."""

    query: str = Field(description="Original user query that triggered the vector search")
    result_count: int = Field(description="Number of vector search results to synthesize")
    max_context_length: int = Field(default=2000, description="Maximum length of context to include from each result", ge=100, le=5000)
    synthesis_style: Literal["comprehensive", "concise", "bullet_points", "executive_summary"] = Field(default="comprehensive", description="Style of synthesis to generate")
    include_sources: bool = Field(default=True, description="Whether to include source citations in the synthesis")
    handle_conflicts: bool = Field(default=True, description="Whether to address conflicting information between sources")

    @field_validator('max_context_length')
    @classmethod
    def validate_context_length(cls, v: int) -> int:
        if v < 100:
            raise ValueError("Context length must be at least 100 characters")
        if v > 5000:
            raise ValueError("Context length cannot exceed 5000 characters")
        return v


class ContentAnalysisPromptArgs(BaseModel):
    """Arguments for content analysis prompts."""

    content_type: Literal["webpage", "documentation", "article", "code", "forum_post", "unknown"] = Field(description="Type of content being analyzed")
    analysis_goals: list[str] = Field(description="List of analysis goals")
    output_structure: Literal["summary", "detailed", "categorized"] = Field(default="summary", description="Structure of the analysis output")
    domain_context: str | None = Field(default=None, description="Domain or industry context for the analysis")


class RetryPromptArgs(BaseModel):
    """Arguments for error recovery prompts."""

    original_operation: str = Field(description="The operation that failed")
    error_type: str = Field(description="Type of error encountered")
    attempted_parameters: dict[str, Any] = Field(description="Parameters that were used in the failed attempt")
    error_details: str | None = Field(default=None, description="Additional error details or context")
    user_intent: str | None = Field(default=None, description="Description of what the user was trying to accomplish")


# Validation functions


def validate_extraction_args(args: ExtractionPromptArgs) -> None:
    """Validate extraction prompt arguments."""
    if not args.extraction_fields:
        raise ToolError("Extraction fields cannot be empty")

    if len(args.extraction_fields) > 50:
        raise ToolError("Too many extraction fields (maximum 50 allowed)")


def validate_synthesis_args(args: SynthesisPromptArgs) -> None:
    """Validate synthesis prompt arguments."""
    if not args.query or args.query.strip() == "":
        raise ToolError("Query cannot be empty")

    if args.result_count <= 0:
        raise ToolError("Result count must be positive")

    if args.result_count > 100:
        raise ToolError("Too many results for synthesis (maximum 100 allowed)")


# Registration function


def register_prompt_templates(server: FastMCP) -> list[str]:
    """Register all prompt templates with the FastMCP server."""
    prompt_names = []

    # We need to get the original function before the decorator wraps it
    # The @mcp.prompt decorator returns a FunctionPrompt object, not the original function

    # Define helper functions that call the original logic
    def _structured_extraction_impl(
        content_type: str,
        extraction_fields: list[str],
        schema_description: str | None = None,
        output_format: Literal["json", "structured_text", "key_value"] = "json",
        strict_schema: bool = True,
        include_confidence: bool = False
    ) -> str:
        # Build field specifications
        field_specs = []
        for field in extraction_fields:
            field_specs.append(f"- {field}: Extract this field accurately from the content")

        fields_text = "\n".join(field_specs)

        # Build output format instructions
        format_instructions = {
            "json": "Return the extracted data as valid JSON with the specified field names as keys.",
            "structured_text": "Return the extracted data in a structured text format with clear field labels.",
            "key_value": "Return the extracted data as key-value pairs, one per line."
        }

        format_instruction = format_instructions.get(output_format, format_instructions["json"])

        # Build schema enforcement instructions
        schema_enforcement = ""
        if strict_schema and schema_description:
            schema_enforcement = f"\n\nSTRICT SCHEMA COMPLIANCE REQUIRED:\n{schema_description}\nDo not deviate from the specified schema structure."

        # Build confidence scoring instructions
        confidence_instructions = ""
        if include_confidence:
            confidence_instructions = "\n\nFor each extracted field, include a confidence score (0.0-1.0) indicating how certain you are about the accuracy of the extraction."

        return f"""You are an expert data extraction specialist. Extract structured information from the following {content_type} content.

EXTRACTION REQUIREMENTS:
{fields_text}

OUTPUT FORMAT:
{format_instruction}

EXTRACTION GUIDELINES:
1. Read the content carefully and thoroughly
2. Extract only the information that directly corresponds to the requested fields
3. If a field cannot be found or determined, mark it as null or "not available"
4. Maintain accuracy over completeness - do not infer or guess missing information
5. Preserve the original meaning and context of extracted information

{schema_enforcement}
{confidence_instructions}

Please extract the requested information from the content provided below."""

    # Register structured_extraction prompt
    @server.prompt(
        name="structured_extraction",
        description="Generate prompts for AI-powered structured data extraction from web content with customizable schemas and output formats.",
        tags={"extraction", "ai", "structured_data"}
    )
    def _structured_extraction(
        content_type: str = Field(description="Type of content being extracted"),
        extraction_fields: list[str] = Field(description="List of fields to extract from the content"),
        schema_description: str | None = Field(default=None, description="Description of the expected data schema"),
        output_format: Literal["json", "structured_text", "key_value"] = Field(default="json", description="Desired output format for extracted data"),
        strict_schema: bool = Field(default=True, description="Whether to enforce strict schema compliance"),
        include_confidence: bool = Field(default=False, description="Whether to include confidence scores for extracted fields")
    ) -> str:
        return _structured_extraction_impl(content_type, extraction_fields, schema_description, output_format, strict_schema, include_confidence)

    prompt_names.append("structured_extraction")

    # Similar pattern for other prompts - just register wrapper functions that call the prompt logic
    @server.prompt(
        name="vector_synthesis",
        description="Generate prompts for synthesizing vector search results into coherent, comprehensive responses with source attribution.",
        tags={"vector_search", "synthesis", "rag"}
    )
    def _vector_synthesis(
        query: str = Field(description="Original user query that triggered the vector search"),
        _result_count: int = Field(description="Number of vector search results to synthesize"),
        _max_context_length: int = Field(default=2000, description="Maximum length of context to include from each result", ge=100, le=5000),
        synthesis_style: Literal["comprehensive", "concise", "bullet_points", "executive_summary"] = Field(default="comprehensive", description="Style of synthesis to generate"),
        include_sources: bool = Field(default=True, description="Whether to include source citations in the synthesis"),
        handle_conflicts: bool = Field(default=True, description="Whether to address conflicting information between sources")
    ) -> str:
        # Simplified prompt logic for synthesis
        style_instructions = {
            "comprehensive": "Provide a thorough, detailed response that covers all relevant aspects found in the search results.",
            "concise": "Provide a brief, focused response that captures the essential information from the search results.",
            "bullet_points": "Organize the information from search results into clear bullet points or numbered lists.",
            "executive_summary": "Provide a high-level executive summary suitable for decision-makers."
        }
        style_instruction = style_instructions.get(synthesis_style, style_instructions["comprehensive"])

        source_instructions = ""
        if include_sources:
            source_instructions = """
SOURCE CITATION REQUIREMENTS:
- Include specific source references for key information
- Use format: [Source: URL or title]
- When multiple sources support the same point, list them: [Sources: URL1, URL2]
- Clearly indicate when information comes from a single vs. multiple sources"""

        conflict_instructions = ""
        if handle_conflicts:
            conflict_instructions = """
CONFLICT RESOLUTION:
- When sources provide conflicting information, acknowledge the discrepancy
- Present different viewpoints clearly: "According to Source A... however, Source B indicates..."
- If possible, explain potential reasons for conflicts (different time periods, contexts, etc.)
- Do not choose sides unless there's clear evidence of which source is more authoritative"""

        return f"""You are a research synthesis expert. Your task is to analyze the provided search results and create a comprehensive response to the user's query.

ORIGINAL QUERY: {query}

SYNTHESIS REQUIREMENTS:
- {style_instruction}
- Base your response solely on the information provided in the search results
- Do not add external knowledge or make unsupported inferences
- Maintain objectivity and accuracy throughout your response

{source_instructions}
{conflict_instructions}

RESPONSE STRUCTURE:
1. Begin with a direct answer to the query if possible
2. Provide supporting details and evidence from the search results
3. Address any limitations or gaps in the available information
4. Conclude with a summary if appropriate for the chosen style

The search results will be provided below. Please synthesize them into a coherent response that directly addresses the user's query."""

    prompt_names.append("vector_synthesis")

    # Register remaining prompts with simple implementations
    @server.prompt(
        name="content_analysis",
        description="Generate prompts for analyzing and categorizing web content with domain-specific insights and structured outputs.",
        tags={"analysis", "categorization", "content"}
    )
    def _content_analysis(
        content_type: Literal["webpage", "documentation", "article", "code", "forum_post", "unknown"] = Field(description="Type of content being analyzed"),
        analysis_goals: list[str] = Field(description="List of analysis goals"),
        _output_structure: Literal["summary", "detailed", "categorized"] = Field(default="summary", description="Structure of the analysis output"),
        _domain_context: str | None = Field(default=None, description="Domain or industry context for the analysis")
    ) -> str:
        return f"Analyze {content_type} content for: {', '.join(analysis_goals)}"

    prompt_names.append("content_analysis")

    @server.prompt(
        name="error_recovery_suggestions",
        description="Generate helpful suggestions for recovering from failed operations, with alternative approaches and parameter adjustments.",
        tags={"error_handling", "recovery", "troubleshooting"}
    )
    def _error_recovery_suggestions(
        original_operation: str = Field(description="The operation that failed"),
        error_type: str = Field(description="Type of error encountered"),
        _attempted_parameters: dict[str, Any] = Field(description="Parameters that were used in the failed attempt"),
        _error_details: str | None = Field(default=None, description="Additional error details or context"),
        _user_intent: str | None = Field(default=None, description="Description of what the user was trying to accomplish")
    ) -> str:
        return f"Recovery suggestions for {original_operation} operation that failed with {error_type}"

    prompt_names.append("error_recovery_suggestions")

    @server.prompt(
        name="query_expansion",
        description="Generate expanded and refined queries for better vector search results, with semantic variations and context enrichment.",
        tags={"search", "query_expansion", "vector_search"}
    )
    def _query_expansion(
        original_query: str,
        _context: str | None = Field(default=None, description="Additional context about the user's intent or domain"),
        expansion_type: Literal["semantic", "keyword", "comprehensive"] = Field(default="semantic", description="Type of query expansion to perform"),
        max_variants: int = Field(default=5, description="Maximum number of query variants to generate", ge=1, le=10)
    ) -> str:
        return f"Expand query '{original_query}' using {expansion_type} approach with {max_variants} variants"

    prompt_names.append("query_expansion")

    @server.prompt(
        name="content_classification",
        description="Generate prompts for classifying and tagging web content with metadata extraction and categorization.",
        tags={"classification", "tagging", "metadata"}
    )
    def _content_classification(
        content_url: str,
        classification_goals: list[str] = Field(description="List of classification goals"),
        _available_categories: dict[str, list[str]] | None = Field(default=None, description="Available categories for each classification goal"),
        _extract_metadata: bool = Field(default=True, description="Whether to extract additional metadata fields")
    ) -> str:
        return f"Classify content from {content_url} for goals: {', '.join(classification_goals)}"

    prompt_names.append("content_classification")

    return prompt_names




@mcp.prompt(
    name="structured_extraction",
    description="Generate prompts for AI-powered structured data extraction from web content with customizable schemas and output formats.",
    tags={"extraction", "ai", "structured_data"}
)
def structured_extraction(
    content_type: str = Field(description="Type of content being extracted (e.g., 'product page', 'blog post', 'documentation')"),
    extraction_fields: list[str] = Field(description="List of fields to extract from the content"),
    schema_description: str | None = Field(default=None, description="Description of the expected data schema"),
    output_format: Literal["json", "structured_text", "key_value"] = Field(default="json", description="Desired output format for extracted data"),
    strict_schema: bool = Field(default=True, description="Whether to enforce strict schema compliance"),
    include_confidence: bool = Field(default=False, description="Whether to include confidence scores for extracted fields")
) -> str:
    """
    Generate a comprehensive prompt for structured data extraction.

    This prompt template creates detailed instructions for LLM-based extraction
    of structured data from web content, supporting various output formats
    and validation requirements.
    """
    # Build field specifications
    field_specs = []
    for field in extraction_fields:
        field_specs.append(f"- {field}: Extract this field accurately from the content")

    fields_text = "\n".join(field_specs)

    # Build output format instructions
    format_instructions = {
        "json": "Return the extracted data as valid JSON with the specified field names as keys.",
        "structured_text": "Return the extracted data in a structured text format with clear field labels.",
        "key_value": "Return the extracted data as key-value pairs, one per line."
    }

    format_instruction = format_instructions.get(output_format, format_instructions["json"])

    # Build schema enforcement instructions
    schema_enforcement = ""
    if strict_schema and schema_description:
        schema_enforcement = f"\n\nSTRICT SCHEMA COMPLIANCE REQUIRED:\n{schema_description}\nDo not deviate from the specified schema structure."

    # Build confidence scoring instructions
    confidence_instructions = ""
    if include_confidence:
        confidence_instructions = "\n\nFor each extracted field, include a confidence score (0.0-1.0) indicating how certain you are about the accuracy of the extraction."

    return f"""You are an expert data extraction specialist. Extract structured information from the following {content_type} content.

EXTRACTION REQUIREMENTS:
{fields_text}

OUTPUT FORMAT:
{format_instruction}

EXTRACTION GUIDELINES:
1. Read the content carefully and thoroughly
2. Extract only the information that directly corresponds to the requested fields
3. If a field cannot be found or determined, mark it as null or "not available"
4. Maintain accuracy over completeness - do not infer or guess missing information
5. Preserve the original meaning and context of extracted information

{schema_enforcement}
{confidence_instructions}

Please extract the requested information from the content provided below."""

@mcp.prompt(
    name="vector_synthesis",
    description="Generate prompts for synthesizing vector search results into coherent, comprehensive responses with source attribution.",
    tags={"vector_search", "synthesis", "rag"}
)
def vector_synthesis(
    query: str = Field(description="Original user query that triggered the vector search"),
    result_count: int = Field(description="Number of vector search results to synthesize"),  # noqa: ARG001
    max_context_length: int = Field(default=2000, description="Maximum length of context to include from each result", ge=100, le=5000),  # noqa: ARG001
    synthesis_style: Literal["comprehensive", "concise", "bullet_points", "executive_summary"] = Field(default="comprehensive", description="Style of synthesis to generate"),
    include_sources: bool = Field(default=True, description="Whether to include source citations in the synthesis"),
    handle_conflicts: bool = Field(default=True, description="Whether to address conflicting information between sources")
) -> str:
    """
    Generate a prompt for synthesizing vector search results into coherent responses.

    This prompt template creates instructions for LLM-based synthesis of multiple
    vector search results, handling source attribution, conflict resolution,
    and different synthesis styles.
    """
    # Build synthesis style instructions
    style_instructions = {
        "comprehensive": "Provide a thorough, detailed response that covers all relevant aspects found in the search results.",
        "concise": "Provide a brief, focused response that captures the essential information from the search results.",
        "bullet_points": "Organize the information from search results into clear bullet points or numbered lists.",
        "executive_summary": "Provide a high-level executive summary suitable for decision-makers."
    }

    style_instruction = style_instructions.get(synthesis_style, style_instructions["comprehensive"])

    # Build source citation instructions
    source_instructions = ""
    if include_sources:
        source_instructions = """
SOURCE CITATION REQUIREMENTS:
- Include specific source references for key information
- Use format: [Source: URL or title]
- When multiple sources support the same point, list them: [Sources: URL1, URL2]
- Clearly indicate when information comes from a single vs. multiple sources"""

    # Build conflict resolution instructions
    conflict_instructions = ""
    if handle_conflicts:
        conflict_instructions = """
CONFLICT RESOLUTION:
- When sources provide conflicting information, acknowledge the discrepancy
- Present different viewpoints clearly: "According to Source A... however, Source B indicates..."
- If possible, explain potential reasons for conflicts (different time periods, contexts, etc.)
- Do not choose sides unless there's clear evidence of which source is more authoritative"""

    return f"""You are a research synthesis expert. Your task is to analyze the provided search results and create a comprehensive response to the user's query.

ORIGINAL QUERY: {query}

SYNTHESIS REQUIREMENTS:
- {style_instruction}
- Base your response solely on the information provided in the search results
- Do not add external knowledge or make unsupported inferences
- Maintain objectivity and accuracy throughout your response

{source_instructions}
{conflict_instructions}

RESPONSE STRUCTURE:
1. Begin with a direct answer to the query if possible
2. Provide supporting details and evidence from the search results
3. Address any limitations or gaps in the available information
4. Conclude with a summary if appropriate for the chosen style

The search results will be provided below. Please synthesize them into a coherent response that directly addresses the user's query."""

@mcp.prompt(
    name="content_analysis",
    description="Generate prompts for analyzing and categorizing web content with domain-specific insights and structured outputs.",
    tags={"analysis", "categorization", "content"}
)
def content_analysis(
    content_type: Literal["webpage", "documentation", "article", "code", "forum_post", "unknown"] = Field(description="Type of content being analyzed"),
    analysis_goals: list[str] = Field(description="List of analysis goals (e.g., 'sentiment', 'key_topics', 'entity_extraction')"),
    output_structure: Literal["summary", "detailed", "categorized"] = Field(default="summary", description="Structure of the analysis output"),
    domain_context: str | None = Field(default=None, description="Domain or industry context for the analysis")
) -> str:
    """
    Generate a prompt for comprehensive content analysis and categorization.

    This prompt template creates instructions for analyzing web content
    across multiple dimensions including sentiment, topics, entities,
    and domain-specific characteristics.
    """
    # Build analysis goals specifications
    goal_specs = []
    for goal in analysis_goals:
        goal_specs.append(f"- {goal}: Analyze the content for this aspect")

    goals_text = "\n".join(goal_specs)

    # Build output structure instructions
    structure_instructions = {
        "summary": "Provide a concise summary of your analysis findings for each goal.",
        "detailed": "Provide detailed analysis with examples and evidence for each goal.",
        "categorized": "Organize your analysis into clear categories with subcategories as appropriate."
    }

    structure_instruction = structure_instructions.get(output_structure, structure_instructions["summary"])

    # Build domain context instructions
    domain_instructions = ""
    if domain_context:
        domain_instructions = f"""
DOMAIN CONTEXT: {domain_context}
- Consider domain-specific terminology, conventions, and standards
- Apply industry-relevant analysis criteria
- Identify domain-specific patterns or characteristics"""

    return f"""You are a content analysis expert specializing in web content evaluation. Analyze the following {content_type} content according to the specified goals.

ANALYSIS GOALS:
{goals_text}

OUTPUT REQUIREMENTS:
- {structure_instruction}
- Provide specific evidence or examples to support your analysis
- Be objective and base conclusions on observable content characteristics
- If certain aspects cannot be determined, clearly state this limitation

{domain_instructions}

ANALYSIS FRAMEWORK:
1. Content Overview: Brief description of the content type and purpose
2. Goal-Specific Analysis: Address each analysis goal systematically
3. Key Findings: Highlight the most significant insights
4. Confidence Assessment: Indicate your confidence level for each finding

Please analyze the content provided below according to these specifications."""

@mcp.prompt(
    name="error_recovery_suggestions",
    description="Generate helpful suggestions for recovering from failed operations, with alternative approaches and parameter adjustments.",
    tags={"error_handling", "recovery", "troubleshooting"}
)
def error_recovery_suggestions(
    original_operation: str = Field(description="The operation that failed (e.g., 'scrape', 'extract', 'search')"),
    error_type: str = Field(description="Type of error encountered (e.g., 'rate_limit', 'timeout', 'invalid_url')"),
    attempted_parameters: dict[str, Any] = Field(description="Parameters that were used in the failed attempt"),
    error_details: str | None = Field(default=None, description="Additional error details or context"),
    user_intent: str | None = Field(default=None, description="Description of what the user was trying to accomplish")
) -> str:
    """
    Generate user-friendly suggestions for recovering from operation failures.

    This prompt template creates helpful guidance for users when operations
    fail, suggesting alternative approaches, parameter adjustments, and
    troubleshooting steps.
    """
    # Build parameter context
    param_context = ""
    if attempted_parameters:
        param_list = [f"  - {k}: {v}" for k, v in attempted_parameters.items()]
        param_context = f"""
ATTEMPTED PARAMETERS:
{chr(10).join(param_list)}"""

    # Build error context
    error_context = f"ERROR TYPE: {error_type}"
    if error_details:
        error_context += f"\nERROR DETAILS: {error_details}"

    # Build user intent context
    intent_context = ""
    if user_intent:
        intent_context = f"USER GOAL: {user_intent}"

    return f"""You are a helpful technical support specialist. A user encountered an error while using the {original_operation} operation. Provide clear, actionable suggestions for resolving the issue.

{error_context}
{param_context}
{intent_context}

SUGGESTION REQUIREMENTS:
1. Acknowledge the specific error and its likely causes
2. Provide immediate troubleshooting steps to try
3. Suggest alternative approaches or tool combinations
4. Recommend parameter adjustments if applicable
5. Include preventive measures for future attempts

RESPONSE FORMAT:
1. **Issue Summary**: Brief explanation of what went wrong
2. **Immediate Actions**: Quick steps to try first
3. **Alternative Approaches**: Different ways to achieve the same goal
4. **Parameter Recommendations**: Suggested changes to avoid the error
5. **Prevention Tips**: How to avoid this issue in the future

Keep suggestions practical, specific, and user-friendly. Focus on actionable solutions rather than technical explanations."""

@mcp.prompt(
    name="query_expansion",
    description="Generate expanded and refined queries for better vector search results, with semantic variations and context enrichment.",
    tags={"search", "query_expansion", "vector_search"}
)
def query_expansion(
    original_query: str,
    context: str | None = Field(
        default=None,
        description="Additional context about the user's intent or domain"
    ),
    expansion_type: Literal["semantic", "keyword", "comprehensive"] = Field(
        default="semantic",
        description="Type of query expansion to perform"
    ),
    max_variants: int = Field(
        default=5,
        description="Maximum number of query variants to generate",
        ge=1,
        le=10
    )
) -> str:
    """
    Generate expanded query variants for improved vector search results.

    This prompt template creates alternative formulations of user queries
    to improve vector search recall and find relevant content that might
    be missed by the original query alone.
    """
    # Build expansion type instructions
    type_instructions = {
        "semantic": "Generate semantically similar queries that express the same intent using different terminology",
        "keyword": "Generate queries with alternative keywords and synonyms while maintaining the core intent",
        "comprehensive": "Generate a mix of semantic variations, keyword alternatives, and context-specific formulations"
    }

    type_instruction = type_instructions.get(expansion_type, type_instructions["semantic"])

    # Build context instructions
    context_instructions = ""
    if context:
        context_instructions = f"""
ADDITIONAL CONTEXT: {context}
- Use this context to inform your query expansions
- Generate variations that would be relevant in this context
- Consider domain-specific terminology if applicable"""

    return f"""You are a search query optimization expert. Generate improved query variants for better vector search results.

ORIGINAL QUERY: "{original_query}"

EXPANSION TASK: {type_instruction}

{context_instructions}

REQUIREMENTS:
1. Generate exactly {max_variants} query variants
2. Each variant should maintain the original intent while using different phrasing
3. Include variations that might match different writing styles or documentation approaches
4. Consider both formal and informal ways of expressing the same concept
5. Ensure variants are distinct from each other and the original

OUTPUT FORMAT:
Return each query variant on a separate line, numbered 1-{max_variants}:
1. [First variant]
2. [Second variant]
...

Focus on creating variants that would help find relevant content that the original query might miss."""

@mcp.prompt(
    name="content_classification",
    description="Generate prompts for classifying and tagging web content with metadata extraction and categorization.",
    tags={"classification", "tagging", "metadata"}
)
def content_classification(
    content_url: str,
    classification_goals: list[str] = Field(
        description="List of classification goals (e.g., 'content_type', 'technical_level', 'audience')"
    ),
    available_categories: dict[str, list[str]] | None = Field(
        default=None,
        description="Available categories for each classification goal"
    ),
    extract_metadata: bool = Field(
        default=True,
        description="Whether to extract additional metadata fields"
    )
) -> str:
    """
    Generate a prompt for classifying and categorizing web content.

    This prompt template creates instructions for systematic content
    classification, metadata extraction, and tagging that can be used
    to organize and filter scraped content effectively.
    """
    # Build classification goals
    goal_specs = []
    for goal in classification_goals:
        if available_categories and goal in available_categories:
            categories = ", ".join(available_categories[goal])
            goal_specs.append(f"- {goal}: Choose from [{categories}]")
        else:
            goal_specs.append(f"- {goal}: Determine the most appropriate classification")

    goals_text = "\n".join(goal_specs)

    # Build metadata extraction instructions
    metadata_instructions = ""
    if extract_metadata:
        metadata_instructions = """
METADATA EXTRACTION:
Additionally extract the following metadata when available:
- Title and headings structure
- Author/organization information
- Publication or last modified date
- Content length and reading time estimate
- Primary language
- Technical requirements or prerequisites
- Target audience level (beginner, intermediate, advanced)"""

    return f"""You are a content classification specialist. Analyze and classify the following web content systematically.

CONTENT SOURCE: {content_url}

CLASSIFICATION REQUIREMENTS:
{goals_text}

{metadata_instructions}

CLASSIFICATION GUIDELINES:
1. Base classifications on observable content characteristics
2. Use consistent criteria across similar content types
3. When unsure between categories, choose the most specific applicable option
4. If content spans multiple categories, indicate the primary and secondary classifications
5. Provide brief justification for non-obvious classifications

OUTPUT FORMAT:
Return your classification in JSON format:
{{
  "classifications": {{
    "goal_name": "chosen_category",
    ...
  }},
  "metadata": {{
    "field_name": "extracted_value",
    ...
  }},
  "confidence": {{
    "goal_name": 0.0-1.0,
    ...
  }},
  "notes": "Additional observations or justifications"
}}

Analyze the content provided below and classify it according to these specifications."""

@mcp.prompt(
    name="content_summarization",
    description="Generate comprehensive summaries of scraped web content with customizable length and focus areas.",
    tags={"summarization", "content", "analysis"}
)
def content_summarization(
    content_type: Literal["article", "documentation", "product_page", "forum_post", "news", "blog", "unknown"] = Field(description="Type of content being summarized"),
    summary_length: Literal["brief", "standard", "detailed"] = Field(default="standard", description="Desired length of the summary"),
    focus_areas: list[str] | None = Field(default=None, description="Specific aspects to focus on in the summary"),
    include_key_points: bool = Field(default=True, description="Whether to extract and highlight key points"),
    preserve_structure: bool = Field(default=False, description="Whether to maintain the original content structure in summary")
) -> str:
    """
    Generate a comprehensive summary of web content with customizable focus and length.

    This prompt template creates instructions for summarizing web content
    while preserving key information and allowing for different summary
    styles and focus areas.
    """
    # Build length instructions
    length_instructions = {
        "brief": "Create a concise summary in 2-3 sentences capturing the essential information.",
        "standard": "Create a comprehensive summary in 1-2 paragraphs covering the main points and key details.",
        "detailed": "Create an extensive summary with multiple paragraphs covering all significant aspects and supporting details."
    }

    length_instruction = length_instructions.get(summary_length, length_instructions["standard"])

    # Build focus area instructions
    focus_instructions = ""
    if focus_areas:
        focus_list = "\n".join([f"- {area}" for area in focus_areas])
        focus_instructions = f"""
FOCUS AREAS - Pay special attention to:
{focus_list}"""

    # Build key points instructions
    key_points_instructions = ""
    if include_key_points:
        key_points_instructions = """

KEY POINTS EXTRACTION:
- Identify and highlight the most important takeaways
- Present key points in a clear, bulleted format after the summary
- Ensure key points are actionable or informative"""

    # Build structure preservation instructions
    structure_instructions = ""
    if preserve_structure:
        structure_instructions = """

STRUCTURE PRESERVATION:
- Maintain the logical flow and organization of the original content
- Preserve section headings and hierarchical relationships where relevant
- Indicate the original content structure in your summary"""

    return f"""You are a content summarization expert. Create a high-quality summary of the following {content_type} content.

SUMMARY REQUIREMENTS:
- {length_instruction}
- Maintain accuracy and fidelity to the original content
- Use clear, engaging language appropriate for the content type
- Focus on the most valuable and relevant information

{focus_instructions}
{key_points_instructions}
{structure_instructions}

SUMMARY GUIDELINES:
1. Begin with the main topic or purpose of the content
2. Cover the most important information in order of relevance
3. Use your own words while preserving the original meaning
4. Avoid redundancy and unnecessary details
5. Conclude with any significant implications or outcomes

Please summarize the content provided below according to these specifications."""

@mcp.prompt(
    name="entity_recognition",
    description="Identify and extract entities from web content with categorization and relationship mapping.",
    tags={"entities", "extraction", "nlp"}
)
def entity_recognition(
    entity_types: list[str] = Field(description="Types of entities to extract (e.g., 'person', 'organization', 'location', 'product')"),
    include_relationships: bool = Field(default=False, description="Whether to identify relationships between entities"),
    confidence_threshold: float = Field(default=0.7, description="Minimum confidence threshold for entity extraction", ge=0.0, le=1.0),
    context_window: int = Field(default=50, description="Number of characters around entity mentions to include as context", ge=10, le=200),
    output_format: Literal["structured", "inline", "table"] = Field(default="structured", description="Format for entity output")
) -> str:
    """
    Generate prompts for comprehensive entity recognition and extraction.

    This prompt template creates instructions for identifying various types
    of entities in web content, with support for relationship mapping and
    confidence scoring.
    """
    # Build entity types specifications
    entity_specs = []
    for entity_type in entity_types:
        entity_specs.append(f"- {entity_type}: Identify all instances of this entity type with high accuracy")

    entity_types_text = "\n".join(entity_specs)

    # Build relationship instructions
    relationship_instructions = ""
    if include_relationships:
        relationship_instructions = """

RELATIONSHIP MAPPING:
- Identify connections and relationships between extracted entities
- Note the type of relationship (e.g., "works for", "located in", "manufactured by")
- Include relationship confidence scores when possible
- Present relationships in a clear format: Entity1 -> [relationship] -> Entity2"""

    # Build output format instructions
    format_instructions = {
        "structured": "Return entities in a structured JSON format with categories, confidence scores, and context.",
        "inline": "Mark entities within the text using brackets and labels: [Entity Name](Entity Type).",
        "table": "Present entities in a table format with columns for Entity, Type, Context, and Confidence."
    }

    format_instruction = format_instructions.get(output_format, format_instructions["structured"])

    return f"""You are an expert entity recognition specialist. Extract and categorize entities from the provided content with high accuracy.

ENTITY EXTRACTION REQUIREMENTS:
{entity_types_text}

OUTPUT FORMAT:
{format_instruction}

{relationship_instructions}

EXTRACTION GUIDELINES:
1. Carefully read through the entire content before extracting entities
2. Only extract entities that clearly belong to the specified types
3. Assign confidence scores based on context clarity and certainty
4. Include {context_window} characters of context around each entity mention
5. Resolve entity disambiguation when the same name could refer to different entities
6. Group variations of the same entity (e.g., "Apple Inc.", "Apple", "Apple Corporation")

CONFIDENCE CRITERIA:
- High confidence (0.8-1.0): Clear, unambiguous entity mentions with sufficient context
- Medium confidence (0.5-0.8): Likely entities with some context but potential ambiguity
- Low confidence (below {confidence_threshold}): Exclude from results

Please extract entities from the content provided below according to these specifications."""

@mcp.prompt(
    name="context_filtering",
    description="Filter and rank relevant content chunks from vector search results based on query relevance and quality.",
    tags={"filtering", "ranking", "context"}
)
def context_filtering(
    query: str = Field(description="Original user query for relevance filtering"),
    max_chunks: int = Field(default=10, description="Maximum number of chunks to return after filtering", ge=1, le=50),
    relevance_threshold: float = Field(default=0.6, description="Minimum relevance score for chunk inclusion", ge=0.0, le=1.0),
    quality_factors: list[str] = Field(default=["completeness", "clarity", "recency"], description="Quality factors to consider in ranking"),
    deduplication: bool = Field(default=True, description="Whether to remove highly similar chunks"),
    preserve_diversity: bool = Field(default=True, description="Whether to maintain diverse perspectives in results")
) -> str:
    """
    Generate prompts for intelligent filtering and ranking of content chunks.

    This prompt template creates instructions for evaluating search results
    and selecting the most relevant, high-quality chunks for context.
    """
    # Build quality factors specifications
    factor_specs = []
    for factor in quality_factors:
        factor_specs.append(f"- {factor}: Evaluate chunks based on this quality dimension")

    quality_factors_text = "\n".join(factor_specs)

    # Build deduplication instructions
    dedup_instructions = ""
    if deduplication:
        dedup_instructions = """

DEDUPLICATION:
- Identify and remove chunks with highly overlapping content (>80% similarity)
- When duplicates are found, prefer the chunk with higher quality or more complete information
- Preserve unique perspectives even if they cover similar topics"""

    # Build diversity instructions
    diversity_instructions = ""
    if preserve_diversity:
        diversity_instructions = """

DIVERSITY PRESERVATION:
- Ensure filtered results represent different aspects of the query topic
- Avoid over-representation of any single source or perspective
- Balance comprehensive coverage with focused relevance"""

    return f"""You are a content filtering and ranking specialist. Evaluate the provided search result chunks and select the most relevant, high-quality content for the user's query.

ORIGINAL QUERY: "{query}"

FILTERING CRITERIA:
- Relevance threshold: {relevance_threshold} (0.0-1.0 scale)
- Maximum chunks to return: {max_chunks}
- Quality evaluation factors:
{quality_factors_text}

{dedup_instructions}
{diversity_instructions}

EVALUATION PROCESS:
1. **Relevance Scoring**: Rate each chunk's relevance to the query (0.0-1.0)
2. **Quality Assessment**: Evaluate chunks based on specified quality factors
3. **Content Filtering**: Remove chunks below the relevance threshold
4. **Ranking**: Order remaining chunks by combined relevance and quality scores
5. **Final Selection**: Return the top {max_chunks} chunks that best serve the query

OUTPUT FORMAT:
For each selected chunk, provide:
- Chunk ID or identifier
- Relevance score (0.0-1.0)
- Quality score (0.0-1.0)
- Brief justification for inclusion
- Key topics or concepts covered

Please evaluate and filter the search result chunks provided below according to these specifications."""

@mcp.prompt(
    name="alternative_approaches",
    description="Suggest alternative tools, strategies, and approaches when current methods fail or are suboptimal.",
    tags={"alternatives", "strategy", "problem_solving"}
)
def alternative_approaches(
    current_approach: str = Field(description="The current approach or tool that failed or is suboptimal"),
    user_goal: str = Field(description="What the user is ultimately trying to accomplish"),
    failure_reason: str | None = Field(default=None, description="Specific reason why the current approach failed"),
    constraints: list[str] | None = Field(default=None, description="Any constraints or limitations to consider"),
    available_tools: list[str] | None = Field(default=None, description="List of alternative tools or methods available"),
    priority_factors: list[str] = Field(default=["effectiveness", "ease_of_use", "speed"], description="Factors to prioritize in alternatives")
) -> str:
    """
    Generate suggestions for alternative approaches and problem-solving strategies.

    This prompt template creates comprehensive guidance for finding alternative
    solutions when current approaches fail or prove inadequate.
    """
    # Build failure context
    failure_context = f"CURRENT APPROACH: {current_approach}"
    if failure_reason:
        failure_context += f"\nFAILURE REASON: {failure_reason}"

    # Build constraints context
    constraints_context = ""
    if constraints:
        constraint_list = "\n".join([f"- {constraint}" for constraint in constraints])
        constraints_context = f"""
CONSTRAINTS TO CONSIDER:
{constraint_list}"""

    # Build available tools context
    tools_context = ""
    if available_tools:
        tools_list = "\n".join([f"- {tool}" for tool in available_tools])
        tools_context = f"""
AVAILABLE ALTERNATIVES:
{tools_list}"""

    # Build priority factors
    priority_list = "\n".join([f"- {factor}: Consider this factor when evaluating alternatives" for factor in priority_factors])
    priority_context = f"""
PRIORITIZATION CRITERIA:
{priority_list}"""

    return f"""You are a problem-solving strategist and technical advisor. Help the user find effective alternative approaches to accomplish their goal.

{failure_context}

USER GOAL: {user_goal}

{constraints_context}
{tools_context}
{priority_context}

ALTERNATIVE STRATEGY FRAMEWORK:
1. **Root Cause Analysis**: Identify why the current approach failed
2. **Goal Decomposition**: Break down the user's objective into smaller, achievable steps
3. **Alternative Identification**: Suggest multiple different approaches or tool combinations
4. **Trade-off Analysis**: Evaluate pros and cons of each alternative
5. **Implementation Guidance**: Provide practical steps for the recommended approaches

SUGGESTION CATEGORIES:
- **Direct Alternatives**: Different tools or methods that accomplish the same goal
- **Workaround Solutions**: Alternative paths that bypass the current obstacle
- **Hybrid Approaches**: Combinations of multiple tools or strategies
- **Iterative Methods**: Step-by-step approaches that reduce complexity
- **Preventive Measures**: Ways to avoid similar issues in the future

OUTPUT FORMAT:
For each suggested alternative, provide:
1. **Approach Name**: Clear, descriptive title
2. **Description**: How this alternative works
3. **Advantages**: Why this might be better than the current approach
4. **Considerations**: Potential drawbacks or requirements
5. **Implementation Steps**: Practical next steps to try this approach

Focus on actionable, practical alternatives that directly address the user's goal while considering their constraints."""



# Utility functions for prompt helpers


def create_default_system_prompt(operation_type: str) -> str:
    """
    Create a default system prompt for LLM operations.

    Args:
        operation_type: Type of operation (extraction, synthesis, analysis, etc.)

    Returns:
        Default system prompt for the operation type
    """
    system_prompts = {
        "extraction": """You are an expert data extraction specialist. Your task is to accurately extract structured information from web content while maintaining fidelity to the source material. Focus on precision and completeness within the specified schema.""",

        "synthesis": """You are a research synthesis expert. Your task is to combine information from multiple sources into coherent, comprehensive responses. Maintain objectivity, cite sources appropriately, and address any conflicting information transparently.""",

        "analysis": """You are a content analysis expert. Your task is to systematically analyze web content across multiple dimensions. Provide objective, evidence-based insights while clearly distinguishing between observable facts and analytical interpretations.""",

        "classification": """You are a content classification specialist. Your task is to systematically categorize and tag web content for organization and retrieval. Use consistent criteria and provide clear justifications for your classifications.""",

        "recovery": """You are a helpful technical support specialist. Your task is to provide clear, actionable guidance for resolving technical issues. Focus on practical solutions and alternative approaches that users can implement immediately."""
    }

    return system_prompts.get(operation_type,
        "You are a helpful AI assistant. Provide accurate, relevant responses based on the provided content and instructions.")


def build_context_string(results: list[dict[str, Any]], max_length: int = 2000) -> str:
    """
    Build a context string from vector search results for LLM synthesis.

    Args:
        results: List of vector search results
        max_length: Maximum length per result

    Returns:
        Formatted context string for LLM input
    """
    context_parts = []

    for i, result in enumerate(results, 1):
        # Extract key information
        title = result.get("title", "Untitled")
        content = result.get("content", "")
        url = result.get("url", "")
        similarity = result.get("similarity", 0.0)

        # Truncate content if needed
        if len(content) > max_length:
            content = content[:max_length] + "..."

        # Format result
        context_part = f"""[Result {i}] {title}
Source: {url}
Relevance: {similarity:.3f}
Content: {content}
"""
        context_parts.append(context_part)

    return "\n" + "="*50 + "\n".join(context_parts)


# Export all prompt-related functionality
__all__ = [
    # Pydantic models
    "ContentAnalysisPromptArgs",
    "ExtractionPromptArgs",
    "RetryPromptArgs",
    "SynthesisPromptArgs",
    # Functions
    "alternative_approaches",
    "build_context_string",
    "content_analysis",
    "content_classification",
    "content_summarization",
    "context_filtering",
    "create_default_system_prompt",
    "entity_recognition",
    "error_recovery_suggestions",
    "mcp",
    "query_expansion",
    "register_prompt_templates",
    "structured_extraction",
    # Validation functions
    "validate_extraction_args",
    "validate_synthesis_args",
    "vector_synthesis"
]
