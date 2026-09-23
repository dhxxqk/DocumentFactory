"""TemplateRunner: apply an OperationPlan to a Document deterministically.

The runner owns element selection (which style is the body, which styles are
headings, which sectPr elements are real) and dispatches the plan's profiles
through the operations layer. It contains no format decisions: the template
decided the facts; the runner only locates targets and calls operations.

Scope (v1): style elements + sectPr only. Direct run-level repair stays with
the normalizer (rule-engine repair semantics). Headers/footers in
word/headerN.xml are out of scope.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import __version__
from ..docx_reader import NS, q, read_docx, sha256
from ..lint_engine import lint, load_rules
from ..models import DocumentFactoryError, ExecutionResult
from ..operations import (
    OperationContext,
    apply_alignment,
    apply_font,
    apply_indent,
    apply_section_properties,
    apply_spacing,
    atomic_text,
    find_style_element,
    write_package,
)
from ..output_paths import checked_output
from ..templates import TemplateDefinition, TemplateNotFoundError, load_template
from .mapper import build_operation_plan
from .models import OperationPlan

_HEADING_RE = re.compile(r"(?:heading\s*|标题\s*)([1-3])", re.I)


def _ctx(changes, object_type, location, template_id, prefix=""):
    return OperationContext(
        changes=changes,
        object_type=object_type,
        location=location,
        rule_id="TEMPLATE_RUN",
        source=f"Template {template_id}",
        prefix=prefix,
    )


def _resolve_heading_levels(document) -> dict[str, str]:
    """Map heading level ("h1"/"h2"/"h3") -> styleId, by scanning style names."""
    result: dict[str, str] = {}
    for style in document.styles.values():
        if style.kind != "paragraph":
            continue
        match = _HEADING_RE.fullmatch(style.name or "")
        if match:
            key = f"h{match.group(1)}"
            if key not in result:
                result[key] = style.style_id
    return result


def _resolve_sect_prs(document) -> list:
    """Return real sectPr elements (excluding those inside sectPrChange)."""
    root = document.parts.get("word/document.xml")
    if root is None:
        return []
    result = []
    for sect_pr in root.findall(".//w:sectPr", NS):
        if any(a.tag == q("sectPrChange") for a in sect_pr.iterancestors()):
            continue
        result.append(sect_pr)
    return result


class TemplateRunner:
    """Apply an OperationPlan to a Document and return an ExecutionResult."""

    def run(self, template: TemplateDefinition, document) -> ExecutionResult:
        plan = build_operation_plan(template)
        return self._apply_plan(template, document, plan)

    def _apply_plan(self, template, document, plan: OperationPlan) -> ExecutionResult:
        changes: list[dict[str, Any]] = []
        changed_parts: set[str] = set()
        warnings: list[str] = []
        errors: list[str] = []
        template_id = template.id

        # --- Body style ---
        body_rule = template.rules.body
        body_style = next(
            (s for s in document.styles.values()
             if s.kind == "paragraph" and s.name == body_rule.style_name),
            None,
        )
        if body_style is None:
            errors.append(f"未找到正文样式：{body_rule.style_name}")
        else:
            element = find_style_element(document, body_style.style_id)
            if element is None:
                errors.append(f"正文样式元素缺失：{body_style.style_id}")
            else:
                location = f"Style {body_style.name}"
                ctx = _ctx(changes, "Style", location, template_id)
                body_profile = plan.body_paragraph
                changed = apply_indent(
                    element, body_profile.indent, ctx,
                    remove=("firstLine", "hanging", "hangingChars"),
                )
                changed |= apply_spacing(
                    element, body_profile.spacing, ctx,
                    remove=("beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"),
                )
                changed |= apply_alignment(element, body_profile.alignment, ctx)
                changed |= apply_font(element, plan.body_font, ctx)
                if changed:
                    changed_parts.add("word/styles.xml")

        # --- Heading styles ---
        heading_levels = _resolve_heading_levels(document)
        for level, font_profile in plan.heading_fonts.items():
            style_id = heading_levels.get(level)
            if style_id is None:
                warnings.append(f"未找到 Heading {level.lstrip('h')} 样式，跳过")
                continue
            element = find_style_element(document, style_id)
            if element is None:
                warnings.append(f"Heading {level.lstrip('h')} 样式元素缺失：{style_id}")
                continue
            name = document.styles[style_id].name
            ctx = _ctx(changes, "Style", f"Style {name}", template_id, prefix=f"{level}_")
            if apply_font(element, font_profile, ctx):
                changed_parts.add("word/styles.xml")

        # --- Page / section ---
        if plan.page is not None:
            sect_prs = _resolve_sect_prs(document)
            if not sect_prs:
                warnings.append("未找到 sectPr 元素，跳过页面规则")
            for sect_pr in sect_prs:
                ctx = _ctx(changes, "Section", "Section properties", template_id, prefix="page_")
                if apply_section_properties(sect_pr, plan.page, ctx):
                    changed_parts.add("word/document.xml")

        # --- Table styles ---
        if plan.table_font is not None and plan.table_style_names:
            matched = 0
            for style in document.styles.values():
                if style.kind != "paragraph" or style.name not in plan.table_style_names:
                    continue
                element = find_style_element(document, style.style_id)
                if element is None:
                    continue
                ctx = _ctx(changes, "Style", f"Style {style.name}", template_id, prefix="table_")
                if apply_font(element, plan.table_font, ctx):
                    changed_parts.add("word/styles.xml")
                matched += 1
            if matched == 0:
                warnings.append(
                    f"未找到表格样式（{', '.join(plan.table_style_names)}），跳过表格规则"
                )

        status = "FAIL" if errors else "PASS"
        return ExecutionResult(
            status=status,
            template_id=template_id,
            input_path="",
            output_path="",
            report_path="",
            input_sha256="",
            output_sha256="",
            operations_count=len(changes),
            before_counts={},
            after_counts={},
            changes=changes,
            changed_parts=sorted(changed_parts),
            warnings=warnings,
            errors=errors,
            source_unchanged=True,
        )


def _write_report(result: ExecutionResult, before, after, generated, report_path, json_path):
    change_types = Counter(change["object_type"] for change in result.changes)
    lines = [
        "# DocumentFactory Template Execution Report", "",
        "## 1. 基本信息", "",
        f"- 实际生成时间（含时区）：{generated}",
        f"- DocumentFactory 版本：{__version__}",
        f"- 模板 ID：{result.template_id}",
        f"- 输入文件：{result.input_path}",
        f"- 输出文件：{result.output_path}",
        f"- 输入 SHA-256：{result.input_sha256}",
        f"- 输出 SHA-256：{result.output_sha256}",
        f"- 报告：{result.report_path}",
        f"- 输入文件未变化：{result.source_unchanged}", "",
        "## 2. 执行结论", "", f"**RESULT: {result.status}**", "",
        "最终结论来自输出 DOCX 的真实 lint；模板应用成功不等于全部格式合格。", "",
        "| 阶段 | ERROR | WARNING | INFO |", "|---|---:|---:|---:|",
        f"| 执行前 | {result.before_counts.get('ERROR', 0)} | {result.before_counts.get('WARNING', 0)} | {result.before_counts.get('INFO', 0)} |",
        f"| 执行后 | {result.after_counts.get('ERROR', 0)} | {result.after_counts.get('WARNING', 0)} | {result.after_counts.get('INFO', 0)} |", "",
        "## 3. 修改统计", "",
        f"- 属性修改记录：{len(result.changes)}",
        f"- 变更部件：{', '.join(result.changed_parts) or '无'}",
        f"- 警告：{len(result.warnings)}",
        f"- 错误：{len(result.errors)}", "",
    ]
    lines += [f"- {name}：{count}" for name, count in sorted(change_types.items())]
    lines += ["", "## 4. 修改明细", "", "| 对象类型 | 位置 | 属性 | 修改前 | 修改后 |", "|---|---|---|---|---|"]
    for change in result.changes:
        values = [change[key] for key in ("object_type", "location", "property", "before", "after")]
        lines.append("| " + " | ".join(_escape(v) for v in values) + " |")
    if not result.changes:
        lines.append("| - | - | - | 无需修改 | 无需修改 |")
    if result.warnings:
        lines += ["", "## 5. 警告", ""] + [f"- {w}" for w in result.warnings]
    if result.errors:
        lines += ["", "## 6. 错误", ""] + [f"- {e}" for e in result.errors]
    lines += ["", "## 7. 机器可读结果", "", f"同名 JSON：`{json_path}`", ""]
    atomic_text(Path(report_path), "\n".join(lines))
    data = {
        "schema_version": "1.0",
        "generated_at": generated,
        "document_factory_version": __version__,
        "execution": result.to_dict(),
        "before_findings": [f.to_dict() for f in before.findings],
        "after_findings": [f.to_dict() for f in after.findings],
    }
    atomic_text(Path(json_path), json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _escape(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>").replace("<", "&lt;").replace(">", "&gt;")


def run_template(template_id, input_path, output_path=None, report_path=None, rules_path=None) -> ExecutionResult:
    """Load a template by id and apply it to a DOCX, producing a validated output.

    Mirrors ``normalizer.normalize``: lint before -> apply -> write_package ->
    read_docx validity check -> lint after -> report. The template defines the
    target facts; the operations layer executes them deterministically.
    """
    root = Path.cwd().resolve()
    source = Path(input_path).resolve()
    if source.suffix.lower() != ".docx":
        raise DocumentFactoryError("run_template 输入必须是 DOCX 文件")
    output = checked_output(
        output_path or Path("output/template_run") / f"{source.stem}_templated.docx",
        root, "output", source,
    )
    report = checked_output(
        report_path or Path("reports") / f"{source.stem}_TEMPLATE_RUN_REPORT.md",
        root, "reports", source,
    )
    if output.suffix.lower() != ".docx":
        raise DocumentFactoryError("run_template 输出必须使用 .docx 扩展名")
    if report.suffix.lower() != ".md":
        raise DocumentFactoryError("run_template 报告必须使用 .md 扩展名（同名 JSON 自动生成）")

    template = load_template(template_id)
    if rules_path is None:
        rules_path = Path("rules/grid_tech_v1_4.yaml")
    rules = load_rules(rules_path)

    before = lint(source, rules)
    input_hash = before.document.sha256
    run_result = TemplateRunner().run(template, before.document)
    if run_result.errors:
        raise DocumentFactoryError(
            f"模板执行失败：{'; '.join(run_result.errors)}"
        )
    if sha256(source) != input_hash:
        raise DocumentFactoryError("INPUT_CHANGED：模板执行期间输入文件发生变化")
    write_package(source, output, before.document, run_result.changed_parts)
    if sha256(source) != input_hash:
        raise DocumentFactoryError("INPUT_CHANGED：模板执行期间输入文件发生变化")
    # read_docx before lint so a corrupt ZIP can never be reported as success.
    output_document = read_docx(output)
    after = lint(output, rules)

    result = ExecutionResult(
        status=after.result,
        template_id=template_id,
        input_path=str(source),
        output_path=str(output),
        report_path=str(report),
        input_sha256=input_hash,
        output_sha256=output_document.sha256,
        operations_count=run_result.operations_count,
        before_counts=before.counts,
        after_counts=after.counts,
        changes=run_result.changes,
        changed_parts=run_result.changed_parts,
        warnings=run_result.warnings,
        errors=run_result.errors,
        source_unchanged=sha256(source) == input_hash,
    )
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    json_path = Path(report).with_suffix(".json")
    _write_report(result, before, after, generated, report, json_path)
    return result
