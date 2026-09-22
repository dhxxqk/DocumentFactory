# TASK_DOC_TRAE_001：DocumentFactory 项目接管与基线审计报告

- 实际生成时间（含时区）：2026-09-22T20:24:59+08:00
- 执行者：Trae
- 审计起始基线：`893a4694e849312b91b3485c3060c12c3d8bd57e`
- 任务性质：只检查、不修改（除本报告外无代码变更）

## 1. RESULT

**PASS**

判定依据：

- Git：`origin` 为 SSH（`git@github.com:dhxxqk/DocumentFactory.git`），`HEAD == origin/master`，working tree clean。
- pytest：**80 passed**，与 TASK_DOC_004 基线完全一致，0 failed / 0 skipped。
- 版本：CLI、包版本、MCP Server 均为 `0.4.0a1`。
- CLI：`lint` / `normalize` / `template analyze` / `template apply` 全部按预期工作。
- MCP：真实子进程协议测试通过，且精确只暴露 3 个工具。
- Template Engine：模板/目标文件不变，文本、段落数量与顺序完全保持，编号 XML 字节级不变，输出可重新读取。
- 未发现 P0 阻塞性 BUG。

延续性限制（非本次新增、不影响 PASS）：本机无 LibreOffice / Microsoft Word 渲染后端，视觉渲染（PDF/PNG）仍为自 TASK_DOC_001 起的环境性条件项；本任务范围内的所有验证均不依赖渲染。

## 2. 当前 Git 状态

| 项目 | 实际值 |
|---|---|
| 分支 | `master` |
| 远端 | `origin  git@github.com:dhxxqk/DocumentFactory.git (fetch/push)` |
| HEAD | `893a4694e849312b91b3485c3060c12c3d8bd57e` |
| origin/master | `893a4694e849312b91b3485c3060c12c3d8bd57e` |
| HEAD == origin/master | 是 |
| working tree | clean |

最近提交：

```text
893a469 feat: add template engine foundation
04fa098 fix: complete DSH end to end document workflow
b491e4b docs: finalize DSH E2E closure report
7f052c3 Merge remote-tracking branch 'origin/master'
64dc109 fix: complete DSH end to end document workflow
986c7ea docs: add DocumentFactory product design direction
f8cdf7e docs: record TASK_DOC_003 validation and push
c1293d7 feat: add DocumentFactory MCP integration for DSH
b919b94 docs: add TASK_DOC_003 DSH MCP integration task
8e17042 docs: record TASK_DOC_002 push failure
```

未执行 reset --hard、force push、rebase、amend 等任何危险操作。

## 3. 环境与版本

| 项目 | 实际值 |
|---|---|
| 操作系统 | Windows（Windows-11） |
| 系统 Python | 3.10.11（满足 `requires-python >=3.10`） |
| 项目虚拟环境 Python | `.venv` → 3.12.14 |
| document-factory 包版本 | `0.4.0a1` |
| 关键依赖 | lxml 6.x、PyYAML 6.x、PyMuPDF 1.x、mcp 2.x、pytest 9.x（TASK_DOC_001 记录：lxml 6.1.3 / PyYAML 6.0.3 / PyMuPDF 1.28.2） |

虚拟环境确实存在且为正式交付环境，后续所有验证均使用 `.venv` 与 `-X utf8`。

## 4. 完整测试结果

命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

结果：

```text
........................................................................ [ 90%]
........                                                                 [100%]
80 passed in 5.08s
```

- 80 passed，0 failed / 0 error / 0 skipped，与 TASK_DOC_004 基线逐项一致。
- 未删除、跳过任何测试，未修改 severity 或预期结果。
- MCP 测试单独复跑（`tests/test_mcp_server.py`）：2 passed，使用官方 `mcp.Client` + `StdioServerParameters` 启动真实子进程（`python -m document_factory.mcp_server`），非 mock。

## 5. CLI 验证

入口：`.venv\Scripts\document-factory.exe`（= `document_factory.cli:main`）。

| 命令 | 结果 | 退出码 | 说明 |
|---|---|---:|---|
| `--version` | `0.4.0a1` | 0 | 版本正确 |
| `lint <样本> --rules ... --report ...` | `RESULT=FAIL ERROR=42 WARNING=20 INFO=4204` | 1 | 样本本身有 ERROR，退出码 1 符合契约；只读 |
| `normalize <样本> --output output\trae_verify\... --report ...` | `STATUS=FAIL BEFORE=42 AFTER=3 CHANGED=6` | 1 | 42→3 与历史一致；退出码 1 表示仍有 3 个 NUM002，符合契约 |
| `template analyze template_demo.docx --output ...` | `STATUS=PASS STYLES=7 TABLE_STYYLES=1` | 0 | Profile 正常生成 |
| `template apply --template ... --input ... --output ... --report ...` | `STATUS=PASS MAPPINGS=5 CHANGED=70` | 0 | 迁移链路正常 |

所有破坏性可能的操作均输出到隔离目录（`output/trae_verify/`、临时报告），未触碰生产样本与既有产物；验证后临时报告已删除。退出码语义（0/1/2/3）与 README 描述一致。

## 6. MCP 验证

- 模块可正常导入并实例化：server name `documentfactory`，version `0.4.0a1`。
- 通过异步 `list_tools()` 实际枚举，精确为：

```text
['list_presets', 'audit_document', 'format_document']
```

- 真实 stdio 子进程协议测试通过（initialize → tools/list → 三工具调用 → 错误传播）。
- 工具实现均为薄适配：
  - `format_document` → 直接调用 Core `normalize(...)`；
  - `audit_document` → 直接调用 `lint(...)` + `write_report(...)`；
  - `list_presets` → 从显式 `PRESETS` registry 读取（当前仅 `grid_tech_v1_4`）。
- MCP 层不含 OOXML、StyleResolver、lint 规则的任何副本，不提供 shell/XML 入口。
- 未新增任何 MCP 工具；模板能力未提前暴露，与 README「下一阶段边界」一致。
- Server instructions 明确要求：不得绕过工具修改 DOCX、完成后必须 `present`、after 有 ERROR 不得宣称合格。

**结论：MCP 仍是健康的薄层。**

## 7. Template Engine 验证

Demo：`testcases/template/template_demo.docx` + `testcases/template/target_demo.docx`。

通过独立只读脚本对一次全新 analyze+apply 的结果做深度校验：

| 校验项 | 结果 |
|---|---|
| 原模板 SHA-256 不变 | PASS |
| 原目标 SHA-256 不变 | PASS |
| 输出可被 `read_docx` 重新读取 | PASS（11 段落） |
| 文本内容完全一致（逐段落 (part, text) 序列比对） | PASS |
| 段落数量 | 目标 11 → 输出 11 |
| 段落顺序 | 完全一致 |
| ZIP 部件集合 | 完全一致 |
| 实际发生变化的部件 | 仅 `word/document.xml`、`word/styles.xml` |
| 编号 XML（word/numbering.xml） | 字节级不变（该 Demo 含编号部件时同样校验） |
| Apply 结果 | `status=PASS`，mappings=5，changes=70，profile mismatches=0 |

安全机制在源码中同样成立：写入前后两次校验输入/模板哈希；先 `read_docx(output)` 再 lint，残缺 ZIP 不可能被报为成功；未修改的 ZIP 部件逐项原样复制。

## 8. 当前架构图

基于源码实际 import 关系绘制（无循环依赖）：

```text
                      入口层（Entry）
  ┌───────────────────────────────┐   ┌──────────────────────────────────┐
  │ CLI (cli.py / __main__.py)    │   │ MCP stdio (mcp_server.py)       │
  │ lint/render/audit/normalize/  │   │ 仅 3 tools：                    │
  │ template analyze|apply        │   │ format/audit/list_presets（薄层）│
  └───────────────┬───────────────┘   └───────────────┬──────────────────┘
                  │                                    │
                  ▼                                    ▼
                          Core（确定性，无 LLM）
  ┌─────────────────────────────────────────────────────────────────────┐
  │ docx_reader.read_docx                                               │
  │   ZIP/OOXML 只读；尺寸/重复部件/DTD 限制；Strict 命名空间归一        │
  │      │                                                              │
  │      ▼                                                              │
  │ models: Document / Paragraph / Run / Style / Table / Field /        │
  │         NormalizationResult / TemplateApplyResult                   │
  │      │                                                              │
  │      ▼                                                              │
  │ StyleResolver: docDefaults → basedOn 链 → 段落/Run 直接格式          │
  │   per-script 字体（cn/ascii/latin/cs）+ 主题字体/语言回退 + 来源追踪 │
  │      │                                                              │
  │      ├── numbering_analyzer / toc_analyzer /                        │
  │      │   section_analyzer / table_analyzer                          │
  │      ▼                                                              │
  │ lint_engine: load_rules(YAML，校验规范主源存在) → LintContext        │
  │      │                                                              │
  │      ▼                                                              │
  │ normalizer.normalize:                                               │
  │   lint before → 样式/段落/Run 级确定性修改 (_apply_normalization)   │
  │   → 临时 ZIP + os.replace 原子落盘 (_write_package)                 │
  │   → read_docx(输出) → lint after → MD+JSON Validation Report        │
  └─────────────────────────────────────────────────────────────────────┘
                  ▲（单向复用，normalizer 不依赖 template）
  ┌───────────────┴─────────────────────────────────────────────────────┐
  │ template/                                                           │
  │   analyzer.analyze_template → extractor.extract_template_data       │
  │      → profile.TemplateProfile (schema 1.0, JSON, 可人工编辑)       │
  │   applier.apply_template: 复用 normalizer 写入原语                  │
  │      (_write_package / apply_format_profile / _atomic_text)         │
  │      → Profile 精确验证 + 现有 lint → Template Apply Report         │
  └─────────────────────────────────────────────────────────────────────┘

  旁路：renderer.py（LibreOffice → Word COM 探测，私有副本，PDF→PNG）
        report_writer.py（lint/audit 的中文 MD + JSON 报告）
        output_paths.py（output/、reports/ 路径边界与输入覆盖保护）
```

架构审计结论：

- **依赖方向合理**：`models`/`docx_reader` 为最底层；`style_resolver` 只依赖 reader；`lint_engine` 依赖 reader/resolver/各 analyzer；`normalizer` 依赖 lint；`template` 单向依赖 normalizer/lint/reader。无循环依赖。
- **审计与修复分离、修复后必验证、不覆盖输入**三项 ADR 原则在代码中真实落地，而非口号。
- 发现的主要结构性瑕疵（详见技术债务）：角色判定逻辑在规则模式与模板模式中各写一份；模板层调用了 normalizer 的多个下划线私有函数，存在内部契约耦合。

## 9. 技术债务

不制造虚假债务，以下均有源码或运行证据。

### P0（阻塞 / 安全）

- **无 P0 问题。** OOXML 安全基座经审计是扎实的：
  - XML 解析 `resolve_entities=False`、`no_network=True`、`load_dtd=False`，含 doctype 直接拒绝（防 XXE / 外部实体）；
  - 包级限制 128 MiB / 10000 部件、重复 ZIP 部件名检测；
  - ZIP 条目从不落盘解压（无 zip-slip），宏/关系目标/外部导入不执行；
  - 输入哈希在操作前后多次校验，输出先重读再 lint。

### P1（应在深化 Migration 前处理）

1. **角色判定逻辑重复、存在分叉风险**。同一「这段是不是 Heading/正文/表格」的判定分散在：[lint_engine.py](file:///G:/Workflows/DocumentFactory/src/document_factory/lint_engine.py#L88-L133)（analyze_styles_and_body / analyze_runs）、[normalizer.py](file:///G:/Workflows/DocumentFactory/src/document_factory/_target_for_paragraph.py#L265-L280)（_target_for_paragraph）、[extractor.py](file:///G:/Workflows/DocumentFactory/src/document_factory/template/extractor.py#L80-L94)（extract_roles）；heading 名称正则在 StyleResolver.heading_level 与 extract_roles 中各写一份。当前结果一致，但任何一处规则演进都可能让 lint 与修复/迁移的语义悄悄分叉。
2. **模板层对 normalizer 内部实现的耦合**。[applier.py](file:///G:/Workflows/DocumentFactory/src/document_factory/template/applier.py#L11-L24) 导入 `_atomic_text`、`_style_element`、`_write_package` 等私有函数，并通过伪造的 `TEMPLATE_RULES = {"rules": {"TEMPLATE": {"source": ...}}}` 来满足 normalizer `_record` 对 `rules["rules"][rule_id]["source"]` 的要求。能工作，但 normalizer 内部重构会无声破坏模板层；建议未来抽出正式的「写入原语 + 变更记录器」公共接口。
3. **渲染/视觉验证缺失（环境性）**。本机无 LibreOffice/Word，自 v0.1 起无法产出真实 PDF/PNG，结构 PASS 与视觉合格之间的验证缺口一直存在。扩展页面/页眉页脚迁移前应先补齐渲染后端，否则无法对新迁移的页面属性做视觉复核。

### P2（演进性 / 整洁度）

4. **Template Profile 版本兼容策略尚未建立**：[profile.py](file:///G:/Workflows/DocumentFactory/src/document_factory/template/profile.py#L54-L55) 硬编码只接受 `1.0`，无向前/向后迁移路径；`load` 对固定字段集之外的键静默丢弃（人工新增字段在 load→save 往返后消失）；除 styles/roles 外缺少字段级类型校验，手写坏 Profile 可能在更晚阶段才报错。
5. **格式迁移边界仍窄**：页面、页眉页脚、表格边框、编号已进入 Profile 但 Apply 不落地；表格默认格式仅取模板「第一张表」的第 1 行 / 其余行，条件表格样式（tblStylePr）不合并；目标缺少某角色样式时不会创建/导入样式（这是与 WPS 样式集重叠、尚不能称为迁移引擎的根因）。
6. **报告体系三套并存**：`report_writer.write_report`、`normalizer._write_validation_report`、`template _write_report`，`_escape` 在 normalizer 与 applier 中重复实现；风格一致但有维护重复。
7. **路径/可移植性**：Profile 记录绝对 `source_path`，跨机器不可移植（仅元数据）；Python API 以 `Path.cwd()` 为根，要求调用方 cwd=仓库根（MCP 用 `PROJECT_ROOT` 规避），需在 Agent 接入时持续保持该契约。
8. **测试覆盖缝隙**：渲染相关路径只在模拟后端下验证；模板只有一对 Demo，缺少多种真实来源（尤其 WPS 产出）DOCX、复杂合并单元格 + 迁移组合、畸形/超大 DOCX 的模糊与边界测试。

## 10. 产品能力边界

### 已经真实可用

- **只读结构审计**：对真实 DOCX 输出带 Rule ID / 严重等级 / 定位 / 实际预期值 / 规范出处的完整证据链（实测 42 ERROR / 20 WARNING），中文 MD + 完整 JSON。
- **规则驱动的确定性规范化闭环**：lint before → normalize → lint after → Validation Report；对「已经使用规范样式体系」的文档，可确定修复字体（含主题字体冲突）、字号、颜色、缩进、行距、段距、对齐；实测 42→3，二次执行幂等，输入永不被覆盖。
- **Agent 可用的薄 MCP**：DSH 真实 E2E 已 PASS（自然语言 → 自主发现工具 → format_document → present 交付）。
- **模板最小迁移**：当模板与目标都具备同名内置角色（Normal/Title/Heading1-3）时，可迁移这些样式定义及表格首行/表体的字体、字号、对齐，并逐项验证。

### 已经有基础但能力不足

- **模板模式**：Profile 已捕获页面、页眉页脚、编号、表格样式等事实，但 Apply 只落地段落样式 + 基础表格格式；目标样式体系不规范或缺角色时无法创建/导入样式。
- **编号体系**：读取、校验与「保持不变」非常可靠，但不能修复（样本 3 个 NUM002 因此保留），也不能跨文档迁移。
- **语义角色识别**：真实 Heading/正文/表格样式识别可靠，疑似标题/正文只给 WARNING；不具备对「未规范使用样式」的真实文档做结构推断的能力。
- **验证体系**：结构验证真实可信，但视觉验证受无渲染后端所限无法闭环。

### 尚未实现

- 「拿去年文档作为模板，把今年文档改成它的格式」——**当前不能完整做到**。
- 具体还缺的能力层（自底向上）：
  1. **样式导入/创建**：目标缺少模板角色样式时，从模板包导入样式定义而不是跳过；
  2. **页面设置 / 页眉页脚迁移**：Profile 已有数据，Apply 未执行；
  3. **编号体系迁移**：numbering.xml + 样式绑定的跨文档映射；
  4. **表格样式/边框/条件格式完整迁移**；
  5. **Document Structure Mapping**：脱离内置样式名，按语义（章、节、正文、图表题、封面）识别与映射任意文档；
  6. **Template Library 与模板选择**：「去年德阳项目建议书」的检索与匹配；
  7. **迁移后视觉验证**：渲染逐页核对。
- 此外未实现：TOC 自动修复、章节增删/重排、文字改写、图片布局迁移、GUI、WorkBuddy、任何 LLM/云调用。

## 11. WPS 样式集差异分析

WPS「样式集」本质：在 GUI 中把一组命名字符/段落样式（标题、正文的字体字号间距）批量套用到当前文档。

**与 WPS 样式集重叠（必须承认）的部分：**

- 当前 Template Apply 所做的「把目标 Heading/Title/Normal 样式的字体、字号、粗斜体、对齐、行距改成模板样式定义」，在效果上与人工使用 WPS 样式集高度重叠；
- 规则模式中对标题/正文/表格的字体字号统一，也与 WPS 手动排版效果重叠。

若 DocumentFactory 长期停留在这一层，它只是「不可视、需命令行、对环境要求更高」的劣化版样式集——这正是任务书警示的退化方向。

**DocumentFactory 应形成的差异化能力：**

1. **验证而非仅套用**：修复前/后基于正式规范的 lint + 机器可读 Validation Report，证明「是否真的合规、还差什么」；WPS 套样式不提供合规判定与证据。
2. **Agent 工作流内的确定性、可批量执行**：MCP 契约、输入保护、原子落盘、幂等，可被 AI 自主串联；WPS 是人工 GUI 操作。
3. **全包迁移（Document Migration Engine）**：样式 + 页面 + 页眉页脚 + 编号 + 表格作为整体跨文档迁移，并在缺失样式时创建/导入——WPS 样式集不跨文档、不建样式、不迁移编号与版式。
4. **Document Structure Mapping**：把「样式体系完全不同」的两份文档按语义角色对应（含非规范文档的结构推断），这是样式集概念里根本不存在的层。
5. **Template Library + Agent 选模板**：按文档类型/历史项目检索模板并自动应用。

结论：差异化护城河 = **规范驱动验证 + 跨文档结构/格式迁移 + Agent 自动化**，而非「自动套样式」。

## 12. 下一阶段开发路线（仅建议，不在本任务开发）

建议顺序总体为：**先补「迁移深度」与验证手段，再做结构映射，最后才开放模板 MCP / WorkBuddy**。不建议在 Core 迁移仍与 WPS 样式集同质时过早铺入口。

### 任务 1（建议最先做）：Template Apply 深化 —— 样式导入 + 页面/页眉页脚迁移

- 目标：目标缺少角色样式时从模板包导入样式定义并建立映射；将 Profile 已捕获的页面设置、页眉页脚落地到输出。
- 为什么现在做：这是跳出「样式集同质」的最小关键一步，且数据已在 Profile 中，无需先改 schema；能立刻回答「能不能像去年文档」中的版式部分。
- 前置条件：渲染环境就绪（见任务 2），否则无法视觉复核页面/页眉迁移；保持输入保护与部件字节复制机制。
- 风险：样式导入涉及 styleId 冲突、关系部件（numbering/theme 引用）牵连，可能引入部件间不一致；必须以「输出可重读 + 现有 lint + Profile 校验 + 渲染核对」四重验收。
- 验收：真实跨样式体系文档（目标缺 Heading 样式）迁移后，角色齐全、页面/页眉与模板一致、文本与段落顺序不变、编号 XML 不被误写、报告如实列出无法迁移项。

### 任务 2（并行/先行基础设施）：渲染与视觉验证环境补齐

- 目标：安装并接通 LibreOffice（或 Word）后端，产出真实 PDF/逐页 PNG，建立迁移前后视觉核对流程，关闭自 v0.1 的条件项。
- 为什么现在做：任务 1/3 都改版面，没有视觉反馈就无法保证正确性。
- 前置条件：本机软件安装；保持 WPS 兼容注册不被误判为 Word 后端的既有逻辑。
- 风险：低；主要是环境与 DPI/字体替换差异。
- 验收：正式样本可输出真实 PDF + PNG，audit 不再返回 RENDER_UNAVAILABLE。

### 任务 3：编号体系迁移

- 目标：把模板编号定义（abstractNum/num/样式绑定）确定性映射进目标，处理 numId 重映射与 pStyle 关联；含当前遗留的 NUM002 类问题的「可验证修复」路径。
- 为什么现在做：编号是中文正式文档最易坏、最体现迁移价值的部分，但复杂度高，适合在样式/页面迁移稳定后进行。
- 前置条件：任务 1 的样式导入；严格的编号 XML 保持/变更测试。
- 风险：高（lvlOverride、numStyleLink、多级关联易错，可能静默改变章节编号）。
- 验收：迁移后多级编号与模板一致、可重新读取、现有 NUM 规则 lint 通过；无法确定时保留原状并报告。

### 任务 4：Document Structure Mapping 基础

- 目标：建立独立于内置样式名的语义结构模型（章/节/正文/图表题/封面等），对非规范文档做置信度分级的结构推断，低置信对象只标记不自动改。
- 为什么现在做：这是 Migration Engine 的战略核心，也是「样式体系完全不同的两年文档」能够对应起来的前提；同时可顺手收敛 P1 的角色判定重复问题。
- 前置条件：Core 写入原语与变更记录器从 normalizer 抽成公共接口（消解 TEMPLATE_RULES 式 hack）。
- 风险：推断误判会导致错误迁移；必须置信度门控 + 人工复核通道，且坚持「AI/推断不确定就不动」。
- 验收：在「无规范样式」的真实文档上，结构识别以 WARNING/候选形式给出且不破坏内容；高置信映射经 lint/渲染验证正确。

### 任务 5：Template Library + 薄 Template MCP

- 目标：可版本管理的模板库与检索注册；在 Core 模板迁移经视觉验证可信后，新增薄适配的 `analyze_template` / `apply_template` MCP 工具（复用 Core，不写业务逻辑）。
- 为什么现在做：模板库与 Agent 入口是放大器，必须放在迁移与验证能力可信之后，否则放大的是不可靠结果。
- 前置条件：任务 1/3/4 完成；MCP 继续保持薄层与 present 交付契约。
- 风险：MCP 工具膨胀、把业务逻辑上移到适配层；需以「薄层」红线和协议测试约束。
- 验收：Agent 可经 MCP 完成「选模板→迁移→验证→present」全链路，返回结果与 CLI/Python 完全一致。

**WorkBuddy 排在最后**：它是入口/体验层，价值依赖完整的迁移 + 验证 + 模板库；在 Template MCP 与 Structure Mapping 成熟前接入只会重复 DSH 已验证过的接入工作。

### 是否应进入 Document Migration Engine

**应该，但以「加深迁移 + 补齐验证」的方式进入，而不是另起炉灶。** 当前 Reader/Resolver/Lint/Normalizer/原子写入/Profile 的分层就是 Migration Engine 的正确底座；禁止事项中的边界（不做样式集、不让 AI 改 OOXML、修复必验证）应继续保留。

## 13. 是否建议立即进入下一个功能任务

**是，建议进入「任务 1：Template Apply 深化（样式导入 + 页面/页眉页脚迁移）」，并以「任务 2 渲染环境补齐」为并行前置。**

理由：它以最小跨度把产品从与 WPS 样式集重叠的区域推向真正的跨文档迁移，数据基础（Profile 1.0）已具备；但开工前应先确保渲染后端可用，并在任务书中明确：不改 Profile schema 字段契约、不碰编号自动迁移（编号留给任务 3）、继续保护输入与未修改部件。

---

## 附：本任务变更范围

- 仓库内仅新增本文件 `reports/TASK_DOC_TRAE_001_REPORT.md`。
- 验证过程产生的临时报告已全部删除；输出在 `output/trae_verify/`（gitignore），不纳入 Git。
- 无代码修改、无 GUI/MCP 工具/模型调用新增，未做编号或 TOC 修改。
