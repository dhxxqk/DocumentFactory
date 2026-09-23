# GRID_RESEARCH_IMPLEMENTATION_PLAN_V1 — 模板结构分析

## 1. 模板来源

- 源文档：`source/课题4实施方案_V1.1.4.docx`（2,295,387 字节，39 页）
- 来源：真实科研课题实施方案 Word 文档
- 提取方式：`document_factory.docx_reader.read_docx` 解析 OOXML，手工核对
  styles / paragraphs / tables / sections / 页眉页脚
- 提取脚本：一次性 `analysis_task011.py`（任务后已删除，不入库）

## 2. 提取的格式事实

### 2.1 页面设置（section #1）

| 项 | 值（twips） | 值（cm） |
| --- | --- | --- |
| 页面尺寸 | 11906 × 16838 | 21.00 × 29.70（A4） |
| 上边距 | 1587 | 2.80 |
| 下边距 | 1474 | 2.60 |
| 左边距 | 1587 | 2.80 |
| 右边距 | 1474 | 2.60 |
| 页眉距边界 | 794 | 1.40 |
| 页脚距边界 | 794 | 1.40 |
| 分节类型 | nextPage | — |

结论：A4 纵向，页边距 2.8/2.6/2.8/2.6 cm，与电网科技项目实施方案文档格式
规范 V1.4 一致。

### 2.2 字体规则（正文 / Normal docDefaults）

- `Normal`（默认段落样式）：`rFonts` ascii/hAnsi/cs = Times New Roman，
  eastAsia = 仿宋；`sz=24`（12pt）；`color=000000`；`jc=start`。
- `正文`（styleId=Style5，基于 Normal）：
  - rFonts：Times New Roman + 仿宋
  - sz=24（12pt），color=000000，bold=False
  - jc=both（两端对齐）
  - ind：firstLine=420 twips（约 1.75 字符，规范要求 2 字符，模板按规范取 2）
  - spacing：line=360 lineRule=auto（1.5 倍行距），before=0，after=0

### 2.3 标题层级（Heading 1/2/3）

| 级别 | styleId | 中文字体 | 西文字体 | sz(half-pt) | 字号 | color | bold |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | Heading1 | 黑体 | Times New Roman | 32 | 16pt(三号) | 000000 | True |
| H2 | Heading2 | 黑体 | Times New Roman | 28 | 14pt(四号) | 000000 | True |
| H3 | Heading3 | 黑体 | Times New Roman | 24 | 12pt(小四) | 000000 | True |

标题段落样本（实文档）：
- `#93 Heading1 课题概述`
- `#94 Heading2 研究背景`
- `#129 Heading3 中长期负荷预测模块研发目标`
- `#236 Heading1 任务1：融合多源数据与不确定性分析的中长期负荷预测模块研发`

### 2.4 表格规则

| 样式名 | styleId | 中文字体 | sz(half-pt) | 字号 | color | bold | jc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 表格表头 | Style6 | 黑体 | 21 | 10.5pt(五号) | 000000 | True | center |
| 表格正文 | Style7 | 仿宋 | 21 | 10.5pt(五号) | 000000 | False | start |
| 表格正文-居中 | - | 仿宋 | 21 | 10.5pt(五号) | 000000 | False | center |

表格样本：5 个表格均使用 `TableGrid` / `TableNormal` 表样式，首行设置
`tblHeader`（重复表头）。表格正文行距 line=240（单倍）。

### 2.5 图片标题规则（Caption 样式）

- `caption`（styleId=Caption，基于 Normal）：
  - rFonts：Times New Roman + 黑体
  - sz=21（10.5pt），color=000000，bold=False
  - jc=center
  - spacing：line=240 lineRule=auto，before=120，after=120
- 实文档中 15 个段落使用 Caption 样式（图/表题注）。

### 2.6 页眉页脚规则

- `header2.xml`：1 段，文本 `课题4：支撑电网中长期规划的负荷预测模块研发与应用`
  （正文区页眉，奇数页）。
- `footer2.xml`：1 段，含 `PAGE` 域（页码，居中）。
- `header1/header3/footer1/footer3.xml`：空段（偶数页/首页占位）。
- `Header`/`Footer` 样式基于 Normal，无额外字体覆盖。

### 2.7 域（Fields）

- TOC 域 1 个：`TOC \z \o "1-2" \u \h`（目录，1-2 级）
- PAGE 域 1 个：` PAGE `（页脚页码）

### 2.8 段落样式使用分布（Top）

| styleId | 样式名 | 段落数 |
| --- | --- | --- |
| Style7 | 表格正文 | 282 |
| - | 表格正文-居中 | 207 |
| Style6 | 表格表头 | 92 |
| Style5 | 正文 | 91 |
| TOC2 | toc 2 | 60 |
| Heading2 | heading 2 | 60 |
| Normal | Normal | 45 |
| ListBullet | List Bullet | 36 |
| Heading3 | heading 3 | 22 |
| Caption | caption | 15 |
| TOC1 | toc 1 | 11 |
| Heading1 | heading 1 | 11 |

### 2.9 诊断

`docx_reader` 报告 0 条诊断（无 altChunk / 文本框 / AlternateContent / 修订）。

## 3. 与 V1.4 规范的关系

源文档格式事实与 `GRID_TECH_V1_4` 模板（电网科技项目实施方案文档格式规范
V1.4）完全一致：

- 页面 A4 + 页边距 2.8/2.6/2.6 cm（注：源文档右边距 2.6，左 2.8，与 V1.4 一致）
- 正文仿宋 12pt 1.5 倍行距 首行缩进 2 字符 两端对齐
- 标题黑体 16/14/12pt
- 表格表头黑体、表格正文仿宋、10.5pt 居中

因此本模板的 `rules` 与 `GRID_TECH_V1_4` 规则参数同构。差异在于 `metadata.source`
指向真实业务文档，`template_id` 为业务语义标识，`category` 增加 `research`。

## 4. 模板定义映射

模板 `template.yaml` 的 `rules` 字段直接对齐 `operations` 层入参：

- `rules.body` → `BodyRule` → `FontProfile` + `ParagraphProfile`
- `rules.headings.h1/h2/h3` → `HeadingRule` → `apply_style` + `FontProfile`
- `rules.tables` → `TableRule` → `apply_table_font` / `apply_table_alignment`
- `rules.page` → `PageFormattingOperation`
