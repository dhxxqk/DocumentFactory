"""Isolated Word COM worker. Open only a private copy, read-only, close without save."""
import json
from pathlib import Path
import sys


def main():
    import pythoncom
    import win32com.client
    import win32process
    app = document = probe = None
    owned = False
    previous_links = None
    pythoncom.CoInitialize()
    try:
        previous = set(win32process.EnumProcesses())
        app = win32com.client.DispatchEx("Word.Application")
        app.AutomationSecurity = 3  # Disable macros before creating the hidden probe.
        # Word exposes Hwnd on Window, not Application. A never-saved blank
        # window establishes process ownership before opening the private input.
        probe = app.Documents.Add(Visible=False)
        pid = win32process.GetWindowThreadProcessId(probe.Windows(1).Hwnd)[1]
        if pid in previous:
            raise RuntimeError("Word 未创建独立进程，为避免影响用户会话停止导出")
        owned = True
        Path(sys.argv[3]).write_text(str(pid), encoding="ascii")
        probe.Close(SaveChanges=0)
        probe = None
        app.Visible = False
        app.DisplayAlerts = 0
        app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        previous_links = app.Options.UpdateLinksAtOpen
        app.Options.UpdateLinksAtOpen = False
        document = app.Documents.Open(FileName=str(Path(sys.argv[1]).resolve()), ConfirmConversions=False,
                                      ReadOnly=True, AddToRecentFiles=False, Visible=False, OpenAndRepair=False,
                                      PasswordDocument="", WritePasswordDocument="", NoEncodingDialog=True)
        document.ExportAsFixedFormat(OutputFileName=str(Path(sys.argv[2]).resolve()), ExportFormat=17,
                                     OpenAfterExport=False, OptimizeFor=0, CreateBookmarks=1)
        print(json.dumps({"status": "SUCCESS", "backend": "Word COM"}))
    finally:
        try:
            if document is not None:
                document.Close(SaveChanges=0)
        finally:
            try:
                if probe is not None:
                    probe.Close(SaveChanges=0)
                if app is not None and owned:
                    if previous_links is not None:
                        app.Options.UpdateLinksAtOpen = previous_links
                    app.Quit(SaveChanges=0)
            finally:
                pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
