"""Document Format Conversion Pipeline.

Word -> Word 格式套用：输入既有 DOCX，选择已注册模板，输出格式规范统一的
保护副本与可追踪审核报告。转换只调整格式（样式脚手架、段落样式重指派、
Run 级字体/字号、页面设置），**不重新生成、不改写任何正文内容**。

Public API:

- inputs:    DocumentInputProvider, load_input_docx
- converter: DocumentFormatConverter, convert_document
- models:    ConversionResult
- classifier: RoleAssignment, classify_paragraphs
- structure: ensure_template_styles, reassign_paragraph_styles
"""
from .classifier import RoleAssignment, classify_paragraphs
from .converter import DocumentFormatConverter, convert_document
from .inputs import DocumentInputProvider, load_input_docx
from .models import ConversionResult
from .structure import ensure_template_styles, reassign_paragraph_styles

__all__ = [
    "RoleAssignment",
    "classify_paragraphs",
    "DocumentFormatConverter",
    "convert_document",
    "DocumentInputProvider",
    "load_input_docx",
    "ConversionResult",
    "ensure_template_styles",
    "reassign_paragraph_styles",
]
