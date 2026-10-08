# -*- coding: utf-8 -*-
"""TASK_DOC_STYLE_BINDING_001: dedicated paragraph-style binding tests.

Covers the eleven required scenarios from the task book:
unstyled body, explicit Normal body, run-level 宋体 override, regular table
header/body, body-polluted table cells, pStyle-less tables, MCP default
preset + grid compatibility, content integrity and idempotency. Additional
tests pin the conservative caption fix, the centered table variant and the
no-basedOn isolation of created table styles.
"""
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from document_factory import mcp_server
from document_factory.docx_reader import NS, W, read_docx
from document_factory.normalizer import normalize
from document_factory.style_resolver import StyleResolver
from conftest import ROOT

DEFAULT_RULES = ROOT / "rules/default_technical_document_v1.yaml"
GRID_RULES = ROOT / "rules/grid_tech_v1_4.yaml"

NORMAL_STYLE = (
    '<w:style w:type="paragraph" w:styleId="Normal" w:default="1">'
    '<w:name w:val="Normal"/>'
    '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>'
    '<w:sz w:val="21"/></w:rPr></w:style>'
)
HEADING1 = (
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="黑体"/>'
    '<w:b/><w:color w:val="000000"/><w:sz w:val="32"/></w:rPr></w:style>'
)
BODY_STYLE = (
    '<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="正文"/></w:style>'
)
SECTION = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1587" w:bottom="1474" w:left="1587" w:right="1474" '
    'w:header="794" w:footer="794"/></w:sectPr>'
)

LONG_BODY = (
    "本系统采用模块化设计，覆盖数据采集、状态监测与远程通信三类核心组件，"
    "所有接口均满足电力监控系统安全防护的相关要求，System uses ABC modules v2.0。"
)
SECOND_BODY = "系统在试运行期间保持稳定，采样与通信链路均未出现中断，availability 达到 99.99%。"


def p(text, style=None, ppr="", rpr=""):
    """Paragraph helper; style=None omits w:pStyle entirely."""
    p_style = f'<w:pStyle w:val="{style}"/>' if style is not None else ""
    run_rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return (
        f'<w:p><w:pPr>{p_style}{ppr}</w:pPr>'
        f'<w:r>{run_rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def table_xml(*rows_xml):
    grid = '<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="3000"/></w:tblGrid>'
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/></w:tblPr>'
        + grid + "".join(rows_xml) + "</w:tbl>"
    )


def row(cell_a, cell_b, header=False):
    tag = "tr"
    head = '<w:trPr><w:tblHeader/></w:trPr>' if header else ""
    return (
        f'<w:{tag}>{head}<w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr>{cell_a}</w:tc>'
        f'<w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/></w:tcPr>{cell_b}</w:tc></w:{tag}>'
    )


def build(tmp_path, body, *, styles=NORMAL_STYLE + HEADING1, name="sample.docx"):
    path = tmp_path / name
    parts = {
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}{SECTION}</w:body></w:document>',
        "word/styles.xml": f'<w:styles xmlns:w="{W}">{styles}</w:styles>',
        "word/settings.xml": f'<w:settings xmlns:w="{W}"/>',
    }
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


def find_para(document, prefix, table=None):
    for paragraph in document.paragraphs:
        if paragraph.part != "word/document.xml":
            continue
        if table is not None and paragraph.table != table:
            continue
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    raise AssertionError(f"paragraph not found: {prefix}")


def style_element(document, name):
    values = document.parts["word/styles.xml"].xpath(
        './w:style[w:name[@w:val=$n]]', n=name, namespaces=NS,
    )
    assert values, f"style not found: {name}"
    return values[0]


def body_with(*paragraphs):
    return p("1 系统概述", "Heading1") + "".join(paragraphs)


# ------------------------------------------------------------------ TEST 1

def test_01_unstyled_body_is_bound_to_created_body_style(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build(tmp_path, body_with(p(LONG_BODY), p(SECOND_BODY)), name="unstyled.docx")
    result = norm(source, tmp_path, name="unstyled")
    document = read_docx(result.output_path)
    paragraph = find_para(document, "本系统采用模块化设计")

    body_style = style_element(document, "正文")
    assert body_style.get(f"{{{W}}}styleId") == "DFBody"
    assert paragraph.style_id == "DFBody"
    assert paragraph.properties["pStyle"] == "DFBody"

    # Effective run format comes from the bound style: 仿宋 / TNR / 12pt.
    run = next(r for r in paragraph.runs if r.text.strip())
    effective = StyleResolver(document).run(paragraph, run)
    assert effective["rFonts"]["eastAsia"] == "仿宋"
    assert effective["rFonts"]["ascii"] == "Times New Roman"
    assert effective["rFonts"]["hAnsi"] == "Times New Roman"
    assert effective["sz"] == "24"

    assert paragraph.properties["ind"] == {"firstLineChars": "200"}
    assert paragraph.properties["spacing"]["line"] == "360"
    assert paragraph.properties["spacing"]["lineRule"] == "auto"
    assert paragraph.properties["jc"] == "both"

    binding = result.normalization_stats["style_binding"]
    assert binding["body_style_created"] == 1
    assert binding["unstyled_body_detected_count"] == 2
    assert binding["unstyled_body_bound_count"] == 2
    assert binding["body_style_bound_count"] == 2


# ------------------------------------------------------------------ TEST 2

def test_02_explicit_normal_body_is_rebound(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build(tmp_path, body_with(p(LONG_BODY, style="Normal")), name="normal.docx")
    result = norm(source, tmp_path, name="normal")
    document = read_docx(result.output_path)
    paragraph = find_para(document, "本系统采用模块化设计")
    assert paragraph.style_id == "DFBody"
    # The original Normal style must not have been rewritten into 正文.
    normal_style = document.parts["word/styles.xml"].xpath(
        './w:style[@w:styleId="Normal"]/w:name', namespaces=NS
    )
    assert normal_style[0].get(f"{{{W}}}val") == "Normal"
    binding = result.normalization_stats["style_binding"]
    objects = result.normalization_stats["objects"]
    assert objects["body_safe_normal_paragraphs"] == 1
    assert binding["body_style_bound_count"] == 1
    assert binding.get("unstyled_body_detected_count", 0) == 0


# ------------------------------------------------------------------ TEST 3

def test_03_run_direct_song_font_is_repaired_and_bold_kept(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = build(
        tmp_path,
        body_with(p(
            LONG_BODY, style="Body",
            rpr='<w:rFonts w:eastAsia="宋体" w:ascii="Arial"/><w:b/>',
        )),
        styles=NORMAL_STYLE + HEADING1 + BODY_STYLE,
        name="directfont.docx",
    )
    result = norm(source, tmp_path, name="directfont")
    document = read_docx(result.output_path)
    paragraph = find_para(document, "本系统采用模块化设计")
    run = next(r for r in paragraph.runs if r.text.strip())
    # Effective CN font must be 仿宋 even though the run forced 宋体.
    assert run.properties["rFonts"]["eastAsia"] == "仿宋"
    assert run.properties["rFonts"]["ascii"] == "Times New Roman"
    effective = StyleResolver(document).run(paragraph, run)
    assert effective["rFonts"]["eastAsia"] == "仿宋"
    assert effective["sz"] == "24"
    # Bold is content-neutral emphasis and must survive.
    assert run.properties["b"] is True
    assert effective["b"] is True
    assert result.normalization_stats["style_binding"]["direct_font_override_repaired_count"] >= 2
    assert run.text == LONG_BODY


# ----------------------------------------- TEST 4 / 5 / 7 (bound table)

def test_04_05_07_regular_table_without_pstyle_is_bound_and_zero_indented(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = table_xml(
        row(p("参数名称"), p("取值"), header=True),
        row(p("额定电压"), p("AC 220V")),
        row(p("额定频率 Hz"), p("50")),
    )
    source = build(
        tmp_path,
        body_with(p("表 3-1 关键参数一览"), table),
        name="table.docx",
    )
    result = norm(source, tmp_path, name="table")
    document = read_docx(result.output_path)

    header_style = style_element(document, "表格表头")
    body_style = style_element(document, "表格正文")
    center_style = style_element(document, "表格正文-居中")
    # Created table styles must stand alone: no basedOn chain at all.
    for element in (header_style, body_style, center_style):
        assert element.find("w:basedOn", NS) is None
        assert element.find("w:pPr/w:ind", NS) is not None
        assert element.find("w:rPr/w:rFonts", NS) is not None
        assert element.find("w:rPr/w:sz", NS).get(f"{{{W}}}val") == "21"

    header = find_para(document, "参数名称", table=1)
    body_cell = find_para(document, "额定电压", table=1)
    assert header.style_id == "DFTableHeader"
    assert header.properties["pStyle"] == "DFTableHeader"
    assert body_cell.style_id == "DFTableBody"

    # All table indents are explicitly zero with no *Chars remnants.
    for paragraph in (header, body_cell):
        ind = paragraph.properties["ind"]
        assert ind == {"firstLine": "0", "left": "0", "right": "0"}
        spacing = paragraph.properties["spacing"]
        assert spacing["before"] == "0" and spacing["after"] == "0"
        assert spacing["line"] == "240" and spacing["lineRule"] == "auto"
        raw = etree.tostring(paragraph.element, encoding="unicode")
        for token in ("firstLineChars", "hangingChars", "leftChars", "rightChars"):
            assert token not in raw

    header_run = next(r for r in header.runs if r.text.strip())
    body_run = next(r for r in body_cell.runs if r.text.strip())
    resolver = StyleResolver(document)
    assert resolver.run(header, header_run)["rFonts"]["eastAsia"] == "黑体"
    assert resolver.run(header, header_run)["rFonts"]["ascii"] == "Times New Roman"
    assert resolver.run(header, header_run)["sz"] == "21"
    assert resolver.run(body_cell, body_run)["rFonts"]["eastAsia"] == "仿宋"
    assert resolver.run(body_cell, body_run)["sz"] == "21"
    assert header.properties["jc"] == "center"
    assert body_cell.properties["jc"] == "start"

    binding = result.normalization_stats["style_binding"]
    assert binding["table_header_style_created"] == 1
    assert binding["table_body_style_created"] == 1
    assert binding["table_center_style_created"] == 1
    assert binding["table_header_bound_count"] == 2
    assert binding["table_body_bound_count"] == 4
    assert binding["table_indent_repaired_count"] == 6


# ------------------------------------------------------------------ TEST 6

def test_06_body_polluted_table_cell_is_rebound_and_indent_cleared(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    polluted = p(
        "额定电压", style="Body",
        ppr='<w:ind w:firstLineChars="200"/><w:spacing w:line="360" w:lineRule="auto"/>',
    )
    table = table_xml(
        row(p("参数名称"), p("取值"), header=True),
        row(f"<w:tc><w:tcPr><w:tcW w:w='2000' w:type='dxa'/></w:tcPr>{polluted}</w:tc>",
            "<w:tc><w:tcPr><w:tcW w:w='3000' w:type='dxa'/></w:tcPr>"
            + p("AC 220V") + "</w:tc>"),
    )
    source = build(
        tmp_path,
        body_with(p("表 3-1 关键参数一览"), table),
        styles=NORMAL_STYLE + HEADING1 + BODY_STYLE,
        name="polluted.docx",
    )
    result = norm(source, tmp_path, name="polluted")
    document = read_docx(result.output_path)
    cell = find_para(document, "额定电压", table=1)
    assert cell.style_id == "DFTableBody"
    assert cell.properties["pStyle"] != "Body"
    assert cell.properties["ind"] == {"firstLine": "0", "left": "0", "right": "0"}
    raw = etree.tostring(cell.element, encoding="unicode")
    assert "firstLineChars" not in raw
    binding = result.normalization_stats["style_binding"]
    assert binding["table_body_bound_count"] >= 1
    assert binding["table_indent_repaired_count"] >= 1


# --------------------------------------- center variant + caption precision

def test_center_variant_is_used_only_for_short_explicit_centered_cells(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    short_center = p("50", ppr='<w:jc w:val="center"/>')
    long_center = p("这是一段较长的居中说明文字，不应当被归入居中表体样式。", ppr='<w:jc w:val="center"/>')
    left_cell = p("AC 220V")
    table = table_xml(
        row(p("参数名称"), p("取值"), header=True),
        row(f"<w:tc><w:tcPr><w:tcW w:w='2000' w:type='dxa'/></w:tcPr>{short_center}</w:tc>",
            f"<w:tc><w:tcPr><w:tcW w:w='3000' w:type='dxa'/></w:tcPr>{left_cell}</w:tc>"),
        row(f"<w:tc><w:tcPr><w:tcW w:w='2000' w:type='dxa'/></w:tcPr>{long_center}</w:tc>",
            f"<w:tc><w:tcPr><w:tcW w:w='3000' w:type='dxa'/></w:tcPr>{p('备注')}</w:tc>"),
    )
    source = build(tmp_path, body_with(table), name="center.docx")
    result = norm(source, tmp_path, name="center")
    document = read_docx(result.output_path)
    assert find_para(document, "50", table=1).style_id == "DFTableBodyCenter"
    assert find_para(document, "这是一段较长的居中说明文字", table=1).style_id == "DFTableBody"
    assert find_para(document, "AC 220V", table=1).style_id == "DFTableBody"
    assert result.normalization_stats["style_binding"]["table_center_bound_count"] == 1


def test_caption_pattern_does_not_swallow_body_sentences(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = body_with(
        p("图3-1显示，2021—2025年全省最大负荷增长42.7%，明显快于平均负荷，"
          "这类句首引用是正文而不是图题，System v2。"),
        p("图 3-2 负荷年度对比图"),
    )
    source = build(tmp_path, body, name="caption_precision.docx")
    result = norm(source, tmp_path, name="caption_precision")
    document = read_docx(result.output_path)
    sentence = find_para(document, "图3-1显示")
    caption = find_para(document, "图 3-2")
    assert sentence.style_id == "DFBody"
    assert result.normalization_stats["objects"]["body_unstyled_paragraphs"] >= 1
    # Captions keep their pStyle (no dedicated caption style exists in V1.4).
    assert caption.style_id == "Normal"
    assert caption.properties["jc"] == "center"
    assert result.normalization_stats["objects"]["caption_paragraphs"] == 1


# -------------------------------------------------------------- MCP tests

def _cleanup(payload):
    for item in payload.get("deliverables", []):
        path = Path(item["path"])
        if path.exists():
            path.unlink()
        json_path = path.with_suffix(".json")
        if json_path.exists():
            json_path.unlink()


def test_08_mcp_default_preset_matches_explicit_default(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    source = build(
        tmp_path,
        body_with(p(LONG_BODY), table_xml(
            row(p("参数名称"), p("取值"), header=True),
            row(p("额定电压"), p("AC 220V")),
        )),
        name="mcp default.docx",
    )
    default_payload = explicit_payload = None
    try:
        default_payload = mcp_server.format_document(str(source))
        explicit_payload = mcp_server.format_document(
            str(source), preset="default_technical_document_v1"
        )
        assert mcp_server.DEFAULT_PRESET == "default_technical_document_v1"
        assert default_payload["preset"] == "default_technical_document_v1"
        assert explicit_payload["preset"] == "default_technical_document_v1"
        assert default_payload["output_path"] == explicit_payload["output_path"]
        assert Path(default_payload["output_path"]).read_bytes() == Path(explicit_payload["output_path"]).read_bytes()
        sb = default_payload["normalization_stats"]["style_binding"]
        assert sb["body_style_created"] == 1
        assert sb["table_header_bound_count"] == 2
        assert len(json.dumps(default_payload, ensure_ascii=False)) < 10_000
    finally:
        if default_payload:
            _cleanup(default_payload)
        if explicit_payload:
            _cleanup(explicit_payload)


def test_09_grid_preset_still_callable_explicitly(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    source = build(tmp_path, body_with(p(LONG_BODY)), name="mcp grid.docx")
    payload = None
    try:
        payload = mcp_server.format_document(str(source), preset="grid_tech_v1_4")
        assert payload["preset"] == "grid_tech_v1_4"
        assert payload["source_unchanged"] is True
        assert Path(payload["output_path"]).is_file()
        assert all(value == 0 for value in payload["normalization_stats"]["style_binding"].values())
    finally:
        if payload:
            _cleanup(payload)


# ------------------------------------------------ integrity + idempotency

def test_10_content_integrity_gate_passes_after_binding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = table_xml(
        row(p("参数名称"), p("取值"), header=True),
        row(p("额定电压"), p("AC 220V")),
    )
    source = build(
        tmp_path,
        body_with(p(LONG_BODY), p("表 3-1 关键参数一览"), table),
        name="integrity.docx",
    )
    result = norm(source, tmp_path, name="integrity")
    integrity = result.content_integrity
    assert integrity["status"] == "PASS"
    for key in (
        "visible_text_equal", "run_text_equal", "table_cell_text_equal",
        "table_structure_equal", "field_instructions_equal", "hyperlink_text_equal",
        "header_footer_text_equal", "relationships_equal", "media_sha256_equal",
    ):
        assert integrity[key] is True
    # Formatting-only ZIP parts changed.
    assert set(integrity["changed_zip_parts"]) <= {"word/document.xml", "word/styles.xml"}


def test_11_binding_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = table_xml(
        row(p("参数名称"), p("取值"), header=True),
        row(p("额定电压"), p("AC 220V")),
    )
    source = build(
        tmp_path,
        body_with(p(LONG_BODY), p("表 3-1 关键参数一览"), table),
        name="idempotent.docx",
    )
    first = norm(source, tmp_path, name="first")
    assert first.changes, "first run should create and bind styles"
    second = norm(first.output_path, tmp_path, name="second")
    assert second.changes == []
    assert second.input_sha256 == second.output_sha256
    assert first.output_sha256 == second.output_sha256


# --------------------------------------- existing chain isolation + Normal

def test_existing_table_style_based_on_body_chain_is_broken(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    styles = (
        NORMAL_STYLE + HEADING1 + BODY_STYLE +
        '<w:style w:type="paragraph" w:styleId="TableHeader"><w:name w:val="表格表头"/>'
        '<w:basedOn w:val="Body"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="TableBody"><w:name w:val="表格正文"/>'
        '<w:basedOn w:val="Body"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="TableCenter"><w:name w:val="表格正文-居中"/>'
        '<w:basedOn w:val="Body"/></w:style>'
    )
    table = table_xml(
        row(p("参数名称", style="TableHeader"), p("取值", style="TableHeader"), header=True),
        row(p("额定电压", style="TableBody"), p("AC 220V", style="TableBody")),
    )
    source = build(
        tmp_path, body_with(table), styles=styles, name="chain.docx",
    )
    result = norm(source, tmp_path, name="chain")
    document = read_docx(result.output_path)
    for name in ("表格表头", "表格正文", "表格正文-居中"):
        element = style_element(document, name)
        assert element.find("w:basedOn", NS) is None
    assert any(change["property"] == "style_based_on" for change in result.changes)
    # 正文/Normal styles themselves keep their identity.
    assert style_element(document, "正文") is not None
    normal = document.parts["word/styles.xml"].xpath(
        './w:style[@w:styleId="Normal"]', namespaces=NS
    )
    assert normal and normal[0].find("w:name", NS).get(f"{{{W}}}val") == "Normal"
