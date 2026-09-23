"""Exception handling: missing template raises TemplateNotFoundError (Test 4)."""
from __future__ import annotations

import pytest

from conftest import ROOT
from document_factory.generation import GenerationRequest, generate_document
from document_factory.templates import TemplateNotFoundError


def test_generate_unknown_template_raises_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = tmp_path / "sample.md"
    md.write_text("# 标题\n\n正文\n", encoding="utf-8")
    request = GenerationRequest(
        template_id="DOES_NOT_EXIST",
        content_source="markdown",
        input_data={"file": str(md)},
        metadata={"rules_path": str(ROOT / "rules/grid_tech_v1_4.yaml")},
    )
    with pytest.raises(TemplateNotFoundError):
        generate_document(request)
