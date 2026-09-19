from document_factory.lint_engine import lint
from conftest import BODY_STYLE, HEADING_STYLES, paragraph, table


def test_table_body_style_detected(make_docx, rules):
    ctx = lint(make_docx(table()), rules)
    assert sum(f.rule_id == 'TABLE001' for f in ctx.findings) == 2
    assert any(f.rule_id == 'TABLE004' and f.severity == 'ERROR' for f in ctx.findings)


def test_based_on_body_transitive(make_docx, rules):
    styles = BODY_STYLE + '<w:style w:type="paragraph" w:styleId="Bridge"><w:name w:val="Bridge"/><w:basedOn w:val="Body"/></w:style><w:style w:type="paragraph" w:styleId="TableBody"><w:name w:val="表格正文"/><w:basedOn w:val="Bridge"/></w:style>'
    ctx = lint(make_docx(table('TableBody'), styles=styles), rules)
    assert any(f.rule_id == 'TABLE005' and f.severity == 'ERROR' for f in ctx.findings)


def test_direct_indent_and_spacing_override(make_docx, rules):
    body = table().replace('</w:pPr>', '<w:ind w:firstLineChars="100"/><w:spacing w:beforeLines="100"/></w:pPr>')
    ctx = lint(make_docx(body), rules)
    assert any(f.rule_id == 'TABLE004' and f.severity == 'ERROR' for f in ctx.findings)
    assert any(f.rule_id == 'TABLE006' and f.severity == 'WARNING' for f in ctx.findings)


def test_repeated_header_stronger_than_first_row_candidate(make_docx, rules):
    ctx = lint(make_docx(table().replace('<w:tr>', '<w:tr><w:trPr><w:tblHeader/></w:trPr>', 1)), rules)
    assert any(f.rule_id == 'TABLE002' and f.severity == 'ERROR' for f in ctx.findings)


def test_cover_metadata_table_is_not_definite_content_table(make_docx, rules):
    styles = BODY_STYLE + '<w:style w:type="paragraph" w:styleId="Cover"><w:name w:val="封面-信息内容"/></w:style>'
    ctx = lint(make_docx(table('Cover', 'Cover'), styles=styles), rules)
    issues = [f for f in ctx.findings if f.rule_id == 'TABLE003']
    assert issues and all(f.severity == 'WARNING' and f.status == 'UNSUPPORTED' for f in issues)
