import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

from mcp import Client, StdioServerParameters

from document_factory.docx_reader import read_docx, sha256
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
            assert presets.structured_content["default"] == "grid_tech_v1_4"
            assert [item["id"] for item in presets.structured_content["presets"]] == ["grid_tech_v1_4"]

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
