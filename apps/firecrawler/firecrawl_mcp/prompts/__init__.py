"""
MCP Prompts package for reusable LLM interaction templates.

This package provides prompt templates with parameterization for various
LLM-powered operations within the Firecrawl MCP server. Prompts are used
by tools that require LLM processing such as extraction and synthesis.

The prompts support:
- Template parameterization with type safety
- Validation of prompt parameters
- Integration with extraction and synthesis tools
- Flexible prompt customization
"""

from .prompts import (
    mcp,
    structured_extraction,
    vector_synthesis,
    content_analysis,
    error_recovery_suggestions,
    query_expansion,
    content_classification,
    content_summarization,
    entity_recognition,
    context_filtering,
    alternative_approaches,
    build_context_string,
    create_default_system_prompt,
)

__all__ = [
    "mcp",
    "structured_extraction",
    "vector_synthesis", 
    "content_analysis",
    "error_recovery_suggestions",
    "query_expansion",
    "content_classification",
    "content_summarization",
    "entity_recognition",
    "context_filtering",
    "alternative_approaches",
    "build_context_string",
    "create_default_system_prompt"
]
