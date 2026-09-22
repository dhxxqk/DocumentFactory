# REPORTING_STANDARD.md — 开发报告标准

适用范围：所有 TASK 的完成报告。开发报告是任务验收的必要交付物，与代码改动同等重要。

## 1. 存放路径与命名

```text
docs/development_reports/TASK_xxx_REPORT.md
```

- 编号与任务书、Git 提交信息一致
- 历史任务报告（TASK_DOC_001～004、TASK_DOC_TRAE_001 等）仍保留在 `reports/`，**不迁移、不重命名**；`docs/development_reports/` 标准自 TASK_DOC_005 起生效
- 报告随任务代码在同一任务中提交

## 2. 报告模板

```markdown
# TASK Report

Task:

Date:

Agent:

## Summary

## Changed Files

## Test Result

## Git Commit

## Remaining Risks

## Next Suggestion
```

### 字段填写要求

- **Task**：任务编号与名称
- **Date**：实际完成日期（必要时带时区与时间戳）
- **Agent**：实际执行的 Agent / 模型名称；多 Agent 协作时全部列出并注明分工
- **Summary**：做了什么、RESULT（PASS / FAIL / CONDITIONAL）及判定依据
- **Changed Files**：新增 / 修改 / 删除文件逐项列出，路径相对工程根
- **Test Result**：按 `TESTING_RULES.md` 的四段格式（Test Command / Result / Failed Cases / Resolution）
- **Git Commit**：提交信息、分支、提交哈希（提交后据实回填）、推送状态
- **Remaining Risks**：剩余风险、未验证项、环境限制；无条件项写 `None`
- **Next Suggestion**：任务外发现的问题与后续建议（只建议，不在本任务动手）

## 3. 证据与诚实要求

- RESULT 必须有证据支撑：测试输出、命令退出码、实际哈希/路径
- 条件性通过（skip、缺渲染后端、缺凭据）只能标记为 CONDITIONAL 并说明条件
- 任务书与仓库事实冲突时，记录冲突、裁定过程与最终采用的编号/方案
- 未执行的步骤写"未执行"及原因，不留空、不编造
- 报告中引用的文件路径、数字、哈希必须来自本次实际执行
