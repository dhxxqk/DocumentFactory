from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Run:
    text: str
    properties: dict
    element: Any = field(default=None, repr=False)


@dataclass
class Paragraph:
    index: int
    part: str
    text: str
    style_id: str
    properties: dict
    runs: list[Run]
    page_break: bool = False
    table: int | None = None
    row: int | None = None
    cell: int | None = None
    in_toc: bool = False
    element: Any = field(default=None, repr=False)

    @property
    def location(self):
        value = f"{self.part} / Paragraph {self.index}"
        if self.table is not None:
            value += f" / Table {self.table}, Row {self.row}, Cell {self.cell}"
        return value + (f" / {self.text[:70]}" if self.text else "")


@dataclass
class Style:
    style_id: str
    name: str
    kind: str
    based_on: str | None
    properties: dict
    custom: bool = False
    default: bool = False


@dataclass
class Field:
    instruction: str
    part: str
    paragraph_index: int
    complete: bool = True

    @property
    def kind(self):
        return self.instruction.strip().split(maxsplit=1)[0].upper() if self.instruction.strip() else ""


@dataclass
class Table:
    index: int
    part: str
    rows: list[dict]
    columns: int
    style_id: str | None = None


@dataclass
class Document:
    path: Any
    sha256: str
    parts: dict
    paragraphs: list[Paragraph]
    styles: dict[str, Style]
    defaults: dict
    default_style: str
    tables: list[Table]
    sections: list[dict]
    fields: list[Field]
    relationships: dict
    diagnostics: list[str]


@dataclass
class Finding:
    rule_id: str
    severity: str
    object_type: str
    location: str
    actual: Any
    expected: Any
    message: str
    status: str = "FAIL"
    source: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class RenderResult:
    status: str
    backend: str = "unavailable"
    pdf: str | None = None
    pages: list[str] = field(default_factory=list)
    message: str = ""
    source_unchanged: bool = True


@dataclass
class NormalizationResult:
    status: str
    input_path: str
    output_path: str
    report_path: str
    input_sha256: str
    output_sha256: str
    before_counts: dict[str, int]
    after_counts: dict[str, int]
    changes: list[dict[str, Any]] = field(default_factory=list)
    remaining_findings: list[dict[str, Any]] = field(default_factory=list)
    source_unchanged: bool = True

    def to_dict(self):
        return asdict(self)


@dataclass
class TemplateApplyResult:
    status: str
    template_path: str
    input_path: str
    output_path: str
    report_path: str
    template_sha256: str
    input_sha256: str
    output_sha256: str
    mappings: list[dict[str, Any]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    validation_mismatches: list[dict[str, Any]] = field(default_factory=list)
    before_lint_counts: dict[str, int] = field(default_factory=dict)
    after_lint_counts: dict[str, int] = field(default_factory=dict)
    template_unchanged: bool = True
    source_unchanged: bool = True

    def to_dict(self):
        return asdict(self)


class DocumentFactoryError(Exception):
    """Expected, user-readable input or execution failure."""
