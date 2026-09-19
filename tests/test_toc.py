from document_factory.docx_reader import read_docx
from document_factory.lint_engine import lint
from conftest import paragraph, W

TOC = r'<w:p><w:fldSimple w:instr="TOC \o &quot;1-2&quot; \h \z \u"><w:r><w:t>目录条目</w:t></w:r></w:fldSimple></w:p>'


def test_simple_toc(make_docx, rules):
    ctx = lint(make_docx(TOC), rules)
    assert any(f.rule_id == 'TOC001' and f.status == 'PASS' for f in ctx.findings)
    assert any(f.rule_id == 'TOC002' and f.status == 'PASS' for f in ctx.findings)
    assert ctx.document.paragraphs[0].in_toc


def test_split_complex_nested_fields(make_docx, rules):
    body = r'<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> TO</w:instrText></w:r><w:r><w:instrText>C \o "1-2" \h \z \u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r></w:p>'
    body += '<w:p><w:r><w:t>引言</w:t><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>PAGEREF _Toc1</w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    body += '<w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    ctx = lint(make_docx(body), rules)
    assert [f.kind for f in ctx.document.fields] == ['PAGEREF', 'TOC']
    assert ctx.document.paragraphs[1].in_toc
    assert any(f.rule_id == 'TOC002' and f.status == 'PASS' for f in ctx.findings)


def test_toc_title_is_not_field(make_docx, rules):
    ctx = lint(make_docx(paragraph('目录') + paragraph('引言......1')), rules)
    assert any(f.rule_id == 'TOC001' and f.severity == 'ERROR' for f in ctx.findings)
    assert any(f.rule_id == 'TOC003' for f in ctx.findings)


def test_wrong_levels_and_additional_sources(make_docx, rules):
    ctx = lint(make_docx(TOC.replace('1-2', '1-3').replace('\\u', '\\u \\t &quot;Extra,1&quot;')), rules)
    assert any(f.rule_id == 'TOC002' and f.severity == 'ERROR' for f in ctx.findings)
    assert any(f.rule_id == 'TOC002' and f.status == 'UNSUPPORTED' for f in ctx.findings)


def test_unclosed_field_is_not_pass(make_docx, rules):
    body = r'<w:p><w:r><w:fldChar w:fldCharType="begin"/><w:instrText>TOC \o "1-2"</w:instrText></w:r></w:p>'
    ctx = lint(make_docx(body), rules)
    assert any(f.rule_id == 'TOC001' and f.severity == 'ERROR' for f in ctx.findings)
    assert ctx.document.fields[0].complete is False


def test_double_backslash_toc_not_silently_passed(make_docx, rules):
    ctx = lint(make_docx(TOC.replace('\\', '\\\\')), rules)
    checks = [f for f in ctx.findings if f.rule_id == 'TOC002']
    assert checks and not any(f.status == 'PASS' for f in checks)
    assert any(f.status == 'UNSUPPORTED' for f in checks)


def test_footer_fields_and_footnotes(make_docx):
    footer = f'<w:ftr xmlns:w="{W}"><w:p>' + ''.join(f'<w:fldSimple w:instr="{name}"><w:r><w:t>1</w:t></w:r></w:fldSimple>' for name in ('PAGE', 'NUMPAGES', 'REF bookmark', 'SEQ figure')) + '</w:p></w:ftr>'
    d = read_docx(make_docx(extra={'word/footer1.xml': footer, 'word/footnotes.xml': f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="1">{paragraph("注释")}</w:footnote></w:footnotes>'}))
    assert {f.kind for f in d.fields} == {'PAGE', 'NUMPAGES', 'REF', 'SEQ'}
    assert any(p.text == '注释' for p in d.paragraphs)
