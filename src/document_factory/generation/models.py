"""Document Generation data models.

A GenerationRequest is the user-facing entry point: "apply template T to the
content at S, write to O". A GenerationResult wraps the template runner's
ExecutionResult together with generation-level status and errors.

Content vs format separation: ``input_data`` carries content (Markdown text or
file); the template (resolved via ``template_id``) carries format facts. The
generation layer never decides format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import DocumentFactoryError, ExecutionResult

#: Content sources supported by the v1 generation pipeline.
SUPPORTED_CONTENT_SOURCES = frozenset({"markdown"})


@dataclass
class GenerationRequest:
    """User request to generate a DOCX from content through a template.

    Fields mirror TASK_DOC_010 §7.1. ``input_data`` accepts either
    ``{"file": "path.md"}`` or ``{"text": "..."}``. ``output_path`` and
    ``metadata`` are optional; ``metadata`` may carry ``rules_path``.
    """

    template_id: str
    content_source: str
    input_data: dict
    output_path: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.template_id or not self.template_id.strip():
            raise DocumentFactoryError("GenerationRequest.template_id 不能为空")
        if self.content_source not in SUPPORTED_CONTENT_SOURCES:
            raise DocumentFactoryError(
                f"不支持的 content_source：{self.content_source}"
                f"（仅支持 {sorted(SUPPORTED_CONTENT_SOURCES)}）"
            )
        if not self.input_data:
            raise DocumentFactoryError("GenerationRequest.input_data 不能为空")
        if "file" not in self.input_data and "text" not in self.input_data:
            raise DocumentFactoryError(
                "input_data 必须包含 'file' 或 'text' 键"
            )


@dataclass
class GenerationResult:
    """Outcome of a generation run.

    On success ``status`` mirrors the ExecutionResult lint status ("PASS"/
    "FAIL"), ``execution_result`` carries the full template-run report, and
    ``errors`` is empty. On a caught generation-level failure
    ``execution_result`` may be ``None`` and ``errors`` lists the messages.
    """

    status: str
    output_path: str
    template_id: str
    execution_result: ExecutionResult | None
    report_path: str
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "template_id": self.template_id,
            "execution_result": self.execution_result.to_dict()
            if self.execution_result is not None
            else None,
            "report_path": self.report_path,
            "errors": list(self.errors),
        }
