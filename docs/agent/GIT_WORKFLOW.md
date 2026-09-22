# GIT_WORKFLOW.md — Git 工作流规则

适用范围：所有 Agent 在 DocumentFactory 仓库中的提交与推送操作。

## 1. 提交信息

格式：

```text
TASK_xxx: description
```

示例：

```text
TASK_DOC_005: Introduce Agent Governance Layer
```

- 编号必须与任务书、开发报告一致，且已通过编号唯一性检查（见 DEVELOPMENT_WORKFLOW.md）
- description 使用简洁祈使句，说明"做了什么"，不写空泛描述
- 一个任务对应一个或少量语义清晰的提交；不得把无关改动夹带入同一提交

## 2. 提交前必须检查

```powershell
git status
git diff
git diff --staged
```

确认：

- 改动文件全部属于本任务范围
- 仅暂存本任务相关文件；不使用 `git add -A` / `git add .` 式盲目暂存
- 没有临时文件、调试代码、注释掉的代码块

## 3. 禁止提交的内容

- 临时文件与本地调试产物
- 运行生成文件：`output/` 下的输出、渲染产物、pytest 缓存（已由 `.gitignore` 覆盖，仍需人工复核）
- 个人配置、IDE 配置、虚拟环境、凭据与密钥（`.env`、`token*`、`secrets*` 等）
- `reports/` 下的机器生成 JSON（`.gitignore` 已有白名单例外：`BASELINE_HASHES.json`、`template_demo_profile.json`）
- 未验证的改动或与任务无关的文件

## 4. 历史与推送纪律

- 不对已推送的提交执行 `rebase`、`amend`、`reset --hard` 或 force push
- 远端领先时：`git fetch` → 阅读远端新增提交 → 普通 `merge` 整合，保留双方完整历史（先例见 `reports/TASK_DOC_TRAE_001_REPORT.md`）
- push 一律使用 SSH（`git@github.com:dhxxqk/DocumentFactory.git`），不使用 HTTPS
- 推送后复核 `HEAD` 与 `origin/master` 一致，并将结果写入报告

## 5. 提交内容真实性

- 只提交实际运行验证过的内容
- 不把未完成、未验证的工作标记为完成提交
- 提交后若发现报告需要回填（如提交哈希），使用独立的 docs 提交补充，不改写已形成的提交历史
