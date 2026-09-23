# GRID_RESEARCH_IMPLEMENTATION_PLAN_V1 — 验证清单

## 验证范围

基于真实科研实施方案文档（课题4实施方案 V1.1.4）建立的第一个业务模板资产，
按 TASK_DOC_011 任务书要求验证四项能力。

## 验证结果

| 验证项 | 方法 | 结果 |
| --- | --- | --- |
| 标题结构 | `load_template` 校验 heading1/2/3 字体字号 | PASS |
| 文档生成 | `generate_document` 从 demo.md 产出 demo.docx | PASS |
| 格式规则继承 | `run_template` 将模板 rules 驱动到 operations 层 | PASS |
| 输出文件存在 | 生成与执行产物落盘且可 `read_docx` 重新读取 | PASS |

## 1. 标题结构

- `rules.headings.h1`：黑体 / Times New Roman / 16pt(三号) / bold / 000000
- `rules.headings.h2`：黑体 / Times New Roman / 14pt(四号) / bold / 000000
- `rules.headings.h3`：黑体 / Times New Roman / 12pt(小四) / bold / 000000
- demo.docx 段落样式分布：Heading1=1、Heading2=4、Heading3=6、Body=16

## 2. 文档生成

- 输入：`examples/demo.md`（含 H1/H2/H3 与 Markdown 表格）
- 输出：`examples/demo.docx`（2261 字节，27 段，1 节）
- 模板执行：7 次属性修改（H1/H2/H3 字体+粗体、页面方向），0 错误
- lint 状态：FAIL（v1 已知边界，draft 缺 TOC/编号；before==after=12 ERROR，模板不引入新错误）

## 3. 格式规则继承

- 输入：坏样式 docx（宋体正文、宋体标题、错页边距）
- `run_template` 应用模板后：operations_count > 0，changed_parts 含
  word/styles.xml 与 word/document.xml
- 改写位置：`Style 正文`、`Style heading 1` 等
- 输出文件可重新读取，`source_unchanged=True`

## 4. 输出文件存在

- `examples/demo.docx` 存在，`read_docx` 成功
- `validation/demo_GENERATION_REPORT.md` + `.json` 旁车存在
- run_template 产出 `output/inherit.docx` 与 `reports/inherit.md` + `.json`

## 自动化测试

`tests/test_template_asset_grid_research.py`（4 项）：

1. `test_template_definition_structure` — 模板定义字段
2. `test_template_registered_in_default_registry` — 注册与无回归
3. `test_generation_produces_structurally_correct_docx` — 生成结构正确
4. `test_format_rule_inheritance_via_run_template` — 格式规则继承

全量测试：168 passed（164 基线 + 4 新增），无回归。
