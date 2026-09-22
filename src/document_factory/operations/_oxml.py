"""Private OOXML writing kernel shared by every deterministic formatting operation.

This module is an internal implementation detail of the operations layer.
It deliberately contains no rules, templates, or semantic decisions: callers
decide *whether* and *what* to change; these helpers only apply exact
attribute values to the right OOXML child elements and record the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from ..docx_reader import NS, q

PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
    "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
    "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
    "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
]
RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
    "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden",
    "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
    "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath", "rPrChange",
]
SECTPR_ORDER = [
    "headerReference", "footerReference", "footnotePr", "endnotePr", "type", "pgSz", "pgMar",
    "paperSrc", "pgBorders", "lnNumType", "pgNumType", "cols", "formProt", "vAlign", "noEndnote",
    "titlePg", "textDirection", "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange",
]


def local(element) -> str:
    return etree.QName(element).localname


def ensure_child(parent, name, order=None):
    child = parent.find(f"w:{name}", NS)
    if child is not None:
        return child
    child = etree.Element(q(name))
    if (name == "pPr" and local(parent) == "p") or (name == "rPr" and local(parent) == "r"):
        parent.insert(0, child)
        return child
    if order and name in order:
        target = order.index(name)
        for index, current in enumerate(parent):
            current_name = local(current)
            if current_name in order and order.index(current_name) > target:
                parent.insert(index, child)
                break
        else:
            parent.append(child)
    else:
        parent.append(child)
    return child


def attributes(element) -> dict[str, str]:
    if element is None:
        return {}
    return {etree.QName(key).localname: value for key, value in element.attrib.items()}


@dataclass
class OperationContext:
    """Attribution and sink for one deterministic formatting application."""

    changes: list[dict[str, Any]]
    object_type: str
    location: str
    rule_id: str = ""
    source: str = ""
    prefix: str = ""

    def record(self, prop, before, after, *, rule_id=None, source=None):
        self.changes.append({
            "object_type": self.object_type,
            "location": self.location,
            "property": f"{self.prefix}{prop}",
            "before": before,
            "after": after,
            "rule": rule_id if rule_id is not None else self.rule_id,
            "source": source if source is not None else self.source,
        })


def set_properties(parent, child_name, wanted, remove, ctx, *, prop, order=None,
                   rule_id=None, source=None):
    """Set exact attributes on an OOXML child; return whether anything changed."""
    child = parent.find(f"w:{child_name}", NS)
    before = attributes(child)
    after = dict(before)
    for key in remove:
        after.pop(key, None)
    after.update({key: str(value) for key, value in wanted.items()})
    if before == after:
        return False
    child = child if child is not None else ensure_child(parent, child_name, order)
    for key in remove:
        child.attrib.pop(q(key), None)
    for key, value in wanted.items():
        child.set(q(key), str(value))
    ctx.record(prop, before, after, rule_id=rule_id, source=source)
    return True


def set_toggle(parent, child_name, wanted, ctx, *, prop, order=None, rule_id=None, source=None):
    """Set an OOXML on/off toggle (w:b / w:i / w:u style on/off switches)."""
    child = parent.find(f"w:{child_name}", NS)
    if child_name == "u":
        before = None if child is None else child.get(q("val"), "single") not in ("none", "0", "false", "off")
        wanted = bool(wanted)
        if before is wanted:
            return False
        child = child if child is not None else ensure_child(parent, child_name, order)
        child.set(q("val"), "single" if wanted else "none")
    else:
        before = None if child is None else child.get(q("val"), "1") not in ("0", "false", "off")
        wanted = bool(wanted)
        if before is wanted:
            return False
        child = child if child is not None else ensure_child(parent, child_name, order)
        child.set(q("val"), "1" if wanted else "0")
    ctx.record(prop, before, wanted, rule_id=rule_id, source=source)
    return True
