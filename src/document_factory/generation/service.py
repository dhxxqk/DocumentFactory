"""Document Generation Service.

Orchestrates the end-to-end generation pipeline:

    request -> validate template exists -> build draft DOCX from content
            -> run_template (lint before -> apply -> write -> lint after)
            -> wrap ExecutionResult into GenerationResult

The service contains no format decisions and no content authoring: the template
owns format, the provider owns content structuring, run_template owns
validation. A missing template (TemplateNotFoundError) propagates to the caller
so callers can distinguish "no such template" from "execution failed".
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..models import DocumentFactoryError
from ..template_runner import run_template
from ..templates import load_template
from .models import GenerationRequest, GenerationResult
from .providers import get_provider


class DocumentGenerationService:
    """Apply a template to source content, producing a validated DOCX."""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        # Resolve template early: a missing id is a caller error
        # (TemplateNotFoundError propagates), not a generation failure.
        load_template(request.template_id)

        provider = get_provider(request.content_source)
        stem = self._stem(request)
        output = (
            Path(request.output_path)
            if request.output_path
            else Path("output") / f"{stem}.docx"
        )
        report = Path("reports") / f"{stem}_GENERATION_REPORT.md"
        rules_path = request.metadata.get("rules_path")

        # Ensure the constrained output/reports roots exist before run_template
        # resolves paths inside them.
        Path("output").mkdir(parents=True, exist_ok=True)
        Path("reports").mkdir(parents=True, exist_ok=True)

        draft_dir = Path(tempfile.mkdtemp(prefix="df_gen_"))
        draft = draft_dir / f"{stem}_draft.docx"
        try:
            provider.build(request.input_data, draft)
            execution_result = run_template(
                request.template_id, draft, output, report, rules_path
            )
            return GenerationResult(
                status=execution_result.status,
                output_path=execution_result.output_path,
                template_id=request.template_id,
                execution_result=execution_result,
                report_path=execution_result.report_path,
                errors=[],
            )
        except DocumentFactoryError as exc:
            return GenerationResult(
                status="FAIL",
                output_path="",
                template_id=request.template_id,
                execution_result=None,
                report_path="",
                errors=[str(exc)],
            )
        finally:
            shutil.rmtree(draft_dir, ignore_errors=True)

    @staticmethod
    def _stem(request: GenerationRequest) -> str:
        if "file" in request.input_data:
            return Path(request.input_data["file"]).stem
        return "generated"
