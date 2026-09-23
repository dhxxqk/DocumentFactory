"""Unit tests for the template mapper (template_runner.mapper)."""
from __future__ import annotations

import pytest

from document_factory.operations import FontProfile, PageFormat, ParagraphProfile
from document_factory.templates import load_template
from document_factory.template_runner import OperationPlan, build_operation_plan


@pytest.fixture(scope="module")
def plan():
    return build_operation_plan(load_template("GRID_TECH_V1_4"))


def test_build_operation_plan_returns_operation_plan(plan):
    assert isinstance(plan, OperationPlan)


def test_body_font_fields(plan):
    assert isinstance(plan.body_font, FontProfile)
    assert plan.body_font.east_asia == "仿宋"
    assert plan.body_font.latin == "Times New Roman"
    assert plan.body_font.size_pt == 12


def test_body_paragraph_unit_conversions(plan):
    """chars*100, line_spacing*240, pt*20 (mirrors normalizer)."""
    assert isinstance(plan.body_paragraph, ParagraphProfile)
    assert plan.body_paragraph.alignment == "both"
    assert plan.body_paragraph.indent["firstLineChars"] == 200  # 2 chars * 100
    assert plan.body_paragraph.spacing["line"] == 360  # 1.5 * 240
    assert plan.body_paragraph.spacing["lineRule"] == "auto"
    assert plan.body_paragraph.spacing["before"] == 0  # 0pt * 20
    assert plan.body_paragraph.spacing["after"] == 0


def test_heading_fonts_for_h1_h2_h3(plan):
    assert set(plan.heading_fonts) == {"h1", "h2", "h3"}
    h1 = plan.heading_fonts["h1"]
    assert h1.east_asia == "黑体"
    assert h1.size_pt == 16
    assert h1.color == "000000"
    assert h1.bold is True
    assert plan.heading_fonts["h2"].size_pt == 14
    assert plan.heading_fonts["h3"].size_pt == 12


def test_page_format_converted_from_cm_to_twips(plan):
    assert isinstance(plan.page, PageFormat)
    assert plan.page.width_twips == 11906  # A4
    assert plan.page.height_twips == 16838
    assert plan.page.orientation == "portrait"
    # 2.8 cm -> 1587 twips, 2.6 cm -> 1474 twips
    assert plan.page.margins["top"] == 1587
    assert plan.page.margins["bottom"] == 1474
    assert plan.page.margins["left"] == 1587
    assert plan.page.margins["right"] == 1474


def test_table_font_and_style_names(plan):
    assert plan.table_font is not None
    assert plan.table_font.east_asia == "黑体"
    assert plan.table_font.size_pt == 10.5
    assert plan.table_alignment == "center"
    assert plan.table_style_names == ["表格表头", "表格正文"]


def test_operations_count_is_seven(plan):
    """body_font + body_paragraph + 3 headings + page + table = 7 groups."""
    assert plan.operations_count == 7


def test_build_operation_plan_is_pure_does_not_touch_filesystem():
    """No document argument required; no filesystem side effects."""
    from document_factory.templates import TemplateDefinition
    from document_factory.templates import BodyRule, HeadingRule, TemplateRules
    body = BodyRule(
        style_name="正文", chinese_font="仿宋", latin_font="Times New Roman",
        font_size_pt=12, first_line_indent_chars=2, line_spacing=1.5,
        space_before_pt=0, space_after_pt=0, alignment="both",
    )
    h1 = HeadingRule(
        word_style="Heading 1", chinese_font="黑体", latin_font="Times New Roman",
        size_pt=16, color="000000", bold=True, alignment="left",
    )
    rules = TemplateRules(
        page={"page_size": "A4", "orientation": "portrait",
              "margins_cm": {"top": 2.8, "bottom": 2.6, "left": 2.8, "right": 2.6}},
        body=body, headings={"h1": h1},
    )
    template = TemplateDefinition(
        id="X", name="X", version="1.0", category=["report"],
        description="pure test", rules=rules,
    )
    plan = build_operation_plan(template)
    assert plan.body_font.east_asia == "仿宋"
    assert plan.page.margins["top"] == 1587
    # No table rule -> table_font is None, not counted
    assert plan.table_font is None
    assert plan.operations_count == 4  # body_font + body_paragraph + h1 + page


def test_page_orientation_landscape_swaps_dimensions():
    from document_factory.templates import TemplateDefinition
    from document_factory.templates import BodyRule, TemplateRules
    body = BodyRule(
        style_name="正文", chinese_font="仿宋", latin_font="Times New Roman",
        font_size_pt=12, first_line_indent_chars=2, line_spacing=1.5,
        space_before_pt=0, space_after_pt=0, alignment="both",
    )
    rules = TemplateRules(
        page={"page_size": "A4", "orientation": "landscape",
              "margins_cm": {"top": 2.5, "bottom": 2.5, "left": 2.5, "right": 2.5}},
        body=body, headings={},
    )
    template = TemplateDefinition(
        id="LAND", name="L", version="1.0", category=["report"],
        description="landscape", rules=rules,
    )
    plan = build_operation_plan(template)
    assert plan.page.width_twips == 16838  # swapped
    assert plan.page.height_twips == 11906


def test_unknown_page_size_keeps_margins_only():
    from document_factory.templates import TemplateDefinition
    from document_factory.templates import BodyRule, TemplateRules
    body = BodyRule(
        style_name="正文", chinese_font="仿宋", latin_font="Times New Roman",
        font_size_pt=12, first_line_indent_chars=2, line_spacing=1.5,
        space_before_pt=0, space_after_pt=0, alignment="both",
    )
    rules = TemplateRules(
        page={"page_size": "B5", "orientation": "portrait",
              "margins_cm": {"top": 2.0, "bottom": 2.0, "left": 2.0, "right": 2.0}},
        body=body, headings={},
    )
    template = TemplateDefinition(
        id="B5", name="B", version="1.0", category=["report"],
        description="b5", rules=rules,
    )
    plan = build_operation_plan(template)
    assert plan.page.width_twips is None  # unknown page size
    assert plan.page.height_twips is None
    assert plan.page.margins["top"] == 1134  # 2.0 cm
