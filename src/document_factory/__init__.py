"""DocumentFactory: audit DOCX files and normalize only into protected copies."""
__version__ = "0.5.0a1"

from .normalizer import normalize
from .template import analyze_template, apply_template, TemplateProfile

__all__ = ["__version__", "normalize", "TemplateProfile", "analyze_template", "apply_template"]
