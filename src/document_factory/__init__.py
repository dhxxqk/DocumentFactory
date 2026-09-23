"""DocumentFactory: audit DOCX files and normalize only into protected copies."""
__version__ = "0.5.0a1"

from .normalizer import normalize
from .template import analyze_template, apply_template, TemplateProfile
from .template_runner import ExecutionResult, run_template
from .templates import (
    TemplateAlreadyRegisteredError,
    TemplateDefinition,
    TemplateNotFoundError,
    TemplateSchemaError,
    list_templates,
    load_template,
    load_template_from_yaml,
)
from .generation import (
    DocumentGenerationService,
    GenerationRequest,
    GenerationResult,
    generate_document,
)
from .analyzer import DocumentProfile, analyze_document
from .conversion import (
    ConversionResult,
    DocumentFormatConverter,
    DocumentInputProvider,
    convert_document,
    load_input_docx,
)

__all__ = [
    "__version__",
    "normalize",
    "TemplateProfile",
    "analyze_template",
    "apply_template",
    "ExecutionResult",
    "run_template",
    "TemplateDefinition",
    "TemplateAlreadyRegisteredError",
    "TemplateNotFoundError",
    "TemplateSchemaError",
    "list_templates",
    "load_template",
    "load_template_from_yaml",
    "DocumentGenerationService",
    "GenerationRequest",
    "GenerationResult",
    "generate_document",
    "DocumentProfile",
    "analyze_document",
    "ConversionResult",
    "DocumentFormatConverter",
    "DocumentInputProvider",
    "convert_document",
    "load_input_docx",
]
