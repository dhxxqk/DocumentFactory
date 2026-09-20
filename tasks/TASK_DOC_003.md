# TASK_DOC_003：DocumentFactory MCP + DSH 首次端到端闭环

状态：Ready  
优先级：P0  
目标版本：v0.3-alpha  
前置任务：TASK_DOC_002（PASS）  
架构依据：docs/ADR_001_DOCUMENTFACTORY_DIRECTION.md

## 1. 目标

把已稳定的 DocumentFactory Core 通过一个薄 MCP Server 暴露给 DeepSeek Harness（DSH），完成第一次真实用户闭环：

用户把 DOCX 放进 DSH 会话/工作区
→ 自然语言要求“按规范统一格式”
→ DSH 自动调用 DocumentFactory MCP
→ MCP 调用现有 normalize(...) Core
→ 生成新 DOCX + Validation Report
→ DSH 使用 present 显式交付 DOCX + Markdown
→ 用简短中文说明修复前后结果和剩余问题。

完成后，用户不需要直接运行 CLI 或 Python。

## 2. 原则

1. MCP 只做薄适配层，不复制 OOXML、StyleResolver、lint、normalize、Validation Report 逻辑。
2. Core 是唯一业务真源；MCP 必须调用现有 Python Core。
3. DSH 只负责编排与交付，不允许 Agent 用 shell/XML 绕过 DocumentFactory 修改同一个 DOCX。
4. 第一版仅做本地 stdio MCP，不做 HTTP/云服务。
5. 最终文件必须调用 DSH present；回复里只写路径不算交付完成。
6. 保留原文件，禁止覆盖输入。
7. MCP 返回简洁结构化结果，不把完整 findings/report 正文塞进 tool result。
8. Git push 一律使用 SSH，不使用 HTTPS。

## 3. 技术路线

使用官方 MCP Python SDK 当前稳定主线，建议可选依赖：
mcp>=2,<3

使用 DSH 官方：
@deepseek-ai/dsh-mcp-client

传输：
stdio

DSH 中应出现类似：
mcp__documentfactory__format_document
mcp__documentfactory__audit_document
mcp__documentfactory__list_presets

不要开发自定义 DSH tool plugin，除非官方 MCP client 在本机确有不可用证据。

## 4. MCP Server

建议新增：
src/document_factory/mcp_server.py

新增 console entry：
document-factory-mcp

同时支持：
python -m document_factory.mcp_server

默认运行 stdio MCP server。

Server instructions / tool descriptions 必须明确：
- 用户要求统一 DOCX 字体、格式、按规范排版、检查并修复格式时优先调用 format_document。
- 只检查不修改时调用 audit_document。
- 查询可用规范时调用 list_presets。
- 不通过 shell、脚本或手工 XML 替代这些工具。
- format_document 完成后，将 DOCX 和 Markdown 报告交给 DSH present。
- after lint 仍有 ERROR 时不得声称“全部合格”。

## 5. 第一版只暴露 3 个工具

### 5.1 format_document

输入建议：
- input_path: str，必填，DOCX 路径
- preset: str，默认 grid_tech_v1_4

行为：
1. 校验文件存在、为普通文件且扩展名 .docx。
2. preset 映射到明确 rules 文件。
3. 调用现有 normalize(...)。
4. 不自行编辑 OOXML。
5. 返回简洁 JSON。

建议返回字段：
- status
- input_path
- output_path
- report_path
- before: ERROR/WARNING/INFO
- after: ERROR/WARNING/INFO
- changed_count
- remaining_error_count
- source_unchanged
- summary
- deliverables: formatted DOCX + Markdown report

不要返回完整 before_findings/after_findings。完整明细留在报告文件中。

### 5.2 audit_document

输入：
- input_path
- preset = grid_tech_v1_4

行为：
- 调用现有 lint/report；
- 不修改输入；
- 生成审计报告；
- 返回 status、ERROR/WARNING/INFO、report_path、source_unchanged、summary；
- deliverables 至少包含 Markdown 审计报告。

### 5.3 list_presets

第一版至少返回：
grid_tech_v1_4

包含：
- id
- 显示名
- rules 文件
- spec_version
- 简短说明

使用明确 registry/mapping，不让 Agent 猜规则文件名。

## 6. 路径与交付

第一版允许 MCP 接受绝对 Windows 路径；中文和空格路径必须可用。不得扫描用户未指定的其他目录。

输出继续复用 Core 的安全策略（output/normalized、reports），MCP 不自行破坏输出边界。

真实 DSH 闭环中，Agent 必须对 format_document 返回的：
- formatted DOCX
- Markdown Validation Report

调用 present。

如果 DSH Session filesystem 无法 present DocumentFactory 项目目录中的绝对路径：
1. 记录真实失败证据；
2. 再做最小安全适配，例如复制最终产物到 Session 可访问目录；
3. 适配放在 Agent/MCP 边界，不破坏 Core 输出安全约束；
4. 报告写清原因和实现。

## 7. DSH 配置

先执行：
dsh --version

不要盲装 latest。若 profile 尚未安装 MCP client，应安装与当前 DSH 主版本匹配的 @deepseek-ai/dsh-mcp-client，并记录版本。

修改前检查：
- $DSH_HOME/profiles/web/cordis.patch.yml
- $DSH_HOME/profiles/headless/cordis.patch.yml
- $DSH_HOME/cordis.patch.yml
- dsh --profile web --dump-config

不得覆盖整个已有 patch 文件；修改前备份并记录备份路径。

最终 stdio 配置应等价于：

- insert:
    - id: mcp-documentfactory
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: documentfactory
        transport: stdio
        command: 'G:\Workflows\DocumentFactory\.venv\Scripts\python.exe'
        args: ['-m', 'document_factory.mcp_server']
        cwd: 'G:\Workflows\DocumentFactory'

实际 schema 以本机当前 DSH 官方版本为准；通过 --dump-config / 官方源码核验，不能凭印象猜。

至少让 web 与 headless 两个 profile 都能使用 DocumentFactory。若使用 home-level patch，共享范围必须记录清楚。

## 8. 自动触发

本任务先不开发复杂 Skill。优先依靠 MCP server instructions、tool name、tool description 和 DSH 官方 MCP client 的指令注入，让以下自然语言可触发：

“把这个 Word 的字体和格式统一一下。”
“按电网科技项目 V1.4 规范修一下这个文档。”
“检查这个 DOCX 的格式，但不要修改。”
“现在有哪些文档规范可以用？”

若真实测试发现模型不能稳定选工具，再增加最小 instruction/skill；不要一开始增加额外复杂度。

## 9. 测试

### 9.1 回归
TASK_DOC_002 基线 74 passed，旧测试必须全部通过。

### 9.2 MCP 单元/协议测试
至少覆盖：
- MCP Server 可 initialize；
- tools/list 仅看到规定的 3 个工具；
- schema 明确；
- list_presets 返回 grid_tech_v1_4；
- format_document 真调用 Core 并生成 DOCX + 报告；
- audit_document 不修改源文件；
- 非 DOCX、缺失路径明确报错；
- 中文/空格路径可用；
- 返回 JSON 可序列化；
- 不返回超大完整 findings；
- Core 异常转为明确 MCP 错误/结构化失败。

必须使用 MCP 官方 Python client，以 stdio subprocess 真实启动：
python -m document_factory.mcp_server

完成：
initialize → tools/list → list_presets → audit_document → format_document

不能只 import Python 函数伪装 MCP 测试。

### 9.3 DSH tool discovery
执行：
dsh --profile web --dump-config

确认 MCP row 进入最终 composition。启动 DSH 后必须有证据工具注册为 mcp__documentfactory__...。

### 9.4 DSH headless 真实 E2E
使用测试 DOCX，真实 DSH Agent 执行自然语言任务，而不是手动指定 tool call。建议：

dsh --profile headless "请把这个 DOCX 按电网科技项目 V1.4 规范统一格式，完成后把修改后的 Word 和格式报告作为文件交给我：<测试文件绝对路径>"

验收：
1. Agent 自主选择 mcp__documentfactory__format_document；
2. 真正生成新 DOCX；
3. 没用 shell 手改 DOCX；
4. 调用 present；
5. Session 有 DOCX + Markdown 两个 deliverables；
6. 最终文本说明 before/after ERROR；
7. after 有 ERROR 时明确剩余问题，不宣布全部合格。

优先用 DSH --json 获取 tool call 和 deliverable 证据，并在报告保留精简证据。

## 10. 文件建议

可按实际调整：
- src/document_factory/mcp_server.py
- src/document_factory/mcp_tools.py（如必要）
- integrations/dsh/documentfactory.cordis.yml
- integrations/dsh/README.md
- tests/test_mcp_server.py
- reports/TASK_DOC_003_REPORT.md

不要把本机绝对路径硬编码进通用 Core；机器路径只出现在本机配置或示例。

## 11. 依赖与版本

建议：
[project.optional-dependencies]
mcp = ["mcp>=2,<3"]

未安装 MCP extra 时，MCP 入口应给清楚错误，提示安装 document-factory[mcp]，不要吞 ImportError。

完成后建议版本：
0.3.0a1

更新：
README.md
CHANGELOG.md
pyproject.toml
reports/TASK_DOC_003_REPORT.md

不要把 API Key、token、凭据写入 Git。

## 12. TASK_DOC_003_REPORT

必须包含：
- 实际生成时间和时区
- RESULT：PASS / CONDITIONAL PASS / FAIL
- DocumentFactory 版本
- DSH 版本
- MCP Python SDK 版本
- DSH MCP client 版本
- 自动测试结果
- MCP stdio 协议测试结果
- DSH tool discovery 证据
- DSH headless E2E 结果
- 实际调用 tool 名
- 是否成功 present DOCX + Markdown
- 测试文档 before/after ERROR/WARNING
- 输入文件是否保持不变
- DSH 配置变更与备份
- 已知限制
- 是否具备下一阶段 WorkBuddy 接入条件
- Git commit hash 与 SSH push 状态

## 13. PASS 标准

只有同时满足以下条件才 PASS：
1. MCP Server stdio 正常启动；
2. 仅暴露规定 3 个工具；
3. format_document 调用真实 normalize Core；
4. audit_document 保持输入不变；
5. 官方 MCP client 协议级测试通过；
6. v0.2 旧测试全部通过；
7. DSH 加载官方 MCP client；
8. DSH 发现 DocumentFactory tools；
9. headless 自然语言任务自主调用 format_document；
10. Agent 调用 present 真正交付新 DOCX + Markdown；
11. Agent 不通过 shell/XML 绕过 MCP；
12. 文档、版本、报告完成；
13. git status clean；
14. 使用 SSH 成功 push origin/master。

如果 Core/MCP 已通过，但 DSH 因其当前版本兼容性或模型服务问题无法完成 E2E，只能 CONDITIONAL PASS，并提供可复现证据，不能写成完整 PASS。

## 14. Git / SSH

从最新 origin/master 开始。

先检查：
git remote -v

origin 必须是：
git@github.com:dhxxqk/DocumentFactory.git

若不是：
git remote set-url origin git@github.com:dhxxqk/DocumentFactory.git

建议 commit：
feat: add DocumentFactory MCP integration for DSH

最终：
git push origin master

严禁：
- HTTPS push
- force push
- reset 远端历史
- rebase 已共享历史
- amend 已 push commit

Push 后：
git fetch origin
git rev-parse HEAD
git rev-parse origin/master
git status

要求 HEAD == origin/master，working tree clean。

## 15. 明确不做

不做：
- WorkBuddy 接入（下一任务）
- WPS/Word 插件
- GUI
- HTTP MCP
- 云服务/账号系统/多租户
- 复杂 preset 编辑器
- 新编号/TOC 自动修复
- LLM 直接修改 OOXML
- shell 替代 DocumentFactory Core

本任务唯一目标：

**让 DSH 第一次可以通过自然语言自动调用 DocumentFactory，并把处理后的 DOCX 真正交回用户。**

## 16. 官方参考

执行时以本机版本和官方源码为准：
- deepseek-ai/deepseek-harness/packages/mcp/mcp-client/README.md
- deepseek-ai/deepseek-harness/docs/tool-catalog.md
- deepseek-ai/deepseek-harness/packages/bundle/headless/README.md
- deepseek-ai/deepseek-harness/docs/architecture.md
- modelcontextprotocol/python-sdk
