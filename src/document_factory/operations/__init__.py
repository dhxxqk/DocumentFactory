"""Formatting Operation Layer.

The shared deterministic execution base for the rule engine, the template
engine and future AI-driven callers. Operations apply exact, already-resolved
format profiles to OOXML elements; they contain no LLM calls, no semantic
inference and no "does this need fixing?" decisions.

Public API:

- font:       FontProfile, apply_font and granular font operations
- paragraph:  ParagraphProfile, apply_paragraph_format and granular operations
- style:      STYLE_ROLES, find_style_element, apply_style
- table:      apply_table_font, apply_table_alignment, apply_table_format
- document:   PageFormat, apply_section_properties
- support:    OperationContext, write_package, atomic_text
"""
from ._oxml import OperationContext
from ._package import atomic_text, write_package
from .document import HEADER_FOOTER_MIGRATION_SUPPORTED, PageFormat, apply_section_properties
from .font import (
    FontProfile,
    apply_bold,
    apply_color,
    apply_east_asian_font,
    apply_font,
    apply_font_size,
    apply_italic,
    apply_latin_font,
    apply_underline,
)
from .paragraph import (
    ParagraphProfile,
    apply_alignment,
    apply_indent,
    apply_paragraph_format,
    apply_spacing,
)
from .style import STYLE_ROLES, apply_style, find_style_element
from .table import apply_table_alignment, apply_table_font, apply_table_format

__all__ = [
    "OperationContext",
    "atomic_text",
    "write_package",
    "HEADER_FOOTER_MIGRATION_SUPPORTED",
    "PageFormat",
    "apply_section_properties",
    "FontProfile",
    "apply_bold",
    "apply_color",
    "apply_east_asian_font",
    "apply_font",
    "apply_font_size",
    "apply_italic",
    "apply_latin_font",
    "apply_underline",
    "ParagraphProfile",
    "apply_alignment",
    "apply_indent",
    "apply_paragraph_format",
    "apply_spacing",
    "STYLE_ROLES",
    "apply_style",
    "find_style_element",
    "apply_table_alignment",
    "apply_table_font",
    "apply_table_format",
]
