"""DocumentFactory: audit DOCX files and normalize only into protected copies."""
__version__ = "0.5.0a1"

from .normalizer import normalize
from .template import analyze_template, apply_template, TemplateProfile
from .templates import (
    TemplateAlreadyRegisteredError,
    TemplateDefinition,
    TemplateNotFoundError,
    TemplateSchemaError,
    list_templates,
    load_template,
    load_template_from_yaml,
)

__all__ = [
    "__version__",
    "normalize",
    "TemplateProfile",
    "analyze_template",
    "apply_template",
    "TemplateDefinition",
    "TemplateAlreadyRegisteredError",
    "TemplateNotFoundError",
    "TemplateSchemaError",
    "list_templates",
    "load_template",
    "load_template_from_yaml",
]
