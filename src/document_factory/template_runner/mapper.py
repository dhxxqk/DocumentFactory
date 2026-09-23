"""Mapper: TemplateDefinition -> OperationPlan (pure, no document).

Translates the human-authored template units (cm, pt, chars, line-spacing
multiplier) into the OOXML units the operations layer expects (twips,
half-points, firstLineChars, line in 240ths). The conversions mirror
``normalizer._normalize_body_ppr`` so lint and the runner agree on what
"2 chars" and "1.5 line spacing" mean.
"""
from __future__ import annotations

from ..operations import PAGE_SIZES, FontProfile, PageFormat, ParagraphProfile
from ..templates import TemplateDefinition
from .models import OperationPlan


def _cm_to_twips(cm: float) -> int:
    """1 inch = 1440 twips, 1 inch = 2.54 cm."""
    return int(round(float(cm) * 1440 / 2.54))


def _build_body_font(rule) -> FontProfile:
    return FontProfile(
        east_asia=rule.chinese_font,
        latin=rule.latin_font,
        size_pt=rule.font_size_pt,
    )


def _build_body_paragraph(rule) -> ParagraphProfile:
    return ParagraphProfile(
        alignment=rule.alignment,
        spacing={
            "before": int(float(rule.space_before_pt) * 20),
            "after": int(float(rule.space_after_pt) * 20),
            "line": int(float(rule.line_spacing) * 240),
            "lineRule": "auto",
        },
        indent={
            "firstLineChars": int(rule.first_line_indent_chars * 100),
        },
    )


def _build_heading_font(rule) -> FontProfile:
    return FontProfile(
        east_asia=rule.chinese_font,
        latin=rule.latin_font,
        size_pt=rule.size_pt,
        color=rule.color,
        bold=rule.bold,
    )


def _build_page(page: dict) -> PageFormat | None:
    page_size = page.get("page_size")
    width = height = None
    if page_size and page_size in PAGE_SIZES:
        width, height = PAGE_SIZES[page_size]
    orientation = page.get("orientation")
    if orientation == "landscape" and width is not None and height is not None:
        width, height = height, width
    margins_cm = page.get("margins_cm") or {}
    margins_twips = {
        key: _cm_to_twips(value)
        for key, value in margins_cm.items()
        if key in ("top", "right", "bottom", "left", "header", "footer", "gutter")
    }
    if width is None and height is None and not margins_twips and not orientation:
        return None
    return PageFormat(
        width_twips=width,
        height_twips=height,
        orientation=orientation,
        margins=margins_twips,
    )


def _build_table_font(rule) -> FontProfile | None:
    return FontProfile(
        east_asia=rule.header_font,
        latin=rule.latin_font,
        size_pt=rule.font_size_pt,
    )


def build_operation_plan(template: TemplateDefinition) -> OperationPlan:
    """Translate a TemplateDefinition into an OperationPlan.

    Pure: no filesystem, no DOCX. The runner consumes the result against a
    Document. Missing optional groups (page/tables) yield None and are
    skipped by the runner.
    """
    rules = template.rules
    body = rules.body
    heading_fonts = {
        level: _build_heading_font(rule)
        for level, rule in rules.headings.items()
    }
    page = _build_page(rules.page) if rules.page else None
    table_font = _build_table_font(rules.tables) if rules.tables else None
    table_alignment = rules.tables.alignment if rules.tables else None
    table_style_names = list(rules.tables.style_names) if rules.tables else []
    return OperationPlan(
        body_font=_build_body_font(body),
        body_paragraph=_build_body_paragraph(body),
        heading_fonts=heading_fonts,
        page=page,
        table_font=table_font,
        table_alignment=table_alignment,
        table_style_names=table_style_names,
    )
