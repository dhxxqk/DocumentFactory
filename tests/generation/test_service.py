"""DocumentGenerationService integration with Template Registry (Test 2)."""
from __future__ import annotations

from conftest import ROOT
from document_factory.generation import DocumentGenerationService, GenerationRequest


def _write_md(tmp_path, name="sample.md"):
    path = tmp_path / name
    path.write_text("# 标题\n\n正文段落 ABC。\n", encoding="utf-8")
    return path


def test_generate_invokes_template_registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = _write_md(tmp_path)
    request = GenerationRequest(
        template_id="GRID_TECH_V1_4",
        content_source="markdown",
        input_data={"file": str(md)},
        metadata={"rules_path": str(ROOT / "rules/grid_tech_v1_4.yaml")},
    )
    result = DocumentGenerationService().generate(request)

    assert result.template_id == "GRID_TECH_V1_4"
    assert result.execution_result is not None
    assert result.execution_result.template_id == "GRID_TECH_V1_4"
    assert result.errors == []


def test_generate_returns_usable_output_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = _write_md(tmp_path)
    request = GenerationRequest(
        template_id="GRID_TECH_V1_4",
        content_source="markdown",
        input_data={"file": str(md)},
        metadata={"rules_path": str(ROOT / "rules/grid_tech_v1_4.yaml")},
    )
    result = DocumentGenerationService().generate(request)
    assert result.output_path.endswith("sample.docx")
    assert result.report_path.endswith("sample_GENERATION_REPORT.md")
