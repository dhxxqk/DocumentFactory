"""Template Analyzer entry point."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..docx_reader import read_docx
from ..models import DocumentFactoryError
from ..output_paths import checked_output
from .extractor import extract_template_data
from .profile import TemplateProfile


def analyze_template(template_path: str | Path, profile_path: str | Path | None = None) -> TemplateProfile:
    """Analyze a DOCX template and optionally persist a versioned JSON profile."""
    root = Path.cwd().resolve()
    source = Path(template_path).resolve()
    if source.suffix.lower() != ".docx":
        raise DocumentFactoryError("模板输入必须是 DOCX 文件")
    document = read_docx(source)
    data = extract_template_data(document)
    profile = TemplateProfile(
        schema_version="1.0",
        template_name=source.stem,
        source_path=str(source),
        source_sha256=document.sha256,
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        **data,
    )
    if profile_path is not None:
        destination = checked_output(profile_path, root, "reports", source)
        profile.save(destination)
    return profile
