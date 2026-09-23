"""Template Loader: YAML -> TemplateDefinition and default registry.

Provides two entry points:

- ``load_template_from_yaml(path)`` reads a single template YAML into a
  TemplateDefinition, with strict schema validation.
- ``load_template(template_id)`` looks up a template in the default
  Registry, which is built by scanning the project's ``templates/`` data
  directory (one subdirectory per template, each containing a
  ``template.yaml``).

The default Registry is built lazily on first access so that importing the
module never performs filesystem work; tests that bring their own Registry
are not affected by the project seed templates.
"""
from __future__ import annotations

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

    Does not touch the Registry; callers may register the result themselves
    or use ``load_template`` for the default-registry path.
    """
    resolved = Path(path).resolve()
    data = _load_yaml(resolved)
    try:
        return TemplateDefinition.from_dict(data, source_path=resolved)
    except DocumentFactoryError as exc:
        raise TemplateSchemaError(f"模板 YAML 校验失败 ({resolved}): {exc}") from exc


def build_registry(templates_dir: str | Path | None = None) -> TemplateRegistry:
    """Scan a directory and build a Registry from ``*/template.yaml`` files.

    Each subdirectory of ``templates_dir`` may contain a ``template.yaml``;
    subdirectories without one are skipped silently. Schema errors abort the
    build; duplicate ids abort the build.
    """
    root = Path(templates_dir).resolve() if templates_dir else default_templates_dir()
    registry = TemplateRegistry()
    if not root.is_dir():
        return registry
    for yaml_path in sorted(root.glob("*/template.yaml")):
        definition = load_template_from_yaml(yaml_path)
        registry.register_template(definition)
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
