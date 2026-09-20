# TASK_DOC_002：DOCX 确定性规范化最小闭环

状态：Ready
优先级：P0
目标版本：v0.2-alpha
前置任务：TASK_DOC_001
架构依据：docs/ADR_001_DOCUMENTFACTORY_DIRECTION.md

## 1. 目标

在 v0.1 只读审计基础上新增确定性规范化：输入 DOCX → 修复前 lint → 按 rules 规范化可确定格式 → 输出新 DOCX → 修复后 lint → Validation Report → 结构化结果供后续 MCP/Agent 调用。

本任务不实现 WorkBuddy / DSH MCP Server；必须先提供稳定 Core 与 Python 调用契约，TASK_DOC_003 再做薄 MCP 适配。

## 2. 原则

- 保留现有 lint / render / audit，不破坏 v0.1。
- 禁止覆盖输入文件，前后校验输入 SHA-256。
- 修复与审计使用同一份 rules 语义，不建立第二套格式标准。
- 只修改语义可确定对象；不确定对象不猜、不修，进入报告。
- Agent 不参与底层 OOXML 决策。
- 优先复用现有 lxml / OOXML 体系，不另起互相冲突的文档语义模型。

## 3. 本轮允许自动规范化

### Heading 1 / 2 / 3

仅处理现有 StyleResolver 明确认定的真实 Heading：按 rules 设置中文字体、字号和纯黑颜色，并修复明确冲突的 Run 直接格式或主题字体覆盖。不得把疑似标题自动升级为 Heading。

### 正文

仅处理明确使用 rules 中正文样式的段落与 Run：中文仿宋、拉丁 Times New Roman、12pt、首行缩进 2 字符、1.5 倍行距、段前段后 0、两端对齐。长 Normal 段落疑似正文不得自动转换。

### 表格

仅处理明确使用表格表头、表格正文、表格正文-居中等既有确定样式的对象：表头黑体、表体仿宋、拉丁 Times New Roman、10.5pt、缩进 0、段前段后 0。疑似表头不得自动套样式。

## 4. 本轮禁止自动修复

- 自动多级编号、numId、lvlOverride
- 手工编号转自动编号
- TOC 创建、重建或刷新
- Normal 转正文、疑似标题转 Heading
- 编制说明、目录标题、封面等语义重分类
- 复杂条件表格样式
- 文本框、浮动对象、修订、RTL、复杂文字
- 图片中文字
- 视觉美化
- 任何无法被现有 lint 再验证的修改

## 5. Core 与接口

建议新增 normalizer.py，并在 models.py 增加 NormalizationResult。返回结果至少包括：status、input_path、output_path、report_path、input_sha256、output_sha256、before_counts、after_counts、changes、remaining_findings、source_unchanged。

changes 至少记录 object_type、location、property、before、after、rule/source。

必须提供无需解析 CLI 文本的 Python 入口：normalize(input_path, rules_path, output_path=None, report_path=None)。核心逻辑不得塞进 CLI。

## 6. CLI

新增 document-factory normalize INPUT.docx --rules rules/grid_tech_v1_4.yaml --output output/normalized/INPUT_formatted.docx --report reports/INPUT_NORMALIZATION_REPORT.md。

CLI 至少打印机器友好摘要：STATUS、OUTPUT、REPORT、BEFORE_ERROR、AFTER_ERROR、CHANGED。

## 7. 输出安全

- 默认生成到 output/normalized。
- 绝不覆盖输入。
- 使用临时文件和安全落盘，避免半个 ZIP。
- 未修改 OOXML/ZIP 部件必须保留。
- 输入操作前后 SHA-256 必须一致。
- 输出必须可再次由 read_docx 正常读取。

## 8. Rules

rules/grid_tech_v1_4.yaml 同时作为 lint 规则源和 normalize 目标格式源。字体、字号、颜色、缩进、行距等目标禁止在 normalizer 中重新硬编码。如果需要 fix 元数据，可以向 YAML 增加向后兼容字段，但不得破坏现有加载和测试。

## 9. Validation Report

每次 normalize 必须自动执行 lint(input) → normalize → lint(output)，生成中文 Markdown + JSON。报告至少包含：实际生成时间和时区、输入输出路径、输入输出 SHA-256、规则文件及规则 SHA-256、修复前后 ERROR/WARNING/INFO、修改统计与明细、剩余 ERROR/WARNING/UNSUPPORTED、明确列出本轮不自动修复项。

不得因为 ERROR 数下降就宣布全部格式合格，最终结论以 after lint 真实结果为准。

## 10. 测试

现有 TASK_DOC_001 全部测试必须继续通过，当前基线为 62 passed，实际以执行时最新数量为准。

新增测试至少覆盖：输入不变、禁止覆盖输入、输出可读、未知 ZIP 部件保留、Heading 1/2/3 修复、正文修复、确定表格样式修复、Normal 疑似正文不自动转换、疑似标题不自动转换、编号和 TOC 不被擅改、二次 normalize 幂等、before/after counts 与真实 lint 一致、Validation JSON 可稳定读取。

## 11. TEST_CASE_001 真实验证

必须对正式样本执行真实 normalize。v0.1 基线 ERROR=42、WARNING=20，已知 ERROR 主要为 FONT001=37、STYLE005=2、NUM002=3。

本任务预期是：属于本轮明确修复范围的 FONT001 / STYLE005 显著减少或归零；NUM002 等排除项保持真实可追踪。不得通过删除检查、降低 severity 或破坏结构制造好看的结果。实际结果不同则按证据解释，禁止硬编码计数。

## 12. 文档与报告

完成后更新 README.md、CHANGELOG.md、版本号，并新增 reports/TASK_DOC_002_REPORT.md。报告必须写实际生成时间、PASS/CONDITIONAL PASS/FAIL、实际修改文件、测试结果、TEST_CASE_001 前后结果、未支持能力、TASK_DOC_003 MCP 接入准备情况。

## 13. 验收

只有同时满足以下条件才可 PASS：normalize CLI 可运行；Python normalize 返回结构化结果；输入 SHA-256 不变；输出为新的有效 DOCX；输出可被现有 lint 再审计；只修改允许范围；不通过降级规则制造 PASS；新旧测试全部通过；TEST_CASE_001 完成真实 normalize 并留报告；README/CHANGELOG/TASK_DOC_002_REPORT 完成。

Office/WPS/LibreOffice 不可用不影响本任务 OOXML 规范化验收，不得伪造视觉渲染成功。

## 14. Git

从最新 origin/master 开始，不重写历史，不 force push，不删除 TASK_DOC_001 证据。测试和真实样本验证后提交。建议 commit：feat: add deterministic DOCX normalization pipeline。有凭据时 push origin/master；push 失败必须在报告中写真实原因。

## 15. 明确不做

GUI、WPS 插件、Word 插件、MCP Server、HTTP API、云服务、LLM API、AI 审美、自动重写标题层级、自动修编号/TOC、一键美化全部格式均不属于本任务。

本任务唯一重点：建立一个安全、确定、可验证、可被 Agent 调用的 DOCX normalize Core。
