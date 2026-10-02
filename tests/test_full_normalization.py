# -*- coding: utf-8 -*-
"""TASK_DOC_FULL_NORMALIZATION_001: production-grade normalization coverage.

The fixture below is a synthetic, business-neutral document that reproduces the
four pre-task gaps (page setup, Normal body, captions, regular content tables)
plus every exclusion case the conservative role classifier must respect.
"""
import base64
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree

from document_factory import mcp_server
from document_factory.docx_reader import NS, read_docx
from document_factory.integrity import verify_content_integrity
from document_factory.models import DocumentFactoryError
from document_factory.normalizer import normalize
from conftest import BODY_STYLE, HEADING_STYLES, ROOT, W

DEFAULT_RULES = ROOT / "rules/default_technical_document_v1.yaml"
GRID_RULES = ROOT / "rules/grid_tech_v1_4.yaml"

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
RELS = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rIdImg1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
</Relationships>'''
DRAWING = (
    '<w:p><w:r><w:drawing '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    '<wp:inline><wp:extent cx="100" cy="100"/><wp:docPr id="1" name="Picture 1"/>'
    '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    '<pic:pic><pic:blipFill><a:blip r:embed="rIdImg1"/></pic:blipFill><pic:spPr/>'
    '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
)
TOC_FIELD = (
    r'<w:p><w:fldSimple w:instr="TOC \o &quot;1-2&quot; \h \z \u">'
    r'<w:r><w:t>目录结果行</w:t></w:r></w:fldSimple></w:p>'
)

NORMAL_STYLE = '<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>'
CAPTION_STYLE = '<w:style w:type="paragraph" w:styleId="CaptionZh"><w:name w:val="题注"/><w:rPr/></w:style>'
COVER_STYLE = '<w:style w:type="paragraph" w:styleId="CoverInfo"><w:name w:val="封面信息"/><w:rPr><w:sz w:val="28"/></w:rPr></w:style>'
NAMED_TABLE_STYLES = '''
<w:style w:type="paragraph" w:styleId="TableHeader"><w:name w:val="表格表头"/><w:pPr/><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="黑体"/><w:sz w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableBody"><w:name w:val="表格正文"/><w:pPr/><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="仿宋"/><w:sz w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableCenter"><w:name w:val="表格正文-居中"/><w:pPr/><w:rPr/></w:style>'''
BAD_HEADINGS = ''.join(
    f'<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/>'
    f'<w:pPr><w:outlineLvl w:val="{i-1}"/></w:pPr><w:rPr><w:rFonts w:eastAsia="宋体"/>'
    f'<w:color w:val="2F5597"/><w:sz w:val="20"/></w:rPr></w:style>' for i in (1, 2, 3)
)
FULL_STYLES = NORMAL_STYLE + BODY_STYLE + BAD_HEADINGS + CAPTION_STYLE + COVER_STYLE + NAMED_TABLE_STYLES

BAD_SECTION = (
    '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
    '<w:pgMar w:top="1000" w:bottom="1000" w:left="1000" w:right="1000" '
    'w:header="500" w:footer="500"/></w:sectPr>'
)
LANDSCAPE_SECTION_P = (
    '<w:p><w:pPr><w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
    '<w:pgMar w:top="1587" w:bottom="1474" w:left="1587" w:right="1474" '
    'w:header="794" w:footer="794"/></w:sectPr></w:pPr></w:p>'
)


def para(text, style="Normal", ppr="", rpr=""):
    run_rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{ppr}</w:pPr>'
        f'<w:r>{run_rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


REGULAR_TABLE = (
    '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/></w:tblPr>'
    '<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="3000"/></w:tblGrid>'
    '<w:tr><w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr>'
    + para("参数名称", "Normal", rpr='<w:rFonts w:eastAsia="宋体"/><w:sz w:val="24"/>')
    + '</w:tc><w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/></w:tcPr>'
    + para("取值", "Normal", rpr='<w:rFonts w:eastAsia="宋体"/><w:sz w:val="24"/>')
    + '</w:tc></w:tr>'
    '<w:tr><w:tc>' + para("额定电压", "Normal", rpr='<w:sz w:val="24"/>') + '</w:tc>'
    '<w:tc>' + para("AC 220V", "Normal", rpr='<w:sz w:val="24"/>') + '</w:tc></w:tr>'
    '<w:tr><w:tc>' + para("额定频率 Hz", "Normal", rpr='<w:sz w:val="24"/>') + '</w:tc>'
    '<w:tc>' + para("50", "Normal", rpr='<w:sz w:val="24"/>') + '</w:tc></w:tr>'
    '</w:tbl>'
)
VMERGE_TABLE = (
    '<w:tbl><w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="2000"/></w:tblGrid>'
    '<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr>' + para("合并项", "Normal") + '</w:tc>'
    '<w:tc>' + para("值A", "Normal") + '</w:tc></w:tr>'
    '<w:tr><w:tc><w:tcPr><w:vMerge/></w:tcPr></w:tc>'
    '<w:tc>' + para("值B", "Normal") + '</w:tc></w:tr>'
    '</w:tbl>'
)
COVER_TABLE = (
    '<w:tbl><w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="3000"/></w:tblGrid>'
    '<w:tr><w:tc>' + para("项目名称", "CoverInfo") + '</w:tc>'
    '<w:tc>' + para("某某示范工程", "CoverInfo") + '</w:tc></w:tr></w:tbl>'
)

BODY_XML = "".join([
    para("某项目技术文档", "Normal", '<w:jc w:val="center"/>', '<w:b/><w:sz w:val="36"/>'),
    para("编制单位：某某公司", "Normal"),
    COVER_TABLE,
    TOC_FIELD,
    para("1 系统概述", "Heading1"),
    para("本系统采用模块化设计，包含数据采集、状态监测与远程通信三类核心组件，"
         "所有接口均满足电力监控系统安全防护的相关要求。System uses ABC modules v2.",
         "Normal"),
    para("系统运行稳定。", "Normal"),
    para("（居中的署名行）", "Normal", '<w:jc w:val="center"/>'),
    para("1.1 模拟小标题", "Normal", '<w:ind w:firstLineChars="0"/>', "<w:b/>"),
    DRAWING,
    para("图 2-1 系统总体架构图", "Normal", rpr='<w:sz w:val="24"/>'),
    para("2 功能设计", "Heading1"),
    para("2.1 数据采集", "Heading2", '<w:jc w:val="center"/>'),
    para("2.1.1 采集模块划分", "Heading3"),
    para("本章节描述采集模块的职责划分与部署方式，采集终端通过加密通道与主站通信，"
         "通信协议采用 DL/T 634.5104。", "Body",
         '<w:ind w:firstLineChars="50"/><w:spacing w:before="80" w:after="40" w:line="240"/>'
         '<w:jc w:val="left"/>',
         '<w:rFonts w:eastAsia="宋体" w:ascii="Arial"/><w:sz w:val="20"/>'),
    para("3 关键参数", "Heading1", '<w:keepNext w:val="0"/>',
         '<w:b w:val="0"/><w:color w:val="FF0000"/>'
         '<w:rFonts w:eastAsia="微软雅黑"/><w:sz w:val="20"/>'),
    para("表 3-1 关键参数一览", "Normal", rpr='<w:b/><w:sz w:val="24"/>'),
    REGULAR_TABLE,
    VMERGE_TABLE,
    LANDSCAPE_SECTION_P,
    para("4 附录", "Heading1"),
    para("附录给出测试用例与接线示意，供现场调试人员参考。", "Normal"),
    BAD_SECTION,
])


def build_docx(tmp_path, body=BODY_XML, styles=FULL_STYLES, section="", extra=None, name="comprehensive.docx"):
    path = tmp_path / name
    parts = {
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}{section}</w:body></w:document>',
        "word/styles.xml": f'<w:styles xmlns:w="{W}">{styles}</w:styles>',
        "word/settings.xml": f'<w:settings xmlns:w="{W}"/>',
    }
    parts.update(extra or {})
    with ZipFile(path, "w") as archive:
        for key, value in parts.items():
            archive.writestr(key, value)
    return path


def norm(source, tmp_path, rules=DEFAULT_RULES, name="normalized"):
    return normalize(
        source, rules,
        tmp_path / "output" / f"{name}.docx",
        tmp_path / "reports" / f"{name}.md",
    )


def find_paragraph(document, prefix, table=None):
    for paragraph in document.paragraphs:
        if paragraph.part != "word/document.xml":
            continue
        if table is not None and paragraph.table != table:
            continue
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise AssertionError(f"paragraph not found: {prefix}")


@pytest.fixture
def normalized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build_docx(
        tmp_path,
        extra={"word/_rels/document.xml.rels": RELS, "word/media/image1.png": PNG_BYTES},
    )
    result = norm(source, tmp_path)
    return source, result, read_docx(result.output_path)


# ---------------------------------------------------------------- page (3)

def test_page01_wrong_size_and_margins_are_normalized(normalized):
    source, result, document = normalized
    section = document.sections[-1]
    assert section["size"]["w"] == "11906"
    assert section["size"]["h"] == "16838"
    assert section["size"].get("orient", "portrait") == "portrait"
    assert section["margins"]["top"] == "1587"
    assert section["margins"]["bottom"] == "1474"
    assert section["margins"]["left"] == "1587"
    assert section["margins"]["right"] == "1474"
    section_changes = [c for c in result.changes if c["object_type"] == "Section"]
    assert {c["property"] for c in section_changes} >= {"page_size", "page_margins"}
    assert result.normalization_stats["page"]["sections_normalized"] >= 1


def test_page02_header_footer_distances_are_normalized(normalized):
    _, result, document = normalized
    for section in document.sections:
        assert section["margins"]["header"] == "794"
        assert section["margins"]["footer"] == "794"


def test_page03_landscape_section_is_preserved_and_reported(normalized):
    _, result, document = normalized
    landscape = document.sections[0]
    assert landscape["size"]["orient"] == "landscape"
    assert landscape["size"]["w"] == "16838" and landscape["size"]["h"] == "11906"
    kinds = {item["kind"] for item in result.normalization_stats["warnings"]}
    assert "SKIP_LANDSCAPE_SECTION" in kinds
    assert result.unresolved_counts["SKIP_LANDSCAPE_SECTION"] == 1


# ---------------------------------------------------------------- body (4)

def test_body01_safe_normal_gets_direct_body_format_and_keeps_pstyle(normalized):
    _, result, document = normalized
    paragraph = find_paragraph(document, "本系统采用模块化设计")
    assert paragraph.style_id == "Normal"
    assert paragraph.properties["jc"] == "both"
    assert paragraph.properties["ind"] == {"firstLineChars": "200"}
    spacing = paragraph.properties["spacing"]
    assert spacing["line"] == "360" and spacing["lineRule"] == "auto"
    text_run = next(run for run in paragraph.runs if run.text.strip())
    fonts = text_run.properties["rFonts"]
    assert fonts["eastAsia"] == "仿宋"
    assert fonts["ascii"] == "Times New Roman" and fonts["hAnsi"] == "Times New Roman"
    assert text_run.properties["sz"] == "24"
    assert result.normalization_stats["objects"]["body_safe_normal_paragraphs"] >= 2


def test_body02_normal_content_before_first_h1_is_untouched(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = (
        para("封面之后、一级标题之前的普通长段落，语义属于前置内容，不允许按正文处理。",
             "Normal", rpr='<w:sz w:val="24"/>')
        + para("1 正文章节", "Heading1")
        + para("章内正文应当被规范化为仿宋字体、首行缩进两字符并采用一点五倍行距。",
               "Normal", rpr='<w:sz w:val="24"/>')
    )
    source = build_docx(tmp_path, body=body, styles=NORMAL_STYLE + BODY_STYLE + BAD_HEADINGS, name="front.docx")
    result = norm(source, tmp_path, name="front")
    document = read_docx(result.output_path)
    front = find_paragraph(document, "封面之后")
    assert front.style_id == "Normal"
    assert "jc" not in front.properties and "ind" not in front.properties
    front_run = next(r for r in front.runs if r.text.strip())
    assert "rFonts" not in front_run.properties
    body_p = find_paragraph(document, "章内正文")
    assert body_p.properties["jc"] == "both"
    assert body_p.properties["ind"] == {"firstLineChars": "200"}


def test_body03_toc_field_and_drawing_paragraphs_are_excluded(normalized):
    _, _, document = normalized
    toc_paragraphs = [p for p in document.paragraphs if p.in_toc]
    assert toc_paragraphs and all(p.style_id == "Normal" for p in toc_paragraphs)
    toc = toc_paragraphs[0]
    assert "jc" not in toc.properties and "ind" not in toc.properties
    image_paragraph = next(p for p in document.paragraphs
                           if p.element.find(".//w:drawing", NS) is not None)
    assert "jc" not in image_paragraph.properties
    assert image_paragraph.element.find(".//w:rPr/w:rFonts", NS) is None


def test_body04_centered_and_bold_short_normal_lines_are_excluded(normalized):
    _, _, document = normalized
    centered = find_paragraph(document, "（居中的署名行）")
    assert centered.properties["jc"] == "center"
    bold_line = find_paragraph(document, "1.1 模拟小标题")
    assert "ind" not in bold_line.properties or bold_line.properties["ind"] == {"firstLineChars": "0"}
    bold_run = next(r for r in bold_line.runs if r.text.strip())
    assert "rFonts" not in bold_run.properties


# ------------------------------------------------------------- heading (2)

def test_heading01_styles_get_bold_left_alignment_and_keep_next(normalized):
    _, _, document = normalized
    styles = document.parts["word/styles.xml"]
    for style_id, size in (("Heading1", "32"), ("Heading2", "28"), ("Heading3", "24")):
        style = styles.xpath('./w:style[@w:styleId=$s]', s=style_id, namespaces=NS)[0]
        assert style.find("w:pPr/w:keepNext", NS) is not None
        assert style.find("w:pPr/w:jc", NS).get(f"{{{W}}}val") == "left"
        assert style.find("w:rPr/w:b", NS).get(f"{{{W}}}val") == "1"
        assert style.find("w:rPr/w:sz", NS).get(f"{{{W}}}val") == size
        fonts = style.find("w:rPr/w:rFonts", NS)
        assert fonts.get(f"{{{W}}}eastAsia") == "黑体"
        assert fonts.get(f"{{{W}}}ascii") == "Times New Roman"


def test_heading02_direct_paragraph_and_run_overrides_are_repaired(normalized):
    _, _, document = normalized
    heading = find_paragraph(document, "3 关键参数")
    assert heading.properties["keepNext"] is True
    run = next(r for r in heading.runs if r.text.strip())
    assert run.properties["b"] is True
    assert run.properties["color"] == {"val": "000000"}
    assert run.properties["rFonts"]["eastAsia"] == "黑体"
    assert run.properties["sz"] == "32"


# ------------------------------------------------------------- caption (3)

def test_caption01_pattern_paragraph_is_normalized(normalized):
    _, _, document = normalized
    caption = find_paragraph(document, "图 2-1")
    assert caption.style_id == "Normal"
    assert caption.properties["jc"] == "center"
    assert caption.properties["spacing"]["line"] == "240"
    assert caption.properties["spacing"]["before"] == "120"
    assert caption.properties["spacing"]["after"] == "120"
    run = next(r for r in caption.runs if r.text.strip())
    assert run.properties["rFonts"]["eastAsia"] == "黑体"
    assert run.properties["rFonts"]["ascii"] == "Times New Roman"
    assert run.properties["sz"] == "21"


def test_caption02_style_alias_paragraph_is_normalized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = (
        para("1 正文章节", "Heading1")
        + para("图 1-2 别名样式题注", "CaptionZh", rpr='<w:b/><w:sz w:val="24"/>')
    )
    source = build_docx(tmp_path, body=body, name="caption_alias.docx")
    result = norm(source, tmp_path, name="caption_alias")
    document = read_docx(result.output_path)
    caption = find_paragraph(document, "图 1-2")
    assert caption.style_id == "CaptionZh"
    assert caption.properties["jc"] == "center"
    run = next(r for r in caption.runs if r.text.strip())
    assert run.properties["sz"] == "21"
    assert run.properties["b"] is False
    assert result.normalization_stats["objects"]["caption_paragraphs"] == 1


def test_caption03_caption_text_and_numbering_are_never_modified(normalized):
    source, result, document = normalized
    before = read_docx(source)
    before_captions = [(p.part, p.index, p.text) for p in before.paragraphs
                       if p.text.strip().startswith(("图 2-1", "表 3-1"))]
    after_captions = [(p.part, p.index, p.text) for p in document.paragraphs
                      if p.text.strip().startswith(("图 2-1", "表 3-1"))]
    assert before_captions == after_captions == [
        ("word/document.xml", after_captions[0][1], "图 2-1 系统总体架构图"),
        ("word/document.xml", after_captions[1][1], "表 3-1 关键参数一览"),
    ]


# --------------------------------------------------------------- table (4)

def test_table01_regular_header_and_body_rows_are_normalized(normalized):
    _, result, document = normalized
    header = find_paragraph(document, "参数名称", table=2)
    body_cell = find_paragraph(document, "额定电压", table=2)
    assert header.style_id == "Normal" and body_cell.style_id == "Normal"
    assert header.properties["jc"] == "center"
    assert body_cell.properties["jc"] == "start"
    header_run = next(r for r in header.runs if r.text.strip())
    body_run = next(r for r in body_cell.runs if r.text.strip())
    assert header_run.properties["rFonts"]["eastAsia"] == "黑体"
    assert header_run.properties["b"] is True
    assert header_run.properties["sz"] == "21"
    assert body_run.properties["rFonts"]["eastAsia"] == "仿宋"
    assert body_run.properties["sz"] == "21"
    objects = result.normalization_stats["objects"]
    assert objects["regular_tables"] == 1
    assert objects["table_header_paragraphs"] == 2
    assert objects["table_body_paragraphs"] == 4


def test_table02_cover_table_is_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = (
        para("1 正文章节", "Heading1")
        + COVER_TABLE
        + BAD_SECTION
    )
    source = build_docx(tmp_path, body=body, name="cover.docx")
    result = norm(source, tmp_path, name="cover")
    assert result.unresolved_counts["SKIP_TABLE_COVER"] == 1
    document = read_docx(result.output_path)
    cell = find_paragraph(document, "项目名称", table=1)
    text_run = next(r for r in cell.runs if r.text.strip())
    # Cover styling comes from the 封面信息 style only: no direct repair allowed.
    assert "rFonts" not in text_run.properties and "sz" not in text_run.properties
    from document_factory.style_resolver import StyleResolver
    effective = StyleResolver(document).run(cell, text_run)
    assert effective["sz"] == "28"


def test_table03_vmerge_table_is_skipped_with_warning(normalized):
    source, result, document = normalized
    assert result.unresolved_counts["SKIP_TABLE_COMPLEX"] == 1
    merged = find_paragraph(document, "合并项", table=3)
    assert merged.style_id == "Normal"
    assert "jc" not in merged.properties
    assert document.tables[2].rows[1]["cells"][0]["v_merge"] == "continue"


def test_table04_grid_widths_and_cell_structure_are_untouched(normalized):
    source, result, _ = normalized
    before_xml = ZipFile(source).read("word/document.xml")
    after_xml = ZipFile(result.output_path).read("word/document.xml")
    before_root = etree.fromstring(before_xml)
    after_root = etree.fromstring(after_xml)

    def grid_signature(root):
        tables = root.findall(".//w:tbl", NS)
        regular = tables[1]
        return etree.tostring(regular.find("w:tblGrid", NS))
    assert grid_signature(before_root) == grid_signature(after_root)
    before_doc, after_doc = read_docx(source), read_docx(result.output_path)
    before_table = next(t for t in before_doc.tables if t.index == 2)
    after_table = next(t for t in after_doc.tables if t.index == 2)
    assert [[c["grid_span"] for c in row["cells"]] for row in before_table.rows] == \
           [[c["grid_span"] for c in row["cells"]] for row in after_table.rows]
    assert [len(row["cells"]) for row in before_table.rows] == [2, 2, 2]


# ---------------------------------------------------------- integrity (4)

def test_integrity01_media_sha256_and_relationships_are_preserved(normalized):
    source, result, _ = normalized
    integrity = result.content_integrity
    assert integrity["status"] == "PASS"
    assert integrity["media_file_count"] == 1
    assert integrity["media_sha256_equal"] is True
    assert integrity["relationships_equal"] is True
    with ZipFile(source) as before, ZipFile(result.output_path) as after:
        assert before.read("word/media/image1.png") == after.read("word/media/image1.png")
        assert before.read("word/_rels/document.xml.rels") == after.read("word/_rels/document.xml.rels")
        assert before.read("word/settings.xml") == after.read("word/settings.xml")


def test_integrity02_full_visible_text_sequence_is_unchanged(normalized):
    source, result, after_doc = normalized
    before_doc = read_docx(source)
    assert [(p.part, p.index, p.text) for p in before_doc.paragraphs] == \
           [(p.part, p.index, p.text) for p in after_doc.paragraphs]
    integrity = result.content_integrity
    assert integrity["visible_text_equal"] is True
    assert integrity["run_text_equal"] is True
    assert integrity["table_cell_text_equal"] is True
    assert integrity["field_instructions_equal"] is True
    assert integrity["hyperlink_text_equal"] is True
    assert integrity["header_footer_text_equal"] is True
    assert integrity["paragraph_count_before"] == integrity["paragraph_count_after"]
    assert integrity["table_count_before"] == integrity["table_count_after"]
    assert integrity["section_count_before"] == integrity["section_count_after"]
    assert integrity["drawing_count_before"] == integrity["drawing_count_after"] == 1


def test_integrity03_gate_raises_on_tampered_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build_docx(
        tmp_path,
        body=para("1 正文章节", "Heading1")
        + para("原始正文内容必须与输出完全一致，篡改任何一个字都应触发完整性闸门失败。", "Normal"),
        styles=NORMAL_STYLE + BODY_STYLE + BAD_HEADINGS,
        extra={"word/_rels/document.xml.rels": RELS, "word/media/image1.png": PNG_BYTES},
        name="tamper.docx",
    )
    tampered = tmp_path / "output" / "tampered_out.docx"
    tampered.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as incoming, ZipFile(tampered, "w") as outgoing:
        for info in incoming.infolist():
            payload = incoming.read(info.filename)
            if info.filename == "word/document.xml":
                root = etree.fromstring(payload)
                text_node = root.findall(".//w:t", NS)[1]
                text_node.text = text_node.text.replace("原始", "篡改")
                payload = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
            outgoing.writestr(info, payload)
    with pytest.raises(DocumentFactoryError, match="CONTENT_INTEGRITY_GATE"):
        verify_content_integrity(source, tampered, {"word/document.xml"})


def test_format_effect_gate_four_object_classes_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build_docx(
        tmp_path,
        extra={"word/_rels/document.xml.rels": RELS, "word/media/image1.png": PNG_BYTES},
    )
    first = norm(source, tmp_path, name="first")
    changed_rules = set(first.normalization_stats["rules_applied"])
    # All four previously-unhandled object classes must have actually changed.
    assert {"PAGE001", "PAGE003"} & changed_rules
    assert {"FONT001", "FONT002", "FONT003", "BODY002"} & changed_rules
    assert "CAPTION001" in changed_rules and "CAPTION002" in changed_rules
    assert {"TABLE002", "TABLE003", "TABLE008"} & changed_rules
    assert len(first.changes) > 0
    assert first.content_integrity["status"] == "PASS"
    # Second run must be a no-op.
    second = norm(first.output_path, tmp_path, name="second")
    assert second.changes == []
    assert second.input_sha256 == second.output_sha256
    assert first.output_sha256 == second.output_sha256


# ----------------------------------------------------------------- mcp (1)

def test_mcp01_format_document_returns_stats_and_integrity(tmp_path, monkeypatch):
    # The MCP adapter always writes under PROJECT_ROOT; mirror the stdio setup.
    monkeypatch.chdir(ROOT)
    source = build_docx(
        tmp_path,
        extra={"word/_rels/document.xml.rels": RELS, "word/media/image1.png": PNG_BYTES},
        name="mcp sample.docx",
    )
    payload = None
    try:
        payload = mcp_server.format_document(str(source), "default_technical_document_v1")
        assert payload["source_unchanged"] is True
        assert payload["content_integrity"]["status"] == "PASS"
        assert payload["content_integrity"]["media_file_count"] == 1
        assert payload["content_integrity"]["changed_zip_parts"] == [
            "word/document.xml", "word/styles.xml"
        ]
        stats = payload["normalization_stats"]
        assert stats["page"]["sections_normalized"] >= 1
        assert stats["objects"]["body_safe_normal_paragraphs"] >= 2
        assert stats["objects"]["caption_paragraphs"] == 2
        assert stats["objects"]["regular_tables"] == 1
        assert "SKIP_TABLE_COMPLEX" in payload["unresolved_counts"]
        assert "RESIDUAL_LINT_ERROR" in payload["unresolved_counts"]
        assert Path(payload["output_path"]).is_file()
        assert Path(payload["report_path"]).is_file()
        assert len(json.dumps(payload, ensure_ascii=False)) < 10_000
    finally:
        if payload is not None:
            for item in payload.get("deliverables", []):
                path = Path(item["path"])
                if path.exists():
                    path.unlink()
                json_path = path.with_suffix(".json")
                if json_path.exists():
                    json_path.unlink()


# ------------------------------------------------- grid preset regression (1)

def test_grid_preset_new_behaviors_remain_opted_out(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build_docx(
        tmp_path,
        extra={"word/_rels/document.xml.rels": RELS, "word/media/image1.png": PNG_BYTES},
        name="grid.docx",
    )
    result = norm(source, tmp_path, rules=GRID_RULES, name="grid")
    objects = result.normalization_stats["objects"]
    assert objects.get("body_safe_normal_paragraphs", 0) == 0
    assert objects.get("caption_paragraphs", 0) == 0
    assert objects.get("regular_tables", 0) == 0
    assert objects.get("table_header_paragraphs", 0) == 0
    assert objects.get("table_body_paragraphs", 0) == 0
    rules_applied = set(result.normalization_stats["rules_applied"])
    assert "CAPTION001" not in rules_applied and "CAPTION002" not in rules_applied
    assert not any(change["property"].startswith(("safe_normal_", "table_regular_"))
                   for change in result.changes)
    assert result.content_integrity["status"] == "PASS"

