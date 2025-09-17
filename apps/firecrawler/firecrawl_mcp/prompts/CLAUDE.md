# Prompts Development Guide

This directory contains reusable prompt templates for LLM interactions used throughout the Firecrawl MCP server.

## Implementation Patterns

### FastMCP Prompt Structure
```python
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts.prompt import Message
from pydantic import Field

mcp = FastMCP(name="FirecrawlPrompts")

@mcp.prompt(
    name="structured_extraction",
    description="Generate prompts for AI-powered structured data extraction from web content with customizable schemas and output formats.",
    tags={"extraction", "ai", "structured_data"}
)
def structured_extraction(
    content_type: str = Field(description="Type of content being extracted (e.g., 'product page', 'blog post', 'documentation')"),
    extraction_fields: list[str] = Field(description="List of fields to extract from the content"),
    schema_description: str | None = Field(default=None, description="Description of the expected data schema"),
    output_format: str = Field(default="json", description="Desired output format for extracted data")
) -> str:
    """Generate prompts for structured data extraction from web content."""
    field_specs = [f"- {field}: Extract this field accurately from the content" for field in extraction_fields]
    fields_text = "\n".join(field_specs)
    
    return f"""You are an expert data extraction specialist. Extract structured information from the following {content_type} content.

EXTRACTION REQUIREMENTS:
{fields_text}

OUTPUT FORMAT: Return the extracted data as valid {output_format} with the specified field names as keys.

Focus on accuracy and completeness. Return data in the requested schema format."""
```

### Prompt Categories

#### Data Extraction Prompts
- **structured_extraction**: Generate extraction prompts based on schema requirements with customizable output formats
- **content_analysis**: Analyze and categorize web content with domain-specific insights and structured outputs
- **content_classification**: Classify and tag web content with metadata extraction and categorization
- **content_summarization**: Create comprehensive summaries of scraped web content with customizable length and focus areas
- **entity_recognition**: Identify and extract entities from web content with categorization and relationship mapping

#### Vector Search Prompts
- **vector_synthesis**: Combine vector search results into coherent responses with source attribution
- **query_expansion**: Enhance user queries for better vector retrieval with semantic variations
- **context_filtering**: Filter and rank relevant content chunks from vector search results based on query relevance and quality

#### Error Recovery Prompts
- **error_recovery_suggestions**: Generate user-friendly recovery suggestions for failed operations with alternative approaches
- **alternative_approaches**: Suggest alternative tools, strategies, and approaches when current methods fail or are suboptimal

## Best Practices

### Parameterization
- Use individual Field parameters instead of BaseModel classes for modern FastMCP patterns
- Support variable field lists and content types with proper Field descriptions
- Include optional parameters with default values for customization
- Use Field validation constraints (ge, le, max_length, etc.) for robust parameter validation

### Template Design
- Keep prompts concise but comprehensive
- Include clear instructions and expected output format
- Use consistent language and terminology
- Provide examples when beneficial for LLM understanding

### Integration Patterns
- Import prompts in tools that require LLM processing
- Pass structured data to prompts rather than raw strings
- Cache frequently used prompt templates
- Log prompt usage for optimization insights

### LLM Compatibility
- Design prompts to work with both OpenAI and Ollama models
- Test with different model capabilities and context limits
- Include fallback strategies for limited models
- Optimize for token efficiency

## Tool Integration

### Current Implementation
The prompts module is currently **standalone** and does not have direct integration with tools:
- Tools accept string `prompt` and `system_prompt` parameters directly from users
- Tools do not import or use the structured prompt functions from this module
- The prompts module provides reusable templates for manual use or future integration

### Potential Integration Patterns
For future integration, tools could:
- Import prompt functions to generate dynamic prompts based on operation context
- Use `structured_extraction` prompts for the extract tool based on provided schemas
- Use `vector_synthesis` prompts for the firerag tool to format search results
- Use `error_recovery_suggestions` prompts to provide helpful error messages

### Manual Usage
The prompts can be used manually by:
- Calling prompt functions programmatically to generate prompt text
- Using the FastMCP prompt endpoints to render templates with parameters
- Integrating generated prompts into custom tools or external applications

## Configuration

### Current State
The prompts module currently has basic functionality without advanced configuration features.

### Future Configuration Features
Planned features for enhanced prompt management:
- Environment-based prompt customization through configuration files
- Override of default prompts through environment variables or config
- Prompt versioning system for A/B testing different prompt variants  
- Backward compatibility mechanisms for existing implementations
- Dynamic prompt loading and hot-reloading for development

### Basic Usage
Currently, prompts are configured through:
- Function parameters with Field validation
- Direct modification of prompt templates in the source code
- FastMCP's built-in prompt management and serving capabilities