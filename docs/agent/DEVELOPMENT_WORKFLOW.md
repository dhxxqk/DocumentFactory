# DEVELOPMENT_WORKFLOW.md — 标准 TASK 开发流程

适用范围：所有 Agent 在 DocumentFactory 中执行的任务。配合 `CORE_RULES.md` 使用；流程中的测试、提交、报告环节分别遵守对应专项规则。

## 1. 标准流程

```text
TASK Receive
  ↓
Repository Inspection
  ↓
Implementation Plan
  ↓
Code Modification
  ↓
Testing
  ↓
Review
  ↓
Report
  ↓
Commit
```

### 1.1 TASK Receive（接收任务）

- 完整阅读任务书，记录任务编号、目标、验收标准与禁止事项
- **校验任务编号唯一性**：在 `tasks/`、`reports/`、`docs/development_reports/` 与 `git log` 中检索该编号，确认未被占用；发现冲突立即停止并向任务提出者确认
- 主线任务使用 `TASK_DOC_NNN`（三位数字顺序取号，不复用、不跳号）；Agent 或工具专属任务使用 `TASK_DOC_<AGENT>_NNN`（先例：`TASK_DOC_TRAE_001`）
- 任务书文件放 `tasks/TASK_xxx.md`；若任务书由外部对话给出未入库，至少在开发报告中完整登记任务目标与范围

### 1.2 Repository Inspection（检查仓库）

- `git status`、`git log --oneline -10`，确认工作区干净、了解近期变更
- 阅读 `README.md`、相关 ADR（`docs/`）与任务相关代码、测试
- 不以任务描述的背景陈述替代检查（仓库才是事实源）

### 1.3 Implementation Plan（制定方案）

- 列出计划新增/修改/删除的文件清单与影响范围
- 识别风险点与需要保留的契约（输入保护、退出码、MCP 工具边界等）
- 需求或边界不清时先提问，不用猜测填补

### 1.4 Code Modification（代码修改）

- 按方案做最小必要修改，不触碰无关模块
- 不引入未验证依赖；依赖变更必须在任务书中明确批准
- 保持入口层薄适配、Core 确定性逻辑的既有分层

### 1.5 Testing（测试）

- 遵守 `TESTING_RULES.md`：新功能加测试，改代码跑全量测试，失败先分析
- 纯文档任务也应运行一次测试，用于证明对现有代码无影响

### 1.6 Review（自检）

- `git status` 与 `git diff`（含暂存区）逐项核对
- 确认：改动仅限任务范围、无临时/生成/个人文件、没有夹带无关修改
- 确认没有为让测试通过而删改测试

### 1.7 Report（报告）

- 按 `REPORTING_STANDARD.md` 在 `docs/development_reports/` 生成 `TASK_xxx_REPORT.md`
- 报告内容如实回填；拿不到的数据标注"未执行/不适用"及原因，不编造

### 1.8 Commit（提交）

- 按 `GIT_WORKFLOW.md` 暂存与提交，信息格式：`TASK_xxx: description`
- 报告文件与代码改动在同一任务中提交

## 2. 任务暂停条件

出现以下情况时暂停并向任务提出者确认，不得自行推进：

- 任务编号冲突或任务书与仓库事实矛盾
- 任务要求触碰禁止事项（改业务代码之外的红线、绕过 Core、引入未批准依赖等）
- 按任务书实施会破坏既有契约或导致测试被删改
- 发现任务范围之外的严重既有缺陷
