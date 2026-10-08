"""Real paragraph-style binding for the default technical specification.

Prior normalisation kept the original ``w:pStyle`` and only layered direct
formatting on top. Under V1.4 the formal body text and every regular-table
cell must instead be *bound* to dedicated, explicitly defined paragraph
styles (正文 / 表格表头 / 表格正文 / 表格正文-居中).

This module owns only the structural part of that work:

1. create the dedicated paragraph styles when the package lacks them (table
   styles are created WITHOUT any basedOn chain so the body style can never
   pollute them again);
2. break an existing table-style basedOn chain that reaches 正文;
3. keep the in-memory ``document.styles`` model in sync with the XML so the
   StyleResolver sees the freshly created/filled styles within the same run;
4. rebind an individual paragraph to a target style and mirror the result in
   the parsed paragraph model.

Every mutation goes through the Formatting Operation Layer; no text, table
structure or content is touched.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .docx_reader import NS, properties, q
from .models import Style
from .operations import (
    OperationContext,
    apply_based_on,
    apply_paragraph_style,
    create_paragraph_style,
    find_style_element,
)

BODY_STYLE_ID = "DFBody"
TABLE_HEADER_STYLE_ID = "DFTableHeader"
TABLE_BODY_STYLE_ID = "DFTableBody"
TABLE_CENTER_STYLE_ID = "DFTableBodyCenter"


@dataclass
class BindingStyleSet:
    """Resolved styleIds of the dedicated binding styles (None = unavailable)."""

    body_id: str | None = None
    table_header_id: str | None = None
    table_body_id: str | None = None
    table_center_id: str | None = None
    created: dict[str, str] = field(default_factory=dict)  # style name -> styleId

    def as_dict(self) -> dict:
        return {
            "body": self.body_id,
            "table_header": self.table_header_id,
            "table_body": self.table_body_id,
            "table_center": self.table_center_id,
        }


def _ctx(changes, rules, rule_id, *, object_type="Style", location="word/styles.xml"):
    return OperationContext(
        changes=changes,
        object_type=object_type,
        location=location,
        rule_id=rule_id,
        source=rules["rules"][rule_id]["source"],
    )


def style_id_by_name(document, name):
    for style in document.styles.values():
        if style.kind == "paragraph" and style.name == name:
            return style.style_id
    return None


def _unique_style_id(document, preferred):
    existing = set(document.styles)
    root = document.parts.get("word/styles.xml")
    if root is not None:
        existing.update(root.xpath("./w:style/@w:styleId", namespaces=NS))
    if preferred not in existing:
        return preferred
    suffix = 2
    while f"{preferred}{suffix}" in existing:
        suffix += 1
    return f"{preferred}{suffix}"


def _register(document, style_id, name, based_on):
    """Mirror a styles.xml paragraph style into the in-memory document model."""
    element = find_style_element(document, style_id)
    props = properties(element.find("w:pPr", NS)) if element is not None else {}
    props["rPr"] = properties(element.find("w:rPr", NS)) if element is not None else {}
    document.styles[style_id] = Style(
        style_id, name, "paragraph", based_on, props, custom=False, default=False
    )


def sync_style_model(document, style_id):
    """Re-parse a style element into its registered Style model object."""
    style = document.styles.get(style_id)
    element = find_style_element(document, style_id)
    if style is None or element is None:
        return
    based = element.find("w:basedOn", NS)
    style.based_on = based.get(q("val")) if based is not None else None
    style.properties = properties(element.find("w:pPr", NS))
    style.properties["rPr"] = properties(element.find("w:rPr", NS))


def _chain_reaches_body(document, style_id, body_name):
    seen = set()
    while style_id and style_id not in seen:
        seen.add(style_id)
        style = document.styles.get(style_id)
        if style is None:
            return False
        if style.name == body_name:
            return True
        style_id = style.based_on
    return False


def ensure_binding_styles(document, rules, changes):
    """Create missing dedicated styles and isolate table styles from 正文.

    Returns a resolved :class:`BindingStyleSet`. Only styles whose gate is
    enabled in the rules are created; callers skip binding of missing ids.
    """
    result = BindingStyleSet()
    body_config = rules["body"]
    table_config = rules["tables"]
    body_enabled = bool(body_config.get("style_binding"))
    table_enabled = bool(table_config.get("style_binding"))

    header_name = table_config["required_styles"][0]
    body_table_name = table_config["required_styles"][1]
    center_name = table_config["optional_styles"][0] if table_config.get("optional_styles") else None
    body_name = body_config["style_name"]

    def create(name, preferred_id, rule_id):
        style_id = _unique_style_id(document, preferred_id)
        create_paragraph_style(
            document, style_id, name, _ctx(changes, rules, rule_id),
            based_on=None, q_format=True,
        )
        _register(document, style_id, name, None)
        result.created[name] = style_id
        return style_id

    def resolve(name, preferred_id, rule_id):
        style_id = style_id_by_name(document, name)
        if style_id is None:
            return create(name, preferred_id, rule_id) if rule_id else None
        return style_id

    if body_enabled:
        result.body_id = resolve(body_name, BODY_STYLE_ID, "BODY001")

    if table_enabled:
        result.table_header_id = resolve(header_name, TABLE_HEADER_STYLE_ID, "TABLE010")
        result.table_body_id = resolve(body_table_name, TABLE_BODY_STYLE_ID, "TABLE010")
        if center_name:
            result.table_center_id = resolve(center_name, TABLE_CENTER_STYLE_ID, "TABLE010")

        # Table styles must never inherit from the body style: an existing
        # chain reaching 正文 would reintroduce the 2-char indent and the
        # 仿宋/12pt body facts into table cells.
        for name, style_id in (
            (header_name, result.table_header_id),
            (body_table_name, result.table_body_id),
            (center_name, result.table_center_id),
        ):
            if style_id is None:
                continue
            if _chain_reaches_body(document, style_id, body_name):
                element = find_style_element(document, style_id)
                if element is not None:
                    apply_based_on(
                        element, None, _ctx(changes, rules, "TABLE005"),
                        prop="style_based_on",
                    )
                    sync_style_model(document, style_id)

    return result


def bind_paragraph_style(document, paragraph, style_id, rules, changes, *, rule_id):
    """Rebind one paragraph to ``style_id`` and sync the parsed paragraph model.

    Returns True when the pStyle actually changed. Content is never touched;
    changing pStyle is a formatting-only mutation.
    """
    if paragraph.style_id == style_id:
        return False
    ctx = OperationContext(
        changes=changes,
        object_type="Paragraph",
        location=paragraph.location,
        rule_id=rule_id,
        source=rules["rules"][rule_id]["source"],
    )
    changed = apply_paragraph_style(paragraph.element, style_id, ctx)
    if changed:
        paragraph.style_id = style_id
        paragraph.properties["pStyle"] = style_id
    return changed
