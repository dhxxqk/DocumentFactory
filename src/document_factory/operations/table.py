"""Deterministic table-content formatting operations.

First version intentionally covers only what the existing engines safely do:
table text font and paragraph alignment. Complex border migration, merged
cells and automatic column width are explicitly out of scope.
"""
from __future__ import annotations

from .font import FontProfile, apply_font
from .paragraph import apply_alignment


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
