"""TASK_DOC_013: Word -> Word 格式转换流水线测试。

覆盖任务要求的四个验收测试：
1. 普通（扁平、直接格式）DOCX 可输入并成功输出规范 DOCX，正文逐字不变；
2. 字体转换：宋体 -> 仿宋（含字号修正）；
3. 普通文本手工编号标题 -> Heading 样式（DFHeadingN / outlineLvl / 黑体）；
4. 生成 Markdown + JSON 审核报告，修改逐条可追踪。

另含输入边界、Analyzer 画像、CLI convert 的测试。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import ROOT, W
from document_factory.analyzer import analyze_document
from document_factory.cli import main
from document_factory.conversion import DocumentInputProvider, convert_document
from document_factory.docx_reader import read_docx, sha256
from document_factory.models import DocumentFactoryError
from document_factory.style_resolver import StyleResolver

TEMPLATE_ID = "GRID_RESEARCH_IMPLEMENTATION_PLAN_V1"
RULES = ROOT / "rules" / "grid_research_implementation_plan_v1.yaml"

# 扁平文档统一 run 直接格式：宋体 五号(10.5pt)——模拟"只有 Normal 样式、
# 所有格式直接堆在 run 上"的真实来稿。
SONG = (
    '<w:rFonts w:hint="eastAsia" w:ascii="宋体" w:hAnsi="宋体" '
    'w:eastAsia="宋体" w:cs="宋体"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
)
# Word 默认页边距（上下 2.54cm / 左右 3.17cm），故意不符合模板 2.8/2.6。
BAD_SECTION = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800"/></w:sectPr>'
)

H1 = "一、研究背景"
H2 = "（一）子目标"
H3 = "1.1.1 量化指标"
BODY_1 = "本项目建设背景说明，描述需求来源与意义，为格式转换验证提供足够长度的正文内容。"
BODY_2 = "本子目标描述格式统一后的预期状态与验收方式，不涉及任何内容改写。"


def flat_p(text: str) -> str:
    return (
        f'<w:p><w:r><w:rPr>{SONG}</w:rPr>'
        f'<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def flat_table() -> str:
    def cell(text: str) -> str:
        return f'<w:tc>{flat_p(text)}</w:tc>'

    rows = (
        "<w:tr>" + cell("序号") + cell("项目") + "</w:tr>",
        "<w:tr>" + cell("1") + cell("负荷预测") + "</w:tr>",
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="4000"/></w:tblGrid>'
        + "".join(rows) + "</w:tbl>"
    )


@pytest.fixture
def flat_docx(make_docx):
    body = "".join([
        flat_p(H1), flat_p(BODY_1), flat_p(H2), flat_p(BODY_2), flat_p(H3),
        flat_table(),
    ])
    # styles='' —— 文档只有 Normal 样式，没有任何正文/标题/表格专用样式。
    return make_docx(body=body, styles="", section=BAD_SECTION)


def _convert(tmp_path, monkeypatch, source, output="output/converted.docx",
             report="reports/conversion.md"):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)
    return convert_document(
        source, TEMPLATE_ID, output, report, rules_path=RULES,
    )


# ---------------------------------------------------------------------------
# 输入边界
# ---------------------------------------------------------------------------

def test_input_provider_loads_docx(flat_docx):
    document = DocumentInputProvider().load_docx(flat_docx)
    assert document.tables
    assert any(p.text.strip() for p in document.paragraphs)


def test_input_provider_rejects_missing_and_doc(tmp_path):
    provider = DocumentInputProvider()
    with pytest.raises(DocumentFactoryError, match="不存在"):
        provider.load_docx(tmp_path / "missing.docx")
    legacy = tmp_path / "old.doc"
    legacy.write_bytes(b"fake")
    with pytest.raises(DocumentFactoryError, match="\\.docx"):
        provider.load_docx(legacy)


# ---------------------------------------------------------------------------
# Analyzer：转换前只读画像
# ---------------------------------------------------------------------------

def test_analyzer_profile_describes_flat_doc(flat_docx):
    profile = analyze_document(flat_docx)
    # 5 个正文级段落 + 4 个表格单元格段落
    assert profile.paragraph_count == 9
    assert profile.nonempty_paragraph_count == 9
    assert profile.table_count == 1
    # 扁平文档没有使用任何内置 Heading 样式
    assert profile.heading_structure == {"h1": 0, "h2": 0, "h3": 0}
    assert profile.style_usage == {"Normal": 9}
    # 所有非空 run 的有效字体均为宋体 10.5pt
    assert profile.font_usage == {"宋体/10.5pt": 9}
    margins = profile.section_info[0]["margins_cm"]
    assert margins["top"] == 2.54
    assert margins["left"] == 3.17
    assert profile.source_sha256 == sha256(flat_docx)


# ---------------------------------------------------------------------------
# Test 1：普通 DOCX -> 成功输出规范 DOCX，正文逐字不变
# ---------------------------------------------------------------------------

def test_convert_flat_docx_success(flat_docx, tmp_path, monkeypatch):
    source_hash = sha256(flat_docx)
    original = [p.text for p in read_docx(flat_docx).paragraphs]

    result = _convert(tmp_path, monkeypatch, flat_docx)

    assert Path(result.output_path).is_file()
    output = read_docx(result.output_path)  # 输出必须可重新解析
    assert [p.text for p in output.paragraphs] == original
    assert result.content_preserved is True
    assert result.source_unchanged is True
    assert sha256(flat_docx) == source_hash  # 输入文件绝不被改写
    assert result.input_sha256 != result.output_sha256

    # 六个目标样式全部按需补建；9 个非空段落全部重指派
    assert set(result.created_styles) == {
        "正文", "heading 1", "heading 2", "heading 3", "表格表头", "表格正文",
    }
    assert result.reassignment_count == 9

    # ERROR 必须显著下降；剩余仅限明确不自动处理的手工编号/目录域
    assert result.after_counts["ERROR"] < result.before_counts["ERROR"]


def test_convert_eliminates_formatting_errors(flat_docx, tmp_path, monkeypatch):
    result = _convert(tmp_path, monkeypatch, flat_docx,
                      output="output/c2.docx", report="reports/r2.md")
    from document_factory.lint_engine import lint
    findings = lint(result.output_path, RULES).findings
    error_rules = {f.rule_id for f in findings if f.severity == "ERROR"}
    # 页面/字体/正文/表格类问题全部消除
    assert not error_rules & {
        "PAGE001", "PAGE003", "STYLE001", "STYLE002", "STYLE003",
        "FONT001", "FONT002", "FONT003", "FONT004",
        "BODY001", "BODY002", "TABLE001", "TABLE003",
    }
    # 剩余只可能是手工编号转自动编号 / 目录域——本任务确定性边界不自动处理
    assert error_rules <= {"NUM001", "NUM002", "NUM003", "TOC001", "TOC002"}

    after_profile = analyze_document(result.output_path)
    margins = after_profile.section_info[0]["margins_cm"]
    assert margins["top"] == 2.8
    assert margins["bottom"] == 2.6
    assert margins["left"] == 2.8
    assert margins["right"] == 2.6


# ---------------------------------------------------------------------------
# Test 2：字体转换 宋体 -> 仿宋（Run 直接格式层）
# ---------------------------------------------------------------------------

def test_body_font_song_to_fangsong(flat_docx, tmp_path, monkeypatch):
    result = _convert(tmp_path, monkeypatch, flat_docx,
                      output="output/c3.docx", report="reports/r3.md")
    output = read_docx(result.output_path)
    resolver = StyleResolver(output)
    body = next(p for p in output.paragraphs if p.text.startswith("本项目"))
    assert resolver.name(body.style_id) == "正文"
    effective = resolver.run(body, body.runs[0])
    cn_font, _ = resolver.font(effective, "cn")
    assert cn_font == "仿宋"
    assert effective["sz"] == "24"  # 五号 10.5pt -> 小四 12pt

    # 修改可追踪：该正文段存在宋体 -> 仿宋的 FONT001 记录
    font_changes = [
        c for c in result.changes
        if c["rule"] == "FONT001" and "本项目" in c["location"]
    ]
    assert font_changes
    sample = font_changes[0]
    assert sample["before"]["eastAsia"] == "宋体"
    assert sample["after"]["eastAsia"] == "仿宋"
    assert "Paragraph" in sample["location"]


# ---------------------------------------------------------------------------
# Test 3：普通文本手工编号标题 -> Heading 样式
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("text", "level", "size"), (
    (H1, 1, "32"),   # 三号 16pt
    (H2, 2, "28"),   # 四号 14pt
    (H3, 3, "24"),   # 小四 12pt
))
def test_manual_heading_becomes_heading_style(
    flat_docx, tmp_path, monkeypatch, text, level, size
):
    result = _convert(tmp_path, monkeypatch, flat_docx,
                      output=f"output/h{level}.docx", report=f"reports/h{level}.md")
    output = read_docx(result.output_path)
    resolver = StyleResolver(output)
    heading = next(p for p in output.paragraphs if p.text == text)

    assert resolver.name(heading.style_id) == f"heading {level}"
    assert resolver.heading_level(heading) == level
    effective = resolver.run(heading, heading.runs[0])
    cn_font, _ = resolver.font(effective, "cn")
    assert cn_font == "黑体"
    assert effective["sz"] == size
    assert effective.get("b")  # 标题加粗来自样式定义

    # XML 层存在 outlineLvl（导航窗格可识别）
    styles_root = output.parts["word/styles.xml"]
    style_el = styles_root.find(
        f".//{{{W}}}style[@{{{W}}}styleId='{heading.style_id}']"
    )
    outline = style_el.find(f".//{{{W}}}outlineLvl")
    assert outline is not None
    assert outline.get(f"{{{W}}}val") == str(level - 1)

    # 样式重指派记录可追踪
    reassign = [
        c for c in result.changes
        if c["property"] == "style" and text[:10] in c["location"]
    ]
    assert reassign and reassign[0]["after"] == f"heading {level}"
    assert reassign[0]["before"] == "Normal"


def test_table_paragraphs_get_table_styles(flat_docx, tmp_path, monkeypatch):
    result = _convert(tmp_path, monkeypatch, flat_docx,
                      output="output/t.docx", report="reports/t.md")
    output = read_docx(result.output_path)
    resolver = StyleResolver(output)
    header = next(p for p in output.paragraphs if p.text == "序号")
    data = next(p for p in output.paragraphs if p.text == "负荷预测")
    assert resolver.name(header.style_id) == "表格表头"
    assert resolver.name(data.style_id) == "表格正文"
    h_eff = resolver.run(header, header.runs[0])
    assert resolver.font(h_eff, "cn")[0] == "黑体"
    d_eff = resolver.run(data, data.runs[0])
    assert d_eff["sz"] == "21"  # 表格五号 10.5pt


# ---------------------------------------------------------------------------
# Test 4：审核报告（Markdown + JSON，修改逐条可追踪）
# ---------------------------------------------------------------------------

def test_conversion_report_generated(flat_docx, tmp_path, monkeypatch):
    result = _convert(tmp_path, monkeypatch, flat_docx)
    report_path = Path(result.report_path)
    json_path = report_path.with_suffix(".json")
    assert report_path.is_file()
    assert json_path.is_file()

    md = report_path.read_text(encoding="utf-8")
    for section in (
        "## 1. 文档信息", "## 2. 转换前文档画像", "## 3. 修改统计",
        "## 4. 修改明细（可追踪）", "## 5. 未解决问题", "## 6. 最终状态",
    ):
        assert section in md
    assert f"套用模板 | {TEMPLATE_ID}" in md
    assert "RESULT:" in md
    assert "PASS（转换前后全文文本逐字一致）" in md

    data = json.loads(json_path.read_text(encoding="utf-8"))
    conversion = data["conversion"]
    assert conversion["template_id"] == TEMPLATE_ID
    assert conversion["content_preserved"] is True
    assert conversion["changes"]
    # 每条修改都可追踪：位置 / before / after / rule 齐全
    for change in conversion["changes"]:
        assert change["location"]
        assert "before" in change and "after" in change
        assert change["rule"]
    # 未解决问题非空（手工编号 + 目录域在确定性边界内不自动处理）
    kinds = " ".join(item["kind"] for item in conversion["unresolved"])
    assert "NUM001" in kinds and "TOC001" in kinds
    assert data["change_categories"]


# ---------------------------------------------------------------------------
# CLI convert 冒烟
# ---------------------------------------------------------------------------

def test_cli_convert(flat_docx, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir()
    (tmp_path / "reports").mkdir()
    code = main([
        "convert", "--input", str(flat_docx),
        "--template-id", TEMPLATE_ID,
        "--output", "output/cli.docx",
        "--report", "reports/cli.md",
        "--rules", str(RULES),
    ])
    out = capsys.readouterr().out
    assert "CONTENT_PRESERVED=True" in out
    assert "REASSIGNED=9" in out
    assert (tmp_path / "output/cli.docx").is_file()
    assert (tmp_path / "reports/cli.md").is_file()
    # 真实文档剩余 NUM/TOC ERROR -> FAIL 退出码 1（执行成功不等于全部规则合格）
    assert code == 1
