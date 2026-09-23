"""Deterministic paragraph role classification for format conversion.

TASK_DOC_013 的关键边界：转换**不重新生成内容、不做 AI 语义理解**。
分类器只用可复现的确定性规则判定段落角色：

- 标题：手工编号模式（一、/（一）/1.1 等）+ 短文本 + 无句末标点；
  或已经是内置 Heading 样式；
- 表格：表格单元格段落，首行/重复表头行为表头，其余为表格正文；
- 封面：第一个标题之前的段落（封面/前置区域），保留原格式交人工复核；
- 正文：其余非空段落；
- 空段：跳过。

日期年份（如 "2026年9月"）、目录点状导引线等被显式排除，避免误判。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: 一、二、… 十、百（h1）
_CN_LEVEL1 = re.compile(r"^\s*([一二三四五六七八九十百]+)\s*[、.．]\s*\S")
#: （一）(二) …（h2）
_CN_LEVEL2 = re.compile(r"^\s*[（(]\s*[一二三四五六七八九十百]+\s*[）)]\s*\S")
#: 1.1 / 1.1.1 后接空白或分隔符（h2/h3）
_NUM_MULTI = re.compile(r"^\s*(\d+(?:\.\d+){1,2})(?:\s+|[、.．)）])\s*\S")
#: 1 / 1) / 1、/ 1． 后接空白或分隔符（h1）；紧贴汉字的纯数字不算（年份/日期）
_NUM_LEVEL1 = re.compile(r"^\s*(\d+)(?:\s+|[、．)）])\s*\S")
#: 加粗且紧贴汉字的编号（如 "1研究目标"），仅在 run 全部加粗时采信
_NUM_BOLD = re.compile(r"^\s*(\d+(?:\.\d+){0,2})(?=[\u4e00-\u9fff])")
#: 目录点状导引线：标题........12
_TOC_DOTS = re.compile(r"(?:\.{3,}|…{2,}|\t)\s*\d+\s*$")
#: 编号后紧跟年月日（年份/日期误判保护）
_DATE_TAIL = re.compile(r"^\s*\d+(?:\.\d+){0,2}\s*[年月日]")

MAX_HEADING_LEN = 50
_SENTENCE_END = tuple("。！？；：!?;:")


@dataclass(frozen=True)
class RoleAssignment:
    """One paragraph's deterministic conversion role."""

    index: int
    location: str
    role: str
    #: 转换目标样式名；cover/blank 为 None（保持原样）
    target_style_name: str | None
    reason: str


def _heading_level(paragraph) -> tuple[str, str] | None:
    """Return (role, reason) if the paragraph is a deterministic heading."""
    text = paragraph.text.strip()
    if not text or len(text) > MAX_HEADING_LEN:
        return None
    if text.endswith(_SENTENCE_END):
        return None
    if _TOC_DOTS.search(text):
        return None
    # 已是内置 Heading 样式：无需再识别，交由样式层处理。
    # 数字模式优先做日期排除。
    if _CN_LEVEL1.match(text):
        return "heading1", "cn_circle_number"
    if _CN_LEVEL2.match(text):
        return "heading2", "cn_paren_number"
    multi = _NUM_MULTI.match(text)
    if multi and not _DATE_TAIL.match(text):
        level = min(3, multi.group(1).count(".") + 1)
        return f"heading{level}", "numeric_dotted"
    if _NUM_LEVEL1.match(text) and not _DATE_TAIL.match(text):
        return "heading1", "numeric_single"
    # 紧贴汉字的编号仅在整段加粗时采信。
    if _NUM_BOLD.match(text) and not _DATE_TAIL.match(text):
        runs = [r for r in paragraph.runs if r.text.strip()]
        if runs and all((r.properties or {}).get("b") for r in runs):
            prefix = _NUM_BOLD.match(text).group(1)
            level = min(3, prefix.count(".") + 1)
            return f"heading{level}", "bold_numbered"
    return None


def classify_paragraphs(document) -> list[RoleAssignment]:
    """Assign a conversion role to every word/document.xml paragraph.

    Table rows flagged as repeat headers, plus each table's first row, are
    treated as table headers. Cover paragraphs precede the first detected
    heading and are left untouched.
    """
    main = [p for p in document.paragraphs if p.part == "word/document.xml"]

    # 表格重复表头行映射。
    repeat_rows: dict[int, set[int]] = {}
    for table in document.tables:
        flagged = {r["index"] for r in table.rows if r["repeat_header"]}
        flagged.add(1)
        repeat_rows[table.index] = flagged

    # 第一遍：发现标题候选（不含表格），确定封面边界。
    detected: dict[int, tuple[str, str]] = {}
    first_heading_index: int | None = None
    for paragraph in main:
        if paragraph.table is not None or paragraph.in_toc:
            continue
        match = _heading_level(paragraph)
        if match is not None:
            detected[paragraph.index] = match
            if first_heading_index is None or paragraph.index < first_heading_index:
                first_heading_index = paragraph.index

    assignments: list[RoleAssignment] = []
    for paragraph in main:
        # 表格单元格。
        if paragraph.table is not None:
            is_header = paragraph.row in repeat_rows.get(paragraph.table, {1})
            role = "table_header" if is_header else "table_body"
            assignments.append(RoleAssignment(
                paragraph.index, paragraph.location, role,
                "表格表头" if is_header else "表格正文",
                "table_first_or_repeat_row" if is_header else "table_cell",
            ))
            continue
        if not paragraph.text.strip():
            assignments.append(RoleAssignment(
                paragraph.index, paragraph.location, "blank", None, "empty_paragraph",
            ))
            continue
        # 手工编号识别的标题。
        if paragraph.index in detected:
            role, reason = detected[paragraph.index]
            target = f"heading {role[-1]}"
            assignments.append(RoleAssignment(
                paragraph.index, paragraph.location, role, target, reason,
            ))
            continue
        # 第一个标题之前：封面/前置区域，保留原样。
        if first_heading_index is not None and paragraph.index < first_heading_index:
            assignments.append(RoleAssignment(
                paragraph.index, paragraph.location, "cover", None,
                "before_first_heading",
            ))
            continue
        # 其余非空段落一律视为正文。
        assignments.append(RoleAssignment(
            paragraph.index, paragraph.location, "body", "正文", "non_heading_text",
        ))
    return assignments
