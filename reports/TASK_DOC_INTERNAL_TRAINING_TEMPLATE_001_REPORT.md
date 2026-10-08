# TASK_DOC_INTERNAL_TRAINING_TEMPLATE_001 报告（MVP）

- 日期：2026-10-08
- 范围：应用户要求由完整任务收缩为 MVP。仅交付：
  1. 第二套独立模板 `INTERNAL_TRAINING_DOCUMENT_V1` 的事实提取与注册；
  2. 表格灰色表头（源稳定值 #D7D7D7）确定性规范化；
  3. 在 **1 份**用户显式指定的真实同类文档上的实际应用验证。
- 明确不做：`document_title` 通用能力、批处理、MCP 扩展、额外大规模测试、
  内容改写、LLM 分类、编号重建、图片 OCR、全盘扫描。
- 真实源文件仅存在于本地 `local_samples/`（已被 `.gitignore` 排除），
  本报告与提交中不含任何真实业务文本/截图。

## 1. 源文档 DF profile 摘要（脱敏，仅结构计数）

| 项 | 值 |
|---|---|
| 节（section）数 | 3：portrait A4 → landscape A4 → portrait A4，分节均为 nextPage |
| 页面尺寸（twips） | 11906×16838 / 16838×11906 / 11906×16838 |
| `w:orient` 显式属性 | §1 无、§2 landscape、§3 无（Word 依宽高推断；规范化保持该写法） |
| 页边距（主流） | 纵向 上下 1440 / 左右 1800 twips；横向 上下 1800 / 左右 1440 twips |
| 段落总数 / 非空 | 465 / 404（其中表格单元格段落 341） |
| 表格数 / 形状 | 7；14×5、5×5、2×5、7×5、2×5、2×5、12×7，均为 Table Grid |
| 图片 | 34 个 media 部件；正文嵌入 31 处（DrawingML + VML） |
| 编号 | numId=1 的多级自动编号挂在内置 Heading 1/2 上（保留，不重建） |

## 2. 实际可见格式统计（不只依赖 styles.xml）

统计由新增只读模块 `analyzer/visible_format.py` 基于"直接格式 + 样式链
有效解析"聚合，单位均为 run/段落计数：

- 正文（非表格主流段落）：宋体 12pt（12pt=189 run，10.5pt=7）；1.5 倍行距
  （360/auto=68 段）；首行缩进 firstLineChars=200（61 段）；两端对齐主流
  （both=64，center=6）。
- Heading 1：华文中宋 16pt 加粗黑色（9 run / 5 段）。
- Heading 2：华文中宋 15pt 加粗黑色（16 run / 14 段）。
- 首页【第X周】总标题：1 段，华文中宋 24pt 加粗黑色、无 numPr；源文档套用
  在内置 "heading 1" 样式上。**MVP 暂不区分**（见已知限制）。
- 表头（7 表首行，37 个表头单元格段落，100% 一致）：
  宋体 / 10.5pt / 加粗 / 水平居中；单元格底纹 **fill=D7D7D7**（无例外）。
- 表体：宋体 / 10.5pt / 非加粗 409 run；水平对齐 both=224、center=53
  （两种对齐均为真实分布，必须逐格保留）；表体无底纹（none=259、auto=18）。
- 颜色：9 个正文 run 为蓝色 0000FF（非超链接），规范化不动颜色。

## 3. 最终模板规则（MVP）

模板目录：`templates/internal_training_document_v1/`
规则文件：`rules/internal_training_document_v1.yaml`（lint 机器规则）

- 无 `extends`，`independent: true`；规则分片：page / paragraph / heading / table。
- 页面：`orientation_policy: preserve`，不新增/改写 `w:orient`；按节方向
  选取纵向/横向边距变体；期望节序 portrait→landscape→portrait。
- 正文：样式名 `Normal`，宋体 12pt、首行缩进 2 字符、1.5 倍行距、两端对齐、
  段前段后 0。
- 标题：内置 heading 1/2/3（华文中宋 16/15/14pt，加粗黑色，左对齐）；
  numbering 原样保留，所有编号重建开关关闭。
- 表头：宋体 10.5pt、加粗、水平居中、黑色文字；底纹 `header_shading_fill:
  D7D7D7`（源稳定主流值），`header_shading_fill_fallback: D9D9D9`（无稳定
  值时的任务书默认值）；表头行距 1.5 倍。
- 表体：宋体 10.5pt；`preserve_body_alignment: true`——表体样式不写 `w:jc`，
  规范化逐格保留原有水平对齐；表体单倍行距。
- 新增确定性原语：`operations/table.py::apply_cell_shading`（显式 fill，
  移除 themeFill*）；表头单元格直写 `apply_table_header_cells`。
- TOC 不要求；PAGE002/NUM/TOC/FRONT 类为 INFO，不阻断。

## 4. 与 DEFAULT_TECHNICAL_DOCUMENT_V1 的差异

| 维度 | DEFAULT_TECHNICAL_DOCUMENT_V1 | INTERNAL_TRAINING_DOCUMENT_V1 |
|---|---|---|
| 继承关系 | 默认基线 | 完全独立，无 extends |
| 正文字体/字号 | 模板既有事实（仿宋等） | 宋体 12pt（小四） |
| 正文行距/缩进 | 模板既有事实 | 1.5 倍 / 首行缩进 2 字符 / 两端对齐 |
| 标题字体 | 模板既有事实 | 华文中宋 16/15/14pt |
| 多 section | 单一页面规范 | portrait→landscape→portrait，orient 保留策略 + 分方向边距变体 |
| 表头底纹 | 无 | D7D7D7（fallback D9D9D9），黑字加粗居中 |
| 表体对齐 | 统一规范 | 逐格保留（both 224 / center 53 的真实分布） |
| 编号 | 默认规则 | 不重建、不迁移，原样保留 |

DEFAULT 模板及其余 2 套既有模板的语义与全部既有测试保持不变。

## 5. 新增/修改文件

新增：

- `templates/internal_training_document_v1/template.yaml`
- `templates/internal_training_document_v1/rules/{page,paragraph,heading,table}_rules.yaml`
- `templates/internal_training_document_v1/definition/template_structure_analysis.md`
- `templates/internal_training_document_v1/validation/VALIDATION_CHECKLIST.md`
- `rules/internal_training_document_v1.yaml`
- `src/document_factory/analyzer/visible_format.py`（实际可见格式统计，只读）
- `src/document_factory/integrity.py`（Content Integrity Gate；与远端
  FULL_NORMALIZATION 任务的生产级实现合并统一，conversion/normalize 均接入）

修改：`.gitignore`（排除 `local_samples/`）、`templates/schema.py`
（TableRule 新增表头底纹/颜色/对齐保留字段）、`conversion/{classifier,
structure,converter,models}.py`、`normalizer.py`、`operations/{table,_oxml,
__init__}.py`、`section_analyzer.py`、`table_analyzer.py`、
`template_runner/{mapper,models,runner}.py`、`analyzer/__init__.py`、
`models.py`。

## 6. 测试结果

- 命令：`.\.venv\Scripts\python.exe -X utf8 -m pytest -q`
- 结果：**231 passed**（合并远端并行任务后全量运行；未新增大规模测试，符合 MVP 约束）。
- 模板注册校验：Registry 列出 4 套模板，新模板 `extends=None`。
- 推送前整合：远端在本任务开发期间合入了 FULL_NORMALIZATION / STYLE_BINDING /
  MCP_DEFAULT_PRESET 等并行任务。已按 GIT_WORKFLOW §4 执行普通 `git merge`
  （merge 提交 `7208ba2`），Content Integrity Gate 改采用远端生产级实现
  `verify_content_integrity`（能力为其超集：可见文本/Run 文本/表格结构与单元格
  文本/域指令/超链接/页眉页脚/关系/media SHA-256/绘图计数），并将多节边距
  variants 支持以**向后兼容**方式补入其 `_normalize_sections`（仅
  `orientation_policy: preserve` 时生效，既有规则集行为不变）。

## 7. 实际应用验证（1 份真实文档，MVP Pilot）

- 输入：用户显式指定的 1 份真实 DOCX（仅存于 `local_samples/`，未入 Git）。
- 输出（新文件，未覆盖输入）：
  `output/internal_training/mvp/第一周_管理规范_INTERNAL_TRAINING_V1.docx`
  （`output/` 被 gitignore）。
- lint（internal_training 规则）：**ERROR 712 / WARNING 37 → ERROR 0 /
  WARNING 0**（INFO 为事实性提示，不阻断）。
- 样式：新建 `heading 3`、`表格表头`、`表格正文`；341 个表格段落重指派。
- 输出可见格式复核：
  - 三节方向与 orient 属性逐节一致（None / landscape / None），表格形状 7/7 一致；
  - 表头 37/37：D7D7D7 底纹、宋体 10.5pt、加粗、水平居中、黑色 000000；
  - 表体对齐分布 before/after 完全一致：both=224、center=53；
  - 表体 409 run：宋体 10.5pt 非加粗；
  - 正文段落：宋体 12pt、360/auto、firstLineChars=200；
  - 蓝色 0000FF run 5/5 保留（颜色不被规范化）。
- 未执行全页 render（本环境渲染后端未纳入 MVP 验证范围；TABLE009 跨页
  重复表头保留为 INFO 人工项）。

## 8. Content Integrity Gate 结果

转换流水线写包后执行生产级 `verify_content_integrity(source, output,
changed_parts)`，本份文档结论 **PASS**：

- 可见文本一致：是；Run 文本一致：是；
- 表格结构一致、表格单元格文本一致：是；
- 域指令一致、超链接显示文本一致、页眉页脚文本一致：是；
- 关系部件一致：是；
- media 部件 34 个，逐个 SHA-256 一致：是；
- 段落/表格/节/绘图计数前后一致；
- 输入文件 SHA-256 全程未变，输出为独立新文件。

## 9. 已知限制（MVP 暂缓项）

1. 首页【第X周】总标题未与普通 Heading 1 区分：MVP 中按 Heading 1 规范化，
   其直接字号由 24pt 归一为 16pt（字体仍为华文中宋、加粗、黑色、文本不变）。
2. 仅验证 1 份真实文档；用户曾计划的第 2 份 Pilot、before/after + 全页
   render 流程未执行（本环境渲染后端状态未确认）。
3. 批处理能力、document_title 通用能力、MCP preset 扩展未开发。
4. 跨页重复表头（TABLE009）需 render 后人工确认。

## 10. 提交信息

- 代码提交 SHA：`80ba4c63d55a1430ea3891c8a2390075a0532f63`
  （28 files changed，1181 insertions，41 deletions）。
- 远端整合 merge 提交：`7208ba2`（普通 merge，保留双方完整历史）。
- 本报告 SHA 回填由独立 docs 提交完成。
- 真实文档与输出产物均未进入 Git；`git status` 已人工核验
  （`local_samples/`、`output/` 命中 .gitignore）。
