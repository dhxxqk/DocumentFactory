# 内部培训管理规范文档模板 V1 格式事实定义

本文件是 `INTERNAL_TRAINING_DOCUMENT_V1` 的唯一人工核对格式事实源，也是
lint 规则文件 `rules/internal_training_document_v1.yaml` 的规范主源（source）。
全部事实来自对源文档的**脱敏聚合统计**（只记录计数、字号、色值、尺寸等格式
事实；不收录任何业务正文）。真实文档仅存放于 `local_samples/`（.gitignore
排除），不进入 Git。

## 1. 适用范围

- 内部培训 / 周度管理规范类 DOCX 文档。
- 本模板为**独立模板**：不 `extends` DEFAULT_TECHNICAL_DOCUMENT_V1。

## 2. 页面（多 section 必须保持）

| 节 | 方向 | 纸张 (twips) | 上下边距 | 左右边距 | 页眉/页脚 |
|---|---|---|---|---|---|
| §1 | portrait | 11906 × 16838 (A4) | 1440 (2.54cm) | 1800 (3.17cm) | 851 / 992 twips |
| §2 | landscape | 16838 × 11906 (A4) | 1800 (3.17cm) | 1440 (2.54cm) | 851 / 992 twips |
| §3 | portrait | 11906 × 16838 (A4) | 1440 (2.54cm) | 1800 (3.17cm) | 851 / 992 twips |

- 分节类型：nextPage / nextPage；顺序 portrait → landscape → portrait。
- 源文档 `w:pgSz` 未显式写 `w:orient`（Word 依宽高推断），规范化保持该写法：
  仅写显式宽高与各方向对应边距，不新增 orient 属性，不改变方向与节顺序。

## 3. 首页总标题（事实记录；MVP 暂不区分）

- 形态：段落开头匹配 `【第X周】`（X 为中文数字或阿拉伯数字）。
- 可见事实：华文中宋、24pt（sz=48）、加粗、黑色；无 numPr、无直接 jc。
- 该段虽曾套用内置 "heading 1" 样式，但**不是**普通章节标题。
- **MVP 范围说明**：独立「文档标题」样式与 document_title 分类能力本次不实现，
  该段在 MVP 中按普通 Heading 1 规范化（字号随 Heading 1 归一为 16pt，24pt
  总标题外观不保留；字体仍为华文中宋、加粗、黑色、文本不变）。
  后续任务再补独立样式、不参与自动编号、段前 17.4pt / 段后 10.5pt 等规则。

## 4. 内置标题

| 层级 | 中文字体 | 字号 | 加粗 | 颜色 | 编号 |
|---|---|---|---|---|---|
| Heading 1 | 华文中宋 | 16pt | 是 | 000000 | numId=1 自动编号（保留，不重建） |
| Heading 2 | 华文中宋 | 15pt | 是 | 000000 | numId=1 自动编号（保留，不重建） |

- 模板不重建、不迁移多级列表；numbering.xml 原样保留。

## 5. 正文

- 字体：宋体（eastAsia / ascii / hAnsi 主流均为宋体）。
- 字号：小四 12pt（主流 189 个 run；10.5pt 仅 7 个 run，属表格/例外）。
- 行距：1.5 倍（line=360/auto，68 段主流）。
- 首行缩进：2 字符（firstLineChars=200，61 段）。
- 对齐：两端对齐（jc=both 主流 64 段）。
- 段前段后：0。
- 少量蓝色 0000FF 直接着色文本（非超链接）：不在本模板处理范围，保持原样。

## 6. 表格

- 共 7 张，均为 Table Grid 单实线边框；仅首行为表头（无 tblHeader 重复标记）。
- 表头（37/37 一致）：宋体 10.5pt、加粗、水平居中、黑色文字；
  底纹 `w:shd fill=D7D7D7`（100% 稳定值，另含 themeFill=background1 与
  themeFillShade=D8 派生属性；规范化写显式 fill 并移除 themeFill* 引用）。
  - 底纹取值规则：优先采用源文档稳定主流值 **D7D7D7**；
    若同类文档无稳定值，回退 **#D9D9D9**。
  - 表头段落行距：line=360/auto。
- 表体：宋体 10.5pt、非加粗；**逐格保留原有水平对齐**
  （统计：both=224 段、center=53 段），不做统一覆盖；单倍行距 line=240。
- 表体单元格原有 fill=auto / vMerge 等结构属性原样保留。

## 7. 图片与关系（禁止修改）

- 33 个 media 部件（29 PNG + 2 EMF 等），正文 31 处嵌入。
- Content Integrity Gate 强制：部件名 → (字节数, SHA-256) 不变；
  a:blip / v:imagedata 嵌入 rId 顺序不变；document.xml.rels 图片目标不变。
- 不修改图片内容、尺寸（drawing extent）、顺序与 media relationship。

## 8. 明确不做

- 不做内容改写、不做 LLM 语义分类；
- 不重建通用多级编号；不做图片 OCR；不做全盘自动扫描；
- 不修改 DEFAULT_TECHNICAL_DOCUMENT_V1 的任何语义。
