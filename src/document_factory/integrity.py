"""Content Integrity Gate for DOCX normalization.

Runs after the output package has been written and compares it against the
source package independently of whole-file hashes (formatting changes are
supposed to change XML bytes). Any drift in visible text, field instructions,
table structure, section/table/drawing counts, relationships or media bytes is
a hard failure and aborts normalization.
"""
from __future__ import annotations

import hashlib
import re
import zipfile

from .docx_reader import NS, read_docx
from .models import DocumentFactoryError

_MEDIA_RE = re.compile(r"word/media/[^/]+$")
_HEADER_FOOTER_RE = re.compile(r"word/(?:header|footer)[^/]*\.xml$")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _paragraph_text_map(document):
    return [
        (paragraph.part, paragraph.index, paragraph.text)
        for paragraph in document.paragraphs
    ]


def _run_text_map(document):
    return [
        (paragraph.part, paragraph.index, index, run.text)
        for paragraph in document.paragraphs
        for index, run in enumerate(paragraph.runs)
    ]


def _table_structure(document):
    structure = []
    for table in document.tables:
        rows = []
        for row in table.rows:
            rows.append([
                {
                    "index": cell["index"],
                    "grid_span": cell["grid_span"],
                    "v_merge": cell["v_merge"],
                    "paragraphs": list(cell["paragraphs"]),
                }
                for cell in row["cells"]
            ])
        structure.append((table.part, table.index, table.columns, rows))
    return structure


def _table_cell_texts(document):
    texts = []
    paragraph_lookup = {
        (paragraph.part, paragraph.index): paragraph
        for paragraph in document.paragraphs
    }
    for table in document.tables:
        for row in table.rows:
            for cell in row["cells"]:
                joined = "".join(
                    paragraph_lookup[(table.part, pi)].text
                    for pi in cell["paragraphs"]
                    if (table.part, pi) in paragraph_lookup
                )
                texts.append((table.part, table.index, row["index"], cell["index"], joined))
    return texts


def _fields(document):
    return sorted(
        (field.part, field.paragraph_index, field.instruction, field.complete)
        for field in document.fields
    )


def _hyperlink_texts(parts):
    result = []
    for name, root in parts.items():
        links = root.findall(".//w:hyperlink", NS)
        for index, link in enumerate(links):
            text = "".join(node.text or "" for node in link.findall(".//w:t", NS))
            result.append((name, index, text))
    return sorted(result)


def _drawing_counts(parts):
    counts = {}
    for name, root in parts.items():
        counts[name] = {
            "drawing": len(root.findall(".//w:drawing", NS)),
            "pict": len(root.findall(".//w:pict", NS)),
        }
    return {name: value for name, value in counts.items()
            if value["drawing"] or value["pict"]}


def _header_footer_text(document):
    return [
        (paragraph.part, paragraph.index, paragraph.text)
        for paragraph in document.paragraphs
        if _HEADER_FOOTER_RE.match(paragraph.part)
    ]


def _media_hashes(archive):
    return {
        name: _sha256_bytes(archive.read(name))
        for name in archive.namelist()
        if _MEDIA_RE.match(name)
    }


def verify_content_integrity(source_path, output_path, changed_parts):
    """Compare output vs source; raise DocumentFactoryError on any content drift."""
    violations = []
    changed_parts = set(changed_parts)

    with zipfile.ZipFile(source_path) as before_zip, zipfile.ZipFile(output_path) as after_zip:
        before_names = before_zip.namelist()
        after_names = after_zip.namelist()
        if before_names != after_names:
            missing = sorted(set(before_names) - set(after_names))
            added = sorted(set(after_names) - set(before_names))
            if missing:
                violations.append(f"ZIP 部件丢失：{missing}")
            if added:
                violations.append(f"新增未知 ZIP 部件：{added}")
        before_media = _media_hashes(before_zip)
        after_media = _media_hashes(after_zip)
        changed_zip_parts = []
        for name in before_names:
            if name not in after_names:
                continue
            before_bytes = before_zip.read(name)
            after_bytes = after_zip.read(name)
            if before_bytes != after_bytes:
                changed_zip_parts.append(name)
                if name not in changed_parts:
                    violations.append(f"未登记的部件被修改：{name}")
                continue
            if name in changed_parts:
                # Declared changed but byte-identical: tolerated, not a violation.
                pass
        after_media = _media_hashes(after_zip)
    unexpected_changes = sorted(set(changed_zip_parts) - {"word/document.xml", "word/styles.xml"})
    if unexpected_changes:
        violations.append(f"格式规范化只允许修改 document/styles 部件，实际改动：{unexpected_changes}")
    if before_media != after_media:
        violations.append(
            f"媒体文件发生变化：before={sorted(before_media)} after={sorted(after_media)}"
        )

    before_doc = read_docx(source_path)
    after_doc = read_docx(output_path)

    before_texts = _paragraph_text_map(before_doc)
    after_texts = _paragraph_text_map(after_doc)
    if before_texts != after_texts:
        violations.append("可见段落文本序列（含题注/标题/页眉页脚）不一致")
    if _run_text_map(before_doc) != _run_text_map(after_doc):
        violations.append("Run 级文本切分或内容不一致")
    if _table_cell_texts(before_doc) != _table_cell_texts(after_doc):
        violations.append("表格单元格文本不一致")
    if _table_structure(before_doc) != _table_structure(after_doc):
        violations.append("表格结构（行数/单元格/gridSpan/vMerge）不一致")
    if len(before_doc.paragraphs) != len(after_doc.paragraphs):
        violations.append(
            f"段落数量不一致：{len(before_doc.paragraphs)} → {len(after_doc.paragraphs)}"
        )
    if len(before_doc.tables) != len(after_doc.tables):
        violations.append(
            f"表格数量不一致：{len(before_doc.tables)} → {len(after_doc.tables)}"
        )
    if len(before_doc.sections) != len(after_doc.sections):
        violations.append(
            f"节数量不一致：{len(before_doc.sections)} → {len(after_doc.sections)}"
        )
    if _fields(before_doc) != _fields(after_doc):
        violations.append("域指令（instrText / fldSimple）不一致")
    if _hyperlink_texts(before_doc.parts) != _hyperlink_texts(after_doc.parts):
        violations.append("超链接显示文本不一致")
    if _header_footer_text(before_doc) != _header_footer_text(after_doc):
        violations.append("页眉页脚文本不一致")
    if _drawing_counts(before_doc.parts) != _drawing_counts(after_doc.parts):
        violations.append("绘图对象（w:drawing/w:pict）数量不一致")
    if before_doc.relationships != after_doc.relationships:
        violations.append("关系部件（*.rels）内容不一致")

    if violations:
        raise DocumentFactoryError(
            "CONTENT_INTEGRITY_GATE 失败，已阻止交付：" + "；".join(violations)
        )

    return {
        "status": "PASS",
        "paragraph_count_before": len(before_doc.paragraphs),
        "paragraph_count_after": len(after_doc.paragraphs),
        "table_count_before": len(before_doc.tables),
        "table_count_after": len(after_doc.tables),
        "section_count_before": len(before_doc.sections),
        "section_count_after": len(after_doc.sections),
        "drawing_count_before": sum(v["drawing"] for v in _drawing_counts(before_doc.parts).values()),
        "drawing_count_after": sum(v["drawing"] for v in _drawing_counts(after_doc.parts).values()),
        "visible_text_equal": True,
        "run_text_equal": True,
        "table_cell_text_equal": True,
        "table_structure_equal": True,
        "field_instructions_equal": True,
        "hyperlink_text_equal": True,
        "header_footer_text_equal": True,
        "relationships_equal": True,
        "media_file_count": len(after_media),
        "media_sha256_equal": True,
        "changed_zip_parts": sorted(changed_zip_parts),
    }
