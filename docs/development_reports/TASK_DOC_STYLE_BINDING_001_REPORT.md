# TASK_DOC_STYLE_BINDING_001 任务报告

## 1. Root Cause

此前**不是** `default_technical_document_v1` 的字体规则错误，而是三层断点导致规范定义没有完整落实到真实业务 DOCX：

1. **role_classifier 对无 pStyle 正文未覆盖**：真实业务 DOCX（如四川课题1 V3）中 524 个非表格段落没有任何 `w:pStyle`，读取器把它们默认解析为 Normal，但旧分类器只识别“显式 pStyle=Normal 且非自定义”的高置信正文，无 pStyle 段落整体落入 `other`，完全跳过。
2. **normalizer 保留原 pStyle**：上一轮 TASK_DOC_FULL_NORMALIZATION_001 的策略是“保留 pStyle + 叠加直接格式”，正文不绑定“正文”样式、表格单元格也不绑定表格专用样式；一旦直接格式覆盖不完整（或在 Word 中重新套用样式），Normal/宋体等继承事实就会回潮。
3. **MCP 默认 preset 仍指向 grid_tech_v1_4**：用户不显式传 preset 时，`format_document / audit_document / list_presets` 加载的是旧兼容规范，默认技术文档规范 V1（映射 V1.4）即使定义正确也不会被默认执行。

附带发现并修复的缺陷：题注正则 `^\s*[图表]\s*\d+\s*[-–—]\s*\d+` 会把“图3-1显示，2021—2025年……”这类**句首引用正文**误判为图题（真实文档 146 个命中里约 72 个是正文句），题注优先于正文判定，进一步压低了正文识别率。

## 2. Architecture Change

```
规则开关（rules/default_technical_document_v1.yaml，grid 无对应键）
  body.style_binding / tables.style_binding
        │
        ▼
role_classifier
  ├─ body_named（显式正文，原有）
  ├─ body_safe_normal（显式 pStyle=Normal，原有）
  ├─ body_unstyled（新增：无 w:pStyle，同一套高置信门限）
  ├─ table_header / table_body（原有）
  └─ table_center（新增：短字段+显式居中的非表头单元格）
        │
        ▼
style_binding（新模块）
  ├─ ensure_binding_styles：缺样式时经 Operations 创建
  │    正文 / 表格表头 / 表格正文 / 表格正文-居中
  │    表格样式无 w:basedOn；既有链式继承到正文的予以切断
  ├─ sync_style_model：样式 XML 填充后回写内存模型，
  │    保证同一次运行内 StyleResolver 级联结果正确
  └─ bind_paragraph_style：pStyle 重绑定并同步段落模型
        │
        ▼
normalizer
  ├─ 脚手架创建 → _normalize_named_styles 显式填充定义 → 模型同步
  ├─ 三类正文角色 → pStyle=正文 → 段落显式正文 pPr →
  │    按 effective format 修复 run 级宋体/主题字体/字号冲突
  ├─ 表格角色 → 绑定表格专用样式 → 全部缩进归零/段前段后 0/
  │    单倍行距 → 表头黑体、表体仿宋、TNR、10.5pt
  └─ STYLE_BINDING 12 项计数器 + Validation Report 3.2 节
```

兼容性闸门：所有新增行为都由 `style_binding` / `safe_normal_normalization` /
`regular_table_normalization` 开关控制；`grid_tech_v1_4.yaml` 不含这些键，
经测试验证其样式集合、pStyle、字节输出与旧版一致。

## 3. Changed Files

| 文件 | 性质 | 说明 |
|---|---|---|
| `src/document_factory/style_binding.py` | 新增 | 样式创建/继承隔离/模型同步/pStyle 绑定 |
| `src/document_factory/operations/style.py` | 修改 | 新增 `create_paragraph_style`、`apply_based_on` |
| `src/document_factory/operations/paragraph.py` | 修改 | 新增 `apply_paragraph_style`（pStyle 位于 pPr 首位） |
| `src/document_factory/operations/__init__.py` | 修改 | 导出新操作 |
| `src/document_factory/role_classifier.py` | 修改 | `body_unstyled`、`table_center` 角色；置信门限重构 |
| `src/document_factory/normalizer.py` | 修改 | 脚手架+绑定调度、表格样式 jc 显式化、STYLE_BINDING 统计、报告 3.2 节 |
| `src/document_factory/mcp_server.py` | 修改 | `DEFAULT_PRESET=default_technical_document_v1`，三处默认值切换；payload 增加 style_binding |
| `rules/default_technical_document_v1.yaml` | 修改 | 两个 `style_binding: true` 开关；题注正则收紧 |
| `tests/test_style_binding.py` | 新增 | 12 个专项测试（覆盖任务书 TEST 1–11 及附加隔离/题注用例） |
| `tests/test_full_normalization.py` | 修改 | 4 处旧期望按 V1.4 新行为改写（保留用例、注释旧→新原因），grid 回归加绑定零行为断言 |
| `tests/test_mcp_server.py` | 修改 | 2 处默认 preset 断言改为 default_technical_document_v1 |
| `docs/development_reports/TASK_DOC_STYLE_BINDING_001_REPORT.md` | 新增 | 本报告 |

未修改：`grid_tech_v1_4.yaml`、CLI 默认值、模板分片、转换器默认规则路径（任务仅要求 MCP 三接口）。

## 4. 正文样式实现

- 文档缺少“正文”时，以 styleId `DFBody`（冲突时自动追加后缀）创建
  `w:style type=paragraph`，随后由 `_normalize_named_styles` 写入全部显式事实：
  仿宋 / Times New Roman / 12pt（sz 24）、firstLineChars=200、
  spacing before/after=0、line=360 auto、jc=both。
- **不修改 Normal，不把 Normal 全局改成正文**；真实文档回归中 Normal 的
  `w:name` 与定义保持原样。
- `body_named` / `body_safe_normal` / `body_unstyled` 三类正式正文统一
  `pStyle=正文`；段落同时写入显式正文 pPr；run 级按 **effective format**
  对比修复：eastAsia 宋体（含主题字体）→仿宋、ascii/hAnsi→Times New
  Roman、字号→12pt。加粗/斜体/下划线/超链接/域/文字内容一律不动
  （专项测试断言加粗保留、文本逐字一致）。

## 5. 表格样式实现

- 缺少时创建 `表格表头(DFTableHeader)`、`表格正文(DFTableBody)`、
  `表格正文-居中(DFTableBodyCenter)`，**均无 w:basedOn**，定义全部显式：
  - 表头：黑体 / TNR / 10.5pt（sz 21）、加粗、居中；
  - 表体：仿宋 / TNR / 10.5pt、左对齐（start）；
  - 居中：仿宋 / TNR / 10.5pt、居中；
  - 三者统一 firstLine/left/right=0、spacing before/after=0、line 240 auto。
- 已存在的表格样式若 basedOn 链到达“正文”，先切断链再补齐显式定义
  （lint TABLE005 修复，非屏蔽）。
- 绑定规则：regular 表第一行或 `w:tblHeader` 重复表头行→表格表头；
  其余行→表格正文；仅当非表头单元格**显式 jc=center 且为 ≤20 字、
  无句读标点的短字段**时使用表格正文-居中（不做复杂语义猜测）。
- 封面表（SKIP_TABLE_COVER）、vMerge 表（SKIP_TABLE_COMPLEX）、
  嵌套/不足两行情景继续整体跳过。

## 6. 无 pStyle 正文识别策略

- 区分依据：读取器在缺 pStyle 时会回填默认 styleId，因此直接检查
  段落原始属性袋 `"pStyle" in paragraph.properties`：无该键→
  `body_unstyled`，有且为 Normal/常规→`body_safe_normal`。
- 两者共用同一套保守置信门限 `_is_confident_body`：位于第一个真实
  Heading 1 之后、非 TOC、非表格、非 Heading、非题注、非 drawing/
  pict/object、非 fldSimple/fldChar/instrText、非 numPr/大纲级别 0–2、
  非居中/右对齐、非 ≤40 字全粗体模拟标题。宁可漏判，不误判。
- 题注正则收紧为 `^\s*[图表]\s*\d+\s*[-–—]\s*\d+[\s　]+\S`（编号后必须
  有空白再跟标题，与模板 `{prefix}{chapter}-{sequence} {title}` 同构），
  真实文档题注命中由 146 收敛到 74，被排除的 72 个句首引用段落按同一
  门限进入正文识别，最终识别正文 445 段。

## 7. MCP 默认 preset 修改

- `mcp_server.DEFAULT_PRESET = "default_technical_document_v1"`；
  `list_presets().default`、`audit_document`、`format_document` 三处默认
  值统一切换。
- `grid_tech_v1_4` 保留注册、可显式调用；专项测试验证显式调用成功且
  绑定统计全 0、样式集合不增、无 style/style_create/style_based_on 变更。
- 回归测试证明 `format_document(path)` 与
  `format_document(path, preset="default_technical_document_v1")`
  产物字节一致、preset 字段一致。

## 8. Content Integrity Gate

绑定仅改 `word/document.xml`（pStyle/段落/run 格式）与
`word/styles.xml`（样式定义），仍在既有白名单内。真实文档回归：

```
visible_text_equal / run_text_equal / table_cell_text_equal /
table_structure_equal / field_instructions_equal / hyperlink_text_equal /
header_footer_text_equal / relationships_equal / media_sha256_equal = True
status = PASS
changed_zip_parts = ['word/document.xml', 'word/styles.xml']
```

表格行列、宽度、合并、图片/图表、域指令、超链接、页眉页脚、章节文字
全部不变；源文件 SHA-256 运行前后一致。

## 9. Real-document Read-only Regression

源文件（只读，未修改、未覆盖）：

```
技术报告_课题1_四川用电负荷特性分析及变化趋势分析_V3_FINAL_INTEGRATE_002.docx
SHA-256 前缀 c51c833464170e2a，13,336,575 bytes
```

临时输出：`output/normalized/<stem>_stylebinding_regression.docx`。

- lint：ERROR 837 → 1，WARNING 356 → 1，INFO 678 → 6130（绑定后大量
  INFO 合格项）；残留 1 ERROR 为 NUM001（标题手写编号，属明确不自动
  修复的编号策略），残留 1 WARNING 为 TOC005（updateFields 设置，
  本轮不修改域），11 条 TABLE009 为 tblHeader 重复标记的 INFO 提示。
- STYLE_BINDING：body_style_created=1、table 三样式 created 各 1；
  unstyled_body_detected=445 / bound=445；body_style_bound=445；
  table_header_bound=59、table_body_bound=259、table_center_bound=6；
  table_indent_repaired=324；direct_font_override_repaired=384。
- 抽查：
  - 第一章正文（p52–p57）与第三章正文（p146 起，含“图3-1显示…”
    句首引用段 p188）：pStyle=正文、中文 effective=仿宋、
    Latin/数字=Times New Roman、12pt、firstLineChars=200、
    line=360 auto、jc=both；
  - 表3-1（Table 1，36 段落）、表3-5（Table 4，40 段落）、
    表3-7（Table 5，30 段落）：单元格样式集合仅
    {表格表头, 表格正文}，无正文/Normal；缩进全部为
    {firstLine:0,left:0,right:0} 且无 *Chars 残留；表头 effective
    黑体/21、表体仿宋/21、Latin TNR；
  - 全文 445 个正文段落绑定正文，**0 个表格单元格仍绑定正文**；
  - 中英文数字混排段（p52 等）effective 双字体正确；
  - 对输出再次规范化：changes=0，且两次输出字节一致（幂等）。

## 10. Test Result

```
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
231 passed
```

- 基线 219 项：0 倒退；其中 4 项旧断言因“保留 pStyle”旧策略与 V1.4
  冲突而改写期望（test_body01/test_body02/test_table01 + MCP 默认值
  2 处），逐项在用例注释中记录“旧行为→为何冲突→新行为”，未删除任何
  测试；grid 回归用例新增字节级“绑定零行为”断言。
- 新增 `tests/test_style_binding.py` 12 个用例，覆盖任务书 TEST 1–11：
  无样式正文、Normal 正文、run 宋体覆盖（兼验加粗保留）、表头、表体、
  正文污染单元格、无 pStyle 表格、MCP 默认 preset、grid 兼容、
  Content Integrity、幂等，另加表格样式 basedOn 隔离、居中变体保守
  判定、题注正则精度三个边界用例。
- BODY001 在普通正文上 0 残留；regular 表 TABLE002/TABLE003 0 残留；
  剩余表格告警仅来自封面表与 vMerge 表（刻意跳过，报告中列为未解决对象），
  未通过屏蔽 severity 使测试变绿。

## 11. Git Commit

- 提交信息：
  `TASK_DOC_STYLE_BINDING_001: bind body and table paragraph styles to default technical spec`
- 任务 commit 哈希：`ceda7ce995789768d8c1e8b9e8bb7672eb809eb2`
  （推送区间 `33d84fa..ceda7ce master -> master`；推送后
  `HEAD == origin/master == ceda7ce`）
- 回填 commit：`docs: backfill TASK_DOC_STYLE_BINDING_001 commit hash`
- 显式暂存上述 12 个变更/新增文件；`reports/` 下 3 个既有未跟踪四川
  报告与 `.trae/` 未暂存。

## 12. Remaining Risks

1. NUM001 手写标题编号、TOC005 updateFields 仍属明确不自动处理范围，
   需要编号/域策略的后续独立任务。
2. vMerge 合并表、封面信息表仍整体不绑定；若后续规范要求逐单元格治理，
   需要先行确定合并区域的表头语义。
3. `表格正文-居中` 采用保守信号（短字段+显式居中）；真实文档 6 处命中
   已正确绑定，但跨文档使用时仍建议抽查居中列。
4. 无 LibreOffice/Word 环境，VISUAL_RENDER_GATE 仍为 NOT_AVAILABLE，
   结论以 OOXML 结构、StyleResolver effective format 与 lint 为准。
5. 题注识别依赖“编号后空白”的规范写法；若个别图题编号后无空格直接
   连写标题，会回落为正文（格式更接近正文而非漏改，且不会误改标题）。

## 13. Next Suggestion

- 后续独立任务 `TASK_TOPIC1_DOCUMENTFACTORY_FORMAT_002` 再对四川课题1
  正式报告执行重新格式化（本任务未启动、未修改正式报告）；
- 编号自动化与 TOC 域更新单列任务处理 NUM001/TOC005；
- 如业务需要，扩展合并表角色判定与表格列级居中配置，但须保持
  “宁可保守、不误绑”的分类原则。
