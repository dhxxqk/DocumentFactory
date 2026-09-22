"""Deterministic run/font formatting operations.

Every function takes the current OOXML element (a w:r, w:p or w:style) plus
an explicit target profile. Operations never decide whether formatting *should*
change and never inspect document semantics; callers (rule engine, template
engine, future agents) make those decisions before invoking them.
"""
from __future__ import annotations

from dataclasses import dataclass

from ._oxml import RPR_ORDER, ensure_child, local, set_properties, set_toggle


@dataclass(frozen=True)
class FontProfile:
    """Exact target font facts. ``None`` means leave the attribute untouched."""

    east_asia: str | None = None
    latin: str | None = None
    size_pt: float | int | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    color: str | None = None

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            east_asia=data.get("east_asia"),
            latin=data.get("latin"),
            size_pt=data.get("size_pt"),
            bold=data.get("bold"),
            italic=data.get("italic"),
            underline=data.get("underline"),
            color=data.get("color"),
        )


def _rpr(parent):
    return ensure_child(parent, "rPr", ["pPr", "rPr"] if local(parent) == "style" else ["rPr"])


def apply_east_asian_font(parent, name, ctx, *, prop="font", rule_id=None, source=None):
    """Set only the eastAsia slot of w:rFonts and clear its theme override."""
    return set_properties(
        _rpr(parent), "rFonts", {"eastAsia": name}, {"eastAsiaTheme"}, ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_latin_font(parent, name, ctx, *, prop="font", rule_id=None, source=None):
    """Set only the ascii/hAnsi slots of w:rFonts and clear theme overrides."""
    return set_properties(
        _rpr(parent), "rFonts", {"ascii": name, "hAnsi": name},
        {"asciiTheme", "hAnsiTheme"}, ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_font_size(parent, size_pt, ctx, *, prop="font_size_pt", rule_id=None, source=None):
    return set_properties(
        _rpr(parent), "sz", {"val": int(float(size_pt) * 2)}, set(), ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_color(parent, hex_color, ctx, *, prop="color", rule_id=None, source=None):
    return set_properties(
        _rpr(parent), "color", {"val": hex_color},
        {"themeColor", "themeTint", "themeShade"}, ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_bold(parent, wanted, ctx, *, prop="bold", rule_id=None, source=None):
    return set_toggle(
        _rpr(parent), "b", wanted, ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_italic(parent, wanted, ctx, *, prop="italic", rule_id=None, source=None):
    return set_toggle(
        _rpr(parent), "i", wanted, ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_underline(parent, wanted, ctx, *, prop="underline", rule_id=None, source=None):
    return set_toggle(
        _rpr(parent), "u", wanted, ctx,
        prop=prop, rule_id=rule_id, source=source, order=RPR_ORDER,
    )


def apply_font(parent, profile, ctx):
    """Apply a full FontProfile as one deterministic batch.

    The w:rFonts element is written in a single operation so one change record
    covers the whole font-name group. Returns whether anything changed.
    """
    profile = profile if isinstance(profile, FontProfile) else FontProfile.from_dict(profile)
    changed = False
    wanted_fonts = {
        key: value for key, value in {
            "eastAsia": profile.east_asia,
            "ascii": profile.latin,
            "hAnsi": profile.latin,
        }.items() if value is not None
    }
    remove_fonts = set()
    if profile.east_asia is not None:
        remove_fonts.add("eastAsiaTheme")
    if profile.latin is not None:
        remove_fonts.update(("asciiTheme", "hAnsiTheme"))
    if wanted_fonts:
        changed |= set_properties(
            _rpr(parent), "rFonts", wanted_fonts, remove_fonts, ctx,
            prop="font", order=RPR_ORDER,
        )
    if profile.size_pt is not None:
        changed |= apply_font_size(parent, profile.size_pt, ctx)
    if profile.color is not None:
        changed |= apply_color(parent, profile.color, ctx)
    if profile.bold is not None:
        changed |= apply_bold(parent, profile.bold, ctx)
    if profile.italic is not None:
        changed |= apply_italic(parent, profile.italic, ctx)
    if profile.underline is not None:
        changed |= apply_underline(parent, profile.underline, ctx)
    return changed
