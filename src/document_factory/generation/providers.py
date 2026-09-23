"""Content providers: convert source content into a draft DOCX.

V1 ships a single MarkdownContentProvider. It performs a minimal, deterministic
Markdown -> OOXML conversion (no external markdown / python-docx dependency):
headings (#/##/###) map to Heading1/2/3 paragraphs, other non-empty lines map
to the body ("正文") paragraph. The produced package reuses the same minimal
styles.xml shape proven by the test fixtures and consumable by run_template.

Inline emphasis, lists and tables are intentionally out of scope for v1: their
text falls through as plain body paragraphs. The template owns all format
facts; the provider only builds structure.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol
from zipfile import ZipFile, ZIP_DEFLATED

from ..models import DocumentFactoryError
from .models import SUPPORTED_CONTENT_SOURCES

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Style elements mirrored from tests/conftest.py (BODY_STYLE/HEADING_STYLES/
# SECTION). They carry format values close to the GRID_TECH_V1_4 target so the
# draft is both valid and cheaply normalized by run_template. Production code
# must not import test fixtures, so the constants are redefined here.
_NORMAL_STYLE = (
    '<w:style w:type="paragraph" w:styleId="Normal" w:default="1">'
    '<w:name w:val="Normal"/></w:style>'
)
_BODY_STYLE = (
    '<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="正文"/>'
    '<w:pPr><w:ind w:firstLineChars="200"/>'
    '<w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="auto"/>'
    '<w:jc w:val="both"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
    'w:eastAsia="仿宋"/><w:sz w:val="24"/></w:rPr></w:style>'
)
_HEADING_STYLES = "".join(
    f'<w:style w:type="paragraph" w:styleId="Heading{i}">'
    f'<w:name w:val="heading {i}"/>'
    f'<w:pPr><w:outlineLvl w:val="{i - 1}"/></w:pPr>'
    f'<w:rPr><w:rFonts w:eastAsia="黑体"/><w:color w:val="000000"/>'
    f'<w:sz w:val="{size}"/></w:rPr></w:style>'
    for i, size in ((1, 32), (2, 28), (3, 24))
)
_SECTION = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1587" w:bottom="1474" w:left="1587" w:right="1474"/>'
    '</w:sectPr>'
)
_SETTINGS = (
    f'<w:settings xmlns:w="{_W}"><w:updateFields w:val="true"/></w:settings>'
)

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _paragraph(text: str, style_id: str) -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style_id}"/></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{_escape(text)}</w:t></w:r></w:p>'
    )


class ContentProvider(Protocol):
    """Convert source content into a draft DOCX at ``draft_path``."""

    def build(self, input_data: dict, draft_path: Path) -> Path: ...


class MarkdownContentProvider:
    """Minimal Markdown -> DOCX builder (headings + body paragraphs)."""

    def build(self, input_data: dict, draft_path: Path) -> Path:
        text = self._read_source(input_data)
        body_xml = self._render_body(text)
        self._write_package(Path(draft_path), body_xml)
        return Path(draft_path)

    def _read_source(self, input_data: dict) -> str:
        if "file" in input_data:
            path = Path(input_data["file"])
            if not path.is_file():
                raise DocumentFactoryError(f"Markdown 输入文件不存在：{path}")
            return path.read_text(encoding="utf-8")
        value = input_data.get("text")
        if value is None:
            raise DocumentFactoryError("input_data['text'] 不能为 None")
        return str(value)

    def _render_body(self, text: str) -> str:
        blocks: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            match = _HEADING_RE.match(line.strip())
            if match:
                level = len(match.group(1))
                blocks.append(_paragraph(match.group(2).strip(), f"Heading{level}"))
            else:
                blocks.append(_paragraph(line, "Body"))
        return "".join(blocks) + _SECTION

    def _write_package(self, path: Path, body_xml: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        parts = {
            "word/document.xml": (
                f'<w:document xmlns:w="{_W}"><w:body>{body_xml}</w:body></w:document>'
            ),
            "word/styles.xml": (
                f'<w:styles xmlns:w="{_W}">'
                f'{_NORMAL_STYLE}{_BODY_STYLE}{_HEADING_STYLES}</w:styles>'
            ),
            "word/settings.xml": _SETTINGS,
        }
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            for name, content in parts.items():
                archive.writestr(name, content)


def get_provider(content_source: str) -> ContentProvider:
    """Return the provider registered for ``content_source``."""
    if content_source == "markdown":
        return MarkdownContentProvider()
    raise DocumentFactoryError(
        f"不支持的 content_source：{content_source}"
        f"（仅支持 {sorted(SUPPORTED_CONTENT_SOURCES)}）"
    )
