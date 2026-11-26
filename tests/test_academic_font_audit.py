from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from document_factory import academic_font_audit as audit
from document_factory.docx_reader import read_docx
from document_factory.models import DocumentFactoryError, RenderResult
from document_factory.normalizer import normalize


def configuration():
    faces={
        'body':dict(reference='Reference Roman',family='Test Family',reason='Authorized substitute',
                    postscript=['Helvetica'],render_size_pt=8),
        'header':dict(reference='Reference Bold',family='Test Family',reason='Authorized substitute',
                      postscript=['Helvetica-Bold'],render_size_pt=8),
    }
    return {'academic_tables':{'font_audit':{'backend':'Word COM','require_embedded':False,'faces':faces}}}


@pytest.fixture
def sample(monkeypatch):
    monkeypatch.setattr(audit,'_runs',lambda *args: iter([('Table sample',[
        ('header','Header','Test Family'),('body','Contents','Test Family')])]))


@pytest.mark.parametrize('mode,status', [('available','PASS'),('face','FAIL'),('glyph','FAIL'),('backend','FAIL')])
def test_preflight_checks_variant_glyph_and_backend(mode,status,sample,monkeypatch):
    monkeypatch.setattr(audit,'available_backends',lambda:{'Word COM':mode!='backend'})
    monkeypatch.setattr(audit,'_windows_faces',lambda:{'test':'test'})
    checker=SimpleNamespace(name='Test Face',has_glyph=lambda code,**kw: mode!='glyph' or code!=ord('C'))
    monkeypatch.setattr(audit,'_find_face',lambda catalog,family,bold,italic:
                        None if bold and mode=='face' else (checker,'Font label',Path('test.ttf')))
    result=audit.preflight(None,configuration())
    assert result['status']==status
    expected={'available':'AVAILABLE','face':'MISSING_FACE','glyph':'MISSING_GLYPH','backend':'UNKNOWN'}
    assert expected[mode] in {face['status'] for face in result['faces']}


@pytest.mark.parametrize('font,text,amount,status',[('hebo','Contents',8,'MATCH'),('helv','Contents',8,'MISMATCH'),
    ('heit','Contents',8,'MISMATCH'),('hebo','Contents',9,'MISMATCH'),('hebo','Different',8,'UNKNOWN')])
def test_pdf_checks_actual_faces_flags_size_and_alignment(font,text,amount,status,tmp_path,sample):
    path=tmp_path/'sample.pdf'
    with pymupdf.open() as pdf:
        page=pdf.new_page()
        page.insert_text((50,50),'Header',fontname=font,fontsize=amount)
        page.insert_text((50,70),text,fontname='helv',fontsize=8)
        pdf.save(path)
    result=audit.audit_pdf(None,configuration(),RenderResult('SUCCESS','Word COM',str(path)))
    assert result['status']==status
    if status=='MATCH':
        glyph=result['tables'][0]['runs'][0]['observed'][0]
        assert glyph['resources'][0]['name']=='Helvetica-Bold' and glyph['origin'][1]==50
        rules=configuration()
        rules['academic_tables']['font_audit']['require_embedded']=True
        assert audit.audit_pdf(None,rules,RenderResult('SUCCESS','Word COM',str(path)))['status']=='UNKNOWN'


def test_verified_subset_alias_and_missing_render():
    assert audit._key('BCDEEE+Arial-BoldMT') == audit._key('Arial-BoldMT')
    assert audit.audit_pdf(None,configuration(),RenderResult('RENDER_FAILED'))['status']=='UNKNOWN'


def test_failed_preflight_prevents_output(make_docx,tmp_path,monkeypatch):
    from document_factory import normalizer
    monkeypatch.chdir(tmp_path)
    source=make_docx()
    monkeypatch.setattr(normalizer,'load_rules',lambda path:{'scope':'academic_tables'})
    monkeypatch.setattr(normalizer,'lint',lambda *args: SimpleNamespace(document=read_docx(source),
        font_preflight={'status':'FAIL','faces':[{'role':'body','status':'MISSING_FACE'}]}))
    with pytest.raises(DocumentFactoryError,match='MISSING_FACE'):
        normalize(source,'rules.yaml','output/result.docx','reports/audit.md')
    assert not (tmp_path/'output/result.docx').exists()
