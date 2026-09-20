"""Thin stdio MCP adapter for the DocumentFactory Core."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

try:
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError as exc:  # pragma: no cover - exercised without the optional extra
    print(
        "DocumentFactory MCP 依赖未安装；请执行：python -m pip install -e '.[mcp]'",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc

from . import __version__
from .docx_reader import sha256
from .lint_engine import lint, load_rules
from .models import DocumentFactoryError
from .normalizer import normalize
from .report_writer import write_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRESETS = {
    "grid_tech_v1_4": {
        "id": "grid_tech_v1_4",
        "display_name": "电网科技项目实施方案 V1.4",
        "rules_path": PROJECT_ROOT / "rules" / "grid_tech_v1_4.yaml",
        "description": "确定性检查并规范化已确认的 Heading、正文和表格样式；不自动修复编号或 TOC。",
    }
}

SERVER_INSTRUCTIONS = """
DocumentFactory 是 DOCX 审计与确定性规范化工具。用户要求统一 Word/DOCX 字体、格式、按规范排版、检查并修复格式时，优先调用 format_document；只检查不修改时调用 audit_document；查询规范时调用 list_presets。不要使用 shell、脚本或手工 XML 替代这些工具修改同一个 DOCX。format_document 完成后，必须对返回的 formatted DOCX 和 Markdown Validation Report 调用 DSH present，不能只回复路径。最终回答应准确说明 before/after ERROR 与 WARNING；after 仍有 ERROR 时必须列明仍需处理，不得声称全部合格。
""".strip()

mcp = MCPServer(
    name="documentfactory",
    title="DocumentFactory",
    description="Thin MCP adapter for deterministic DOCX audit and normalization.",
    instructions=SERVER_INSTRUCTIONS,
    version=__version__,
)


def _preset(preset_id: str) -> dict[str, Any]:
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        available = ", ".join(sorted(PRESETS))
        raise ToolError(f"未知 preset：{preset_id}；可用值：{available}") from exc


def _input_docx(input_path: str) -> Path:
    source = Path(input_path).expanduser().resolve()
    if not source.exists():
        raise ToolError(f"输入文件不存在：{source}")
    if not source.is_file():
        raise ToolError(f"输入路径不是普通文件：{source}")
    if source.suffix.lower() != ".docx":
        raise ToolError(f"输入文件必须使用 .docx 扩展名：{source}")
    return source


def _artifact_paths(source: Path, digest: str, operation: str) -> tuple[Path | None, Path]:
    token = digest[:12]
    if operation == "format":
        output = PROJECT_ROOT / "output" / "normalized" / f"{source.stem}_{token}_formatted.docx"
        report = PROJECT_ROOT / "reports" / f"{source.stem}_{token}_NORMALIZATION_REPORT.md"
        return output, report
    report = PROJECT_ROOT / "reports" / f"{source.stem}_{token}_AUDIT_REPORT.md"
    return None, report


@mcp.tool(structured_output=True)
def list_presets() -> dict[str, Any]:
    """列出 DocumentFactory 明确注册的可用文档规范；不要猜测规则文件名。"""
    presets = []
    for item in PRESETS.values():
        try:
            rules = load_rules(item["rules_path"])
        except DocumentFactoryError as exc:
            raise ToolError(f"DocumentFactory preset 加载失败：{exc}") from exc
        presets.append(
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "rules_file": str(item["rules_path"]),
                "spec_version": rules["spec_version"],
                "description": item["description"],
            }
        )
    return {"presets": presets, "default": "grid_tech_v1_4"}


@mcp.tool(structured_output=True)
def audit_document(input_path: str, preset: str = "grid_tech_v1_4") -> dict[str, Any]:
    """只检查指定 DOCX，不修改输入；生成 Markdown 审计报告。用户说“检查但不要修改”时使用。"""
    source = _input_docx(input_path)
    preset_info = _preset(preset)
    before_hash = sha256(source)
    try:
        context = lint(source, preset_info["rules_path"])
        _, report = _artifact_paths(source, before_hash, "audit")
        report = write_report(context, report, root=PROJECT_ROOT)
    except DocumentFactoryError as exc:
        raise ToolError(f"DocumentFactory audit 失败：{exc}") from exc
    source_unchanged = sha256(source) == before_hash
    if not source_unchanged:
        raise ToolError("INPUT_CHANGED：audit_document 执行期间输入文件发生变化")
    counts = context.counts
    summary = (
        f"审计完成：ERROR={counts['ERROR']}，WARNING={counts['WARNING']}，INFO={counts['INFO']}。"
        + ("文档仍有 ERROR，不能宣称全部合格。" if counts["ERROR"] else "未发现 ERROR，但 WARNING 仍需人工确认。")
    )
    return {
        "status": context.result,
        "input_path": str(source),
        "preset": preset,
        "counts": counts,
        "report_path": str(report),
        "source_unchanged": source_unchanged,
        "summary": summary,
        "deliverables": [{"kind": "markdown", "path": str(report), "label": "DOCX 审计报告"}],
    }


@mcp.tool(structured_output=True)
def format_document(input_path: str, preset: str = "grid_tech_v1_4") -> dict[str, Any]:
    """按已注册规范统一 DOCX 格式。直接调用 DocumentFactory normalize Core，并返回需用 DSH present 交付的 DOCX 与 Markdown。"""
    source = _input_docx(input_path)
    preset_info = _preset(preset)
    input_hash = sha256(source)
    output, report = _artifact_paths(source, input_hash, "format")
    try:
        result = normalize(source, preset_info["rules_path"], output, report)
    except DocumentFactoryError as exc:
        raise ToolError(f"DocumentFactory normalize 失败：{exc}") from exc
    after_error = result.after_counts["ERROR"]
    summary = (
        f"规范化完成：ERROR {result.before_counts['ERROR']} → {after_error}，"
        f"WARNING {result.before_counts['WARNING']} → {result.after_counts['WARNING']}，"
        f"修改 {len(result.changes)} 项。"
        + ("输出仍有 ERROR，不能宣称全部合格；请查看 Validation Report。" if after_error else "输出未发现 ERROR；WARNING 仍需人工确认。")
    )
    return {
        "status": result.status,
        "input_path": result.input_path,
        "output_path": result.output_path,
        "report_path": result.report_path,
        "preset": preset,
        "before": result.before_counts,
        "after": result.after_counts,
        "changed_count": len(result.changes),
        "remaining_error_count": after_error,
        "source_unchanged": result.source_unchanged,
        "summary": summary,
        "deliverables": [
            {"kind": "docx", "path": result.output_path, "label": "规范化后的 DOCX"},
            {"kind": "markdown", "path": result.report_path, "label": "Validation Report"},
        ],
    }


def main() -> None:
    """Run the local MCP server over stdio."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
