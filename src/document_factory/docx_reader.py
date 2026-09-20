"""ZIP/OOXML reader. No write access to the package is ever requested."""
from pathlib import Path
import hashlib
import re
import zipfile
from lxml import etree
from .models import Document, DocumentFactoryError, Field, Paragraph, Run, Style, Table

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W, "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def q(name):
    return f"{{{W}}}{name}"


def val(node, path, default=None):
    found = node.find(path, NS) if node is not None else None
    return found.get(q("val"), default) if found is not None else default


def attrs(node):
    return {etree.QName(k).localname: v for k, v in node.attrib.items()} if node is not None else {}


def on(value):
    return value not in ("0", "false", "off")


def properties(node):
    if node is None:
        return {}
    result = {}
    groups = {"rFonts", "color", "spacing", "ind", "lang", "shd"}
    toggles = {"b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "vanish", "pageBreakBefore", "keepNext", "keepLines", "cs", "rtl"}
    for child in node:
        name = etree.QName(child).localname
        if name in {"pPrChange", "rPrChange"}:
            continue
        if name in {"rPr", "numPr"}:
            result[name] = properties(child)
        elif name in groups:
            result[name] = attrs(child)
        elif name in toggles:
            result[name] = on(child.get(q("val"), "1"))
        else:
            result[name] = child.get(q("val"), attrs(child) or True)
    return result


def sha256(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def read_docx(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise DocumentFactoryError(f"输入文件不存在：{path}")
    parts = {}
    diagnostics = []
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > 10000 or sum(i.file_size for i in members) > 128 * 1024 * 1024:
                raise DocumentFactoryError("DOCX 包超过安全读取限制（128 MiB / 10000 个部件）")
            if len({i.filename for i in members}) != len(members):
                raise DocumentFactoryError("DOCX 含重复 ZIP 部件名，无法可靠解析")
            parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
            for entry in members:
                if entry.filename.endswith((".xml", ".rels")):
                    data = archive.read(entry)
                    root = etree.fromstring(data, parser)
                    if root.getroottree().docinfo.doctype:
                        raise DocumentFactoryError("DOCX XML 不允许包含 DTD")
                    # Strict WordprocessingML uses the same element model here.
                    for element in root.iter():
                        if not isinstance(element.tag, str):
                            continue
                        element.tag = element.tag.replace("http://purl.oclc.org/ooxml/wordprocessingml/main", W)
                        for key in list(element.attrib):
                            if "http://purl.oclc.org/ooxml/wordprocessingml/main" in key:
                                element.set(key.replace("http://purl.oclc.org/ooxml/wordprocessingml/main", W), element.attrib.pop(key))
                    parts[entry.filename] = root
    except (OSError, zipfile.BadZipFile, RuntimeError, etree.XMLSyntaxError) as exc:
        raise DocumentFactoryError(f"无法读取 DOCX ZIP / OOXML：{exc}") from exc
    if "word/document.xml" not in parts:
        raise DocumentFactoryError("DOCX 缺少 word/document.xml")
    styles = {}
    defaults = {}
    default_style = "Normal"
    style_root = parts.get("word/styles.xml")
    if style_root is not None:
        defaults = properties(style_root.find("w:docDefaults/w:pPrDefault/w:pPr", NS))
        defaults["rPr"] = properties(style_root.find("w:docDefaults/w:rPrDefault/w:rPr", NS))
        for s in style_root.findall("w:style", NS):
            sid = s.get(q("styleId"), "")
            props = properties(s.find("w:pPr", NS))
            props["rPr"] = properties(s.find("w:rPr", NS))
            style = Style(sid, val(s, "w:name", sid), s.get(q("type"), "paragraph"),
                          val(s, "w:basedOn"), props, on(s.get(q("customStyle"), "0")), on(s.get(q("default"), "0")))
            styles[sid] = style
            if style.kind == "paragraph" and style.default:
                default_style = sid
    else:
        diagnostics.append("缺少 styles.xml，样式继承无法完整判断")
    paragraphs, tables, fields, sections = [], [], [], []
    relationships = {name: [attrs(e) for e in root] for name, root in parts.items() if name.endswith(".rels")}
    stories = [n for n in parts if re.fullmatch(r"word/(document|header[^/]*|footer[^/]*|footnotes|endnotes)\.xml", n)]
    stories.sort(key=lambda n: (n != "word/document.xml", n))
    for part in stories:
        root = parts[part]
        para_elements = root.findall(".//w:p", NS)
        indices = {p: i for i, p in enumerate(para_elements, 1)}
        table_map = {}
        for t in root.findall(".//w:tbl", NS):
            ti = len(tables) + 1
            rows = []
            for ri, row in enumerate(t.findall("w:tr", NS), 1):
                cells = []
                for ci, cell in enumerate(row.findall("w:tc", NS), 1):
                    cell_ps = [p for p in cell.findall(".//w:p", NS) if next(p.iterancestors(q("tbl")), None) is t]
                    for p in cell_ps:
                        table_map[p] = (ti, ri, ci)
                    cells.append({"index": ci, "paragraphs": [indices[p] for p in cell_ps],
                                  "grid_span": int(val(cell, "w:tcPr/w:gridSpan", "1")),
                                  "v_merge": val(cell, "w:tcPr/w:vMerge", "continue") if cell.find("w:tcPr/w:vMerge", NS) is not None else None})
                repeat = row.find("w:trPr/w:tblHeader", NS)
                rows.append({"index": ri, "repeat_header": repeat is not None and on(repeat.get(q("val"), "1")), "cells": cells})
            tables.append(Table(ti, part, rows, len(t.findall("w:tblGrid/w:gridCol", NS)), val(t, "w:tblPr/w:tblStyle")))
        pmap = {}
        for p in para_elements:
            runs = []
            for r in p.findall(".//w:r", NS):
                if next(r.iterancestors(q("p")), None) is not p:
                    continue
                if any(a.tag == q("del") for a in r.iterancestors()):
                    continue
                text = "".join((e.text or "") if e.tag == q("t") else "\t" if e.tag == q("tab") else "\n" if e.tag == q("br") else "" for e in r)
                runs.append(Run(text, properties(r.find("w:rPr", NS)), element=r))
            props = properties(p.find("w:pPr", NS))
            pp = Paragraph(indices[p], part, "".join(r.text for r in runs), props.get("pStyle", default_style), props, runs,
                           bool(p.xpath('.//w:br[@w:type="page"]', namespaces=NS)), *table_map.get(p, (None, None, None)), element=p)
            paragraphs.append(pp)
            pmap[p] = pp
        # Fields span runs and sometimes paragraphs. The stack isolates nested fields.
        stack = []
        for e in root.iter():
            parent_p = next(e.iterancestors(q("p")), None)
            pi = indices.get(parent_p, 0)
            if e.tag == q("fldSimple"):
                instruction = e.get(q("instr"), "")
                fields.append(Field(instruction, part, pi))
                if instruction.strip().upper().startswith("TOC "):
                    for p in e.findall(".//w:p", NS):
                        pmap[p].in_toc = True
                    if parent_p in pmap:
                        pmap[parent_p].in_toc = True
            elif e.tag == q("fldChar"):
                kind = e.get(q("fldCharType"))
                if kind == "begin":
                    stack.append({"text": "", "index": pi, "result": False})
                elif kind == "separate" and stack:
                    stack[-1]["result"] = True
                elif kind == "end" and stack:
                    f = stack.pop()
                    fields.append(Field(f["text"], part, f["index"]))
            elif e.tag == q("instrText") and stack and not stack[-1]["result"]:
                stack[-1]["text"] += e.text or ""
            if parent_p in pmap and any(f["result"] and re.match(r"\s*TOC\b", f["text"], re.I) for f in stack):
                pmap[parent_p].in_toc = True
        for f in stack:
            fields.append(Field(f["text"], part, f["index"], False))
            diagnostics.append(f"{part} Paragraph {f['index']}：域缺少结束标记")
    root = parts["word/document.xml"]
    for tag, description in (("altChunk", "外部导入内容 altChunk"), ("txbxContent", "文本框内容")):
        if root.find(f".//w:{tag}", NS) is not None:
            diagnostics.append(f"存在{description}：v0.1 不保证此类对象的阅读顺序、样式与分页语义")
    if root.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent') is not None:
        diagnostics.append("存在 AlternateContent：v0.1 未按 Office 功能集选择分支，相关对象需人工复核")
    for section in root.findall(".//w:sectPr", NS):
        if any(a.tag == q("sectPrChange") for a in section.iterancestors()):
            continue
        parent_p = next(section.iterancestors(q("p")), None)
        sections.append({"index": len(sections) + 1, "size": attrs(section.find("w:pgSz", NS)),
                         "margins": attrs(section.find("w:pgMar", NS)), "break_type": val(section, "w:type", "nextPage"),
                         "paragraph_index": next((p.index for p in paragraphs if p.element is parent_p), None),
                         "properties": properties(section)})
    if root.find(".//w:ins", NS) is not None or root.find(".//w:del", NS) is not None:
        diagnostics.append("存在修订：正文采用当前插入内容、排除删除 Run；修订中的段落/表格结构需要人工复核")
    return Document(path, sha256(path), parts, paragraphs, styles, defaults, default_style, tables, sections, fields, relationships, diagnostics)
