from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
import uuid
from document_factory.lint_engine import load_rules

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config):
    # Keep generated fixtures in output; unique base avoids deleting existing data.
    if config.option.basetemp is None:
        config.option.basetemp = str(ROOT / 'output' / f'pytest_{uuid.uuid4().hex[:12]}')

BODY_STYLE = '''<w:style w:type="paragraph" w:styleId="Body"><w:name w:val="正文"/><w:pPr><w:ind w:firstLineChars="200"/><w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="仿宋"/><w:sz w:val="24"/></w:rPr></w:style>'''
HEADING_STYLES = ''.join(f'''<w:style w:type="paragraph" w:styleId="Heading{i}"><w:name w:val="heading {i}"/><w:pPr><w:outlineLvl w:val="{i-1}"/></w:pPr><w:rPr><w:rFonts w:eastAsia="黑体"/><w:color w:val="000000"/><w:sz w:val="{size}"/></w:rPr></w:style>''' for i, size in ((1, 32), (2, 28), (3, 24)))
SECTION = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1587" w:bottom="1474" w:left="1587" w:right="1474"/></w:sectPr>'
NUMBERING = '<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="multilevel"/>' + ''.join(f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading{i+1}"/><w:lvlText w:val="' + '.'.join(f'%{j+1}' for j in range(i+1)) + '"/></w:lvl>' for i in range(3)) + '</w:abstractNum><w:num w:numId="5"><w:abstractNumId w:val="1"/></w:num>'


def paragraph(text='测试文本', style='Body', properties='', run_properties=''):
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{properties}</w:pPr><w:r><w:rPr>{run_properties}</w:rPr><w:t>{text}</w:t></w:r></w:p>'


def table(body_style='Body', header_style='Body'):
    return '<w:tbl><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid><w:tr><w:tc>' + paragraph('表头', header_style) + '</w:tc></w:tr><w:tr><w:tc>' + paragraph('内容', body_style) + '</w:tc></w:tr></w:tbl>'


@pytest.fixture
def rules():
    return load_rules(ROOT / 'rules/grid_tech_v1_4.yaml')


@pytest.fixture
def make_docx(tmp_path):
    def build(body='', styles=None, numbering=None, extra=None, section=SECTION):
        path = tmp_path / f'fixture_{len(list(tmp_path.glob("*.docx")))}.docx'
        parts = {'word/document.xml': f'<w:document xmlns:w="{W}"><w:body>{body}{section}</w:body></w:document>',
                 'word/styles.xml': f'<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:styleId="Normal" w:default="1"><w:name w:val="Normal"/></w:style>{BODY_STYLE + HEADING_STYLES if styles is None else styles}</w:styles>',
                 'word/settings.xml': f'<w:settings xmlns:w="{W}"><w:updateFields w:val="true"/></w:settings>'}
        if numbering is not None:
            parts['word/numbering.xml'] = f'<w:numbering xmlns:w="{W}">{numbering}</w:numbering>'
        parts.update(extra or {})
        with ZipFile(path, 'w', ZIP_DEFLATED) as z:
            for key, value in parts.items():
                z.writestr(key, value)
        return path
    return build
