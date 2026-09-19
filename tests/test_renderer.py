import json
from pathlib import Path
import pymupdf
import pytest
from document_factory import renderer
from document_factory.docx_reader import sha256
from document_factory.models import DocumentFactoryError


def test_unavailable_explicit_and_input_unchanged(make_docx, tmp_path, monkeypatch):
    path = make_docx()
    original = sha256(path)
    monkeypatch.setattr(renderer, 'available_backends', lambda: {'LibreOffice': None, 'Word COM': False})
    result = renderer.render(path, root=tmp_path)
    assert result.status == 'RENDER_UNAVAILABLE'
    assert sha256(path) == original
    assert list((tmp_path / 'output').rglob('render_result.json'))


def test_pdf_to_png_success_without_native_office(make_docx, tmp_path, monkeypatch):
    path = make_docx()
    original = sha256(path)
    monkeypatch.setattr(renderer, 'available_backends', lambda: {'LibreOffice': None, 'Word COM': True})
    def fake_export(copy, pdf, temp, timeout):
        assert copy != path and sha256(copy) == original
        with pymupdf.open() as doc:
            doc.new_page().insert_text((50, 50), 'Renderer fixture page 1')
            doc.new_page().insert_text((50, 50), 'Renderer fixture page 2')
            doc.save(pdf)
    monkeypatch.setattr(renderer, '_export_word', fake_export)
    result = renderer.render(path, root=tmp_path, dpi=72)
    assert result.status == 'SUCCESS' and len(result.pages) == 2
    assert all(Path(p).read_bytes().startswith(b'\x89PNG') for p in result.pages)
    assert sha256(path) == original
    second = renderer.render(path, root=tmp_path, dpi=72)
    assert second.pdf != result.pdf  # No stale pages across runs.


def test_failed_backend_not_silently_skipped(make_docx, tmp_path, monkeypatch):
    monkeypatch.setattr(renderer, 'available_backends', lambda: {'LibreOffice': None, 'Word COM': True})
    def fail(*args):
        raise RuntimeError('export failed')
    monkeypatch.setattr(renderer, '_export_word', fail)
    assert renderer.render(make_docx(), root=tmp_path).status == 'RENDER_FAILED'


def test_output_cannot_escape_or_overwrite_input(make_docx, tmp_path):
    path = make_docx()
    with pytest.raises(DocumentFactoryError, match='output'):
        renderer.render(path, output_dir=tmp_path / 'testcases', root=tmp_path)


def test_word_timeout_targets_only_owned_pid(tmp_path, monkeypatch):
    import subprocess
    commands = []
    pid = tmp_path / 'word.pid'
    pid.write_text('12345', encoding='ascii')
    def fake_run(command, timeout):
        commands.append(command)
        if len(commands) == 1:
            raise subprocess.TimeoutExpired(command, timeout)
        return SimpleNamespace(returncode=0)
    from types import SimpleNamespace
    monkeypatch.setattr(renderer, '_run', fake_run)
    with pytest.raises(subprocess.TimeoutExpired):
        renderer._export_word(tmp_path / 'private.docx', tmp_path / 'document.pdf', tmp_path, 1)
    if renderer.sys.platform == 'win32':
        assert commands[1] == ['taskkill', '/PID', '12345', '/T', '/F']
