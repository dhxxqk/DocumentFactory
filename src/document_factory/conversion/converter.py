"""DocumentFormatConverter: Word -> Word 格式转换流水线。

流程（确定性，无 AI、无内容重写）：

    输入 DOCX
      -> DocumentInputProvider（只读加载）
      -> DocumentAnalyzer（转换前画像）
      -> TemplateDefinition 选择
      -> 样式脚手架（缺什么样式补什么样式）
      -> 段落角色确定性分类 + w:pStyle 重指派
      -> TemplateRunner（样式定义 + sectPr 页面规范）
      -> normalizer 直接格式层（Run 字体/字号/颜色、表格段落）
      -> 内容一致性守卫 + 写保护副本 + read_docx 校验
      -> lint 复检
      -> 审核报告（逐条可追踪修改 + 未解决问题）

与 generation 的区别：generation 是 Markdown -> 新 DOCX（产生内容）；
conversion 是既有 DOCX -> 规范 DOCX（只调格式，正文逐字不动）。
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..analyzer import analyze_document
from ..docx_reader import read_docx, sha256
from ..lint_engine import lint, load_rules
from ..models import DocumentFactoryError
from ..normalizer import _apply_normalization
from ..operations import write_package
from ..output_paths import checked_output
from ..templates import load_template
from ..template_runner.runner import TemplateRunner
from .classifier import classify_paragraphs
from .inputs import DocumentInputProvider
from .models import ConversionResult
from .report import write_conversion_report
from .structure import ensure_template_styles, reassign_paragraph_styles


def _project_root() -> Path:
    # src/document_factory/conversion/converter.py -> parents[3] = project root
    return Path(__file__).resolve().parents[3]


def _all_text(document) -> list[str]:
    return [p.text for p in document.paragraphs if p.part == "word/document.xml"]


class DocumentFormatConverter:
    """Apply a registered template's format to an existing DOCX in place of
    its formatting, emitting a protected copy and a traceable review report.
    """

    def convert(
        self,
        input_docx: str | Path,
        template_id: str,
        output_docx: str | Path | None = None,
        report_path: str | Path | None = None,
        rules_path: str | Path | None = None,
    ) -> ConversionResult:
        root = Path.cwd().resolve()
        source = Path(input_docx).resolve()
        if source.suffix.lower() != ".docx":
            raise DocumentFactoryError("convert 输入必须是 DOCX 文件")
        output = checked_output(
            output_docx or Path("output/converted") / f"{source.stem}_converted.docx",
            root, "output", source,
        )
        report = checked_output(
            report_path or Path("reports") / f"{source.stem}_CONVERSION_REPORT.md",
            root, "reports", source,
        )
        if output.suffix.lower() != ".docx":
            raise DocumentFactoryError("convert 输出必须使用 .docx 扩展名")
        if report.suffix.lower() != ".md":
            raise DocumentFactoryError("convert 报告必须使用 .md 扩展名（同名 JSON 自动生成）")

        template = load_template(template_id)
        if rules_path is None:
            rule_file = template.metadata.get("rule_file")
            rules_path = _project_root() / rule_file if rule_file \
                else Path("rules/grid_tech_v1_4.yaml")
        rules = load_rules(rules_path)

        # 1. 只读加载 + 转换前 lint/画像。
        document = DocumentInputProvider().load_docx(source)
        before = lint(source, rules)
        input_hash = document.sha256
        profile_before = analyze_document(document).to_dict()
        original_texts = _all_text(document)

        changes: list = []
        changed_parts: set[str] = set()
        warnings: list[str] = []
        errors: list[str] = []

        # 2. 样式脚手架：任意 DOCX 可能缺 正文/Heading/表格 样式。
        created_styles, scaffold_parts = ensure_template_styles(document, template, changes)
        changed_parts |= scaffold_parts

        # 3. 确定性角色分类 + 段落样式重指派（仅 w:pStyle，不动文本）。
        assignments = classify_paragraphs(document)
        cover_assignments = [a for a in assignments if a.role == "cover"]
        count, reassign_parts = reassign_paragraph_styles(document, assignments, template_id, changes)
        changed_parts |= reassign_parts

        # 4. 模板执行层：样式定义事实 + sectPr 页面规范。
        run_result = TemplateRunner().run(template, document)
        changes.extend(run_result.changes)
        changed_parts |= set(run_result.changed_parts)
        warnings.extend(run_result.warnings)
        errors.extend(run_result.errors)
        if run_result.errors:
            raise DocumentFactoryError(f"格式转换失败：{'; '.join(run_result.errors)}")

        # 5. 直接格式层：Run 字体/字号/颜色、表格段落（复用 normalizer 决策+操作）。
        norm_changes, norm_parts = _apply_normalization(document, rules)
        changes.extend(norm_changes)
        changed_parts |= norm_parts

        # 6. 内容一致性守卫（内存态）：转换前后正文逐字一致。
        content_preserved = _all_text(document) == original_texts
        if not content_preserved:
            raise DocumentFactoryError("CONTENT_CHANGED：格式转换检测到正文文本变化，已中止")

        # 7. 写保护副本（输入 sha 双重守卫 + 写后 read_docx 有效性校验）。
        if sha256(source) != input_hash:
            raise DocumentFactoryError("INPUT_CHANGED：格式转换期间输入文件发生变化")
        write_package(source, output, document, changed_parts)
        if sha256(source) != input_hash:
            raise DocumentFactoryError("INPUT_CHANGED：格式转换期间输入文件发生变化")
        output_document = read_docx(output)
        content_preserved = _all_text(output_document) == original_texts
        if not content_preserved:
            raise DocumentFactoryError("CONTENT_CHANGED：输出文件正文文本与输入不一致")

        # 8. 真实 lint 复检 + 转换后画像。
        after = lint(output, rules)
        profile_after = analyze_document(output_document).to_dict()

        unresolved = self._build_unresolved(
            assignments, cover_assignments, after, document,
        )

        result = ConversionResult(
            status=after.result,
            template_id=template_id,
            input_path=str(source),
            output_path=str(output),
            report_path=str(report),
            input_sha256=input_hash,
            output_sha256=output_document.sha256,
            profile_before=profile_before,
            profile_after=profile_after,
            before_counts=before.counts,
            after_counts=after.counts,
            changes=changes,
            reassignment_count=count,
            created_styles=created_styles,
            unresolved=unresolved,
            content_preserved=content_preserved,
            warnings=warnings,
            errors=errors,
            source_unchanged=sha256(source) == input_hash,
        )
        write_conversion_report(result)
        return result

    @staticmethod
    def _build_unresolved(assignments, cover_assignments, after, document) -> list[dict]:
        unresolved: list[dict] = []
        if cover_assignments:
            samples = "；".join(
                document.paragraphs[a.index - 1].text.strip()[:20]
                for a in cover_assignments[:5]
                if 0 < a.index <= len(document.paragraphs)
            )
            unresolved.append({
                "kind": "封面/前置区域",
                "count": len(cover_assignments),
                "message": f"首个标题之前的段落保留原格式，需人工确认（样本：{samples}）",
            })
        remaining = Counter()
        messages: dict[str, str] = {}
        for finding in after.findings:
            if finding.severity in ("ERROR", "WARNING") or finding.status == "UNSUPPORTED":
                remaining[finding.rule_id] += 1
                messages.setdefault(finding.rule_id, finding.message)
        rule_severity = {f.rule_id: f.severity for f in after.findings}
        for rule_id, count in sorted(remaining.items()):
            unresolved.append({
                "kind": f"{rule_id}（{rule_severity.get(rule_id, '')}）",
                "count": count,
                "message": messages[rule_id],
            })
        for diagnostic in document.diagnostics:
            unresolved.append({
                "kind": "STRUCT001", "count": 1, "message": diagnostic,
            })
        return unresolved


def convert_document(
    input_docx: str | Path,
    template_id: str,
    output_docx: str | Path | None = None,
    report_path: str | Path | None = None,
    rules_path: str | Path | None = None,
) -> ConversionResult:
    """Functional shorthand for ``DocumentFormatConverter().convert(...)``."""
    return DocumentFormatConverter().convert(
        input_docx, template_id, output_docx, report_path, rules_path
    )
