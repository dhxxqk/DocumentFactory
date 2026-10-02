"""Deterministic style-level formatting operations.

The supported roles are the five roles already shared by the rule and template
engines. Role *detection* (which target style plays which role) stays with the
calling engines; this module only applies an already-resolved profile to an
already-identified style element.
"""
from __future__ import annotations

from lxml import etree

from ..docx_reader import NS, q
from .font import FontProfile, apply_font
from .paragraph import ParagraphProfile, apply_paragraph_format

STYLE_ROLES = ("Normal", "Title", "Heading1", "Heading2", "Heading3")

# ECMA-376 CT_Style child order (only the entries we may create).
_STYLE_ORDER = [
    "name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden",
    "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "locked",
    "personal", "personalCompose", "personalReply", "rsid",
    "pPr", "rPr", "tblPr", "trPr", "tcPr", "tblStylePr",
]


def find_style_element(document, style_id):
    """Return the w:style element with the given styleId, or None."""
    root = document.parts.get("word/styles.xml")
    if root is None:
        return None
    values = root.xpath('./w:style[@w:styleId=$sid]', sid=style_id, namespaces=NS)
    return values[0] if values else None


def create_paragraph_style(document, style_id, name, ctx, *, based_on=None,
                           q_format=True, default_style=False):
    """Create a new paragraph style element in word/styles.xml and return it.

    Structural scaffolding only: paragraph/font facts are filled afterwards
    through the regular deterministic paragraph/font operations so that every
    format fact stays attributable. The new w:style element is appended to the
    styles part; Word does not require a particular order between sibling
    w:style elements.
    """
    root = document.parts.get("word/styles.xml")
    if root is None:
        raise ValueError("document has no word/styles.xml part")
    element = etree.Element(q("style"))
    element.set(q("type"), "paragraph")
    element.set(q("styleId"), style_id)
    if default_style:
        element.set(q("default"), "1")
    name_el = etree.SubElement(element, q("name"))
    name_el.set(q("val"), name)
    if based_on:
        based = etree.Element(q("basedOn"))
        based.set(q("val"), based_on)
        _insert_ordered(element, based)
    if q_format:
        etree.SubElement(element, q("qFormat"))
    root.append(element)
    ctx.record("style_create", None, name, rule_id=ctx.rule_id, source=ctx.source)
    return element


def apply_based_on(style_element, target_id, ctx, *, prop="style_based_on",
                   rule_id=None, source=None):
    """Set or remove the w:basedOn reference of a style element.

    ``target_id=None`` breaks the inheritance chain (used when a table style
    must no longer inherit from the body style).
    """
    child = style_element.find("w:basedOn", NS)
    before = child.get(q("val")) if child is not None else None
    if target_id is None:
        if child is None:
            return False
        style_element.remove(child)
        ctx.record(prop, before, None, rule_id=rule_id, source=source)
        return True
    if before == target_id:
        return False
    if child is None:
        child = etree.Element(q("basedOn"))
        _insert_ordered(style_element, child)
    child.set(q("val"), target_id)
    ctx.record(prop, before, target_id, rule_id=rule_id, source=source)
    return True


def _insert_ordered(style_element, child):
    name = etree.QName(child).localname
    if name not in _STYLE_ORDER:
        style_element.append(child)
        return
    target = _STYLE_ORDER.index(name)
    for index, current in enumerate(style_element):
        current_name = etree.QName(current).localname
        if current_name in _STYLE_ORDER and _STYLE_ORDER.index(current_name) > target:
            style_element.insert(index, child)
            break
    else:
        style_element.append(child)


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
