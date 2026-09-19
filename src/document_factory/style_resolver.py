"""Property cascade with provenance, per-script fonts and theme diagnostics."""
from copy import deepcopy
import re
from .docx_reader import NS, q

TOGGLES = {"b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "vanish"}


def merge(base, override, *, style_layer=False):
    result = deepcopy(base)
    for key, value in override.items():
        if key == "rFonts" and isinstance(value, dict):
            fonts = dict(result.get(key, {}))
            # Each direct/theme pair is one cascade slot (MS-OI29500 §17.3.2.26e).
            for direct, theme in (("ascii", "asciiTheme"), ("hAnsi", "hAnsiTheme"), ("eastAsia", "eastAsiaTheme"), ("cs", "cstheme")):
                if direct in value or theme in value:
                    fonts.pop(direct, None)
                    fonts.pop(theme, None)
            fonts.update(value)
            result[key] = fonts
        elif key == "color" and isinstance(value, dict):
            result[key] = deepcopy(value)
        elif isinstance(value, dict):
            result[key] = merge(result.get(key, {}) if isinstance(result.get(key, {}), dict) else {}, value, style_layer=style_layer)
        elif style_layer and key in TOGGLES:
            if value:
                result[key] = not result.get(key, False)
        else:
            result[key] = value
    return result


class StyleResolver:
    def __init__(self, document):
        self.document = document
        self.diagnostics = []

    def chain(self, style_id):
        seen, chain = set(), []
        while style_id:
            if style_id in seen:
                self.diagnostics.append(f"样式 basedOn 循环：{style_id}")
                break
            seen.add(style_id)
            style = self.document.styles.get(style_id)
            if style is None:
                self.diagnostics.append(f"样式引用不存在：{style_id}")
                break
            chain.append(style)
            style_id = style.based_on
        return list(reversed(chain))

    def style(self, style_id, include_defaults=True):
        props = deepcopy(self.document.defaults) if include_defaults else {}
        for s in self.chain(style_id):
            props = merge(props, s.properties, style_layer=True)
        return props

    def paragraph(self, paragraph):
        return merge(self.style(paragraph.style_id), paragraph.properties)

    def run(self, paragraph, run):
        # Paragraph mark rPr is not direct character formatting for each text run.
        effective = self.style(paragraph.style_id).get("rPr", {})
        for style in self.chain(run.properties.get("rStyle")):
            effective = merge(effective, style.properties.get("rPr", {}), style_layer=True)
        return merge(effective, run.properties)

    def trace(self, paragraph, run=None):
        layers = [{"source": "docDefaults", "properties": self.document.defaults}]
        layers += [{"source": f"style:{s.style_id}", "properties": s.properties} for s in self.chain(paragraph.style_id)]
        layers.append({"source": "paragraph direct", "properties": paragraph.properties})
        if run is not None:
            layers += [{"source": f"character style:{s.style_id}", "properties": s.properties} for s in self.chain(run.properties.get("rStyle"))]
            layers.append({"source": "run direct", "properties": run.properties})
        return layers

    def name(self, style_id):
        style = self.document.styles.get(style_id)
        return style.name if style else style_id

    def heading_level(self, paragraph, inherited=False):
        styles = self.chain(paragraph.style_id) if inherited else [self.document.styles.get(paragraph.style_id)]
        for style in reversed(styles):
            if style is None or style.kind != "paragraph" or style.custom:
                continue
            # Built-in Word names are canonical in OOXML even on localized Office.
            match = re.fullmatch(r"(?:heading\s*|标题\s*)([1-3])", style.name, re.I)
            if match:
                return int(match[1])
        return None

    def font(self, properties, script):
        fonts = properties.get("rFonts", {})
        key = {"cn": "eastAsia", "ascii": "ascii", "latin": "hAnsi", "cs": "cs"}[script]
        theme_key = {"ascii": "asciiTheme", "hAnsi": "hAnsiTheme", "eastAsia": "eastAsiaTheme", "cs": "cstheme"}[key]
        theme = fonts.get(theme_key) or (fonts.get("csTheme") if key == "cs" else None)
        if theme:
            root = self.document.parts.get("word/theme/theme1.xml")
            branch = "majorFont" if theme.startswith("major") else "minorFont"
            # eastAsia theme requires language/script fallback when ea is empty.
            if root is not None:
                item = root.find(f".//a:fontScheme/a:{branch}/a:{'ea' if key == 'eastAsia' else 'cs' if key == 'cs' else 'latin'}", NS)
                face = item.get("typeface") if item is not None else None
                if face:
                    return face, f"theme:{theme}"
                if key == "eastAsia":
                    lang = None
                    settings = self.document.parts.get("word/settings.xml")
                    if settings is not None:
                        language = settings.find("w:themeFontLang", NS)
                        lang = language.get(q("eastAsia")) if language is not None else None
                    lang = lang or properties.get("lang", {}).get("eastAsia")
                    script_name = {"zh-CN": "Hans", "zh-SG": "Hans", "zh-TW": "Hant", "zh-HK": "Hant", "ja-JP": "Jpan", "ko-KR": "Hang"}.get(lang)
                    if script_name:
                        item = root.find(f'.//a:fontScheme/a:{branch}/a:font[@script="{script_name}"]', NS)
                        if item is not None and item.get("typeface"):
                            return item.get("typeface"), f"theme:{theme}/{script_name}"
            return None, f"主题字体无法确定：{theme}"
        return fonts.get(key), f"rFonts:{key}"
