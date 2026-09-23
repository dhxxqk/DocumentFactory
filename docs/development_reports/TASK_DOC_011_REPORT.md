# TASK_DOC_011 — Real Template Asset & Validation Pipeline

## 1. 任务概述

基于真实科研实施方案 Word 文档（`课题4实施方案_V1.1.4.docx`，39 页），
建立 DocumentFactory 第一个业务模板资产，并完成验证流水线。

## 2. 模板来源

- 源文档：`templates/grid_research_implementation_plan_v1/source/课题4实施方案_V1.1.4.docx`
  （2,295,387 字节，真实科研课题实施方案）
- 提取方式：`document_factory.docx_reader.read_docx` 解析 OOXML，手工核对
  styles / paragraphs / tables / sections / 页眉页脚 / fields
- 提取脚本一次性运行后删除，不入库
- 0 条 `docx_reader` 诊断（无 altChunk / 文本框 / 修订）

## 3. 提取规则

源文档格式事实与电网科技项目实施方案文档格式规范 V1.4 完全一致：

### 3.1 页面设置
- A4 纵向（11906 × 16838 twips = 21.0 × 29.7 cm）
- 页边距：上 2.8 / 下 2.6 / 左 2.8 / 右 2.6 cm
- 页眉/页脚距边界 1.4 cm

### 3.2 字体规则
- 正文（styleId=Style5，名称"正文"）：仿宋 + Times New Roman，12pt(小四)，
  color 000000，两端对齐，1.5 倍行距，首行缩进 2 字符
- Normal 默认：仿宋 + Times New Roman，12pt

### 3.3 标题层级
| 级别 | 中文字体 | 西文字体 | 字号 | color | bold |
| --- | --- | --- | --- | --- | --- |
| H1 | 黑体 | Times New Roman | 16pt(三号) | 000000 | True |
| H2 | 黑体 | Times New Roman | 14pt(四号) | 000000 | True |
| H3 | 黑体 | Times New Roman | 12pt(小四) | 000000 | True |

### 3.4 表格规则
- 表格表头（Style6）：黑体 + Times New Roman，10.5pt(五号)，bold，居中
- 表格正文（Style7）：仿宋 + Times New Roman，10.5pt，居左
- 表格正文-居中：仿宋 + Times New Roman，10.5pt，居中
- 首行 tblHeader 重复表头

### 3.5 图片标题规则
- caption 样式：黑体 + Times New Roman，10.5pt，居中，before=120/after=120
- 实文档 15 个题注段落使用该样式

### 3.6 页眉页脚规则
- header2：`课题4：支撑电网中长期规划的负荷预测模块研发与应用`
- footer2：PAGE 域（页码居中）
- 其余 header/footer 为空段占位

### 3.7 域
- TOC 域：`TOC \z \o "1-2" \u \h`（1-2 级目录）
- PAGE 域：页脚页码

## 4. Template Definition

- 资产目录：`templates/grid_research_implementation_plan_v1/`
  - `template.yaml`（TemplateDefinition，符合 schema）
  - `source/课题4实施方案_V1.1.4.docx`（源文档副本）
  - `definition/template_structure_analysis.md`（结构分析）
  - `examples/demo.md` + `demo.docx`（最小 Demo）
  - `validation/`（生成报告 + 验证清单）
- 规则文件：`rules/grid_research_implementation_plan_v1.yaml`（参数与
  template.yaml 一致，lint 引擎可直接消费）
- template_id：`GRID_RESEARCH_IMPLEMENTATION_PLAN_V1`
- category：`[report, research]`
- `default_registry` 自动扫描 `templates/*/template.yaml` 注册，无需改代码

## 5. Demo 结果

- 输入：`examples/demo.md`（H1/H2/H3 + 正文 + Markdown 表格）
- 输出：`examples/demo.docx`（2261 字节，27 段，1 节）
- 模板执行：7 次属性修改（H1/H2/H3 补齐 Times New Roman + bold、
  页面补齐 orient=portrait），0 错误，1 警告（表格样式未找到，见已知限制）
- 段落样式分布：Heading1=1、Heading2=4、Heading3=6、Body=16 —— 标题层级结构正确
- 结论：**能够基于该模板生成一个结构正确的 Word 文档**（验收标准 PASS）

## 6. 验证测试

`tests/test_template_asset_grid_research.py`（4 项，全部 PASS）：

1. 标题结构：`test_template_definition_structure`
2. 文档生成 + 输出存在：`test_generation_produces_structurally_correct_docx`
3. 格式规则继承：`test_format_rule_inheritance_via_run_template`
4. 注册无回归：`test_template_registered_in_default_registry`

全量：**168 passed**（164 基线 + 4 新增），原 164 项无回归。

## 7. 已知限制

1. **Demo lint 状态为 FAIL（v1 已知边界）**：MarkdownContentProvider v1
   只产出标题+正文段落，不生成 TOC 域与多级编号绑定，导致 lint 报 TOC/NUM
   类 ERROR。模板执行 before==after（12 ERROR），不引入新错误。这是
   TASK_DOC_010 已记录的 generation v1 边界，非模板缺陷。
2. **v1 Markdown provider 不支持表格**：demo.md 中的 Markdown 表格会 fall
   through 为正文段落（providers.py 注释明确“tables intentionally out of
   scope for v1”）。表格规则通过 `run_template` + make_docx 表格样式夹具
   验证，不依赖 demo 表格。
3. **首行缩进取规范值 2 字符**：源文档正文样式 firstLine=420 twips（约 1.75
   字符），与规范 2 字符略有偏差。模板按规范 V1.4 取
   `first_line_indent_chars: 2`（规定性而非描述性）。
4. **页眉页脚不在 TemplateRunner v1 作用域**：runner v1 作用域为 style 元素
   + sectPr，headerN.xml/footerN.xml 的格式治理留待后续任务。
5. **未完整复制 39 页内容 / 未自动识别所有复杂格式 / 无 AI 生成内容**
   （任务书明确不要求）。

## 8. 与现有体系的关系

- `GRID_RESEARCH_IMPLEMENTATION_PLAN_V1` 与 `GRID_TECH_V1_4` 规则参数同构
  （源文档即 V1.4 规范的一个真实实例），差异在 `metadata.source` 指向真实
  业务文档、`template_id` 为业务语义标识、`category` 增加 `research`。
- `TemplateDefinition` 是规定性的，与 `rules/*.yaml`（lint 事实源）和
  `template/profile.py`（描述性分析）互补不替代。
- 新模板复用既有 `run_template` / `generate_document` 流水线，无需任何运行时
  代码改动，仅新增数据资产 + 测试。

## 9. Commit 与哈希回填

- 实现 commit：`d21e998`（TASK_DOC_011: Add real template asset and validation pipeline）
- 回填 commit：本次 `docs: backfill TASK_DOC_011 commit hash`
- 推送：`git push origin master`

## 10. Remaining Risks

- demo.docx 体积小（2261 B）且无表格——若需演示完整业务文档形态，需等
  Markdown provider 支持表格或改用真实 docx 作为 run_template 输入。
- 源 docx（2.3 MB）入库作为模板资产 source；后续若仓库体积敏感，可考虑
  Git LFS 或仅保留结构分析。

## 11. Next Suggestion

- 进入下一任务：扩展 MarkdownContentProvider v2 支持表格 / 列表，或
  将 TemplateRunner 作用域扩展至页眉页脚，使 demo 能完整复现源文档形态。
