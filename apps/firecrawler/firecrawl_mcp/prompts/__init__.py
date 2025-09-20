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
    alternative_approaches,
    build_context_string,
    content_analysis,
    content_classification,
    content_summarization,
    context_filtering,
    create_default_system_prompt,
    entity_recognition,
    error_recovery_suggestions,
    mcp,
    query_expansion,
    structured_extraction,
    vector_synthesis,
)

__all__ = [
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
    "structured_extraction",
    "vector_synthesis"
]
