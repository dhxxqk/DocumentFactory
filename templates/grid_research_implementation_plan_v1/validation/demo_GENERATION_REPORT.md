# DocumentFactory Template Execution Report

## 1. 基本信息

- 实际生成时间（含时区）：2026-09-23T17:20:45+08:00
- DocumentFactory 版本：0.5.0a1
- 模板 ID：GRID_RESEARCH_IMPLEMENTATION_PLAN_V1
- 输入文件：C:\Users\清能互联-覃恳\AppData\Local\Temp\df_gen_80mlf57f\demo_draft.docx
- 输出文件：C:\Users\清能互联-覃恳\AppData\Local\Temp\df_demo_k6k0grur\output\demo.docx
- 输入 SHA-256：93820159a2230316397ca25fe701c7323f984a566624bc432d13e49f7b7ef5a9
- 输出 SHA-256：d00e3ad5b4fba9720dc2cfae8cbb4307691037c10cd6adf11621f18d8f4346cd
- 报告：C:\Users\清能互联-覃恳\AppData\Local\Temp\df_demo_k6k0grur\reports\demo_GENERATION_REPORT.md
- 输入文件未变化：True

## 2. 执行结论

**RESULT: FAIL**

最终结论来自输出 DOCX 的真实 lint；模板应用成功不等于全部格式合格。

| 阶段 | ERROR | WARNING | INFO |
|---|---:|---:|---:|
| 执行前 | 12 | 0 | 186 |
| 执行后 | 12 | 0 | 186 |

## 3. 修改统计

- 属性修改记录：7
- 变更部件：word/document.xml, word/styles.xml
- 警告：1
- 错误：0

- Section：1
- Style：6

## 4. 修改明细

| 对象类型 | 位置 | 属性 | 修改前 | 修改后 |
|---|---|---|---|---|
| Style | Style heading 1 | h1_font | {"eastAsia": "黑体"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Style | Style heading 1 | h1_bold | null | true |
| Style | Style heading 2 | h2_font | {"eastAsia": "黑体"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Style | Style heading 2 | h2_bold | null | true |
| Style | Style heading 3 | h3_font | {"eastAsia": "黑体"} | {"ascii": "Times New Roman", "eastAsia": "黑体", "hAnsi": "Times New Roman"} |
| Style | Style heading 3 | h3_bold | null | true |
| Section | Section properties | page_page_size | {"h": "16838", "w": "11906"} | {"h": "16838", "orient": "portrait", "w": "11906"} |

## 5. 警告

- 未找到表格样式（表格表头, 表格正文），跳过表格规则

## 7. 机器可读结果

同名 JSON：`C:\Users\清能互联-覃恳\AppData\Local\Temp\df_demo_k6k0grur\reports\demo_GENERATION_REPORT.json`
