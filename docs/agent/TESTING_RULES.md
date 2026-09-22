# TESTING_RULES.md — 测试规则

适用范围：所有涉及代码修改的任务；纯文档任务参考第 4 节。

## 1. 基本要求

- **新功能必须增加测试**：测试与实现同任务提交，覆盖正常路径、边界与失败路径
- **修复缺陷优先先写复现测试**，再修复，证明测试从失败转为通过
- **修改已有功能必须运行全部已有测试**，不能只跑自己认为相关的子集
- 测试失败必须分析根本原因并在报告中说明；禁止：
  - 删除测试用例
  - 跳过（skip）失败测试而不说明原因
  - 弱化断言、降低 severity 或修改测试期望来"解决"失败
- 既有 skip 机制（如正式样本缺失时的条件跳过）必须保留其语义，skip 不计为通过

## 2. 测试命令

在工程根目录（`G:\Workflows\DocumentFactory`）执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

需要 JUnit 结果时：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q --junitxml=reports/pytest.xml
```

- `-X utf8` 用于避免 Windows 终端中文乱码
- 测试产生的临时文件必须落在 `output/`（已 gitignore）下的隔离目录，不得写入 `testcases/` 或覆盖正式样本
- 测试用例总数随版本演进变化；以本次实际执行结果为准，总数与历史基线不一致时必须在报告中解释原因

## 3. 报告格式

开发报告的 Test Result 一节至少包含：

```text
Test Command:

Result:

Failed Cases:

Resolution:
```

- Test Command：实际执行的完整命令
- Result：通过/失败数量与耗时，例如 `80 passed in 5.08s`
- Failed Cases：失败用例名称与原因；无失败写 `None`
- Resolution：失败的根因与处理；无失败写 `Not applicable`

## 4. 不涉及代码的任务

纯文档/治理类任务不新增测试，但应运行一次全量测试，证明本任务未影响现有代码；报告中据实记录结果，并注明"本任务不涉及代码修改"。

## 5. 依赖

- 不允许以"测试需要"为由引入未在任务书中批准的新依赖
- 新增依赖后须在报告中记录版本与来源，并在干净环境可复现安装
