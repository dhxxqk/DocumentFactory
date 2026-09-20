"""Extract stable template facts through Document and StyleResolver."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from lxml import etree

from ..docx_reader import NS, properties, q
from ..style_resolver import StyleResolver


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _font_profile(resolver: StyleResolver, rpr: dict[str, Any]) -> dict[str, Any]:
    east_asia, east_asia_source = resolver.font(rpr, "cn")
    latin, latin_source = resolver.font(rpr, "ascii")
    fonts = rpr.get("rFonts", {})
    east_asia = east_asia or fonts.get("eastAsia")
    latin = latin or fonts.get("ascii") or fonts.get("hAnsi")
    size_half_points = _number(rpr.get("sz"))
    color = rpr.get("color", {})
    return {
        "east_asia": east_asia,
        "east_asia_source": east_asia_source,
        "latin": latin,
        "latin_source": latin_source,
        "size_pt": None if size_half_points is None else size_half_points / 2,
        "bold": bool(rpr.get("b", False)),
        "italic": bool(rpr.get("i", False)),
        "color": color.get("val") if isinstance(color, dict) else None,
    }


def _paragraph_profile(props: dict[str, Any]) -> dict[str, Any]:
    spacing = props.get("spacing", {})
    indent = props.get("ind", {})
    return {
        "alignment": props.get("jc"),
        "spacing": {key: spacing.get(key) for key in ("before", "after", "line", "lineRule")},
        "indent": {
            key: indent.get(key)
            for key in ("firstLine", "firstLineChars", "hanging", "hangingChars", "left", "right")
        },
    }


def format_profile(resolver: StyleResolver, paragraph_props: dict[str, Any], run_props: dict[str, Any]) -> dict[str, Any]:
    return {
        "font": _font_profile(resolver, run_props),
        "paragraph": _paragraph_profile(paragraph_props),
    }


def extract_style(document, resolver: StyleResolver, style_id: str) -> dict[str, Any]:
    style = document.styles[style_id]
    effective = resolver.style(style_id)
    profile = format_profile(resolver, effective, effective.get("rPr", {}))
    profile.update({
        "style_id": style.style_id,
        "name": style.name,
        "kind": style.kind,
        "based_on": style.based_on,
        "custom": style.custom,
        "default": style.default,
        "numbering": deepcopy(effective.get("numPr")),
    })
    return profile


def extract_roles(document) -> dict[str, str]:
    roles: dict[str, str] = {}
    for style in document.styles.values():
        if style.kind != "paragraph":
            continue
        normalized = re.sub(r"\s+", "", style.name).casefold()
        style_id = re.sub(r"\s+", "", style.style_id).casefold()
        if style.default or normalized in {"normal", "常规"} or style_id == "normal":
            roles.setdefault("Normal", style.style_id)
        match = re.fullmatch(r"(?:heading|标题)([1-3])", normalized)
        if match and not style.custom:
            roles[f"Heading{match.group(1)}"] = style.style_id
        if normalized in {"title", "标题"} or style_id == "title":
            roles.setdefault("Title", style.style_id)
    return roles


def _story_profile(document, prefix: str) -> list[dict[str, Any]]:
    result = []
    for name in sorted(part for part in document.parts if re.fullmatch(fr"word/{prefix}[^/]*\.xml", part)):
        paragraphs = [p for p in document.paragraphs if p.part == name]
        fields = [field for field in document.fields if field.part == name]
        result.append({
            "part": name,
            "paragraph_count": len(paragraphs),
            "style_ids": sorted({p.style_id for p in paragraphs}),
            "field_kinds": sorted({field.kind for field in fields if field.kind}),
        })
    return result


def extract_page(document) -> dict[str, Any]:
    sections = []
    for section in document.sections:
        size = dict(section.get("size", {}))
        margins = dict(section.get("margins", {}))
        width, height = _number(size.get("w")), _number(size.get("h"))
        page_name = "A4" if width is not None and height is not None and {
            round(width), round(height)
        } in ({11906, 16838}, {16838, 11906}) else None
        sections.append({
            "index": section["index"],
            "size": {
                "name": page_name,
                "width_twips": width,
                "height_twips": height,
                "orientation": size.get("orient", "landscape" if width and height and width > height else "portrait"),
            },
            "margins": {
                key: {
                    "twips": _number(value),
                    "cm": None if _number(value) is None else round(float(value) / 1440 * 2.54, 4),
                }
                for key, value in margins.items()
            },
            "break_type": section.get("break_type"),
            "page_numbering": deepcopy(section.get("properties", {}).get("pgNumType")),
        })
    return {"section_count": len(sections), "sections": sections}


def _border_profile(parent) -> dict[str, dict[str, str]]:
    if parent is None:
        return {}
    borders = parent.find("w:tblBorders", NS)
    if borders is None:
        return {}
    return {
        etree.QName(child).localname: {etree.QName(key).localname: value for key, value in child.attrib.items()}
        for child in borders
    }


def extract_table_styles(document) -> dict[str, dict[str, Any]]:
    root = document.parts.get("word/styles.xml")
    if root is None:
        return {}
    result = {}
    for element in root.xpath('./w:style[@w:type="table"]', namespaces=NS):
        style_id = element.get(q("styleId"), "")
        conditionals = {}
        for conditional in element.findall("w:tblStylePr", NS):
            kind = conditional.get(q("type"), "unknown")
            conditionals[kind] = {
                "paragraph": _paragraph_profile(properties(conditional.find("w:pPr", NS))),
                "run_properties": properties(conditional.find("w:rPr", NS)),
                "borders": _border_profile(conditional.find("w:tblPr", NS)),
            }
        result[style_id] = {
            "style_id": style_id,
            "name": element.find("w:name", NS).get(q("val"), style_id) if element.find("w:name", NS) is not None else style_id,
            "based_on": element.find("w:basedOn", NS).get(q("val")) if element.find("w:basedOn", NS) is not None else None,
            "borders": _border_profile(element.find("w:tblPr", NS)),
            "conditionals": conditionals,
        }
    return result


def paragraph_format(document, resolver: StyleResolver, paragraph) -> dict[str, Any]:
    paragraph_props = resolver.paragraph(paragraph)
    visible_run = next((run for run in paragraph.runs if run.text.strip()), None)
    run_props = resolver.run(paragraph, visible_run) if visible_run is not None else paragraph_props.get("rPr", {})
    return format_profile(resolver, paragraph_props, run_props)


def extract_table_defaults(document, resolver: StyleResolver) -> dict[str, dict[str, Any]]:
    main_tables = [table for table in document.tables if table.part == "word/document.xml"]
    if not main_tables:
        return {}
    first_index = main_tables[0].index
    paragraphs = [
        paragraph for paragraph in document.paragraphs
        if paragraph.part == "word/document.xml" and paragraph.table == first_index and paragraph.text.strip()
    ]
    result = {}
    for role, candidates in (
        ("header", [p for p in paragraphs if p.row == 1]),
        ("body", [p for p in paragraphs if p.row and p.row > 1]),
    ):
        if candidates:
            result[role] = paragraph_format(document, resolver, candidates[0]) | {
                "source_style_id": candidates[0].style_id,
                "source_table_index": first_index,
            }
    return result


def extract_numbering(document) -> dict[str, Any]:
    style_ids = set()
    root = document.parts.get("word/numbering.xml")
    if root is not None:
        style_ids.update(
            element.get(q("val")) for element in root.findall(".//w:pStyle", NS) if element.get(q("val"))
        )
    for style in document.styles.values():
        num_pr = style.properties.get("numPr")
        if isinstance(num_pr, dict) and num_pr:
            style_ids.add(style.style_id)
    return {
        "exists": root is not None and bool(root.findall(".//w:num", NS)),
        "style_ids": sorted(style_ids),
        "abstract_numbering_count": 0 if root is None else len(root.findall("w:abstractNum", NS)),
        "numbering_instance_count": 0 if root is None else len(root.findall("w:num", NS)),
        "migration_supported": False,
    }


def extract_template_data(document) -> dict[str, Any]:
    resolver = StyleResolver(document)
    styles = {
        style_id: extract_style(document, resolver, style_id)
        for style_id, style in sorted(document.styles.items()) if style.kind == "paragraph"
    }
    return {
        "page": extract_page(document),
        "headers": _story_profile(document, "header"),
        "footers": _story_profile(document, "footer"),
        "styles": styles,
        "roles": extract_roles(document),
        "table_styles": extract_table_styles(document),
        "table_defaults": extract_table_defaults(document, resolver),
        "numbering": extract_numbering(document),
        "diagnostics": list(dict.fromkeys(document.diagnostics + resolver.diagnostics)),
    }
