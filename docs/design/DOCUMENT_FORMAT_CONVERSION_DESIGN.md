# Document Format Conversion Pipeline 设计文档（TASK_DOC_013）

> 编号说明：本任务开发时编号为 TASK_DOC_012，2026-09-23 路线调整后
> 顺延为 TASK_DOC_013（TASK_DOC_012 改由"默认技术文档规范"占用）。

## 1. 背景与目标

TASK_DOC_010 建立了"内容 → 新 Word"的生成流水线（generation），
TASK_DOC_011 建立了真实模板资产 `GRID_RESEARCH_IMPLEMENTATION_PLAN_V1`。
但实际工作中最常见的诉求不是生成，而是：

> 我已经有一份 Word，只需要套用规范。

本设计新增 **Word → Word 格式转换流水线**：

```
input.docx ──▶ DocumentFactory ──▶ output.docx + conversion_report.md
                  （选择模板）
```

验收硬约束：

1. 任意 DOCX 可以输入；
2. 可以选择已注册模板（011 模板为首个验证对象）；
3. 输出格式规范的 DOCX 保护副本；
4. **不修改、不重写任何正文内容**；
5. 输出审核报告，且**每一条修改都可追踪**（位置 + before + after + rule）。

## 2. 为什么不是"生成"

| 维度 | generation（TASK_DOC_010） | conversion（本任务） |
| --- | --- | --- |
| 输入 | Markdown / 文本（内容源） | 既有 DOCX（成品来稿） |
| 动作 | 解析内容并**构建**段落/表格 | **读取**既有结构并调整格式 |
| 正文文本 | 从内容源产生 | 逐字保留，转换前后全文比对 |
| 样式来源 | 模板构建时赋予 | 样式脚手架 + 段落样式重指派 |
| 失败模式 | 内容理解错误 | 格式识别/套用错误 |

明确禁止的链路：

```
DOCX ──▶ AI 理解 ──▶ 重新写Word      （禁止）
```

本流水线的实际链路：

```
DOCX ──▶ 结构读取（docx_reader，只读）
      ──▶ 格式调整（样式 / pStyle / run rPr / sectPr）
      ──▶ 输出 DOCX（保护副本，输入文件 sha256 双重守卫）
```

整条链路没有任何内容提供方（ContentProvider）参与，也不存在文本生成步骤。
正文一致性由两道守卫保证：

- **内存守卫**：转换前缓存全部正文文本，格式操作完成后比对，不一致即中止；
- **落盘守卫**：写出保护副本后重新 `read_docx`，再次全文比对。

## 3. 转换流程

```
用户
 │
 ▼
输入 DOCX
 │
 ▼
DocumentInputProvider（load_docx，路径/扩展名校验 + 只读解析）
 │
 ▼
Document Analyzer ──▶ DocumentProfile（转换前画像）
 │
 ▼
Template Selection（load_template(template_id) + rules yaml）
 │
 ▼
Formatting Converter
   ├─ 1. lint before（真实基线）
   ├─ 2. 样式脚手架 ensure_template_styles（缺什么样式补什么样式）
   ├─ 3. 确定性角色分类 classify_paragraphs
   ├─ 4. 段落样式重指派 reassign_paragraph_styles（仅 w:pStyle）
   ├─ 5. TemplateRunner（样式定义事实 + sectPr 页面规范）
   ├─ 6. normalizer（Run 级字体/字号/颜色、表格段落直接格式）
   ├─ 7. 内存内容守卫 + sha256 守卫 + write_package + 复读校验
   └─ 8. lint after（真实复检）+ 转换后画像
 │
 ▼
Review Report（Markdown + 同名 JSON 旁车）
 │
 ▼
final.docx（output/ 保护副本）
```

流水线代码入口：

- API：`document_factory.conversion.convert_document(input, template_id, output, report, rules)`
- CLI：`document-factory convert --input <docx> --template-id <id> [--output --report --rules]`

规则文件默认从 `template.metadata["rule_file"]` 解析，无需手工指定。

## 4. 模块设计

### 4.1 DocumentInputProvider（`conversion/inputs.py`）

转换流水线的显式输入边界：

- `load_docx(path)`：校验文件存在、扩展名为 `.docx`，委托只读的 `docx_reader`；
- 返回的 `Document` 包含 paragraphs / styles / tables / sections / fields；
- 本身不做任何写操作。

### 4.2 Document Analyzer（`analyzer/profile.py`）

回答"转换前这份文档是什么状态"，输出 `DocumentProfile`：

| 字段 | 含义 |
| --- | --- |
| `source_path` / `source_sha256` | 输入路径与内容指纹 |
| `paragraph_count` / `nonempty_paragraph_count` | 段落总数 / 非空数（含表格单元格段） |
| `table_count` | 表格数 |
| `heading_structure` | 内置 Heading 样式使用数 `{h1,h2,h3}` |
| `style_usage` | 段落样式名 → 使用段落数 |
| `font_usage` | "有效字体/字号" → 非空文本 run 数 |
| `section_info` | 每节纸张尺寸与页边距（twips → cm） |

设计要点：

- **只读、描述性、与规则无关**：analyzer 不知道任何模板，也不判断"应该改成什么"；
  规定性决策全部属于 conversion 层；
- **有效值而非原始 XML**：字体/字号通过 `StyleResolver` 解析样式继承与主题字体，
  统计口径与 lint 引擎一致，避免被"run 没写字体但样式里有"的情况误导；
- 含中文的 run 计 eastAsia 槽，纯拉丁 run 计 ascii 槽。

### 4.3 确定性角色分类（`conversion/classifier.py`）

转换不做 AI 语义理解，段落角色只能由**可复现的确定性规则**判定：

| 角色 | 判定规则 | 目标样式 |
| --- | --- | --- |
| heading1 | `一、` `二、`… 中文编号开头 | heading 1 |
| heading2 | `（一）` `(二)`… 开头 | heading 2 |
| heading2/3 | `1.1` / `1.1.1` 数字点分编号（点数+1，上限 3） | heading 2 / 3 |
| heading1 | `1` `1、` `1．` `1)` 单级数字编号 | heading 1 |
| heading1-3 | 紧贴汉字的数字编号（如 `1研究目标`），**仅当整段 run 全加粗**才采信 | 对应级别 |
| table_header | 表格首行或 `tblHeader` 重复表头行 | 表格表头 |
| table_body | 其余表格单元格段落 | 表格正文 |
| cover | 第一个被识别标题之前的段落 | 不指派（保留原样） |
| body | 其余非空段落 | 正文 |
| blank | 空段 | 不指派 |

误判保护（全部确定性）：

- 标题文本长度 > 50 字、以句末标点（`。！？；：!?;:`）结尾 → 非标题；
- 目录点状导引线（`标题........12` / tab + 页码）→ 排除；
- 编号后紧跟年月日（日期）→ 排除；
- 封面区域只做"首个标题之前"的边界识别，**不改格式**，交人工复核，
  并进入报告"未解决问题"。

### 4.4 样式脚手架与样式重指派（`conversion/structure.py`）

任意来稿通常缺少模板所需样式（正文 / heading 1-3 / 表格表头 / 表格正文）。

1. `ensure_template_styles`：按 `TemplateDefinition.rules` 的事实生成缺失样式的
   OOXML（pPr + rPr 完整），追加进 `word/styles.xml`，并同步注册到解析模型
   `document.styles`，使 resolver/lint/runner 立即可见。样式名取规范名
   （"正文"/"heading N"/"表格表头"/"表格正文"），styleId 使用固定内部 id
   （`DFBody` / `DFHeading1..3` / `DFTableHeader` / `DFTableBody`），
   `basedOn` 挂文档默认样式。**同名样式已存在则复用，绝不覆盖**。
2. `reassign_paragraph_styles`：对分类结果设置 `w:pStyle`（pPr 缺失时按
   schema 顺序创建），同步解析模型的 `style_id/properties`。只改段落样式引用，
   run 与文本一律不触碰。cover/blank 跳过。

### 4.5 Formatting Converter（`conversion/converter.py`）

编排 8 步流程（见第 3 节），最大化复用既有能力：

- 模板事实执行复用 `template_runner.runner.TemplateRunner`
  （样式定义 + sectPr，作用域与 010/011 完全一致）；
- run 级直接格式修复复用 `normalizer._apply_normalization`
  （FONT001-004 / BODY002-003 / TABLE004/007 等同一套规则决策与操作层）。
  关键顺序：**先重指派样式，后跑 normalizer**，使新指派的段落能被
  normalizer 按目标角色处理；
- 写出复用 `operations.write_package`（变更部件序列化，未变更部件字节复制）；
- 输出路径复用 `output_paths.checked_output`：只能落 cwd 的 `output/`、
  `reports/` 下，且不能等于输入路径。

结果模型 `ConversionResult` 记录：状态、路径、双 sha256、转换前后画像、
转换前后 lint 计数、**全部 change 记录**、重指派数、补建样式列表、
未解决问题、内容一致性、输入未变化标志。

### 4.6 审核报告（`conversion/report.py`）

输出 `*_CONVERSION_REPORT.md` + 同名 `.json`，七个部分：

1. **文档信息**：输入/输出路径、模板 id、转换时间、双 sha256、输入未变化、
   正文一致性；
2. **转换前文档画像**：DocumentProfile（段落/表格/标题结构/样式使用/
   有效字体/页面信息）；
3. **修改统计**：change 总数、重指派数、补建样式，以及按维度归桶
   （样式补建 / 页面页边距 / 字体字号颜色 / 标题样式指派 /
   表格样式指派 / 正文样式指派 / 段落格式 / 样式定义修正）；
4. **修改明细（可追踪）**：逐条表格
   `位置 | 属性 | 修改前 | 修改后 | Rule`。位置精确到
   `word/document.xml / Paragraph N / 文本… / Run M`（表格段落到
   `Table t, Row r, Cell c`），满足"Paragraph 25 before 宋体 10.5
   after 仿宋 12 rule GRID_RESEARCH_IMPLEMENTATION_PLAN_V1.body"的追踪要求；
5. **未解决问题（需人工复核）**：封面区域样本、lint 后剩余的
   ERROR/WARNING/UNSUPPORTED（按 rule 聚合计数）、解析诊断；
6. **最终状态**：转换前后 ERROR/WARNING/INFO 对比 + `RESULT`。
   明确标注"转换执行成功 ≠ 全部规则合格"；
7. **机器可读结果**：JSON 旁车（含完整 ConversionResult 与分类统计）。

## 5. 确定性边界（明确不自动处理项）

以下事项在 v1 显式不自动处理，只在报告中列为未解决问题：

1. **手工编号转自动多级编号（NUM001/NUM002/NUM003）**：识别手工编号标题并
   赋予 Heading 样式，但不创建 numId / numPr 绑定——编号绑定属于文档结构
   重排，超出"只调格式"范围，且与既有 normalizer 的 UNSUPPORTED 声明一致；
2. **目录域创建/刷新（TOC001 等）**：不生成 TOC 域、不更新页码；
3. **封面/前置区域**：首个标题之前的段落保留原格式，仅在报告中给出样本；
4. **图片/图表标题格式**：v1 无 caption 角色识别规则，不推断图片标题；
5. **文本框、浮动对象、修订、页眉页脚部件**：沿用既有引擎边界；
6. **纯中文 run 的西文字体槽**：run 直接格式只在含拉丁字符时修复 ascii/hAnsi
   （既有保守策略，避免对中文渲染无影响的槽位做无谓改写）；中文实际渲染
   走 eastAsia 槽，该槽始终被正确修复。

## 6. 与既有体系的关系

```
docx_reader（只读解析）  ──▶ analyzer（描述性画像）
style_resolver（有效属性）──▶ analyzer / normalizer / lint 同一口径
templates + rules yaml  ──▶ TemplateRunner（样式事实 + 页面）
normalizer              ──▶ run 级直接格式（复用，无新决策）
operations/write_package──▶ 全部 OOXML 变更与保护副本写出
lint_engine             ──▶ before / after 同口径复检
```

conversion 层不新增任何 OOXML 写入器，也不新增 lint 规则；它是既有能力的
编排层 + 两个新增确定性环节（角色分类、样式脚手架）+ 一个审计面（报告）。

## 7. 测试设计

`tests/conversion/test_conversion.py`（12 项）：

- 输入边界：存在性/扩展名拒绝；
- Analyzer：段落/表格/样式/有效字体/页边距画像；
- Test 1：扁平 DOCX（仅 Normal、宋体五号直接格式、错误页边距、手工标题、
  表格）转换成功，输出可读、正文逐字一致、6 个样式补建、9 段重指派、
  ERROR 显著下降，页边距变为 2.8/2.6；
- Test 2：正文 run 宋体 → 仿宋、10.5pt → 12pt，且存在对应 FONT001
  可追踪记录；
- Test 3：`一、` / `（一）` / `1.1.1` 手工编号标题 → heading 1/2/3
  样式（黑体、规定字号、加粗、outlineLvl 可被导航窗格识别），
  表格段落 → 表格表头/表格正文；
- Test 4：Markdown + JSON 报告生成，七个章节齐全，每条 change 含
  location/before/after/rule，未解决问题包含 NUM001/TOC001；
- CLI：`convert` 子命令冒烟（含退出码语义：仍有 NUM/TOC ERROR 时退出码 1）。

## 8. 后续演进方向

- 编号与目录：在用户显式确认下，提供"手工编号 → numPr 绑定 / TOC 域生成"
  的可选结构任务（独立于格式转换）；
- 封面识别模板化：基于模板 `cover_style_pattern` 做受控封面样式指派；
- caption 角色：图片标题模式识别与样式套用；
- 多模板对照报告：同一输入对多模板的画像/差异预检。
