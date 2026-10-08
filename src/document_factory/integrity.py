"""Content Integrity Gate — 内容不可变守卫。

DocumentFactory 的一切操作只允许改格式。本模块在规范化前后对以下内容做
逐字/逐字节比对，任何不一致都抛出 ``ContentIntegrityError`` 中止流程：

- word/document.xml 全部故事段落文本（含表格单元格，按文档顺序）；
- word/media/* 每个部件的字节数与 SHA-256（图片内容不得改变）；
- 图片嵌入引用顺序（a:blip@r:embed 与 VML v:imagedata@r:id）；
- 图片显示尺寸（wp:extent cx/cy 序列）；
- word/_rels/document.xml.rels 中图片关系目标；
- 表格数量与 section 方向序列（portrait/landscape 结构不得被破坏）。

纯确定性实现：不调用任何外部服务，不做语义判断。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from zipfile import ZipFile

from lxml import etree

from .models import DocumentFactoryError

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V_NS = "urn:schemas-microsoft-com:vml"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

MEDIA_PREFIX = "word/media/"
IMAGE_REL_TYPE_SUFFIX = "/image"


class ContentIntegrityError(DocumentFactoryError):
    """Raised when a normalization would change protected document content."""


@dataclass(frozen=True)
class ContentFingerprint:
    """Immutable snapshot of the content that must survive normalization."""

    source_path: str
    texts: list[str]
    media: dict[str, dict]
    image_rels: dict[str, str]
    embeds: list[list]
    extents: list[list]
    table_count: int
    section_sequence: list[str]

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "paragraph_count": len(self.texts),
            "text_chars": sum(len(t) for t in self.texts),
            "media_parts": len(self.media),
            "media": self.media,
            "image_relationship_count": len(self.image_rels),
            "embed_count": len(self.embeds),
            "extent_count": len(self.extents),
            "table_count": self.table_count,
            "section_sequence": self.section_sequence,
        }


def _story_texts(document) -> list[str]:
    return [p.text for p in document.paragraphs if p.part == "word/document.xml"]


def _extract_embeds(root) -> list[list]:
    """Ordered image references: [kind, rId] for blip@embed + imagedata@id."""
    result: list[list] = []
    for node in root.iter():
        tag = etree.QName(node).localname
        namespace = etree.QName(node).namespace
        if namespace == A_NS and tag == "blip":
            rid = node.get(f"{{{R_NS}}}embed")
            if rid:
                result.append(["blip", rid])
        elif namespace == V_NS and tag == "imagedata":
            rid = node.get(f"{{{R_NS}}}id")
            if rid:
                result.append(["imagedata", rid])
    return result


def _extract_extents(root) -> list[list]:
    """Ordered wp:extent [cx, cy] pairs (inline/anchor image display size)."""
    result: list[list] = []
    for node in root.iter(f"{{{WP_NS}}}extent"):
        result.append([node.get("cx"), node.get("cy")])
    return result


def _section_sequence(root) -> list[str]:
    sequence = []
    for sect_pr in root.iter(f"{{{W_NS}}}sectPr"):
        if any(a.tag == f"{{{W_NS}}}sectPrChange" for a in sect_pr.iterancestors()):
            continue
        pg_size = sect_pr.find(f"{{{W_NS}}}pgSz")
        orientation = "portrait"
        if pg_size is not None:
            orient = pg_size.get(f"{{{W_NS}}}orient")
            if orient in ("portrait", "landscape"):
                orientation = orient
            else:
                try:
                    w = int(pg_size.get(f"{{{W_NS}}}w") or 0)
                    h = int(pg_size.get(f"{{{W_NS}}}h") or 0)
                    if w > h:
                        orientation = "landscape"
                except ValueError:
                    pass
        sequence.append(orientation)
    return sequence


def _read_package_facts(path) -> tuple[dict, dict, list, list]:
    """Return (media, image_rels, embeds, extents) directly from a DOCX zip."""
    media: dict[str, dict] = {}
    image_rels: dict[str, str] = {}
    with ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir() or info.filename.endswith("/"):
                continue
            if info.filename.startswith(MEDIA_PREFIX):
                data = archive.read(info.filename)
                media[info.filename] = {
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
        rels_name = "word/_rels/document.xml.rels"
        if rels_name in archive.namelist():
            rels_root = etree.fromstring(archive.read(rels_name))
            for relation in rels_root:
                rel_type = relation.get("Type", "")
                target = relation.get("Target")
                if rel_type.endswith(IMAGE_REL_TYPE_SUFFIX) and target:
                    image_rels[relation.get("Id")] = target
        document_root = etree.fromstring(archive.read("word/document.xml"))
    return media, image_rels, _extract_embeds(document_root), _extract_extents(document_root)


def capture_fingerprint(source_path, document=None) -> ContentFingerprint:
    """Snapshot the protected content of a source DOCX."""
    source_path = str(source_path)
    media, image_rels, embeds, extents = _read_package_facts(source_path)
    if document is not None:
        root = document.parts.get("word/document.xml")
        texts = _story_texts(document)
        embeds = _extract_embeds(root) if root is not None else embeds
        extents = _extract_extents(root) if root is not None else extents
        table_count = len(document.tables)
        section_sequence = _section_sequence(root) if root is not None else []
    else:
        with ZipFile(source_path) as archive:
            document_root = etree.fromstring(archive.read("word/document.xml"))
        texts = [
            "".join(node.text or "" for node in paragraph.iter(f"{{{W_NS}}}t"))
            for paragraph in document_root.iter(f"{{{W_NS}}}p")
        ]
        table_count = len(document_root.findall(f".//{{{W_NS}}}tbl"))
        section_sequence = _section_sequence(document_root)
    return ContentFingerprint(
        source_path=source_path,
        texts=texts,
        media=media,
        image_rels=image_rels,
        embeds=embeds,
        extents=extents,
        table_count=table_count,
        section_sequence=section_sequence,
    )


def _check(name: str, ok: bool, before, after) -> dict:
    return {"check": name, "passed": bool(ok), "before": before, "after": after}


def verify_content(
    fingerprint: ContentFingerprint,
    *,
    document=None,
    output_path=None,
    raise_on_failure: bool = True,
) -> dict:
    """Verify a (possibly normalized) document against a content fingerprint.

    - ``document``: in-memory Document to compare texts/structure against;
    - ``output_path``: written DOCX whose media/embeds/extents/rels are
      compared at byte level.
    Returns a result dict ``{passed, checks}`` and raises on failure unless
    ``raise_on_failure`` is False.
    """
    checks: list[dict] = []

    if document is not None:
        actual_texts = _story_texts(document)
        checks.append(_check(
            "paragraph_text", actual_texts == fingerprint.texts,
            {"paragraphs": len(fingerprint.texts),
             "chars": sum(len(t) for t in fingerprint.texts)},
            {"paragraphs": len(actual_texts),
             "chars": sum(len(t) for t in actual_texts)},
        ))
        root = document.parts.get("word/document.xml")
        if root is not None:
            actual_embeds = _extract_embeds(root)
            checks.append(_check(
                "image_embed_order", actual_embeds == fingerprint.embeds,
                fingerprint.embeds, actual_embeds,
            ))
            actual_extents = _extract_extents(root)
            checks.append(_check(
                "image_extents", actual_extents == fingerprint.extents,
                fingerprint.extents, actual_extents,
            ))
            actual_sections = _section_sequence(root)
            checks.append(_check(
                "section_sequence", actual_sections == fingerprint.section_sequence,
                fingerprint.section_sequence, actual_sections,
            ))
        checks.append(_check(
            "table_count", len(document.tables) == fingerprint.table_count,
            fingerprint.table_count, len(document.tables),
        ))

    if output_path is not None:
        media, image_rels, embeds, extents = _read_package_facts(output_path)
        checks.append(_check(
            "media_parts", media == fingerprint.media,
            fingerprint.media, media,
        ))
        checks.append(_check(
            "image_relationships", image_rels == fingerprint.image_rels,
            fingerprint.image_rels, image_rels,
        ))
        checks.append(_check(
            "package_embed_order", embeds == fingerprint.embeds,
            fingerprint.embeds, embeds,
        ))
        checks.append(_check(
            "package_extents", extents == fingerprint.extents,
            fingerprint.extents, extents,
        ))

    failures = [c for c in checks if not c["passed"]]
    result = {"passed": not failures, "checks": checks}
    if failures and raise_on_failure:
        labels = ", ".join(c["check"] for c in failures)
        raise ContentIntegrityError(
            f"CONTENT_INTEGRITY_GATE_FAILED：{labels}；已中止写出/继续处理"
        )
    return result
