import re
from .docx_reader import NS, q, on


def switches(instruction):
    return {match.group(1).lower(): (match.group(2) or match.group(3) or "") for match in re.finditer(r'\\([a-z])(?:\s+(?:"([^"]*)"|([^\s\\]+)))?', instruction, re.I)}


def analyze(ctx):
    fields = [f for f in ctx.document.fields if f.kind == "TOC" and f.part == "word/document.xml" and f.complete]
    if ctx.rules["toc"]["required"]:
        ctx.check("TOC001", "Document", bool(fields), [f.instruction for f in fields], "真实完整 Word TOC Field", "按 fldSimple / begin-instrText-separate-end 检测目录域")
    levels = ctx.rules["toc"]["levels"]
    expected = f"{min(levels)}-{max(levels)}"
    for field in fields:
        options = switches(field.instruction)
        loc = f"{field.part} / Paragraph {field.paragraph_index}"
        if re.search(r"\\{2,}[a-z]", field.instruction, re.I):
            ctx.add("TOC002", loc, field.instruction, f'单反斜线开关 \\o "{expected}"', "域代码含连续反斜线，不能证明 Word 按预期识别层级；请在 Word 中查看域代码", severity="WARNING", status="UNSUPPORTED")
        else:
            ctx.check("TOC002", loc, options.get("o") == expected, options, f'\\o "{expected}"', "目录标题范围应为 1–2 级")
        if any(k in options for k in ("t", "f", "a", "c")):
            ctx.add("TOC002", loc, options, "只收录 Heading 1 / Heading 2", "存在额外目录来源开关，需复核实际目录源", severity="WARNING", status="UNSUPPORTED")
        expected_options = switches(ctx.rules["toc"]["expected_field_logic"])
        missing = sorted(set(expected_options) - set(options))
        if missing:
            ctx.add("TOC004", loc, missing, ctx.rules["toc"]["expected_field_logic"], "目录缺少规范建议的等价域开关")
    for p in ctx.main_paragraphs:
        if not p.in_toc and p.table is None and re.search(r"(?:\.{3,}|…{2,}|\t)\s*\d+\s*$", p.text):
            ctx.add("TOC003", p, p.text, "目录条目由 TOC 域生成", "疑似手写点线/页码；仅凭结构不能确认语义")
        if fields and any("u" in switches(f.instruction) for f in fields) and not p.in_toc:
            outline = ctx.resolver.paragraph(p).get("outlineLvl")
            if outline in ("0", "1") and not ctx.resolver.heading_level(p):
                ctx.add("TOC002", p, {"outlineLvl": outline}, "只收录 Heading 1 / Heading 2", "\\u 可能额外收录具有大纲级别的非 Heading 段落", severity="WARNING")
    settings = ctx.document.parts.get("word/settings.xml")
    update = settings.find("w:updateFields", NS) if settings is not None else None
    if ctx.rules["toc"].get("update_fields"):
        ctx.check("TOC005", "word/settings.xml", update is not None and on(update.get(q("val"), "1")),
                  update.get(q("val"), "1") if update is not None else None, True, "应设置打开 Word 时更新域；本审计不修改域")
