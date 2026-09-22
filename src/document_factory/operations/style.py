"""Deterministic style-level formatting operations.

The supported roles are the five roles already shared by the rule and template
engines. Role *detection* (which target style plays which role) stays with the
calling engines; this module only applies an already-resolved profile to an
already-identified style element.
"""
from __future__ import annotations

from ..docx_reader import NS
from .font import FontProfile, apply_font
from .paragraph import ParagraphProfile, apply_paragraph_format

STYLE_ROLES = ("Normal", "Title", "Heading1", "Heading2", "Heading3")


def find_style_element(document, style_id):
    """Return the w:style element with the given styleId, or None."""
    root = document.parts.get("word/styles.xml")
    if root is None:
        return None
    values = root.xpath('./w:style[@w:styleId=$sid]', sid=style_id, namespaces=NS)
    return values[0] if values else None


def apply_style(element, profile, ctx):
    """Apply paragraph and font facts from a template style profile dict.

    Expected profile shape (produced by template extractor)::

        {"font": {...}, "paragraph": {...}}
    """
    profile = profile or {}
    changed = apply_paragraph_format(
        element, ParagraphProfile.from_dict(profile.get("paragraph", {})), ctx,
    )
    changed |= apply_font(
        element, FontProfile.from_dict(profile.get("font", {})), ctx,
    )
    return changed
