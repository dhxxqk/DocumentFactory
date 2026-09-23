"""Structural preparation for converting an arbitrary DOCX to a template.

Two deterministic structure passes (no content is ever rewritten):

1. ``ensure_template_styles`` — arbitrary input DOCX files usually lack the
   template's target styles (正文 / heading 1-3 / 表格表头 / 表格正文). The
   missing paragraph styles are scaffolded into word/styles.xml with facts
   taken verbatim from the TemplateDefinition, and registered into the parsed
   ``Document.styles`` map so resolver/lint/runner see them.

2. ``reassign_paragraph_styles`` — point classified paragraphs at the target
   styles by setting w:pStyle (created in schema order when absent). Cover
   and blank paragraphs are never touched.
"""
from __future__ import annotations

from lxml import etree

from ..docx_reader import NS, W, q, properties
from ..models import Style
from ..operations import OperationContext
from ..operations._oxml import PPR_ORDER, ensure_child

#: 脚手架样式固定 styleId（name 与模板/规范一致，id 仅为包内引用）
BODY_STYLE_ID = "DFBody"
HEADING_STYLE_IDS = {1: "DFHeading1", 2: "DFHeading2", 3: "DFHeading3"}
TABLE_HEADER_STYLE_ID = "DFTableHeader"
TABLE_BODY_STYLE_ID = "DFTableBody"


def _append_style(document, xml: str, style_id: str, name: str, based_on: str | None) -> Style:
    root = document.parts["word/styles.xml"]
    element = etree.fromstring(xml)
    root.append(element)
    props = properties(element.find("w:pPr", NS))
    props["rPr"] = properties(element.find("w:rPr", NS))
    style = Style(style_id, name, "paragraph", based_on, props, custom=False, default=False)
    document.styles[style_id] = style
    return style


def ensure_template_styles(document, template, changes: list) -> tuple[list[str], set[str]]:
    """Create target styles that the input document is missing.

    Returns ``(created_style_names, changed_parts)``. Existing styles with the
    same name are reused untouched.
    """
    existing_names = {s.name for s in document.styles.values() if s.kind == "paragraph"}
    based_on = document.default_style or None
    created: list[str] = []
    changed_parts: set[str] = set()
    rules = template.rules

    def record(name: str):
        changes.append({
            "object_type": "Style",
            "location": f"Style {name}",
            "property": "scaffold_create",
            "before": None,
            "after": name,
            "rule": "CONVERT_STYLE",
            "source": template.id,
        })
        changed_parts.add("word/styles.xml")

    based = f'<w:basedOn w:val="{based_on}"/>' if based_on else ""

    # 正文
    if rules.body.style_name not in existing_names:
        b = rules.body
        xml = (
            f'<w:style xmlns:w="{W}" w:type="paragraph" w:styleId="{BODY_STYLE_ID}">'
            f'<w:name w:val="{b.style_name}"/>{based}'
            f'<w:pPr><w:ind w:firstLineChars="{int(b.first_line_indent_chars * 100)}"/>'
            f'<w:spacing w:before="{int(b.space_before_pt * 20)}" w:after="{int(b.space_after_pt * 20)}" '
            f'w:line="{int(b.line_spacing * 240)}" w:lineRule="auto"/>'
            f'<w:jc w:val="{b.alignment}"/></w:pPr>'
            f'<w:rPr><w:rFonts w:ascii="{b.latin_font}" w:hAnsi="{b.latin_font}" '
            f'w:eastAsia="{b.chinese_font}" w:cs="{b.latin_font}"/>'
            f'<w:sz w:val="{int(b.font_size_pt * 2)}"/><w:szCs w:val="{int(b.font_size_pt * 2)}"/>'
            f'</w:rPr></w:style>'
        )
        _append_style(document, xml, BODY_STYLE_ID, b.style_name, based_on)
        created.append(b.style_name)
        record(b.style_name)

    # 标题 1-3
    for level, style_id in HEADING_STYLE_IDS.items():
        h = rules.headings.get(f"h{level}")
        if h is None or h.word_style.lower() in existing_names:
            continue
        name = h.word_style  # "Heading 1" 与内置名 "heading N" 同名异写，统一落为 heading N
        canonical = f"heading {level}"
        if canonical in existing_names:
            continue
        outline = level - 1
        xml = (
            f'<w:style xmlns:w="{W}" w:type="paragraph" w:styleId="{style_id}">'
            f'<w:name w:val="{canonical}"/>{based}'
            f'<w:qFormat/>'
            f'<w:pPr><w:keepNext/><w:outlineLvl w:val="{outline}"/>'
            f'<w:spacing w:before="240" w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>'
            f'<w:rPr><w:rFonts w:ascii="{h.latin_font}" w:hAnsi="{h.latin_font}" '
            f'w:eastAsia="{h.chinese_font}" w:cs="{h.latin_font}"/>'
            f'<w:b/><w:bCs/><w:color w:val="{h.color}"/>'
            f'<w:sz w:val="{int(h.size_pt * 2)}"/><w:szCs w:val="{int(h.size_pt * 2)}"/>'
            f'</w:rPr></w:style>'
        )
        _append_style(document, xml, style_id, canonical, based_on)
        created.append(canonical)
        record(canonical)

    # 表格表头 / 表格正文
    if rules.tables is not None:
        t = rules.tables
        specs = (
            ("表格表头", TABLE_HEADER_STYLE_ID, t.header_font, True, "center"),
            ("表格正文", TABLE_BODY_STYLE_ID, t.body_font, False, "start"),
        )
        for name, style_id, cn_font, bold, jc in specs:
            if name in existing_names:
                continue
            bold_xml = "<w:b/><w:bCs/>" if bold else ""
            xml = (
                f'<w:style xmlns:w="{W}" w:type="paragraph" w:styleId="{style_id}">'
                f'<w:name w:val="{name}"/>{based}'
                f'<w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
                f'<w:jc w:val="{jc}"/></w:pPr>'
                f'<w:rPr><w:rFonts w:ascii="{t.latin_font}" w:hAnsi="{t.latin_font}" '
                f'w:eastAsia="{cn_font}" w:cs="{t.latin_font}"/>{bold_xml}'
                f'<w:color w:val="000000"/>'
                f'<w:sz w:val="{int(t.font_size_pt * 2)}"/><w:szCs w:val="{int(t.font_size_pt * 2)}"/>'
                f'</w:rPr></w:style>'
            )
            _append_style(document, xml, style_id, name, based_on)
            created.append(name)
            record(name)

    return created, changed_parts


def _style_id_by_name(document, name: str) -> str | None:
    for style in document.styles.values():
        if style.kind == "paragraph" and style.name == name:
            return style.style_id
    return None


def reassign_paragraph_styles(document, assignments, template_id: str, changes: list) -> tuple[int, set[str]]:
    """Set w:pStyle on classified paragraphs. Content runs are never touched.

    Returns ``(reassignment_count, changed_parts)``. Paragraphs already using
    the target style, cover and blank paragraphs are skipped.
    """
    count = 0
    changed_parts: set[str] = set()
    by_index = {p.index: p for p in document.paragraphs if p.part == "word/document.xml"}
    for assignment in assignments:
        if assignment.target_style_name is None:
            continue
        paragraph = by_index.get(assignment.index)
        if paragraph is None or paragraph.element is None:
            continue
        target_id = _style_id_by_name(document, assignment.target_style_name)
        if target_id is None:
            continue
        if paragraph.style_id == target_id:
            continue
        before_name = document.styles.get(paragraph.style_id)
        before_label = before_name.name if before_name else paragraph.style_id
        p_pr = ensure_child(paragraph.element, "pPr", PPR_ORDER)
        p_style = p_pr.find("w:pStyle", NS)
        if p_style is None:
            p_style = etree.Element(q("pStyle"))
            p_pr.insert(0, p_style)
        p_style.set(q("val"), target_id)
        # 同步解析模型，保证 resolver/lint/runner 看到新样式。
        paragraph.style_id = target_id
        paragraph.properties["pStyle"] = target_id
        changes.append({
            "object_type": "Paragraph",
            "location": paragraph.location,
            "property": "style",
            "before": before_label,
            "after": assignment.target_style_name,
            "rule": f"CONVERT_{assignment.role.upper()}",
            "source": f"{template_id}.{assignment.role}（{assignment.reason}）",
        })
        changed_parts.add("word/document.xml")
        count += 1
    return count, changed_parts
