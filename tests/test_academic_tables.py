from zipfile import ZipFile

from lxml import etree
import pytest

from conftest import ROOT, paragraph
from document_factory.docx_reader import NS, q, read_docx, sha256
from document_factory.lint_engine import lint, load_rules
from document_factory.models import DocumentFactoryError
from document_factory.normalizer import normalize


RULES=ROOT/'rules/academic_three_line_v1.yaml'
PAPER=ROOT/'rules/academic_ijlct_oup_v1.yaml'
M='http://schemas.openxmlformats.org/officeDocument/2006/math'


def sample(label='AcademicThreeLine', first_properties='', second_properties='', body_extra='', cols=2):
    # The fixture deliberately conflicts at the style, table, row and cell levels.
    style='<w:tblPr><w:tblStyle w:val="Grid"/><w:tblBorders><w:left w:val="double"/></w:tblBorders>'
    marker=f'<w:tblCaption w:val="{label}"/>' if label else ''
    grid='<w:tblGrid>'+'<w:gridCol w:w="1000"/>'*cols+'</w:tblGrid>'
    def row(contents,properties):
        return '<w:tr>'+properties+''.join(f'<w:tc>{cell}</w:tc>' for cell in contents)+'</w:tr>'
    overrides='<w:tblPrEx><w:tblBorders><w:insideH w:val="double"/></w:tblBorders><w:shd w:fill="00FF00"/></w:tblPrEx>'
    cell='<w:tcPr><w:tcBorders><w:start w:val="double"/><w:right w:val="double"/></w:tcBorders><w:shd w:fill="FF0000"/></w:tcPr>'
    math=(f'<m:oMath xmlns:m="{M}"><m:r><m:t>x</m:t></m:r></m:oMath>')
    text=paragraph('X',run_properties='<w:i/>')[:-6]+'<w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>1</w:t></w:r>'
    text+='<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>'+math+body_extra+'</w:p>'
    return ('<w:tbl>'+style+marker+'</w:tblPr>'+grid+
            row([paragraph('Head')]*cols,overrides+first_properties)+
            row([cell+text]*cols,second_properties)+'</w:tbl>')


def tables(path):
    root=read_docx(path).parts['word/document.xml']
    return root.findall('w:body/w:tbl',NS)


def test_explicit_selection_border_conflicts_math_and_repeat(make_docx,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    source=make_docx(paragraph('Outside')+sample(label='')+sample())
    old_hash=sha256(source)
    old_tables=tables(source)
    first=normalize(source,RULES,'output/result.docx','reports/first.md')
    assert first.status=='PASS' and first.before_counts['ERROR']>0 and first.after_counts['ERROR']==0
    assert first.source_unchanged and sha256(source)==old_hash
    unrelated,table=tables(first.output_path)
    assert etree.tostring(unrelated)==etree.tostring(old_tables[0])
    assert table.find('w:tblPr/w:tblStyle',NS) is None
    assert table.find('w:tblPr/w:tblBorders/w:top',NS).get(q('val'))=='nil'
    assert table.find('w:tr/w:tblPrEx/w:tblBorders',NS) is None
    assert table.find('w:tr/w:trPr/w:tblHeader',NS) is not None
    upper,body=table.findall('w:tr',NS)
    for cell in upper.findall('w:tc',NS):
        props=cell.find('w:tcPr/w:tcBorders',NS)
        assert props.find('w:top',NS).get(q('sz'))=='8'
        assert props.find('w:bottom',NS).get(q('sz'))=='4'
        assert props.find('w:start',NS) is None and props.find('w:right',NS).get(q('val'))=='nil'
    assert body.find('w:tc/w:tcPr/w:tcBorders/w:bottom',NS).get(q('sz'))=='8'
    assert body.find('w:tc/w:tcPr/w:shd',NS).get(q('val'))=='nil'
    assert body.find('.//w:i',NS) is not None
    assert body.xpath('.//w:vertAlign/@w:val',namespaces=NS)==['subscript','superscript']*2
    math=lambda value: [etree.tostring(e) for e in value.findall(f'.//{{{M}}}oMath')]
    assert math(table)==math(old_tables[1])
    second=normalize(first.output_path,RULES,'output/repeat.docx','reports/repeat.md')
    assert second.status=='PASS' and second.changes==[]
    with ZipFile(first.output_path) as a,ZipFile(second.output_path) as b:
        assert a.read('word/document.xml')==b.read('word/document.xml')


@pytest.mark.parametrize('fragment',[
    sample().replace('<w:tcPr>', '<w:tcPr><w:gridSpan w:val="2"/>',1),
    sample(second_properties='<w:trPr><w:tblHeader/></w:trPr>'),
    sample().replace('</w:p></w:tc>', '</w:p>'+sample(label='')+'</w:tc>',1),
    sample()+sample(),
    sample(label=''),
],ids=['merged','additional-header','nested','duplicate-role','unmarked'])
def test_unsupported_or_unmatched_tables_are_not_modified(fragment,make_docx,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    source=make_docx(fragment)
    result=normalize(source,RULES,'output/unmodified.docx','reports/unmodified.md')
    assert result.status=='FAIL' and not result.changes
    assert result.remaining_findings[0]['rule_id']=='TABLEA000'
    with ZipFile(source) as a,ZipFile(result.output_path) as b:
        assert a.read('word/document.xml')==b.read('word/document.xml')


def test_paper_inheritance_and_caption_scope(make_docx,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    rules=load_rules(PAPER)
    assert 'academic_three_line_v1.yaml' in rules['_inherited_rules']
    assert rules['academic_tables']['format']['borders']['top']['width_pt']==.504
    tag='IJLCT-Table-1'
    invalid=make_docx(paragraph('Unrelated caption')+sample(label=tag))
    assert lint(invalid,PAPER).counts['ERROR']==1
    source=make_docx(paragraph('Table 1.  Input feature.',run_properties='<w:b/>')+sample(label=tag))
    result=normalize(source,PAPER,'output/paper.docx','reports/paper.md')
    assert result.status=='PASS'
    table=tables(result.output_path)[0]
    assert table.xpath('./w:tblGrid/w:gridCol/@w:w',namespaces=NS)==['1089','3730']
    assert table.find('w:tr/w:tc/w:tcPr/w:tcBorders/w:top',NS).get(q('sz'))=='4'
    caption=table.getprevious()
    assert caption.find('w:pPr/w:keepNext',NS) is not None
    assert caption.find('w:r/w:rPr/w:b',NS) is not None


def test_invalid_profile_fails_loading(tmp_path):
    base=RULES.read_text(encoding='utf-8')
    broken=tmp_path/'bad.yaml'
    broken.write_text(base.replace('width_pt: 0.5','width_pt: -0.5'),encoding='utf-8')
    with pytest.raises(DocumentFactoryError,match='header'):
        load_rules(broken)
