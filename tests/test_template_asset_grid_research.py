"""TASK_DOC_011 — 真实模板资产验证测试。

覆盖任务书要求的四项验证：
1. 标题结构（TemplateDefinition 的 heading/body/table/page 规则正确）
2. 文档生成（generate_document 基于 Markdown 产出结构正确的 DOCX）
3. 格式规则继承（run_template 将模板规则驱动到 operations 层）
4. 输出文件存在（生成与执行产物落盘且可重新读取）
"""
from __future__ import annotations

from pathlib import Path

from conftest import ROOT, W, paragraph
from document_factory.docx_reader import read_docx
from document_factory.generation import GenerationRequest, generate_document
from document_factory.template_runner import run_template
from document_factory.templates import list_templates, load_template

TEMPLATE_ID = "GRID_RESEARCH_IMPLEMENTATION_PLAN_V1"
RULES = ROOT / "rules/grid_research_implementation_plan_v1.yaml"

# 与 conftest 默认样式“接近但不达标”的坏样式，用于验证模板规则被真正应用。
NORMAL_STYLE = (
    '<w:style w:type="paragraph" w:styleId="Normal" w:default="1">'
    '<w:name w:val="Normal"/></w:style>'
)
BAD_BODY = (
    '<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="正文"/>'
    '<w:pPr><w:ind w:firstLineChars="100" w:hanging="20"/>'
    '<w:spacing w:before="120" w:after="120" w:line="240"/><w:jc w:val="left"/></w:pPr>'
    '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="宋体"/>'
    '<w:sz w:val="20"/></w:rPr></w:style>'
)
BAD_HEADINGS = "".join(
    f'<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/>'
    f'<w:pPr><w:outlineLvl w:val="{i-1}"/></w:pPr><w:rPr>'
    f'<w:rFonts w:eastAsia="宋体" w:eastAsiaTheme="majorEastAsia"/>'
    f'<w:color w:val="2F5597" w:themeColor="accent1"/><w:sz w:val="20"/></w:rPr></w:style>'
    for i in range(1, 4)
)
BAD_SECTION = (
    '<w:sectPr><w:pgSz w:w="10000" w:h="10000"/>'
    '<w:pgMar w:top="1000" w:bottom="1000" w:left="1000" w:right="1000" '
    'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
)

SAMPLE_MD = (
    "# 课题实施方案\n\n"
    "## 研究背景\n\n"
    "本课题围绕新型负荷特性分析开展研究。\n\n"
    "### 具体目标\n\n"
    "建立中长期负荷预测模块。\n"
)


# ---- 1. 标题结构 / 模板定义 ---------------------------------------------

def test_template_definition_structure():
    """模板元数据与 rules 字段对齐真实文档提取的格式事实。"""
    t = load_template(TEMPLATE_ID)
    assert t.id == TEMPLATE_ID
    assert t.name == "科研课题实施方案模板"
    assert t.version == "1.0"
    assert "research" in t.category
    # 标题层级：黑体 16/14/12pt
    assert t.rules.headings["h1"].chinese_font == "黑体"
    assert t.rules.headings["h1"].size_pt == 16
    assert t.rules.headings["h2"].size_pt == 14
    assert t.rules.headings["h3"].size_pt == 12
    assert t.rules.headings["h1"].latin_font == "Times New Roman"
    assert t.rules.headings["h1"].bold is True
    # 正文：仿宋 12pt 1.5倍 首行缩进2字符 两端对齐
    assert t.rules.body.chinese_font == "仿宋"
    assert t.rules.body.font_size_pt == 12
    assert t.rules.body.line_spacing == 1.5
    assert t.rules.body.first_line_indent_chars == 2
    assert t.rules.body.alignment == "both"
    # 表格：表头黑体 / 正文仿宋 / 10.5pt 居中
    assert t.rules.tables.header_font == "黑体"
    assert t.rules.tables.body_font == "仿宋"
    assert t.rules.tables.font_size_pt == 10.5
    assert t.rules.tables.alignment == "center"
    assert t.rules.tables.style_names == ["表格表头", "表格正文"]
    # 页面：A4 纵向 + 页边距 2.8/2.6/2.8/2.6
    assert t.rules.page["page_size"] == "A4"
    assert t.rules.page["orientation"] == "portrait"
    assert t.rules.page["margins_cm"] == {
        "top": 2.8, "bottom": 2.6, "left": 2.8, "right": 2.6
    }
    # 来源指向真实业务文档
    assert "课题4实施方案" in t.metadata.get("source", "")


def test_template_registered_in_default_registry():
    """新模板被 default_registry 自动注册（loader 扫描 templates/*/template.yaml）。"""
    ids = [s.id for s in list_templates()]
    assert TEMPLATE_ID in ids
    # 原 seed 模板仍在，未发生回归
    assert "GRID_TECH_V1_4" in ids


# ---- 2 & 4. 文档生成 + 输出文件存在 ------------------------------------

def test_generation_produces_structurally_correct_docx(tmp_path, monkeypatch):
    """基于该模板从 Markdown 生成结构正确的 Word 文档（标题 + 正文 + 可读取）。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    (tmp_path / "reports").mkdir()
    md_path = tmp_path / "demo.md"
    md_path.write_text(SAMPLE_MD, encoding="utf-8")
    request = GenerationRequest(
        template_id=TEMPLATE_ID,
        content_source="markdown",
        input_data={"file": str(md_path)},
        metadata={"rules_path": str(RULES)},
    )
    result = generate_document(request)

    er = result.execution_result
    assert er is not None
    assert er.template_id == TEMPLATE_ID
    # 模板执行不引入新 ERROR（v1 边界：draft 缺 TOC/编号，before==after）
    assert er.after_counts["ERROR"] <= er.before_counts["ERROR"]
    assert er.errors == []
    # 输出文件存在且为 .docx
    output = Path(result.output_path)
    assert output.is_file()
    assert output.suffix == ".docx"
    # 报告与同名 JSON 旁车存在
    assert Path(result.report_path).is_file()
    assert Path(result.report_path).with_suffix(".json").is_file()
    # DOCX 可重新读取，结构正确：含 H1/H2/H3 标题与正文
    document = read_docx(result.output_path)
    assert document.sha256 == er.output_sha256
    style_ids = {p.style_id for p in document.paragraphs}
    assert "Heading1" in style_ids
    assert "Heading2" in style_ids
    assert "Heading3" in style_ids
    assert "Body" in style_ids
    assert er.source_unchanged is True


# ---- 3. 格式规则继承 ---------------------------------------------------

def test_format_rule_inheritance_via_run_template(make_docx, tmp_path, monkeypatch):
    """run_template 将模板 rules 驱动到 operations 层：坏样式被改写为模板目标值。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    (tmp_path / "reports").mkdir()
    body = "".join(paragraph(f"标题{i}", f"Heading{i}") for i in range(1, 4))
    body += paragraph("正文内容 ABC 123", "Body")
    source = make_docx(
        body,
        styles=NORMAL_STYLE + BAD_BODY + BAD_HEADINGS,
        section=BAD_SECTION,
    )
    output = tmp_path / "output" / "inherit.docx"
    report = tmp_path / "reports" / "inherit.md"
    result = run_template(TEMPLATE_ID, source, output, report, RULES)

    assert result.template_id == TEMPLATE_ID
    assert result.operations_count > 0
    assert "word/styles.xml" in result.changed_parts
    assert "word/document.xml" in result.changed_parts  # section/page 规则被应用
    assert result.errors == []
    # 正文与标题样式被改写
    change_locs = {c["location"] for c in result.changes if c["object_type"] == "Style"}
    assert "Style 正文" in change_locs
    assert "Style heading 1" in change_locs
    # 输出文件存在且可重新读取
    assert Path(result.output_path).is_file()
    assert read_docx(result.output_path).sha256 == result.output_sha256
    # 模板应用不引入新 ERROR
    assert result.after_counts["ERROR"] <= result.before_counts["ERROR"]
