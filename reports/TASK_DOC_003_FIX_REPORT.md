# TASK_DOC_003_FIX：DSH E2E Closure 报告

实际生成时间：2026-09-20T23:05:22+08:00（Asia/Hong_Kong）

## 1. 结果

**RESULT：FAIL**

本轮目标是补齐“自然语言 → DSH Agent → DocumentFactory MCP → `format_document` → DOCX/Validation Report → `present`”真实闭环，不开发新功能。DSH 模型启动测试仍被 `MISSING_CREDENTIAL` 阻断，因此 Agent 回合、MCP tool call 和 `present` 均未发生。本报告不把 TASK_DOC_003 期间由官方 MCP Python Client 生成的旧产物冒充为本轮 DSH E2E 结果。

失败后严格按任务书 A 类处理：只检查 credential 与 DSH 配置，没有修改 DocumentFactory Core、MCP Server、tool schema、prompt/instructions 或任何格式规则。

## 2. 基础信息

| 项目 | 实际值 |
|---|---|
| DocumentFactory 版本 | `0.3.0a1` |
| DSH 版本 | `0.1.5-rc.2` |
| DSH profile | `headless` |
| 模型 provider route | `deepseek-official` |
| 模型配置方式 | DSH credential service 或 `DEEPSEEK_API_KEY` 环境变量 |
| 本轮可用凭据 | 无 |
| 仓库 | `G:\Workflows\DocumentFactory` |
| origin | `git@github.com:dhxxqk/DocumentFactory.git` |

凭据检查只记录是否存在，不读取或输出 secret：当前进程、Windows User 和 Windows Machine 三个作用域的 `DEEPSEEK_API_KEY` 均未设置；DSH credential service 也没有可用的 DeepSeek key。API Key 未写入仓库、Git、`cordis.patch.yml` 或本报告。

任务开始时，指定必读文件 `docs/DOCUMENTFACTORY_PRODUCT_DESIGN_V1.md` 尚未出现在本地或当时的 `origin/master`。本轮提交后发现远端并发新增提交 `986c7ea`，随即 fetch 并完整阅读该文件，再以普通 merge 保留双方历史。`README.md`、`docs/ADR_001_DOCUMENTFACTORY_DIRECTION.md` 与 `reports/TASK_DOC_003_REPORT.md` 也已完整读取。资料共同确认 `DSH → MCP → DocumentFactory → normalize Core` 架构。

## 3. DSH CLI 与配置核验

`dsh --help` 和 `dsh --profile headless --help` 已核验：

- launcher 使用 `--profile <name>`；
- headless 用法为 `dsh --profile headless "<task>"`；
- `0.1.5-rc.2` 的 headless profile 没有单独 credential CLI 参数；错误信息指定通过 web Models 页面写入 credential service，或在启动环境导出 `DEEPSEEK_API_KEY`。

`dsh --profile headless --dump-config` 退出成功，并确认：

```text
name: '@deepseek-ai/dsh-mcp-client'
serverName: documentfactory
transport: stdio
command: G:\Workflows\DocumentFactory\.venv\Scripts\python.exe
args: ['-m', 'document_factory.mcp_server']
cwd: G:\Workflows\DocumentFactory
failOnStartupError: true
```

实际配置位置：`C:\Users\dhxxq\.dsh\profiles\headless\cordis.patch.yml`。本轮没有修改该文件。

DocumentFactory MCP 在模型凭据检查之前由 DSH loader 成功启动；如果 stdio 启动或工具同步失败，`failOnStartupError: true` 会使 DSH 在 MCP startup 阶段失败。结合 TASK_DOC_003 已完成的官方 `tools/list` 证据，注册工具仍为：

- `mcp__documentfactory__format_document`
- `mcp__documentfactory__audit_document`
- `mcp__documentfactory__list_presets`

## 4. 模型启动测试

执行：

```text
dsh --profile headless "你好，请介绍一下自己"
```

实际结果：

```text
dsh: MISSING_CREDENTIAL: llm-deepseek: no API key for provider route "deepseek-official"; store DEEPSEEK_API_KEY through the credentials service (the web Models page writes it), or export DEEPSEEK_API_KEY in the launching environment
```

因此没有进入 Agent 回合。依照任务书，本轮没有继续发送真实文档 E2E prompt，也没有通过修改 DocumentFactory 或绕过 DSH 来制造成功结果。

## 5. 测试结果

| 项目 | 结果 |
|---|---|
| 模型启动 | **FAIL** — `MISSING_CREDENTIAL` |
| MCP 加载 | **PASS** — stdio 配置有效，loader 未报 startup error |
| 工具发现 | **PASS** — 三个既有工具由官方 client 验证并按 DSH 命名规则注册 |
| `format_document` 调用 | **FAIL / 未发生** — Agent 回合未启动 |
| DOCX 生成 | **FAIL / 本轮未生成** |
| Report 生成 | **FAIL / 本轮未生成** |
| `present` 交付 | **FAIL / 未发生** |

## 6. Tool Evidence

本轮实际调用的 DocumentFactory MCP tool：**无**。

预期但未发生的调用：

```text
mcp__documentfactory__format_document
```

调用参数：**无**。因为模型未启动，不能声称曾使用以下预期参数：

```text
input_path: G:\Workflows\DocumentFactory\testcases\第三周_规划管理能力_培训材料_格式规范V1.4.docx
preset: grid_tech_v1_4
```

## 7. 文件验证

测试输入：`testcases/第三周_规划管理能力_培训材料_格式规范V1.4.docx`

- 输入文件大小：60624 bytes
- 启动测试前 SHA-256：`a94bcfe25e6741bc7eb38684eb5e88e809d3acad8ee486c89763a9274fbd237b`
- 启动测试后 SHA-256：`a94bcfe25e6741bc7eb38684eb5e88e809d3acad8ee486c89763a9274fbd237b`
- 原文件是否变化：**否**
- 本轮输出 DOCX：**无**
- 本轮输出 DOCX SHA-256：**不适用**
- 本轮 Validation Report：**无**
- 本轮 DSH `present` deliverables：**无**

仓库中可能存在 TASK_DOC_003 协议测试生成的 `*_formatted.docx` 与 `*_NORMALIZATION_REPORT.md`；它们不是本轮 DSH Agent 生成或 present 的证据。

## 8. 闭环所需外部条件

用户需要使用以下任一官方方式向 DSH 提供有效 DeepSeek API Key：

1. 在 DSH web 的 Models 页面保存凭据；或
2. 在启动 `dsh` 的进程环境中设置 `DEEPSEEK_API_KEY`。

凭据就绪后，应从“你好，请介绍一下自己”的模型启动测试重新开始；只有模型回答成功，才继续不指定工具的 DOCX 自然语言 E2E，并验收真实 `mcp__documentfactory__format_document` tool call、两个新产物、输入哈希不变及 DSH `present` 双文件交付。

## 9. 修改范围

本轮功能提交仅新增本报告：`reports/TASK_DOC_003_FIX_REPORT.md`。没有修改功能代码、配置、规则、测试或已有报告。远端并发新增的产品设计文档通过普通 merge 纳入本地历史。

- TASK_DOC_003_FIX 提交：`64dc1098047634b9ad95bb95b6dd64260f525a0d`（`fix: complete DSH end to end document workflow`）。
- 首次 SSH push 因远端并发提交而被 non-fast-forward 保护拒绝；未使用 force push、reset、rebase 或 amend。
- fetch 后确认远端只新增 `986c7ea docs: add DocumentFactory product design direction`，通过普通 merge 提交 `7f052c3` 合并，无冲突。
- 合并结果已通过 SSH 成功推送至 `origin/master`；本次报告事实修正使用后续独立 docs 提交。
