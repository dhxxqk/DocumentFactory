import re


def zero_indent(props):
    ind = props.get("ind", {})
    return all(float(ind.get(k, 0)) == 0 for k in ("firstLine", "firstLineChars", "hanging", "hangingChars", "left", "leftChars", "right", "rightChars", "start", "startChars", "end", "endChars"))


def zero_spacing(props):
    spacing = props.get("spacing", {})
    return all(float(spacing.get(k, 0)) == 0 for k in ("before", "after", "beforeLines", "afterLines")) and all(spacing.get(k, "0") in ("0", "false", "off") for k in ("beforeAutospacing", "afterAutospacing"))


def allowed_line_spacing(props, config):
    spacing = props.get("spacing", {})
    rule, line = spacing.get("lineRule", "auto"), spacing.get("line")
    return ("single" in config["line_spacing_allowed"] and rule == "auto" and line == "240") or ("exact" in config["line_spacing_allowed"] and rule == "exact" and line is not None and int(line) > 0)


def analyze(ctx):
    config = ctx.rules["tables"]
    required = config["required_styles"]
    allowed = required + config["optional_styles"]
    body_name = ctx.rules["body"]["style_name"]
    if ctx.document.tables:
        for name in required:
            found = [s for s in ctx.document.styles.values() if s.name == name and s.kind == "paragraph"]
            ctx.check("TABLE010", f"Style {name}", bool(found), [s.style_id for s in found], name, "表格要求独立段落样式")
    for style in ctx.document.styles.values():
        if style.name not in allowed or style.kind != "paragraph":
            continue
        chain = ctx.resolver.chain(style.style_id)
        ctx.check("TABLE005", f"Style {style.name}", not any(s.name == body_name for s in chain[:-1]),
                  [s.name for s in chain], "不得直接或间接 basedOn 正文", "检查完整 basedOn 链")
        effective = ctx.resolver.style(style.style_id)
        ctx.check("TABLE004", f"Style {style.name}", zero_indent(effective), effective.get("ind"), "首行/左/右缩进全部为 0", "检查有效样式缩进（含字符单位和悬挂缩进）")
        ctx.check("TABLE006", f"Style {style.name}", zero_spacing(effective), effective.get("spacing"), "段前/段后为 0", "检查有效段间距")
        own = style.properties
        ind, spacing, fonts = own.get("ind", {}), own.get("spacing", {}), own.get("rPr", {}).get("rFonts", {})
        explicit = any(k in ind for k in ("firstLine", "firstLineChars")) and any(k in ind for k in ("left", "start")) and any(k in ind for k in ("right", "end")) and all(k in spacing for k in ("before", "after", "line")) and all(k in fonts for k in ("eastAsia", "ascii", "hAnsi"))
        ctx.check("TABLE007", f"Style {style.name}", explicit, own, "显式定义缩进、行距、段前段后、中英文字体", "表格样式不能仅依赖继承")
        ctx.check("TABLE007", f"Style {style.name}", allowed_line_spacing(effective, config), effective.get("spacing"), "单倍或固定正值行距", "固定值是否适度需人工查看渲染")
        expected_cn = config["header_font"] if style.name == required[0] else config["body_font"]
        rpr = effective.get("rPr", {})
        cn, source = ctx.resolver.font(rpr, "cn")
        ctx.compare_font("TABLE008", f"Style {style.name}", cn, expected_cn, source)
        for script in ("ascii", "latin"):
            face, origin = ctx.resolver.font(rpr, script)
            ctx.compare_font("TABLE008", f"Style {style.name}", face, config["latin_font"], origin)
        ctx.check("TABLE008", f"Style {style.name}", rpr.get("sz") == str(int(config["font_size_pt"] * 2)), rpr.get("sz"), config["font_size_pt"], "表格字体为五号（OOXML sz 单位为半磅）")
    for table in ctx.document.tables:
        if table.part != "word/document.xml":
            ctx.add("STRUCT001", f"{table.part} Table {table.index}", "附属部件表格", "人工复核用途", "页眉页脚/注释中的布局表不强行套用正文表格语义", severity="INFO", status="UNSUPPORTED")
            continue
        table_paragraphs = [p for p in ctx.main_paragraphs if p.table == table.index]
        # §3.2 explicitly permits cover metadata tables with separate 14pt styles.
        # A style-name hint is not enough to prove semantics, so downgrade conflicts.
        cover_candidate = bool(table_paragraphs) and all(re.match(config.get("cover_style_pattern", r"(?!)"), ctx.resolver.name(p.style_id), re.I) for p in table_paragraphs if p.text.strip()) and any(p.text.strip() for p in table_paragraphs)
        for row in table.rows:
            header = row["repeat_header"] or (config["header_strategy"] == "first_row_or_repeat" and row["index"] == 1)
            for p in (p for p in ctx.main_paragraphs if p.table == table.index and p.row == row["index"]):
                name = ctx.resolver.name(p.style_id)
                if name == body_name:
                    ctx.add("TABLE001", p, name, allowed, "表格单元格禁止继续使用正文样式")
                if cover_candidate:
                    ctx.add("TABLE003", p, name, "按 §3.2 封面信息表或 §6.1 内容表确认", "专用封面样式提示此表可能为封面布局；规范封面与内容表要求不同，不能按普通内容表确定判错", severity="WARNING", status="UNSUPPORTED")
                    continue
                if header:
                    ctx.check("TABLE002", p, name == required[0], name, required[0], "重复表头标记" if row["repeat_header"] else "首行仅作表头候选，封面信息表等需人工确认", severity="ERROR" if row["repeat_header"] else "WARNING")
                else:
                    ctx.check("TABLE003", p, name in [required[1]] + config["optional_styles"], name, [required[1]] + config["optional_styles"], "普通表格段落必须使用专用样式")
                props = ctx.resolver.paragraph(p)
                ctx.check("TABLE004", p, zero_indent(props), props.get("ind"), "首行/左/右缩进全部为 0", "含段落直接格式的最终缩进")
                ctx.check("TABLE006", p, zero_spacing(props), props.get("spacing"), "段前/段后为 0", "含段落直接格式的最终间距")
                # Table style conditional formatting is not fully resolved in v0.1.
                if name in allowed:
                    ctx.check("TABLE007", p, allowed_line_spacing(props, config), props.get("spacing"), "单倍或固定正值行距", "检查段落直接格式是否覆盖表格行距")
        ctx.add("TABLE009", f"Table {table.index}", [row["index"] for row in table.rows if row["repeat_header"]],
                "跨页表格应重复表头", "XML 可读取重复标记，但无法确定表格是否实际跨页", severity="INFO", status="UNSUPPORTED")
