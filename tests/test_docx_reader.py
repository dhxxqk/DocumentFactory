from zipfile import ZipFile
import pytest
from document_factory.docx_reader import read_docx, sha256
from document_factory.models import DocumentFactoryError
from conftest import paragraph, table, W


def test_zip_styles_sections_relationships(make_docx):
    path = make_docx(paragraph(), extra={'word/_rels/document.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="header1.xml" Type="header"/></Relationships>', 'word/header1.xml': f'<w:hdr xmlns:w="{W}">{paragraph("页眉")}</w:hdr>'})
    before = sha256(path)
    d = read_docx(path)
    assert d.styles['Body'].name == '正文'
    assert d.sections[0]['margins']['top'] == '1587'
    assert d.sections[0]['break_type'] == 'nextPage'
    assert len(d.paragraphs) == 2
    assert d.relationships['word/_rels/document.xml.rels'][0]['Target'] == 'header1.xml'
    assert sha256(path) == before


def test_direct_formatting_and_breaks(make_docx):
    text = paragraph('中文 English', properties='<w:pageBreakBefore/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="3"/></w:numPr>', run_properties='<w:rFonts w:eastAsia="黑体" w:ascii="Arial" w:asciiTheme="majorAscii"/><w:b/><w:sz w:val="28"/>')
    d = read_docx(make_docx(text.replace('</w:r>', '<w:br w:type="page"/></w:r>')))
    p = d.paragraphs[0]
    assert p.page_break and p.properties['pageBreakBefore']
    assert p.properties['numPr'] == {'ilvl': '1', 'numId': '3'}
    assert p.runs[0].properties['rFonts']['asciiTheme'] == 'majorAscii'
    assert p.runs[0].properties['b'] is True


def test_merged_and_nested_tables(make_docx):
    body = table().replace('<w:tc>', '<w:tc><w:tcPr><w:gridSpan w:val="2"/><w:vMerge w:val="restart"/></w:tcPr>', 1)
    body = body.replace('</w:tc>', table() + '</w:tc>', 1)
    d = read_docx(make_docx(body))
    assert len(d.tables) == 2
    assert d.tables[0].rows[0]['cells'][0]['grid_span'] == 2
    assert d.tables[0].rows[0]['cells'][0]['v_merge'] == 'restart'
    assert len([p for p in d.paragraphs if p.table == 1]) == 2
    assert len([p for p in d.paragraphs if p.table == 2]) == 2


def test_missing_and_bad_package(tmp_path):
    with pytest.raises(DocumentFactoryError, match='不存在'):
        read_docx(tmp_path / 'missing.docx')
    path = tmp_path / 'broken.docx'
    path.write_text('not a zip')
    with pytest.raises(DocumentFactoryError, match='ZIP'):
        read_docx(path)
    with ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', '<bad')
    with pytest.raises(DocumentFactoryError, match='OOXML'):
        read_docx(path)


def test_dtd_rejected(make_docx):
    path = make_docx(extra={'word/document.xml': '<!DOCTYPE root [<!ENTITY secret SYSTEM "file:///private">]><root>&secret;</root>'})
    with pytest.raises(DocumentFactoryError, match='DTD'):
        read_docx(path)
