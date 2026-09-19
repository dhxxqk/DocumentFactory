from document_factory.lint_engine import lint
from conftest import paragraph, SECTION


def test_landscape_warning_not_whole_document_error(make_docx, rules):
    section = SECTION.replace('w:w="11906" w:h="16838"', 'w:w="16838" w:h="11906" w:orient="landscape"')
    ctx = lint(make_docx(section=section), rules)
    assert any(f.rule_id == 'PAGE001' and f.status == 'PASS' for f in ctx.findings)
    assert any(f.rule_id == 'PAGE002' and f.severity == 'WARNING' for f in ctx.findings)


def test_margin_violation(make_docx, rules):
    ctx = lint(make_docx(section=SECTION.replace('w:top="1587"', 'w:top="100"')), rules)
    assert any(f.rule_id == 'PAGE003' and f.severity == 'ERROR' for f in ctx.findings)


def test_front_title_and_missing_page_boundary(make_docx, rules):
    ctx = lint(make_docx(paragraph('编制说明', 'Heading1') + paragraph('目录', 'Heading1') + paragraph('引言', 'Heading1')), rules)
    for rule in ('FRONT001', 'FRONT002'):
        assert any(f.rule_id == rule and f.severity == 'ERROR' for f in ctx.findings)
    assert any(f.rule_id == 'FRONT003' and f.severity == 'WARNING' for f in ctx.findings)


def test_explicit_page_break_before_first_heading(make_docx, rules):
    ctx = lint(make_docx(paragraph('前置') + paragraph('引言', 'Heading1', '<w:pageBreakBefore/>')), rules)
    assert any(f.rule_id == 'FRONT003' and f.status == 'PASS' for f in ctx.findings)


def test_break_before_previous_text_does_not_separate_heading(make_docx, rules):
    prior = '<w:p><w:r><w:br w:type="page"/><w:t>目录末尾内容</w:t></w:r></w:p>'
    ctx = lint(make_docx(prior + paragraph('引言', 'Heading1')), rules)
    assert any(f.rule_id == 'FRONT003' and f.severity == 'WARNING' for f in ctx.findings)


def test_toc_content_cannot_be_skipped_when_testing_boundary(make_docx, rules):
    body = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    body += r'<w:p><w:fldSimple w:instr="TOC \o &quot;1-2&quot;"><w:r><w:t>目录尾部</w:t></w:r></w:fldSimple></w:p>'
    ctx = lint(make_docx(body + paragraph('引言', 'Heading1')), rules)
    assert any(f.rule_id == 'FRONT003' and f.severity == 'WARNING' for f in ctx.findings)
