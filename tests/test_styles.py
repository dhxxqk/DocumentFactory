from document_factory.docx_reader import read_docx
from document_factory.style_resolver import StyleResolver
from document_factory.lint_engine import lint
from conftest import BODY_STYLE, HEADING_STYLES, paragraph, W, A


def test_run_overrides_chinese_not_english(make_docx, rules):
    body = paragraph('中文', run_properties='<w:rFonts w:eastAsia="微软雅黑"/>') + paragraph('English 123', run_properties='<w:rFonts w:ascii="Times New Roman" w:eastAsia="微软雅黑"/>')
    ctx = lint(make_docx(body), rules)
    errors = [f for f in ctx.findings if f.rule_id == 'FONT001' and f.severity == 'ERROR']
    assert len(errors) == 1 and 'Paragraph 1' in errors[0].location
    assert not any(f.rule_id == 'FONT002' and f.severity == 'ERROR' for f in ctx.findings)


def test_heading_style_theme_blue_cannot_be_hidden_by_run(make_docx, rules):
    styles = BODY_STYLE + HEADING_STYLES.replace('<w:color w:val="000000"/>', '<w:color w:val="4F81BD" w:themeColor="accent1"/>')
    ctx = lint(make_docx(paragraph('标题', 'Heading1', run_properties='<w:color w:val="000000"/>'), styles=styles), rules)
    assert any(f.rule_id == 'STYLE004' and f.severity == 'ERROR' for f in ctx.findings)
    assert any(f.rule_id == 'FONT004' and f.status == 'PASS' for f in ctx.findings)


def test_direct_font_supersedes_inherited_theme(make_docx, rules):
    styles = BODY_STYLE.replace('w:eastAsia="仿宋"', 'w:eastAsiaTheme="majorEastAsia"')
    ctx = lint(make_docx(paragraph(run_properties='<w:rFonts w:eastAsia="仿宋"/>'), styles=styles), rules)
    checks = [f for f in ctx.findings if f.rule_id == 'FONT001' and 'Run 1' in f.location]
    assert checks and all(f.status == 'PASS' for f in checks)


def test_visual_heading_candidate_is_warning(make_docx, rules):
    ctx = lint(make_docx(paragraph('1.1 项目范围', 'Normal', run_properties='<w:b/><w:sz w:val="28"/>')), rules)
    assert any(f.rule_id == 'STYLE002' and f.severity == 'WARNING' for f in ctx.findings)


def test_basedon_cycle_does_not_hang(make_docx, rules):
    styles = '<w:style w:type="paragraph" w:styleId="A"><w:name w:val="A"/><w:basedOn w:val="B"/></w:style><w:style w:type="paragraph" w:styleId="B"><w:name w:val="B"/><w:basedOn w:val="A"/></w:style>'
    ctx = lint(make_docx(paragraph(style='A'), styles=styles), rules)
    assert any('循环' in f.message for f in ctx.findings)


def test_character_style_and_toggle_cascade(make_docx):
    styles = BODY_STYLE.replace('<w:sz w:val="24"/>', '<w:sz w:val="24"/><w:b/>') + '<w:style w:type="character" w:styleId="Toggle"><w:name w:val="Toggle"/><w:rPr><w:b/><w:rFonts w:eastAsia="黑体"/></w:rPr></w:style>'
    d = read_docx(make_docx(paragraph(run_properties='<w:rStyle w:val="Toggle"/>'), styles=styles))
    r = StyleResolver(d)
    props = r.run(d.paragraphs[0], d.paragraphs[0].runs[0])
    assert props['b'] is False and props['rFonts']['eastAsia'] == '黑体'
    assert any(x['source'] == 'character style:Toggle' for x in r.trace(d.paragraphs[0], d.paragraphs[0].runs[0]))


def test_theme_font_precedes_explicit_font(make_docx, rules):
    theme = f'<a:theme xmlns:a="{A}"><a:themeElements><a:fontScheme><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:font script="Hans" typeface="微软雅黑"/></a:majorFont></a:fontScheme></a:themeElements></a:theme>'
    settings = f'<w:settings xmlns:w="{W}"><w:themeFontLang w:eastAsia="zh-CN"/></w:settings>'
    body = paragraph(run_properties='<w:rFonts w:eastAsia="仿宋" w:eastAsiaTheme="majorEastAsia"/>')
    ctx = lint(make_docx(body, extra={'word/theme/theme1.xml': theme, 'word/settings.xml': settings}), rules)
    assert any(f.rule_id == 'FONT001' and f.severity == 'ERROR' and f.actual['font'] == '微软雅黑' for f in ctx.findings)


def test_missing_theme_is_unsupported(make_docx, rules):
    ctx = lint(make_docx(paragraph(run_properties='<w:rFonts w:eastAsiaTheme="majorEastAsia"/>')), rules)
    assert any(f.rule_id == 'FONT001' and f.status == 'UNSUPPORTED' for f in ctx.findings)


def test_normal_cover_toc_caption_not_body_errors(make_docx, rules):
    ctx = lint(make_docx(paragraph('封面项目标题', 'Normal') + paragraph('目录', 'Normal') + paragraph('表1-1 ' + '说明' * 30, 'Normal')), rules)
    assert not any(f.rule_id == 'BODY001' and f.status != 'PASS' for f in ctx.findings)


def test_custom_heading_lookalike_is_not_builtin(make_docx, rules):
    styles = BODY_STYLE + HEADING_STYLES.replace('w:styleId="Heading1"', 'w:styleId="Heading1" w:customStyle="1"')
    ctx = lint(make_docx(paragraph('标题', 'Heading1'), styles=styles), rules)
    assert any(f.rule_id == 'STYLE001' and f.severity == 'WARNING' for f in ctx.findings)
