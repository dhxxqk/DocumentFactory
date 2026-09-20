# DocumentFactory Template Apply Report

## 1. 基本信息

- 实际生成时间（含时区）：2026-09-20T23:47:34+08:00
- 模板：G:\Workflows\DocumentFactory\testcases\template\template_demo.docx
- 目标输入：G:\Workflows\DocumentFactory\testcases\template\target_demo.docx
- 输出：G:\Workflows\DocumentFactory\output\template\target_demo_formatted.docx
- Template Profile schema：1.0
- 模板 SHA-256：d4dd7faf0ac4d56ce13d1e28b5813ae7cd6f3e59b223f78f7adfce319ad39909
- 输入 SHA-256：40b99ea3b5691477fca55f82cf1551fae09f443e75ce9249890a375ddeabafb2
- 输出 SHA-256：35bc70cf6b2d84fac5b9f7bfa8e30c3decce764519d791c06b0cd7ba4ddd9a68
- 模板未变化：True
- 输入未变化：True

## 2. 迁移结果

**RESULT: PASS**

- Style 映射：5
- 属性修改记录：70
- Profile 验证不一致：0

## 3. Style 映射

| Role | Template style | Target style |
|---|---|---|
| Normal | Normal | Normal |
| Title | Title | Title |
| Heading1 | Heading1 | Heading1 |
| Heading2 | Heading2 | Heading2 |
| Heading3 | Heading3 | Heading3 |

## 4. 修改明细

| 对象 | 位置 | 属性 | 修改前 | 修改后 |
|---|---|---|---|---|
| Style | Style Normal | font | {"ascii": "Calibri", "eastAsia": "宋体", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "仿宋", "hAnsi": "Times New Roman"} |
| Style | Style Normal | font_size_pt | {"val": "20"} | {"val": "24"} |
| Style | Style Normal | bold | null | false |
| Style | Style Normal | italic | null | false |
| Style | Style Title | spacing | {} | {"after": "0", "before": "0", "line": "360", "lineRule": "auto"} |
| Style | Style Title | indent | {} | {"firstLineChars": "200"} |
| Style | Style Title | font | {"ascii": "Calibri", "eastAsia": "宋体", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "方正小标宋简体", "hAnsi": "Times New Roman"} |
| Style | Style Title | font_size_pt | {"val": "20"} | {"val": "36"} |
| Style | Style Title | italic | null | false |
| Style | Style heading 1 | alignment | {} | {"val": "both"} |
| Style | Style heading 1 | spacing | {"after": "120", "before": "240"} | {"after": "120", "before": "240", "line": "360", "lineRule": "auto"} |
| Style | Style heading 1 | indent | {} | {"firstLineChars": "200"} |
| Style | Style heading 1 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Style | Style heading 1 | font_size_pt | {"val": "20"} | {"val": "32"} |
| Style | Style heading 1 | italic | null | false |
| Style | Style heading 2 | alignment | {} | {"val": "both"} |
| Style | Style heading 2 | spacing | {} | {"after": "0", "before": "0", "line": "360", "lineRule": "auto"} |
| Style | Style heading 2 | indent | {} | {"firstLineChars": "200"} |
| Style | Style heading 2 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Style | Style heading 2 | font_size_pt | {"val": "20"} | {"val": "28"} |
| Style | Style heading 2 | italic | null | false |
| Style | Style heading 3 | alignment | {} | {"val": "both"} |
| Style | Style heading 3 | spacing | {} | {"after": "0", "before": "0", "line": "360", "lineRule": "auto"} |
| Style | Style heading 3 | indent | {} | {"firstLineChars": "200"} |
| Style | Style heading 3 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Style | Style heading 3 | font_size_pt | {"val": "20"} | {"val": "24"} |
| Style | Style heading 3 | italic | null | false |
| Run | word/document.xml / Paragraph 1 / 2026 年项目建议书 / Run 1 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "方正小标宋简体", "hAnsi": "Times New Roman"} |
| Run | word/document.xml / Paragraph 1 / 2026 年项目建议书 / Run 1 | font_size_pt | {"val": "18"} | {"val": "36"} |
| Run | word/document.xml / Paragraph 1 / 2026 年项目建议书 / Run 1 | bold | null | true |
| Run | word/document.xml / Paragraph 1 / 2026 年项目建议书 / Run 1 | italic | null | false |
| Run | word/document.xml / Paragraph 2 / 项目概述 / Run 1 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Run | word/document.xml / Paragraph 2 / 项目概述 / Run 1 | font_size_pt | {"val": "18"} | {"val": "32"} |
| Run | word/document.xml / Paragraph 2 / 项目概述 / Run 1 | color | {} | {"val": "000000"} |
| Run | word/document.xml / Paragraph 2 / 项目概述 / Run 1 | bold | null | true |
| Run | word/document.xml / Paragraph 2 / 项目概述 / Run 1 | italic | null | false |
| Run | word/document.xml / Paragraph 3 / 建设目标 / Run 1 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Run | word/document.xml / Paragraph 3 / 建设目标 / Run 1 | font_size_pt | {"val": "18"} | {"val": "28"} |
| Run | word/document.xml / Paragraph 3 / 建设目标 / Run 1 | color | {} | {"val": "000000"} |
| Run | word/document.xml / Paragraph 3 / 建设目标 / Run 1 | bold | null | true |
| Run | word/document.xml / Paragraph 3 / 建设目标 / Run 1 | italic | null | false |
| Run | word/document.xml / Paragraph 4 / 范围边界 / Run 1 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Run | word/document.xml / Paragraph 4 / 范围边界 / Run 1 | font_size_pt | {"val": "18"} | {"val": "24"} |
| Run | word/document.xml / Paragraph 4 / 范围边界 / Run 1 | color | {} | {"val": "000000"} |
| Run | word/document.xml / Paragraph 4 / 范围边界 / Run 1 | bold | null | true |
| Run | word/document.xml / Paragraph 4 / 范围边界 / Run 1 | italic | null | false |
| Run | word/document.xml / Paragraph 5 / 本项目用于验证模板驱动格式迁移，不改变任何文字内容。 / Run 1 | font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Times New Roman", "eastAsia": "仿宋", "hAnsi": "Times New Roman"} |
| Run | word/document.xml / Paragraph 5 / 本项目用于验证模板驱动格式迁移，不改变任何文字内容。 / Run 1 | font_size_pt | {"val": "18"} | {"val": "24"} |
| Run | word/document.xml / Paragraph 5 / 本项目用于验证模板驱动格式迁移，不改变任何文字内容。 / Run 1 | bold | null | false |
| Run | word/document.xml / Paragraph 5 / 本项目用于验证模板驱动格式迁移，不改变任何文字内容。 / Run 1 | italic | null | false |
| Paragraph | word/document.xml / Paragraph 6 / Table 1, Row 1, Cell 1 / 字段 | table_header_alignment | {} | {"val": "center"} |
| Run | word/document.xml / Paragraph 6 / Table 1, Row 1, Cell 1 / 字段 / Run 1 | table_header_font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Arial", "eastAsia": "黑体", "hAnsi": "Arial"} |
| Run | word/document.xml / Paragraph 6 / Table 1, Row 1, Cell 1 / 字段 / Run 1 | table_header_font_size_pt | {"val": "18"} | {"val": "22"} |
| Run | word/document.xml / Paragraph 6 / Table 1, Row 1, Cell 1 / 字段 / Run 1 | table_header_bold | null | true |
| Run | word/document.xml / Paragraph 6 / Table 1, Row 1, Cell 1 / 字段 / Run 1 | table_header_italic | null | false |
| Paragraph | word/document.xml / Paragraph 7 / Table 1, Row 1, Cell 2 / 要求 | table_header_alignment | {} | {"val": "center"} |
| Run | word/document.xml / Paragraph 7 / Table 1, Row 1, Cell 2 / 要求 / Run 1 | table_header_font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Arial", "eastAsia": "黑体", "hAnsi": "Arial"} |
| Run | word/document.xml / Paragraph 7 / Table 1, Row 1, Cell 2 / 要求 / Run 1 | table_header_font_size_pt | {"val": "18"} | {"val": "22"} |
| Run | word/document.xml / Paragraph 7 / Table 1, Row 1, Cell 2 / 要求 / Run 1 | table_header_bold | null | true |
| Run | word/document.xml / Paragraph 7 / Table 1, Row 1, Cell 2 / 要求 / Run 1 | table_header_italic | null | false |
| Paragraph | word/document.xml / Paragraph 8 / Table 1, Row 2, Cell 1 / 范围 | table_body_alignment | {} | {"val": "left"} |
| Run | word/document.xml / Paragraph 8 / Table 1, Row 2, Cell 1 / 范围 / Run 1 | table_body_font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Arial", "eastAsia": "宋体", "hAnsi": "Arial"} |
| Run | word/document.xml / Paragraph 8 / Table 1, Row 2, Cell 1 / 范围 / Run 1 | table_body_font_size_pt | {"val": "18"} | {"val": "20"} |
| Run | word/document.xml / Paragraph 8 / Table 1, Row 2, Cell 1 / 范围 / Run 1 | table_body_bold | null | false |
| Run | word/document.xml / Paragraph 8 / Table 1, Row 2, Cell 1 / 范围 / Run 1 | table_body_italic | null | false |
| Paragraph | word/document.xml / Paragraph 9 / Table 1, Row 2, Cell 2 / 完成项目建议书 | table_body_alignment | {} | {"val": "left"} |
| Run | word/document.xml / Paragraph 9 / Table 1, Row 2, Cell 2 / 完成项目建议书 / Run 1 | table_body_font | {"ascii": "Calibri", "eastAsia": "微软雅黑", "hAnsi": "Calibri"} | {"ascii": "Arial", "eastAsia": "宋体", "hAnsi": "Arial"} |
| Run | word/document.xml / Paragraph 9 / Table 1, Row 2, Cell 2 / 完成项目建议书 / Run 1 | table_body_font_size_pt | {"val": "18"} | {"val": "20"} |
| Run | word/document.xml / Paragraph 9 / Table 1, Row 2, Cell 2 / 完成项目建议书 / Run 1 | table_body_bold | null | false |
| Run | word/document.xml / Paragraph 9 / Table 1, Row 2, Cell 2 / 完成项目建议书 / Run 1 | table_body_italic | null | false |

## 5. Profile 验证

| 位置 | 属性 | 预期 | 实际 |
|---|---|---|---|
| - | - | 全部已应用 | 全部已应用 |

## 6. 现有 lint 回归

Template Apply 不改变既有规则 severity，也不以电网规则代替模板 Profile；以下计数仅证明现有 lint 可对输出继续执行。

| 阶段 | RESULT | ERROR | WARNING | INFO |
|---|---|---:|---:|---:|
| 应用前 | FAIL | 45 | 3 | 33 |
| 应用后 | FAIL | 31 | 3 | 47 |

## 7. 本版边界

- 只映射目标文档中已经存在并明确标记的 Normal、Title、Heading 1/2/3 样式。
- 表格只应用首行/表体的字体、字号和对齐；不迁移复杂条件表格样式。
- 页面、页眉、页脚和编号仅分析，不在本版迁移。
- 不修改文本、段落数量、章节顺序、图片布局、TOC 或复杂编号。
