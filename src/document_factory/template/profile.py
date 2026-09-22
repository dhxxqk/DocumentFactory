"""Versioned, human-editable Template Profile model."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from ..models import DocumentFactoryError
from ..operations import atomic_text


@dataclass
class TemplateProfile:
    schema_version: str
    template_name: str
    source_path: str
    source_sha256: str
    generated_at: str
    page: dict[str, Any] = field(default_factory=dict)
    headers: list[dict[str, Any]] = field(default_factory=list)
    footers: list[dict[str, Any]] = field(default_factory=list)
    styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    table_styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    table_defaults: dict[str, dict[str, Any]] = field(default_factory=dict)
    numbering: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        destination = Path(path).resolve()
        if destination.suffix.lower() != ".json":
            raise DocumentFactoryError("Template Profile 必须使用 .json 扩展名")
        atomic_text(destination, json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "TemplateProfile":
        source = Path(path).resolve()
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DocumentFactoryError(f"Template Profile 无法读取：{exc}") from exc
        required = {
            "schema_version", "template_name", "source_path", "source_sha256", "generated_at",
            "page", "headers", "footers", "styles", "roles", "table_styles", "table_defaults",
            "numbering", "diagnostics",
        }
        if not isinstance(data, dict) or not required.issubset(data):
            raise DocumentFactoryError("Template Profile 缺少必需字段")
        if data["schema_version"] != "1.0":
            raise DocumentFactoryError(f"不支持的 Template Profile schema：{data['schema_version']}")
        if not isinstance(data["styles"], dict) or not isinstance(data["roles"], dict):
            raise DocumentFactoryError("Template Profile styles/roles 必须是对象")
        return cls(**{name: data[name] for name in required})
