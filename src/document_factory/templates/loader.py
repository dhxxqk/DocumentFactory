"""Template Loader: YAML -> TemplateDefinition and default registry.

Provides two entry points:

- ``load_template_from_yaml(path)`` reads a single template YAML into a
  TemplateDefinition, with strict schema validation. Templates declaring
  ``extends`` are resolved against sibling template directories.
- ``load_template(template_id)`` looks up a template in the default
  Registry, which is built by scanning the project's ``templates/`` data
  directory (one subdirectory per template, each containing a
  ``template.yaml``).

Two composition mechanisms (TASK_DOC_012 default specification):

- ``rules_include``: a template YAML may list relative fragment files whose
  top-level sections (page/body/headings/tables/...) are deep-merged in
  order, then inline ``rules`` win. This keeps the normative spec split
  into page/paragraph/heading/table/figure files while the loader and
  schema still see one complete rules mapping.
- ``extends: PARENT_TEMPLATE_ID``: a business template inherits rules and
  metadata from a parent (e.g. DEFAULT_TECHNICAL_DOCUMENT_V1) by recursive
  deep merge; dict keys are merged, lists/scalars are replaced by the
  child. Identity fields (id/name/version/category/description) always
  come from the child. Cycles and missing parents fail the build.

The default Registry is built lazily on first access so that importing the
module never performs filesystem work; tests that bring their own Registry
are not affected by the project seed templates.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from ..models import DocumentFactoryError
from .registry import (
    TemplateAlreadyRegisteredError,
    TemplateNotFoundError,
    TemplateRegistry,
)
from .schema import TemplateDefinition


class TemplateSchemaError(DocumentFactoryError):
    """Raised when a template YAML is missing fields or has wrong types."""


def deep_merge(base, override):
    """Recursively merge two mappings; lists/scalars in ``override`` win.

    Neither input is mutated. Used for both rules-fragment composition and
    parent -> child template inheritance.
    """
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    return deepcopy(override)


def _compose_rules(data: dict, template_dir: Path) -> dict:
    """Merge ``rules_include`` fragments and inline rules into ``data``.

    Fragments are merged in listed order; inline ``rules`` take precedence.
    Mutates and returns ``data`` for convenience.
    """
    rules: dict = {}
    for relative in data.get("rules_include") or []:
        fragment_path = (template_dir / relative).resolve()
        fragment = _load_yaml(fragment_path)
        if not isinstance(fragment, dict):
            raise TemplateSchemaError(
                f"规则分片顶层必须是映射 ({fragment_path})"
            )
        rules = deep_merge(rules, fragment)
    if data.get("rules"):
        rules = deep_merge(rules, data["rules"])
    if rules:
        data["rules"] = rules
    return data


def _project_root() -> Path:
    """Project root as resolved from this module file.

    src/document_factory/templates/loader.py -> parents[3] = project root.
    """
    return Path(__file__).resolve().parents[3]


def default_templates_dir() -> Path:
    """Default on-disk templates directory (project root ``templates/``)."""
    return _project_root() / "templates"


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        raise TemplateSchemaError(f"模板 YAML 无法读取 ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise TemplateSchemaError(f"模板 YAML 顶层必须是映射 ({path})")
    return data


def load_template_from_yaml(path: str | Path) -> TemplateDefinition:
    """Read a single template YAML into a TemplateDefinition.

    ``rules_include`` fragments are composed. A template declaring
    ``extends`` is resolved by building the registry of its sibling
    template directory (``<templates>/<id>/template.yaml`` convention);
    standalone extending templates therefore need the parent present on
    disk next to them.
    """
    resolved = Path(path).resolve()
    data = _compose_rules(_load_yaml(resolved), resolved.parent)
    if data.get("extends"):
        templates_dir = resolved.parents[1]
        registry = build_registry(templates_dir)
        try:
            return registry.get_template(data["id"])
        except TemplateNotFoundError:
            raise TemplateSchemaError(
                f"模板 {data.get('id', resolved)} 声明 extends="
                f"{data['extends']}，但无法在 {templates_dir} 解析继承链"
            ) from None
    try:
        return TemplateDefinition.from_dict(data, source_path=resolved)
    except DocumentFactoryError as exc:
        raise TemplateSchemaError(f"模板 YAML 校验失败 ({resolved}): {exc}") from exc


def _read_entry(yaml_path: Path) -> dict:
    return _compose_rules(_load_yaml(yaml_path), yaml_path.parent)


def _resolve_inheritance(
    template_id: str,
    entries: dict[str, tuple[Path, dict]],
    resolved: dict[str, TemplateDefinition],
    chain: tuple[str, ...] = (),
) -> TemplateDefinition:
    """Deep-merge parent entries into ``template_id`` and validate."""
    if template_id in resolved:
        return resolved[template_id]
    if template_id in chain:
        cycle = " -> ".join((*chain, template_id))
        raise TemplateSchemaError(f"模板继承存在循环：{cycle}")
    yaml_path, data = entries[template_id]
    parent_id = data.get("extends")
    if parent_id:
        if parent_id not in entries:
            raise TemplateSchemaError(
                f"模板 {template_id} ({yaml_path}) 声明 extends={parent_id}，"
                "但该父模板未在模板目录中注册"
            )
        _resolve_inheritance(parent_id, entries, resolved, (*chain, template_id))
        parent_data = entries[parent_id][1]
        # 直接深合并两份已组装 raw data，子字段覆盖父字段（identity 字段
        # 同样被子字段覆盖，故子模板必须自带完整身份信息）。
        merged = deep_merge(parent_data, data)
    else:
        merged = data
    try:
        definition = TemplateDefinition.from_dict(merged, source_path=yaml_path)
    except DocumentFactoryError as exc:
        raise TemplateSchemaError(f"模板 YAML 校验失败 ({yaml_path}): {exc}") from exc
    resolved[template_id] = definition
    return definition


def build_registry(templates_dir: str | Path | None = None) -> TemplateRegistry:
    """Scan a directory and build a Registry from ``*/template.yaml`` files.

    Each subdirectory of ``templates_dir`` may contain a ``template.yaml``;
    subdirectories without one are skipped silently. Rule fragments are
    composed and ``extends`` chains are deep-merged before validation.
    Schema errors, missing parents, inheritance cycles and duplicate ids
    abort the build.
    """
    root = Path(templates_dir).resolve() if templates_dir else default_templates_dir()
    registry = TemplateRegistry()
    if not root.is_dir():
        return registry
    entries: dict[str, tuple[Path, dict]] = {}
    for yaml_path in sorted(root.glob("*/template.yaml")):
        data = _read_entry(yaml_path)
        template_id = data.get("id")
        if not isinstance(template_id, str):
            raise TemplateSchemaError(f"模板缺少有效 id ({yaml_path})")
        if template_id in entries:
            raise TemplateAlreadyRegisteredError(f"模板 id 重复：{template_id}")
        entries[template_id] = (yaml_path, data)
    resolved: dict[str, TemplateDefinition] = {}
    for template_id in sorted(entries):
        registry.register_template(
            _resolve_inheritance(template_id, entries, resolved)
        )
    return registry


_default_registry: TemplateRegistry | None = None


def default_registry() -> TemplateRegistry:
    """Return the lazily-built default Registry from project templates/."""
    global _default_registry
    if _default_registry is None:
        _default_registry = build_registry()
    return _default_registry


def load_template(template_id: str) -> TemplateDefinition:
    """Look up a template by id in the default Registry.

    Raises TemplateNotFoundError if the id is not registered.
    """
    return default_registry().get_template(template_id)


def list_templates():
    """Return summaries of all templates in the default Registry."""
    return default_registry().list_templates()


__all__ = [
    "TemplateSchemaError",
    "load_template",
    "load_template_from_yaml",
    "build_registry",
    "default_registry",
    "default_templates_dir",
    "list_templates",
    "TemplateAlreadyRegisteredError",
    "TemplateNotFoundError",
]
