"""End-to-end tests for the Template Execution Pipeline (template_runner.runner)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_factory.docx_reader import read_docx, sha256
from document_factory.lint_engine import lint
from document_factory.models import DocumentFactoryError, ExecutionResult
from document_factory.template_runner import TemplateRunner, run_template
from document_factory.templates import TemplateNotFoundError, load_template
from conftest import BODY_STYLE, HEADING_STYLES, ROOT, W, paragraph

NORMAL_STYLE = '<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>'

BAD_HEADINGS = ''.join(
    f'<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/>'
    f'<w:pPr><w:outlineLvl w:val="{i-1}"/></w:pPr><w:rPr>'
    f'<w:rFonts w:eastAsia="宋体" w:eastAsiaTheme="majorEastAsia"/>'
    f'<w:color w:val="2F5597" w:themeColor="accent1"/><w:sz w:val="20"/></w:rPr></w:style>'
    for i in range(1, 4)
)

BAD_BODY = (
    '<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="正文"/>'
    '<w:pPr><w:ind w:firstLineChars="100" w:hanging="20"/>'
    '<w:spacing w:before="120" w:after="120" w:line="240"/><w:jc w:val="left"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/>'
    '<w:sz w:val="20"/></w:rPr></w:style>'
)

BAD_TABLE_STYLES = (
    '<w:style w:type="paragraph" w:styleId="TableHeader"><w:name w:val="表格表头"/>'
    '<w:pPr><w:ind w:firstLineChars="100"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/>'
    '<w:sz w:val="20"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="TableBody"><w:name w:val="表格正文"/>'
    '<w:pPr/><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/>'
    '<w:sz w:val="20"/></w:rPr></w:style>'
)

BAD_SECTION = (
    '<w:sectPr><w:pgSz w:w="10000" w:h="10000"/>'
    '<w:pgMar w:top="1000" w:bottom="1000" w:left="1000" w:right="1000" '
    'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
)


def run(template_id, source, tmp_path, name="run"):
    output = tmp_path / "output" / f"{name}.docx"
    report = tmp_path / "reports" / f"{name}.md"
    return run_template(template_id, source, output, report,
                        ROOT / "rules/grid_tech_v1_4.yaml")


# ---- Test 1: template loading ------------------------------------------

def test_load_template_returns_seed_definition():
    definition = load_template("GRID_TECH_V1_4")
    assert definition.id == "GRID_TECH_V1_4"
    assert definition.rules.body.chinese_font == "仿宋"


# ---- Test 2 is in test_mapper.py ---------------------------------------


# ---- Test 3: execution pipeline end-to-end ----------------------------

def test_run_template_produces_valid_output(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    body = "".join(paragraph(f"标题{i}", f"Heading{i}") for i in range(1, 4))
    body += paragraph("正文内容 ABC 123", "Body")
    source = make_docx(
        body,
        styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS + BAD_TABLE_STYLES,
        section=BAD_SECTION,
    )
    result = run("GRID_TECH_V1_4", source, tmp_path)
    assert isinstance(result, ExecutionResult)
    assert result.template_id == "GRID_TECH_V1_4"
    assert result.operations_count > 0
    assert Path(result.output_path).is_file()
    assert read_docx(result.output_path).sha256 == result.output_sha256
    assert Path(result.report_path).is_file()
    assert Path(result.report_path).with_suffix(".json").is_file()
    assert result.source_unchanged is True
    assert sha256(source) == result.input_sha256


def test_run_template_applies_body_heading_and_page_changes(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = make_docx(
        paragraph("标题", "Heading1"),
        styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS,
        section=BAD_SECTION,
    )
    result = run("GRID_TECH_V1_4", source, tmp_path)
    change_locations = {c["location"] for c in result.changes if c["object_type"] == "Style"}
    assert "Style 正文" in change_locations
    assert "Style heading 1" in change_locations
    assert "word/styles.xml" in result.changed_parts
    assert "word/document.xml" in result.changed_parts  # section changes


def test_run_template_reduces_lint_errors(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    source = make_docx(
        paragraph("标题", "Heading1"),
        styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS,
        section=BAD_SECTION,
    )
    result = run("GRID_TECH_V1_4", source, tmp_path)
    assert result.before_counts["ERROR"] >= result.after_counts["ERROR"]


def test_second_run_is_idempotent(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = make_docx(
        paragraph("标题", "Heading1"),
        styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS,
        section=BAD_SECTION,
    )
    first = run("GRID_TECH_V1_4", source, tmp_path, "first")
    second = run("GRID_TECH_V1_4", Path(first.output_path), tmp_path, "second")
    assert second.changes == []
    assert second.operations_count == 0
    assert second.input_sha256 == second.output_sha256
    assert first.output_sha256 == second.output_sha256


def test_report_counts_match_real_lint(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    source = make_docx(
        paragraph("标题", "Heading1"),
        styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS,
        section=BAD_SECTION,
    )
    result = run("GRID_TECH_V1_4", source, tmp_path)
    before = lint(source, rules)
    after = lint(result.output_path, rules)
    assert result.before_counts == before.counts
    assert result.after_counts == after.counts
    data = json.loads(Path(result.report_path).with_suffix(".json").read_text(encoding="utf-8"))
    assert data["execution"]["before_counts"] == before.counts
    assert data["execution"]["after_counts"] == after.counts


# ---- Test 4: exceptions ------------------------------------------------

def test_run_template_unknown_id_raises_not_found(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = make_docx(paragraph("正文", "Body"))
    with pytest.raises(TemplateNotFoundError):
        run("DOES_NOT_EXIST", source, tmp_path)


def test_runner_missing_body_style_records_error(make_docx, tmp_path, monkeypatch):
    """A doc with no 正文 body style -> runner records an error (not a crash)."""
    monkeypatch.chdir(tmp_path)
    # Only Normal + headings, no Body/正文 style.
    source = make_docx(
        paragraph("标题", "Heading1"),
        styles=NORMAL_STYLE + HEADING_STYLES,
        section=BAD_SECTION,
    )
    template = load_template("GRID_TECH_V1_4")
    document = read_docx(source)
    result = TemplateRunner().run(template, document)
    assert result.status == "FAIL"
    assert any("正文" in e for e in result.errors)


def test_output_cannot_overwrite_input(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "output" / "input.docx"
    source.parent.mkdir()
    make_docx(paragraph("标题", "Heading1"), styles=NORMAL_STYLE + BODY_STYLE + HEADING_STYLES).replace(source)
    report = tmp_path / "reports" / "report.md"
    with pytest.raises(DocumentFactoryError, match="不得覆盖输入"):
        run_template("GRID_TECH_V1_4", source, source, report,
                     ROOT / "rules/grid_tech_v1_4.yaml")
