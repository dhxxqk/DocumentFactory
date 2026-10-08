"""实际可见格式统计（visible-format statistics）。

``analyzer.profile.analyze_document`` 主要回答样式层（styles.xml）事实；
真实文档大量格式直接堆在段落/Run/单元格上，仅看 styles.xml 会误判。本模块
统计**解析继承链之后的有效可见格式**，作为模板规则与 Pilot 前后对比的依据：

- 多 section 方向/尺寸/页边距；
- 正文 Run 的字体/字号/加粗/颜色、段落行距/首行缩进/对齐分布；
- 内置标题层级与总标题（仅记录位置/长度/格式，绝不收录文本）；
- 表格表头/表体单元格字体、加粗、对齐、底纹 fill 分布；
- media 部件清单（字节数/SHA-256）、嵌入顺序与显示尺寸；
- numPr 段落数与 numId 分布（只统计，不重建）。

输出全部为聚合格式事实，不含业务正文。
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..docx_reader import read_docx
from ..style_resolver import StyleResolver

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
V_NS = "urn:schemas-microsoft-com:vml"


def _media_facts(source, document) -> dict:
    """Read-only media inventory: per-part size/sha256, embed rId order,
    and drawing extents in document order. Aggregates only — no content text.
    """
    parts: list[dict] = []
    with zipfile.ZipFile(source, "r") as archive:
        for info in archive.infolist():
            if re.match(r"word/media/[^/]+$", info.filename):
                payload = archive.read(info.filename)
                parts.append({
                    "part": info.filename,
                    "size": info.file_size,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                })
    root = document.parts.get("word/document.xml")
    embed_order: list[str] = []
    extents: list[dict] = []
    if root is not None:
        for blip in root.iter(f"{{{A_NS}}}blip"):
            rid = blip.get(f"{{{R_NS}}}embed")
            if rid:
                embed_order.append(rid)
        for image in root.iter(f"{{{V_NS}}}imagedata"):
            rid = image.get(f"{{{R_NS}}}id")
            if rid:
                embed_order.append(rid)
        for extent in root.iter(f"{{{WP_NS}}}extent"):
            extents.append({"cx": extent.get("cx"), "cy": extent.get("cy")})
    return {"parts": parts, "embed_order": embed_order, "extents": extents}

_BUILTIN_HEADING = re.compile(r"(?:heading\s*|标题\s*)([1-3])$", re.I)
_SZ_TO_PT = 2.0


@dataclass
class VisibleFormatStats:
    sections: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    titles: list[dict] = field(default_factory=list)
    headings: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)
    media: dict = field(default_factory=dict)
    numbering: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sections": self.sections,
            "counts": self.counts,
            "body": self.body,
            "titles": self.titles,
            "headings": self.headings,
            "tables": self.tables,
            "media": self.media,
            "numbering": self.numbering,
        }


def _counter(counter: Counter, top: int | None = None) -> dict:
    items = counter.most_common(top)
    return {str(key): value for key, value in items}


def _heading_level(document, paragraph) -> str | None:
    style = document.styles.get(paragraph.style_id)
    if style is not None and style.kind == "paragraph":
        match = _BUILTIN_HEADING.match((style.name or "").strip())
        if match:
            return f"h{match.group(1)}"
    return None


def analyze_visible_format(source, *, document=None, title_pattern: str | None = None) -> VisibleFormatStats:
    """Collect aggregated visible-format facts from one DOCX.

    ``source`` is needed for media byte hashes; ``document`` may be supplied
    when the caller already parsed it. Title paragraphs are identified by
    ``title_pattern`` and reported without their text.
    """
    source = str(source)
    doc = document if document is not None else read_docx(source)
    resolver = StyleResolver(doc)
    title_regex = re.compile(title_pattern) if title_pattern else None

    # --- sections ---
    sections = []
    for index, section in enumerate(doc.sections, 1):
        size = section.get("size", {})
        sections.append({
            "index": index,
            "width_twips": size.get("w"),
            "height_twips": size.get("h"),
            "orientation_attr": size.get("orient"),
            "orientation": (
                size.get("orient")
                if size.get("orient") in ("portrait", "landscape")
                else ("landscape" if int(size.get("w") or 0) > int(size.get("h") or 0) > 0 else "portrait")
            ),
            "margins_twips": dict(section.get("margins", {})),
            "break_type": section.get("break_type"),
        })

    main = [p for p in doc.paragraphs if p.part == "word/document.xml"]
    nonempty = [p for p in main if p.text.strip()]
    counts = {
        "paragraphs_total": len(main),
        "paragraphs_nonempty": len(nonempty),
        "tables": len(doc.tables),
        "paragraphs_in_table_cells": sum(1 for p in main if p.table is not None),
        "paragraphs_with_numpr": sum(
            1 for p in main if (p.properties or {}).get("numPr")
        ),
    }

    body_font_cn, body_font_latin = Counter(), Counter()
    body_size, body_bold, body_color = Counter(), Counter(), Counter()
    body_jc, body_line, body_indent = Counter(), Counter(), Counter()
    heading_fonts, heading_sizes, heading_bold = Counter(), Counter(), Counter()
    heading_levels: Counter = Counter()
    titles: list[dict] = []

    for paragraph in main:
        if paragraph.table is not None or paragraph.in_toc or not paragraph.text.strip():
            continue
        text = paragraph.text.strip()
        if title_regex is not None and title_regex.match(text):
            effective = resolver.paragraph(paragraph)
            run_props = [resolver.run(paragraph, run) for run in paragraph.runs if run.text.strip()]
            titles.append({
                "index": paragraph.index,
                "length": len(text),
                "style_name": resolver.name(paragraph.style_id),
                "has_numpr": bool((paragraph.properties or {}).get("numPr")),
                "jc": effective.get("jc"),
                "fonts": _counter(Counter(
                    (props.get("rFonts", {}) or {}).get("eastAsia") for props in run_props
                )),
                "size_pt": _counter(Counter(
                    round(int(props["sz"]) / _SZ_TO_PT, 2) for props in run_props if props.get("sz")
                )),
                "bold": _counter(Counter(str(bool(props.get("b"))) for props in run_props)),
            })
            continue
        level = _heading_level(doc, paragraph)
        if level:
            heading_levels[level] += 1
            for run in paragraph.runs:
                if not run.text.strip():
                    continue
                props = resolver.run(paragraph, run)
                fonts = props.get("rFonts", {}) or {}
                if fonts.get("eastAsia"):
                    heading_fonts[(level, fonts["eastAsia"])] += 1
                if props.get("sz"):
                    heading_sizes[(level, round(int(props["sz"]) / _SZ_TO_PT, 2))] += 1
                heading_bold[(level, str(bool(props.get("b"))))] += 1
            continue
        # 正文（非表格、非标题、非内置 heading）。
        effective = resolver.paragraph(paragraph)
        body_jc[str(effective.get("jc", "default(left)"))] += 1
        spacing = effective.get("spacing", {}) or {}
        if spacing.get("line"):
            body_line[f"{spacing.get('line')}/{spacing.get('lineRule', 'auto')}"] += 1
        indent = effective.get("ind", {}) or {}
        if indent.get("firstLineChars"):
            body_indent[f"firstLineChars={indent['firstLineChars']}"] += 1
        for run in paragraph.runs:
            if not run.text.strip():
                continue
            props = resolver.run(paragraph, run)
            fonts = props.get("rFonts", {}) or {}
            if fonts.get("eastAsia"):
                body_font_cn[fonts["eastAsia"]] += 1
            if fonts.get("ascii"):
                body_font_latin[fonts["ascii"]] += 1
            if props.get("sz"):
                body_size[round(int(props["sz"]) / _SZ_TO_PT, 2)] += 1
            body_bold[str(bool(props.get("b")))] += 1
            color = (props.get("color") or {}).get("val")
            body_color[str(color or "default(auto)")] += 1

    # --- tables ---
    repeat_rows: dict[int, set[int]] = {}
    for table in doc.tables:
        rows = {r["index"] for r in table.rows if r["repeat_header"]}
        rows.add(1)
        repeat_rows[table.index] = rows
    header_fill, header_font, header_size, header_bold, header_jc = (
        Counter() for _ in range(5)
    )
    body_fill, body_font_c, body_size_c, body_bold_c, body_jc_c = (
        Counter() for _ in range(5)
    )
    table_shapes = []
    for table in doc.tables:
        table_shapes.append(f"{len(table.rows)}x{table.columns}")
        for paragraph in (p for p in main if p.table == table.index):
            if not paragraph.text.strip():
                continue
            is_header = paragraph.row in repeat_rows.get(table.index, {1})
            tc = paragraph.element.getparent()
            fill = None
            if tc is not None:
                shd = tc.find(
                    "w:tcPr/w:shd",
                    {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"},
                )
                if shd is not None:
                    fill = shd.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill")
            effective = resolver.paragraph(paragraph)
            jc = str(effective.get("jc", "default(left)"))
            # 底纹与对齐按单元格段落计（每段一次），字体/字号/加粗按 run 计。
            if is_header:
                header_fill[str(fill or "none")] += 1
                header_jc[jc] += 1
            else:
                body_fill[str(fill or "none")] += 1
                body_jc_c[jc] += 1
            for run in paragraph.runs:
                if not run.text.strip():
                    continue
                props = resolver.run(paragraph, run)
                fonts = props.get("rFonts", {}) or {}
                cn_font = fonts.get("eastAsia")
                size = round(int(props["sz"]) / _SZ_TO_PT, 2) if props.get("sz") else None
                bold = str(bool(props.get("b")))
                if is_header:
                    if cn_font:
                        header_font[cn_font] += 1
                    if size:
                        header_size[size] += 1
                    header_bold[bold] += 1
                else:
                    if cn_font:
                        body_font_c[cn_font] += 1
                    if size:
                        body_size_c[size] += 1
                    body_bold_c[bold] += 1

    media = _media_facts(source, doc)
    num_ids = Counter(
        str((p.properties or {}).get("numPr", {}).get("numId"))
        for p in main if (p.properties or {}).get("numPr")
    )

    def heading_block(counter: Counter) -> dict:
        grouped: dict[str, Counter] = {}
        for (level, value), count in counter.items():
            grouped.setdefault(level, Counter())[str(value)] += count
        return {level: _counter(values) for level, values in sorted(grouped.items())}

    return VisibleFormatStats(
        sections=sections,
        counts=counts,
        body={
            "eastAsia_font_runs": _counter(body_font_cn),
            "ascii_font_runs": _counter(body_font_latin),
            "size_pt_runs": _counter(body_size),
            "bold_runs": _counter(body_bold),
            "color_runs": _counter(body_color),
            "alignment_paragraphs": _counter(body_jc),
            "line_spacing_paragraphs": _counter(body_line),
            "first_line_indent_paragraphs": _counter(body_indent),
        },
        titles=titles,
        headings={
            "levels": _counter(heading_levels),
            "eastAsia_font_runs": heading_block(heading_fonts),
            "size_pt_runs": heading_block(heading_sizes),
            "bold_runs": heading_block(heading_bold),
        },
        tables={
            "shapes": table_shapes,
            "header_shading_fill_cell_runs": _counter(header_fill),
            "header_eastAsia_font_runs": _counter(header_font),
            "header_size_pt_runs": _counter(header_size),
            "header_bold_runs": _counter(header_bold),
            "header_alignment_paragraphs": _counter(header_jc),
            "body_shading_fill_cell_runs": _counter(body_fill),
            "body_eastAsia_font_runs": _counter(body_font_c),
            "body_size_pt_runs": _counter(body_size_c),
            "body_bold_runs": _counter(body_bold_c),
            "body_alignment_paragraphs": _counter(body_jc_c),
        },
        media=media,
        numbering={"numpr_paragraphs": counts["paragraphs_with_numpr"],
                   "num_ids": _counter(num_ids)},
    )
