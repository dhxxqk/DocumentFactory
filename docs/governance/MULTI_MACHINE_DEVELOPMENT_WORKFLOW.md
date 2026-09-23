# MULTI_MACHINE_DEVELOPMENT_WORKFLOW.md — 多电脑、多 Agent 协同开发规范

任务来源: GOV_DOC_001 — Multi Machine Development Workflow

生效日期: 2026-09-23 (+08:00)

适用范围：DocumentFactory 的所有开发节点（台式机、笔记本及未来新增节点）与所有参与 Agent（Codex、Trae、DeepSeek Harness 及其他兼容 Agent）。

本文件是「多节点协同层」规范，不替代既有 Agent 治理层：任务执行细则仍以根目录 `AGENTS.md` 与 `docs/agent/`（CORE_RULES、DEVELOPMENT_WORKFLOW、GIT_WORKFLOW、TESTING_RULES、REPORTING_STANDARD）为准；本文件只规定跨节点、跨 Agent 协同所必需的额外约束。两者冲突时，按 `docs/agent/CORE_RULES.md` §4 的优先级处理并向任务提出者确认。

## 1. 核心原则

```text
GitHub Repository = Single Source of Truth（唯一事实源）
Local Machine     = Development Node（开发节点，只是工作副本）
Agent             = Execution Worker（执行工人，不是事实源）
```

1. 唯一事实源是 GitHub 仓库 `dhxxqk/DocumentFactory` 的 `master` 分支。聊天记录、个人记忆、跨会话印象、任务书背景陈述均不得作为事实。
2. 任何本地节点的工作区都是可重建的临时副本：环境可重装、仓库可重新克隆，只有推送进仓库的内容算数。
3. Agent 只负责任务的执行与证据输出，不拥有任务，也不把"自己机器上的状态"当成项目状态。
4. 节点之间不直接同步（不拷贝目录、不传补丁文件）；一切状态交换只经过 GitHub。
5. 不产生状态分叉：禁止 force push、禁止改写已推送历史；远端领先时只允许普通 merge（见 `docs/agent/GIT_WORKFLOW.md` §4）。

## 2. 开发节点管理

1. 节点登记表：[`DEVELOPMENT_NODES.md`](./DEVELOPMENT_NODES.md)。每个节点上线、退役、路径或工具链变更时，必须更新登记表并随代码提交入库。
2. 统一本地路径：所有 Windows 节点一律使用 `E:\Project\DocumentFactory`。禁止克隆到桌面、下载目录或临时目录。
3. 节点准入条件（缺一不可）：
   - `git fetch` 成功且工作区可与 `origin/master` 保持一致；
   - push 走 SSH（`git@github.com:dhxxqk/DocumentFactory.git`），节点公钥已登记到 GitHub 账号；
   - Git 提交身份与仓库历史一致（`dhxxqk <dhxxqk@gmail.com>`）；
   - 按 README 规范建好 `.venv` 并跑通全量测试；
   - 节点已在 `DEVELOPMENT_NODES.md` 登记。
4. 节点差异（Python 小版本、OS、是否安装 Codex/DSH、渲染后端）只允许作为该节点的"条件项"如实登记，不得通过修改项目代码或降低测试来迁就节点。
5. 行尾与换行：仓库以 `.gitattributes`（`* text=auto eol=lf`）为唯一准绳，节点保持 Git 默认行为即可；禁止针对单节点关闭 text 归一化或添加个人 gitattributes 覆盖。

## 3. 标准工作流程

### 3.1 开始开发前（每个节点、每次开工）

必须依次执行：

```powershell
git fetch origin
git status                 # 工作区必须 clean
git pull                   # 或明确 merge origin/master
```

然后阅读：

- `README.md`
- `AGENTS.md` 与 `docs/agent/CORE_RULES.md`、`docs/agent/DEVELOPMENT_WORKFLOW.md`
- `TASK_REGISTRY.md`（见下注）、`CURRENT_STATE.md`（见下注）
- 本次任务书与相关既有报告

注：本规范生效时仓库尚未建立 `TASK_REGISTRY.md` 与 `CURRENT_STATE.md`。在其建立之前，当前任务状态以 `docs/development_reports/`、`CHANGELOG.md` 与 `git log` 的事实为准（先例：TASK_DOC_007 报告即按此恢复上下文）。建立该两份文件是后续治理任务，不在 GOV_DOC_001 范围内。

### 3.2 开发过程中

1. 一个任务同一时间只有一个负责节点 / 一个负责 Agent；需要换节点或换 Agent 时，先按 §3.3 完整离场，再在新节点按 §3.1 入场。
2. 避免多个设备同时修改同一模块；如不可避免，事先划分文件边界，各自小步提交，靠普通 merge 汇合。
3. 任务编号开工前必须做唯一性检索（`tasks/`、`reports/`、`docs/development_reports/`、`docs/reports/`、`git log`）；主线用 `TASK_DOC_NNN`，Agent 专属用 `TASK_DOC_<AGENT>_NNN`，治理用 `GOV_DOC_NNN`，维护用 `MAINT_DOC_NNN`，系列之间不得重号。
4. 任务范围、代码红线、测试、提交、报告全部遵守 `docs/agent/` 既有五件规范，不因多节点而放松。
5. 长任务中也要勤提交：每个语义完整的小步即提交，未推送的提交不视为已保存。

### 3.3 离开设备前（收工、换机、会话结束）

必须完成且确认成功：

```powershell
git status
git add <仅本任务相关文件>      # 禁止 git add -A / git add . 盲暂存
git commit -m "TASK_xxx: description"   # 或 GOV_/MAINT_ 前缀
git push origin master
git rev-parse HEAD             # 与 origin/master 复核一致
```

1. 推送后核对 `HEAD` 与 `origin/master` 一致，并把推送结果写入任务报告。
2. 未跑通测试、未写报告的任务不得标记完成离场。
3. 因故无法完成提交推送（断网、凭据失效等）时：保留工作区原样，在节点登记表或任务沟通中明确"该节点持有未推送改动"，恢复后第一件事完成推送；不得在另一节点重复实施同一改动。

## 4. Agent 规则（跨节点共性）

Agent 在任一节点执行任务时，统一遵守根目录 [`AGENT_WORKFLOW.md`](../../AGENT_WORKFLOW.md) 的六步流程（获取最新仓库状态 → 阅读项目规则 → 确认当前任务 → 修改代码 → 输出报告 → Commit/Push）。该文件与本规范配套：本文件管"节点之间"，AGENT_WORKFLOW.md 管"单个 Agent 在节点上怎么开工"。

附加要求：

1. Agent 开工先确认自己所在节点（机器名、路径、HEAD、是否 clean），并与 `DEVELOPMENT_NODES.md` 核对。
2. Agent 上下文丢失或会话重建后，以仓库为唯一恢复源，重新执行 §3.1，不凭记忆续作。
3. Agent 不得在节点之间搬运未入库文件（手工复制源码、补丁、输出物）；需要交接就先推送。
4. Agent 的接入配置（DSH patch、MCP server 命令等）属于节点本地配置，按 `integrations/` 下说明配置，不纳入仓库提交。

## 5. 冲突与异常处置

| 情况 | 处置 |
|---|---|
| `git pull` 提示远端领先 | `git fetch` → 阅读远端新增提交 → 普通 merge 整合，保留双方历史（先例见 `reports/TASK_DOC_TRAE_001_REPORT.md`） |
| 两个节点改了同一文件冲突 | 人工/任务提出者裁定，保留双方有效改动；禁止以"保留我的版本"覆盖远端 |
| 节点环境损坏 | 不抢救本地改动之外的任何东西：确认已推送内容齐全后，重新克隆 + 重建 `.venv`，按 MAINT 类任务出报告 |
| 任务书与仓库事实冲突 | 暂停，向任务提出者确认；冲突与裁定写入报告（CORE_RULES §1） |
| 凭据/SSH 失效 | 停止推送操作，重新登记密钥后再试；禁止把 token 写入 remote URL，禁止索取/提交凭据 |

## 6. 验收标准（GOV_DOC_001）

- [x] 多设备开发规范存在：本文件
- [x] Agent 流程明确：根目录 `AGENT_WORKFLOW.md`
- [x] 开发节点记录完成：`docs/governance/DEVELOPMENT_NODES.md`
- [x] 文档提交仓库：随 `GOV_DOC_001: Add multi machine development workflow` 提交
