"""Pipeline orchestrator entry point.

``generate_document`` is the functional entry point corresponding to the
"Document Generation Pipeline" in the design doc. It delegates to
``DocumentGenerationService`` so callers can use either the function or the
class interchangeably.
"""
from __future__ import annotations

from .models import GenerationRequest, GenerationResult
from .service import DocumentGenerationService


def generate_document(request: GenerationRequest) -> GenerationResult:
    """Run the full generation pipeline for ``request``."""
    return DocumentGenerationService().generate(request)
