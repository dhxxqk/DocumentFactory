# TASK_DOC_INTERNAL_TRAINING_CONVERT_002 报告

- 日期：2026-10-08
- 性质：**纯文档转换任务**。转换未引入新模板/批处理/MCP/编号/OCR/LLM 能力。
- 转换中发现的 1×1 排版容器误着色问题，经用户确认后做了**最小 Core 修复**
  （见 §8），并补充 synthetic 测试、全量回归后重跑两篇转换。
- 模板：`INTERNAL_TRAINING_DOCUMENT_V1`；规则：`rules/internal_training_document_v1.yaml`。
- 输入仅为用户显式提供的两篇 DOCX（已逐字节校验与上传原件一致），存放于
  gitignored 的 `local_samples/internal_training/`；未扫描任何其他目录。
- 本报告仅含聚合格式事实与文件名，不含业务正文文本。

## 1. 输入登记

| 项 | 文档 A | 文档 B |
|---|---|---|
| 文件名 | 第三周_规划管理能力_培训材料初稿(1).docx | 第四周 执行管理（初稿-已发送征求意见）(1).docx |
| 大小（字节） | 68,344 | 277,551 |
| SHA-256 | c5e24bb2932b443886ecef32f0e85057adec79c429794f6bffc04117b6842515 | e2ff59b85d60ef9685b8c511ad952aa06b5368e4edea5f2c7098c76a2a65d5de |
| section 数 | 1 | 1 |
| 横向 section | 无（单节纵向） | 无（单节纵向） |
| 表格数（其中 1×1 容器） | 43（13） | 80（0） |
| media 部件 / 嵌入 / 显示尺寸 | 0 / 0 / 0 | 2 / 2 / 2 |
| Heading 1 / 2 / 3 | 11 / 26 / 0 | 9 / 31 / 40 |

两篇均无横向 section（与第一周模板源文档的三节结构不同；本任务无横向页检查对象）。

## 2. 输出（均为新文件，未覆盖输入）

- `output/internal_training/converted/第三周_规划管理能力_培训材料初稿_INTERNAL_TRAINING_V1.docx`
- `output/internal_training/converted/第四周 执行管理（初稿-已发送征求意见）_INTERNAL_TRAINING_V1.docx`
- 逐篇流水线报告（含完整修改记录，本地保留，已加入 .gitignore）：
  `reports/internal_training_conversion/<原文件名>_NORMALIZATION_REPORT.md`
  （同名 .json 机器报告）。
- 两篇的实际变更部件均仅为 `word/document.xml`、`word/styles.xml`。

## 3. lint 前后对比

| 文档 | Before ERROR | Before WARNING | 流水线 After ERROR/WARNING | 总标题修正后 ERROR | WARNING |
|---|---:|---:|---|---:|---:|
| A 第三周 | 1597 | 154 | 0 / 0 | 2 | 0 |
| B 第四周 | 2915 | 369 | 0 / 0 | 4 | 0 |

注：A 的 Before 计数与首次试跑（1584/167）略有差异，原因是 §8 的 1×1 判定
修复同时作用于 lint/统计层（13 个 1×1 容器不再按表头统计），属同一修复的
确定性结果。

总标题修正后的残留 ERROR 全部来自该标题段落本身（见 §6 待人工确认 1）：

- A：FONT003×1、FONT001×1；
- B：FONT003×4。

除此之外两篇最终文档 ERROR/WARNING 均为 0。INFO 为事实性提示，不阻断
（A：4276；B：13935）。

## 4. Content Integrity Gate

每篇执行两次闸门：转换流水线写包后一次、总标题最小修正写包后再一次
（Core 生产级 `verify_content_integrity`，登记实际差异部件，仅允许
word/document.xml 与 word/styles.xml 变化）。

| 检查项 | A 第三周 | B 第四周 |
|---|---|---|
| 闸门结论（两次） | PASS / PASS | PASS / PASS |
| 可见段落文本序列 | 一致 | 一致 |
| Run 级文本切分 | 一致 | 一致 |
| 表格单元格文本 | 一致 | 一致 |
| 表格结构（行/单元格/gridSpan/vMerge） | 一致 | 一致 |
| 域指令 / 超链接显示文本 / 页眉页脚文本 | 一致 | 一致 |
| *.rels 关系部件 | 一致 | 一致 |
| media 部件数 | 0 | 2 |
| media SHA-256 集合 | 一致（无图片） | 逐个一致 |
| 嵌入 rId 顺序 / 显示尺寸 cx,cy | —（无图片） | 一致 / 一致 |
| 段落/表格/节/绘图计数 | 一致 | 一致 |

## 5. 格式核验（OOXML 有效格式统计，非 styles.xml 推断）

### 5.1 正文

- A：正文 run 宋体 12pt 共 106（另有 1 个总标题 run 为华文中宋 24pt）；
  1.5 倍行距（360/auto）99 段、首行缩进 firstLineChars=200 99 段、两端对齐 99 段。
- B：正文 run 宋体 12pt 共 1016；1.5 倍行距 459 段、首行缩进 2 字符 459 段、
  两端对齐 459 段。

### 5.2 总标题最小修正（任务书第 5 条）

两篇正文第一个非空段落均匹配 `【第X周】…`，已做且仅做格式修正
（华文中宋 / 24pt / 加粗 / 黑色），使用 Core 原语 `operations.apply_font`，
未改文字、未改 pStyle、未改编号：

| 文档 | 匹配 | 修正 run 数 | 原 pStyle | numPr |
|---|---|---:|---|---|
| A | 是 | 1 | 无（保持无样式） | 无 |
| B | 是 | 4 | styleId "2"（heading 1，保持不变） | 无 |

### 5.3 表格（1×1 修复后重跑结果）

表头（各内容表首行；1×1 排版容器已排除）：

| 项 | A 第三周 | B 第四周 |
|---|---|---|
| 底纹 fill=D7D7D7 表头段落 | 96/96 | 269/269 |
| 宋体 10.5pt 加粗 run | 97/97 | 278/278 |
| 水平居中表头段落 | 96/96 | 269/269 |
| 黑字 000000 | 是 | 是 |
| 表体 run 宋体 10.5pt | 481/481（非加粗 468；保留源原有加粗 13） | 1303（非加粗 1292；保留源原有加粗 11） |
| 表体水平对齐分布 | before left 412 → after left 425（含 13 个容器段按表体保留原对齐，净增为容器重新归类所致，无任何对齐被改写） | before left 693 / center 404 / both 9 → 完全相同 |
| 表格形状序列（行列结构） | 43/43 一致 | 80/80 一致 |

1×1 排版容器（A 独有，13 个）底纹**逐格原样保留**：EAF2F8 ×12、F2F2F2 ×1
（before/after 完全一致）；不再被加粗/居中/灰底。B 无 1×1 表。

未重算列宽、未拆表/合表；vMerge/gridSpan 由闸门表格结构比对保证一致。

### 5.4 section

两篇均为单节纵向，转换前后逐节方向与 `w:orient`（均为缺省，不新增属性）
一致；无横向节。

## 6. 待人工确认的问题（非阻断）

1. **总标题 24pt 与 lint 字号规则的预期偏差**：任务书第 5 条显式要求总标题
   24pt，而模板 lint 对 Heading 1 期望 16pt（B 的标题段样式为 heading 1 →
   FONT003×4）；A 的标题段无段落样式，按正文规则统计 → FONT001×1 +
   FONT003×1。这些 ERROR 是任务书要求格式的直接结果，未通过修改 Core 或
   降低断言来清零。请确认 24pt 为预期保留。
2. ~~1×1 单格表被误着色~~ **已修复，见 §8**；修复后建议人工在 Word 中快速
   目检第三周 13 个提示框外观。
3. **RENDER_UNAVAILABLE**：本机探测 `LibreOffice=null`、`Word COM=false`，
   未执行全页渲染。任务书要求的快速位置检查（第一页、首个一级/二级标题、
   第一张表、图片页、横向页、最后一页）无法以截图完成，已用 OOXML 有效
   格式统计替代（§5）；A 无图片页/横向页，B 的 2 张图片由闸门保证未变。
   建议人工在 Word 中打开两篇输出做最终视觉确认。

## 7. 其他事实

- 输入 SHA-256 全程未变；转换与修正均写独立新文件。
- 未重建编号：numbering 相关部件/内容未触碰，闸门关系检查通过。
- 流水线为每篇新建样式「表格表头」「表格正文」（文档已内置 heading 1/2/3）。
- 全量回归：`pytest -q` → **233 passed**（含本次新增 2 个 1×1 容器测试）。

## 8. Core 最小修复（经用户确认后实施）

- 问题：Core 的 `first_row_or_repeat` 表头策略把 1 行 × 1 列的排版容器
  （提示/要点框）唯一单元格判为表头，导致 A 的 13 个容器被统一改为
  D7D7D7 灰底、加粗、水平居中。
- 规则：新增共享确定性判定 `docx_reader.is_single_cell_table(table)`
  （`len(rows)==1 and columns==1`），在四个表头判定/统计点统一接入：
  转换分类器 `conversion/classifier.py`、normalize 角色分类
  `role_classifier.py`、lint `table_analyzer.py`、只读统计
  `analyzer/visible_format.py`。显式 `w:tblHeader` 重复表头标记仍优先
  尊重（源文档显式意图不被隐式规则覆盖）。
- 效果：1×1 容器段落归类为表体（宋体 10.5、不写 jc、不动底纹/加粗），
  真实内容表首行表头行为不变。
- 测试：新增 `tests/conversion/test_single_cell_layout_table.py`
  （分类单测 + INTERNAL_TRAINING_DOCUMENT_V1 端到端：容器底纹/对齐保留、
  普通表与显式 tblHeader 表仍按表头规范化），2 个用例通过；全量 233 passed。
- 提交 SHA：代码提交 `0560faacd3a7230a2a07d3d754d77b8ae4850ea9`
  （7 files changed，173 insertions，8 deletions）；本报告由独立 docs 提交入库。
