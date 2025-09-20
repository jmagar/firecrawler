"""
Tests for prompt template validation and parameterization.

This module provides comprehensive testing for prompt templates including
parameter validation, template generation, content verification, and integration
with FastMCP prompt system.
"""


from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from firecrawl_mcp.prompts.prompts import (
    ContentAnalysisPromptArgs,
    ExtractionPromptArgs,
    RetryPromptArgs,
    SynthesisPromptArgs,
    build_context_string,
    create_default_system_prompt,
    register_prompt_templates,
    validate_extraction_args,
    validate_synthesis_args,
)


class TestExtractionPromptArgs:
    """Test extraction prompt argument validation and usage."""

    def test_valid_extraction_args(self) -> None:
        """Test creation of valid extraction prompt arguments."""
        args = ExtractionPromptArgs(
            content_type="product page",
            extraction_fields=["title", "price", "description"],
            schema_description="Product information schema",
            output_format="json",
            strict_schema=True,
            include_confidence=True
        )

        assert args.content_type == "product page"
        assert args.extraction_fields == ["title", "price", "description"]
        assert args.schema_description == "Product information schema"
        assert args.output_format == "json"
        assert args.strict_schema is True
        assert args.include_confidence is True

    def test_extraction_args_defaults(self) -> None:
        """Test extraction prompt arguments with default values."""
        args = ExtractionPromptArgs(
            content_type="blog post",
            extraction_fields=["title", "author"]
        )

        assert args.content_type == "blog post"
        assert args.extraction_fields == ["title", "author"]
        assert args.schema_description is None
        assert args.output_format == "json"
        assert args.strict_schema is True
        assert args.include_confidence is False

    def test_invalid_output_format(self) -> None:
        """Test validation of invalid output format."""
        with pytest.raises(ValueError):
            # Use type: ignore to bypass mypy check for this intentional test
            ExtractionPromptArgs(
                content_type="webpage",
                extraction_fields=["title"],
                output_format="invalid_format"  # type: ignore
            )


class TestSynthesisPromptArgs:
    """Test synthesis prompt argument validation and usage."""

    def test_valid_synthesis_args(self) -> None:
        """Test creation of valid synthesis prompt arguments."""
        args = SynthesisPromptArgs(
            query="How to implement vector search?",
            result_count=5,
            max_context_length=1500,
            synthesis_style="comprehensive",
            include_sources=True,
            handle_conflicts=True
        )

        assert args.query == "How to implement vector search?"
        assert args.result_count == 5
        assert args.max_context_length == 1500
        assert args.synthesis_style == "comprehensive"
        assert args.include_sources is True
        assert args.handle_conflicts is True

    def test_synthesis_args_defaults(self) -> None:
        """Test synthesis prompt arguments with default values."""
        args = SynthesisPromptArgs(
            query="test query",
            result_count=3
        )

        assert args.query == "test query"
        assert args.result_count == 3
        assert args.max_context_length == 2000
        assert args.synthesis_style == "comprehensive"
        assert args.include_sources is True
        assert args.handle_conflicts is True

    def test_invalid_context_length(self) -> None:
        """Test validation of invalid context length."""
        with pytest.raises(ValueError):
            SynthesisPromptArgs(
                query="test",
                result_count=1,
                max_context_length=50  # Below minimum of 100
            )

        with pytest.raises(ValueError):
            SynthesisPromptArgs(
                query="test",
                result_count=1,
                max_context_length=6000  # Above maximum of 5000
            )


class TestContentAnalysisPromptArgs:
    """Test content analysis prompt argument validation and usage."""

    def test_valid_analysis_args(self) -> None:
        """Test creation of valid content analysis prompt arguments."""
        args = ContentAnalysisPromptArgs(
            content_type="documentation",
            analysis_goals=["sentiment", "key_topics"],
            output_structure="detailed",
            domain_context="technology documentation"
        )

        assert args.content_type == "documentation"
        assert args.analysis_goals == ["sentiment", "key_topics"]
        assert args.output_structure == "detailed"
        assert args.domain_context == "technology documentation"

    def test_analysis_args_defaults(self) -> None:
        """Test content analysis prompt arguments with default values."""
        args = ContentAnalysisPromptArgs(
            content_type="webpage",
            analysis_goals=["sentiment"]
        )

        assert args.content_type == "webpage"
        assert args.analysis_goals == ["sentiment"]
        assert args.output_structure == "summary"
        assert args.domain_context is None


class TestRetryPromptArgs:
    """Test retry prompt argument validation and usage."""

    def test_valid_retry_args(self) -> None:
        """Test creation of valid retry prompt arguments."""
        args = RetryPromptArgs(
            original_operation="scrape",
            error_type="rate_limit",
            error_details="Rate limit exceeded: 429",
            attempted_parameters={"url": "https://example.com", "timeout": 30},
            user_intent="Extract product information from e-commerce site"
        )

        assert args.original_operation == "scrape"
        assert args.error_type == "rate_limit"
        assert args.error_details == "Rate limit exceeded: 429"
        assert args.attempted_parameters == {"url": "https://example.com", "timeout": 30}
        assert args.user_intent == "Extract product information from e-commerce site"

    def test_retry_args_minimal(self) -> None:
        """Test retry prompt arguments with minimal required fields."""
        args = RetryPromptArgs(
            original_operation="extract",
            error_type="timeout",
            attempted_parameters={"url": "https://slow-site.com"}
        )

        assert args.original_operation == "extract"
        assert args.error_type == "timeout"
        assert args.error_details is None
        assert args.attempted_parameters == {"url": "https://slow-site.com"}
        assert args.user_intent is None


class TestPromptValidation:
    """Test prompt argument validation functions."""

    def test_validate_extraction_args_success(self) -> None:
        """Test successful validation of extraction arguments."""
        args = ExtractionPromptArgs(
            content_type="webpage",
            extraction_fields=["title", "content"],
            schema_description="Basic webpage schema"
        )

        # Should not raise any exception
        validate_extraction_args(args)

    def test_validate_extraction_args_empty_fields(self) -> None:
        """Test validation failure for empty extraction fields."""
        args = ExtractionPromptArgs(
            content_type="webpage",
            extraction_fields=[]
        )

        with pytest.raises(ToolError, match="Extraction fields cannot be empty"):
            validate_extraction_args(args)

    def test_validate_extraction_args_too_many_fields(self) -> None:
        """Test validation failure for too many extraction fields."""
        args = ExtractionPromptArgs(
            content_type="webpage",
            extraction_fields=[f"field_{i}" for i in range(51)]  # 51 fields, max is 50
        )

        with pytest.raises(ToolError, match="Too many extraction fields"):
            validate_extraction_args(args)

    def test_validate_synthesis_args_success(self) -> None:
        """Test successful validation of synthesis arguments."""
        args = SynthesisPromptArgs(
            query="Valid query",
            result_count=5
        )

        # Should not raise any exception
        validate_synthesis_args(args)

    def test_validate_synthesis_args_empty_query(self) -> None:
        """Test validation failure for empty query."""
        args = SynthesisPromptArgs(
            query="   ",  # Empty/whitespace query
            result_count=5
        )

        with pytest.raises(ToolError, match="Query cannot be empty"):
            validate_synthesis_args(args)

    def test_validate_synthesis_args_invalid_result_count(self) -> None:
        """Test validation failure for invalid result count."""
        args = SynthesisPromptArgs(
            query="Valid query",
            result_count=0
        )

        with pytest.raises(ToolError, match="Result count must be positive"):
            validate_synthesis_args(args)

        args = SynthesisPromptArgs(
            query="Valid query",
            result_count=101
        )

        with pytest.raises(ToolError, match="Too many results for synthesis"):
            validate_synthesis_args(args)


class TestPromptTemplateRegistration:
    """Test prompt template registration and integration with FastMCP."""

    @pytest.fixture
    def test_server(self) -> FastMCP:
        """Create a test FastMCP server."""
        return FastMCP("TestPromptServer")

    def test_register_prompt_templates(self, test_server: FastMCP) -> None:
        """Test registration of all prompt templates."""
        registered_names = register_prompt_templates(test_server)

        expected_prompts = [
            "structured_extraction",
            "vector_synthesis",
            "content_analysis",
            "error_recovery_suggestions",
            "query_expansion",
            "content_classification"
        ]

        assert set(registered_names) == set(expected_prompts)
        assert len(registered_names) == len(expected_prompts)

    async def test_structured_extraction_prompt_generation(self, test_server: FastMCP) -> None:
        """Test generation of structured extraction prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            args = ExtractionPromptArgs(
                content_type="product page",
                extraction_fields=["title", "price", "description"],
                output_format="json",
                include_confidence=True
            )

            prompt = await client.get_prompt("structured_extraction", args.model_dump())

            assert isinstance(prompt, dict)
            assert "role" in prompt
            assert prompt["role"] == "user"
            assert "content" in prompt
            assert "product page" in prompt["content"]
            assert "title" in prompt["content"]
            assert "price" in prompt["content"]
            assert "description" in prompt["content"]
            assert "confidence score" in prompt["content"]

    async def test_vector_synthesis_prompt_generation(self, test_server: FastMCP) -> None:
        """Test generation of vector synthesis prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            args = SynthesisPromptArgs(
                query="How to implement vector search?",
                result_count=3,
                synthesis_style="concise",
                include_sources=True
            )

            prompt = await client.get_prompt("vector_synthesis", args.model_dump())

            assert isinstance(prompt, dict)
            assert "role" in prompt
            assert prompt["role"] == "user"
            assert "content" in prompt
            assert "How to implement vector search?" in prompt["content"]
            assert "concise" in prompt["content"]
            assert "SOURCE CITATION" in prompt["content"]

    async def test_content_analysis_prompt_generation(self, test_server: FastMCP) -> None:
        """Test generation of content analysis prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            args = ContentAnalysisPromptArgs(
                content_type="documentation",
                analysis_goals=["sentiment", "key_topics"],
                output_structure="detailed",
                domain_context="AI/ML documentation"
            )

            prompt = await client.get_prompt("content_analysis", args.model_dump())

            assert isinstance(prompt, dict)
            assert "role" in prompt
            assert prompt["role"] == "user"
            assert "content" in prompt
            assert "documentation" in prompt["content"]
            assert "sentiment" in prompt["content"]
            assert "key_topics" in prompt["content"]
            assert "AI/ML documentation" in prompt["content"]

    async def test_error_recovery_prompt_generation(self, test_server: FastMCP) -> None:
        """Test generation of error recovery prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            args = RetryPromptArgs(
                original_operation="scrape",
                error_type="rate_limit",
                error_details="Rate limit exceeded",
                attempted_parameters={"url": "https://example.com"},
                user_intent="Extract article content"
            )

            prompt = await client.get_prompt("error_recovery_suggestions", args.model_dump())

            assert isinstance(prompt, dict)
            assert "role" in prompt
            assert prompt["role"] == "user"
            assert "content" in prompt
            assert "scrape" in prompt["content"]
            assert "rate_limit" in prompt["content"]
            assert "Rate limit exceeded" in prompt["content"]
            assert "https://example.com" in prompt["content"]

    async def test_query_expansion_prompt_generation(self, test_server: FastMCP) -> None:
        """Test generation of query expansion prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            params = {
                "original_query": "machine learning algorithms",
                "expansion_type": "semantic",
                "max_variants": 3,
                "context": "academic research"
            }

            prompt = await client.get_prompt("query_expansion", params)

            assert isinstance(prompt, dict)
            assert "role" in prompt
            assert prompt["role"] == "user"
            assert "content" in prompt
            assert "machine learning algorithms" in prompt["content"]
            assert "semantic" in prompt["content"]
            assert "exactly 3 query variants" in prompt["content"]
            assert "academic research" in prompt["content"]

    async def test_content_classification_prompt_generation(self, test_server: FastMCP) -> None:
        """Test generation of content classification prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            params = {
                "content_url": "https://example.com/article",
                "classification_goals": ["content_type", "technical_level"],
                "available_categories": {
                    "content_type": ["tutorial", "reference", "blog_post"],
                    "technical_level": ["beginner", "intermediate", "advanced"]
                },
                "extract_metadata": True
            }

            prompt = await client.get_prompt("content_classification", params)

            assert isinstance(prompt, dict)
            assert "role" in prompt
            assert prompt["role"] == "user"
            assert "content" in prompt
            assert "https://example.com/article" in prompt["content"]
            assert "content_type" in prompt["content"]
            assert "tutorial" in prompt["content"]
            assert "METADATA EXTRACTION" in prompt["content"]


class TestPromptUtilities:
    """Test prompt utility functions."""

    def test_create_default_system_prompt_extraction(self) -> None:
        """Test creation of default system prompt for extraction."""
        prompt = create_default_system_prompt("extraction")

        assert "expert data extraction specialist" in prompt.lower()
        assert "structured information" in prompt.lower()
        assert "web content" in prompt.lower()

    def test_create_default_system_prompt_synthesis(self) -> None:
        """Test creation of default system prompt for synthesis."""
        prompt = create_default_system_prompt("synthesis")

        assert "research synthesis expert" in prompt.lower()
        assert "multiple sources" in prompt.lower()
        assert "comprehensive responses" in prompt.lower()

    def test_create_default_system_prompt_analysis(self) -> None:
        """Test creation of default system prompt for analysis."""
        prompt = create_default_system_prompt("analysis")

        assert "content analysis expert" in prompt.lower()
        assert "systematically analyze" in prompt.lower()
        assert "web content" in prompt.lower()

    def test_create_default_system_prompt_unknown(self) -> None:
        """Test creation of default system prompt for unknown operation."""
        prompt = create_default_system_prompt("unknown_operation")

        assert "helpful AI assistant" in prompt.lower()
        assert "accurate, relevant responses" in prompt.lower()

    def test_build_context_string(self) -> None:
        """Test building context string from vector search results."""
        results = [
            {
                "title": "First Document",
                "content": "This is the content of the first document with important information.",
                "url": "https://example.com/doc1",
                "similarity": 0.95
            },
            {
                "title": "Second Document",
                "content": "This is the content of the second document with more information.",
                "url": "https://example.com/doc2",
                "similarity": 0.87
            }
        ]

        context = build_context_string(results, max_length=50)

        assert "[Result 1] First Document" in context
        assert "[Result 2] Second Document" in context
        assert "https://example.com/doc1" in context
        assert "https://example.com/doc2" in context
        assert "0.950" in context
        assert "0.870" in context
        assert "..." in context  # Content should be truncated

    def test_build_context_string_missing_fields(self) -> None:
        """Test building context string with missing fields."""
        results: list[dict[str, Any]] = [
            {
                "content": "Content without title or URL",
                "similarity": 0.8
            },
            {
                "title": "Title Only Document"
                # Missing content, url, similarity
            }
        ]

        context = build_context_string(results)

        assert "[Result 1] Untitled" in context
        assert "[Result 2] Title Only Document" in context
        assert "Content without title or URL" in context
        assert "0.800" in context
        assert "0.000" in context  # Default similarity for missing value

    def test_build_context_string_empty_results(self) -> None:
        """Test building context string with empty results."""
        context = build_context_string([])

        assert context == "\n" + "="*50


class TestPromptParameterValidation:
    """Test parameter validation for different prompt types."""

    @pytest.fixture
    def test_server(self) -> FastMCP:
        """Create a test FastMCP server."""
        return FastMCP("TestPromptValidationServer")

    async def test_extraction_prompt_parameter_validation(self, test_server: FastMCP) -> None:
        """Test parameter validation for extraction prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            # Test with invalid parameters
            with pytest.raises(ValueError):  # Should raise validation error
                await client.get_prompt("structured_extraction", {
                    "content_type": "webpage",
                    "extraction_fields": [],  # Empty fields
                    "output_format": "json"
                })

    async def test_synthesis_prompt_parameter_validation(self, test_server: FastMCP) -> None:
        """Test parameter validation for synthesis prompt."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            # Test with invalid parameters
            with pytest.raises(ValueError):  # Should raise validation error
                await client.get_prompt("vector_synthesis", {
                    "query": "",  # Empty query
                    "result_count": 5
                })

    async def test_prompt_with_missing_required_parameters(self, test_server: FastMCP) -> None:
        """Test prompt generation with missing required parameters."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            # Test extraction prompt with missing required fields
            with pytest.raises((KeyError, ValueError)):  # Should raise validation error
                await client.get_prompt("structured_extraction", {
                    "content_type": "webpage"
                    # Missing extraction_fields
                })

            # Test synthesis prompt with missing required fields
            with pytest.raises((KeyError, ValueError)):  # Should raise validation error
                await client.get_prompt("vector_synthesis", {
                    "result_count": 5
                    # Missing query
                })


class TestPromptContentValidation:
    """Test validation of generated prompt content."""

    @pytest.fixture
    def test_server(self) -> FastMCP:
        """Create a test FastMCP server."""
        return FastMCP("TestPromptContentServer")

    async def test_extraction_prompt_contains_required_elements(self, test_server: FastMCP) -> None:
        """Test that extraction prompt contains all required elements."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            args = ExtractionPromptArgs(
                content_type="product page",
                extraction_fields=["title", "price"],
                output_format="json",
                strict_schema=True,
                schema_description="Product schema",
                include_confidence=True
            )

            prompt = await client.get_prompt("structured_extraction", args.model_dump())
            content = prompt["content"]

            # Check that all key elements are present
            assert "product page" in content
            assert "title" in content
            assert "price" in content
            assert "JSON" in content
            assert "STRICT SCHEMA" in content
            assert "Product schema" in content
            assert "confidence score" in content

    async def test_synthesis_prompt_handles_different_styles(self, test_server: FastMCP) -> None:
        """Test that synthesis prompt adapts to different synthesis styles."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            # Test comprehensive style
            args = SynthesisPromptArgs(
                query="Test query",
                result_count=3,
                synthesis_style="comprehensive"
            )
            prompt = await client.get_prompt("vector_synthesis", args.model_dump())
            assert "thorough, detailed response" in prompt["content"]

            # Test concise style
            args = SynthesisPromptArgs(
                query="Test query",
                result_count=3,
                synthesis_style="concise"
            )
            prompt = await client.get_prompt("vector_synthesis", args.model_dump())
            assert "brief, focused response" in prompt["content"]

            # Test bullet points style
            args = SynthesisPromptArgs(
                query="Test query",
                result_count=3,
                synthesis_style="bullet_points"
            )
            prompt = await client.get_prompt("vector_synthesis", args.model_dump())
            assert "bullet points" in prompt["content"]

    async def test_analysis_prompt_includes_domain_context(self, test_server: FastMCP) -> None:
        """Test that analysis prompt includes domain context when provided."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            # Test with domain context
            args = ContentAnalysisPromptArgs(
                content_type="documentation",
                analysis_goals=["sentiment"],
                domain_context="medical research"
            )
            prompt = await client.get_prompt("content_analysis", args.model_dump())
            content = prompt["content"]

            assert "DOMAIN CONTEXT: medical research" in content
            assert "domain-specific terminology" in content

            # Test without domain context
            args = ContentAnalysisPromptArgs(
                content_type="documentation",
                analysis_goals=["sentiment"]
            )
            prompt = await client.get_prompt("content_analysis", args.model_dump())
            content = prompt["content"]

            assert "DOMAIN CONTEXT:" not in content

    async def test_recovery_prompt_includes_all_context(self, test_server: FastMCP) -> None:
        """Test that recovery prompt includes all provided context."""
        register_prompt_templates(test_server)

        async with Client(test_server) as client:
            args = RetryPromptArgs(
                original_operation="scrape",
                error_type="timeout",
                error_details="Connection timed out after 30 seconds",
                attempted_parameters={"url": "https://slow-site.com", "timeout": 30},
                user_intent="Extract article content for research"
            )

            prompt = await client.get_prompt("error_recovery_suggestions", args.model_dump())
            content = prompt["content"]

            assert "scrape" in content
            assert "timeout" in content
            assert "Connection timed out after 30 seconds" in content
            assert "https://slow-site.com" in content
            assert "timeout: 30" in content
            assert "Extract article content for research" in content


class TestPromptIntegration:
    """Test integration of prompts with MCP server components."""

    @pytest.fixture
    def test_server(self) -> FastMCP:
        """Create a test FastMCP server with prompts registered."""
        server = FastMCP("TestPromptIntegrationServer")
        register_prompt_templates(server)
        return server

    async def test_prompt_registration_with_server(self, test_server: FastMCP) -> None:
        """Test that prompts are properly registered with server."""
        async with Client(test_server) as client:
            prompts = await client.list_prompts()

            prompt_names = [prompt["name"] for prompt in prompts]

            expected_prompts = [
                "structured_extraction",
                "vector_synthesis",
                "content_analysis",
                "error_recovery_suggestions",
                "query_expansion",
                "content_classification"
            ]

            for expected_prompt in expected_prompts:
                assert expected_prompt in prompt_names

    async def test_prompt_metadata_correctness(self, test_server: FastMCP) -> None:
        """Test that prompt metadata is correctly set."""
        async with Client(test_server) as client:
            prompts = await client.list_prompts()

            prompt_dict = {prompt["name"]: prompt for prompt in prompts}

            # Test structured_extraction prompt metadata
            extraction_prompt = prompt_dict["structured_extraction"]
            assert "extraction" in extraction_prompt.get("tags", [])
            assert "ai" in extraction_prompt.get("tags", [])
            assert "structured_data" in extraction_prompt.get("tags", [])
            assert "AI-powered structured data extraction" in extraction_prompt["description"]

            # Test vector_synthesis prompt metadata
            synthesis_prompt = prompt_dict["vector_synthesis"]
            assert "vector_search" in synthesis_prompt.get("tags", [])
            assert "synthesis" in synthesis_prompt.get("tags", [])
            assert "rag" in synthesis_prompt.get("tags", [])
            assert "synthesizing vector search results" in synthesis_prompt["description"]

    async def test_prompt_error_handling(self, test_server: FastMCP) -> None:
        """Test error handling in prompt generation."""
        async with Client(test_server) as client:
            # Test with completely invalid parameters
            with pytest.raises((KeyError, ValueError, TypeError)):
                await client.get_prompt("structured_extraction", {
                    "invalid_param": "invalid_value"
                })

            # Test with partially invalid parameters
            with pytest.raises((ValueError, TypeError)):
                await client.get_prompt("vector_synthesis", {
                    "query": "valid query",
                    "result_count": "invalid_type"  # Should be int
                })
