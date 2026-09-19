import pytest
from document_factory.docx_reader import read_docx
from document_factory.style_resolver import StyleResolver
from document_factory.numbering_analyzer import NumberingAnalyzer
from document_factory.lint_engine import lint
from conftest import paragraph, NUMBERING, BODY_STYLE, HEADING_STYLES


def binding(path):
    d = read_docx(path)
    return NumberingAnalyzer(d, StyleResolver(d)).binding(d.paragraphs[0])


@pytest.mark.parametrize('text', ['1 引言', '1.1 范围', '1.1.1目标', '一、引言', '（一）范围', '1）范围'])
def test_manual_numbering(text, make_docx, rules):
    ctx = lint(make_docx(paragraph(text, 'Heading1')), rules)
    assert any(f.rule_id == 'NUM001' and f.severity == 'ERROR' for f in ctx.findings)
    assert any(f.rule_id == 'NUM002' and f.severity == 'ERROR' for f in ctx.findings)


def test_real_automatic_numbering(make_docx, rules):
    path = make_docx(paragraph('引言', 'Heading1', '<w:numPr><w:numId w:val="5"/><w:ilvl w:val="0"/></w:numPr>'), numbering=NUMBERING)
    b = binding(path)
    assert b['valid'] and b['multilevel'] and b['ilvl'] == 0
    assert not any(f.rule_id.startswith('NUM') and f.severity == 'ERROR' for f in lint(path, rules).findings)


def test_style_linked_level_ignores_style_ilvl(make_docx):
    styles = HEADING_STYLES.replace('<w:outlineLvl w:val="1"/>', '<w:outlineLvl w:val="1"/><w:numPr><w:numId w:val="5"/><w:ilvl w:val="0"/></w:numPr>')
    b = binding(make_docx(paragraph('标题二', 'Heading2'), styles=styles, numbering=NUMBERING))
    assert b['valid'] and b['ilvl'] == 1


def test_explicit_cancel_and_dangling_id(make_docx):
    for number in ('0', '999'):
        path = make_docx(paragraph('引言', 'Heading1', f'<w:numPr><w:numId w:val="{number}"/></w:numPr>'), numbering=NUMBERING)
        assert not binding(path)['valid']


def test_single_level_is_not_multilevel(make_docx, rules):
    path = make_docx(paragraph('引言', 'Heading1', '<w:numPr><w:numId w:val="5"/></w:numPr>'), numbering=NUMBERING.replace('multilevel', 'singleLevel'))
    assert any(f.rule_id == 'NUM003' and f.severity == 'ERROR' for f in lint(path, rules).findings)


def test_num_style_link_and_override(make_docx):
    style = '<w:style w:type="numbering" w:styleId="Linked"><w:name w:val="Linked"/><w:pPr><w:numPr><w:numId w:val="5"/></w:numPr></w:pPr></w:style>'
    numbers = NUMBERING + '<w:abstractNum w:abstractNumId="2"><w:numStyleLink w:val="Linked"/></w:abstractNum><w:num w:numId="6"><w:abstractNumId w:val="2"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="4"/></w:lvlOverride></w:num>'
    path = make_docx(paragraph('引言', 'Heading1', '<w:numPr><w:numId w:val="6"/></w:numPr>'), styles=HEADING_STYLES + style, numbering=numbers)
    b = binding(path)
    assert b['valid'] and b['start_override'] == '4'


def test_num_style_cycle_is_reported(make_docx):
    style = '<w:style w:type="numbering" w:styleId="Loop"><w:name w:val="Loop"/><w:pPr><w:numPr><w:numId w:val="5"/></w:numPr></w:pPr></w:style>'
    numbers = '<w:abstractNum w:abstractNumId="1"><w:numStyleLink w:val="Loop"/></w:abstractNum><w:num w:numId="5"><w:abstractNumId w:val="1"/></w:num>'
    b = binding(make_docx(paragraph('引言', 'Heading1', '<w:numPr><w:numId w:val="5"/></w:numPr>'), styles=HEADING_STYLES + style, numbering=numbers))
    assert not b['valid'] and '循环' in b['reason']
