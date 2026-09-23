"""GenerationRequest validation tests (TASK_DOC_010 Test 1)."""
from __future__ import annotations

import pytest

from document_factory.generation import GenerationRequest
from document_factory.models import DocumentFactoryError


def test_rejects_empty_template_id():
    with pytest.raises(DocumentFactoryError):
        GenerationRequest(template_id="", content_source="markdown", input_data={"text": "x"})


def test_rejects_whitespace_template_id():
    with pytest.raises(DocumentFactoryError):
        GenerationRequest(template_id="   ", content_source="markdown", input_data={"text": "x"})


def test_rejects_unsupported_content_source():
    with pytest.raises(DocumentFactoryError):
        GenerationRequest(template_id="T", content_source="html", input_data={"text": "x"})


def test_rejects_empty_input_data():
    with pytest.raises(DocumentFactoryError):
        GenerationRequest(template_id="T", content_source="markdown", input_data={})


def test_rejects_input_data_without_file_or_text():
    with pytest.raises(DocumentFactoryError):
        GenerationRequest(template_id="T", content_source="markdown", input_data={"foo": "bar"})


def test_accepts_file_source():
    req = GenerationRequest(
        template_id="GRID_TECH_V1_4",
        content_source="markdown",
        input_data={"file": "sample.md"},
    )
    assert req.template_id == "GRID_TECH_V1_4"
    assert req.output_path is None
    assert req.metadata == {}


def test_accepts_text_source_with_optional_fields():
    req = GenerationRequest(
        template_id="GRID_TECH_V1_4",
        content_source="markdown",
        input_data={"text": "标题"},
        output_path="output/out.docx",
        metadata={"rules_path": "rules/grid_tech_v1_4.yaml"},
    )
    assert req.output_path == "output/out.docx"
    assert req.metadata == {"rules_path": "rules/grid_tech_v1_4.yaml"}
