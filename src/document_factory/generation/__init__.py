"""Document Generation Workflow.

User-facing pipeline: build a DOCX from Markdown content, apply a template
through run_template, and validate via lint. LLM-generated content stays
outside this pipeline; format facts come from TemplateDefinition.

Public API:

- models:    GenerationRequest, GenerationResult, SUPPORTED_CONTENT_SOURCES
- service:   DocumentGenerationService
- pipeline:  generate_document
- providers: MarkdownContentProvider, get_provider
"""
from .models import (
    SUPPORTED_CONTENT_SOURCES,
    GenerationRequest,
    GenerationResult,
)
from .pipeline import generate_document
from .providers import MarkdownContentProvider, get_provider
from .service import DocumentGenerationService

__all__ = [
    "SUPPORTED_CONTENT_SOURCES",
    "GenerationRequest",
    "GenerationResult",
    "DocumentGenerationService",
    "generate_document",
    "MarkdownContentProvider",
    "get_provider",
]
