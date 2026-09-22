"""Unit tests for the shared Formatting Operation Layer."""
from lxml import etree

from document_factory.docx_reader import read_docx
from document_factory.operations import (
    HEADER_FOOTER_MIGRATION_SUPPORTED,
    FontProfile,
    OperationContext,
    PageFormat,
    apply_alignment,
    apply_bold,
    apply_color,
    apply_font,
    apply_font_size,
    apply_indent,
    apply_italic,
    apply_section_properties,
    apply_spacing,
    apply_style,
    apply_table_alignment,
    apply_table_font,
    apply_underline,
    find_style_element,
)
from conftest import W, paragraph


def _run(xml=""):
    return etree.fromstring(f'<w:r xmlns:w="{W}"><w:rPr>{xml}</w:rPr><w:t>文本 ABC</w:t></w:r>')


def _ctx(changes=None, prefix=""):
    return OperationContext(changes if changes is not None else [], "Run", "doc / Run 1",
                            "FONT001", "测试规范 3.1", prefix)


# ---- Font ----------------------------------------------------------------

def test_apply_font_sets_chinese_and_latin_font_in_one_record():
    run = _run('<w:rFonts w:asciiTheme="majorAscii" w:hAnsiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia"/>')
    changes = []
    assert apply_font(run, FontProfile(east_asia="仿宋", latin="Times New Roman"), _ctx(changes)) is True
    rfonts = run.find("w:rPr/w:rFonts", {"w": W})
    assert rfonts.get(f"{{{W}}}eastAsia") == "仿宋"
    assert rfonts.get(f"{{{W}}}ascii") == "Times New Roman"
    assert rfonts.get(f"{{{W}}}hAnsi") == "Times New Roman"
    assert rfonts.get(f"{{{W}}}asciiTheme") is None
    assert rfonts.get(f"{{{W}}}eastAsiaTheme") is None
    assert len(changes) == 1
    assert changes[0]["property"] == "font"
    assert set(changes[0]) == {"object_type", "location", "property", "before", "after", "rule", "source"}
    # Idempotent: the same profile produces no second change.
    assert apply_font(run, FontProfile(east_asia="仿宋", latin="Times New Roman"), _ctx()) is False


def test_apply_font_size_uses_half_points():
    run = _run('<w:sz w:val="20"/>')
    changes = []
    assert apply_font_size(run, 16, _ctx(changes)) is True
    assert run.find("w:rPr/w:sz", {"w": W}).get(f"{{{W}}}val") == "32"
    assert changes[0]["property"] == "font_size_pt"


def test_apply_bold_and_italic_toggles():
    run = _run('<w:b w:val="0"/><w:i/>')
    changes = []
    ctx = _ctx(changes)
    assert apply_bold(run, True, ctx) is True
    assert run.find("w:rPr/w:b", {"w": W}).get(f"{{{W}}}val") == "1"
    assert apply_italic(run, False, ctx) is True
    assert run.find("w:rPr/w:i", {"w": W}).get(f"{{{W}}}val") == "0"
    assert {change["property"] for change in changes} == {"bold", "italic"}
    assert apply_bold(run, True, _ctx()) is False


def test_apply_underline_and_color_removes_theme_color():
    run = _run('<w:u w:val="none"/><w:color w:themeColor="accent1"/>')
    changes = []
    ctx = _ctx(changes)
    assert apply_underline(run, True, ctx) is True
    assert run.find("w:rPr/w:u", {"w": W}).get(f"{{{W}}}val") == "single"
    assert apply_color(run, "000000", ctx) is True
    color = run.find("w:rPr/w:color", {"w": W})
    assert color.get(f"{{{W}}}val") == "000000"
    assert color.get(f"{{{W}}}themeColor") is None


# ---- Paragraph -----------------------------------------------------------

def test_apply_alignment_creates_ordered_pPr():
    p = etree.fromstring(f'<w:p xmlns:w="{W}"><w:r><w:t>x</w:t></w:r></w:p>')
    changes = []
    assert apply_alignment(p, "center", _ctx(changes)) is True
    assert p[0].tag == f"{{{W}}}pPr"
    assert p.find("w:pPr/w:jc", {"w": W}).get(f"{{{W}}}val") == "center"
    assert changes[0]["property"] == "alignment"


def test_apply_spacing_and_indent_only_writes_non_none_values():
    p = etree.fromstring(
        f'<w:p xmlns:w="{W}"><w:pPr><w:spacing w:beforeLines="50"/><w:ind w:firstLineChars="100" w:hanging="20"/></w:pPr></w:p>'
    )
    changes = []
    ctx = _ctx(changes)
    assert apply_spacing(
        p, {"before": 0, "after": 120, "line": 360, "lineRule": "auto"}, ctx,
        remove=("beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"),
    ) is True
    assert apply_indent(p, {"firstLineChars": 200}, ctx, remove=("firstLine", "hanging", "hangingChars")) is True
    spacing = p.find("w:pPr/w:spacing", {"w": W})
    assert spacing.get(f"{{{W}}}before") == "0"
    assert spacing.get(f"{{{W}}}after") == "120"
    assert spacing.get(f"{{{W}}}line") == "360"
    assert spacing.get(f"{{{W}}}beforeLines") is None
    indent = p.find("w:pPr/w:ind", {"w": W})
    assert indent.get(f"{{{W}}}firstLineChars") == "200"
    assert indent.get(f"{{{W}}}hanging") is None
    assert {change["property"] for change in changes} == {"spacing", "indent"}


# ---- Style ---------------------------------------------------------------

NORMAL_STYLE = '<w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>'
BAD_HEADING1 = (
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:pPr><w:outlineLvl w:val="0"/></w:pPr>'
    '<w:rPr><w:rFonts w:eastAsia="宋体" w:eastAsiaTheme="majorEastAsia"/><w:color w:val="2F5597" w:themeColor="accent1"/>'
    '<w:sz w:val="20"/></w:rPr></w:style>'
)


def test_apply_style_heading_mapping_on_real_style_element(make_docx):
    source = make_docx(paragraph("标题", "Heading1"), styles=NORMAL_STYLE + BAD_HEADING1)
    document = read_docx(source)
    element = find_style_element(document, "Heading1")
    assert element is not None
    profile = {
        "font": {"east_asia": "黑体", "latin": "Times New Roman", "size_pt": 16,
                 "bold": True, "italic": False, "color": "000000"},
        "paragraph": {"alignment": None, "spacing": {"before": 240, "after": 120, "line": None, "lineRule": None}, "indent": {}},
    }
    changes = []
    ctx = OperationContext(changes, "Style", "Style heading 1", "TEMPLATE", "Template Profile 1.0")
    assert apply_style(element, profile, ctx) is True
    rpr = element.find("w:rPr", {"w": W})
    assert rpr.find("w:rFonts", {"w": W}).get(f"{{{W}}}eastAsia") == "黑体"
    assert rpr.find("w:rFonts", {"w": W}).get(f"{{{W}}}ascii") == "Times New Roman"
    assert rpr.find("w:sz", {"w": W}).get(f"{{{W}}}val") == "32"
    assert rpr.find("w:b", {"w": W}).get(f"{{{W}}}val") == "1"
    assert rpr.find("w:i", {"w": W}).get(f"{{{W}}}val") == "0"
    assert rpr.find("w:color", {"w": W}).get(f"{{{W}}}val") == "000000"
    spacing = element.find("w:pPr/w:spacing", {"w": W})
    assert spacing.get(f"{{{W}}}before") == "240"
    assert spacing.get(f"{{{W}}}after") == "120"
    assert all(change["rule"] == "TEMPLATE" for change in changes)
    assert find_style_element(document, "MissingStyle") is None


# ---- Table ---------------------------------------------------------------

def test_table_font_and_alignment_operations():
    run = _run('<w:rFonts w:eastAsia="微软雅黑"/><w:sz w:val="18"/>')
    changes = []
    ctx = OperationContext(changes, "Run", "表格 / Run 1", "TEMPLATE", "Template Profile 1.0", "table_header_")
    assert apply_table_font(
        run, {"font": {"east_asia": "黑体", "latin": "Arial", "size_pt": 11}}, ctx,
    ) is True
    rfonts = run.find("w:rPr/w:rFonts", {"w": W})
    assert rfonts.get(f"{{{W}}}eastAsia") == "黑体"
    assert rfonts.get(f"{{{W}}}ascii") == "Arial"
    assert run.find("w:rPr/w:sz", {"w": W}).get(f"{{{W}}}val") == "22"
    p = etree.fromstring(f'<w:p xmlns:w="{W}"><w:pPr/></w:p>')
    assert apply_table_alignment(p, "center", OperationContext([], "Paragraph", "表格", "TEMPLATE", "Template Profile 1.0")) is True
    assert p.find("w:pPr/w:jc", {"w": W}).get(f"{{{W}}}val") == "center"
    assert all(change["property"].startswith("table_header_") for change in changes)


# ---- Document ------------------------------------------------------------

def test_apply_section_properties_sets_ordered_page_size_and_margins():
    sect = etree.fromstring(f'<w:sectPr xmlns:w="{W}"><w:pgNumType w:start="1"/></w:sectPr>')
    changes = []
    page = PageFormat(
        width_twips=11906, height_twips=16838, orientation="portrait",
        margins={"top": 1440, "bottom": 1440, "left": 1800, "right": 1800},
    )
    assert apply_section_properties(sect, page, OperationContext(changes, "Section", "sectPr 1")) is True
    names = [etree.QName(child).localname for child in sect]
    assert names.index("pgSz") < names.index("pgMar") < names.index("pgNumType")
    pg_sz = sect.find("w:pgSz", {"w": W})
    assert pg_sz.get(f"{{{W}}}w") == "11906"
    assert pg_sz.get(f"{{{W}}}h") == "16838"
    pg_mar = sect.find("w:pgMar", {"w": W})
    assert pg_mar.get(f"{{{W}}}top") == "1440"
    assert pg_mar.get(f"{{{W}}}left") == "1800"
    assert {change["property"] for change in changes} == {"page_size", "page_margins"}
    # Headers and footers are analyzed but not migrated in this version.
    assert HEADER_FOOTER_MIGRATION_SUPPORTED is False
