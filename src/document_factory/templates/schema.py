"""Prescriptive TemplateDefinition data model.

A TemplateDefinition is the *target* format facts for a class of documents
(technical report, government doc, enterprise report ...). It is intentionally
prescriptive ("the body must be FangSong 12pt") rather than descriptive
("this DOCX happens to use FangSong 12pt"). The operations layer consumes
these rules verbatim; no LLM is involved in interpreting them.

Field names are aligned with ``operations.font.FontProfile``,
``operations.paragraph.ParagraphProfile``, ``operations.document.PageFormat``
and the table operations so the future TemplateRunner can map rules directly
into operation calls without translation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BodyRule:
    """Body paragraph format. Maps to FontProfile + ParagraphProfile."""

    style_name: str
    chinese_font: str
    latin_font: str
    font_size_pt: float
    first_line_indent_chars: int
    line_spacing: float
    space_before_pt: float
    space_after_pt: float
    alignment: str

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        required = (
            "style_name", "chinese_font", "latin_font", "font_size_pt",
            "first_line_indent_chars", "line_spacing", "space_before_pt",
            "space_after_pt", "alignment",
        )
        missing = [k for k in required if k not in data]
        if missing:
            from ..models import DocumentFactoryError
            raise DocumentFactoryError(f"body 规则缺少字段: {', '.join(missing)}")
        return cls(**{k: data[k] for k in required})


@dataclass(frozen=True)
class HeadingRule:
    """Heading format. Maps to FontProfile + apply_style."""

    word_style: str
    chinese_font: str
    latin_font: str
    size_pt: float
    color: str
    bold: bool
    alignment: str

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        required = (
            "word_style", "chinese_font", "latin_font", "size_pt",
            "color", "bold", "alignment",
        )
        missing = [k for k in required if k not in data]
        if missing:
            from ..models import DocumentFactoryError
            raise DocumentFactoryError(f"heading 规则缺少字段: {', '.join(missing)}")
        return cls(**{k: data[k] for k in required})


@dataclass(frozen=True)
class TableRule:
    """Table format. Maps to apply_table_font / apply_table_alignment."""

    header_font: str
    body_font: str
    latin_font: str
    font_size_pt: float
    alignment: str

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        required = (
            "header_font", "body_font", "latin_font", "font_size_pt", "alignment",
        )
        missing = [k for k in required if k not in data]
        if missing:
            from ..models import DocumentFactoryError
            raise DocumentFactoryError(f"tables 规则缺少字段: {', '.join(missing)}")
        return cls(**{k: data[k] for k in required})


@dataclass(frozen=True)
class TemplateRules:
    """All formatting rules for one template."""

    page: dict[str, Any]
    body: BodyRule
    headings: dict[str, HeadingRule]
    tables: TableRule | None = None
    font_aliases: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        if "page" not in data:
            from ..models import DocumentFactoryError
            raise DocumentFactoryError("rules.page 缺失")
        if "body" not in data:
            from ..models import DocumentFactoryError
            raise DocumentFactoryError("rules.body 缺失")
        if "headings" not in data:
            from ..models import DocumentFactoryError
            raise DocumentFactoryError("rules.headings 缺失")
        headings = {
            key: HeadingRule.from_dict(value)
            for key, value in data["headings"].items()
        }
        tables = TableRule.from_dict(data["tables"]) if data.get("tables") else None
        return cls(
            page=dict(data["page"]),
            body=BodyRule.from_dict(data["body"]),
            headings=headings,
            tables=tables,
            font_aliases=dict(data.get("font_aliases") or {}),
        )


@dataclass(frozen=True)
class TemplateDefinition:
    """A complete prescriptive template."""

    id: str
    name: str
    version: str
    category: list[str]
    description: str
    rules: TemplateRules
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    @classmethod
    def from_dict(cls, data, *, source_path=None):
        from ..models import DocumentFactoryError

        data = data or {}
        required = ("id", "name", "version", "category", "description", "rules")
        missing = [k for k in required if k not in data]
        if missing:
            raise DocumentFactoryError(
                f"模板缺少必需字段: {', '.join(missing)}"
            )
        if not isinstance(data["category"], list):
            raise DocumentFactoryError("模板 category 必须是列表")
        return cls(
            id=data["id"],
            name=data["name"],
            version=str(data["version"]),
            category=list(data["category"]),
            description=data["description"],
            rules=TemplateRules.from_dict(data["rules"]),
            metadata=dict(data.get("metadata") or {}),
            source_path=str(source_path) if source_path else None,
        )


@dataclass(frozen=True)
class TemplateSummary:
    """Lightweight summary used by list_templates()."""

    id: str
    name: str
    version: str
    category: list[str]

    @classmethod
    def from_definition(cls, definition):
        return cls(
            id=definition.id,
            name=definition.name,
            version=definition.version,
            category=list(definition.category),
        )
