from .docx_reader import NS, q


def analyze(ctx):
    config = ctx.rules["document"]
    if not ctx.document.sections:
        ctx.add("PAGE001", "Document", None, "显式节页面设置", "缺少 sectPr，页面设置不能确定", severity="WARNING", status="UNSUPPORTED")
    for section in ctx.document.sections:
        loc = f"Section {section['index']}"
        size = section["size"]
        try:
            dims = sorted([int(size["w"]), int(size["h"])])
            good = all(abs(a - b) <= config["tolerance_twips"] for a, b in zip(dims, sorted(config["page_size_twips"])))
            ctx.check("PAGE001", loc, good, size, config["page_size"], "纸张尺寸按 twip 比较（允许单位转换舍入）")
        except (KeyError, ValueError):
            ctx.add("PAGE001", loc, size, config["page_size"], "缺少或无法读取页面尺寸", severity="WARNING", status="UNSUPPORTED")
        landscape = size.get("orient", "portrait") == "landscape"
        ctx.check("PAGE002", loc, not landscape, size.get("orient", "portrait"), config["orientation"], "横向节允许用于宽表，需人工确认用途" if landscape else "默认纵向")
        for side, cm in config["margins_cm"].items():
            actual = section["margins"].get(side)
            if actual is None:
                ctx.add("PAGE003", loc, section["margins"], config["margins_cm"], f"未显式给出 {side} 页边距", severity="WARNING", status="UNSUPPORTED")
                continue
            ctx.check("PAGE003", loc, abs(int(actual) - cm / 2.54 * 1440) <= config["tolerance_twips"],
                      {side: {"twips": actual, "cm": round(int(actual) * 2.54 / 1440, 4)}}, {side: cm}, "默认页边距")
    first_heading = None
    top = [p for p in ctx.main_paragraphs if p.table is None and not p.in_toc]
    for p in top:
        name = p.text.strip().replace(" ", "").replace("\u3000", "")
        level = ctx.resolver.heading_level(p, inherited=True)
        if name == "编制说明":
            ctx.check("FRONT001", p, level != 1, ctx.resolver.name(p.style_id), "非 Heading 1", "编制说明标题不得作为一级标题")
        if name == "目录":
            outline = ctx.resolver.paragraph(p).get("outlineLvl")
            ctx.check("FRONT002", p, level is None and outline not in ("0", "1"),
                      {"style": ctx.resolver.name(p.style_id), "outlineLvl": outline}, "不进入 TOC 源", "目录标题自身不应进入目录")
        if level == 1 and name not in ("编制说明", "目录") and first_heading is None:
            first_heading = p
    if first_heading is not None:
        p = first_heading
        prior = [item for item in ctx.main_paragraphs if item.table is None and item.index < p.index]
        # Check the boundary after the last preceding visible paragraph, including empty break paragraphs.
        last_visible = next((i for i in reversed(prior) if i.text.strip()), None)
        boundary = [item for item in prior if last_visible is None or item.index >= last_visible.index]
        page_before = bool(ctx.resolver.paragraph(p).get("pageBreakBefore"))
        if p.page_break:
            # A break after heading text does not start the heading on a new page.
            seen_text = False
            for node in p.element.iter():
                if node.tag == q("t") and node.text:
                    seen_text = True
                if node.tag == q("br") and node.get(q("type")) == "page" and not seen_text:
                    page_before = True
        explicit = False
        for item in boundary:
            for node in item.element.iter():
                if node.tag == q("br") and node.get(q("type")) == "page":
                    explicit = True
                elif node.tag == q("t") and node.text and node.text.strip():
                    explicit = False
        section_boundary = any(s["paragraph_index"] in {i.index for i in boundary} and
                               (ctx.document.sections[n + 1]["break_type"] if n + 1 < len(ctx.document.sections) else "continuous")
                               in ("nextPage", "oddPage", "evenPage") for n, s in enumerate(ctx.document.sections))
        reliable = page_before or explicit or section_boundary or not prior
        ctx.check("FRONT003", p, reliable, {"pageBreakBefore": page_before, "precedingPageBreak": explicit, "sectionBreak": section_boundary},
                  "第一个 Heading 1 前有明确新页结构", "结构存在分页依据；不推断真实页码" if reliable else "未发现明确分页依据；自然分页须查看渲染结果")
