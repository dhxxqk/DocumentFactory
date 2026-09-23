"""Operation plan: typed bag of resolved operation inputs.

The mapper builds an OperationPlan from a TemplateDefinition; the runner
applies it to a Document. The plan reuses the operations-layer profile
dataclasses (FontProfile / ParagraphProfile / PageFormat) verbatim — no
parallel type layer, no translation step.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..operations import FontProfile, PageFormat, ParagraphProfile


@dataclass(frozen=True)
class OperationPlan:
    """Resolved target facts grouped by the role they apply to."""

    body_font: FontProfile
    body_paragraph: ParagraphProfile
    heading_fonts: dict[str, FontProfile] = field(default_factory=dict)
    page: PageFormat | None = None
    table_font: FontProfile | None = None
    table_alignment: str | None = None
    table_style_names: list[str] = field(default_factory=list)

    @property
    def operations_count(self) -> int:
        """Number of operation groups the runner will dispatch.

        Used as a fast sanity figure in tests and reports. One group per
        role: body font, body paragraph, each heading level, page, table.
        """
        count = 2  # body_font + body_paragraph
        count += len(self.heading_fonts)
        if self.page is not None:
            count += 1
        if self.table_font is not None:
            count += 1
        return count
