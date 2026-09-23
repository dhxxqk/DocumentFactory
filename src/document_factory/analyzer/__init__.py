"""Document Analyzer.

Read-only pre-conversion analysis: given an arbitrary DOCX, produce a
``DocumentProfile`` describing *what state the document is in* before any
format conversion. The analyzer never mutates the package and performs no
format decisions — it only counts structure, styles and effective fonts.

Public API:

- profile:          DocumentProfile, analyze_document
"""
from .profile import DocumentProfile, analyze_document

__all__ = ["DocumentProfile", "analyze_document"]
