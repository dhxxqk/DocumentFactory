"""DocumentFactory: audit DOCX files and normalize only into protected copies."""
__version__ = "0.2.0a1"

from .normalizer import normalize

__all__ = ["__version__", "normalize"]
