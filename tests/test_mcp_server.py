import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

from mcp import Client, StdioServerParameters

from document_factory import mcp_server
from document_factory.docx_reader import read_docx, sha256
from document_factory.lint_engine import load_rules
from conftest import ROOT, paragraph


def client_parameters():
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "document_factory.mcp_server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def cleanup_deliverables(*results):
    for result in results:
        if not result:
            continue
        for item in result.get("deliverables", []):
            path = Path(item["path"])
            if path.exists():
                path.unlink()
            json_path = path.with_suffix(".json")
            if json_path.exists():
                json_path.unlink()


def test_official_client_stdio_initialize_list_and_real_calls(make_docx, tmp_path):
    original = make_docx(paragraph("测试标题", "Heading1"))
    source = tmp_path / "中文 空格 测试文档.docx"
    shutil.copyfile(original, source)
    source_hash = sha256(source)

    async def scenario():
        audit_data = format_data = None
        async with Client(client_parameters(), mode="legacy", read_timeout_seconds=60) as client:
            assert client.server_info.name == "documentfactory"
            assert "format_document" in client.instructions
            assert "present" in client.instructions

            listed = await client.list_tools(cache_mode="bypass")
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == {"format_document", "audit_document", "list_presets"}
            assert tools["format_document"].input_schema["required"] == ["input_path"]
            assert "preset" in tools["format_document"].input_schema["properties"]
            assert tools["audit_document"].input_schema["required"] == ["input_path"]
            assert tools["list_presets"].input_schema.get("properties") == {}

            presets = await client.call_tool("list_presets", {})
            assert not presets.is_error
            # TASK_DOC_STYLE_BINDING_001：MCP 默认规范改为 default_technical_document_v1。
            assert presets.structured_content["default"] == "default_technical_document_v1"
            assert [item["id"] for item in presets.structured_content["presets"]] == [
                "default_technical_document_v1",
                "grid_tech_v1_4",
            ]

            audit = await client.call_tool("audit_document", {"input_path": str(source)})
            assert not audit.is_error
            audit_data = audit.structured_content
            assert audit_data["source_unchanged"] is True
            assert Path(audit_data["report_path"]).is_file()
            assert audit_data["deliverables"] == [
                {"kind": "markdown", "path": audit_data["report_path"], "label": "DOCX 审计报告"}
            ]

            formatted = await client.call_tool("format_document", {"input_path": str(source)})
            assert not formatted.is_error
            format_data = formatted.structured_content
            assert format_data["source_unchanged"] is True
            assert Path(format_data["output_path"]).is_file()
            assert Path(format_data["report_path"]).is_file()
            assert read_docx(format_data["output_path"])
            assert format_data["remaining_error_count"] == format_data["after"]["ERROR"]
            assert [item["kind"] for item in format_data["deliverables"]] == ["docx", "markdown"]
            assert "before_findings" not in format_data and "remaining_findings" not in format_data
            assert len(json.dumps(format_data, ensure_ascii=False)) < 10_000
            json.dumps(audit_data, ensure_ascii=False)
            json.dumps(format_data, ensure_ascii=False)
        return audit_data, format_data

    audit_data = format_data = None
    try:
        audit_data, format_data = asyncio.run(scenario())
        assert sha256(source) == source_hash
    finally:
        cleanup_deliverables(audit_data, format_data)


def test_official_client_stdio_reports_input_and_core_errors(tmp_path):
    missing = tmp_path / "不存在.docx"
    text_file = tmp_path / "不是文档.txt"
    text_file.write_text("not a docx", encoding="utf-8")
    broken_docx = tmp_path / "损坏 文档.docx"
    broken_docx.write_bytes(b"not a zip package")

    async def scenario():
        async with Client(client_parameters(), mode="legacy", read_timeout_seconds=30) as client:
            missing_result = await client.call_tool("audit_document", {"input_path": str(missing)})
            extension_result = await client.call_tool("format_document", {"input_path": str(text_file)})
            preset_result = await client.call_tool(
                "audit_document", {"input_path": str(broken_docx), "preset": "does_not_exist"}
            )
            core_result = await client.call_tool("format_document", {"input_path": str(broken_docx)})
            for result in (missing_result, extension_result, preset_result, core_result):
                assert result.is_error
                assert result.structured_content is None
            messages = [result.content[0].text for result in (missing_result, extension_result, preset_result, core_result)]
            assert "不存在" in messages[0]
            assert ".docx" in messages[1]
            assert "未知 preset" in messages[2]
            assert "DocumentFactory normalize 失败" in messages[3]

    asyncio.run(scenario())


DEFAULT_PRESET = "default_technical_document_v1"
GRID_PRESET = "grid_tech_v1_4"


def test_list_presets_contains_default_technical_document_v1():
    async def scenario():
        async with Client(client_parameters(), mode="legacy", read_timeout_seconds=30) as client:
            listed = await client.call_tool("list_presets", {})
            assert not listed.is_error
            data = listed.structured_content
            # TASK_DOC_STYLE_BINDING_001：默认 preset 切换为默认技术文档规范；
            # grid_tech_v1_4 仍作为兼容 preset 保留。
            assert data["default"] == DEFAULT_PRESET
            ids = [item["id"] for item in data["presets"]]
            assert DEFAULT_PRESET in ids
            assert GRID_PRESET in ids
            default_preset = next(item for item in data["presets"] if item["id"] == DEFAULT_PRESET)
            assert set(default_preset) >= {
                "id", "display_name", "rules_file", "spec_version", "description"
            }
            assert default_preset["display_name"] == "DocumentFactory 默认技术文档规范 V1"
            assert default_preset["spec_version"] == "V1"
            assert default_preset["description"]
            rules_file = Path(default_preset["rules_file"])
            assert rules_file == ROOT / "rules" / "default_technical_document_v1.yaml"
            assert rules_file.is_file()

    asyncio.run(scenario())


def test_default_preset_can_be_loaded():
    # MCP 只注册规则文件路径；代表性格式事实必须来自 rules YAML，而非硬编码副本。
    info = mcp_server.PRESETS[DEFAULT_PRESET]
    assert info["id"] == DEFAULT_PRESET
    assert info["rules_path"] == ROOT / "rules" / "default_technical_document_v1.yaml"
    assert info["rules_path"].is_file()
    rules = load_rules(info["rules_path"])
    assert Path(rules["_path"]) == info["rules_path"].resolve()

    document = rules["document"]
    assert document["page_size"] == "A4"
    assert document["orientation"] == "portrait"
    assert document["margins_cm"] == {"top": 2.8, "bottom": 2.6, "left": 2.8, "right": 2.6}

    body = rules["body"]
    assert body["style_name"] == "正文"
    assert body["chinese_font"] == "仿宋"
    assert body["latin_font"] == "Times New Roman"
    assert body["font_size_pt"] == 12
    assert body["line_spacing"] == 1.5
    assert body["first_line_indent_chars"] == 2
    assert body["alignment"] == "both"

    assert (rules["heading1"]["chinese_font"], rules["heading1"]["size_pt"]) == ("黑体", 16)
    assert (rules["heading2"]["chinese_font"], rules["heading2"]["size_pt"]) == ("黑体", 14)
    assert (rules["heading3"]["chinese_font"], rules["heading3"]["size_pt"]) == ("黑体", 12)

    tables = rules["tables"]
    assert tables["font_size_pt"] == 10.5
    assert tables["header_font"] == "黑体"
    assert tables["body_font"] == "仿宋"
    assert tables["latin_font"] == "Times New Roman"


def test_audit_document_accepts_default_preset(make_docx, tmp_path):
    original = make_docx(paragraph("默认规范审计标题", "Heading1"))
    source = tmp_path / "默认规范审计样本.docx"
    shutil.copyfile(original, source)
    source_hash = sha256(source)

    async def scenario():
        async with Client(client_parameters(), mode="legacy", read_timeout_seconds=60) as client:
            audit = await client.call_tool(
                "audit_document", {"input_path": str(source), "preset": DEFAULT_PRESET}
            )
            assert not audit.is_error
            data = audit.structured_content
            assert data["preset"] == DEFAULT_PRESET
            assert data["source_unchanged"] is True
            report_path = Path(data["report_path"])
            assert report_path.is_file()
            # 审计报告元数据中的规范版本来自实际加载的默认规则文件。
            assert "- 规范版本：V1\n" in report_path.read_text(encoding="utf-8")
            return data

    data = None
    try:
        data = asyncio.run(scenario())
        assert sha256(source) == source_hash
    finally:
        cleanup_deliverables(data)


def test_format_document_accepts_default_preset(make_docx, tmp_path):
    original = make_docx(paragraph("默认规范格式化标题", "Heading1"))
    source = tmp_path / "默认规范格式化样本.docx"
    shutil.copyfile(original, source)
    source_hash = sha256(source)

    async def scenario():
        async with Client(client_parameters(), mode="legacy", read_timeout_seconds=60) as client:
            formatted = await client.call_tool(
                "format_document", {"input_path": str(source), "preset": DEFAULT_PRESET}
            )
            assert not formatted.is_error
            data = formatted.structured_content
            assert data["preset"] == DEFAULT_PRESET
            assert data["source_unchanged"] is True
            output_path = Path(data["output_path"])
            report_path = Path(data["report_path"])
            assert output_path.is_file()
            assert report_path.is_file()
            assert read_docx(output_path)
            # Validation Report 必须证明 normalize Core 实际消费默认规则文件。
            assert "default_technical_document_v1.yaml" in report_path.read_text(encoding="utf-8")
            return data

    data = None
    try:
        data = asyncio.run(scenario())
        assert sha256(source) == source_hash
    finally:
        cleanup_deliverables(data)


def test_existing_grid_tech_preset_still_available(make_docx, tmp_path):
    original = make_docx(paragraph("电网规范回归标题", "Heading1"))
    source = tmp_path / "电网规范回归样本.docx"
    shutil.copyfile(original, source)
    source_hash = sha256(source)

    async def scenario():
        async with Client(client_parameters(), mode="legacy", read_timeout_seconds=60) as client:
            audit = await client.call_tool(
                "audit_document", {"input_path": str(source), "preset": GRID_PRESET}
            )
            assert not audit.is_error
            audit_data = audit.structured_content
            assert audit_data["preset"] == GRID_PRESET
            assert audit_data["source_unchanged"] is True
            assert Path(audit_data["report_path"]).is_file()

            formatted = await client.call_tool(
                "format_document", {"input_path": str(source), "preset": GRID_PRESET}
            )
            assert not formatted.is_error
            format_data = formatted.structured_content
            assert format_data["preset"] == GRID_PRESET
            assert format_data["source_unchanged"] is True
            assert Path(format_data["output_path"]).is_file()
            assert Path(format_data["report_path"]).is_file()
            assert read_docx(format_data["output_path"])
            assert "grid_tech_v1_4.yaml" in Path(format_data["report_path"]).read_text(encoding="utf-8")
            return audit_data, format_data

    audit_data = format_data = None
    try:
        audit_data, format_data = asyncio.run(scenario())
        assert sha256(source) == source_hash
    finally:
        cleanup_deliverables(audit_data, format_data)
