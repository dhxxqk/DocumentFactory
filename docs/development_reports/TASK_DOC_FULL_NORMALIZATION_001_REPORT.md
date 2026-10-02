# TASK Report

Task: TASK_DOC_FULL_NORMALIZATION_001 — DocumentFactory 生产级完整 DOCX 格式规范化能力增强

Date: 2026-10-02 +08:00

Agent: TRAE Agent（单 Agent 全流程实现；代码、测试、报告均由本 Agent 产出）

基线：`origin/master` @ `8ec741c`（任务开始前 `HEAD == origin/master`，工作树仅含本任务明确忽略的未跟踪文件）。

## Summary

将 normalize/MCP 能力从"只治理具名样式段落"升级为生产级完整规范化，新增 7 项能力：

1. **页面规范化（PAGE001/PAGE003）**：正文纵向节统一 A4（11906×16838 twips）
   与页边距（上 2.8 / 下 2.6 / 左 2.8 / 右 2.6 cm，页眉页脚距 1.4 cm）；
   横向节保留横向（PAGE002 允许宽表），仅规范化页边距，并发
   `SKIP_LANDSCAPE_SECTION` 警告。
2. **Safe Normal 正文识别与规范化**：保守识别仍挂 `pStyle=Normal/常规` 的
   高置信正文段落，**保留 pStyle 不改样式语义**，仅施加直接格式
   （仿宋/Times New Roman/12pt、首行缩进 2 字符 firstLineChars=200、
   1.5 倍行距、两端对齐）。
3. **Heading 完整格式**：heading1/2/3 样式补齐既有规范事实（Times New Roman
   西文、加粗 true、jc=left、keepNext=true）；标题段落仅修复直接覆盖项。
4. **题注规范化（CAPTION001/CAPTION002）**：按样式名（caption/题注）与保守
   文本模式（`^[图表]\s*\d+[-–—]\d+`）识别；黑体/TNR/10.5pt/不加粗/黑色/
   居中/单倍行距/段前段后 6pt/零缩进；不重排、不重编号、不移动题注。
5. **普通内容表格规范化**：表格经独立分类（regular / cover / layout /
   complex / ambiguous），仅对 ≥2 行、非嵌套、无 vMerge、非封面样式族的
   regular 表，直接格式治理表头（黑体/加粗/居中）与表体（仿宋/start）；
   不改列宽、tblGrid、合并，不重写 pStyle。
6. **Content Integrity Gate**：输出落盘复读后逐部件/逐文本/逐结构比对，
   任何内容漂移硬失败（`CONTENT_INTEGRITY_GATE 失败，已阻止交付`），
   只允许 `word/document.xml` 与 `word/styles.xml` 两个部件发生字节变化。
7. **Validation Report / MCP 统计增强**：报告 schema_version 1.1，9 节
   （角色统计、按规则归因、完整性闸门、未解决对象明细表等）；
   MCP `format_document` 返回 `normalization_stats` / `content_integrity` /
   `unresolved_counts`，summary 携带完整性闸门结论。

**新增行为全部由 opt-in 规则键门控**（`body.safe_normal_normalization`、
`tables.regular_table_normalization`、`caption` 块、`heading_policy`）。
MCP 默认 preset 仍为 `grid_tech_v1_4`；该 YAML 未增加任何新键，在同一综合
fixture 上实测不产生任何 safe-normal / caption / regular-table 对象，
grid_tech_v1_4 行为零变化（有专项回归测试）。

### RESULT：CONDITIONAL

- 功能、测试、CONTENT_INTEGRITY_GATE、FORMAT_EFFECT_GATE（幂等）均 PASS；
- 唯一未达标项：**VISUAL_RENDER_GATE = NOT_AVAILABLE**——本机无
  LibreOffice / Word 渲染后端，按任务红线未使用 WPS 等替代后端，视觉渲染
  未执行，如实标记而非伪造通过。

### 综合 fixture 复现（业务中性合成文档，非四川正式报告）

`tests/test_full_normalization.py` 的合成 fixture 一次性覆盖：封面信息表
（封面样式族）、TOC 域、1px 嵌入图片（+rels+drawing）、手工编号
heading1/2/3（含错误直接覆盖）、Safe Normal 正文段（中英文混合）、
图/表题注、3×2 普通内容表格、vMerge 复杂表、中部横向节、错误 Letter
尺寸末节 sectPr。任务开始前在该 fixture 上复现了任务书指出的 4 个缺口：
页面/正文/题注/普通表格均未进入 normalize。

同一 fixture 任务完成后的实测证据（规则文件 SHA-256
`35db36a62174afd764b3bbd15a000f2340c94ff4079d530c6b49d336e0e32e87`）：

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| ERROR | 62 | 17 |
| WARNING | 21 | 11 |
| INFO | 64 | 119 |

- 属性修改记录：**108**；实际改动 ZIP 部件恰为
  `word/document.xml, word/styles.xml`。
- 页面：2 个节，1 个纵向节规范化（Letter→A4 + 页边距/页眉页脚距），
  1 个横向节保留并登记 `SKIP_LANDSCAPE_SECTION`。
- 对象角色：标题样式 3、标题段落 6、具名正文 1、Safe Normal 正文 3、
  题注 2、普通内容表格 1（表头段落 2、表体段落 4）；封面表与 vMerge 表
  分别登记 `SKIP_TABLE_COVER` / `SKIP_TABLE_COMPLEX`，零误改。
- 按规则归因：BODY002×8、BODY003×4、CAPTION001×6、CAPTION002×9、
  FONT001×5、FONT002×5、FONT003×5、FONT004×1、PAGE001×1、PAGE003×1、
  STYLE001×8、STYLE004×3、STYLE005×10、TABLE002×2、TABLE003×4、
  TABLE004×9、TABLE007×9、TABLE008×18。
- 剩余 17 ERROR 全部是任务书/既有 UNSUPPORTED 明确不自动处理的确定性
  边界项：NUM001×6 + NUM002×6（手工编号标题，永不转自动编号）、
  TABLE003×5（普通表 4 单元格 + vMerge 跳过表 1 单元格：lint 要求绑定
  命名"表格正文"样式，而本任务禁止重写 pStyle，直接格式已实际生效，
  属刻意保留的告警语义）。
- 剩余 11 WARNING：TABLE002×4 / TABLE003×2（同上 pStyle 保留取舍）、
  BODY001×1（Safe Normal 段保留 pStyle=Normal 的同源取舍）、
  PAGE002×1（横向节，刻意保留）、FRONT003×1、STYLE002×1、TOC005×1
  （均为既有规则，不在本任务范围）。

### FORMAT_EFFECT_GATE：PASS

综合 fixture 连续执行两次 normalize：第二次 **0 条修改**，输出 SHA-256
与第一次完全一致（所有 Operation 均 before==after 幂等）；
专项测试 `test_format_effect_gate_four_object_classes_and_idempotency`
断言四类对象（页面/正文/题注/表格）目标格式全部命中且重跑零改动。

### CONTENT_INTEGRITY_GATE：PASS

fixture 实测：段落 30→30、表格 3→3、节 2→2、drawing 1→1、
媒体文件 1 个且 SHA-256 全等、域指令/超链接显示文本/页眉页脚文本/
关系部件全等；另有篡改测试（人为改动输出文本/媒体）确认闸门必抛错
阻止交付。

## Changed Files

### 新增

| 文件 | 职责 |
| --- | --- |
| `src/document_factory/role_classifier.py` | 保守角色识别：`classify()` / `Classification` / `ParagraphRole` / `TableClassification`；8 种段落角色 + 5 种表格分类，宁可漏判不可错判 |
| `src/document_factory/integrity.py` | Content Integrity Gate：ZIP 部件清单/字节、媒体 SHA-256、段落/Run/单元格文本、表格结构、段落/表/节数量、域、超链接、页眉页脚、drawing/pict、关系部件比对 |
| `tests/test_full_normalization.py` | 22 项新测试：页面×3、Safe Normal 正文×4、Heading×2、题注×3、表格×4、完整性×4（含 FORMAT_EFFECT 幂等与篡改阻断）、MCP×1、grid opt-out 回归×1 |

### 修改

| 文件 | 修改要点 |
| --- | --- |
| `rules/default_technical_document_v1.yaml` | 仅映射模板分片既有事实：`document.header/footer_distance_cm:1.4`（page_rules.yaml）；heading1/2/3 补 latin_font Times New Roman / bold true / alignment left、新增 `heading_policy.keep_with_next`（heading_rules.yaml）；新增 `caption` 块（figure_rules.yaml 全部事实，含保守识别 pattern）；tables 补 header_bold / header_alignment / body_alignment / `regular_table_normalization` 开关（table_rules.yaml）；body 新增 `safe_normal_normalization` 开关；新增 CAPTION001/CAPTION002 规则 ID（仅规范化归因消费，lint 不发射） |
| `src/document_factory/normalizer.py` | `_apply_normalization` 改返回 `(changes, changed_parts, stats)`；新增 `_normalize_sections` / `_normalize_caption_ppr` / `_apply_effective_run_target`；命名样式处理扩展 Heading 完整格式；按角色分派段落；`normalize()` 落盘复读后执行完整性闸门、构建 stats/unresolved；Validation Report 升级为 9 节 schema 1.1 |
| `src/document_factory/operations/paragraph.py` | 新增 `apply_keep_next()`（`w:keepNext` toggle，经 Operations Layer） |
| `src/document_factory/operations/__init__.py` | 导出 `apply_keep_next`（import 与 `__all__`） |
| `src/document_factory/models.py` | `NormalizationResult` 增加 `normalization_stats` / `content_integrity` / `unresolved_counts`（default_factory，asdict 兼容） |
| `src/document_factory/mcp_server.py` | `format_document` 返回三类新统计，summary 含完整性闸门结论；JSON 仍 <10000 字符（有断言测试） |
| `src/document_factory/__init__.py` | 导出 `classify_roles` / `Classification` / `ParagraphRole` / `verify_content_integrity` |
| `src/document_factory/conversion/converter.py` | 适配 `_apply_normalization` 三元组返回（converter 默认仍用 grid_tech_v1_4，新键缺席即自动 opt-out，转换流水线行为不变） |

未删除任何文件。`grid_tech_v1_4.yaml` 零修改。

### 明确未触碰

- `reports/` 下 3 个未跟踪四川课题1报告：未 add、未修改、未删除；
- `.trae/` 未跟踪目录：未提交；
- 未使用任何四川正式报告作为 fixture（全部证据来自业务中性合成 fixture）；
- 未启动四川课题1的再次格式化。

## 实现要点与合规性

### Operations Layer 唯一路径

本任务没有引入任何 python-docx / 手工 zip+OOXML patch / LibreOffice /
Word COM 格式修改路径。所有 OOXML 变更均经由既有
`document_factory.operations`：`apply_section_properties`、
`apply_east_asian_font`、`apply_latin_font`、`apply_font_size`、
`apply_bold`、`apply_color`、`apply_alignment`、`apply_indent`、
`apply_spacing`、新增 `apply_keep_next`。角色识别与完整性校验为只读，
不构造 XML 写操作。

### Safe Normal 识别的保守条件（全部满足才纳入）

非自定义 Normal/常规样式；位于第一个真实 Heading 1 之后（排除编制说明/
目录/封面）；非空；无 drawing/pict/object；无 fldSimple/fldChar/instrText；
无 numPr、有效 outlineLvl ∉ {0,1,2}；有效 jc 非 center/right；
≤40 字且全 run 加粗的短行视为模拟标题而排除。误判代价由"仅直接格式、
pStyle 不动、且完整性闸门兜底文本"控制；漏判段落保持原状并列报告。

### 普通表格分类顺序

嵌套表/含嵌套子表 → SKIP_TABLE_LAYOUT；含 vMerge → SKIP_TABLE_COMPLEX；
全部非空单元格段落使用封面样式族 → SKIP_TABLE_COVER（先于行数判定，
保证单行封面登记表不误判）；<2 行 → SKIP_TABLE_AMBIGUOUS；其余 regular。
表头 = 第 1 行或 `tblHeader` 重复标题行（`first_row_or_repeat` 策略）。
表内题注优先于单元格角色。所有跳过项进入报告"未解决对象"表。

### 规则映射零新增规范

YAML 新增的每一项机器映射都逐一核对自
`templates/default_technical_document_v1/rules/` 既有分片
（page_rules.yaml / heading_rules.yaml / figure_rules.yaml /
table_rules.yaml），注释中注明来源分片，未发明任何规范事实。

## Test Result

### Test Command

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

### Result

- 任务基线（本任务开工时的 origin/master `8ec741c`）：**197 passed**；
- 本任务完成后：**219 passed**（197 + 新增 22，全绿，0 failed / 0 skipped）；
- 新增测试单独运行：22 passed；
- 开发中途曾出现 10 项失败，根因为 converter 未适配三元组返回，已修复
  （converter.py 第 119 行），修复后全量复跑 219 全绿。

覆盖矩阵：页面 A4/页边距/横向保留 3 项；Safe Normal 正文识别排除项
（前置区域/居中段/域/短粗行）与格式命中 4 项；Heading 样式+段落 2 项；
题注样式别名/模式/排除 3 项；regular 表命中 + cover/vMerge/单行跳过 4 项；
完整性 PASS/文本篡改阻断/媒体篡改阻断/四对象幂等 4 项；MCP 返回结构与
字符上限 1 项；grid_tech_v1_4 新能力全部 opt-out 1 项。

### MCP / preset 回归

- `tests/test_mcp_server.py` 随全量执行通过：stdio initialize /
  list_presets / audit / format 双 preset（默认 grid_tech_v1_4 与
  default_technical_document_v1）全部覆盖；
- 进程启动冒烟：`python -m document_factory.mcp_server` 与
  `.venv\Scripts\document-factory-mcp.exe` 启动无 stderr 输出、无 traceback；
- CLI 冒烟：`document-factory normalize ... --rules default_technical...`
  在合成 fixture 上成功生成 docx + md + json 三件套（退出码 1 仅因
  fixture 刻意保留的手工编号 NUM 残留 ERROR，语义与 lint/normalize 一致：
  "执行成功 ≠ 全部规则合格"）；
- conversion/template 回归 68 项全绿（三元组适配后）。

### Failed Cases

最终全量：无失败项。

### Resolution

不适用（最终全绿）。

### VISUAL_RENDER_GATE

**NOT_AVAILABLE**：执行机无 LibreOffice、无 Word COM；按任务书明确禁令
未使用 WPS/任何其他渲染后端替代。分页/孤行/实际字体渲染等视觉项未验证，
作为已知条件性限制如实声明。

## Git Commit

- 任务实现 commit：`TASK_DOC_FULL_NORMALIZATION_001: production-grade page/safe-normal/caption/table normalization with content integrity gate`
- 分支：`master`；推送：`git push origin master`（SSH）
- 任务 commit 哈希：`d0cdc34fa0bcec2d75ed01b5eeeb6fc3d3814105`
  （推送区间 `8ec741c..d0cdc34 master -> master`；推送后
  `HEAD == origin/master == d0cdc34`）
- 回填 commit：`docs: backfill TASK_DOC_FULL_NORMALIZATION_001 commit hash`
  （仅更新本报告的哈希/推送字段）
- 推送后校验：`git rev-parse HEAD` == `git rev-parse origin/master`
- 暂存方式：逐文件显式 `git add`，未使用 `git add -A`；
  reports/ 四川文件与 .trae/ 均不在暂存区。

## 九个交付字段

| 字段 | 值 |
| --- | --- |
| TASK_STATUS | CONDITIONAL（功能/测试/双闸门 PASS；VISUAL_RENDER_GATE NOT_AVAILABLE） |
| TASK_COMMIT | d0cdc34fa0bcec2d75ed01b5eeeb6fc3d3814105 |
| REPORT_PATH | docs/development_reports/TASK_DOC_FULL_NORMALIZATION_001_REPORT.md |
| TEST_RESULT | 219 passed（基线 197 + 新增 22），0 failed |
| FORMAT_EFFECT_GATE | PASS（四类对象目标格式命中，二次执行 0 修改且 SHA-256 一致） |
| CONTENT_INTEGRITY_GATE | PASS（篡改必阻断；仅 document.xml/styles.xml 可变） |
| HEAD | d0cdc34fa0bcec2d75ed01b5eeeb6fc3d3814105 |
| ORIGIN_MASTER | d0cdc34fa0bcec2d75ed01b5eeeb6fc3d3814105 |
| PUSH_STATUS | SUCCESS（8ec741c..d0cdc34 master -> master，HEAD == origin/master） |

> 注：本表为任务代码 commit 的闭环快照。随后的 `docs:` 哈希回填 commit
> 仅修改本报告，推送成功后 `HEAD` 与 `origin/master` 同步前进到该回填
> commit（最终值以任务回报中的 HEAD / ORIGIN_MASTER 字段为准）。

## Remaining Risks

1. **视觉渲染未验证**：无渲染后端，首页分页、keepNext 的实际孤行控制、
   字体槽实际命中需在有 Word/LibreOffice 的环境补验。
2. **pStyle 保留导致的残留 lint**：Safe Normal 正文保留 BODY001 WARNING、
   regular 表单元格保留 TABLE002/TABLE003 ERROR/WARNING——直接格式已生效
   但 lint 要求样式绑定，这是本任务"不做语义重分类"红线的刻意结果，
   报告已逐项透明列出，不能把这些残留解读为格式未生效。
3. **Safe Normal 识别为启发式保守策略**：真实文档中若正文段落含域
   （如内嵌交叉引用）、被居中、或整段加粗，会被排除而维持原状
   （漏判安全、错判被严格限制）；规则模式与阈值集中在 role_classifier，
   后续可按真实样本继续收紧/扩充并补测试。
4. **手工编号标题（NUM001/NUM002）仍是剩余 ERROR 主体**：属结构重排，
   本任务与既有 UNSUPPORTED 声明一致，不自动转多级编号。
5. 题注识别正则只覆盖"章-序"模式（图N-M/表N-M）；其他编号体例
  （图N.M、附图、全文连续编号）不识别，保持原状。
6. MCP 统计载荷受 <10000 字符 JSON 上限约束，只回传精简聚合；
   完整明细以 Validation Report 的 md/json 旁车为准。

## Next Suggestion

1. 在具备 Word/LibreOffice 的环境补 VISUAL_RENDER_GATE（渲染前后分页/
   字体/孤行对比），将本任务的 CONDITIONAL 收口为 PASS。
2. 将"手工编号 → 自动多级编号 + TOC 域刷新"作为需用户显式确认的独立
   结构任务实现（与格式规范化隔离），可消除 NUM001/NUM002/TOC005。
3. 待 lint 支持"直接格式合规"判定后，重新评估 BODY001/TABLE002/TABLE003
   在保留 pStyle 场景下的告警语义（lint 侧调整，不在格式层做 pStyle 改写）。
4. 在真实（非四川、用户授权的）业务样本集上回归 role_classifier 的
   排除阈值，沉淀误判/漏判样本进测试夹具。
