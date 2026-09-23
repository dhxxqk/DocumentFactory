"""Conversion result model."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ConversionResult:
    """Outcome of one Word -> Word format conversion.

    ``status`` is the real lint result of the output DOCX. ``changes`` carries
    every traceable modification (location / before / after / rule); the
    converter never edits text, and ``content_preserved`` asserts that.
    """

    status: str
    template_id: str
    input_path: str
    output_path: str
    report_path: str
    input_sha256: str
    output_sha256: str
    profile_before: dict[str, Any]
    profile_after: dict[str, Any]
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    changes: list[dict[str, Any]] = field(default_factory=list)
    reassignment_count: int = 0
    created_styles: list[str] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    content_preserved: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_unchanged: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
