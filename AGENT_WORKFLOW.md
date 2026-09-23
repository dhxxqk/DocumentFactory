# AGENT_WORKFLOW.md — Agent 任务执行流程（跨节点统一）

任务来源: GOV_DOC_001 — Multi Machine Development Workflow

生效日期: 2026-09-23 (+08:00)

适用对象：Codex、Trae、DeepSeek Harness 及其他任何参与 DocumentFactory 开发的 Agent。本文件工具中立，不含任何单一工具专属条款；工具接入说明放 `integrations/`。

本文件是单任务执行的最小检查清单，权威细则仍以 [`AGENTS.md`](./AGENTS.md) 与 `docs/agent/` 五件规范为准；多节点协同规则见 [`docs/governance/MULTI_MACHINE_DEVELOPMENT_WORKFLOW.md`](./docs/governance/MULTI_MACHINE_DEVELOPMENT_WORKFLOW.md)。

## 六步流程

```text
1. 获取最新仓库状态
2. 阅读项目规则
3. 确认当前任务
4. 修改代码
5. 输出报告
6. Commit / Push
```

### 1. 获取最新仓库状态

- 确认节点身份：机器名、工作路径必须是 `E:\Project\DocumentFactory`，并与 `docs/governance/DEVELOPMENT_NODES.md` 登记一致
- `git status` 工作区 clean；`git fetch origin` + `git pull`，确认 HEAD 与 `origin/master` 一致或已普通 merge
- 查看 `git log --oneline -10`，不凭聊天记录或跨会话记忆续作

### 2. 阅读项目规则

必读：`AGENTS.md`、`docs/agent/CORE_RULES.md`、`docs/agent/DEVELOPMENT_WORKFLOW.md`。

按任务范围追加：测试 → `docs/agent/TESTING_RULES.md`；提交 → `docs/agent/GIT_WORKFLOW.md`；报告 → `docs/agent/REPORTING_STANDARD.md`。多节点任务另读 `docs/governance/MULTI_MACHINE_DEVELOPMENT_WORKFLOW.md`。

### 3. 确认当前任务

- 完整读取任务书，记录编号、目标、验收标准与禁止事项
- 编号唯一性检索：`tasks/`、`reports/`、`docs/development_reports/`、`docs/reports/`、`git log`
- 当前任务状态以仓库为准：`docs/development_reports/`、`CHANGELOG.md`、`git log`；`TASK_REGISTRY.md` / `CURRENT_STATE.md` 建立后一并读取
- 任务书与仓库事实冲突时暂停，向任务提出者确认，冲突与裁定写入报告

### 4. 修改代码

- 最小必要修改，不扩大范围，不做无需求重构，不触碰无关模块
- 确定性 OOXML 修改只能由 DocumentFactory Core 完成，Agent 不得直接改 OOXML（ADR-001 红线）
- 不删除/弱化既有功能与测试，不引入未批准依赖，不覆盖输入文件
- 新功能加测试；改代码跑全量测试；纯文档任务也跑一次测试证明无影响

### 5. 输出报告

- 主线任务：`docs/development_reports/TASK_xxx_REPORT.md`，按 `docs/agent/REPORTING_STANDARD.md`
- 治理/维护任务（GOV_DOC_、MAINT_DOC_ 系列）：按任务书指定路径（治理规范 `docs/governance/`，维护报告 `docs/reports/`）
- RESULT 必须有证据：真实命令、退出码、哈希、路径；条件通过标 CONDITIONAL；未执行写"未执行"及原因，禁止编造

### 6. Commit / Push

- 提交信息：`TASK_xxx: description`（治理 / 维护任务用对应 `GOV_DOC_NNN:` / `MAINT_DOC_NNN:` 前缀）
- 仅暂存本任务文件，禁止 `git add -A` / `git add .`；提交前 `git status` / `git diff` / `git diff --staged` 逐项自检
- push 一律走 SSH 到 `origin/master`；禁止 force push 与改写已推送历史
- 推送后复核 HEAD 与 origin/master 一致，哈希与推送结果回填报告（回填用独立 docs 提交，不改写历史）
- 离场前必须确认推送成功；未推送不得视为完成

## 暂停确认条件

出现以下任一情况，Agent 必须停止并向任务提出者确认，不得自行推进：任务编号冲突；任务书与仓库事实矛盾；任务要求触碰红线或引入未批准依赖；节点持有未推送改动且无法确定远端状态；发现任务范围外的严重既有缺陷。
