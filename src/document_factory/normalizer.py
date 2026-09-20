"""Deterministic DOCX normalization built on the v0.1 reader and lint model."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import json
import os
import re
import tempfile
import zipfile

from lxml import etree

from . import __version__
from .docx_reader import NS, q, read_docx, sha256
from .lint_engine import lint, load_rules
from .models import DocumentFactoryError, NormalizationResult
from .output_paths import checked_output
from .style_resolver import StyleResolver


UNSUPPORTED_CAPABILITIES = [
    "自动多级编号、numId、lvlOverride，以及手工编号转自动编号",
    "TOC 创建、重建或刷新",
    "Normal 转正文、疑似标题转 Heading，以及编制说明、目录标题、封面等语义重分类",
    "复杂条件表格样式",
    "文本框、浮动对象、修订、RTL、复杂文字和图片中文字",
    "视觉美化以及任何无法被现有 lint 再验证的修改",
]

PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
    "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
    "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
    "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
]
RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
    "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden",
    "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
    "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath", "rPrChange",
]


def _local(element):
    return etree.QName(element).localname


def _ensure(parent, name, order=None):
    child = parent.find(f"w:{name}", NS)
    if child is not None:
        return child
    child = etree.Element(q(name))
    if (name == "pPr" and _local(parent) == "p") or (name == "rPr" and _local(parent) == "r"):
        parent.insert(0, child)
        return child
    if order and name in order:
        target = order.index(name)
        for index, current in enumerate(parent):
            current_name = _local(current)
            if current_name in order and order.index(current_name) > target:
                parent.insert(index, child)
                break
        else:
            parent.append(child)
    else:
        parent.append(child)
    return child


def _attributes(element):
    if element is None:
        return {}
    return {etree.QName(key).localname: value for key, value in element.attrib.items()}


def _record(changes, object_type, location, prop, before, after, rule_id, rules):
    changes.append({
        "object_type": object_type,
        "location": location,
        "property": prop,
        "before": before,
        "after": after,
        "rule": rule_id,
        "source": rules["rules"][rule_id]["source"],
    })


def _set_properties(parent, child_name, wanted, remove, changes, *, object_type, location, prop, rule_id, rules, order):
    child = parent.find(f"w:{child_name}", NS)
    before = _attributes(child)
    after = dict(before)
    for key in remove:
        after.pop(key, None)
    after.update({key: str(value) for key, value in wanted.items()})
    if before == after:
        return False
    child = child if child is not None else _ensure(parent, child_name, order)
    for key in remove:
        child.attrib.pop(q(key), None)
    for key, value in wanted.items():
        child.set(q(key), str(value))
    _record(changes, object_type, location, prop, before, after, rule_id, rules)
    return True


def _set_toggle(parent, child_name, wanted, changes, *, object_type, location, prop, rule_id, rules, order):
    """Set an OOXML on/off property through the shared normalization recorder."""
    child = parent.find(f"w:{child_name}", NS)
    before = None if child is None else child.get(q("val"), "1") not in ("0", "false", "off")
    wanted = bool(wanted)
    if before is wanted:
        return False
    child = child if child is not None else _ensure(parent, child_name, order)
    child.set(q("val"), "1" if wanted else "0")
    _record(changes, object_type, location, prop, before, wanted, rule_id, rules)
    return True


def apply_format_profile(
    parent, profile, changes, *, object_type, location, rules, rule_id, prefix="", table_basic=False,
    include_paragraph=True, include_run=True,
):
    """Apply an exact, already-resolved format profile through the normalizer writer."""
    changed = False
    if include_paragraph:
        paragraph = profile.get("paragraph", {})
        ppr = _ensure(parent, "pPr", ["pPr", "rPr"] if _local(parent) == "style" else ["pPr"])
        if paragraph.get("alignment") is not None:
            changed |= _set_properties(
                ppr, "jc", {"val": paragraph["alignment"]}, set(), changes,
                object_type=object_type, location=location, prop=f"{prefix}alignment", rule_id=rule_id,
                rules=rules, order=PPR_ORDER,
            )
        if not table_basic:
            spacing = {key: value for key, value in paragraph.get("spacing", {}).items() if value is not None}
            if spacing:
                changed |= _set_properties(
                    ppr, "spacing", spacing, set(), changes,
                    object_type=object_type, location=location, prop=f"{prefix}spacing", rule_id=rule_id,
                    rules=rules, order=PPR_ORDER,
                )
            indent = {key: value for key, value in paragraph.get("indent", {}).items() if value is not None}
            if indent:
                changed |= _set_properties(
                    ppr, "ind", indent, set(), changes,
                    object_type=object_type, location=location, prop=f"{prefix}indent", rule_id=rule_id,
                    rules=rules, order=PPR_ORDER,
                )

    if not include_run:
        return changed
    font = profile.get("font", {})
    rpr = _ensure(parent, "rPr", ["pPr", "rPr"] if _local(parent) == "style" else ["rPr"])
    wanted_fonts = {
        key: value for key, value in {
            "eastAsia": font.get("east_asia"), "ascii": font.get("latin"), "hAnsi": font.get("latin"),
        }.items() if value is not None
    }
    remove_fonts = set()
    if font.get("east_asia") is not None:
        remove_fonts.add("eastAsiaTheme")
    if font.get("latin") is not None:
        remove_fonts.update(("asciiTheme", "hAnsiTheme"))
    if wanted_fonts:
        changed |= _set_properties(
            rpr, "rFonts", wanted_fonts, remove_fonts, changes,
            object_type=object_type, location=location, prop=f"{prefix}font", rule_id=rule_id,
            rules=rules, order=RPR_ORDER,
        )
    if font.get("size_pt") is not None:
        changed |= _set_properties(
            rpr, "sz", {"val": int(float(font["size_pt"]) * 2)}, set(), changes,
            object_type=object_type, location=location, prop=f"{prefix}font_size_pt", rule_id=rule_id,
            rules=rules, order=RPR_ORDER,
        )
    if font.get("color") is not None:
        changed |= _set_properties(
            rpr, "color", {"val": font["color"]}, {"themeColor", "themeTint", "themeShade"}, changes,
            object_type=object_type, location=location, prop=f"{prefix}color", rule_id=rule_id,
            rules=rules, order=RPR_ORDER,
        )
    for key, child_name in (("bold", "b"), ("italic", "i")):
        if font.get(key) is not None:
            changed |= _set_toggle(
                rpr, child_name, font[key], changes,
                object_type=object_type, location=location, prop=f"{prefix}{key}", rule_id=rule_id,
                rules=rules, order=RPR_ORDER,
            )
    return changed


def _style_element(document, style_id):
    root = document.parts.get("word/styles.xml")
    if root is None:
        return None
    values = root.xpath('./w:style[@w:styleId=$sid]', sid=style_id, namespaces=NS)
    return values[0] if values else None


def _normalize_rpr(parent, target, changes, *, object_type, location, rules, prefix="", heading=False):
    changed = False
    rpr = _ensure(parent, "rPr", ["pPr", "rPr"] if _local(parent) == "style" else ["rPr"])
    if target.get("chinese_font"):
        changed |= _set_properties(
            rpr, "rFonts", {"eastAsia": target["chinese_font"]}, {"eastAsiaTheme"}, changes,
            object_type=object_type, location=location, prop=f"{prefix}chinese_font", rule_id="STYLE005" if object_type == "Style" and heading else "TABLE008" if prefix.startswith("table") else "FONT001", rules=rules, order=RPR_ORDER,
        )
    if target.get("latin_font"):
        changed |= _set_properties(
            rpr, "rFonts", {"ascii": target["latin_font"], "hAnsi": target["latin_font"]}, {"asciiTheme", "hAnsiTheme"}, changes,
            object_type=object_type, location=location, prop=f"{prefix}latin_font", rule_id="TABLE008" if prefix.startswith("table") else "FONT002", rules=rules, order=RPR_ORDER,
        )
    size = target.get("font_size_pt", target.get("size_pt"))
    if size is not None:
        changed |= _set_properties(
            rpr, "sz", {"val": int(float(size) * 2)}, set(), changes,
            object_type=object_type, location=location, prop=f"{prefix}font_size_pt", rule_id="STYLE005" if object_type == "Style" and heading else "TABLE008" if prefix.startswith("table") else "FONT003", rules=rules, order=RPR_ORDER,
        )
    if heading:
        changed |= _set_properties(
            rpr, "color", {"val": target["color"]}, {"themeColor", "themeTint", "themeShade"}, changes,
            object_type=object_type, location=location, prop=f"{prefix}color", rule_id="STYLE004" if object_type == "Style" else "FONT004", rules=rules, order=RPR_ORDER,
        )
    return changed


def _normalize_body_ppr(parent, config, changes, *, object_type, location, rules, prefix=""):
    ppr = _ensure(parent, "pPr", ["pPr", "rPr"] if _local(parent) == "style" else ["pPr"])
    changed = _set_properties(
        ppr, "ind", {"firstLineChars": int(config["first_line_indent_chars"] * 100)}, {"firstLine", "hanging", "hangingChars"}, changes,
        object_type=object_type, location=location, prop=f"{prefix}indent", rule_id="BODY002", rules=rules, order=PPR_ORDER,
    )
    changed |= _set_properties(
        ppr, "spacing", {"before": int(config["space_before_pt"] * 20), "after": int(config["space_after_pt"] * 20), "line": int(config["line_spacing"] * 240), "lineRule": "auto"},
        {"beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"}, changes,
        object_type=object_type, location=location, prop=f"{prefix}spacing", rule_id="BODY003", rules=rules, order=PPR_ORDER,
    )
    changed |= _set_properties(
        ppr, "jc", {"val": config["alignment"]}, set(), changes,
        object_type=object_type, location=location, prop=f"{prefix}alignment", rule_id="BODY002", rules=rules, order=PPR_ORDER,
    )
    return changed


def _normalize_table_ppr(parent, config, changes, *, object_type, location, rules, prefix="table_"):
    ppr = _ensure(parent, "pPr", ["pPr", "rPr"] if _local(parent) == "style" else ["pPr"])
    changed = _set_properties(
        ppr, "ind", {"firstLine": int(config["first_line_indent"]), "left": int(config["left_indent"]), "right": int(config["right_indent"])},
        {"firstLineChars", "hanging", "hangingChars", "leftChars", "rightChars", "start", "startChars", "end", "endChars"}, changes,
        object_type=object_type, location=location, prop=f"{prefix}indent", rule_id="TABLE004", rules=rules, order=PPR_ORDER,
    )
    line = config["normalization_line_spacing"]
    line_attrs = {"line": 240, "lineRule": "auto"} if line == "single" else {"line": int(config["normalization_exact_line_twips"]), "lineRule": "exact"}
    changed |= _set_properties(
        ppr, "spacing", {"before": int(config["space_before_pt"] * 20), "after": int(config["space_after_pt"] * 20), **line_attrs},
        {"beforeLines", "afterLines", "beforeAutospacing", "afterAutospacing"}, changes,
        object_type=object_type, location=location, prop=f"{prefix}spacing", rule_id="TABLE007", rules=rules, order=PPR_ORDER,
    )
    return changed


def _target_for_paragraph(document, resolver, paragraph, rules):
    if paragraph.in_toc:
        return None
    name = resolver.name(paragraph.style_id)
    level = resolver.heading_level(paragraph)
    if level and paragraph.table is None:
        return "heading", dict(rules[f"heading{level}"])
    if name == rules["body"]["style_name"] and paragraph.table is None:
        return "body", dict(rules["body"])
    tables = rules["tables"]
    allowed = tables["required_styles"] + tables["optional_styles"]
    if name in allowed:
        target = dict(tables)
        target["chinese_font"] = tables["header_font"] if name == tables["required_styles"][0] else tables["body_font"]
        return "table", target
    return None


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


def _normalize_run(document, resolver, paragraph, run, index, role, target, changes, rules):
    if not run.text.strip() or run.element is None or run.properties.get("cs") or run.properties.get("rtl"):
        return False
    effective = resolver.run(paragraph, run)
    location = f"{paragraph.location} / Run {index}"
    rpr = run.element.find("w:rPr", NS)
    direct = run.properties
    changed = False
    has_cn = bool(re.search(r"[\u3400-\u9fff\U00020000-\U0002fa1f]", run.text))
    has_latin = bool(re.search(r"[A-Za-z0-9\u00c0-\u024f]", run.text))
    if has_cn:
        actual, _ = resolver.font(effective, "cn")
        slot = direct.get("rFonts", {})
        if actual is None or actual.casefold() not in [value.casefold() for value in rules.get("font_aliases", {}).get(target["chinese_font"], [target["chinese_font"]])] or "eastAsiaTheme" in slot:
            if "eastAsia" in slot or "eastAsiaTheme" in slot or _has_character_override(document, run, "rFonts"):
                rpr = rpr if rpr is not None else _ensure(run.element, "rPr", ["rPr"])
                changed |= _set_properties(
                    rpr, "rFonts", {"eastAsia": target["chinese_font"]}, {"eastAsiaTheme"}, changes,
                    object_type="Run", location=location, prop="chinese_font", rule_id="FONT001", rules=rules, order=RPR_ORDER,
                )
    if has_latin and target.get("latin_font"):
        slot = direct.get("rFonts", {})
        actual_ascii, _ = resolver.font(effective, "ascii")
        aliases = [value.casefold() for value in rules.get("font_aliases", {}).get(target["latin_font"], [target["latin_font"]])]
        if actual_ascii is None or actual_ascii.casefold() not in aliases or any(key in slot for key in ("asciiTheme", "hAnsiTheme")):
            if any(key in slot for key in ("ascii", "hAnsi", "asciiTheme", "hAnsiTheme")) or _has_character_override(document, run, "rFonts"):
                rpr = rpr if rpr is not None else _ensure(run.element, "rPr", ["rPr"])
                changed |= _set_properties(
                    rpr, "rFonts", {"ascii": target["latin_font"], "hAnsi": target["latin_font"]}, {"asciiTheme", "hAnsiTheme"}, changes,
                    object_type="Run", location=location, prop="latin_font", rule_id="FONT002", rules=rules, order=RPR_ORDER,
                )
    expected_size = int(float(target.get("font_size_pt", target.get("size_pt"))) * 2)
    if effective.get("sz") != str(expected_size) and ("sz" in direct or _has_character_override(document, run, "sz")):
        rpr = rpr if rpr is not None else _ensure(run.element, "rPr", ["rPr"])
        changed |= _set_properties(
            rpr, "sz", {"val": expected_size}, set(), changes,
            object_type="Run", location=location, prop="font_size_pt", rule_id="FONT003", rules=rules, order=RPR_ORDER,
        )
    if role == "heading":
        color = effective.get("color", {})
        direct_color = direct.get("color")
        if (color.get("val", "").upper() != target["color"] or any(key.startswith("theme") for key in color)) and (direct_color is not None or _has_character_override(document, run, "color")):
            rpr = rpr if rpr is not None else _ensure(run.element, "rPr", ["rPr"])
            changed |= _set_properties(
                rpr, "color", {"val": target["color"]}, {"themeColor", "themeTint", "themeShade"}, changes,
                object_type="Run", location=location, prop="color", rule_id="FONT004", rules=rules, order=RPR_ORDER,
            )
    return changed


def _apply_normalization(document, rules):
    resolver = StyleResolver(document)
    changes = []
    changed_parts = set()

    heading_styles = {}
    for paragraph in document.paragraphs:
        if paragraph.part == "word/document.xml" and paragraph.table is None and not paragraph.in_toc:
            level = resolver.heading_level(paragraph)
            if level:
                heading_styles[paragraph.style_id] = level
    for style_id, level in heading_styles.items():
        element = _style_element(document, style_id)
        if element is not None and _normalize_rpr(element, rules[f"heading{level}"], changes, object_type="Style", location=f"Style {resolver.name(style_id)}", rules=rules, heading=True):
            changed_parts.add("word/styles.xml")

    table_names = rules["tables"]["required_styles"] + rules["tables"]["optional_styles"]
    for style in document.styles.values():
        element = _style_element(document, style.style_id)
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

    for paragraph in document.paragraphs:
        if paragraph.part != "word/document.xml":
            continue
        selected = _target_for_paragraph(document, resolver, paragraph, rules)
        if selected is None:
            continue
        role, target = selected
        changed = False
        if role == "body" and any(name in paragraph.properties for name in ("ind", "spacing", "jc")):
            changed |= _normalize_body_ppr(paragraph.element, target, changes, object_type="Paragraph", location=paragraph.location, rules=rules)
        elif role == "table" and any(name in paragraph.properties for name in ("ind", "spacing")):
            changed |= _normalize_table_ppr(paragraph.element, target, changes, object_type="Paragraph", location=paragraph.location, rules=rules)
        for index, run in enumerate(paragraph.runs, 1):
            changed |= _normalize_run(document, resolver, paragraph, run, index, role, target, changes, rules)
        if changed:
            changed_parts.add("word/document.xml")
    return changes, changed_parts


def _write_package(source, destination, document, changed_parts):
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{destination.stem}_", suffix=".tmp", dir=destination.parent)
    os.close(handle)
    temp = Path(temp_name)
    try:
        if not changed_parts:
            temp.write_bytes(source.read_bytes())
        else:
            with zipfile.ZipFile(source, "r") as incoming, zipfile.ZipFile(temp, "w") as outgoing:
                for info in incoming.infolist():
                    payload = incoming.read(info.filename)
                    if info.filename in changed_parts:
                        payload = etree.tostring(document.parts[info.filename], encoding="UTF-8", xml_declaration=True)
                    outgoing.writestr(info, payload)
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()


def _atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.stem}_", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temp = Path(temp_name)
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _write_validation_report(result, before, after, rules, generated):
    report = Path(result.report_path)
    json_path = report.with_suffix(".json")
    remaining = result.remaining_findings
    data = {
        "schema_version": "1.0",
        "generated_at": generated,
        "document_factory_version": __version__,
        "rules": {"path": rules["_path"], "sha256": rules["_sha256"], "spec_version": rules["spec_version"]},
        "normalization": result.to_dict(),
        "before_findings": [finding.to_dict() for finding in before.findings],
        "after_findings": [finding.to_dict() for finding in after.findings],
        "unsupported_capabilities": UNSUPPORTED_CAPABILITIES,
    }
    change_types = Counter(change["object_type"] for change in result.changes)
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
    ]
    lines += [f"- {name}：{count}" for name, count in sorted(change_types.items())]
    lines += ["", "## 4. 修改明细", "", "| 对象类型 | 位置 | 属性 | 修改前 | 修改后 | Rule | 规范出处 |", "|---|---|---|---|---|---|---|"]
    for change in result.changes:
        values = [change[key] for key in ("object_type", "location", "property", "before", "after", "rule", "source")]
        lines.append("| " + " | ".join(_escape(value) for value in values) + " |")
    if not result.changes:
        lines.append("| - | - | - | 无需修改 | 无需修改 | - | - |")
    lines += ["", "## 5. 修复后剩余 ERROR / WARNING / UNSUPPORTED", "", "| Rule ID | Severity | 状态 | 位置 | 当前值 | 预期值 | 说明 |", "|---|---|---|---|---|---|---|"]
    for finding in remaining:
        values = [finding[key] for key in ("rule_id", "severity", "status", "location", "actual", "expected", "message")]
        lines.append("| " + " | ".join(_escape(value) for value in values) + " |")
    if not remaining:
        lines.append("| - | - | - | - | - | - | 无剩余 ERROR / WARNING / UNSUPPORTED |")
    lines += ["", "## 6. 本轮明确不自动修复", ""] + [f"- {item}" for item in UNSUPPORTED_CAPABILITIES]
    lines += ["", "## 7. 机器可读结果", "", f"同名 JSON：`{json_path}`", ""]
    _atomic_text(report, "\n".join(lines))
    _atomic_text(json_path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


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
    changes, changed_parts = _apply_normalization(before.document, rules)
    if sha256(source) != input_hash:
        raise DocumentFactoryError("INPUT_CHANGED：规范化期间输入文件发生变化")
    _write_package(source, output, before.document, changed_parts)
    if sha256(source) != input_hash:
        raise DocumentFactoryError("INPUT_CHANGED：规范化期间输入文件发生变化")
    # read_docx is intentionally called before lint so an invalid or partial ZIP can never be reported as success.
    read_docx(output)
    after = lint(output, rules)
    remaining = [
        finding.to_dict() for finding in after.findings
        if finding.severity in ("ERROR", "WARNING") or finding.status == "UNSUPPORTED"
    ]
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
    )
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_validation_report(result, before, after, rules, generated)
    return result
