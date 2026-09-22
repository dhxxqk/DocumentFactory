# AGENTS.md — DocumentFactory AI Agent 统一入口

本文件是所有 AI Coding Agent 参与 DocumentFactory 开发时的统一入口，适用对象包括但不限于 Codex、Trae、DSH、Grok 及其他兼容 Agent。本治理层与具体 Agent 工具无关：不得在本文件或 `docs/agent/` 中写入仅服务于单一工具的强制条款。工具专属接入说明放在各自的 `integrations/` 目录（例如 `integrations/dsh/`）。

## 1. 项目定位

DocumentFactory 是面向 AI 驱动文档生产流程的自动化基础设施项目：以确定性的 DOCX 文档质量核心（OOXML 解析 → 结构审计 → 规则或模板驱动的确定性格式规范化 → 修复后验证 → Markdown / JSON 报告）为主体，并通过本地 stdio MCP 向 Agent 暴露薄适配接口。DocumentFactory 本身不调用 LLM、OCR 或自动排版服务；AI 负责意图与编排，确定性 OOXML 修改只允许由 Core 完成（见 `docs/ADR_001_DOCUMENTFACTORY_DIRECTION.md`）。

```text
输入：
文档需求 / 模板 / 规范

  ↓

处理：
规则解析 → 格式控制 → 自动生成 → 静态校验

  ↓

输出：
符合规范的 Office 文档（默认生成新文件，绝不覆盖输入）
```

工程事实速览（权威细节以 `README.md` 与仓库当前代码为准）：

- Python >= 3.10，src layout，包名 `document_factory`，版本见 `pyproject.toml`
- 代码：`src/document_factory/`；测试：`tests/`；正式规范：`specs/`；机器规则：`rules/`
- Windows 测试命令（在工程根目录执行）：`.\.venv\Scripts\python.exe -X utf8 -m pytest -q`
- 报告产物：`reports/`（工具运行报告与历史任务报告）、`docs/development_reports/`（新标准任务开发报告）

## 2. Agent 工作入口

任何 Agent 执行任何任务**之前**，必须阅读：

- `docs/agent/CORE_RULES.md`
- `docs/agent/DEVELOPMENT_WORKFLOW.md`

按任务涉及范围追加阅读：

| 任务涉及 | 必读 |
|---|---|
| 编写或运行测试 | `docs/agent/TESTING_RULES.md` |
| Git 提交 | `docs/agent/GIT_WORKFLOW.md` |
| 编写开发报告 | `docs/agent/REPORTING_STANDARD.md` |

## 3. 基础行为约束

- 修改前先检查现有代码与仓库当前状态，**不根据任务描述猜测实现状态**
- 不扩大任务范围，不修改无关模块，不做无需求重构
- 不删除已有功能；不通过删除或修改测试用例、降低断言来解决测试失败
- 不引入未验证依赖；不提交临时文件、运行生成物与个人配置
- 发现问题（任务书与仓库事实冲突、疑似既有缺陷、边界不清）先记录，必要时暂停并向任务提出者确认
- 完成后必须交付：代码修改（如涉及）+ 测试结果 + Git diff 自检 + 开发报告，四者缺一不可
