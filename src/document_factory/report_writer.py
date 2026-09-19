from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from collections import Counter
import json
import platform
import sys
from . import __version__
from .output_paths import checked_output


def escaped(value):
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>").replace("<", "&lt;").replace(">", "&gt;")


def write_report(ctx, path, render_result=None, *, root=None):
    root = Path(root or Path.cwd()).resolve()
    path = checked_output(path, root, "reports", ctx.document.path)
    json_path = checked_output(path.with_suffix(".json"), root, "reports", ctx.document.path)
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    metadata = {"生成时间": generated, "DocumentFactory 版本": __version__, "规范版本": ctx.rules["spec_version"],
                "输入文件": str(ctx.document.path), "输入 SHA-256": ctx.document.sha256, "Lint 规则版本": ctx.rules["version"],
                "规则 SHA-256": ctx.rules.get("_sha256", "未提供"), "规范 SHA-256": ctx.rules.get("_source_sha256", "未提供"),
                "运行环境": f"{platform.platform()} / Python {platform.python_version()} / {sys.executable}",
                "是否成功渲染": render_result.status if render_result else "NOT_REQUESTED（仅执行 lint）"}
    data = {"metadata": metadata, "result": ctx.result, "counts": ctx.counts,
            "render": asdict(render_result) if render_result else None, "findings": [f.to_dict() for f in ctx.findings],
            "inventory": {"paragraphs": len(ctx.document.paragraphs), "tables": len(ctx.document.tables), "sections": ctx.document.sections,
                          "styles": len(ctx.document.styles), "parts": sorted(ctx.document.parts),
                          "fields": [asdict(f) for f in ctx.document.fields]}}
    lines = ["# DocumentFactory 文档审计报告", "", "## 1. 基本信息", ""]
    lines += [f"- {k}：{v}" for k, v in metadata.items()]
    lines += ["", "## 2. 总体结果", "", f"**RESULT: {ctx.result}**", "", *[f"- {k}: {v}" for k, v in ctx.counts.items()],
              f"- PASS 检查记录：{sum(f.status == 'PASS' for f in ctx.findings)}", f"- UNSUPPORTED 记录：{sum(f.status == 'UNSUPPORTED' for f in ctx.findings)}",
              "", "RESULT 为结构规则结果：任何 ERROR 均为 FAIL。WARNING / UNSUPPORTED 不代表合规已获证明；渲染状态单独列出。INFO 数含 PASS 检查记录。", ""]
    categories = [("3. 页面结构检查", ("PAGE", "FRONT")), ("4. 样式检查", ("STYLE004", "STYLE005", "STRUCT")),
                  ("5. Heading 与编号检查", ("STYLE001", "STYLE002", "STYLE003", "NUM")), ("6. TOC 检查", ("TOC",)),
                  ("7. 正文检查", ("BODY",)), ("8. 表格检查", ("TABLE",)), ("9. 字体与 Run 异常检查", ("FONT",))]
    for title, prefixes in categories:
        items = [f for f in ctx.findings if f.rule_id.startswith(prefixes)]
        counts = Counter(f.severity for f in items)
        lines += [f"## {title}", "", f"ERROR {counts['ERROR']} / WARNING {counts['WARNING']} / INFO {counts['INFO']}", "", "| Rule ID | PASS | FAIL | UNSUPPORTED |", "|---|---:|---:|---:|"]
        for rule in sorted({f.rule_id for f in items}):
            c = Counter(f.status for f in items if f.rule_id == rule)
            lines.append(f"| {rule} | {c['PASS']} | {c['FAIL']} | {c['UNSUPPORTED']} |")
        lines.append("")
    lines += ["## 10. 渲染结果", ""]
    if render_result:
        lines += [f"- 状态：{render_result.status}", f"- 后端：{render_result.backend}", f"- PDF：{render_result.pdf or '未生成'}",
                  f"- PNG 页数：{len(render_result.pages)}", f"- 原文件 SHA-256 未变化：{render_result.source_unchanged}", f"- 说明：{render_result.message}"]
    else:
        lines.append("本次仅执行 lint，未请求渲染。")
    lines += ["", "## 11. 问题明细", "", "完整 PASS 与问题记录另见同名 JSON。以下列出所有非 PASS 记录。", "", "| Rule ID | Severity | 状态 | 对象类型 | 位置 | 当前值 | 预期值 | 说明 | 规范出处 |", "|---|---|---|---|---|---|---|---|---|"]
    for f in ctx.findings:
        if f.status != "PASS":
            lines.append("| " + " | ".join(escaped(v) for v in (f.rule_id, f.severity, f.status, f.object_type, f.location, f.actual, f.expected, f.message, f.source)) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
