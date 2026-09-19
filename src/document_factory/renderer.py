from pathlib import Path
from dataclasses import asdict
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from .docx_reader import read_docx, sha256
from .models import DocumentFactoryError, RenderResult
from .output_paths import checked_output


def find_libreoffice():
    candidates = [os.environ.get("DOCUMENT_FACTORY_SOFFICE"), shutil.which("soffice"), shutil.which("libreoffice")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append(str(Path(base) / "LibreOffice/program/soffice.exe"))
    return next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()), None)


def word_available():
    if sys.platform != "win32" or importlib.util.find_spec("win32com") is None:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application\\CLSID") as key:
            clsid = winreg.QueryValueEx(key, None)[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\LocalServer32") as key:
            server = winreg.QueryValueEx(key, None)[0]
        # WPS may register Word.Application. It is not Microsoft Word COM.
        return "winword.exe" in server.lower()
    except OSError:
        return False


def available_backends():
    return {"LibreOffice": find_libreoffice(), "Word COM": word_available()}


def _run(command, timeout):
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def _export_word(copy, pdf, temp, timeout):
    pidfile = temp / "word.pid"
    try:
        result = _run([sys.executable, "-X", "utf8", "-m", "document_factory._word_export", str(copy), str(pdf), str(pidfile)], timeout)
    except subprocess.TimeoutExpired:
        # Kill only the newly created Word process recorded by our worker, never all WINWORDs.
        if pidfile.exists() and sys.platform == "win32":
            pid = int(pidfile.read_text(encoding="ascii"))
            _run(["taskkill", "/PID", str(pid), "/T", "/F"], 10)
        raise
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Word COM 导出失败")


def render(source, output_dir=None, *, root=None, timeout=120, dpi=144, backend="auto"):
    root = Path(root or Path.cwd()).resolve()
    source = Path(source).resolve()
    # Validate before launching any native program.
    document = read_docx(source)
    output_dir = checked_output(output_dir or root / "output/render" / source.stem, root, "output", source)
    if dpi < 36 or dpi > 600 or timeout <= 0:
        raise DocumentFactoryError("dpi 必须在 36–600，timeout 必须为正数")
    output_dir.mkdir(parents=True, exist_ok=True)
    backends = available_backends()
    choices = (["LibreOffice"] if backends["LibreOffice"] else []) + (["Word COM"] if backends["Word COM"] else [])
    if backend != "auto":
        choices = [backend] if backend in choices else []
    if not choices:
        result = RenderResult("RENDER_UNAVAILABLE", message="未找到可用 LibreOffice 或 Microsoft Word COM（含 pywin32 依赖）；WPS 的 Word.Application 兼容注册不视为 Microsoft Word")
    else:
        result = RenderResult("RENDER_FAILED", message="所有可用后端均导出失败")
        errors = []
        for choice in choices:
            try:
                with tempfile.TemporaryDirectory(prefix=".render-", dir=output_dir) as name:
                    temp = Path(name)
                    private_copy = temp / "document.docx"
                    shutil.copyfile(source, private_copy)
                    pdf = temp / "document.pdf"
                    if choice == "LibreOffice":
                        profile = (temp / "lo-profile").as_uri()
                        completed = _run([backends["LibreOffice"], f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", str(temp), str(private_copy)], timeout)
                        if completed.returncode:
                            raise RuntimeError(completed.stderr or completed.stdout)
                    else:
                        _export_word(private_copy, pdf, temp, timeout)
                    if not pdf.is_file() or not pdf.stat().st_size:
                        raise RuntimeError("转换器未生成非空 PDF")
                    import pymupdf
                    images = []
                    with pymupdf.open(pdf) as rendered:
                        if not len(rendered):
                            raise RuntimeError("PDF 无页面")
                        for i, page in enumerate(rendered, 1):
                            target = temp / f"page_{i:03}.png"
                            page.get_pixmap(dpi=dpi, alpha=False).save(target)
                            images.append(target)
                    # Separate run directory prevents stale pages from appearing in new results.
                    run_dir = output_dir / f"run_{uuid.uuid4().hex[:12]}"
                    run_dir.mkdir()
                    final_pdf = run_dir / "document.pdf"
                    shutil.copyfile(pdf, final_pdf)
                    final_images = []
                    for image in images:
                        target = run_dir / image.name
                        shutil.copyfile(image, target)
                        final_images.append(str(target))
                    result = RenderResult("SUCCESS", choice, str(final_pdf), final_images,
                                          "已对私有副本完成 PDF 和逐页 PNG 渲染；未作视觉质量判定。" + (" 后端回退记录：" + "；".join(errors) if errors else ""))
                    break
            except (OSError, RuntimeError, subprocess.SubprocessError, ImportError, ValueError) as exc:
                errors.append(f"{choice}: {exc}")
                result = RenderResult("RENDER_FAILED", choice, message="；".join(errors))
    result.source_unchanged = sha256(source) == document.sha256
    if not result.source_unchanged:
        raise DocumentFactoryError("INPUT_CHANGED：渲染期间原始 DOCX 发生变化")
    manifest = checked_output(output_dir / "render_result.json", root, "output", source)
    manifest.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    return result
