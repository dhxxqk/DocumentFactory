import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest

from document_factory.cli import main
from document_factory.docx_reader import read_docx, sha256
from document_factory.lint_engine import lint
from document_factory.models import DocumentFactoryError, TemplateApplyResult
from document_factory.template import TemplateProfile, analyze_template, apply_template
from document_factory.template.extractor import extract_style, paragraph_format
from document_factory.style_resolver import StyleResolver
from conftest import NUMBERING, ROOT, SECTION, W, paragraph


TEMPLATE_NORMAL = '''<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/>
<w:pPr><w:ind w:firstLineChars="200"/><w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
<w:rPr><w:rFonts w:eastAsia="仿宋" w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr></w:style>'''
TEMPLATE_STYLES = '''
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:rFonts w:eastAsia="方正小标宋简体" w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="36"/><w:b/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:eastAsia="黑体" w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="32"/><w:b/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:eastAsia="黑体" w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="28"/><w:b/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:rFonts w:eastAsia="黑体" w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/><w:b/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableHeader"><w:name w:val="表格表头"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:rFonts w:eastAsia="黑体" w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="22"/><w:b/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableBody"><w:name w:val="表格正文"/><w:pPr><w:jc w:val="left"/></w:pPr><w:rPr><w:rFonts w:eastAsia="宋体" w:ascii="Arial" w:hAnsi="Arial"/><w:sz w:val="20"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="GridTable"><w:name w:val="网格表"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/></w:tblBorders></w:tblPr><w:tblStylePr w:type="firstRow"><w:rPr><w:b/></w:rPr></w:tblStylePr></w:style>'''

TARGET_NORMAL = '''<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/>
<w:pPr><w:ind w:firstLineChars="0"/><w:spacing w:before="120" w:after="120" w:line="240"/><w:jc w:val="left"/></w:pPr>
<w:rPr><w:rFonts w:eastAsia="宋体" w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="20"/></w:rPr></w:style>'''
TARGET_STYLES = TEMPLATE_STYLES.replace('方正小标宋简体', '宋体').replace('w:sz w:val="36"', 'w:sz w:val="20"').replace('w:eastAsia="黑体"', 'w:eastAsia="宋体"').replace('w:sz w:val="32"', 'w:sz w:val="20"').replace('w:sz w:val="28"', 'w:sz w:val="20"').replace('w:sz w:val="24"', 'w:sz w:val="20"').replace('w:eastAsia="宋体" w:ascii="Arial"', 'w:eastAsia="微软雅黑" w:ascii="Calibri"')


def demo_table(header_style="TableHeader", body_style="TableBody", direct=False):
    run = '<w:rFonts w:eastAsia="微软雅黑" w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="18"/>' if direct else ''
    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="GridTable"/></w:tblPr><w:tblGrid><w:gridCol w:w="3000"/></w:tblGrid>'
        f'<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc>{paragraph("表头 A", header_style, run_properties=run)}</w:tc></w:tr>'
        f'<w:tr><w:tc>{paragraph("内容 B", body_style, run_properties=run)}</w:tc></w:tr></w:tbl>'
    )


def build_template(make_docx):
    body = paragraph("模板标题", "Title") + paragraph("第一章", "Heading1") + paragraph("模板正文", "Normal") + demo_table()
    section = '<w:sectPr><w:headerReference w:type="default" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/><w:footerReference w:type="default" r:id="rId2" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:bottom="1440" w:left="1800" w:right="1800"/><w:pgNumType w:start="1"/></w:sectPr>'
    extra = {
        "word/header1.xml": f'<w:hdr xmlns:w="{W}">{paragraph("页眉", "Normal")}</w:hdr>',
        "word/footer1.xml": f'<w:ftr xmlns:w="{W}"><w:p><w:r><w:fldChar w:fldCharType="begin"/><w:instrText>PAGE</w:instrText><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>',
    }
    return make_docx(body, styles=TEMPLATE_STYLES, numbering=NUMBERING, extra=extra, section=section, normal_style=TEMPLATE_NORMAL)


def build_target(make_docx):
    direct = '<w:jc w:val="right"/>'
    run = '<w:rFonts w:eastAsia="微软雅黑" w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="18"/>'
    body = paragraph("今年建议书", "Title", direct, run) + paragraph("项目概述", "Heading1", direct, run) + paragraph("目标正文 ABC", "Normal", direct, run) + demo_table(direct=True)
    return make_docx(body, styles=TARGET_STYLES, numbering=NUMBERING, normal_style=TARGET_NORMAL)


def test_template_analyzer_profile_round_trip(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    template = build_template(make_docx)
    before = sha256(template)
    profile_path = tmp_path / "reports" / "template_profile.json"
    profile = analyze_template(template, profile_path)
    assert sha256(template) == before
    assert profile.schema_version == "1.0"
    assert profile.roles == {"Normal": "Normal", "Title": "Title", "Heading1": "Heading1", "Heading2": "Heading2", "Heading3": "Heading3"}
    assert len(profile.styles) == 7
    assert profile.styles["Heading1"]["font"]["east_asia"] == "黑体"
    assert profile.styles["Normal"]["font"]["size_pt"] == 12
    assert profile.page["sections"][0]["size"]["name"] == "A4"
    assert profile.headers[0]["paragraph_count"] == 1
    assert profile.footers[0]["field_kinds"] == ["PAGE"]
    assert profile.table_styles["GridTable"]["borders"]["top"]["val"] == "single"
    assert profile.table_defaults["header"]["font"]["east_asia"] == "黑体"
    assert profile.numbering["exists"] is True and "Heading1" in profile.numbering["style_ids"]
    loaded = TemplateProfile.load(profile_path)
    assert loaded.to_dict() == profile.to_dict()
    assert json.loads(profile_path.read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_template_apply_preserves_inputs_and_applies_profile(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    template, target = build_template(make_docx), build_target(make_docx)
    template_hash, target_hash = sha256(template), sha256(target)
    original_text = [p.text for p in read_docx(target).paragraphs if p.part == "word/document.xml"]
    numbering_bytes = ZipFile(target).read("word/numbering.xml")
    result = apply_template(
        template, target,
        tmp_path / "output" / "template" / "result.docx",
        tmp_path / "reports" / "template_apply_report.md",
        ROOT / "rules/grid_tech_v1_4.yaml",
    )
    assert isinstance(result, TemplateApplyResult) and result.status == "PASS"
    assert result.source_unchanged and result.template_unchanged
    assert sha256(template) == template_hash and sha256(target) == target_hash
    output = read_docx(result.output_path)
    assert [p.text for p in output.paragraphs if p.part == "word/document.xml"] == original_text
    assert Path(result.report_path).is_file() and result.validation_mismatches == []
    lint(result.output_path, ROOT / "rules/grid_tech_v1_4.yaml")
    template_profile = analyze_template(template)
    resolver = StyleResolver(output)
    for role in ("Normal", "Title", "Heading1", "Heading2", "Heading3"):
        actual = extract_style(output, resolver, role)
        expected = template_profile.styles[role]
        assert actual["font"] == expected["font"]
    title = next(p for p in output.paragraphs if p.style_id == "Title")
    title_run = resolver.run(title, title.runs[0])
    assert resolver.font(title_run, "cn")[0] == "方正小标宋简体"
    assert title_run["sz"] == "36"
    table_paragraphs = [p for p in output.paragraphs if p.table is not None and p.text.strip()]
    assert paragraph_format(output, resolver, table_paragraphs[0])["font"]["east_asia"] == "黑体"
    assert paragraph_format(output, resolver, table_paragraphs[1])["font"]["east_asia"] == "宋体"
    with ZipFile(result.output_path) as archive:
        assert archive.read("word/numbering.xml") == numbering_bytes


def test_template_apply_rejects_overwrite_and_bad_profile(make_docx, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    template, target = build_template(make_docx), build_target(make_docx)
    protected_target = tmp_path / "output" / "protected.docx"
    protected_target.parent.mkdir()
    shutil.copyfile(target, protected_target)
    with pytest.raises(DocumentFactoryError, match="不得覆盖输入"):
        apply_template(template, protected_target, protected_target, tmp_path / "reports" / "report.md", ROOT / "rules/grid_tech_v1_4.yaml")
    bad = tmp_path / "reports" / "bad.json"
    bad.parent.mkdir()
    bad.write_text('{"schema_version":"2.0"}', encoding="utf-8")
    with pytest.raises(DocumentFactoryError, match="缺少必需字段"):
        TemplateProfile.load(bad)


def test_template_cli_analyze_and_apply(make_docx, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    template, target = build_template(make_docx), build_target(make_docx)
    profile = tmp_path / "reports" / "cli_profile.json"
    assert main(["template", "analyze", str(template), "--output", str(profile)]) == 0
    assert profile.is_file() and "STYLES=7" in capsys.readouterr().out
    output = tmp_path / "output" / "template" / "cli_result.docx"
    report = tmp_path / "reports" / "cli_report.md"
    assert main([
        "template", "apply", "--template", str(template), "--input", str(target),
        "--output", str(output), "--report", str(report), "--rules", str(ROOT / "rules/grid_tech_v1_4.yaml"),
    ]) == 0
    printed = capsys.readouterr().out
    assert output.is_file() and report.is_file()
    assert all(key in printed for key in ("STATUS=PASS", "OUTPUT=", "REPORT=", "MAPPINGS=5", "CHANGED="))
