# Development Nodes — 开发节点登记表

配套规范：[`MULTI_MACHINE_DEVELOPMENT_WORKFLOW.md`](./MULTI_MACHINE_DEVELOPMENT_WORKFLOW.md)

登记规则：

1. 每个参与开发的节点在此登记一节；节点上线、退役、路径/工具链变更时更新本表并提交入库。
2. 统一本地路径：`E:\Project\DocumentFactory`；push 一律走 SSH。
3. 表中事实以该节点最近一次上线时实际核验为准；无法核验的字段写"待该节点上线核对"，不凭印象填写。

最近更新：2026-09-23 (+08:00)

## 节点总览

| 节点 | 机型 / 系统 | 用途 | 路径 | 状态 | 主要 Agent |
|---|---|---|---|---|---|
| Node-Desktop | 待该节点上线核对 | 主要开发（主力节点） | `E:\Project\DocumentFactory` | 在用（未于本次恢复中核验） | Codex / Trae / DSH |
| Node-Laptop | MSI Cyborg 15 A13VF / Windows 11 Home 26200 | 移动开发、第二开发节点 | `E:\Project\DocumentFactory` | 2026-09-23 恢复上线（MAINT_DOC_001，PASS） | Trae（已验证） |

## Node-Desktop

用途:

主要开发（主力节点）

路径:

`E:\Project\DocumentFactory`（多节点统一规范路径）

Agent:

Codex（任务书指定主力）；据 `docs/development_reports/TASK_DOC_007_REPORT.md`，Trae 亦曾在该节点执行任务

待该节点下次上线核对项（本次恢复无法从笔记本核验，按 CORE_RULES 不猜测）:

- 实际工作路径：任务书规范为 `E:\Project\DocumentFactory`；`README.md` 历史记载为 `G:\Workflows\DocumentFactory`，以节点实测为准并回填本表
- 机型 / OS / Python 小版本 / `.venv` 依赖版本
- SSH 远程 URL 与推送身份
- Codex、DSH 的实际安装版本

## Node-Laptop

用途:

移动开发，可独立运行项目的第二开发节点

设备 / 系统:

Micro-Star International Cyborg 15 A13VF；Microsoft Windows 11 家庭版中文版（Build 10.0.26200）；本机用户 清能互联-覃恳；COMPUTERNAME=MSI

路径:

`E:\Project\DocumentFactory`（恢复时 HEAD `f3a48661a72a8e29445766c076ca68f2bd19a884`，clean，与 origin/master 一致）

环境:

- Python 3.13.1（`%LOCALAPPDATA%\Programs\Python\Python313\python.exe`，未加入系统 PATH）
- 工程根 `.venv`，`pip install -e ".[test,word,mcp]"`；CLI 版本 0.5.0a1
- 全量验证：89 passed in 8.56s（2026-09-23）
- Git 2.55.0 + OpenSSH 9.5p2；ed25519 密钥（无密码，注释 dhxxqk@gmail.com）已于 2026-09-23 登记到 GitHub
- GitHub CLI 已安装、未登录

Agent:

- Trae：已安装并验证（执行 MAINT_DOC_001 / GOV_DOC_001）
- Codex：未安装
- DeepSeek Harness：未安装（Node.js 已具备，接入见 `integrations/dsh/`）

已知条件项:

- 无 LibreOffice / Microsoft Word 渲染后端，渲染相关验收延续 RENDER_UNAVAILABLE 基线
- 与任务书 3.10.x 的偏差：本节点 Python 为 3.13.1（满足 `requires-python >= 3.10`，经任务提出者裁定接受）
