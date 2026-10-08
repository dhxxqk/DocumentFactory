"""Deterministic table-content formatting operations.

First version intentionally covers only what the existing engines safely do:
table text font and paragraph alignment. Complex border migration, merged
cells and automatic column width are explicitly out of scope.
"""
from __future__ import annotations

from ..docx_reader import NS
from ._oxml import TCPR_ORDER, ensure_child, set_properties
from .font import FontProfile, apply_font
from .paragraph import apply_alignment


def apply_cell_shading(tc, fill, ctx, *, color="auto", rule_id=None, source=None):
    """Set explicit w:shd fill on a w:tc and drop theme fill references.

    The shading is made deterministic: val=clear, color=auto and an explicit
    hex fill; themeFill/themeFillTint/themeFillShade are removed so the
    rendered gray cannot drift with the document theme.
    """
    tc_pr = tc.find("w:tcPr", NS)
    if tc_pr is None:
        tc_pr = ensure_child(tc, "tcPr", TCPR_ORDER)
    return set_properties(
        tc_pr, "shd",
        {"val": "clear", "color": color, "fill": str(fill)},
        {"themeFill", "themeFillTint", "themeFillShade"},
        ctx, prop="cell_shading", rule_id=rule_id, source=source,
        order=TCPR_ORDER,
    )


def apply_table_font(parent, profile, ctx):
    """Apply font facts (including size/color/bold/italic when present)."""
    return apply_font(parent, FontProfile.from_dict((profile or {}).get("font", {})), ctx)


def apply_table_alignment(parent, alignment, ctx, *, rule_id=None, source=None):
    return apply_alignment(
        parent, alignment, ctx, rule_id=rule_id, source=source,
    )


def apply_table_format(parent, profile, ctx, *, include_paragraph=True, include_run=True):
    """Apply the table-basic subset: paragraph alignment plus run font."""
    profile = profile or {}
    changed = False
    if include_paragraph:
        alignment = profile.get("paragraph", {}).get("alignment")
        if alignment is not None:
            changed |= apply_table_alignment(parent, alignment, ctx)
    if include_run:
        changed |= apply_table_font(parent, profile, ctx)
    return changed
