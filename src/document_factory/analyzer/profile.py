"""DocumentProfile: read-only structural profile of an input DOCX.

The profile answers "转换前这份文档是什么状态": paragraph/table counts,
heading structure (paragraphs actually using built-in Heading styles),
effective font usage of text runs, section/page info and paragraph-style
usage. Effective values (not raw XML) are counted via ``StyleResolver`` so
theme fonts and style inheritance are resolved the same way lint sees them.

The analyzer is deliberately descriptive and rule-agnostic: it does not know
about templates and never decides what *should* change. The conversion layer
owns prescriptive decisions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ..docx_reader import read_docx
from ..style_resolver import StyleResolver


@dataclass
class DocumentProfile:
    """Structural facts of one DOCX, captured before conversion."""

    source_path: str
    source_sha256: str
    paragraph_count: int
    nonempty_paragraph_count: int
    table_count: int
    section_info: list[dict[str, Any]] = field(default_factory=list)
    #: 段落样式名 -> 使用段落数（仅 word/document.xml）
    style_usage: dict[str, int] = field(default_factory=dict)
    #: 内置 Heading 样式使用数：{"h1": n, "h2": n, "h3": n}
    heading_structure: dict[str, int] = field(default_factory=dict)
    #: 有效字体使用数：{"仿宋/12pt": n, ...}（非空文本 run，按脚本归并中文字体）
    font_usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _twips_to_cm(value: str | None) -> float | None:
    if value is None:
        return None
    return round(int(value) * 2.54 / 1440, 2)


def analyze_document(source) -> DocumentProfile:
    """Read ``source`` (path or Document) and build its DocumentProfile.

    No mutation, no lint rules: pure observation of structural facts.
    """
    if isinstance(source, (str, Path)):
        document = read_docx(source)
        source_path = str(Path(source).resolve())
    else:
        document = source
        source_path = str(document.path)

    main = [p for p in document.paragraphs if p.part == "word/document.xml"]
    resolver = StyleResolver(document)

    style_counter: Counter[str] = Counter()
    heading_counter: Counter[str] = Counter()
    font_counter: Counter[str] = Counter()

    for paragraph in main:
        style_counter[resolver.name(paragraph.style_id)] += 1
        level = resolver.heading_level(paragraph)
        if level:
            heading_counter[f"h{level}"] += 1
        for run in paragraph.runs:
            if not run.text.strip():
                continue
            effective = resolver.run(paragraph, run)
            size = effective.get("sz")
            size_pt = f"{int(size) / 2:g}pt" if size is not None else "字号未知"
            # 含中文的 run 计 eastAsia，否则计 ascii；同一 run 的中英混排归中文字体。
            if any("\u3400" <= ch <= "\u9fff" or "\U00020000" <= ch <= "\U0002fa1f" for ch in run.text):
                font, _ = resolver.font(effective, "cn")
            else:
                font, _ = resolver.font(effective, "ascii")
            font_counter[f"{font or '字体未知'}/{size_pt}"] += 1

    section_info = []
    for section in document.sections:
        size = section.get("size", {}) or {}
        margins = section.get("margins", {}) or {}
        section_info.append({
            "index": section["index"],
            "page_width_cm": _twips_to_cm(size.get("w")),
            "page_height_cm": _twips_to_cm(size.get("h")),
            "margins_cm": {
                "top": _twips_to_cm(margins.get("top")),
                "bottom": _twips_to_cm(margins.get("bottom")),
                "left": _twips_to_cm(margins.get("left")),
                "right": _twips_to_cm(margins.get("right")),
            },
        })

    return DocumentProfile(
        source_path=source_path,
        source_sha256=document.sha256,
        paragraph_count=len(main),
        nonempty_paragraph_count=sum(1 for p in main if p.text.strip()),
        table_count=len(document.tables),
        section_info=section_info,
        style_usage=dict(style_counter.most_common()),
        heading_structure={f"h{i}": heading_counter.get(f"h{i}", 0) for i in range(1, 4)},
        font_usage=dict(font_counter.most_common()),
    )
