# -*- coding: utf-8 -*-
"""1×1 单格排版容器不得按"首行即表头"处理（TASK_DOC_INTERNAL_TRAINING_CONVERT_002 修复）。

真实内部培训文档中 1×1 表格是提示/要点框（浅蓝/浅灰底纹），既不是内容表也
没有表头语义。确定性规则：

- 1 行 × 1 列（tblGrid 仅 1 个 gridCol）→ 排版容器，首行不自动升级为表头；
- 显式 w:tblHeader 重复表头标记是源文档显式意图，仍优先尊重。
"""
from __future__ import annotations

import zipfile

import pytest
from lxml import etree

from conftest import ROOT, W
from document_factory.conversion import classify_paragraphs, convert_document
from document_factory.docx_reader import read_docx

TEMPLATE_ID = "INTERNAL_TRAINING_DOCUMENT_V1"
RULES = ROOT / "rules" / "internal_training_document_v1.yaml"

SONG = (
    '<w:rFonts w:hint="eastAsia" w:ascii="宋体" w:hAnsi="宋体" '
    'w:eastAsia="宋体" w:cs="宋体"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
)


def flat_p(text: str) -> str:
    return (
        f'<w:p><w:r><w:rPr>{SONG}</w:rPr>'
        f'<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def single_cell_table(text: str, fill: str, *, repeat_header: bool = False) -> str:
    trpr = "<w:trPr><w:tblHeader/></w:trPr>" if repeat_header else ""
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="4000"/></w:tblGrid>'
        f'<w:tr>{trpr}<w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" '
        f'w:fill="{fill}"/></w:tcPr>{flat_p(text)}</w:tc></w:tr></w:tbl>'
    )


def regular_table() -> str:
    def cell(text: str) -> str:
        return f'<w:tc>{flat_p(text)}</w:tc>'

    rows = (
        "<w:tr>" + cell("表头一") + cell("表头二") + "</w:tr>",
        "<w:tr>" + cell("内容一") + cell("内容二") + "</w:tr>",
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="4000"/></w:tblGrid>'
        + "".join(rows) + "</w:tbl>"
    )


@pytest.fixture
def docx_with_containers(make_docx):
    body = "".join([
        flat_p("一、管理要求"),
        flat_p("本章说明表格与提示框的格式要求。"),
        single_cell_table("提示：这是一个浅蓝要点框。", "EAF2F8"),
        single_cell_table("重复表头的单格表（显式标记）。", "F2F2F2",
                          repeat_header=True),
        regular_table(),
    ])
    return make_docx(body=body, styles="")


def _roles_by_cell(document):
    assignments = classify_paragraphs(document, body_style_name="Normal")
    role_by_index = {a.index: a.role for a in assignments}
    result = {}
    for p in document.paragraphs:
        if p.table is not None:
            result[(p.table, p.row)] = role_by_index[p.index]
    return result


def test_single_cell_layout_container_is_body_not_header(docx_with_containers):
    document = read_docx(docx_with_containers)
    roles = _roles_by_cell(document)
    # 表 1：无 tblHeader 的 1×1 容器 → 表体
    assert roles[(1, 1)] == "table_body"
    # 表 2：带显式 tblHeader 的 1×1 表 → 仍按源文档显式意图视为表头
    assert roles[(2, 1)] == "table_header"
    # 表 3：普通 2×2 表首行表头、第二行表体
    assert roles[(3, 1)] == "table_header"
    assert roles[(3, 2)] == "table_body"


def test_conversion_preserves_container_shading_and_alignment(
    docx_with_containers, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)
    result = convert_document(
        docx_with_containers, TEMPLATE_ID,
        "output/converted.docx", "reports/converted.md", rules_path=RULES,
    )
    assert result.content_preserved is True

    with zipfile.ZipFile(result.output_path) as zf:
        root = etree.fromstring(zf.read("word/document.xml"))

    tables = root.findall(f".//{{{W}}}body/{{{W}}}tbl")
    container, explicit, regular = tables

    # 1×1 排版容器：底纹保持源值 EAF2F8；不居中、不加粗。
    tc = container.find(f".//{{{W}}}tc")
    shd = tc.find(f"{{{W}}}tcPr/{{{W}}}shd")
    assert shd is not None and shd.get(f"{{{W}}}fill") == "EAF2F8"
    p = tc.find(f"{{{W}}}p")
    assert p.find(f"{{{W}}}pPr/{{{W}}}jc") is None
    run = next(r for r in p.iter(f"{{{W}}}r")
               if "".join(t.text or "" for t in r.iter(f"{{{W}}}t")).strip())
    assert run.find(f"{{{W}}}rPr/{{{W}}}b") is None

    # 显式 tblHeader 的 1×1 表：按表头规范化（D7D7D7 + 居中 + 加粗）。
    tc2 = explicit.find(f".//{{{W}}}tc")
    assert tc2.find(f"{{{W}}}tcPr/{{{W}}}shd").get(f"{{{W}}}fill") == "D7D7D7"
    p2 = tc2.find(f"{{{W}}}p")
    assert p2.find(f"{{{W}}}pPr/{{{W}}}jc").get(f"{{{W}}}val") == "center"

    # 普通 2×2 表首行：D7D7D7 + 居中 + 加粗。
    first_row = regular.find(f"{{{W}}}tr")
    for hc in first_row.findall(f"{{{W}}}tc"):
        assert hc.find(f"{{{W}}}tcPr/{{{W}}}shd").get(f"{{{W}}}fill") == "D7D7D7"
        hp = hc.find(f"{{{W}}}p")
        assert hp.find(f"{{{W}}}pPr/{{{W}}}jc").get(f"{{{W}}}val") == "center"
        hr = next(r for r in hp.iter(f"{{{W}}}r")
                  if "".join(t.text or "" for t in r.iter(f"{{{W}}}t")).strip())
        assert hr.find(f"{{{W}}}rPr/{{{W}}}b") is not None
