# TASK_DOC_012 — Document Format Conversion & Validation Pipeline

## 1. 任务概述

在 TASK_DOC_011 真实模板资产 `GRID_RESEARCH_IMPLEMENTATION_PLAN_V1` 之上，
实现 **Word → Word 格式转换流水线**：输入任意既有 DOCX，选择模板，
输出格式规范的保护副本与逐条可追踪的审核报告。

核心原则（任务书硬性要求）：

1. **不重新生成内容**：没有 AI 理解、没有 ContentProvider、没有文本重写，
   只做"结构读取 → 格式调整 → 输出"；
2. **所有修改可追踪**：每条修改记录 位置 / before / after / rule；
3. **输入保护**：输出只能写 `output/`、报告只能写 `reports/`，
   输入文件 sha256 在转换前后双重校验。

设计文档：`docs/design/DOCUMENT_FORMAT_CONVERSION_DESIGN.md`。

## 2. 交付物

### 2.1 新增模块

| 文件 | 职责 |
| --- | --- |
| `src/document_factory/analyzer/__init__.py` | analyzer 公共 API |
| `src/document_factory/analyzer/profile.py` | `DocumentProfile` + `analyze_document`（转换前只读画像） |
| `src/document_factory/conversion/__init__.py` | conversion 公共 API 导出 |
| `src/document_factory/conversion/inputs.py` | `DocumentInputProvider.load_docx` |
| `src/document_factory/conversion/classifier.py` | 确定性段落角色分类（标题/表格/封面/正文/空段） |
| `src/document_factory/conversion/structure.py` | 样式脚手架 + `w:pStyle` 重指派 |
| `src/document_factory/conversion/models.py` | `ConversionResult` |
| `src/document_factory/conversion/report.py` | Markdown + JSON 审核报告 |
| `src/document_factory/conversion/converter.py` | `DocumentFormatConverter.convert` / `convert_document` |
| `tests/conversion/test_conversion.py` | 12 项流水线测试 |

### 2.2 修改文件

- `src/document_factory/__init__.py`：导出 analyzer / conversion 公共 API；
- `src/document_factory/cli.py`：新增 `convert` 子命令
  （`--input/--template-id/--output/--report/--rules`）。

### 2.3 流水线 8 步

1. 输出/报告路径校验（`checked_output`，禁止覆盖输入）；
2. `load_docx` 只读加载 + lint before + analyzer 画像 + 缓存原文；
3. 样式脚手架：缺什么样式补什么样式（同名样式复用不覆盖）；
4. 确定性角色分类 + `w:pStyle` 重指派（cover/blank 跳过）；
5. `TemplateRunner`：样式定义事实 + sectPr 页面规范；
6. normalizer：run 级字体/字号/颜色、表格段落直接格式
   （**先重指派、后规范化**，新指派段按目标角色被修复）；
7. 内存内容守卫 → sha256 守卫 → `write_package` → 复读 `read_docx` 校验；
8. lint after + 转换后画像 + 未解决问题归集 + 写审核报告。

## 3. 真实文档验证（广东负荷预测系统达标评估测评报告）

- 输入：`广东负荷预测系统现货边界系统达标评估测评报告_v1.1_校正版.docx`
  （210,849 字节，523 段、3 表、1 节，扁平文档：520 段直接挂 styleId=1
  的 Normal，无内置 Heading 样式，标题为手工编号普通段，格式全部直接堆在
  run 上，页边距为 Word 默认 2.54/3.17cm）
- 模板：`GRID_RESEARCH_IMPLEMENTATION_PLAN_V1`
- 结果：

| 指标 | 转换前 | 转换后 |
| --- | --- | --- |
| ERROR | 485 | **11** |
| WARNING | 11 | 2 |
| INFO | 959 | 3172 |
| 正文一致性 | — | **PASS（全文逐字一致）** |
| 输入文件变化 | — | **无（sha256 双校验）** |

执行统计：段落样式重指派 **495** 处（标题 5 + 正文 13 + 表格 477），
补建样式 **6** 个（正文 / heading 1-3 / 表格表头 / 表格正文），
属性修改记录 **1703** 条，分类：

| 修改维度 | 数量 |
| --- | ---: |
| 字体/字号/颜色 | 1108 |
| 表格样式指派 | 477 |
| 段落格式（缩进/行距） | 88 |
| 正文样式指派 | 13 |
| 样式补建 | 6 |
| 样式定义修正 | 4 |
| 标题样式指派 | 5 |
| 页面/页边距 | 2 |

关键格式修正实例（报告中逐条可追踪）：

- `Paragraph 23 / 一、系统简介`：style `Normal → heading 1`
  （CONVERT_HEADING1），run eastAsia `仿宋 → 黑体`（FONT001）、
  字号 16pt 保持三号、颜色 000000、outlineLvl=0；
- `Paragraph 24 / 广东负荷预测系统…`：style `Normal → 正文`
  （CONVERT_BODY），字号 `16pt → 12pt`（FONT003），
  首行缩进 `firstLine=640 → firstLineChars=200`（BODY002），
  行距补齐 1.5 倍（BODY003）；
- 477 个表格单元格段落：`Normal → 表格表头/表格正文`，
  字体黑体/仿宋、五号 10.5pt（TABLE003 全部消除）；
- 页边距：Word 默认 → 上 2.8 / 下 2.6 / 左 2.8 / 右 2.6 cm（PAGE003 消除）。

转换后剩余 11 个 ERROR 全部是 v1 **明确不自动处理**的确定性边界项：

- NUM001 × 5：5 个手工编号标题（"一、…"～"五、…"）识别为 Heading 1
  但不转自动编号；
- NUM002 × 5：标题无 numPr 绑定；
- TOC001 × 1：文档无目录域，不自动创建 TOC。

WARNING 2 项：FRONT003（首个标题前无显式分页依据，需渲染确认）、
TOC005（updateFields 设置）。另有 8 个封面/前置非空段保留原格式并在
报告中列出样本（报告 UNRESOLVED=7 类）。

## 4. 可追踪性设计

- 每条 change：`object_type / location / property / before / after /
  rule / source`；
- 位置精确到 `word/document.xml / Paragraph N / 文本前 70 字 / Run M`，
  表格段落为 `Table t, Row r, Cell c`；
- before/after 为操作瞬间的真实属性快照（如
  `{'eastAsia': '宋体'} → {'eastAsia': '仿宋'}`），rule 为 lint 规则号
  或 CONVERT_* 转换规则号；
- 报告含 Markdown 明细表 + 同名 JSON（完整 ConversionResult），
  机器可复核、可对账。

## 5. 测试

`tests/conversion/test_conversion.py` 新增 **12 项**，覆盖任务书 4 项
验收测试：

1. **普通 DOCX 输出成功**：扁平文档（仅 Normal、宋体五号直接格式、
   错误页边距、手工标题、表格）转换成功，输出可读、正文逐字一致、
   6 样式补建、9 段重指派、ERROR 显著下降、页边距 2.8/2.6；
2. **字体转换 宋体 → 仿宋**：正文 run eastAsia 宋体 → 仿宋、
   10.5pt → 12pt，FONT001 记录位置/before/after 齐全；
3. **普通文本标题 → Heading Style**：`一、`/`（一）`/`1.1.1` →
   heading 1/2/3（黑体、规定字号、加粗、outlineLvl），
   表格段落 → 表格表头/表格正文；
4. **审核报告生成**：Markdown 七节齐全 + JSON 旁车，每条 change 含
   location/before/after/rule，未解决问题含 NUM001/TOC001；
   另含输入边界、Analyzer 画像、CLI convert（退出码语义）测试。

全量：**180 passed**（TASK_DOC_011 基线 168 + 新增 12），原 168 项
无回归。

## 6. 已知限制

1. **手工编号不转自动编号（NUM001/NUM002）**：赋予 Heading 样式但不创建
   numId/numPr，属文档结构重排，与既有 normalizer UNSUPPORTED 声明一致；
2. **不创建/刷新目录域（TOC001/TOC005）**；
3. **封面/前置区域保留原格式**：仅做"首个标题之前"的边界识别并列样本，
   不自动套用封面样式；
4. **纯中文 run 的西文字体槽保守处理**：ascii/hAnsi 只在 run 含拉丁字符时
   修复（中文实际渲染走 eastAsia 槽，该槽始终正确修复）；
5. **无图片/图表标题（caption）识别规则**：图片标题格式不自动判断；
6. **文本框、浮动对象、修订、页眉页脚部件**沿用既有引擎边界；
7. CLI 退出码：转换执行成功但输出仍有 ERROR（如 NUM/TOC）时返回 1，
   语义与 lint/normalize 一致——"执行成功不等于全部规则合格"。

## 7. Remaining Risks

- 确定性标题识别面向常见公文/报告编号模式（中文干支编号、`1.1.1`、
  全 run 加粗紧贴编号），非常规编号（字母编号、"第 N 章"、自动编号与
  手工编号混用）可能漏判，漏判段落按正文处理，不会产生错误标题；
- 封面区域按"首个标题之前"界定，若文档前置部分出现符合编号模式的非标题
  短句（<50 字、无句末标点），可能被提前截断封面边界；报告给出封面样本
  供人工核销；
- 转换依赖模板与 rules 参数同构（011 模板与规则文件同源维护），后续模板
  需沿用 `metadata.rule_file` 约定。

## 8. Commit 与哈希回填

- 实现 commit：`934ec2f`
  （TASK_DOC_012: Implement document format conversion pipeline）
- 回填 commit：`docs: backfill TASK_DOC_012 commit hash`
- 推送：`git push origin master`

## 9. 完成后的能力

```
任何 Word
   ↓ DocumentInputProvider（只读）
DocumentFactory  ← 选择规范模板（GRID_RESEARCH_IMPLEMENTATION_PLAN_V1）
   ↓ 样式脚手架 + 确定性重指派 + 模板执行 + 规范化
格式统一
   ↓ lint 复检
自动检查
   ↓ 逐条可追踪审核报告
最终交付（保护副本，正文逐字不动）
```

## 10. Next Suggestion

- 将"手工编号 → 自动多级编号 / TOC 域生成"作为需用户显式确认的**结构
  任务**独立实现（不混入格式转换），可消除剩余 NUM001/NUM002/TOC001；
- 基于模板 `cover_style_pattern` 做受控封面样式识别与套用；
- 增加 caption 角色规则（图表标题编号模式）覆盖图片标题格式。
