"""Conservative formatting-role classification for production normalization.

The normalizer only mutates formatting; it never reclassifies semantics. This
module therefore errs on the side of *exclusion*: a paragraph becomes a
formatting target only when every available structural signal agrees.

Roles (main document part only):

- ``heading``            built-in non-custom Heading 1/2/3 paragraph
- ``body_named``         paragraph explicitly using the spec's 正文 style
- ``body_safe_normal``   high-confidence body text still carrying pStyle Normal
                         (direct formatting only; pStyle is never rewritten)
- ``caption``            题注/Caption styled or figure/table caption pattern
- ``table_header``       first/repeated header row of a regular content table
- ``table_body``         non-header row of a regular content table
- ``table_named``        cell paragraph already using a named 表格* paragraph style
- ``other``              everything else (never normalized)

Tables are independently classified as ``regular`` / ``cover`` / ``layout`` /
``complex`` / ``ambiguous``; only ``regular`` tables receive direct formatting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .docx_reader import NS

NORMAL_STYLE_NAMES = {"normal", "常规"}
FRONT_MATTER_HEADING_NAMES = {"编制说明", "目录"}

# Skip-reason codes surfaced as unresolved items in the validation report.
SKIP_TABLE_COVER = "SKIP_TABLE_COVER"
SKIP_TABLE_LAYOUT = "SKIP_TABLE_LAYOUT"
SKIP_TABLE_COMPLEX = "SKIP_TABLE_COMPLEX"
SKIP_TABLE_AMBIGUOUS = "SKIP_TABLE_AMBIGUOUS"


@dataclass(frozen=True)
class ParagraphRole:
    role: str = "other"
    level: int | None = None
    table_index: int | None = None
    row_kind: str | None = None  # "header" / "body"


@dataclass
class TableClassification:
    kind: str
    table_index: int
    reason: str = ""
    reason_code: str = ""


@dataclass
class Classification:
    paragraph_roles: dict = field(default_factory=dict)
    table_classifications: dict = field(default_factory=dict)
    warnings: list[dict] = field(default_factory=list)
    first_heading1_index: int | None = None

    def role(self, paragraph) -> ParagraphRole:
        return self.paragraph_roles.get((paragraph.part, paragraph.index), ParagraphRole())


def _contains(paragraph, *names):
    for name in names:
        if paragraph.element.find(f".//w:{name}", NS) is not None:
            return True
    return False


def _all_runs_bold(resolver, paragraph):
    runs = [run for run in paragraph.runs if run.text.strip()]
    return bool(runs) and all(resolver.run(paragraph, run).get("b") for run in runs)


def _compile_caption_patterns(rules):
    caption_rules = rules.get("caption") or {}
    patterns = []
    for pattern in caption_rules.get("patterns", []):
        try:
            patterns.append(re.compile(pattern))
        except re.error:
            continue
    return patterns


def _classify_tables(document, resolver, rules, main_paragraphs, warnings):
    """Return {table_index: TableClassification} for main-part tables."""
    config = rules["tables"]
    cover_pattern = config.get("cover_style_pattern", r"(?!)")
    root = document.parts["word/document.xml"]
    tbl_elements = root.findall(".//w:tbl", NS)
    main_tables = [table for table in document.tables if table.part == "word/document.xml"]
    result = {}
    for table, element in zip(main_tables, tbl_elements):
        location = f"word/document.xml / Table {table.index}"
        nested_parent = element.findall(".//w:tbl", NS)
        is_nested = next(element.iterancestors(f"{{{NS['w']}}}tbl"), None) is not None
        if is_nested:
            kind, reason = SKIP_TABLE_LAYOUT, "嵌套表格，无法确定行列语义"
        elif nested_parent:
            kind, reason = SKIP_TABLE_LAYOUT, "表格包含嵌套子表，按布局表处理"
        elif element.find(".//w:vMerge", NS) is not None:
            kind, reason = SKIP_TABLE_COMPLEX, "表格包含纵向合并单元格(vMerge)，表头/数据行角色不能确定"
        else:
            cell_paragraphs = [
                p for p in main_paragraphs
                if p.table == table.index and p.text.strip()
            ]
            cover_candidate = bool(cell_paragraphs) and all(
                re.match(cover_pattern, resolver.name(p.style_id), re.I)
                for p in cell_paragraphs
            )
            if cover_candidate:
                kind, reason = SKIP_TABLE_COVER, "封面/信息登记表：全部单元格使用封面样式族"
            elif len(table.rows) < 2:
                kind, reason = SKIP_TABLE_AMBIGUOUS, "表格不足两行，无法区分表头与数据行"
            else:
                kind, reason = "regular", ""
        if kind != "regular":
            warnings.append({"kind": kind, "location": location, "reason": reason})
        result[table.index] = TableClassification(
            "regular" if kind == "regular" else "skipped", table.index, reason, kind
        )
    return result


def classify(document, resolver, rules):
    """Classify every main-part paragraph and table under conservative rules."""
    classification = Classification()
    warnings = classification.warnings
    main_paragraphs = [
        paragraph for paragraph in document.paragraphs
        if paragraph.part == "word/document.xml"
    ]

    # 1. First real Heading 1 boundary (excludes 编制说明 / 目录 per FRONT rules).
    first_h1 = None
    for paragraph in main_paragraphs:
        if paragraph.table is not None or paragraph.in_toc:
            continue
        level = resolver.heading_level(paragraph)
        cleaned = paragraph.text.strip().replace(" ", "").replace("　", "")
        if level == 1 and cleaned not in FRONT_MATTER_HEADING_NAMES:
            first_h1 = paragraph.index
            break
    classification.first_heading1_index = first_h1

    # 2. Tables.
    table_info = _classify_tables(document, resolver, rules, main_paragraphs, warnings)

    caption_cfg = rules.get("caption") or {}
    aliases = {
        str(name).casefold() for name in caption_cfg.get("style_aliases", [])
    }
    patterns = _compile_caption_patterns(rules)
    body_style_name = rules["body"]["style_name"]
    safe_normal_enabled = bool(rules["body"].get("safe_normal_normalization"))
    regular_table_enabled = bool(rules["tables"].get("regular_table_normalization"))
    named_table_styles = set(
        rules["tables"]["required_styles"] + rules["tables"]["optional_styles"]
    )

    def is_caption(paragraph):
        if not caption_cfg:
            return False
        if resolver.name(paragraph.style_id).casefold() in aliases:
            return True
        text = paragraph.text.strip()
        return bool(text) and any(pattern.search(text) for pattern in patterns)

    # 3. Paragraphs.
    for paragraph in main_paragraphs:
        key = (paragraph.part, paragraph.index)
        name = resolver.name(paragraph.style_id)
        style = document.styles.get(paragraph.style_id)
        level = resolver.heading_level(paragraph)

        if paragraph.in_toc:
            continue
        if level and paragraph.table is None:
            classification.paragraph_roles[key] = ParagraphRole("heading", level=level)
            continue
        if is_caption(paragraph) and paragraph.table is None:
            classification.paragraph_roles[key] = ParagraphRole("caption")
            continue
        if name == body_style_name and paragraph.table is None:
            classification.paragraph_roles[key] = ParagraphRole("body_named")
            continue

        if paragraph.table is not None:
            if name in named_table_styles:
                classification.paragraph_roles[key] = ParagraphRole(
                    "table_named", table_index=paragraph.table
                )
                continue
            if regular_table_enabled:
                info = table_info.get(paragraph.table)
                if info is not None and info.kind == "regular":
                    row = next(
                        (row for row in document.tables[paragraph.table - 1].rows
                         if row["index"] == paragraph.row),
                        None,
                    )
                    is_header = (
                        row is not None
                        and (row["repeat_header"]
                             or (rules["tables"]["header_strategy"] == "first_row_or_repeat"
                                 and paragraph.row == 1))
                    )
                    if is_caption(paragraph):
                        classification.paragraph_roles[key] = ParagraphRole("caption")
                    else:
                        classification.paragraph_roles[key] = ParagraphRole(
                            "table_header" if is_header else "table_body",
                            table_index=paragraph.table,
                            row_kind="header" if is_header else "body",
                        )
            continue

        # Main-body Normal paragraphs: only with high-confidence body signals.
        if safe_normal_enabled and _is_safe_normal_body(
            document, resolver, paragraph, name, style, first_h1, is_caption
        ):
            classification.paragraph_roles[key] = ParagraphRole("body_safe_normal")

    classification.table_classifications = table_info
    return classification


def _is_safe_normal_body(document, resolver, paragraph, name, style, first_h1, is_caption):
    if is_caption(paragraph):
        return False
    if style is None or style.custom or name.casefold() not in NORMAL_STYLE_NAMES:
        return False
    if first_h1 is None or paragraph.index <= first_h1:
        return False
    if not paragraph.text.strip():
        return False
    # Drawing / embedded-object paragraphs (images, OLE, shapes) are not body text.
    if _contains(paragraph, "drawing", "pict", "object"):
        return False
    # Any field involvement (PAGE/REF/TOC results etc.) stays out of scope.
    if _contains(paragraph, "fldSimple", "fldChar", "instrText"):
        return False
    effective = resolver.paragraph(paragraph)
    # Numbered list items belong to numbering policy; centered/right short lines
    # are titles, captions or signature lines, not justified body text.
    if "numPr" in paragraph.properties or effective.get("outlineLvl") in ("0", "1", "2"):
        return False
    if effective.get("jc") in ("center", "right"):
        return False
    # Short, fully-bold Normal lines are almost certainly simulated headings.
    if len(paragraph.text.strip()) <= 40 and _all_runs_bold(resolver, paragraph):
        return False
    return True
