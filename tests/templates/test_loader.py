"""Unit tests for the template loader (templates.loader)."""
from __future__ import annotations

import pytest

from document_factory.models import DocumentFactoryError
from document_factory.templates import (
    TemplateAlreadyRegisteredError,
    TemplateDefinition,
    TemplateNotFoundError,
    TemplateSchemaError,
    build_registry,
    default_registry,
    default_templates_dir,
    list_templates,
    load_template,
    load_template_from_yaml,
)


def _write_template_yaml(path, *, template_id="TECH_REPORT_V1", name="技术报告"):
    content = f"""
id: {template_id}
name: {name}
version: "1.0"
category:
  - report
description: 示例模板
metadata:
  author: dhxxqk
  created_at: "2026-09-23"
rules:
  page:
    page_size: A4
    orientation: portrait
  body:
    style_name: 正文
    chinese_font: 仿宋
    latin_font: Times New Roman
    font_size_pt: 12
    first_line_indent_chars: 2
    line_spacing: 1.5
    space_before_pt: 0
    space_after_pt: 0
    alignment: both
  headings:
    h1:
      word_style: Heading 1
      chinese_font: 黑体
      latin_font: Times New Roman
      size_pt: 16
      color: "000000"
      bold: true
      alignment: left
  tables:
    header_font: 黑体
    body_font: 仿宋
    latin_font: Times New Roman
    font_size_pt: 10.5
    alignment: center
  font_aliases:
    仿宋: [仿宋, FangSong]
"""
    path.write_text(content, encoding="utf-8")


# ---- load_template_from_yaml --------------------------------------------

def test_load_template_from_yaml_returns_definition(tmp_path):
    yaml_path = tmp_path / "template.yaml"
    _write_template_yaml(yaml_path)
    definition = load_template_from_yaml(yaml_path)
    assert isinstance(definition, TemplateDefinition)
    assert definition.id == "TECH_REPORT_V1"
    assert definition.name == "技术报告"
    assert definition.source_path == str(yaml_path.resolve())
    assert definition.rules.body.chinese_font == "仿宋"
    assert definition.rules.headings["h1"].size_pt == 16
    assert definition.rules.tables.font_size_pt == 10.5
    assert definition.rules.font_aliases["仿宋"] == ["仿宋", "FangSong"]


def test_load_template_from_yaml_missing_file_raises(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(TemplateSchemaError):
        load_template_from_yaml(missing)


def test_load_template_from_yaml_missing_required_field_raises(tmp_path):
    yaml_path = tmp_path / "template.yaml"
    yaml_path.write_text("id: ONLY_ID\nname: 只有 id\n", encoding="utf-8")
    with pytest.raises(TemplateSchemaError) as exc:
        load_template_from_yaml(yaml_path)
    assert "version" in str(exc.value) or "缺少" in str(exc.value)


def test_load_template_from_yaml_top_level_not_mapping_raises(tmp_path):
    yaml_path = tmp_path / "template.yaml"
    yaml_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(TemplateSchemaError):
        load_template_from_yaml(yaml_path)


def test_load_template_from_yaml_invalid_yaml_raises(tmp_path):
    yaml_path = tmp_path / "template.yaml"
    yaml_path.write_text("id: \n  bad: : : :\n", encoding="utf-8")
    with pytest.raises(TemplateSchemaError):
        load_template_from_yaml(yaml_path)


def test_load_template_from_yaml_optional_tables_can_be_omitted(tmp_path):
    yaml_path = tmp_path / "template.yaml"
    content = """
id: NO_TABLES
name: 无表格模板
version: "1.0"
category: [report]
description: 测试 tables 可选
rules:
  page: {page_size: A4}
  body:
    style_name: 正文
    chinese_font: 仿宋
    latin_font: Times New Roman
    font_size_pt: 12
    first_line_indent_chars: 2
    line_spacing: 1.5
    space_before_pt: 0
    space_after_pt: 0
    alignment: both
  headings:
    h1:
      word_style: Heading 1
      chinese_font: 黑体
      latin_font: Times New Roman
      size_pt: 16
      color: "000000"
      bold: true
      alignment: left
"""
    yaml_path.write_text(content, encoding="utf-8")
    definition = load_template_from_yaml(yaml_path)
    assert definition.rules.tables is None
    assert definition.rules.font_aliases == {}


# ---- build_registry -----------------------------------------------------

def _make_templates_root(tmp_path):
    root = tmp_path / "templates"
    sub_a = root / "template_a"
    sub_b = root / "template_b"
    sub_a.mkdir(parents=True)
    sub_b.mkdir(parents=True)
    _write_template_yaml(sub_a / "template.yaml", template_id="A", name="A 模板")
    _write_template_yaml(sub_b / "template.yaml", template_id="B", name="B 模板")
    return root


def test_build_registry_loads_all_subdirectories(tmp_path):
    root = _make_templates_root(tmp_path)
    registry = build_registry(root)
    assert registry.has_template("A")
    assert registry.has_template("B")
    summaries = registry.list_templates()
    assert [s.id for s in summaries] == ["A", "B"]


def test_build_registry_skips_subdirectories_without_template_yaml(tmp_path):
    root = tmp_path / "templates"
    sub_a = root / "template_a"
    empty = root / "empty"
    sub_a.mkdir(parents=True)
    empty.mkdir(parents=True)
    _write_template_yaml(sub_a / "template.yaml", template_id="A", name="A 模板")
    (empty / "note.txt").write_text("not a template", encoding="utf-8")
    registry = build_registry(root)
    assert registry.list_templates().__len__() == 1


def test_build_registry_missing_directory_returns_empty_registry(tmp_path):
    registry = build_registry(tmp_path / "no_such_dir")
    assert registry.list_templates() == []


def test_build_registry_duplicate_ids_raises(tmp_path):
    root = tmp_path / "templates"
    sub_a = root / "template_a"
    sub_b = root / "template_b"
    sub_a.mkdir(parents=True)
    sub_b.mkdir(parents=True)
    _write_template_yaml(sub_a / "template.yaml", template_id="DUP", name="A 模板")
    _write_template_yaml(sub_b / "template.yaml", template_id="DUP", name="B 模板")
    with pytest.raises(TemplateAlreadyRegisteredError):
        build_registry(root)


# ---- default registry & seed template -----------------------------------

def test_default_templates_dir_resolves_to_project_root():
    path = default_templates_dir()
    assert path.name == "templates"
    # The seed template ships with the repo, so this directory must exist.
    assert path.is_dir()


def test_default_registry_loads_seed_grid_tech_v1_4():
    registry = default_registry()
    assert registry.has_template("GRID_TECH_V1_4")


def test_load_template_by_id_returns_seed_definition():
    definition = load_template("GRID_TECH_V1_4")
    assert definition.id == "GRID_TECH_V1_4"
    assert definition.name == "电网科技项目实施方案模板"
    assert definition.rules.body.chinese_font == "仿宋"
    assert definition.rules.body.font_size_pt == 12
    assert set(definition.rules.headings) >= {"h1", "h2", "h3"}
    assert definition.rules.headings["h1"].size_pt == 16
    assert definition.rules.tables is not None
    assert definition.rules.tables.font_size_pt == 10.5


def test_load_template_unknown_id_raises_not_found():
    with pytest.raises(TemplateNotFoundError):
        load_template("DOES_NOT_EXIST")


def test_list_templates_includes_seed_template():
    summaries = list_templates()
    ids = [s.id for s in summaries]
    assert "GRID_TECH_V1_4" in ids


def test_schema_error_is_document_factory_error():
    assert issubclass(TemplateSchemaError, DocumentFactoryError)
