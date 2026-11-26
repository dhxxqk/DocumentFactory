"""Availability evidence and PDF font verification for opt-in academic tables."""
from collections import defaultdict
from pathlib import Path
import os
import re
import sys

from .academic_tables import _targets
from .docx_reader import NS, sha256
from .operations.academic_table import run_role, text_runs
from .renderer import available_backends


def _key(name):
    return re.sub('[^a-z0-9]', '', re.sub(r'^[A-Z]{6}\+', '', name).lower())


def validate(policy):
    if policy['backend'] != 'Word COM' or not isinstance(policy['faces'],dict) or not policy['faces']:
        raise ValueError('字体审计需要 Word COM 及显式字体映射')
    if not isinstance(policy.get('require_embedded',True),bool):
        raise ValueError('require_embedded 应为布尔值')
    for role, face in policy['faces'].items():
        if role not in ('caption','caption_bold','header','body','italic','script','numeric'):
            raise ValueError(f'未知字体角色：{role}')
        for key in ('reference','family','reason'):
            if not isinstance(face[key],str) or not face[key].strip():
                raise ValueError(f'{role}.{key} 需要明示')
        aliases=face['postscript']
        if not isinstance(aliases,list) or not aliases or any(not isinstance(a,str) or not _key(a) for a in aliases):
            raise ValueError(f'{role}.postscript 需要非空名称清单')
        if not 3<=float(face['render_size_pt'])<=100:
            raise ValueError(f'{role}.render_size_pt 超出范围')


def _runs(document,rules):
    for location,table,caption,profile,issue in _targets(document,rules):
        if issue:
            continue
        records=[]

        def collect(paragraph,area):
            for run in text_runs(paragraph):
                text=''.join(run.xpath('./w:t/text()',namespaces=NS))
                if not text.strip():
                    continue
                role=run_role(run,area)
                base=profile['caption']['font'] if area=='caption' else profile['font']
                font=profile.get('font_overrides',{}).get(role,base)
                records.append((role,text,font['latin']))

        if caption is not None:
            collect(caption,'caption')
        for index,row in enumerate(table.findall('w:tr',NS)):
            for column,cell in enumerate(row.findall('w:tc',NS),1):
                area='header' if index==0 else 'numeric' if column in profile.get('numeric_columns',[]) else 'body'
                for paragraph in cell.findall('w:p',NS):
                    collect(paragraph,area)
        yield location,records


def _windows_faces():
    if sys.platform!='win32' or any(key not in os.environ for key in ('WINDIR','LOCALAPPDATA')):
        return None
    import winreg
    names={}
    for hive,folder in ((winreg.HKEY_LOCAL_MACHINE,Path(os.environ['WINDIR'])/'Fonts'),
                        (winreg.HKEY_CURRENT_USER,Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts')):
        try:
            with winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
                for index in range(winreg.QueryInfoKey(key)[1]):
                    label,value,_=winreg.EnumValue(key,index)
                    if isinstance(value,str):
                        names[label]=folder/os.path.expandvars(value)
        except FileNotFoundError:
            continue
        except OSError:
            return None
    return names


def _styles(role):
    return role in ('header','caption_bold'), role=='italic'


def _find_face(catalog,family,bold,italic):
    import pymupdf
    name=_key(family)
    variants={'','regular','bold','italic','bolditalic','oblique','boldoblique'}
    for label,path in catalog.items():
        normalized=_key(label.split(' (')[0])
        if not normalized.startswith(name) or normalized[len(name):] not in variants or not path.is_file():
            continue
        try:
            font=pymupdf.Font(fontfile=str(path))
        except (RuntimeError,ValueError,OSError):
            continue
        actual=_key(font.name)
        if actual.startswith(name) and actual[len(name):] in variants and (bool(font.is_bold),bool(font.is_italic))==(bold,italic):
            return font,label,path
    return None


def preflight(document,rules):
    policy=rules['academic_tables']['font_audit']
    backend=policy['backend']
    characters=defaultdict(set)
    configured=defaultdict(set)
    for _,runs in _runs(document,rules):
        for role,text,family in runs:
            characters[role].update(c for c in text if not c.isspace())
            configured[role].add(family)
    catalog=_windows_faces() if available_backends().get(backend) else None
    results=[]
    for role,chars in sorted(characters.items()):
        face=policy['faces'].get(role)
        entry=dict(role=role,configured_families=sorted(configured[role]),characters=''.join(sorted(chars)),status='UNKNOWN')
        if face is None or configured[role]!={face['family']}:
            entry.update(status='MISMATCH',message='Configured run role differs from the approved target face')
        elif catalog is None:
            entry.update(message='Word COM availability or the installed-font registry could not be verified')
        else:
            entry.update(family=face['family'],reference=face['reference'],substitution_reason=face['reason'])
            resolved=_find_face(catalog,face['family'],*_styles(role))
            if resolved is None:
                entry.update(status='MISSING_FACE',message='Installed family and required variant could not be verified')
            else:
                font,label,path=resolved
                missing=''.join(c for c in sorted(chars) if not font.has_glyph(ord(c),fallback=False))
                entry.update(status='MISSING_GLYPH' if missing else 'AVAILABLE',file=path.name,
                             registry_name=label,installed_face=font.name,missing_characters=missing)
        results.append(entry)
    return dict(status='PASS' if results and all(r['status']=='AVAILABLE' for r in results) else 'FAIL',
                backend=backend,evidence='Windows font registry, face metadata and local glyph coverage. PDF verification is separate.',faces=results)


def _embedded(pdf,xref):
    kind,descriptor=pdf.xref_get_key(xref,'FontDescriptor')
    if kind=='xref':
        descriptor_ref=int(descriptor.split()[0])
        return any(pdf.xref_get_key(descriptor_ref,name)[0]=='xref' for name in ('FontFile','FontFile2','FontFile3'))
    if kind=='dict':
        return bool(re.search(r'/FontFile[23]?\s+\d+\s+\d+\s+R',descriptor))
    kind,descendant=pdf.xref_get_key(xref,'DescendantFonts')
    if kind=='array' and (ref:=re.search(r'(\d+)\s+\d+\s+R',descendant)):
        child=int(ref[1])
        if child!=xref:
            kind,descriptor=pdf.xref_get_key(child,'FontDescriptor')
            if kind=='xref':
                return any(pdf.xref_get_key(int(descriptor.split()[0]),name)[0]=='xref'
                           for name in ('FontFile','FontFile2','FontFile3'))
    return False


def _stream(pdf):
    chars=[]
    for page in pdf:
        resources=defaultdict(list)
        for resource in page.get_fonts(full=True):
            resources[_key(resource[3])].append(dict(xref=resource[0],name=resource[3],type=resource[2],
                                                    embedded=_embedded(pdf,resource[0]) if resource[0]>0 else False))
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    evidence=resources[_key(span['font'])]
                    for char in span['chars']:
                        if not char['c'].isspace():
                            chars.append(dict(char, page=page.number+1,font=span['font'],size_pt=round(span['size'],3),
                                              bold=bool(span['flags']&16),italic=bool(span['flags']&2),resources=evidence))
    return chars


def audit_pdf(document,rules,render_result):
    import pymupdf
    policy=rules['academic_tables']['font_audit']
    if not render_result.pdf or render_result.status!='SUCCESS' or render_result.backend!=policy['backend']:
        return {'status':'UNKNOWN','message':'A PDF from the configured renderer is required','tables':[]}
    path=Path(render_result.pdf)
    try:
        with pymupdf.open(path) as pdf:
            chars=_stream(pdf)
    except (OSError,RuntimeError,ValueError):
        return {'status':'UNKNOWN','message':'PDF font resources could not be read','tables':[]}
    actual=''.join(c['c'] for c in chars)
    outcomes=[]
    for location,runs in _runs(document,rules):
        target=''.join(c for _,text,_ in runs for c in text if not c.isspace())
        start=actual.find(target) if target else -1
        if start<0 or actual.find(target,start+1)>=0:
            outcomes.append(dict(location=location,status='UNKNOWN',message='Table text cannot be uniquely aligned to PDF characters'))
            continue
        checked=[]
        cursor=start
        for role,text,family in runs:
            size=len(''.join(text.split()))
            observed=chars[cursor:cursor+size]
            cursor+=size
            face=policy['faces'].get(role)
            missing_resources=any(not c['resources'] for c in observed)
            unembedded=any(not any(r['embedded'] for r in c['resources']) for c in observed)
            if not face or missing_resources or (policy.get('require_embedded',True) and unembedded):
                status='UNKNOWN'
            else:
                aliases={_key(a) for a in face['postscript']}
                bold,italic=_styles(role)
                status='MATCH' if all(_key(c['font']) in aliases and (c['bold'],c['italic'])==(bold,italic)
                                      and abs(c['size_pt']-face['render_size_pt'])<=.18 for c in observed) else 'MISMATCH'
            checked.append(dict(role=role,text=text,family=family,status=status,expected=face,observed=observed))
        status='MISMATCH' if any(item['status']=='MISMATCH' for item in checked) else (
            'MATCH' if checked and all(item['status']=='MATCH' for item in checked) else 'UNKNOWN')
        outcomes.append(dict(location=location,status=status,runs=checked))
    status='MISMATCH' if any(item['status']=='MISMATCH' for item in outcomes) else (
        'MATCH' if outcomes and all(item['status']=='MATCH' for item in outcomes) else 'UNKNOWN')
    return dict(status=status,backend=render_result.backend,pdf_sha256=sha256(path),tables=outcomes)
