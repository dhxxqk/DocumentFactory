"""Unit tests for TemplateRegistry (templates.registry)."""
from __future__ import annotations

import pytest

from document_factory.templates import (
    TemplateAlreadyRegisteredError,
    TemplateDefinition,
    TemplateNotFoundError,
    TemplateRegistry,
    TemplateSummary,
)
from document_factory.templates.schema import BodyRule, HeadingRule, TemplateRules


def _make_definition(template_id="TECH_REPORT_V1", name="技术报告"):
    body = BodyRule(
        style_name="正文",
        chinese_font="仿宋",
        latin_font="Times New Roman",
        font_size_pt=12,
        first_line_indent_chars=2,
        line_spacing=1.5,
        space_before_pt=0,
        space_after_pt=0,
        alignment="both",
    )
    heading = HeadingRule(
        word_style="Heading 1",
        chinese_font="黑体",
        latin_font="Times New Roman",
        size_pt=16,
        color="000000",
        bold=True,
        alignment="left",
    )
    rules = TemplateRules(page={"page_size": "A4"}, body=body, headings={"h1": heading})
    return TemplateDefinition(
        id=template_id,
        name=name,
        version="1.0",
        category=["report"],
        description="测试模板",
        rules=rules,
    )


# ---- register + get + has -----------------------------------------------

def test_register_and_get_template():
    registry = TemplateRegistry()
    definition = _make_definition()
    registry.register_template(definition)
    assert registry.has_template("TECH_REPORT_V1")
    assert registry.get_template("TECH_REPORT_V1") is definition


def test_get_template_not_found_raises():
    registry = TemplateRegistry()
    with pytest.raises(TemplateNotFoundError) as exc:
        registry.get_template("MISSING")
    assert "MISSING" in str(exc.value)


def test_has_template_returns_false_for_missing():
    registry = TemplateRegistry()
    assert registry.has_template("MISSING") is False


def test_register_duplicate_id_raises():
    registry = TemplateRegistry()
    registry.register_template(_make_definition("DUP_ID"))
    with pytest.raises(TemplateAlreadyRegisteredError) as exc:
        registry.register_template(_make_definition("DUP_ID", name="另一个"))
    assert "DUP_ID" in str(exc.value)


def test_register_non_definition_raises():
    registry = TemplateRegistry()
    with pytest.raises(Exception):
        registry.register_template({"id": "not a definition"})  # type: ignore[arg-type]


# ---- list_templates ------------------------------------------------------

def test_list_templates_empty_returns_empty_list():
    registry = TemplateRegistry()
    assert registry.list_templates() == []


def test_list_templates_returns_summaries_sorted_by_id():
    registry = TemplateRegistry()
    registry.register_template(_make_definition("B_TEMPLATE", "B 模板"))
    registry.register_template(_make_definition("A_TEMPLATE", "A 模板"))
    summaries = registry.list_templates()
    assert [s.id for s in summaries] == ["A_TEMPLATE", "B_TEMPLATE"]
    assert all(isinstance(s, TemplateSummary) for s in summaries)
    assert summaries[0].name == "A 模板"


def test_list_templates_summary_fields_match_definition():
    registry = TemplateRegistry()
    registry.register_template(_make_definition("X", name="X 模板"))
    summary = registry.list_templates()[0]
    assert summary.id == "X"
    assert summary.name == "X 模板"
    assert summary.version == "1.0"
    assert summary.category == ["report"]


# ---- inheritance / exception hierarchy ----------------------------------

def test_registry_exceptions_are_document_factory_errors():
    from document_factory.models import DocumentFactoryError
    assert issubclass(TemplateNotFoundError, DocumentFactoryError)
    assert issubclass(TemplateAlreadyRegisteredError, DocumentFactoryError)


def test_get_template_returns_same_instance_registered():
    registry = TemplateRegistry()
    definition = _make_definition()
    registry.register_template(definition)
    assert registry.get_template(definition.id) is definition
