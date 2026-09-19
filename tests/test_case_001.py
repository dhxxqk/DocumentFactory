from pathlib import Path
import json
import pytest
from document_factory.docx_reader import sha256
from document_factory.lint_engine import lint
from document_factory.report_writer import write_report
from conftest import ROOT


def test_case_001_full_structural_audit_without_mutation(rules, tmp_path):
    path = ROOT / 'testcases/第三周_规划管理能力_培训材料_格式规范V1.4.docx'
    if not path.exists():
        pytest.skip('正式 TEST_CASE_001 缺失；不伪造替代样本')
    before = sha256(path)
    ctx = lint(path, rules)
    report = write_report(ctx, tmp_path / 'reports/TEST_CASE_001_LINT_REPORT.md', root=tmp_path)
    data = json.loads(report.with_suffix('.json').read_text(encoding='utf-8'))
    assert data['result'] == ('FAIL' if data['counts']['ERROR'] else 'PASS')
    assert ctx.document.fields and ctx.document.tables and ctx.document.sections
    assert all(f.rule_id and f.location and f.source and f.message for f in ctx.findings)
    assert 'DocumentFactory 文档审计报告' in report.read_text(encoding='utf-8')
    assert sha256(path) == before


def test_repeat_audit_is_deterministic(rules):
    path = ROOT / 'testcases/第三周_规划管理能力_培训材料_格式规范V1.4.docx'
    if not path.exists():
        pytest.skip('正式 TEST_CASE_001 缺失')
    a, b = lint(path, rules), lint(path, rules)
    assert [f.to_dict() for f in a.findings] == [f.to_dict() for f in b.findings]
