"""TASK_DOC_012 — 默认技术文档规范资产与模板继承机制测试。

覆盖：
1. 默认规范注册、资产去业务化（无项目名称/编号/单位/特定章节）；
2. 格式事实（页面/正文/三级标题/表格/题注/页眉页脚距离）；
3. 业务模板 extends 继承：格式事实一致、业务身份保留；
4. 默认规范驱动 Markdown -> DOCX 生成；
5. 默认规范驱动扁平 DOCX -> 规范 DOCX 转换；
6. rules_include 分片组装、缺失父模板、继承循环、独立路径解析。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import ROOT, W
from document_factory.conversion import convert_document
from document_factory.docx_reader import read_docx
from document_factory.generation import GenerationRequest, generate_document
from document_factory.templates import (
    TemplateSchemaError,
    build_registry,
    list_templates,
    load_template,
    load_template_from_yaml,
)

DEFAULT_ID = "DEFAULT_TECHNICAL_DOCUMENT_V1"
CHILD_ID = "GRID_RESEARCH_IMPLEMENTATION_PLAN_V1"
ASSET_DIR = ROOT / "templates" / "default_technical_document_v1"
RULES = ROOT / "rules" / "default_technical_document_v1.yaml"

# 默认规范任何资产中都不得出现的业务绑定信息。
FORBIDDEN_TOKENS = ("课题4", "课题四", "国家电网", "项目编号")

SAMPLE_MD = (
    "# 项目背景\n\n"
    "这是一份用于验证默认技术文档规范的测试正文，验证正文字体字号行距。\n\n"
    "## 建设目标\n\n"
    "测试内容：验证二级标题格式。\n\n"
    "### 具体指标\n\n"
    "测试内容：验证三级标题格式。\n"
)

# 扁平来稿：宋体五号直接格式 + Word 默认页边距（不符合默认规范）。
SONG = (
    '<w:rFonts w:hint="eastAsia" w:ascii="宋体" w:hAnsi="宋体" '
    'w:eastAsia="宋体" w:cs="宋体"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
)
BAD_SECTION = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800"/></w:sectPr>'
)


def _flat_p(text: str) -> str:
    return (
        f'<w:p><w:r><w:rPr>{SONG}</w:rPr>'
        f'<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def _flat_table() -> str:
    def cell(text: str) -> str:
        return f'<w:tc>{_flat_p(text)}</w:tc>'

    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="4000"/></w:tblGrid>'
        "<w:tr>" + cell("序号") + cell("项目") + "</w:tr>"
        "<w:tr>" + cell("1") + cell("负荷预测") + "</w:tr>"
        "</w:tbl>"
    )


def _style_element(doc, style_id: str):
    return doc.parts["word/styles.xml"].find(
        f".//{{{W}}}style[@{{{W}}}styleId='{style_id}']"
    )


def _font_fact(style_el):
    rfonts = style_el.find(f".//{{{W}}}rFonts")
    size = style_el.find(f".//{{{W}}}sz")
    return (
        rfonts.get(f"{{{W}}}eastAsia") if rfonts is not None else None,
        size.get(f"{{{W}}}val") if size is not None else None,
    )


# --------------------------------------------------------------- 1. 注册/去业务化

def test_default_spec_registered():
    summaries = {s.id: s for s in list_templates()}
    assert DEFAULT_ID in summaries
    t = load_template(DEFAULT_ID)
    assert t.name == "DocumentFactory默认技术文档规范"
    assert "technical_document" in t.category
    assert "default" in t.category
    assert t.extends is None


def test_assets_contain_no_business_information():
    scanned = list(ASSET_DIR.rglob("*.yaml")) + list(ASSET_DIR.rglob("*.md"))
    scanned.append(RULES)
    assert scanned, "默认规范资产文件缺失"
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in text, f"{path} 含业务信息：{token}"


def test_asset_structure_matches_task_layout():
    for relative in (
        "template.yaml",
        "definition/style_definition.yaml",
        "rules/page_rules.yaml",
        "rules/paragraph_rules.yaml",
        "rules/heading_rules.yaml",
        "rules/table_rules.yaml",
        "rules/figure_rules.yaml",
        "examples/default_test.md",
        "validation/VALIDATION_CHECKLIST.md",
    ):
        assert (ASSET_DIR / relative).is_file(), relative
    assert RULES.is_file()


# ----------------------------------------------------------------- 2. 格式事实

def test_default_format_facts():
    t = load_template(DEFAULT_ID)
    # 页面
    assert t.rules.page["page_size"] == "A4"
    assert t.rules.page["orientation"] == "portrait"
    assert t.rules.page["margins_cm"] == {
        "top": 2.8, "bottom": 2.6, "left": 2.8, "right": 2.6
    }
    # 正文
    body = t.rules.body
    assert (body.chinese_font, body.latin_font, body.font_size_pt) == (
        "仿宋", "Times New Roman", 12
    )
    assert body.line_spacing == 1.5
    assert body.first_line_indent_chars == 2
    assert body.alignment == "both"
    # 三级标题：黑体 16/14/12
    for level, size in (("h1", 16), ("h2", 14), ("h3", 12)):
        h = t.rules.headings[level]
        assert h.chinese_font == "黑体"
        assert h.latin_font == "Times New Roman"
        assert h.size_pt == size
        assert h.bold is True
        assert h.alignment == "left"
    # 表格
    table = t.rules.tables
    assert (table.header_font, table.body_font, table.font_size_pt) == (
        "黑体", "仿宋", 10.5
    )
    assert table.alignment == "center"
    assert table.style_names == ["表格表头", "表格正文"]


def test_figure_and_header_footer_facts_are_abstract_assets():
    """题注/页眉页脚为去业务化的资产层事实（Runner v1 不执行）。"""
    definition = (
        ASSET_DIR / "definition" / "style_definition.yaml"
    ).read_text(encoding="utf-8")
    assert "business_defined" in definition          # 页眉文本不固定
    assert "{prefix}{chapter}-{sequence} {title}" in definition
    assert "header_distance_cm: 1.4" in definition
    assert "footer_distance_cm: 1.4" in definition


# ------------------------------------------------------------------- 3. 继承

def test_business_template_extends_default_with_identical_format_facts():
    parent = load_template(DEFAULT_ID)
    child = load_template(CHILD_ID)
    assert child.extends == DEFAULT_ID
    # 格式事实逐项一致（继承所得）
    assert child.rules.body == parent.rules.body
    assert child.rules.headings == parent.rules.headings
    assert child.rules.tables == parent.rules.tables
    assert child.rules.page == parent.rules.page
    assert child.rules.font_aliases == parent.rules.font_aliases
    # 业务身份保留
    assert child.id == CHILD_ID
    assert child.id != DEFAULT_ID
    assert child.name == "科研课题实施方案模板"
    assert child.category == ["report", "research"]
    assert "课题4" in child.metadata["source"]
    assert child.metadata["rule_file"] == (
        "rules/grid_research_implementation_plan_v1.yaml"
    )
    assert child.metadata["kind"] == "business_extension"
    # 子模板文件不再内嵌重复 rules，只声明 extends
    child_yaml = (
        ROOT / "templates" / "grid_research_implementation_plan_v1" / "template.yaml"
    ).read_text(encoding="utf-8")
    assert "extends: DEFAULT_TECHNICAL_DOCUMENT_V1" in child_yaml


# ------------------------------------------------------- 4. 默认规范驱动生成

def test_default_spec_drives_markdown_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    (tmp_path / "reports").mkdir()
    md_path = tmp_path / "default_test.md"
    md_path.write_text(SAMPLE_MD, encoding="utf-8")
    request = GenerationRequest(
        template_id=DEFAULT_ID,
        content_source="markdown",
        input_data={"file": str(md_path)},
        metadata={"rules_path": str(RULES)},
    )
    result = generate_document(request)
    er = result.execution_result
    assert er is not None
    assert er.errors == []

    doc = read_docx(result.output_path)
    style_ids = {p.style_id for p in doc.paragraphs}
    assert {"Heading1", "Heading2", "Heading3", "Body"} <= style_ids

    # 正文：仿宋 12pt（sz=24 半磅）；H1：黑体 16pt（sz=32）
    body_font, body_size = _font_fact(_style_element(doc, "Body"))
    assert body_font == "仿宋"
    assert body_size == "24"
    h1_font, h1_size = _font_fact(_style_element(doc, "Heading1"))
    assert h1_font == "黑体"
    assert h1_size == "32"
    h3_font, h3_size = _font_fact(_style_element(doc, "Heading3"))
    assert h3_font == "黑体"
    assert h3_size == "24"

    # 页面：2.8/2.6/2.8/2.6 cm -> 1587/1474/1587/1474 twips
    pg_mar = doc.parts["word/document.xml"].find(f".//{{{W}}}pgMar")
    assert pg_mar is not None
    assert (
        pg_mar.get(f"{{{W}}}top"), pg_mar.get(f"{{{W}}}bottom"),
        pg_mar.get(f"{{{W}}}left"), pg_mar.get(f"{{{W}}}right"),
    ) == ("1587", "1474", "1587", "1474")


# ------------------------------------------------------- 5. 默认规范驱动转换

def test_default_spec_drives_flat_docx_conversion(make_docx, tmp_path, monkeypatch):
    body = "".join([
        _flat_p("一、项目背景"),
        _flat_p("本段落用于验证扁平来稿被默认规范转换为仿宋正文，内容逐字保留。"),
        _flat_p("（一）建设目标"),
        _flat_p("验证手工编号标题被识别并改写为规范标题样式。"),
        _flat_table(),
    ])
    source = make_docx(body=body, styles="", section=BAD_SECTION)

    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    (tmp_path / "reports").mkdir()
    result = convert_document(
        source, DEFAULT_ID, "output/converted.docx", "reports/conversion.md",
        rules_path=RULES,
    )
    assert Path(result.output_path).is_file()
    assert result.after_counts["ERROR"] <= result.before_counts["ERROR"]

    doc = read_docx(result.output_path)
    # 脚手架样式：正文仿宋小四(24)、标题黑体、表头黑体五号(21)、表体仿宋
    body_font, body_size = _font_fact(_style_element(doc, "DFBody"))
    assert body_font == "仿宋"
    assert body_size == "24"
    header_font, header_size = _font_fact(_style_element(doc, "DFTableHeader"))
    assert header_font == "黑体"
    assert header_size == "21"
    table_body_font, _ = _font_fact(_style_element(doc, "DFTableBody"))
    assert table_body_font == "仿宋"
    h1_font, _ = _font_fact(_style_element(doc, "DFHeading1"))
    assert h1_font == "黑体"


# ------------------------------------------- 6. 继承机制：缺失父/循环/独立解析

MINIMAL_TEMPLATE = """\
id: {tid}
name: {tid} 模板
version: "1.0"
category: [report]
description: 继承机制测试模板
{extends_line}rules:
  page:
    page_size: A4
    orientation: portrait
    margins_cm: {{top: 2.8, bottom: 2.6, left: 2.8, right: 2.6}}
  body:
    style_name: 正文
    chinese_font: 仿宋
    latin_font: Times New Roman
    font_size_pt: 12
    first_line_indent_chars: 2
    line_spacing: 1.5
    space_before_pt: 0
    space_after_pt: 0
    alignment: both
  headings: {{}}
"""


def _write_template(root: Path, tid: str, extends: str | None = None) -> Path:
    directory = root / tid.lower()
    directory.mkdir(parents=True, exist_ok=True)
    extends_line = f"extends: {extends}\n" if extends else ""
    (directory / "template.yaml").write_text(
        MINIMAL_TEMPLATE.format(tid=tid, extends_line=extends_line),
        encoding="utf-8",
    )
    return directory


def test_missing_parent_raises(tmp_path):
    root = tmp_path / "templates"
    _write_template(root, "CHILD", extends="GHOST_PARENT")
    with pytest.raises(TemplateSchemaError, match="父模板"):
        build_registry(root)


def test_inheritance_cycle_raises(tmp_path):
    root = tmp_path / "templates"
    _write_template(root, "ALPHA", extends="BETA")
    _write_template(root, "BETA", extends="ALPHA")
    with pytest.raises(TemplateSchemaError, match="循环"):
        build_registry(root)


def test_standalone_yaml_resolves_sibling_parent(tmp_path):
    root = tmp_path / "templates"
    child_dir = _write_template(root, "CHILD", extends="PARENT")
    _write_template(root, "PARENT")
    definition = load_template_from_yaml(child_dir / "template.yaml")
    assert definition.id == "CHILD"
    assert definition.extends == "PARENT"
    # 父模板的 rules 经继承合并可用
    assert definition.rules.body.chinese_font == "仿宋"


def test_child_override_wins_over_parent(tmp_path):
    root = tmp_path / "templates"
    _write_template(root, "PARENT")
    child_dir = _write_template(root, "CHILD", extends="PARENT")
    # 子模板内联 rules 覆盖正文字号（子覆盖父）
    child_yaml = (child_dir / "template.yaml").read_text(encoding="utf-8")
    (child_dir / "template.yaml").write_text(
        child_yaml.replace("font_size_pt: 12", "font_size_pt: 14", 1),
        encoding="utf-8",
    )
    registry = build_registry(root)
    assert registry.get_template("CHILD").rules.body.font_size_pt == 14
    assert registry.get_template("PARENT").rules.body.font_size_pt == 12
