"""End-to-end generation pipeline: Markdown -> DOCX -> template -> validated output (Test 3)."""
from __future__ import annotations

from pathlib import Path

from conftest import ROOT
from document_factory.docx_reader import read_docx
from document_factory.generation import GenerationRequest, generate_document


SAMPLE_MD = (
    "# 项目实施方案\n\n"
    "## 背景\n\n"
    "本项目建设背景说明，描述需求来源与意义。\n\n"
    "### 目标\n\n"
    "实现企业级文档自动化生产。\n"
)


def test_pipeline_generates_valid_docx(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md_path = tmp_path / "sample.md"
    md_path.write_text(SAMPLE_MD, encoding="utf-8")
    request = GenerationRequest(
        template_id="GRID_TECH_V1_4",
        content_source="markdown",
        input_data={"file": str(md_path)},
        metadata={"rules_path": str(ROOT / "rules/grid_tech_v1_4.yaml")},
    )
    result = generate_document(request)

    # TemplateRunner v1 作用域为 style + sectPr；numbering(NUM002)/TOC(TOC001)
    # 等结构性规则归 normalizer，模板执行不引入新 ERROR 即视为流程正确。
    er = result.execution_result
    assert er is not None
    assert er.after_counts["ERROR"] <= er.before_counts["ERROR"]
    output = Path(result.output_path)
    assert output.is_file()
    # DOCX 可重新读取
    document = read_docx(result.output_path)
    assert document.sha256 == er.output_sha256
    # 报告与 JSON 旁车存在
    assert Path(result.report_path).is_file()
    assert Path(result.report_path).with_suffix(".json").is_file()
    # 结构被正确构建：标题 + 正文
    assert len(document.paragraphs) >= 4
    assert any(p.style_id == "Heading1" for p in document.paragraphs)
    assert any(p.style_id == "Body" for p in document.paragraphs)
    assert er.operations_count >= 0
    assert er.source_unchanged is True


def test_pipeline_text_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    request = GenerationRequest(
        template_id="GRID_TECH_V1_4",
        content_source="markdown",
        input_data={"text": "# 标题\n\n正文。\n"},
        metadata={"rules_path": str(ROOT / "rules/grid_tech_v1_4.yaml")},
    )
    result = generate_document(request)
    assert result.execution_result is not None
    assert result.execution_result.after_counts["ERROR"] <= result.execution_result.before_counts["ERROR"]
    assert Path(result.output_path).is_file()
    # text 源默认 stem 为 generated
    assert result.output_path.endswith("generated.docx")
