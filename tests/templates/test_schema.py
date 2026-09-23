"""Unit tests for the TemplateDefinition schema (templates.schema)."""
from __future__ import annotations

import pytest

from document_factory.models import DocumentFactoryError
from document_factory.templates import (
    BodyRule,
    HeadingRule,
    TableRule,
    TemplateDefinition,
    TemplateRules,
    TemplateSummary,
)


def _body_dict(**overrides):
    base = {
        "style_name": "正文",
        "chinese_font": "仿宋",
        "latin_font": "Times New Roman",
        "font_size_pt": 12,
        "first_line_indent_chars": 2,
        "line_spacing": 1.5,
        "space_before_pt": 0,
        "space_after_pt": 0,
        "alignment": "both",
    }
    base.update(overrides)
    return base


def _heading_dict(**overrides):
    base = {
        "word_style": "Heading 1",
        "chinese_font": "黑体",
        "latin_font": "Times New Roman",
        "size_pt": 16,
        "color": "000000",
        "bold": True,
        "alignment": "left",
    }
    base.update(overrides)
    return base


def _rules_dict(**overrides):
    base = {
        "page": {"page_size": "A4", "orientation": "portrait"},
        "body": _body_dict(),
        "headings": {
            "h1": _heading_dict(),
            "h2": _heading_dict(word_style="Heading 2", size_pt=14),
            "h3": _heading_dict(word_style="Heading 3", size_pt=12),
        },
        "tables": {
            "header_font": "黑体",
            "body_font": "仿宋",
            "latin_font": "Times New Roman",
            "font_size_pt": 10.5,
            "alignment": "center",
        },
        "font_aliases": {"仿宋": ["仿宋", "FangSong"]},
    }
    base.update(overrides)
    return base


def _definition_dict(**overrides):
    base = {
        "id": "TECH_REPORT_V1",
        "name": "技术报告模板",
        "version": "1.0",
        "category": ["report"],
        "description": "示例模板",
        "rules": _rules_dict(),
        "metadata": {"author": "dhxxqk"},
    }
    base.update(overrides)
    return base


# ---- BodyRule / HeadingRule / TableRule ----------------------------------

def test_body_rule_from_dict_full_fields():
    body = BodyRule.from_dict(_body_dict())
    assert body.style_name == "正文"
    assert body.chinese_font == "仿宋"
    assert body.font_size_pt == 12
    assert body.first_line_indent_chars == 2
    assert body.line_spacing == 1.5


def test_body_rule_from_dict_missing_field_raises():
    data = _body_dict()
    data.pop("alignment")
    with pytest.raises(DocumentFactoryError) as exc:
        BodyRule.from_dict(data)
    assert "alignment" in str(exc.value)


def test_heading_rule_from_dict():
    heading = HeadingRule.from_dict(_heading_dict())
    assert heading.word_style == "Heading 1"
    assert heading.bold is True
    assert heading.color == "000000"


def test_table_rule_from_dict():
    table = TableRule.from_dict({
        "header_font": "黑体",
        "body_font": "仿宋",
        "latin_font": "Times New Roman",
        "font_size_pt": 10.5,
        "alignment": "center",
    })
    assert table.font_size_pt == 10.5
    assert table.header_font == "黑体"


def test_table_rule_from_dict_missing_field_raises():
    data = {
        "header_font": "黑体",
        "body_font": "仿宋",
        "latin_font": "Times New Roman",
        "font_size_pt": 10.5,
    }
    with pytest.raises(DocumentFactoryError):
        TableRule.from_dict(data)


# ---- TemplateRules -------------------------------------------------------

def test_template_rules_optional_tables_defaults_to_none():
    rules = TemplateRules.from_dict({
        "page": {"page_size": "A4"},
        "body": _body_dict(),
        "headings": {"h1": _heading_dict()},
    })
    assert rules.tables is None
    assert rules.font_aliases == {}


def test_template_rules_missing_body_raises():
    with pytest.raises(DocumentFactoryError):
        TemplateRules.from_dict({"page": {"page_size": "A4"}, "headings": {}})


def test_template_rules_missing_headings_raises():
    with pytest.raises(DocumentFactoryError):
        TemplateRules.from_dict({"page": {"page_size": "A4"}, "body": _body_dict()})


def test_template_rules_missing_page_raises():
    with pytest.raises(DocumentFactoryError):
        TemplateRules.from_dict({"body": _body_dict(), "headings": {}})


def test_template_rules_builds_headings_dict():
    rules = TemplateRules.from_dict({
        "page": {"page_size": "A4"},
        "body": _body_dict(),
        "headings": {
            "h1": _heading_dict(),
            "h2": _heading_dict(word_style="Heading 2"),
        },
    })
    assert set(rules.headings) == {"h1", "h2"}
    assert all(isinstance(h, HeadingRule) for h in rules.headings.values())


# ---- TemplateDefinition -------------------------------------------------

def test_definition_from_dict_full():
    definition = TemplateDefinition.from_dict(_definition_dict())
    assert definition.id == "TECH_REPORT_V1"
    assert definition.version == "1.0"
    assert definition.category == ["report"]
    assert isinstance(definition.rules, TemplateRules)
    assert definition.metadata == {"author": "dhxxqk"}
    assert definition.source_path is None


def test_definition_from_dict_records_source_path(tmp_path):
    src = tmp_path / "template.yaml"
    src.write_text("placeholder", encoding="utf-8")
    definition = TemplateDefinition.from_dict(_definition_dict(), source_path=src)
    assert definition.source_path == str(src)


def test_definition_from_dict_missing_required_field_raises():
    for field_name in ("id", "name", "version", "category", "description", "rules"):
        data = _definition_dict()
        data.pop(field_name)
        with pytest.raises(DocumentFactoryError) as exc:
            TemplateDefinition.from_dict(data)
        assert field_name in str(exc.value)


def test_definition_from_dict_category_must_be_list():
    data = _definition_dict()
    data["category"] = "report"
    with pytest.raises(DocumentFactoryError):
        TemplateDefinition.from_dict(data)


def test_definition_from_dict_version_coerced_to_string():
    data = _definition_dict()
    data["version"] = 1.0
    definition = TemplateDefinition.from_dict(data)
    assert definition.version == "1.0"
    assert isinstance(definition.version, str)


def test_definition_metadata_defaults_to_empty_dict():
    data = _definition_dict()
    data.pop("metadata")
    definition = TemplateDefinition.from_dict(data)
    assert definition.metadata == {}


# ---- TemplateSummary ----------------------------------------------------

def test_template_summary_from_definition():
    definition = TemplateDefinition.from_dict(_definition_dict())
    summary = TemplateSummary.from_definition(definition)
    assert summary.id == "TECH_REPORT_V1"
    assert summary.name == "技术报告模板"
    assert summary.version == "1.0"
    assert summary.category == ["report"]


def test_template_definition_is_frozen():
    definition = TemplateDefinition.from_dict(_definition_dict())
    with pytest.raises(Exception):
        definition.id = "OTHER"  # type: ignore[misc]
