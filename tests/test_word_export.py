"""COM contract tests only; these do not claim native Word rendering works here."""
from types import ModuleType, SimpleNamespace
import sys
import pytest
from document_factory import _word_export


@pytest.mark.parametrize('failure', [None, 'open', 'export', 'existing_process'])
def test_word_window_readonly_export_and_cleanup(tmp_path, monkeypatch, failure):
    calls = []
    class Document:
        def __init__(self, probe=False):
            self.probe = probe

        def Windows(self, index):
            assert index == 1
            return SimpleNamespace(Hwnd=345)

        def Close(self, **kwargs):
            calls.append(('close_probe' if self.probe else 'close_input', kwargs))

        def ExportAsFixedFormat(self, **kwargs):
            calls.append(('export', kwargs))
            if failure == 'export':
                raise RuntimeError('export failure')

    class Documents:
        def Add(self, **kwargs):
            calls.append(('probe', kwargs))
            return Document(probe=True)

        def Open(self, **kwargs):
            calls.append(('open', kwargs))
            if failure == 'open':
                raise RuntimeError('open failure')
            return Document()

    options = SimpleNamespace(UpdateLinksAtOpen=True)
    app = SimpleNamespace(Documents=Documents(), Options=options, Quit=lambda **kwargs: calls.append(('quit', kwargs)))
    com = ModuleType('win32com')
    client = ModuleType('win32com.client')
    client.DispatchEx = lambda name: app
    com.client = client
    monkeypatch.setitem(sys.modules, 'win32com', com)
    monkeypatch.setitem(sys.modules, 'win32com.client', client)
    monkeypatch.setitem(sys.modules, 'pythoncom', SimpleNamespace(CoInitialize=lambda: calls.append(('init', {})), CoUninitialize=lambda: calls.append(('uninit', {}))))
    monkeypatch.setitem(sys.modules, 'win32process', SimpleNamespace(EnumProcesses=lambda: [11], GetWindowThreadProcessId=lambda hwnd: (0, 11 if failure == 'existing_process' else 22)))
    pid = tmp_path / 'word.pid'
    monkeypatch.setattr(sys, 'argv', ['worker', str(tmp_path / 'private.docx'), str(tmp_path / 'document.pdf'), str(pid)])
    if failure:
        with pytest.raises(RuntimeError):
            _word_export.main()
    else:
        _word_export.main()
    assert ('probe', {'Visible': False}) in calls
    assert ('close_probe', {'SaveChanges': 0}) in calls
    assert calls[-1][0] == 'uninit'
    if failure == 'existing_process':
        assert not any(name in ('open', 'quit') for name, _ in calls)
    else:
        assert pid.read_text(encoding='ascii') == '22'
        assert ('quit', {'SaveChanges': 0}) in calls
        opening = next(kwargs for name, kwargs in calls if name == 'open')
        assert opening['ReadOnly'] and not opening['Visible'] and not opening['AddToRecentFiles']
        assert options.UpdateLinksAtOpen is True
        if failure != 'open':
            assert ('close_input', {'SaveChanges': 0}) in calls
