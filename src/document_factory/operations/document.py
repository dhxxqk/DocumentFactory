"""Deterministic document-level formatting operations.

Current scope: page properties (w:pgSz / w:pgMar) on a section.
Headers and footers are analyzed by the template engine but their migration is
deliberately not implemented yet; no apply operation is exposed for them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ._oxml import SECTPR_ORDER, set_properties

HEADER_FOOTER_MIGRATION_SUPPORTED = False


@dataclass(frozen=True)
class PageFormat:
    width_twips: int | None = None
    height_twips: int | None = None
    orientation: str | None = None
    margins: dict = field(default_factory=dict)

    @classmethod
    def from_section_dict(cls, section):
        """Build from a template extractor section dict."""
        section = section or {}
        size = section.get("size", {})
        margins = {
            key: value.get("twips") if isinstance(value, dict) else value
            for key, value in (section.get("margins") or {}).items()
        }
        return cls(
            width_twips=size.get("width_twips"),
            height_twips=size.get("height_twips"),
            orientation=size.get("orientation"),
            margins=margins,
        )


def apply_section_properties(sect_pr, page, ctx):
    """Apply page size and margins onto a w:sectPr element.

    Returns whether anything changed. Header/footer references are never
    touched.
    """
    page = page if isinstance(page, PageFormat) else PageFormat.from_section_dict(page)
    changed = False
    size_attrs = {
        key: value for key, value in {
            "w": page.width_twips, "h": page.height_twips,
            "orient": page.orientation,
        }.items() if value is not None
    }
    if size_attrs:
        changed |= set_properties(
            sect_pr, "pgSz", size_attrs, set(), ctx,
            prop="page_size", order=SECTPR_ORDER,
        )
    margin_attrs = {
        key: value for key, value in page.margins.items()
        if value is not None and key in ("top", "right", "bottom", "left", "gutter", "header", "footer")
    }
    if margin_attrs:
        changed |= set_properties(
            sect_pr, "pgMar", margin_attrs, set(), ctx,
            prop="page_margins", order=SECTPR_ORDER,
        )
    return changed
