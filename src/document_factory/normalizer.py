"""Deterministic DOCX normalization: rule decisions, operations execution, validation.

The rule engine owns *decisions* (which object is a heading/body/table cell,
which rule applies, when a direct override is safe to repair). Every actual
OOXML mutation goes through the shared Formatting Operation Layer
(`document_factory.operations`); this module contains no low-level XML writers.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import json
import re

from . import __version__
from . import role_classifier
from .docx_reader import NS, q, read_docx, sha256
from .integrity import verify_content_integrity
from .lint_engine import lint, load_rules
from .models import DocumentFactoryError, NormalizationResult
from .operations import (
    OperationContext,
    PageFormat,
    apply_alignment,
    apply_bold,
    apply_color,
    apply_east_asian_font,
    apply_font_size,
    apply_indent,
    apply_keep_next,
    apply_latin_font,
    apply_section_properties,
    apply_spacing,
    atomic_text,
    find_style_element,
    write_package,
)
from .output_paths import checked_output
from .style_resolver import StyleResolver


UNSUPPORTED_CAPABILITIES = [
    "自动多级编号、numId、lvlOverride，以及手工编号转自动编号",
    "TOC 创建、重建或刷新",
    "Normal 转正文、疑似标题转 Heading，以及编制说明、目录标题、封面等语义重分类",
    "复杂条件表格样式、嵌套/合并单元格表格的直接格式规范化",
    "文本框、浮动对象、修订、RTL、复杂文字和图片中文字",
    "视觉美化以及任何无法被现有 lint 再验证的修改",
]


def _ctx(changes, object_type, location, rules, rule_id, prefix=""):
    return OperationContext(
        changes=changes,
        object_type=object_type,
        location=location,
        rule_id=rule_id,
        source=rules["rules"][rule_id]["source"],
        prefix=prefix,
    )


def _cm_to_twips(value):
    return int(round(float(value) / 2.54 * 1440))


def _normalize_rpr(parent, target, changes, *, object_type, location, rules, prefix="", heading=False):
    """Rule-engine composition: translate a resolved rule target to font ops."""
    changed = False
    if target.get("chinese_font"):
        rule_id = "STYLE005" if object_type == "Style" and heading else "TABLE008" if prefix.startswith("table") else "FONT001"
        changed |= apply_east_asian_font(
            parent, target["chinese_font"],
            _ctx(changes, object_type, location, rules, rule_id, prefix),
            prop="chinese_font",
        )
    if target.get("latin_font"):
        rule_id = "TABLE008" if prefix.startswith("table") else "FONT002"
        changed |= apply_latin_font(
            parent, target["latin_font"],
            _ctx(changes, object_type, location, rules, rule_id, prefix),
            prop="latin_font",
        )
    size = target.get("font_size_pt", target.get("size_pt"))
    if size is not None:
        rule_id = "STYLE005" if object_type == "Style" and heading else "TABLE008" if prefix.startswith("table") else "FONT003"
        changed |= apply_font_size(
            parent, size,
            _ctx(changes, object_type, location, rules, rule_id, prefix),
        )
    if heading:
        changed |= apply_color(
            parent, target["color"],
            _ctx(
                changes, object_type, location, rules,
                "STYLE004" if object_type == "Style" else "FONT004", prefix,
            ),
        )
    return changed


def _normalize_body_ppr(parent, config, changes, *, object_type, location, rules, prefix=""):
    """Rule-engine composition: body paragraph indent/spacing/alignment ops."""
    changed = apply_indent(
        parent, {"firstLineChars": int(config["first_line_indent_chars"] * 100)},
        _ctx(changes, object_type, location, rules, "BODY002", prefix),
        remove=("firstLine", "hanging", "hangingChars"),
    )
    changed |= apply_spacing(
        parent,
        {
            "before": int(config["space_before_pt"] * 20),
            "after": int(config["space_after_pt"] * 20),
            "line": int(config["line_spacing"] * 240),
            "lineRule": "auto",
        },
        _ctx(changes, object_type, location, rules, "BODY003", prefix),
        remove=("beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"),
    )
    changed |= apply_alignment(
        parent, config["alignment"],
        _ctx(changes, object_type, location, rules, "BODY002", prefix),
    )
    return changed


def _normalize_table_ppr(parent, config, changes, *, object_type, location, rules, prefix="table_"):
    """Rule-engine composition: table paragraph indent/spacing ops."""
    changed = apply_indent(
        parent,
        {
            "firstLine": int(config["first_line_indent"]),
            "left": int(config["left_indent"]),
            "right": int(config["right_indent"]),
        },
        _ctx(changes, object_type, location, rules, "TABLE004", prefix),
        remove=(
            "firstLineChars", "hanging", "hangingChars", "leftChars", "rightChars",
            "start", "startChars", "end", "endChars",
        ),
    )
    line = config["normalization_line_spacing"]
    line_attrs = (
        {"line": 240, "lineRule": "auto"}
        if line == "single"
        else {"line": int(config["normalization_exact_line_twips"]), "lineRule": "exact"}
    )
    changed |= apply_spacing(
        parent,
        {
            "before": int(config["space_before_pt"] * 20),
            "after": int(config["space_after_pt"] * 20),
            **line_attrs,
        },
        _ctx(changes, object_type, location, rules, "TABLE007", prefix),
        remove=("beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"),
    )
    return changed


def _normalize_caption_ppr(parent, config, changes, *, location, rules):
    """Caption paragraph: zero indent, single spacing, 6pt before/after, centered."""
    changed = apply_indent(
        parent, {"firstLine": 0, "left": 0, "right": 0},
        _ctx(changes, "Paragraph", location, rules, "CAPTION001"),
        remove=(
            "firstLineChars", "hanging", "hangingChars", "leftChars", "rightChars",
            "start", "startChars", "end", "endChars",
        ),
    )
    line = config.get("line_spacing", "single")
    line_attrs = (
        {"line": 240, "lineRule": "auto"}
        if line == "single"
        else {"line": int(config["line_spacing_twips"]), "lineRule": "exact"}
    )
    changed |= apply_spacing(
        parent,
        {
            "before": int(float(config["space_before_pt"]) * 20),
            "after": int(float(config["space_after_pt"]) * 20),
            **line_attrs,
        },
        _ctx(changes, "Paragraph", location, rules, "CAPTION001"),
        remove=("beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"),
    )
    changed |= apply_alignment(
        parent, config["alignment"],
        _ctx(changes, "Paragraph", location, rules, "CAPTION001"),
    )
    return changed


def _has_character_override(document, run, property_name):
    style_id = run.properties.get("rStyle")
    seen = set()
    while style_id and style_id not in seen:
        seen.add(style_id)
        style = document.styles.get(style_id)
        if style is None:
            break
        rpr = style.properties.get("rPr", {})
        if property_name in rpr:
            return True
        style_id = style.based_on
    return False


def _font_matches(rules, target, actual, expected):
    aliases = [value.casefold() for value in rules.get("font_aliases", {}).get(expected, [expected])]
    return actual is not None and actual.casefold() in aliases


def _normalize_run(document, resolver, paragraph, run, index, role, target, changes, rules):
    if not run.text.strip() or run.element is None or run.properties.get("cs") or run.properties.get("rtl"):
        return False
    effective = resolver.run(paragraph, run)
    location = f"{paragraph.location} / Run {index}"
    direct = run.properties
    changed = False
    has_cn = bool(re.search(r"[㐀-鿿\U00020000-\U0002fa1f]", run.text))
    has_latin = bool(re.search(r"[A-Za-z0-9À-ɏ]", run.text))
    if has_cn:
        actual, _ = resolver.font(effective, "cn")
        slot = direct.get("rFonts", {})
        if actual is None or not _font_matches(rules, target, actual, target["chinese_font"]) or "eastAsiaTheme" in slot:
            if "eastAsia" in slot or "eastAsiaTheme" in slot or _has_character_override(document, run, "rFonts"):
                changed |= apply_east_asian_font(
                    run.element, target["chinese_font"],
                    _ctx(changes, "Run", location, rules, "FONT001"),
                    prop="chinese_font",
                )
    if has_latin and target.get("latin_font"):
        slot = direct.get("rFonts", {})
        actual_ascii, _ = resolver.font(effective, "ascii")
        if actual_ascii is None or not _font_matches(rules, target, actual_ascii, target["latin_font"]) or any(key in slot for key in ("asciiTheme", "hAnsiTheme")):
            if any(key in slot for key in ("ascii", "hAnsi", "asciiTheme", "hAnsiTheme")) or _has_character_override(document, run, "rFonts"):
                changed |= apply_latin_font(
                    run.element, target["latin_font"],
                    _ctx(changes, "Run", location, rules, "FONT002"),
                    prop="latin_font",
                )
    size = target.get("font_size_pt", target.get("size_pt"))
    expected_size = int(float(size) * 2)
    if effective.get("sz") != str(expected_size) and ("sz" in direct or _has_character_override(document, run, "sz")):
        changed |= apply_font_size(
            run.element, size,
            _ctx(changes, "Run", location, rules, "FONT003"),
        )
    if role == "heading":
        color = effective.get("color", {})
        direct_color = direct.get("color")
        if (color.get("val", "").upper() != target["color"] or any(key.startswith("theme") for key in color)) and (direct_color is not None or _has_character_override(document, run, "color")):
            changed |= apply_color(
                run.element, target["color"],
                _ctx(changes, "Run", location, rules, "FONT004"),
            )
        if target.get("bold") is not None and bool(effective.get("b")) != bool(target["bold"]):
            if "b" in direct or _has_character_override(document, run, "b"):
                changed |= apply_bold(
                    run.element, target["bold"],
                    _ctx(changes, "Run", location, rules, "STYLE005"),
                )
    return changed


def _apply_effective_run_target(document, resolver, paragraph, run, index, target, changes, rules, *, prefix=""):
    """Apply a font target whenever the *effective* run format disagrees.

    Unlike ``_normalize_run`` this does not require a direct rPr override:
    safe-Normal body paragraphs, captions and regular table cells usually
    inherit wrong fonts from Normal / docDefaults and must receive direct
    run formatting because their pStyle is deliberately kept.
    """
    if not run.text.strip() or run.element is None or run.properties.get("cs") or run.properties.get("rtl"):
        return False
    effective = resolver.run(paragraph, run)
    location = f"{paragraph.location} / Run {index}"
    changed = False
    has_cn = bool(re.search(r"[㐀-鿿\U00020000-\U0002fa1f]", run.text))
    has_latin = bool(re.search(r"[A-Za-z0-9À-ɏ]", run.text))
    font_rule = "CAPTION002" if prefix == "caption" else "TABLE008" if prefix.startswith("table") else "FONT001"
    latin_rule = "CAPTION002" if prefix == "caption" else "TABLE008" if prefix.startswith("table") else "FONT002"
    size_rule = "CAPTION002" if prefix == "caption" else "TABLE008" if prefix.startswith("table") else "FONT003"
    if has_cn and target.get("chinese_font"):
        actual, _ = resolver.font(effective, "cn")
        if actual is None or not _font_matches(rules, target, actual, target["chinese_font"]):
            changed |= apply_east_asian_font(
                run.element, target["chinese_font"],
                _ctx(changes, "Run", location, rules, font_rule, prefix),
                prop="chinese_font",
            )
    if has_latin and target.get("latin_font"):
        actual_ascii, _ = resolver.font(effective, "ascii")
        if actual_ascii is None or not _font_matches(rules, target, actual_ascii, target["latin_font"]):
            changed |= apply_latin_font(
                run.element, target["latin_font"],
                _ctx(changes, "Run", location, rules, latin_rule, prefix),
                prop="latin_font",
            )
    size = target.get("font_size_pt", target.get("size_pt"))
    if size is not None and effective.get("sz") != str(int(float(size) * 2)):
        changed |= apply_font_size(
            run.element, size,
            _ctx(changes, "Run", location, rules, size_rule, prefix),
        )
    if target.get("bold") is not None and bool(effective.get("b")) != bool(target["bold"]):
        changed |= apply_bold(
            run.element, target["bold"],
            _ctx(changes, "Run", location, rules, font_rule, prefix),
        )
    if target.get("color"):
        color = effective.get("color", {})
        if color.get("val", "").upper() != target["color"].upper() or any(key.startswith("theme") for key in color):
            color_rule = "CAPTION002" if prefix == "caption" else "FONT004"
            changed |= apply_color(
                run.element, target["color"],
                _ctx(changes, "Run", location, rules, color_rule, prefix),
            )
    return changed


def _normalize_sections(document, rules, changes, changed_parts, stats, warnings):
    config = rules["document"]
    root = document.parts.get("word/document.xml")
    if root is None:
        return
    sect_prs = [
        section for section in root.findall(".//w:sectPr", NS)
        if not any(ancestor.tag == q("sectPrChange") for ancestor in section.iterancestors())
    ]
    stats["page"]["sections_total"] = len(sect_prs)
    size_pair = config.get("page_size_twips")
    orientation = config.get("orientation")
    margins_cm = config.get("margins_cm", {})
    for number, sect_pr in enumerate(sect_prs, 1):
        location = f"word/document.xml / Section {number}"
        section_changed = False
        current_orient = sect_pr.find("w:pgSz", NS)
        current_orient = current_orient.get(q("orient"), "portrait") if current_orient is not None else "portrait"
        if size_pair and not (orientation == "portrait" and current_orient == "landscape"):
            width, height = int(size_pair[0]), int(size_pair[1])
            if orientation == "landscape":
                width, height = max(width, height), min(width, height)
            page = PageFormat(
                width_twips=width, height_twips=height, orientation=orientation,
            )
            section_changed |= apply_section_properties(
                sect_pr, page,
                _ctx(changes, "Section", location, rules, "PAGE001"),
            )
        elif current_orient == "landscape":
            warnings.append({
                "kind": "SKIP_LANDSCAPE_SECTION",
                "location": location,
                "reason": "横向节允许用于宽表（PAGE002 WARNING），不强制改回纵向",
            })
        margin_attrs = {
            side: _cm_to_twips(value)
            for side, value in margins_cm.items()
            if side in ("top", "right", "bottom", "left")
        }
        if config.get("header_distance_cm") is not None:
            margin_attrs["header"] = _cm_to_twips(config["header_distance_cm"])
        if config.get("footer_distance_cm") is not None:
            margin_attrs["footer"] = _cm_to_twips(config["footer_distance_cm"])
        if margin_attrs:
            section_changed |= apply_section_properties(
                sect_pr, PageFormat(margins=margin_attrs),
                _ctx(changes, "Section", location, rules, "PAGE003"),
            )
        if section_changed:
            changed_parts.add("word/document.xml")
            stats["page"]["sections_normalized"] += 1


def _normalize_named_styles(document, resolver, rules, changes, changed_parts, stats):
    """Style-element normalization: headings (extended), 正文 and named table styles."""
    heading_styles = {}
    for paragraph in document.paragraphs:
        if paragraph.part == "word/document.xml" and paragraph.table is None and not paragraph.in_toc:
            level = resolver.heading_level(paragraph)
            if level:
                heading_styles[paragraph.style_id] = level
    heading_policy = rules.get("heading_policy") or {}
    for style_id, level in heading_styles.items():
        element = find_style_element(document, style_id)
        if element is None:
            continue
        target = rules[f"heading{level}"]
        changed = _normalize_rpr(
            element, target, changes, object_type="Style",
            location=f"Style {resolver.name(style_id)}", rules=rules, heading=True,
        )
        effective_rpr = resolver.style(style_id).get("rPr", {})
        if target.get("bold") is not None and bool(effective_rpr.get("b")) != bool(target["bold"]):
            changed |= apply_bold(
                element, target["bold"],
                _ctx(changes, "Style", f"Style {resolver.name(style_id)}", rules, "STYLE005"),
            )
        if target.get("alignment") and resolver.style(style_id).get("jc") != target["alignment"]:
            changed |= apply_alignment(
                element, target["alignment"],
                _ctx(changes, "Style", f"Style {resolver.name(style_id)}", rules, "STYLE001"),
            )
        if heading_policy.get("keep_with_next") and not resolver.style(style_id).get("keepNext"):
            changed |= apply_keep_next(
                element, True,
                _ctx(changes, "Style", f"Style {resolver.name(style_id)}", rules, "STYLE001"),
            )
        if changed:
            changed_parts.add("word/styles.xml")
            stats["objects"]["heading_styles"] += 1

    table_names = rules["tables"]["required_styles"] + rules["tables"]["optional_styles"]
    for style in document.styles.values():
        element = find_style_element(document, style.style_id)
        if element is None or style.kind != "paragraph":
            continue
        if style.name == rules["body"]["style_name"]:
            changed = _normalize_body_ppr(element, rules["body"], changes, object_type="Style", location=f"Style {style.name}", rules=rules)
            changed |= _normalize_rpr(element, rules["body"], changes, object_type="Style", location=f"Style {style.name}", rules=rules)
            if changed:
                changed_parts.add("word/styles.xml")
        elif style.name in table_names:
            target = dict(rules["tables"])
            target["chinese_font"] = rules["tables"]["header_font"] if style.name == table_names[0] else rules["tables"]["body_font"]
            changed = _normalize_table_ppr(element, target, changes, object_type="Style", location=f"Style {style.name}", rules=rules)
            changed |= _normalize_rpr(element, target, changes, object_type="Style", location=f"Style {style.name}", rules=rules, prefix="table_")
            if changed:
                changed_parts.add("word/styles.xml")


def _apply_normalization(document, rules):
    resolver = StyleResolver(document)
    classification = role_classifier.classify(document, resolver, rules)
    changes = []
    changed_parts = set()
    warnings = list(classification.warnings)
    stats = {
        "page": {"sections_total": 0, "sections_normalized": 0},
        "objects": Counter(),
        "warnings": warnings,
    }

    _normalize_sections(document, rules, changes, changed_parts, stats, warnings)
    _normalize_named_styles(document, resolver, rules, changes, changed_parts, stats)

    table_config = rules["tables"]
    caption_config = rules.get("caption") or {}
    heading_policy = rules.get("heading_policy") or {}
    regular_tables_seen = set()

    for paragraph in document.paragraphs:
        if paragraph.part != "word/document.xml":
            continue
        info = classification.role(paragraph)
        role = info.role
        if role == "other":
            continue
        location = paragraph.location
        changed = False

        if role == "heading":
            level = info.level
            target = dict(rules[f"heading{level}"])
            stats["objects"]["heading_paragraphs"] += 1
            if target.get("alignment") and paragraph.properties.get("jc") and paragraph.properties["jc"] != target["alignment"]:
                changed |= apply_alignment(
                    paragraph.element, target["alignment"],
                    _ctx(changes, "Paragraph", location, rules, "STYLE001"),
                )
            if heading_policy.get("keep_with_next") and "keepNext" in paragraph.properties and not paragraph.properties["keepNext"]:
                changed |= apply_keep_next(
                    paragraph.element, True,
                    _ctx(changes, "Paragraph", location, rules, "STYLE001"),
                )
            for index, run in enumerate(paragraph.runs, 1):
                changed |= _normalize_run(document, resolver, paragraph, run, index, "heading", target, changes, rules)

        elif role == "body_named":
            target = dict(rules["body"])
            stats["objects"]["body_named_paragraphs"] += 1
            if any(name in paragraph.properties for name in ("ind", "spacing", "jc")):
                changed |= _normalize_body_ppr(paragraph.element, target, changes, object_type="Paragraph", location=location, rules=rules)
            for index, run in enumerate(paragraph.runs, 1):
                changed |= _normalize_run(document, resolver, paragraph, run, index, "body", target, changes, rules)

        elif role == "body_safe_normal":
            target = dict(rules["body"])
            stats["objects"]["body_safe_normal_paragraphs"] += 1
            changed |= _normalize_body_ppr(paragraph.element, target, changes, object_type="Paragraph", location=location, rules=rules, prefix="safe_normal_")
            for index, run in enumerate(paragraph.runs, 1):
                changed |= _apply_effective_run_target(document, resolver, paragraph, run, index, target, changes, rules, prefix="safe_normal_")

        elif role == "caption":
            stats["objects"]["caption_paragraphs"] += 1
            changed |= _normalize_caption_ppr(paragraph.element, caption_config, changes, location=location, rules=rules)
            target = {
                "chinese_font": caption_config["chinese_font"],
                "latin_font": caption_config["latin_font"],
                "font_size_pt": caption_config["font_size_pt"],
                "bold": caption_config.get("bold"),
                "color": caption_config.get("color"),
            }
            for index, run in enumerate(paragraph.runs, 1):
                changed |= _apply_effective_run_target(document, resolver, paragraph, run, index, target, changes, rules, prefix="caption")

        elif role in ("table_header", "table_body"):
            is_header = role == "table_header"
            regular_tables_seen.add(info.table_index)
            stats["objects"]["table_header_paragraphs" if is_header else "table_body_paragraphs"] += 1
            target = {
                "chinese_font": table_config["header_font"] if is_header else table_config["body_font"],
                "latin_font": table_config["latin_font"],
                "font_size_pt": table_config["font_size_pt"],
                "bold": table_config.get("header_bold") if is_header else None,
            }
            changed |= _normalize_table_ppr(
                paragraph.element, table_config, changes,
                object_type="Paragraph", location=location, rules=rules, prefix="table_regular_",
            )
            alignment = table_config.get("header_alignment") if is_header else table_config.get("body_alignment")
            if alignment:
                rule_id = "TABLE002" if is_header else "TABLE003"
                if paragraph.properties.get("jc") != alignment:
                    changed |= apply_alignment(
                        paragraph.element, alignment,
                        _ctx(changes, "Paragraph", location, rules, rule_id, "table_regular_"),
                    )
            for index, run in enumerate(paragraph.runs, 1):
                changed |= _apply_effective_run_target(document, resolver, paragraph, run, index, target, changes, rules, prefix="table_regular_")

        elif role == "table_named":
            name = resolver.name(paragraph.style_id)
            target = dict(table_config)
            target["chinese_font"] = table_config["header_font"] if name == table_config["required_styles"][0] else table_config["body_font"]
            stats["objects"]["table_named_paragraphs"] += 1
            if any(name_ in paragraph.properties for name_ in ("ind", "spacing")):
                changed |= _normalize_table_ppr(paragraph.element, target, changes, object_type="Paragraph", location=location, rules=rules)
            for index, run in enumerate(paragraph.runs, 1):
                changed |= _normalize_run(document, resolver, paragraph, run, index, "table", target, changes, rules)

        if changed:
            changed_parts.add("word/document.xml")

    stats["objects"]["regular_tables"] = len(regular_tables_seen)
    return changes, changed_parts, stats


def _write_validation_report(result, before, after, rules, generated):
    report = Path(result.report_path)
    json_path = report.with_suffix(".json")
    remaining = result.remaining_findings
    stats = result.normalization_stats
    integrity = result.content_integrity
    data = {
        "schema_version": "1.1",
        "generated_at": generated,
        "document_factory_version": __version__,
        "rules": {"path": rules["_path"], "sha256": rules["_sha256"], "spec_version": rules["spec_version"]},
        "normalization": result.to_dict(),
        "before_findings": [finding.to_dict() for finding in before.findings],
        "after_findings": [finding.to_dict() for finding in after.findings],
        "unsupported_capabilities": UNSUPPORTED_CAPABILITIES,
    }
    change_types = Counter(change["object_type"] for change in result.changes)
    rule_counts = Counter(change["rule"] for change in result.changes)
    lines = [
        "# DocumentFactory DOCX 规范化 Validation Report", "", "## 1. 基本信息", "",
        f"- 实际生成时间（含时区）：{generated}",
        f"- DocumentFactory 版本：{__version__}",
        f"- 输入文件：{result.input_path}",
        f"- 输出文件：{result.output_path}",
        f"- 输入 SHA-256：{result.input_sha256}",
        f"- 输出 SHA-256：{result.output_sha256}",
        f"- 规则文件：{rules['_path']}",
        f"- 规则 SHA-256：{rules['_sha256']}",
        f"- 输入文件未变化：{result.source_unchanged}", "",
        "## 2. Validation 结论", "", f"**RESULT: {result.status}**", "",
        "最终结论来自输出 DOCX 的真实 lint；ERROR 下降不等于全部格式合格。", "",
        "| 阶段 | ERROR | WARNING | INFO |", "|---|---:|---:|---:|",
        f"| 修复前 | {result.before_counts['ERROR']} | {result.before_counts['WARNING']} | {result.before_counts['INFO']} |",
        f"| 修复后 | {result.after_counts['ERROR']} | {result.after_counts['WARNING']} | {result.after_counts['INFO']} |", "",
        "## 3. 修改统计", "", f"- 属性修改记录：{len(result.changes)}",
        f"- 实际改动 ZIP 部件：{', '.join(integrity.get('changed_zip_parts', [])) or '无'}",
    ]
    lines += [f"- {name}：{count}" for name, count in sorted(change_types.items())]
    page_stats = stats.get("page", {})
    objects = stats.get("objects", {})
    lines += [
        "", "### 3.1 对象角色统计", "",
        f"- 页面节：{page_stats.get('sections_normalized', 0)}/{page_stats.get('sections_total', 0)} 个节被规范化",
        f"- 标题样式：{objects.get('heading_styles', 0)} 个；标题段落：{objects.get('heading_paragraphs', 0)} 个",
        f"- 具名正文（正文）段落：{objects.get('body_named_paragraphs', 0)} 个",
        f"- Safe Normal 正文段落：{objects.get('body_safe_normal_paragraphs', 0)} 个（保留 pStyle，仅直接格式）",
        f"- 题注段落：{objects.get('caption_paragraphs', 0)} 个",
        f"- 普通内容表格：{objects.get('regular_tables', 0)} 个；表头段落：{objects.get('table_header_paragraphs', 0)} 个；表体段落：{objects.get('table_body_paragraphs', 0)} 个",
        f"- 具名表格样式段落：{objects.get('table_named_paragraphs', 0)} 个", "",
        "### 3.2 按规则归因的修改次数", "",
        "| Rule | 次数 |", "|---|---:|",
    ]
    lines += [f"| {rule_id} | {count} |" for rule_id, count in sorted(rule_counts.items())]
    lines += [
        "", "## 4. 内容完整性闸门（Content Integrity Gate）", "",
        f"- 结论：**{integrity.get('status', '未执行')}**",
        f"- 可见文本一致：{integrity.get('visible_text_equal')}",
        f"- Run 文本一致：{integrity.get('run_text_equal')}",
        f"- 表格单元格文本一致：{integrity.get('table_cell_text_equal')}",
        f"- 表格结构一致：{integrity.get('table_structure_equal')}",
        f"- 域指令一致：{integrity.get('field_instructions_equal')}",
        f"- 超链接显示文本一致：{integrity.get('hyperlink_text_equal')}",
        f"- 页眉页脚文本一致：{integrity.get('header_footer_text_equal')}",
        f"- 关系部件一致：{integrity.get('relationships_equal')}",
        f"- 媒体文件数：{integrity.get('media_file_count')}；媒体 SHA-256 一致：{integrity.get('media_sha256_equal')}",
        f"- 段落 {integrity.get('paragraph_count_before')} → {integrity.get('paragraph_count_after')}；"
        f"表格 {integrity.get('table_count_before')} → {integrity.get('table_count_after')}；"
        f"节 {integrity.get('section_count_before')} → {integrity.get('section_count_after')}；"
        f"绘图 {integrity.get('drawing_count_before')} → {integrity.get('drawing_count_after')}",
        f"- 实际改动 ZIP 部件：{integrity.get('changed_zip_parts')}", "",
        "## 5. 未解决对象（本轮刻意不做语义处理）", "",
        "| 类别 | 数量 |", "|---|---:|",
    ]
    for name, count in sorted(result.unresolved_counts.items()):
        lines.append(f"| {name} | {count} |")
    if not result.unresolved_counts:
        lines.append("| 无 | 0 |")
    warning_items = stats.get("warnings", [])
    lines += ["", "| 类别 | 位置 | 原因 |", "|---|---|---|"]
    if warning_items:
        for item in warning_items:
            lines.append(f"| {_escape(item['kind'])} | {_escape(item['location'])} | {_escape(item['reason'])} |")
    else:
        lines.append("| - | - | 无 |")
    lines += [
        "", "## 6. 修改明细", "",
        "| 对象类型 | 位置 | 属性 | 修改前 | 修改后 | Rule | 规范出处 |",
        "|---|---|---|---|---|---|---|",
    ]
    for change in result.changes:
        values = [change[key] for key in ("object_type", "location", "property", "before", "after", "rule", "source")]
        lines.append("| " + " | ".join(_escape(value) for value in values) + " |")
    if not result.changes:
        lines.append("| - | - | - | 无需修改 | 无需修改 | - | - |")
    lines += ["", "## 7. 修复后剩余 ERROR / WARNING / UNSUPPORTED", "", "| Rule ID | Severity | 状态 | 位置 | 当前值 | 预期值 | 说明 |", "|---|---|---|---|---|---|---|"]
    for finding in remaining:
        values = [finding[key] for key in ("rule_id", "severity", "status", "location", "actual", "expected", "message")]
        lines.append("| " + " | ".join(_escape(value) for value in values) + " |")
    if not remaining:
        lines.append("| - | - | - | - | - | - | 无剩余 ERROR / WARNING / UNSUPPORTED |")
    lines += ["", "## 8. 本轮明确不自动修复", ""] + [f"- {item}" for item in UNSUPPORTED_CAPABILITIES]
    lines += ["", "## 9. 机器可读结果", "", f"同名 JSON：`{json_path}`", ""]
    atomic_text(report, "\n".join(lines))
    atomic_text(json_path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _escape(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value.replace("|", "\\|").replace("\r", "").replace("\n", "<br>").replace("<", "&lt;").replace(">", "&gt;")


def normalize(input_path, rules_path, output_path=None, report_path=None):
    """Normalize a DOCX into a new file and return a structured validation result."""
    root = Path.cwd().resolve()
    source = Path(input_path).resolve()
    if source.suffix.lower() != ".docx":
        raise DocumentFactoryError("normalize 输入必须是 DOCX 文件")
    output = checked_output(
        output_path or Path("output/normalized") / f"{source.stem}_formatted.docx",
        root, "output", source,
    )
    report = checked_output(
        report_path or Path("reports") / f"{source.stem}_NORMALIZATION_REPORT.md",
        root, "reports", source,
    )
    if output.suffix.lower() != ".docx":
        raise DocumentFactoryError("normalize 输出必须使用 .docx 扩展名")
    if report.suffix.lower() != ".md":
        raise DocumentFactoryError("normalize 报告必须使用 .md 扩展名（同名 JSON 自动生成）")
    rules = load_rules(rules_path)
    if rules["tables"].get("normalization_line_spacing") is None:
        raise DocumentFactoryError("规则缺少 tables.normalization_line_spacing，无法确定表格规范化目标")
    before = lint(source, rules)
    input_hash = before.document.sha256
    changes, changed_parts, stats = _apply_normalization(before.document, rules)
    if sha256(source) != input_hash:
        raise DocumentFactoryError("INPUT_CHANGED：规范化期间输入文件发生变化")
    write_package(source, output, before.document, changed_parts)
    if sha256(source) != input_hash:
        raise DocumentFactoryError("INPUT_CHANGED：规范化期间输入文件发生变化")
    # read_docx is intentionally called before lint so an invalid or partial ZIP can never be reported as success.
    read_docx(output)
    integrity = verify_content_integrity(source, output, changed_parts)
    stats["changed_zip_parts"] = integrity["changed_zip_parts"]
    after = lint(output, rules)
    remaining = [
        finding.to_dict() for finding in after.findings
        if finding.severity in ("ERROR", "WARNING") or finding.status == "UNSUPPORTED"
    ]
    unresolved_counts = Counter(item["kind"] for item in stats.get("warnings", []))
    unresolved_counts["RESIDUAL_LINT_ERROR"] = after.counts["ERROR"]
    unresolved_counts["RESIDUAL_LINT_WARNING"] = after.counts["WARNING"]
    result = NormalizationResult(
        status=after.result,
        input_path=str(source),
        output_path=str(output),
        report_path=str(report),
        input_sha256=input_hash,
        output_sha256=after.document.sha256,
        before_counts=before.counts,
        after_counts=after.counts,
        changes=changes,
        remaining_findings=remaining,
        source_unchanged=sha256(source) == input_hash,
        normalization_stats={
            "page": stats["page"],
            "objects": dict(stats["objects"]),
            "rules_applied": dict(Counter(change["rule"] for change in changes)),
            "changed_zip_parts": stats["changed_zip_parts"],
            "warnings": stats["warnings"],
        },
        content_integrity=integrity,
        unresolved_counts=dict(unresolved_counts),
    )
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_validation_report(result, before, after, rules, generated)
    return result
