import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest
from lxml import etree

from document_factory.docx_reader import NS, read_docx, sha256
from document_factory.lint_engine import lint
from document_factory.models import DocumentFactoryError, NormalizationResult
from document_factory.normalizer import normalize
from conftest import BODY_STYLE, HEADING_STYLES, ROOT, W, paragraph


NORMAL_STYLE = '<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>'
BAD_HEADINGS = ''.join(
    f'<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/>'
    f'<w:pPr><w:outlineLvl w:val="{i-1}"/></w:pPr><w:rPr><w:rFonts w:eastAsia="宋体" '
    f'w:eastAsiaTheme="majorEastAsia"/><w:color w:val="2F5597" w:themeColor="accent1"/>'
    f'<w:sz w:val="20"/></w:rPr></w:style>' for i in range(1, 4)
)
BAD_BODY = '''<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="正文"/>
<w:pPr><w:ind w:firstLineChars="100" w:hanging="20"/><w:spacing w:before="120" w:after="120" w:line="240"/><w:jc w:val="left"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr></w:style>'''
BAD_TABLE_STYLES = '''
<w:style w:type="paragraph" w:styleId="TableHeader"><w:name w:val="表格表头"/><w:pPr><w:ind w:firstLineChars="100"/><w:spacing w:before="100"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableBody"><w:name w:val="表格正文"/><w:pPr/><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableCenter"><w:name w:val="表格正文-居中"/><w:pPr/><w:rPr/></w:style>'''


def run_normalize(path, tmp_path, name="normalized"):
    output = tmp_path / "output" / f"{name}.docx"
    report = tmp_path / "reports" / f"{name}.md"
    return normalize(path, ROOT / "rules/grid_tech_v1_4.yaml", output, report)


def test_input_unchanged_output_readable_and_structured_result(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = make_docx(paragraph("标题", "Heading1"), styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS)
    before = sha256(source)
    result = run_normalize(source, tmp_path)
    assert isinstance(result, NormalizationResult)
    assert sha256(source) == before and result.source_unchanged
    assert Path(result.output_path) != source.resolve()
    assert read_docx(result.output_path).sha256 == result.output_sha256
    assert Path(result.report_path).is_file() and Path(result.report_path).with_suffix(".json").is_file()


def test_output_cannot_overwrite_input(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "output/input.docx"
    source.parent.mkdir()
    shutil.copyfile(make_docx(), source)
    before = sha256(source)
    with pytest.raises(DocumentFactoryError, match="不得覆盖输入"):
        normalize(source, ROOT / "rules/grid_tech_v1_4.yaml", source, tmp_path / "reports/report.md")
    assert sha256(source) == before


def test_unknown_zip_part_is_preserved_byte_for_byte(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = b"opaque-extension-payload\x00\xff"
    source = make_docx(paragraph("标题", "Heading1"), styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS, extra={"custom/opaque.bin": payload})
    result = run_normalize(source, tmp_path)
    with ZipFile(result.output_path) as archive:
        assert archive.read("custom/opaque.bin") == payload


def test_heading_1_2_3_styles_and_run_overrides_are_repaired(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    body = "".join(paragraph(f"标题{i}", f"Heading{i}", run_properties='<w:rFonts w:eastAsia="微软雅黑"/><w:color w:val="FF0000"/><w:sz w:val="18"/>') for i in range(1, 4))
    source = make_docx(body, styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS)
    result = run_normalize(source, tmp_path)
    after = lint(result.output_path, rules)
    relevant = [f for f in after.findings if f.rule_id in {"STYLE005", "FONT001", "FONT003", "FONT004"} and f.severity == "ERROR"]
    assert not relevant
    assert {change["location"] for change in result.changes if change["object_type"] == "Style"} >= {"Style heading 1", "Style heading 2", "Style heading 3"}


def test_body_style_paragraph_and_run_are_repaired(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    direct = '<w:ind w:firstLineChars="50"/><w:spacing w:before="80" w:after="40" w:line="240"/><w:jc w:val="left"/>'
    run = '<w:rFonts w:eastAsia="宋体" w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="18"/>'
    source = make_docx(paragraph("正文 ABC 123", "Body", direct, run), styles=NORMAL_STYLE + BAD_BODY + HEADING_STYLES)
    result = run_normalize(source, tmp_path)
    after = lint(result.output_path, rules)
    assert not [f for f in after.findings if f.rule_id.startswith(("BODY", "FONT")) and f.severity == "ERROR"]


def test_certain_table_styles_are_repaired(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    header = paragraph("表头 A", "TableHeader", '<w:ind w:firstLineChars="100"/><w:spacing w:before="100"/>', '<w:rFonts w:eastAsia="宋体" w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="18"/>')
    body = paragraph("内容 B", "TableBody", '<w:ind w:left="20"/><w:spacing w:after="100"/>', '<w:rFonts w:eastAsia="宋体" w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="18"/>')
    table = f'<w:tbl><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid><w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc>{header}</w:tc></w:tr><w:tr><w:tc>{body}</w:tc></w:tr></w:tbl>'
    source = make_docx(table, styles=NORMAL_STYLE + BODY_STYLE + HEADING_STYLES + BAD_TABLE_STYLES)
    result = run_normalize(source, tmp_path)
    after = lint(result.output_path, rules)
    assert not [f for f in after.findings if f.rule_id in {"TABLE004", "TABLE006", "TABLE007", "TABLE008", "FONT001", "FONT002", "FONT003"} and f.severity == "ERROR"]


def test_normal_body_candidate_and_heading_candidate_are_not_reclassified(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    normal = paragraph("这是一段足够长的普通样式正文候选，长度超过四十个字符但语义不确定，因此绝不能自动升级为正文样式。", "Normal")
    candidate = paragraph("1 疑似标题", "Normal", run_properties="<w:b/>")
    source = make_docx(normal + candidate, styles=NORMAL_STYLE + BAD_BODY + HEADING_STYLES)
    result = run_normalize(source, tmp_path)
    document = read_docx(result.output_path)
    selected = [p for p in document.paragraphs if p.text.startswith(("这是", "1 疑似"))]
    assert [p.style_id for p in selected] == ["Normal", "Normal"]


def test_numbering_and_toc_xml_are_not_changed(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    heading = '<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr><w:r><w:t>标题</w:t></w:r></w:p>'
    toc = r'<w:p><w:fldSimple w:instr="TOC \o &quot;1-2&quot; \h \z \u"><w:r><w:t>目录结果</w:t></w:r></w:fldSimple></w:p>'
    source = make_docx(toc + heading, styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS, numbering='<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="multilevel"/><w:lvl w:ilvl="0"><w:pStyle w:val="Heading1"/></w:lvl></w:abstractNum><w:num w:numId="5"><w:abstractNumId w:val="1"/></w:num>')
    before = read_docx(source)
    before_num = etree.tostring(before.parts["word/document.xml"].find(".//w:numPr", NS))
    before_field = before.fields[0].instruction
    numbering_bytes = ZipFile(source).read("word/numbering.xml")
    result = run_normalize(source, tmp_path)
    after = read_docx(result.output_path)
    assert etree.tostring(after.parts["word/document.xml"].find(".//w:numPr", NS)) == before_num
    assert after.fields[0].instruction == before_field
    with ZipFile(result.output_path) as archive:
        assert archive.read("word/numbering.xml") == numbering_bytes


def test_second_normalization_is_idempotent(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = make_docx(paragraph("标题", "Heading1"), styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS)
    first = run_normalize(source, tmp_path, "first")
    second = run_normalize(first.output_path, tmp_path, "second")
    assert second.changes == []
    assert second.input_sha256 == second.output_sha256
    assert first.output_sha256 == second.output_sha256


def test_counts_and_validation_json_match_real_lint(make_docx, tmp_path, monkeypatch, rules):
    monkeypatch.chdir(tmp_path)
    source = make_docx(paragraph("标题", "Heading1"), styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS)
    result = run_normalize(source, tmp_path)
    before = lint(source, rules)
    after = lint(result.output_path, rules)
    data = json.loads(Path(result.report_path).with_suffix(".json").read_text(encoding="utf-8"))
    assert result.before_counts == before.counts
    assert result.after_counts == after.counts
    assert data["normalization"]["before_counts"] == before.counts
    assert data["normalization"]["after_counts"] == after.counts
    assert isinstance(data["normalization"]["changes"], list)
    assert data["unsupported_capabilities"]
