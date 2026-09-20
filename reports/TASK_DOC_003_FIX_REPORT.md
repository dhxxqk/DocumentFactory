# TASK_DOC_003_FIX：DSH E2E Closure 报告

实际生成时间：2026-09-20T23:22:42+08:00（Asia/Hong_Kong）

## 1. 结果

**RESULT：PASS**

DocumentFactory 已完成真实用户体验闭环：自然语言请求由 DSH Agent 理解，Agent 自主发现 DocumentFactory MCP，在未被告知工具名的情况下调用 `mcp__documentfactory__format_document`，生成新的 DOCX 和 Markdown Validation Report，并在最终回复前通过 DSH `present` 成功交付两个文件。

本轮没有开发或修改 DocumentFactory Core、MCP Server、tool schema、格式规则、编号/TOC 修复或其他产品功能。唯一运行配置修正是在 DSH headless profile 中挂载官方 `@deepseek-ai/dsh-tool-present`。

## 2. 基础信息

| 项目 | 实际值 |
|---|---|
| DocumentFactory 版本 | `0.3.0a1` |
| DSH 版本 | `0.1.5-rc.2` |
| 模型 provider route | `deepseek-official` |
| 实际模型 | `deepseek-flash` |
| DSH profile | `headless` |
| 模型配置方式 | 仅当前临时进程的 `DEEPSEEK_API_KEY` 环境变量 |
| 仓库 | `G:\Workflows\DocumentFactory` |
| origin | `git@github.com:dhxxqk/DocumentFactory.git` |

API Key 没有写入仓库、Git、`cordis.patch.yml`、报告或 Windows User/Machine 持久环境；两个 DSH 进程结束时均清除了进程环境变量。报告不记录 key 值。

## 3. 必读资料与架构确认

已完整阅读：

- `README.md`
- `docs/ADR_001_DOCUMENTFACTORY_DIRECTION.md`
- `docs/DOCUMENTFACTORY_PRODUCT_DESIGN_V1.md`
- `reports/TASK_DOC_003_REPORT.md`

任务开始时产品设计文档尚未出现在本地；远端并发新增 `986c7ea docs: add DocumentFactory product design direction` 后已 fetch、完整阅读，并通过普通 merge 纳入本地历史。资料共同确认本轮架构保持：

```text
DSH Agent
→ MCP stdio
→ DocumentFactory
→ normalize Core
→ DOCX + Validation Report
→ DSH present
```

## 4. DSH 环境与配置

`dsh --help` 与 `dsh --profile headless --help` 已确认：

- launcher 使用 `--profile <name>`；
- headless 用法为 `dsh --profile headless "<task>"`；
- 模型凭据可由 DSH web Models 页的 credential service 或启动进程的 `DEEPSEEK_API_KEY` 提供。

`dsh --profile headless --dump-config` 验证 DocumentFactory MCP 配置：

```text
name: '@deepseek-ai/dsh-mcp-client'
serverName: documentfactory
transport: stdio
command: G:\Workflows\DocumentFactory\.venv\Scripts\python.exe
args: ['-m', 'document_factory.mcp_server']
cwd: G:\Workflows\DocumentFactory
failOnStartupError: true
```

首次有模型的 E2E 已成功完成 MCP 调用与产物生成，但发现 headless composition 没有挂载 `present`。本机 DSH 已安装官方 `@deepseek-ai/dsh-tool-present@0.1.5-rc.2`；根据该包自带 README 的标准 composition 配置，在 headless patch 中追加：

```yaml
- insert:
    - id: present
      name: '@deepseek-ai/dsh-tool-present'
      config:
        maxFiles: 8
```

配置位置：`C:\Users\dhxxq\.dsh\profiles\headless\cordis.patch.yml`

修改前备份：`C:\Users\dhxxq\.dsh\profiles\headless\cordis.patch.yml.TASK_DOC_003_FIX.20260920_231815.bak`

备份与修改前原文件 SHA-256 一致。修改后再次执行 `--dump-config`，确认同时包含 `mcp-documentfactory`、`serverName: documentfactory`、`transport: stdio`、`id: present` 和 `@deepseek-ai/dsh-tool-present`。没有把 API Key 写入配置。

## 5. 模型启动验证

实际执行：

```text
dsh --profile headless "你好，请介绍一下自己"
```

**PASS**：DSH 返回由 `deepseek-flash` 生成的中文自我介绍，退出码为 0。模型明确识别当前工作目录与 DocumentFactory 三项 MCP 能力。

## 6. 真实 Agent E2E

最终成功测试使用的自然语言请求：

```text
请把 G:\Workflows\DocumentFactory\testcases\第三周_规划管理能力_培训材料_格式规范V1.4.docx 这个 DOCX 按电网科技项目 V1.4 规范统一格式。完成后把修改后的 Word 文件和格式检查报告交给我。
```

请求没有指定工具名，也没有要求 Agent 调用 `format_document`。DSH 会话：`session-9ff2951d-a432-4e34-99eb-dda30ecefd35`。

| 项目 | 结果 |
|---|---|
| 模型启动 | **PASS** |
| MCP 加载 | **PASS** |
| 三工具发现 | **PASS** |
| Agent 自主选择 preset | **PASS** — `grid_tech_v1_4` |
| `format_document` 调用 | **PASS** |
| DOCX 生成 | **PASS** |
| Markdown Report 生成 | **PASS** |
| 原文件保护 | **PASS** |
| 输出 DOCX 可读 | **PASS** |
| `present` 双文件交付 | **PASS** |
| 最终回答准确说明剩余 ERROR | **PASS** |

DSH durable session log 中存在完整的 `tool/call`、`tool/result` 和 `deliverables/presented` 事件。本轮 Agent 仅使用 shell 做 `Get-ChildItem` / `Get-Item` 只读存在性检查，没有通过 shell、Python 或 XML 修改 DOCX。

## 7. Tool Evidence

Agent 先自主调用：

```text
mcp__documentfactory__list_presets
```

随后实际调用：

```text
mcp__documentfactory__format_document
```

调用参数：

```json
{
  "input_path": "G:\\Workflows\\DocumentFactory\\testcases\\第三周_规划管理能力_培训材料_格式规范V1.4.docx",
  "preset": "grid_tech_v1_4"
}
```

MCP 返回证据：

- `status: FAIL`（表示修复后仍有 ERROR，不代表调用失败）
- `before`: ERROR 42 / WARNING 20 / INFO 4204
- `after`: ERROR 3 / WARNING 20 / INFO 4243
- `changed_count: 6`
- `remaining_error_count: 3`
- `source_unchanged: true`
- deliverables：一个 DOCX 和一个 Markdown

## 8. Present Evidence

实际调用：

```text
present
```

参数包含两个现存文件：

1. `output/normalized/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_formatted.docx`
2. `reports/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_NORMALIZATION_REPORT.md`

DSH durable session 记录了：

```text
deliverables/presented
Presented ..._formatted.docx
Presented ..._NORMALIZATION_REPORT.md
```

`present` tool result 的 `isError` 为 `false`，两个文件均在 Agent 最终回复之前完成声明交付。

## 9. 文件验证

| 文件 | SHA-256 |
|---|---|
| 输入 DOCX | `a94bcfe25e6741bc7eb38684eb5e88e809d3acad8ee486c89763a9274fbd237b` |
| 输出 DOCX | `90785a3561fa1eec26d7c68721adf0958c65c74dd063d1c8853f91cd4860c094` |
| Markdown Validation Report | `d68a6f20e19aaaea173b10cb4391a70bcbe6997dd4e2c152a6183fb41f219b0d` |

- 输入大小：60624 bytes
- 输出大小：60611 bytes
- 输入调用前后 SHA-256 相同：**是**
- 原文件是否变化：**否**
- 输出实际生成时间：2026-09-20T23:19:13+08:00
- Report 实际生成时间：2026-09-20T23:19:13+08:00
- 输出可由 DocumentFactory `read_docx` 重新读取：**是**
- 读取到段落数：786

## 10. 最终回答验收

Agent 最终回答准确说明：

- 已使用 `grid_tech_v1_4` 完成规范化；
- 原文件未修改；
- ERROR 42 → 3；
- WARNING 20 → 20；
- 仍有 3 个 NUM002 编号问题，不能声称全部合格；
- 三个剩余位置为 Paragraph 62、742、763；
- 编号修复属于当前明确不自动修复范围；
- 已列出并交付 DOCX 与 Validation Report。

## 11. 修改范围

仓库内没有功能代码变更。本轮只更新：

- `reports/TASK_DOC_003_FIX_REPORT.md`
- E2E 真实生成的 `reports/第三周_规划管理能力_培训材料_格式规范V1.4_a94bcfe25e67_NORMALIZATION_REPORT.md` 时间证据

仓库外只修改 DSH headless profile，且保留修改前备份。没有 force push、reset、rebase、amend 或重写历史。
