"""Rules for opt-in academic tables, shared by lint and normalize."""
from copy import deepcopy
import math
import re

from .docx_reader import NS, q
from .operations import OperationContext
from .operations.academic_table import apply_three_line_table
from .templates.loader import deep_merge


SCOPE='academic_tables'
ASPECTS={
    'TABLEA001':'三线、边框冲突和底色',
    'TABLEA002':'表宽、列宽、边距、行高与重复表头',
    'TABLEA003':'单元格段落与字体，保留斜体和上下标',
    'TABLEA004':'表题位置、字体与段落',
}


def _number(value, name, low, high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{name} 必须在 [{low}, {high}] 内')


def _font(font):
    if set(font)-{'latin','east_asia','size_pt','color'}:
        raise ValueError('学术表格字体只配置字号、字族和颜色，局部斜体和上下标从原文保留')
    if any(not isinstance(font[key],str) or not font[key].strip() for key in ('latin','east_asia')):
        raise ValueError('字体名称不能为空')
    _number(font['size_pt'],'字号',4,72)
    if font['size_pt']*2 % 1 or not re.fullmatch(r'[A-F0-9]{6}',font['color']):
        raise ValueError('字号使用半磅单位，颜色使用六位大写 RGB')


def _validate_profile(profile):
    allowed={'font','borders','cell_margins_pt','header_height_pt','body_line_pt','column_widths_pt',
             'header_alignments','body_alignments','first_body_pad_pt','last_body_pad_pt','caption','script_size_pt','body_bold',
             'font_overrides','body_line_rule','math_line_rule','subscript_position_pt','numeric_columns'}
    if set(profile)-allowed:
        raise ValueError(f'未知学术表格属性：{set(profile)-allowed}')
    lines=profile['borders']
    if set(lines)!={'top','header','bottom'}:
        raise ValueError('需要且仅配置顶线、表头底线及底线')
    for name,rule in lines.items():
        _number(rule['width_pt'],name,0.25,12)
        if set(rule)!={'width_pt','color','style'} or rule['style'] not in ('single','double','dashed','dotted') or not re.fullmatch(r'[A-F0-9]{6}',rule['color']):
            raise ValueError(f'无效的 {name} 边框配置')
    if set(profile['cell_margins_pt'])!={'left','right','top','bottom'}:
        raise ValueError('单元格需要四向边距')
    for side,value in profile['cell_margins_pt'].items():
        _number(value,f'{side} 边距',0,72)
    for key in ('header_height_pt','body_line_pt'):
        _number(profile[key],key,4,144)
    for key in ('first_body_pad_pt','last_body_pad_pt'):
        _number(profile.get(key,0),key,0,72)
    _font(profile['font'])
    if 'script_size_pt' in profile:
        _number(profile['script_size_pt'],'上下标基准字号',4,72)
        if profile['script_size_pt']*2 % 1:
            raise ValueError('上下标基准字号使用半磅单位')
    if profile.get('body_bold') is not None and not isinstance(profile['body_bold'],bool):
        raise ValueError('body_bold 应为布尔值或 null')
    for rule in ('body_line_rule','math_line_rule'):
        if profile.get(rule,'atLeast') not in ('atLeast','exact'):
            raise ValueError(f'{rule} 只支持 atLeast 或 exact')
    if 'subscript_position_pt' in profile:
        _number(profile['subscript_position_pt'],'下标垂直偏移',-4,4)
        if profile['subscript_position_pt']*2 % 1:
            raise ValueError('下标垂直偏移使用半磅单位')
    for role,font in profile.get('font_overrides',{}).items():
        if role not in ('header','italic','script','caption_bold','numeric'):
            raise ValueError(f'不支持的字体局部覆盖：{role}')
        _font(font)
    if any(type(col) is not int or col<1 for col in profile.get('numeric_columns',[])):
        raise ValueError('numeric_columns 使用从 1 开始的列号')
    widths=profile['column_widths_pt']
    if widths is not None:
        if not isinstance(widths,list) or not widths:
            raise ValueError('column_widths_pt 需要正宽度列表或 null（复用原有列网格）')
        for width in widths:
            _number(width,'列宽',1,1584)
    for key in ('header_alignments','body_alignments'):
        alignments=profile[key]
        if not isinstance(alignments,list) or any(a not in ('left','center','right') for a in alignments):
            raise ValueError(f'{key} 应为 left/center/right 列表')
        if alignments and widths is not None and len(alignments)!=len(widths):
            raise ValueError(f'{key} 与列宽数量不一致')
    if profile['caption'] is not None:
        caption=profile['caption']
        if set(caption)!={'font','line_pt','space_after_pt'}:
            raise ValueError('需要配置表题字体、行距和段后间距')
        _font(caption['font'])
        _number(caption['line_pt'],'表题行距',4,144)
        _number(caption['space_after_pt'],'表题段后间距',0,144)


def validate_rules(rules):
    if any(key not in rules for key in ('version','spec_version','source','rules',SCOPE)):
        raise ValueError('学术表规则缺少必需配置节')
    config=rules[SCOPE]
    _validate_profile(config['format'])
    labels=set()
    if not isinstance(config['targets'],list) or not config['targets']:
        raise ValueError('必须显式声明学术表目标')
    for target in config['targets']:
        label=target['table_caption']
        if not isinstance(label,str) or not label.strip() or label in labels or set(target)-{'table_caption','caption_text','format'}:
            raise ValueError('学术表目标需要唯一的 w:tblCaption 标记')
        if 'caption_text' in target and (not isinstance(target['caption_text'],str) or not target['caption_text'].strip()):
            raise ValueError('caption_text 应为非空字符串')
        labels.add(label)
        _validate_profile(deep_merge(config['format'],target.get('format',{})))
    if any(key not in rules['rules'] for key in (*ASPECTS,'TABLEA000')):
        raise ValueError('学术表缺少审计规则定义')


def _unsupported(table,caption,expect_caption,profile):
    if table.getparent().tag!=q('body') or table.findall('.//w:tbl',NS):
        return '嵌套表格或非顶层表格超出 V1 范围'
    incompatible=('gridSpan','hMerge','vMerge','gridBefore','gridAfter','tblpPr','bidiVisual','txbxContent',
                  'ins','del','moveFrom','moveTo','tblPrChange','tcPrChange','trPrChange')
    if any(table.find(f'.//w:{child}',NS) is not None for child in incompatible):
        return '包含合并、浮动、方向控制或修订标记，无法安全规范化'
    rows=table.findall('w:tr',NS)
    cols=table.findall('w:tblGrid/w:gridCol',NS)
    if len(rows)<2 or not cols or any(len(row.findall('w:tc',NS))!=len(cols) for row in rows):
        return '需要矩形列网格、一个表头和至少一个表体行'
    if table.xpath('./w:tr[position() > 1]/w:trPr/w:tblHeader[not(@w:val="0" or @w:val="false" or @w:val="off")]',namespaces=NS):
        return '多行或非首行表头超出 V1 范围'
    if profile['column_widths_pt'] is None:
        try:
            profile['column_widths_pt']=[int(col.get(q('w'),0))/20 for col in cols]
        except ValueError:
            return '列网格宽度缺少有效数字'
    for key in ('column_widths_pt','header_alignments','body_alignments'):
        if profile[key] and len(profile[key])!=len(cols):
            return f'{key} 与实际列数不一致'
    if any(col>len(cols) for col in profile.get('numeric_columns',[])):
        return '数值格式列号超出实际范围'
    if any(w<=0 for w in profile['column_widths_pt']):
        return '列网格宽度必须为正'
    if profile['caption'] is not None and (caption is None or caption.tag!=q('p')):
        return '所选表格前缺少显式题注段落'
    if expect_caption is not None:
        actual=''.join(caption.xpath('.//w:t/text()',namespaces=NS)) if caption is not None else ''
        if actual!=expect_caption:
            return f'题注文本不匹配：{actual}'
    return None


def _targets(document,rules):
    tables={}
    for i,table in enumerate(document.parts['word/document.xml'].findall('.//w:tbl',NS),1):
        label=table.find('w:tblPr/w:tblCaption',NS)
        if label is not None:
            tables.setdefault(label.get(q('val')),[]).append((i,table))
    config=rules[SCOPE]
    for target in config['targets']:
        key=target['table_caption']
        matches=tables.get(key,[])
        if not matches:
            continue
        if len(matches)!=1:
            yield f'Table {key}',None,None,None,'同一表格标记出现多次'
            continue
        index,table=matches[0]
        profile=deep_merge(config['format'],target.get('format',{}))
        caption=table.getprevious() if profile['caption'] is not None or 'caption_text' in target else None
        issue=_unsupported(table,caption,target.get('caption_text'),profile)
        yield f'Table {index} [{key}]',table,caption if profile['caption'] is not None else None,profile,issue


def _operations(rules,changes,location,table,caption,profile):
    contexts=tuple(OperationContext(changes,'Table',location,key,rules['rules'][key]['source'])
                   for key in ('TABLEA002','TABLEA001','TABLEA003','TABLEA004'))
    apply_three_line_table(table,caption,profile,contexts)


def analyze(ctx):
    found=False
    for location,table,caption,profile,issue in _targets(ctx.document,ctx.rules):
        found=True
        if issue:
            ctx.add('TABLEA000',location,issue,'显式标记的矩形单表头表格','保留原表',status='UNSUPPORTED')
            continue
        changes=[]
        _operations(ctx.rules,changes,location,deepcopy(table),deepcopy(caption),profile)
        for key,label in ASPECTS.items():
            differences=[c for c in changes if c['rule']==key]
            if not differences and (key!='TABLEA004' or caption is not None):
                ctx.check(key,location,True,'符合配置','符合配置',label)
            for diff in differences:
                ctx.check(key,diff['location'],False,diff['before'],diff['after'],f'{label} / {diff["property"]}')
    if not found:
        labels=[target['table_caption'] for target in ctx.rules[SCOPE]['targets']]
        ctx.add('TABLEA000','Table',None,labels,'找不到任何显式学术表格目标')


def normalize(document,rules):
    changes=[]
    stats={'page':{},'style_binding':{},'objects':{'regular_tables':0},'warnings':[]}
    for location,table,caption,profile,issue in _targets(document,rules):
        if issue:
            stats['warnings'].append({'kind':'TABLEA000','location':location,'reason':issue})
            continue
        stats['objects']['regular_tables']+=1
        _operations(rules,changes,location,table,caption,profile)
    return changes, {'word/document.xml'} if changes else set(), stats
