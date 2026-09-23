"""Template Library & Registry.

Prescriptive Word format templates. A TemplateDefinition defines the target
format for a class of documents; the operations layer consumes its rules
verbatim to produce DOCX output deterministically.

Public API:

- schema:   TemplateDefinition, TemplateRules, BodyRule, HeadingRule,
            TableRule, TemplateSummary
- registry: TemplateRegistry, TemplateNotFoundError,
            TemplateAlreadyRegisteredError
- loader:   load_template, load_template_from_yaml, build_registry,
            default_registry, list_templates, TemplateSchemaError
"""
from .loader import (
    TemplateSchemaError,
    build_registry,
    default_registry,
    default_templates_dir,
    list_templates,
    load_template,
    load_template_from_yaml,
)
from .registry import (
    TemplateAlreadyRegisteredError,
    TemplateNotFoundError,
    TemplateRegistry,
)
from .schema import (
    BodyRule,
    HeadingRule,
    TableRule,
    TemplateDefinition,
    TemplateRules,
    TemplateSummary,
)

__all__ = [
    "BodyRule",
    "HeadingRule",
    "TableRule",
    "TemplateDefinition",
    "TemplateRules",
    "TemplateSummary",
    "TemplateRegistry",
    "TemplateNotFoundError",
    "TemplateAlreadyRegisteredError",
    "TemplateSchemaError",
    "load_template",
    "load_template_from_yaml",
    "build_registry",
    "default_registry",
    "default_templates_dir",
    "list_templates",
]
