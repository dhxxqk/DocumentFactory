# TASK_DOC_003 完成报告

实际生成时间：2026-09-20T13:34:00+08:00（Asia/Hong_Kong）

## 1. 任务结果

**CONDITIONAL PASS**

DocumentFactory `0.3.0a1` 已完成 Core 之上的薄 MCP stdio 适配层，并通过官方 MCP Python Client 以真实子进程完成 `initialize → tools/list → list_presets → audit_document → format_document` 全协议链路。三项工具均复用现有 `lint`、`normalize`、规则和 Validation Report 实现，没有复制 OOXML、StyleResolver 或 lint 判断逻辑。

本机 DSH 已安装官方 MCP Client、完成 web/headless 配置、通过 `--dump-config` 核验，并在 headless 启动阶段成功加载 MCP Server。真实自然语言 E2E 在模型回合开始前被 DSH 的 `MISSING_CREDENTIAL` 阻断：本机没有 `DEEPSEEK_API_KEY`。因此本次没有发生 DSH Agent 自主调用 `format_document`，也没有发生 DSH `present`。报告不将这两项写成成功，故结果为 CONDITIONAL PASS，而非 PASS。

## 2. 版本

| 组件 | 实际版本 |
|---|---|
| DocumentFactory | `0.3.0a1` |
| Python | `3.12.14` |
| MCP Python SDK | `2.2.0` |
| DSH | `0.1.5-rc.2` |
| `@deepseek-ai/dsh-mcp-client` | `0.1.5-rc.2` |

MCP Python SDK 通过项目可选依赖 `mcp>=2,<3` 安装；DSH MCP Client 是 DSH 官方包的实际依赖版本。

## 3. 实现范围

- 新增 `python -m document_factory.mcp_server` 和 `document-factory-mcp` stdio 启动入口。
- 仅暴露 `format_document`、`audit_document`、`list_presets` 三项 MCP tool。
- `format_document` 直接调用 Core `normalize(...)`；`audit_document` 直接调用既有 `lint(...)` 和 `write_report(...)`；`list_presets` 加载既有规则。
- 工具返回紧凑、结构化、可序列化结果，包含路径、状态、before/after 计数、输入哈希和可交付文件；不把完整 findings 塞入对话上下文。
- 所有生成路径都在仓库既有 `output/` 和 `reports/` 范围内；输入只读并在调用前后验证 SHA-256。
- Server instructions 明确要求 Agent 不得通过 shell/XML 绕过 DocumentFactory 修改 DOCX，且必须用 DSH `present` 交付 DOCX 和 Markdown。
- 没有实现 HTTP MCP、GUI、WorkBuddy、WPS/Word 插件、新编号修复或 TOC 修复。

## 4. 完整自动测试

**76 passed，0 failed/error，0 skipped**，耗时 **4.05 秒**。

JUnit XML：`reports/pytest.xml`，记录时间 `2026-09-20T13:33:07.442588+08:00`。

其中新增 2 项 MCP 测试，均通过官方 `mcp.Client` 与 `StdioServerParameters` 启动真实 subprocess，不是 import 工具函数模拟：

- `test_official_client_stdio_initialize_list_and_real_calls`
- `test_official_client_stdio_reports_input_and_core_errors`

覆盖 initialize、tool discovery、真实 audit/format、中文和空格路径、输出可读、输入不变、序列化边界，以及缺失文件、非 DOCX、未知 preset、损坏 DOCX 的 MCP 错误响应。

`git diff --check` 通过。

## 5. MCP stdio 协议验证

**PASS**

启动命令：

```text
G:\Workflows\DocumentFactory\.venv\Scripts\python.exe -m document_factory.mcp_server
```

官方 MCP Python Client 的真实协议顺序与结果：

1. `initialize`：成功，server name `documentfactory`，version `0.3.0a1`。
2. `tools/list`：成功，且精确得到三个工具：`list_presets`、`audit_document`、`format_document`。
3. `list_presets`：成功，默认 preset 为 `grid_tech_v1_4`。
4. `audit_document`：成功，真实 lint 为 ERROR 42 / WARNING 20 / INFO 4204，生成 Markdown Validation Report。
5. `format_document`：成功，真实生成新 DOCX 和 Markdown Validation Report，ERROR 42 → 3。

协议返回明确说明修复后仍有 3 个 ERROR，不声称文档全部合格。

## 6. TEST_CASE_001 真实结果与交付物

输入：`testcases/第三周_规划管理能力_培训材料_格式规范V1.4.docx`

| 指标 | 修复前 | 修复后 | 变化 |
|---|---:|---:|---:|
| ERROR | 42 | 3 | -39 |
| WARNING | 20 | 20 | 0 |
| INFO | 4204 | 4243 | +39 |

- 输入 SHA-256（调用前）：`a94bcfe25e6741bc7eb38684eb5e88e809d3acad8ee486c89763a9274fbd237b`
- 输入 SHA-256（调用后）：`a94bcfe25e6741bc7eb38684eb5e88e809d3acad8ee486c89763a9274fbd237b`
- 输入文件保持不变：**是**
- 输出 SHA-256：`90785a3561fa1eec26d7c68721adf0958c65c74dd063d1c8853f91cd4860c094`
- 新 DOCX：`output/normalized/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_formatted.docx`
- Audit Markdown：`reports/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_AUDIT_REPORT.md`
- Normalize Markdown：`reports/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_NORMALIZATION_REPORT.md`
- 同名 JSON Validation Report 已在本地生成；按仓库既有 `.gitignore` 策略不纳入 Git。

上述 DOCX 与 Markdown 是由官方 MCP Client 协议调用真实交付的文件，不是 DSH `present` 的交付结果。

## 7. DSH 配置与工具发现

修改前已检查版本和现有配置。`C:\Users\dhxxq\.dsh` 在本任务前不存在；首次 `--dump-config` 由 DSH 创建了默认空 patch。修改前已分别备份：

- `C:\Users\dhxxq\.dsh\profiles\web\cordis.patch.yml.TASK_DOC_003.20260920_132156.bak`
- `C:\Users\dhxxq\.dsh\profiles\headless\cordis.patch.yml.TASK_DOC_003.20260920_132156.bak`

实际追加配置的位置：

- `C:\Users\dhxxq\.dsh\profiles\web\cordis.patch.yml`
- `C:\Users\dhxxq\.dsh\profiles\headless\cordis.patch.yml`

没有覆盖用户已有的 `cordis.patch.yml` 内容；没有修改 home 级 patch。仓库另提供可复用模板 `integrations/dsh/documentfactory.cordis.yml`。

web 与 headless 的 `dsh --profile <profile> --dump-config` 均退出 0，并确认最终组合配置使用：

- 官方插件 `@deepseek-ai/dsh-mcp-client`
- `serverName: documentfactory`
- `transport: stdio`
- 项目 `.venv` Python 执行 `-m document_factory.mcp_server`
- `failOnStartupError: true`

### DSH tool discovery

**PASS**

DSH headless 在启动真实任务时完成 loader 初始化后才进入模型凭据检查；本次错误发生在模型凭据检查阶段而不是 MCP startup，且 `failOnStartupError: true`，证明 DocumentFactory MCP Server 已成功连接并同步工具。官方 DSH MCP Client 按 `mcp__<serverName>__<toolName>` 映射，本次实际注册名为：

- `mcp__documentfactory__format_document`
- `mcp__documentfactory__audit_document`
- `mcp__documentfactory__list_presets`

同一 server 的官方 MCP `tools/list` 原始结果精确为上述三个 tool name，没有额外 DocumentFactory 工具。

## 8. DSH headless E2E

**BLOCKED：未完成 Agent 回合**

真实执行了 headless 自然语言请求，要求 Agent 自主判断并调用 `mcp__documentfactory__format_document`，随后用 DSH `present` 交付 DOCX 与 Markdown。DSH 返回：

```text
dsh: MISSING_CREDENTIAL: llm-deepseek: no API key for provider route "deepseek-official"; store DEEPSEEK_API_KEY through the credentials service (the web Models page writes it), or export DEEPSEEK_API_KEY in the launching environment
```

本机没有 `DEEPSEEK_API_KEY`，也没有可替代的 OpenAI、Anthropic 或 Gemini 模型凭据。出于安全边界，本任务没有伪造凭据、读取外部秘密或绕过 DSH 官方 Agent。

| 验证项 | 结果 |
|---|---|
| DSH 加载 DocumentFactory MCP Server | 成功 |
| DSH 发现三个 DocumentFactory 工具 | 成功 |
| Agent 自主调用 `format_document` | **未发生** |
| 实际调用的 MCP tool | **无（模型回合未开始）** |
| Agent 通过 shell/XML 手改 DOCX | 未发生 |
| DSH `present` | **未发生** |
| DSH 最终交付 formatted DOCX | **否** |
| DSH 最终交付 Markdown Validation Report | **否** |
| Agent 正确说明 before/after ERROR | **未产生最终回答** |

当前 DSH `0.1.5-rc.2` 也不支持任务书示例中的 `--json` CLI 参数；本次使用该版本实际支持的 headless task 参数执行。这个 CLI 差异不是 MCP Server 故障，但会影响后续自动采集结构化 DSH 会话证据。

## 9. 已知限制

- 需要用户通过 DSH web Models 页面或启动环境提供有效 `DEEPSEEK_API_KEY`，才能完成最后一跳的 Agent 自动调用与 `present` 验收。
- MCP 第一版只支持一个 preset：`grid_tech_v1_4`。
- MCP Server 只接受明确输入路径，不扫描目录，不提供任意 shell、XML 或文件编辑工具。
- `format_document` 仍保留 Core 的范围：不修复多级编号、TOC 或未确认语义分类；TEST_CASE_001 修复后仍有 3 个 NUM002 ERROR。
- stdio Server 的进程工作目录必须指向仓库，以便生成路径落入受控 `output/` 和 `reports/`。
- DSH `0.1.5-rc.2` 的 headless CLI 没有 `--json` 输出选项。

## 10. WorkBuddy 下一阶段准备情况

**有条件具备。**

DocumentFactory Core、稳定 Python 结果结构、三工具 MCP stdio 契约、官方协议测试、DSH 配置模板和交付路径已经具备下一阶段 WorkBuddy 接入的技术前提。MCP 层保持薄适配，不需要 WorkBuddy 复制任何 OOXML/lint/normalize 逻辑。

但在进入 WorkBuddy 接入前，应先为 DSH 配置有效模型凭据并补跑同一条 headless E2E，取得“Agent 自动调用 `format_document` + `present` DOCX/Markdown + 最终文本准确说明 42 → 3”的完整证据。因此当前不是无条件进入下一阶段。

## 11. 修改文件列表

| 类别 | 文件 |
|---|---|
| MCP Server | `src/document_factory/mcp_server.py` |
| 版本与依赖 | `src/document_factory/__init__.py`、`pyproject.toml` |
| DSH 集成 | `integrations/dsh/documentfactory.cordis.yml`、`integrations/dsh/README.md` |
| 测试 | `tests/test_mcp_server.py` |
| 用户文档 | `README.md`、`CHANGELOG.md` |
| 自动测试证据 | `reports/pytest.xml` |
| 协议样本证据 | `reports/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_AUDIT_REPORT.md`、`reports/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_NORMALIZATION_REPORT.md` |
| 任务报告 | `reports/TASK_DOC_003_REPORT.md` |

DSH profile 配置与备份位于用户配置目录，不纳入项目 Git。生成的 DOCX 和 JSON 按既有 `.gitignore` 规则保留在本地。

## 12. Git 提交与推送

功能提交与 SSH push 状态将在完成提交和远端校验后回填。本任务不会 force push、reset、rebase、amend 或改写已共享历史。
