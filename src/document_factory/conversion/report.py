"""Conversion review report (Markdown + JSON sidecar).

The report is the audit face of TASK_DOC_012: it must show, per the task
specification, 文档信息 / 转换前画像 / 修改统计（按维度归类）/ 逐条可追踪的
修改明细（Paragraph N, before -> after, rule）/ 未解决问题 / 最终状态。
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import __version__
from ..operations import atomic_text


def _escape(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return (
        value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")
        .replace("<", "&lt;").replace(">", "&gt;")
    )


def categorize_changes(changes: list[dict[str, Any]]) -> dict[str, int]:
    """Group change records into the report's 修改统计 dimensions."""
    buckets = Counter()
    for change in changes:
        obj, prop = change["object_type"], change["property"]
        after = str(change.get("after", ""))
        if prop == "scaffold_create":
            buckets["样式补建"] += 1
        elif obj == "Section":
            buckets["页面/页边距"] += 1
        elif obj == "Run":
            buckets["字体/字号/颜色"] += 1
        elif obj == "Paragraph" and prop == "style":
            if after.startswith("heading"):
                buckets["标题样式指派"] += 1
            elif "表格" in after:
                buckets["表格样式指派"] += 1
            elif after == "正文":
                buckets["正文样式指派"] += 1
            else:
                buckets["段落样式指派"] += 1
        elif obj == "Paragraph":
            buckets["段落格式"] += 1
        elif obj == "Style":
            buckets["样式定义修正"] += 1
        else:
            buckets["其他"] += 1
    return dict(buckets)


def write_conversion_report(result, generated: str | None = None) -> None:
    generated = generated or datetime.now().astimezone().isoformat(timespec="seconds")
    report = Path(result.report_path)
    json_path = report.with_suffix(".json")
    before_p, after_p = result.profile_before, result.profile_after
    stats = categorize_changes(result.changes)

    lines = [
        "# DocumentFactory 格式转换审核报告（Conversion Report）", "",
        "## 1. 文档信息", "",
        "| 项 | 值 |", "|---|---|",
        f"| 输入文件 | {result.input_path} |",
        f"| 输出文件 | {result.output_path} |",
        f"| 套用模板 | {result.template_id} |",
        f"| 转换时间 | {generated} |",
        f"| DocumentFactory 版本 | {__version__} |",
        f"| 输入 SHA-256 | {result.input_sha256} |",
        f"| 输出 SHA-256 | {result.output_sha256} |",
        f"| 输入文件未变化 | {result.source_unchanged} |",
        f"| 正文内容一致性 | {'PASS（转换前后全文文本逐字一致）' if result.content_preserved else 'FAIL'} |",
        "",
        "## 2. 转换前文档画像（DocumentProfile）", "",
        f"- 段落数：{before_p.get('paragraph_count')}"
        f"（非空 {before_p.get('nonempty_paragraph_count')}）",
        f"- 表格数：{before_p.get('table_count')}",
        f"- 标题结构（内置 Heading 样式）：{before_p.get('heading_structure')}",
        f"- 节/页面信息：{before_p.get('section_info')}",
        "",
        "段落样式使用：",
        "",
        "| 样式 | 段落数 |", "|---|---:|",
    ]
    for name, count in (before_p.get("style_usage") or {}).items():
        lines.append(f"| {_escape(name)} | {count} |")
    if not before_p.get("style_usage"):
        lines.append("| - | 0 |")
    lines += ["", "有效字体使用（非空文本 Run）：", "", "| 字体/字号 | Run 数 |", "|---|---:|"]
    for name, count in (before_p.get("font_usage") or {}).items():
        lines.append(f"| {_escape(name)} | {count} |")
    if not before_p.get("font_usage"):
        lines.append("| - | 0 |")

    lines += [
        "",
        "## 3. 修改统计", "",
        f"- 属性修改记录合计：**{len(result.changes)}**",
        f"- 段落样式重指派：{result.reassignment_count} 处",
        f"- 补建样式：{', '.join(result.created_styles) if result.created_styles else '无'}",
        "",
        "| 修改维度 | 数量 |", "|---|---:|",
    ]
    for name, count in sorted(stats.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    if not stats:
        lines.append("| 无需修改 | 0 |")

    lines += [
        "",
        "## 4. 修改明细（可追踪）", "",
        "所有修改均为格式调整，**不重写、不生成任何正文内容**。", "",
        "| 位置 | 属性 | 修改前 | 修改后 | Rule |",
        "|---|---|---|---|---|",
    ]
    for change in result.changes:
        values = (change["location"], change["property"], change.get("before"),
                  change.get("after"), change.get("rule"))
        lines.append("| " + " | ".join(_escape(v) for v in values) + " |")
    if not result.changes:
        lines.append("| - | - | 无需修改 | 无需修改 | - |")

    lines += ["", "## 5. 未解决问题（需人工复核）", ""]
    if result.unresolved:
        lines += ["| 类别 | 数量 | 说明 |", "|---|---:|---|"]
        for item in result.unresolved:
            lines.append(
                f"| {_escape(item.get('kind'))} | {item.get('count', '')} | "
                f"{_escape(item.get('message', ''))} |"
            )
    else:
        lines.append("无。")
    if result.warnings:
        lines += ["", "执行警告：", ""] + [f"- {w}" for w in result.warnings]
    if result.errors:
        lines += ["", "执行错误：", ""] + [f"- {e}" for e in result.errors]

    lines += [
        "",
        "## 6. 最终状态", "",
        "最终结论来自输出 DOCX 的真实 lint；转换执行成功不等于全部规则合格"
        "（如目录域、手工编号转自动编号属于明确不自动处理项）。", "",
        "| 阶段 | ERROR | WARNING | INFO |", "|---|---:|---:|---:|",
        f"| 转换前 | {result.before_counts.get('ERROR', 0)} | "
        f"{result.before_counts.get('WARNING', 0)} | {result.before_counts.get('INFO', 0)} |",
        f"| 转换后 | {result.after_counts.get('ERROR', 0)} | "
        f"{result.after_counts.get('WARNING', 0)} | {result.after_counts.get('INFO', 0)} |",
        "",
        f"**RESULT: {result.status}**", "",
        "## 7. 机器可读结果", "",
        f"同名 JSON：`{json_path}`", "",
    ]
    atomic_text(report, "\n".join(lines))

    data = {
        "schema_version": "1.0",
        "generated_at": generated,
        "document_factory_version": __version__,
        "conversion": result.to_dict(),
        "change_categories": stats,
    }
    atomic_text(json_path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
