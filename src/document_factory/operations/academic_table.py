"""Three-line table operations for an explicitly selected regular table."""
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP

from ..docx_reader import NS, q
from ._oxml import PPR_ORDER, RPR_ORDER, TCPR_ORDER, attributes, ensure_child, local, set_properties, set_toggle
from .font import apply_font
from .paragraph import apply_alignment, apply_indent, apply_keep_next, apply_spacing


TABLE_ORDER = (
    'tblStyle', 'tblpPr', 'tblOverlap', 'bidiVisual', 'tblStyleRowBandSize', 'tblStyleColBandSize',
    'tblW', 'jc', 'tblCellSpacing', 'tblInd', 'tblBorders', 'shd', 'tblLayout', 'tblCellMar',
    'tblLook', 'tblCaption', 'tblDescription', 'tblPrChange',
)
ROW_ORDER = ('cnfStyle','divId','gridBefore','gridAfter','wBefore','wAfter','cantSplit',
             'trHeight','tblHeader','tblCellSpacing','jc','hidden','ins','del','trPrChange')
EDGES = ('top','left','bottom','right','insideH','insideV')
SPACING_OVERRIDES = {'beforeLines','afterLines','beforeAutospacing','afterAutospacing'}
INDENT_OVERRIDES = {'leftChars','rightChars','start','end','startChars','endChars','firstLineChars','hanging','hangingChars'}


def units(value, scale):
    return int((Decimal(str(value))*scale).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _exact(parent, name, wanted, ctx, order=None):
    previous = attributes(parent.find(f'w:{name}',NS))
    set_properties(parent,name,wanted,previous.keys()-wanted.keys(),ctx,prop=name,order=order)


def _clear(parent,names,ctx):
    if parent is None:
        return
    tags={q(name) for name in names}
    for child in list(parent):
        if child.tag in tags:
            before = attributes(child) if len(child)==0 else [local(e) for e in child]
            parent.remove(child)
            ctx.record(local(child),before,None)


def _line(definition):
    if definition is None:
        return {'val':'nil'}
    return {'val':definition['style'],'sz':units(definition['width_pt'],8),
            'color':definition['color'],'space':0}


def _borders(parent,name,top,bottom,ctx,order,*,cells=False):
    props=ensure_child(parent,name,order)
    sides=(*EDGES,'tl2br','tr2bl') if cells else EDGES
    _clear(props,{'start','end'},ctx)
    for where in sides:
        _exact(props,where,_line({'top':top,'bottom':bottom}.get(where)),ctx,sides)


def _margins(parent,name,values,ctx,order):
    props=ensure_child(parent,name,order)
    _clear(props,{'start','end'},ctx)
    for side in EDGES[:4]:
        _exact(props,side,{'w':units(values[side],20),'type':'dxa'},ctx,EDGES)


def _paragraph(paragraph, alignment, line, ctx, *, after=0):
    ppr=ensure_child(paragraph,'pPr',PPR_ORDER)
    borders=ensure_child(ppr,'pBdr',PPR_ORDER)
    edges=(*EDGES[:4],'between','bar')
    _clear(borders,{'start','end'},ctx)
    for side in edges:
        _exact(borders,side,{'val':'nil'},ctx,edges)
    _exact(ppr,'shd',{'val':'nil'},ctx,PPR_ORDER)
    apply_alignment(paragraph,alignment,ctx)
    apply_spacing(paragraph,{'before':0,'after':units(after,20),'line':units(line,20),'lineRule':'atLeast'},
                  ctx,remove=SPACING_OVERRIDES)
    apply_indent(paragraph,{'left':0,'right':0,'firstLine':0},ctx,remove=INDENT_OVERRIDES)
    set_toggle(ppr,'contextualSpacing',False,ctx,prop='contextualSpacing',order=PPR_ORDER)
    set_toggle(ppr,'snapToGrid',False,ctx,prop='snapToGrid',order=PPR_ORDER)


def _runs(paragraph,profile,ctx,*,override_bold=None,script_size=None):
    for i,run in enumerate(paragraph.findall('.//w:r',NS),1):
        if run.xpath('ancestor::*[namespace-uri()="http://schemas.openxmlformats.org/officeDocument/2006/math"]'):
            continue
        run_ctx=replace(ctx,location=f'{ctx.location} / Run {i}')
        run_profile=dict(profile, bold=override_bold)
        special=run.find('w:rPr/w:vertAlign',NS)
        if script_size is not None and special is not None and special.get(q('val')) in ('subscript','superscript'):
            run_profile['size_pt']=script_size
        apply_font(run,run_profile,run_ctx)
        rpr=run.find('w:rPr',NS)
        _exact(rpr,'shd',{'val':'nil'},run_ctx,RPR_ORDER)
        _exact(rpr,'highlight',{'val':'none'},run_ctx,RPR_ORDER)


def apply_three_line_table(table,caption,profile,contexts):
    """Apply one prepared profile. Callers validate target shape first."""
    geometry,lines,content,caption_ctx=contexts
    widths=[units(width,20) for width in profile['column_widths_pt']]
    table_props=ensure_child(table,'tblPr',('tblPr','tblGrid','tr'))
    _clear(table_props,{'tblStyle','tblLook'},lines)
    _exact(table_props,'tblW',{'w':sum(widths),'type':'dxa'},geometry,TABLE_ORDER)
    _exact(table_props,'tblLayout',{'type':'fixed'},geometry,TABLE_ORDER)
    _exact(table_props,'jc',{'val':'left'},geometry,TABLE_ORDER)
    _exact(table_props,'tblInd',{'w':0,'type':'dxa'},geometry,TABLE_ORDER)
    _exact(table_props,'tblCellSpacing',{'w':0,'type':'dxa'},geometry,TABLE_ORDER)
    _exact(table_props,'shd',{'val':'nil'},lines,TABLE_ORDER)
    border=profile['borders']
    # A single owner per visible edge avoids duplicate strokes in Word's PDF export.
    # Table-level nils suppress a default table style. The cell edges supply all three rules.
    _borders(table_props,'tblBorders',None,None,lines,TABLE_ORDER)
    _margins(table_props,'tblCellMar',profile['cell_margins_pt'],geometry,TABLE_ORDER)
    for i,(column,width) in enumerate(zip(table.findall('w:tblGrid/w:gridCol',NS),widths),1):
        old=column.get(q('w'))
        if old!=str(width):
            column.set(q('w'),str(width))
            geometry.record(f'gridCol[{i}]',old,str(width))

    rows=table.findall('w:tr',NS)
    for i,row in enumerate(rows):
        header=i==0
        row_geometry=replace(geometry,location=f'{geometry.location} / Row {i+1}')
        row_lines=replace(lines,location=row_geometry.location)
        # Row-local table overrides can defeat the table-level properties above.
        row_exception=row.find('w:tblPrEx',NS)
        _clear(row_exception,{'tblW','jc','tblCellSpacing','tblInd','tblBorders','shd','tblLayout','tblCellMar','tblLook'},row_lines)
        row_props=ensure_child(row,'trPr',('tblPrEx','trPr','tc'))
        _clear(row_props,{'tblCellSpacing','jc'},row_geometry)
        set_toggle(row_props,'cantSplit',True,row_geometry,prop='cantSplit',order=ROW_ORDER)
        if header:
            set_toggle(row_props,'tblHeader',True,row_geometry,prop='tblHeader',order=ROW_ORDER)
        row_height=profile['header_height_pt'] if header else profile['body_line_pt']
        _exact(row_props,'trHeight',{'val':units(row_height,20),'hRule':'atLeast'},row_geometry,ROW_ORDER)
        top=border['top'] if header else None
        bottom=border['header'] if header else border['bottom'] if i==len(rows)-1 else None
        alignment=profile['header_alignments'] if header else profile['body_alignments']
        for j,(cell,width) in enumerate(zip(row.findall('w:tc',NS),widths)):
            loc=f'{row_geometry.location} / Cell {j+1}'
            cell_lines=replace(row_lines,location=loc)
            cell_geometry=replace(row_geometry,location=loc)
            cell_content=replace(content,location=loc)
            cp=ensure_child(cell,'tcPr',('tcPr','p'))
            _exact(cp,'tcW',{'w':width,'type':'dxa'},cell_geometry,TCPR_ORDER)
            _exact(cp,'shd',{'val':'nil'},cell_lines,TCPR_ORDER)
            _clear(cp,{'noWrap','tcFitText'},cell_geometry)
            _borders(cp,'tcBorders',top,bottom,cell_lines,TCPR_ORDER,cells=True)
            _exact(cp,'vAlign',{'val':'center' if header else 'top'},cell_geometry,TCPR_ORDER)
            margins=dict(profile['cell_margins_pt'])
            if i==1:
                margins['top']+=profile.get('first_body_pad_pt',0)
            if i==len(rows)-1:
                margins['bottom']+=profile.get('last_body_pad_pt',0)
            _margins(cp,'tcMar',margins,cell_geometry,TCPR_ORDER)
            column_alignment=alignment[j] if alignment else ('left' if j==0 else 'center')
            for k,paragraph in enumerate(cell.findall('w:p',NS),1):
                pctx=replace(cell_content,location=f'{loc} / Paragraph {k}')
                _paragraph(paragraph,column_alignment,profile['body_line_pt'],pctx)
                _runs(paragraph,profile['font'],pctx,override_bold=True if header else profile.get('body_bold'),
                      script_size=profile.get('script_size_pt'))

    if caption is not None:
        style=profile['caption']
        _paragraph(caption,'left',style['line_pt'],caption_ctx,after=style['space_after_pt'])
        apply_keep_next(caption,True,caption_ctx)
        _runs(caption,style['font'],caption_ctx)
