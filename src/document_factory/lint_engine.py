from pathlib import Path
from collections import Counter
import re
import yaml
from .models import DocumentFactoryError, Finding, Paragraph
from .docx_reader import read_docx, sha256
from .style_resolver import StyleResolver
from .numbering_analyzer import NumberingAnalyzer
from . import table_analyzer, section_analyzer, toc_analyzer


def load_rules(path):
    path = Path(path).resolve()
    try:
        rules = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        required = ("version", "spec_version", "source", "document", "body", "heading1", "heading2", "heading3", "toc", "numbering", "tables", "rules")
        if not isinstance(rules, dict) or any(k not in rules for k in required):
            raise ValueError("规则缺少必需配置节")
        for name, definition in rules["rules"].items():
            if definition["severity"] not in ("ERROR", "WARNING", "INFO") or not definition.get("source"):
                raise ValueError(f"规则 {name} 缺少有效 severity/source")
        for pattern in rules["numbering"]["manual_patterns"]:
            re.compile(pattern)
        source = (path.parent.parent / rules["source"]).resolve()
        if not source.is_file():
            raise ValueError(f"规范主源缺失，停止正式审计：{source}")
        rules["_path"], rules["_sha256"] = str(path), sha256(path)
        rules["_source_sha256"] = sha256(source)
        return rules
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError, re.error) as exc:
        raise DocumentFactoryError(f"规则文件无法加载：{exc}") from exc


class LintContext:
    def __init__(self, document, rules):
        self.document, self.rules = document, rules
        self.resolver = StyleResolver(document)
        self.findings = []
        self.main_paragraphs = [p for p in document.paragraphs if p.part == "word/document.xml"]

    def add(self, rule_id, obj, actual, expected, message, severity=None, status="FAIL"):
        definition = self.rules["rules"][rule_id]
        self.findings.append(Finding(rule_id, severity or definition["severity"],
                                     "Paragraph" if isinstance(obj, Paragraph) else "Run" if " / Run " in str(obj) else str(obj).split()[0],
                                     obj.location if isinstance(obj, Paragraph) else str(obj), actual, expected, message, status, definition["source"]))

    def check(self, rule_id, obj, condition, actual, expected, message, severity=None):
        self.add(rule_id, obj, actual, expected, message, "INFO" if condition else severity, "PASS" if condition else "FAIL")

    def compare_font(self, rule_id, obj, actual, expected, origin):
        if actual is None:
            self.add(rule_id, obj, {"font": actual, "origin": origin}, expected, "无法可靠解析字体，不能判为 PASS", severity="WARNING", status="UNSUPPORTED")
        else:
            aliases = self.rules.get("font_aliases", {}).get(expected, [expected])
            self.check(rule_id, obj, actual.casefold() in [s.casefold() for s in aliases], {"font": actual, "origin": origin}, expected, "按文字脚本检查有效字体")

    @property
    def counts(self):
        count = Counter(f.severity for f in self.findings)
        return {level: count[level] for level in ("ERROR", "WARNING", "INFO")}

    @property
    def result(self):
        return "FAIL" if self.counts["ERROR"] else "PASS"


def check_body_properties(ctx, obj, props):
    body = ctx.rules["body"]
    ind, spacing = props.get("ind", {}), props.get("spacing", {})
    if "firstLineChars" in ind:
        good = int(ind["firstLineChars"]) == body["first_line_indent_chars"] * 100 and not any(float(ind.get(k, 0)) for k in ("hanging", "hangingChars"))
        ctx.check("BODY002", obj, good, ind, {"firstLineChars": body["first_line_indent_chars"] * 100}, "首行缩进必须为 2 字符")
    elif "firstLine" in ind:
        ctx.add("BODY002", obj, ind, "2 字符缩进", "仅有物理长度缩进，不能保证字符单位等价", severity="WARNING", status="UNSUPPORTED")
    else:
        ctx.check("BODY002", obj, False, ind, "2 字符缩进", "未设置两字符首行缩进")
    good = spacing.get("line") == str(int(body["line_spacing"] * 240)) and spacing.get("lineRule", "auto") == "auto"
    ctx.check("BODY002", obj, good, spacing, "1.5 倍行距（line=360, lineRule=auto）", "检查行距单位与值")
    ctx.check("BODY002", obj, props.get("jc") == body["alignment"], props.get("jc"), body["alignment"], "正文应两端对齐")
    ctx.check("BODY003", obj, table_analyzer.zero_spacing(props), spacing, "段前/段后原则上 0", "正文段间距")


def analyze_styles_and_body(ctx):
    resolver, body = ctx.resolver, ctx.rules["body"]
    checked = set()
    for p in ctx.main_paragraphs:
        if p.in_toc or p.table is not None or not p.text.strip():
            continue
        level = resolver.heading_level(p)
        name = resolver.name(p.style_id)
        if level:
            ctx.check(f"STYLE00{level}", p, True, {"styleId": p.style_id, "name": name}, f"Heading {level}", "真实内置 Heading 段落样式")
            if p.style_id not in checked:
                checked.add(p.style_id)
                expected = ctx.rules[f"heading{level}"]
                style = ctx.document.styles[p.style_id]
                color = style.properties.get("rPr", {}).get("color", {})
                ctx.check("STYLE004", f"Style {name}", color.get("val", "").upper() == expected["color"] and not any(k.startswith("theme") for k in color), color, {"val": expected["color"], "themeColor": None}, "标题样式本身必须显式纯黑，不允许直接格式掩盖主题色")
                props = resolver.style(p.style_id).get("rPr", {})
                font, origin = resolver.font(props, "cn")
                ctx.compare_font("STYLE005", f"Style {name}", font, expected["chinese_font"], origin)
                ctx.check("STYLE005", f"Style {name}", props.get("sz") == str(int(expected["size_pt"] * 2)), props.get("sz"), expected["size_pt"], "标题样式字号（当前值单位：半磅）")
        elif name == body["style_name"]:
            ctx.check("BODY001", p, True, name, body["style_name"], "专用正文样式")
            check_body_properties(ctx, p, resolver.paragraph(p))
        else:
            outline = resolver.paragraph(p).get("outlineLvl")
            inherited_level = resolver.heading_level(p, inherited=True)
            candidate = inherited_level or (int(outline) + 1 if outline in ("0", "1", "2") else None)
            if candidate:
                ctx.add(f"STYLE00{candidate}", p, name, f"Heading {candidate}", "具有标题大纲级别或继承标题样式，但未使用真实 Heading；语义需复核", severity="WARNING")
            elif len(p.text.strip()) <= 100 and re.match(r"^\s*\d+(?:\.\d+){0,2}\s+\S", p.text) and any(ctx.resolver.run(p, run).get("b") for run in p.runs):
                prefix = re.match(r"^\s*(\d+(?:\.\d+){0,2})", p.text).group(1)
                guessed_level = prefix.count(".") + 1
                ctx.add(f"STYLE00{guessed_level}", p, name, f"Heading {guessed_level}", "短编号段落加粗，疑似直接格式模拟标题；语义不能确定，需人工确认", severity="WARNING")
            elif name.lower() in ("normal", "常规") and len(p.text.strip()) >= 40:
                props = resolver.paragraph(p)
                if props.get("jc") != "center" and not re.match(r"^\s*[图表]\s*\d", p.text):
                    ctx.add("BODY001", p, name, body["style_name"], "长 Normal 段落疑似正文，封面/图表说明等语义不能确定，需人工确认", severity="WARNING")
    body_styles = [s for s in ctx.document.styles.values() if s.name == body["style_name"] and s.kind == "paragraph"]
    ctx.check("BODY001", "Document", bool(body_styles), [s.style_id for s in body_styles], body["style_name"], "文档必须建立专用正文段落样式")
    for s in body_styles:
        props = resolver.style(s.style_id)
        check_body_properties(ctx, f"Style {s.name}", props)
        for script, expected in (("cn", body["chinese_font"]), ("ascii", body["latin_font"]), ("latin", body["latin_font"])):
            font, origin = resolver.font(props.get("rPr", {}), script)
            ctx.compare_font("FONT001" if script == "cn" else "FONT002", f"Style {s.name}", font, expected, origin)
        ctx.check("FONT003", f"Style {s.name}", props.get("rPr", {}).get("sz") == str(int(body["font_size_pt"] * 2)), props.get("rPr", {}).get("sz"), body["font_size_pt"], "正文样式小四（半磅单位）")


def analyze_runs(ctx):
    for p in ctx.main_paragraphs:
        if p.in_toc:
            continue
        name, heading = ctx.resolver.name(p.style_id), ctx.resolver.heading_level(p)
        if name == ctx.rules["body"]["style_name"] and p.table is None:
            cfg = ctx.rules["body"]
        elif heading and p.table is None:
            cfg = dict(ctx.rules[f"heading{heading}"])
            cfg["font_size_pt"] = cfg["size_pt"]
        elif name in ctx.rules["tables"]["required_styles"] + ctx.rules["tables"]["optional_styles"]:
            cfg = dict(ctx.rules["tables"])
            cfg["chinese_font"] = cfg["header_font"] if name == cfg["required_styles"][0] else cfg["body_font"]
        else:
            continue
        for index, run in enumerate(p.runs, 1):
            if not run.text.strip():
                continue
            props = ctx.resolver.run(p, run)
            location = f"{p.location} / Run {index}"
            if props.get("cs") or props.get("rtl"):
                ctx.add("FONT001", location, props, "可确定脚本选择的字体", "Run 强制复杂文字/RTL 字体选择，v0.1 不按普通中英文脚本判定", severity="WARNING", status="UNSUPPORTED")
                continue
            # Avoid treating Latin-only runs as Chinese font failures.
            if re.search(r"[\u3400-\u9fff\U00020000-\U0002fa1f]", run.text):
                font, origin = ctx.resolver.font(props, "cn")
                ctx.compare_font("FONT001", location, font, cfg["chinese_font"], origin)
            for script, pattern in (("ascii", r"[A-Za-z0-9]"), ("latin", r"[\u00c0-\u024f]")):
                if cfg.get("latin_font") and re.search(pattern, run.text):
                    font, origin = ctx.resolver.font(props, script)
                    ctx.compare_font("FONT002", location, font, cfg["latin_font"], origin)
            if props.get("sz") is None:
                ctx.add("FONT003", location, None, cfg["font_size_pt"], "未能确定有效字号", severity="WARNING", status="UNSUPPORTED")
            else:
                ctx.check("FONT003", location, props["sz"] == str(int(cfg["font_size_pt"] * 2)), props["sz"], cfg["font_size_pt"], "Run 有效字号（当前值单位：半磅），包含字符样式和直接格式")
            if heading:
                color = props.get("color", {})
                ctx.check("FONT004", location, color.get("val", "").upper() == cfg["color"] and not any(k.startswith("theme") for k in color), color, cfg["color"], "标题 Run 有效颜色")


def lint_document(document, rules):
    ctx = LintContext(document, rules)
    try:
        section_analyzer.analyze(ctx)
        analyze_styles_and_body(ctx)
        NumberingAnalyzer(document, ctx.resolver).analyze(ctx)
        toc_analyzer.analyze(ctx)
        table_analyzer.analyze(ctx)
        analyze_runs(ctx)
    except (KeyError, ValueError, TypeError) as exc:
        raise DocumentFactoryError(f"OOXML 或规则包含无法处理的属性值：{exc}") from exc
    for diagnostic in dict.fromkeys(document.diagnostics + ctx.resolver.diagnostics):
        ctx.add("STRUCT001", "Document", diagnostic, "可完整确定的结构", diagnostic, status="UNSUPPORTED")
    for table in document.tables:
        style = document.styles.get(table.style_id)
        if style and (style.properties.get("rPr") or document.parts["word/styles.xml"].xpath('./w:style[@w:styleId=$sid]/w:tblStylePr', sid=style.style_id, namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"})):
            ctx.add("STRUCT001", f"Table {table.index}", table.style_id, "人工核对条件表格样式", "v0.1 未完整合并 tblStylePr 条件格式；表格字体以段落/字符样式为依据", status="UNSUPPORTED")
    if sha256(document.path) != document.sha256:
        raise DocumentFactoryError("INPUT_CHANGED：审计期间输入文件发生变化")
    return ctx


def lint(path, rules):
    return lint_document(read_docx(path), load_rules(rules) if isinstance(rules, (str, Path)) else rules)
