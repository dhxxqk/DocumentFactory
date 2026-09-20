import json
from pathlib import Path
import shutil
import pytest
from document_factory.cli import main
from document_factory.lint_engine import load_rules
from document_factory.models import DocumentFactoryError
from conftest import ROOT, paragraph


def test_lint_fail_exit_report_written(make_docx, tmp_path, monkeypatch):
    path = make_docx(paragraph('1 引言', 'Heading1'))
    monkeypatch.chdir(tmp_path)
    code = main(['lint', str(path), '--rules', str(ROOT / 'rules/grid_tech_v1_4.yaml')])
    assert code == 1
    assert list((tmp_path / 'reports').glob('*.md'))


def test_missing_input_exit_two(tmp_path):
    assert main(['lint', str(tmp_path / 'missing.docx'), '--rules', str(ROOT / 'rules/grid_tech_v1_4.yaml')]) == 2


def test_missing_spec_refuses_rules(tmp_path):
    destination = tmp_path / 'rules/grid_tech_v1_4.yaml'
    destination.parent.mkdir()
    destination.write_text((ROOT / 'rules/grid_tech_v1_4.yaml').read_text(encoding='utf-8'), encoding='utf-8')
    with pytest.raises(DocumentFactoryError, match='规范主源缺失'):
        load_rules(destination)


def test_bad_yaml_readable_error(tmp_path):
    path = tmp_path / 'bad.yaml'
    path.write_text('version: [', encoding='utf-8')
    with pytest.raises(DocumentFactoryError, match='规则文件'):
        load_rules(path)


def test_v01_rules_without_normalization_metadata_still_load_for_lint(tmp_path):
    destination = tmp_path / 'rules/grid_tech_v1_4.yaml'
    destination.parent.mkdir()
    source_text = (ROOT / 'rules/grid_tech_v1_4.yaml').read_text(encoding='utf-8')
    destination.write_text(source_text.replace('  normalization_line_spacing: single\n', ''), encoding='utf-8')
    spec = tmp_path / 'specs/电网科技项目实施方案文档格式规范_V1.4.md'
    spec.parent.mkdir()
    shutil.copyfile(ROOT / 'specs/电网科技项目实施方案文档格式规范_V1.4.md', spec)
    assert load_rules(destination)['tables'].get('normalization_line_spacing') is None


def test_audit_writes_report_on_unavailable_render(make_docx, tmp_path, monkeypatch):
    from document_factory import renderer
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(renderer, 'available_backends', lambda: {'LibreOffice': None, 'Word COM': False})
    code = main(['audit', str(make_docx()), '--rules', str(ROOT / 'rules/grid_tech_v1_4.yaml')])
    assert code == 3
    data = json.loads(next((tmp_path / 'reports').glob('*.json')).read_text(encoding='utf-8'))
    assert data['render']['status'] == 'RENDER_UNAVAILABLE'


def test_report_path_cannot_overwrite_input(make_docx, tmp_path, monkeypatch):
    from document_factory.docx_reader import sha256
    path = make_docx()
    before = sha256(path)
    monkeypatch.chdir(tmp_path)
    assert main(['lint', str(path), '--rules', str(ROOT / 'rules/grid_tech_v1_4.yaml'), '--report', str(path)]) == 2
    assert sha256(path) == before


def test_normalize_cli_prints_machine_friendly_summary(make_docx, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = make_docx()
    code = main(['normalize', str(path), '--rules', str(ROOT / 'rules/grid_tech_v1_4.yaml')])
    output = capsys.readouterr().out
    assert code in (0, 1)
    assert all(f'{key}=' in output for key in ('STATUS', 'OUTPUT', 'REPORT', 'BEFORE_ERROR', 'AFTER_ERROR', 'CHANGED'))
