"""DocumentInputProvider: DOCX -> parsed Document for the conversion pipeline.

Thin, explicit input boundary for "我已经有一份 Word，只需要套用规范":
``load_docx`` validates the path and delegates to the read-only
``docx_reader`` (paragraphs / styles / tables / sections / fields). It never
writes to the input file — conversion always emits a protected copy.
"""
from __future__ import annotations

from pathlib import Path

from ..docx_reader import read_docx
from ..models import Document, DocumentFactoryError


class DocumentInputProvider:
    """Load an existing DOCX into the in-memory Document model."""

    def load_docx(self, path: str | Path) -> Document:
        source = Path(path).resolve()
        if not source.is_file():
            raise DocumentFactoryError(f"转换输入文件不存在：{source}")
        if source.suffix.lower() != ".docx":
            raise DocumentFactoryError("转换输入必须是 .docx 文件（.doc 请先另存为 .docx）")
        return read_docx(source)


def load_input_docx(path: str | Path) -> Document:
    """Functional shorthand for ``DocumentInputProvider().load_docx(path)``."""
    return DocumentInputProvider().load_docx(path)
