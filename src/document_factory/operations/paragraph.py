"""Deterministic paragraph-format operations (alignment, spacing, indentation)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ._oxml import PPR_ORDER, ensure_child, local, set_properties, set_toggle
from ..docx_reader import NS, q


@dataclass(frozen=True)
class ParagraphProfile:
    """Exact target paragraph facts. Empty/None groups are left untouched."""

    alignment: str | None = None
    spacing: dict = field(default_factory=dict)
    indent: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            alignment=data.get("alignment"),
            spacing=dict(data.get("spacing") or {}),
            indent=dict(data.get("indent") or {}),
        )


def _ppr(parent):
    return ensure_child(parent, "pPr", ["pPr", "rPr"] if local(parent) == "style" else ["pPr"])


def apply_alignment(parent, value, ctx, *, prop="alignment", rule_id=None, source=None):
    return set_properties(
        _ppr(parent), "jc", {"val": value}, set(), ctx,
        prop=prop, rule_id=rule_id, source=source, order=PPR_ORDER,
    )


def apply_spacing(parent, attrs, ctx, *, prop="spacing", remove=frozenset(),
                  rule_id=None, source=None):
    wanted = {key: value for key, value in attrs.items() if value is not None}
    if not wanted:
        return False
    return set_properties(
        _ppr(parent), "spacing", wanted, set(remove), ctx,
        prop=prop, rule_id=rule_id, source=source, order=PPR_ORDER,
    )


def apply_indent(parent, attrs, ctx, *, prop="indent", remove=frozenset(),
                 rule_id=None, source=None):
    wanted = {key: value for key, value in attrs.items() if value is not None}
    if not wanted:
        return False
    return set_properties(
        _ppr(parent), "ind", wanted, set(remove), ctx,
        prop=prop, rule_id=rule_id, source=source, order=PPR_ORDER,
    )


def apply_keep_next(parent, wanted, ctx, *, prop="keep_next", rule_id=None, source=None):
    """Set the w:keepNext paragraph toggle (keep paragraph on same page as next)."""
    return set_toggle(
        _ppr(parent), "keepNext", wanted, ctx,
        prop=prop, rule_id=rule_id, source=source, order=PPR_ORDER,
    )


def apply_paragraph_style(parent, style_id, ctx, *, prop="style", rule_id=None, source=None):
    """Bind a paragraph to a paragraph style via w:pStyle (created in order).

    The binding is a formatting change only; run text and structure are never
    touched. The pStyle child is always the first child of w:pPr.
    """
    p_pr = _ppr(parent)
    p_style = p_pr.find("w:pStyle", NS)
    before = p_style.get(q("val")) if p_style is not None else None
    if before == style_id:
        return False
    p_style = ensure_child(p_pr, "pStyle", PPR_ORDER)
    p_style.set(q("val"), style_id)
    ctx.record(prop, before, style_id, rule_id=rule_id, source=source)
    return True


def apply_paragraph_format(parent, profile, ctx, *, include_spacing=True, include_indent=True):
    """Apply alignment and (optionally) spacing/indentation in one batch."""
    profile = (
        profile if isinstance(profile, ParagraphProfile)
        else ParagraphProfile.from_dict(profile.get("paragraph", {}) if profile else {})
    )
    changed = False
    if profile.alignment is not None:
        changed |= apply_alignment(parent, profile.alignment, ctx)
    if include_spacing:
        changed |= apply_spacing(parent, profile.spacing, ctx)
    if include_indent:
        changed |= apply_indent(parent, profile.indent, ctx)
    return changed
