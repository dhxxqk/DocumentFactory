# TASK Report

Task: TASK_DOC_MCP_DEFAULT_PRESET_001 — DocumentFactory 默认技术文档规范 MCP 注册修复

Date: 2026-10-02 13:48 (+08:00)

Agent: Trae Agent

> 报告路径说明：`docs/agent/REPORTING_STANDARD.md` 常规要求新任务报告放
> `docs/development_reports/`；本任务任务书第 18 节显式指定路径
> `reports/TASK_DOC_MCP_DEFAULT_PRESET_001_REPORT.md`。按 CORE_RULES 第 4 节
> “任务书显式约束优先”的顺序，采用任务书指定路径，并在此登记该差异。

## Summary

将仓库中已存在的默认技术文档规范（正式 ID：`DEFAULT_TECHNICAL_DOCUMENT_V1`，
规则文件 `rules/default_technical_document_v1.yaml`）以**路径注册**方式接入
DocumentFactory MCP preset registry，使 `list_presets()`、
`audit_document(..., preset=...)`、`format_document(..., preset=...)`
均可显式调用该规范。

- 未在 `mcp_server.py` 中硬编码任何格式规则副本；MCP 仅持有规则文件路径，
  规则加载、校验与消费仍走 `lint_engine.load_rules` / `normalize` Core。
- 未改变全局默认 preset：`list_presets()` 的 `default` 仍为 `grid_tech_v1_4`，
  `audit_document` / `format_document` 的默认参数未改（`CHANGE_GLOBAL_MCP_DEFAULT = NO`）。
- 未修改两份规则文件、normalizer、lint 算法、模板与任何四川项目文件
  （`SICHUAN_REPORT_FORMATTING_STARTED = NO`，`SICHUAN_REPORT_CHANGED = NO`）。
- RESULT: **PASS**。判定依据：全量 197 项测试通过（含新增 5 项），MCP 两种启动方式
  initialize 握手成功，probe 实际调用三个工具成功，输入文件 SHA-256 前后一致。

## Changed Files

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/document_factory/mcp_server.py` | 修改 | `PRESETS` 新增 `default_technical_document_v1` 一项（id / display_name / rules_path / description），插在 `grid_tech_v1_4` 之前；其余逻辑零改动 |
| `tests/test_mcp_server.py` | 修改 | 新增 5 个测试场景；更新原有序列表断言以反映两个 preset（非弱化断言，见下） |
| `README.md` | 修改 | MCP 工具表 `list_presets` 一行同步为两个 preset，并注明默认仍为 `grid_tech_v1_4` |
| `reports/TASK_DOC_MCP_DEFAULT_PRESET_001_REPORT.md` | 新增 | 本报告 |

关于既有断言的更新（非绕过失败）：原
`test_official_client_stdio_initialize_list_and_real_calls` 断言
`presets == ["grid_tech_v1_4"]`，本任务验收 Gate 要求两个 preset 均可见，
因此将期望更新为 `["default_technical_document_v1", "grid_tech_v1_4"]`
（与 `PRESETS` 插入顺序一致）；同测试中 `default == "grid_tech_v1_4"` 断言保留未动。

未改动：`rules/default_technical_document_v1.yaml`、`rules/grid_tech_v1_4.yaml`、
`templates/default_technical_document_v1/**`、`normalizer.py`、`lint_engine.py`。
`git diff -- rules/` 为空。

## 注册内容与实际 rules_path

```python
"default_technical_document_v1": {
    "id": "default_technical_document_v1",
    "display_name": "DocumentFactory 默认技术文档规范 V1",
    "rules_path": PROJECT_ROOT / "rules" / "default_technical_document_v1.yaml",
    "description": "与业务无关的默认技术文档规范（正式 ID：DEFAULT_TECHNICAL_DOCUMENT_V1）……",
}
```

- MCP 调用 ID（小写稳定 ID）：`default_technical_document_v1`
- 规范正式 ID（模板内，未修改）：`DEFAULT_TECHNICAL_DOCUMENT_V1`
- 实际加载文件（绝对路径）：`E:\Project\DocumentFactory\rules\default_technical_document_v1.yaml`
- `load_rules` 解析的规范主源（`source` 字段）：
  `templates/default_technical_document_v1/definition/style_definition.yaml`（存在性校验通过）

## list_presets 实际返回结果

进程内直接调用 `list_presets()`（2026-10-02 实际执行）：

```json
{
  "presets": [
    {
      "id": "default_technical_document_v1",
      "display_name": "DocumentFactory 默认技术文档规范 V1",
      "rules_file": "E:\\Project\\DocumentFactory\\rules\\default_technical_document_v1.yaml",
      "spec_version": "V1",
      "description": "与业务无关的默认技术文档规范（正式 ID：DEFAULT_TECHNICAL_DOCUMENT_V1）：A4 纵向、仿宋正文、黑体多级标题、10.5pt 表格；确定性检查并规范化，不含任何项目身份信息，不自动修复编号或 TOC。"
    },
    {
      "id": "grid_tech_v1_4",
      "display_name": "电网科技项目实施方案 V1.4",
      "rules_file": "E:\\Project\\DocumentFactory\\rules\\grid_tech_v1_4.yaml",
      "spec_version": "V1.4",
      "description": "确定性检查并规范化已确认的 Heading、正文和表格样式；不自动修复编号或 TOC。"
    }
  ],
  "default": "grid_tech_v1_4"
}
```

`DEFAULT_PRESET_VISIBLE = YES`，`DEFAULT_PRESET_RULE_FILE_EXISTS = YES`，
五个必需字段 `id / display_name / rules_file / spec_version / description` 齐全。

## 默认规范真实性校验（RULE_SOURCE_MATCH = YES）

`test_default_preset_can_be_loaded` 通过 `load_rules(PRESETS[...]["rules_path"])`
加载并断言以下代表性事实，值全部来自
`rules/default_technical_document_v1.yaml`，MCP 层无第二套规则：

| 维度 | 任务书期望 | 实际加载值 |
|---|---|---|
| 页面 | A4 portrait | `page_size=A4`，`orientation=portrait` |
| 页边距 cm | 上2.8 / 下2.6 / 左2.8 / 右2.6 | `{top: 2.8, bottom: 2.6, left: 2.8, right: 2.6}` |
| 正文 | 仿宋 / 12pt / Times New Roman / 1.5 倍行距 / 首行缩进 2 字符 / 两端对齐 | `chinese_font=仿宋`，`font_size_pt=12`，`latin_font=Times New Roman`，`line_spacing=1.5`，`first_line_indent_chars=2`，`alignment=both` |
| Heading 1 | 黑体 16pt | `黑体 / 16` |
| Heading 2 | 黑体 14pt | `黑体 / 14` |
| Heading 3 | 黑体 12pt | `黑体 / 12` |
| 表格 | 10.5pt，表头黑体，正文仿宋 | `font_size_pt=10.5`，`header_font=黑体`，`body_font=仿宋`（另含 `latin_font=Times New Roman`） |

同时断言 `rules["_path"]` 与注册路径 resolve 后完全相等，证明加载的就是
`rules/default_technical_document_v1.yaml`，而非同名副本。

## audit_document 测试结果

- 单元/集成测试 `test_audit_document_accepts_default_preset`（stdio 官方 MCP Client）：**PASS**
  - `preset == "default_technical_document_v1"`，无“未知 preset”错误
  - `source_unchanged is True`，审计报告 `.md` 落盘，进程结束后输入 SHA-256 不变
  - 报告元数据含 `- 规范版本：V1`，证明实际消费默认规则文件
- probe 实际调用（最小 fixture，临时文件，产物已清理）：
  `status=FAIL` 是 fixture 文档自身缺 TOC/编号导致的**文档合规结论**
  （`ERROR=2, WARNING=0, INFO=32`），工具执行本身完整成功，
  `source_unchanged=true`，报告已生成。

`UNKNOWN_PRESET_ERROR = NO`，`AUDIT_EXECUTION_COMPLETE = YES`，
`SOURCE_UNCHANGED = YES`，`AUDIT_REPORT_CREATED = YES`。

## format_document 测试结果

- 测试 `test_format_document_accepts_default_preset`（stdio 官方 MCP Client）：**PASS**
  - 调用现有 `normalize(...)` Core：格式化 DOCX 与 Validation Report（`.md`）均落盘，
    输出可被 `read_docx` 重新解析
  - 报告文本包含 `default_technical_document_v1.yaml`（Validation Report “规则文件”行），
    证明 Core 实际使用默认规则
  - `source_unchanged is True`，进程结束后输入 SHA-256 不变
- probe 实际调用：`before ERROR=2 → after ERROR=2`，`changed_count=0`
  （该 fixture 仅缺 TOC/编号等明确不自动修复项，属预期），
  `FORMATTED_DOCX_CREATED = YES`，`VALIDATION_REPORT_CREATED = YES`，probe 产物已全部删除。

`FORMAT_EXECUTION_COMPLETE = YES`，`FORMATTED_DOCX_CREATED = YES`，
`VALIDATION_REPORT_CREATED = YES`，`SOURCE_UNCHANGED = YES`。

未使用任何四川正式报告作为测试样本；测试样本全部来自现有
`make_docx` fixture 体系（`tests/conftest.py`）。

## 向后兼容性（grid_tech_v1_4）

- `test_existing_grid_tech_preset_still_available`：显式
  `preset="grid_tech_v1_4"` 的 audit + format 均 **PASS**，报告含 `grid_tech_v1_4.yaml`。
- 既有 `test_official_client_stdio_reports_input_and_core_errors`（含未知 preset 报错路径）**PASS**。
- `GRID_TECH_V1_4_STILL_AVAILABLE = YES`，`GRID_TECH_RULE_CONTENT_CHANGED = NO`。

## MCP 实际启动验证

向两种入口发送标准 JSON-RPC `initialize`（cwd=工程根，2026-10-02 实际执行）：

| 入口 | 结果 |
|---|---|
| `python -X utf8 -m document_factory.mcp_server` | exit 0，返回 `serverInfo: documentfactory 0.5.0a1` |
| `.venv\Scripts\document-factory-mcp.exe` | exit 0，返回 `serverInfo: documentfactory 0.5.0a1` |

新增 preset 在 Server 初始化期间加载无异常（`list_presets` 的 `load_rules`
在 stdio 集成测试中已被真实执行）。`MCP_STARTUP_GATE = PASS`。

## Test Result

Test Command:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Result:

```text
197 passed in 23.66s
```

- 变更前 HEAD（`3ebcc1e`）实测收集基线：**192 tests collected**（stash 后 `pytest --co` 实测）。
- 本次新增 5 个测试：192 + 5 = 197，全部通过，无 skip、无 xfail、无降低断言。
- 与 `docs/development_reports/TASK_DOC_013_REPORT.md` 记载的 180 基线差异：
  TASK_DOC_013 之后的既有提交已使 HEAD 基线增至 192（本任务开始前的仓库事实），非本任务引入。
- 单独运行 `tests/test_mcp_server.py -v`：7 passed in 8.71s（2 既有 + 5 新增）。

Failed Cases:

None

Resolution:

Not applicable

## 验收 Gate 自检

| Gate | 结果 | 证据 |
|---|---|---|
| SCOPE_GATE | PASS | 仅改 MCP 注册层、对应测试与一行 README；规则/Core/四川文件未动 |
| DEFAULT_PRESET_REGISTRATION_GATE | PASS | `PRESETS["default_technical_document_v1"]` |
| RULE_PATH_GATE | PASS | 指向 `rules/default_technical_document_v1.yaml`，文件存在且为主源 |
| LIST_PRESETS_GATE | PASS | 返回两个 preset 及五个必需字段 |
| AUDIT_TOOL_GATE | PASS | `test_audit_document_accepts_default_preset` |
| FORMAT_TOOL_GATE | PASS | `test_format_document_accepts_default_preset` |
| BACKWARD_COMPATIBILITY_GATE | PASS | `test_existing_grid_tech_preset_still_available` 等 |
| MCP_STARTUP_GATE | PASS | module 与 console-script initialize 握手成功 |
| TEST_GATE | PASS | 197 passed，无失败/skip/删改 |
| SOURCE_RULE_UNCHANGED_GATE | PASS | `git diff -- rules/` 为空 |
| GIT_DIFF_GATE | PASS | 仅 3 个跟踪文件修改 + 本报告新增；`.trae/` 未跟踪不提交 |

## Git Commit

- 分支：`master`
- 提交信息：`TASK_DOC_MCP_DEFAULT_PRESET_001: register default technical document preset in MCP`
- 提交哈希：提交后回填（见后续 `docs: backfill ...` 提交）
- 推送：提交后回填（SSH `git@github.com:dhxxqk/DocumentFactory.git`）

## Remaining Risks

- 全局默认 preset 仍为 `grid_tech_v1_4`（本任务刻意不改）；下一阶段四川报告任务必须显式传
  `preset="default_technical_document_v1"`，否则仍会走电网规范。
- probe 中 fixture 文档 `status=FAIL`（缺 TOC/自动编号）是 DocumentFactory 既定
  “不自动创建/刷新 TOC 与编号”边界，非本任务缺陷；真实业务文档的格式效果需在
  四川报告任务中以正式样本另行验证。
- 未发现新增 preset 无法工作的现存 Bug；无额外 Bug 需要登记。

## Next Suggestion

- 四川中长期项目报告格式化任务可直接显式传入
  `preset="default_technical_document_v1"` 调用 audit/format（本任务结束状态：
  `READY_FOR_SICHUAN_REPORT_FORMAT_TASK = YES`，但本任务未启动该任务）。
- 未来如需统一 Template Registry 与 MCP Registry，单独开任务处理；
  本任务按要求未做 registry 重构或自动发现改造
  （`REGISTRY_REFACTOR = FORBIDDEN`，`AUTO_DISCOVERY_REFACTOR = FORBIDDEN`）。

## 最终状态

```ini
DEFAULT_TECHNICAL_DOCUMENT_SPEC_EXISTS = YES
DEFAULT_PRESET_ID = default_technical_document_v1
DEFAULT_PRESET_REGISTERED_IN_MCP = YES
DEFAULT_PRESET_VISIBLE_IN_LIST_PRESETS = YES
DEFAULT_RULE_FILE = rules/default_technical_document_v1.yaml
AUDIT_WITH_DEFAULT_PRESET = PASS
FORMAT_WITH_DEFAULT_PRESET = PASS
GRID_TECH_V1_4_STILL_AVAILABLE = YES
DEFAULT_RULE_CONTENT_CHANGED = NO
GRID_TECH_RULE_CONTENT_CHANGED = NO
SICHUAN_REPORT_CHANGED = NO
SICHUAN_REPORT_FORMATTING_STARTED = NO
ALL_TESTS_PASS = YES

TASK_STATUS = DOC_MCP_DEFAULT_PRESET_001_COMPLETED
TASK_EXECUTION_COMPLETE = YES
GPT_REVIEW_COMPLETE = NO
DOCUMENTFACTORY_DEFAULT_PRESET_READY = YES
READY_FOR_SICHUAN_REPORT_FORMAT_TASK = YES
NEXT_TASK_STARTED = NO
```
