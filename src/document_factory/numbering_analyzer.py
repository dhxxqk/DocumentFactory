"""Resolve concrete lists, style-linked levels, overrides and cancellation."""
import re
from .docx_reader import NS, q, val
from .style_resolver import merge


class NumberingAnalyzer:
    def __init__(self, document, resolver):
        self.resolver = resolver
        root = document.parts.get("word/numbering.xml")
        self.nums = {e.get(q("numId")): e for e in root.findall("w:num", NS)} if root is not None else {}
        self.abstracts = {e.get(q("abstractNumId")): e for e in root.findall("w:abstractNum", NS)} if root is not None else {}

    def definition(self, num_id, seen=None):
        seen = set() if seen is None else seen
        if num_id in seen:
            return None, "numStyleLink 循环"
        seen.add(num_id)
        num = self.nums.get(num_id)
        if num is None:
            return None, f"numId={num_id} 不存在"
        abstract = self.abstracts.get(val(num, "w:abstractNumId"))
        if abstract is None:
            return None, "abstractNumId 不存在"
        link = val(abstract, "w:numStyleLink")
        if link:
            linked = self.resolver.style(link).get("numPr", {}).get("numId")
            resolved, error = self.definition(linked, seen)
            if error:
                return None, error
            levels = dict(resolved["levels"])
            kind = resolved["kind"]
        else:
            levels = {e.get(q("ilvl")): e for e in abstract.findall("w:lvl", NS)}
            kind = val(abstract, "w:multiLevelType")
        overrides = {}
        for override in num.findall("w:lvlOverride", NS):
            level = override.get(q("ilvl"))
            replacement = override.find("w:lvl", NS)
            if replacement is not None:
                levels[level] = replacement
            overrides[level] = val(override, "w:startOverride")
        return {"levels": levels, "kind": kind, "overrides": overrides}, None

    def binding(self, paragraph):
        style_num = self.resolver.style(paragraph.style_id).get("numPr", {})
        direct_num = paragraph.properties.get("numPr", {})
        num = merge(style_num, direct_num)
        num_id = num.get("numId")
        if not num_id or num_id == "0":
            return {"valid": False, "reason": "无编号绑定" if not num_id else "numId=0 显式取消编号"}
        definition, error = self.definition(num_id)
        if error:
            return {"valid": False, "reason": error, "numId": num_id}
        level = direct_num.get("ilvl")
        if level is None:
            # w:ilvl inside a paragraph style is ignored (ISO 29500 numPr).
            style_ids = [s.style_id for s in reversed(self.resolver.chain(paragraph.style_id))]
            for sid in style_ids:
                linked = [n for n, elem in definition["levels"].items() if val(elem, "w:pStyle") == sid]
                if len(linked) == 1:
                    level = linked[0]
                    break
            if level is None:
                if style_num and "numId" not in direct_num:
                    return {"valid": False, "reason": "样式编号缺少唯一 pStyle 级别关联", "numId": num_id}
                level = "0"
        elem = definition["levels"].get(level)
        if elem is None:
            return {"valid": False, "reason": f"编号级别 {level} 不存在", "numId": num_id}
        fmt, text = val(elem, "w:numFmt"), val(elem, "w:lvlText")
        valid = fmt not in (None, "none", "bullet") and bool(text) and bool(re.search(r"%[1-9]", text))
        return {"valid": valid, "numId": num_id, "ilvl": int(level), "format": fmt, "text": text,
                "multilevel": definition["kind"] != "singleLevel" and len(definition["levels"]) > 1,
                "style_link": val(elem, "w:pStyle"), "start_override": definition["overrides"].get(level),
                "reason": "有效自动编号" if valid else "非有效标题数字编号"}

    def analyze(self, ctx):
        for p in ctx.main_paragraphs:
            level = self.resolver.heading_level(p)
            if not level or p.in_toc or p.table is not None:
                continue
            binding = self.binding(p)
            manual = any(re.match(pattern, p.text) for pattern in ctx.rules["numbering"]["manual_patterns"])
            if ctx.rules["numbering"]["manual_heading_number_forbidden"] and manual:
                ctx.add("NUM001", p, p.text, "编号由 Word 多级列表产生", "检测到标题文本中的手写编号" + ("，且无有效自动编号绑定" if not binding["valid"] else "，与自动编号同时存在，需移除手写编号"))
            if ctx.rules["numbering"]["automatic_multilevel_required"]:
                ctx.check("NUM002", p, binding["valid"], binding, "有效 Word 自动编号", "解析 paragraph numPr、样式编号、numbering.xml")
                if binding["valid"]:
                    linked_ids = {s.style_id for s in self.resolver.chain(p.style_id)}
                    good = binding["multilevel"] and binding["ilvl"] == level - 1 and binding["style_link"] in linked_ids
                    ctx.check("NUM003", p, good, binding, f"Heading {level} 绑定多级编号级别 {level - 1} 及 pStyle", "检查级别与真实标题样式关联")
