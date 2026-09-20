"""Apply a Template Profile through the existing normalization write primitives."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from ..docx_reader import NS, read_docx, sha256
from ..lint_engine import lint
from ..models import DocumentFactoryError, TemplateApplyResult
from ..normalizer import (
    _atomic_text,
    _style_element,
    _write_package,
    apply_format_profile,
)
from ..output_paths import checked_output
from ..style_resolver import StyleResolver
from .analyzer import analyze_template
from .extractor import extract_roles, extract_style, paragraph_format


TEMPLATE_RULES = {"rules": {"TEMPLATE": {"source": "Template Profile 1.0"}}}
SUPPORTED_ROLES = ("Normal", "Title", "Heading1", "Heading2", "Heading3")


def _apply_format(
    parent, profile, changes, *, object_type, location, prefix="", table_basic=False,
    include_paragraph=True, include_run=True,
):
    return apply_format_profile(
        parent, profile, changes, object_type=object_type, location=location,
        rules=TEMPLATE_RULES, rule_id="TEMPLATE", prefix=prefix, table_basic=table_basic,
        include_paragraph=include_paragraph, include_run=include_run,
    )


def _apply_profile(document, profile):
    changes: list[dict[str, Any]] = []
    changed_parts: set[str] = set()
    mappings: list[dict[str, Any]] = []
    target_roles = extract_roles(document)

    for role in SUPPORTED_ROLES:
        template_style_id = profile.roles.get(role)
        target_style_id = target_roles.get(role)
        if template_style_id is None or target_style_id is None or template_style_id not in profile.styles:
            continue
        style_profile = profile.styles[template_style_id]
        element = _style_element(document, target_style_id)
        if element is None:
            continue
        location = f"Style {document.styles[target_style_id].name}"
        changed = _apply_format(element, style_profile, changes, object_type="Style", location=location)
        if changed:
            changed_parts.add("word/styles.xml")
        mappings.append({
            "role": role,
            "template_style_id": template_style_id,
            "target_style_id": target_style_id,
        })

    mapped_target_ids = {item["target_style_id"]: item["role"] for item in mappings}
    for paragraph in document.paragraphs:
        if paragraph.part != "word/document.xml" or paragraph.in_toc:
            continue
        role = mapped_target_ids.get(paragraph.style_id)
        if role is not None:
            style_profile = profile.styles[profile.roles[role]]
            direct_changed = False
            if any(key in paragraph.properties for key in ("jc", "spacing", "ind")):
                direct_changed |= _apply_format(
                    paragraph.element, style_profile, changes,
                    object_type="Paragraph", location=paragraph.location, include_run=False,
                )
            for index, run in enumerate(paragraph.runs, 1):
                if not run.text.strip() or not any(key in run.properties for key in ("rFonts", "sz", "b", "i", "color")):
                    continue
                direct_changed |= _apply_format(
                    run.element, style_profile, changes,
                    object_type="Run", location=f"{paragraph.location} / Run {index}",
                    table_basic=True, include_paragraph=False,
                )
            if direct_changed:
                changed_parts.add("word/document.xml")

        if paragraph.table is None or not paragraph.text.strip():
            continue
        table_role = "header" if paragraph.row == 1 else "body"
        table_profile = profile.table_defaults.get(table_role)
        if table_profile is None:
            continue
        table_changed = _apply_format(
            paragraph.element, table_profile, changes,
            object_type="Paragraph", location=paragraph.location, prefix=f"table_{table_role}_", table_basic=True,
            include_run=False,
        )
        for index, run in enumerate(paragraph.runs, 1):
            if run.text.strip():
                table_changed |= _apply_format(
                    run.element, table_profile, changes,
                    object_type="Run", location=f"{paragraph.location} / Run {index}", prefix=f"table_{table_role}_",
                    table_basic=True, include_paragraph=False,
                )
        if table_changed:
            changed_parts.add("word/document.xml")
    return changes, changed_parts, mappings


def _compare(expected, actual, location, mismatches, keys, section):
    for key in keys:
        wanted = expected.get(section, {}).get(key)
        if wanted is None:
            continue
        observed = actual.get(section, {}).get(key)
        if observed != wanted:
            mismatches.append({"location": location, "property": f"{section}.{key}", "expected": wanted, "actual": observed})


def _validate_profile(document, profile, mappings):
    resolver = StyleResolver(document)
    mismatches: list[dict[str, Any]] = []
    for mapping in mappings:
        expected = profile.styles[mapping["template_style_id"]]
        actual = extract_style(document, resolver, mapping["target_style_id"])
        location = f"Style {document.styles[mapping['target_style_id']].name}"
        _compare(expected, actual, location, mismatches, ("east_asia", "latin", "size_pt", "bold", "italic", "color"), "font")
        _compare(expected, actual, location, mismatches, ("alignment",), "paragraph")
        for group in ("spacing", "indent"):
            for key, wanted in expected.get("paragraph", {}).get(group, {}).items():
                if wanted is not None and actual.get("paragraph", {}).get(group, {}).get(key) != wanted:
                    mismatches.append({
                        "location": location,
                        "property": f"paragraph.{group}.{key}",
                        "expected": wanted,
                        "actual": actual.get("paragraph", {}).get(group, {}).get(key),
                    })
    for paragraph in document.paragraphs:
        if paragraph.part != "word/document.xml" or paragraph.table is None or not paragraph.text.strip():
            continue
        role = "header" if paragraph.row == 1 else "body"
        expected = profile.table_defaults.get(role)
        if expected is None:
            continue
        actual = paragraph_format(document, resolver, paragraph)
        _compare(expected, actual, paragraph.location, mismatches, ("east_asia", "latin", "size_pt"), "font")
        _compare(expected, actual, paragraph.location, mismatches, ("alignment",), "paragraph")
    return mismatches


def _escape(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _write_report(result, profile, before_lint, after_lint, generated):
    lines = [
        "# DocumentFactory Template Apply Report", "",
        "## 1. 基本信息", "",
        f"- 实际生成时间（含时区）：{generated}",
        f"- 模板：{result.template_path}",
        f"- 目标输入：{result.input_path}",
        f"- 输出：{result.output_path}",
        f"- Template Profile schema：{profile.schema_version}",
        f"- 模板 SHA-256：{result.template_sha256}",
        f"- 输入 SHA-256：{result.input_sha256}",
        f"- 输出 SHA-256：{result.output_sha256}",
        f"- 模板未变化：{result.template_unchanged}",
        f"- 输入未变化：{result.source_unchanged}", "",
        "## 2. 迁移结果", "", f"**RESULT: {result.status}**", "",
        f"- Style 映射：{len(result.mappings)}",
        f"- 属性修改记录：{len(result.changes)}",
        f"- Profile 验证不一致：{len(result.validation_mismatches)}", "",
        "## 3. Style 映射", "", "| Role | Template style | Target style |", "|---|---|---|",
    ]
    for mapping in result.mappings:
        lines.append(f"| {mapping['role']} | {mapping['template_style_id']} | {mapping['target_style_id']} |")
    if not result.mappings:
        lines.append("| - | - | - |")
    lines += ["", "## 4. 修改明细", "", "| 对象 | 位置 | 属性 | 修改前 | 修改后 |", "|---|---|---|---|---|"]
    for change in result.changes:
        lines.append("| " + " | ".join(_escape(change[key]) for key in ("object_type", "location", "property", "before", "after")) + " |")
    if not result.changes:
        lines.append("| - | - | - | 无需修改 | 无需修改 |")
    lines += ["", "## 5. Profile 验证", "", "| 位置 | 属性 | 预期 | 实际 |", "|---|---|---|---|"]
    for mismatch in result.validation_mismatches:
        lines.append("| " + " | ".join(_escape(mismatch[key]) for key in ("location", "property", "expected", "actual")) + " |")
    if not result.validation_mismatches:
        lines.append("| - | - | 全部已应用 | 全部已应用 |")
    lines += [
        "", "## 6. 现有 lint 回归", "",
        "Template Apply 不改变既有规则 severity，也不以电网规则代替模板 Profile；以下计数仅证明现有 lint 可对输出继续执行。", "",
        "| 阶段 | RESULT | ERROR | WARNING | INFO |", "|---|---|---:|---:|---:|",
        f"| 应用前 | {before_lint.result} | {before_lint.counts['ERROR']} | {before_lint.counts['WARNING']} | {before_lint.counts['INFO']} |",
        f"| 应用后 | {after_lint.result} | {after_lint.counts['ERROR']} | {after_lint.counts['WARNING']} | {after_lint.counts['INFO']} |", "",
        "## 7. 本版边界", "",
        "- 只映射目标文档中已经存在并明确标记的 Normal、Title、Heading 1/2/3 样式。",
        "- 表格只应用首行/表体的字体、字号和对齐；不迁移复杂条件表格样式。",
        "- 页面、页眉、页脚和编号仅分析，不在本版迁移。",
        "- 不修改文本、段落数量、章节顺序、图片布局、TOC 或复杂编号。", "",
    ]
    _atomic_text(Path(result.report_path), "\n".join(lines))


def apply_template(template_path, input_path, output_path=None, report_path=None, rules_path=None):
    """Apply deterministic profile facts from a template to an existing DOCX."""
    root = Path.cwd().resolve()
    template = Path(template_path).resolve()
    source = Path(input_path).resolve()
    if template.suffix.lower() != ".docx" or source.suffix.lower() != ".docx":
        raise DocumentFactoryError("Template Apply 的模板和输入都必须是 DOCX 文件")
    output = checked_output(
        output_path or Path("output/template") / f"{source.stem}_formatted.docx", root, "output", source,
    )
    report = checked_output(
        report_path or Path("reports") / f"{source.stem}_TEMPLATE_REPORT.md", root, "reports", source,
    )
    if output == template:
        raise DocumentFactoryError("Template Apply 输出不得覆盖模板文件")
    if output.suffix.lower() != ".docx":
        raise DocumentFactoryError("Template Apply 输出必须使用 .docx 扩展名")
    if report.suffix.lower() != ".md":
        raise DocumentFactoryError("Template Apply 报告必须使用 .md 扩展名")

    profile = analyze_template(template)
    template_hash = profile.source_sha256
    before_lint = lint(source, rules_path or root / "rules/grid_tech_v1_4.yaml")
    input_hash = before_lint.document.sha256
    changes, changed_parts, mappings = _apply_profile(before_lint.document, profile)
    if sha256(source) != input_hash or sha256(template) != template_hash:
        raise DocumentFactoryError("INPUT_CHANGED：Template Apply 期间模板或输入文件发生变化")
    _write_package(source, output, before_lint.document, changed_parts)
    if sha256(source) != input_hash or sha256(template) != template_hash:
        raise DocumentFactoryError("INPUT_CHANGED：Template Apply 期间模板或输入文件发生变化")
    output_document = read_docx(output)
    after_lint = lint(output, rules_path or root / "rules/grid_tech_v1_4.yaml")
    mismatches = _validate_profile(output_document, profile, mappings)
    result = TemplateApplyResult(
        status="PASS" if not mismatches else "FAIL",
        template_path=str(template),
        input_path=str(source),
        output_path=str(output),
        report_path=str(report),
        template_sha256=template_hash,
        input_sha256=input_hash,
        output_sha256=output_document.sha256,
        mappings=mappings,
        changes=changes,
        validation_mismatches=mismatches,
        before_lint_counts=before_lint.counts,
        after_lint_counts=after_lint.counts,
        template_unchanged=sha256(template) == template_hash,
        source_unchanged=sha256(source) == input_hash,
    )
    _write_report(result, profile, before_lint, after_lint, datetime.now().astimezone().isoformat(timespec="seconds"))
    return result
