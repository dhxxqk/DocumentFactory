# ADR-001：DocumentFactory 产品与架构演进方向

状态：Accepted  
决定日期：2026-09-19  
适用范围：DocumentFactory v0.2 及后续版本

## 1. 背景

DocumentFactory v0.1 已建立只读 DOCX 审计基础：OOXML 解析、结构识别、规则检查、Markdown/JSON 报告、CLI 以及可选渲染后端。

下一阶段需要解决的核心问题不再只是“发现格式错误”，而是让 AI 工作流能够安全、确定地把格式混乱的 DOCX 规范化，并验证修改是否真正符合既定规范。

与此同时，用户当前主要使用 WPS，但项目未来还需要被 DeepSeek Harness、Codex、CLI 和可能的桌面工具调用。因此不能把核心能力直接设计成 WPS 专用插件。

## 2. 决策

DocumentFactory 的长期定位确定为：

**一个独立的文档分析、规范化与验证核心引擎。**

WPS、Word、CLI、DeepSeek Harness、Codex 或其他 Agent 均属于入口层，而不是核心实现本身。

目标架构：

```text
                ┌─ CLI
                ├─ DeepSeek Harness / Agent Skill
                ├─ Codex / Tool / MCP
Input DOCX ──→ DocumentFactory Core
                ├─ Desktop / Drag & Drop
                └─ WPS / Word Add-in（未来可选）
```

核心内部采用：

```text
Document Analyzer
→ Document Structure Model
→ Formatting Rules / Preset
→ Normalization Engine
→ Validation
→ DOCX Output + Report
```

## 3. 必须遵守的原则

### 3.1 审计与修复分离

v0.1 的 lint / audit 不被替代。未来 normalization/fix 必须建立在可审计结构之上。

推荐闭环：

```text
lint before
→ normalize
→ lint after
→ validation report
```

### 3.2 不直接覆盖原文件

任何自动规范化操作默认生成新的 DOCX。原始输入应保持不变，并继续保留哈希、路径和输出边界保护。

### 3.3 规则配置化

字体、字号、行距、段距、缩进、标题级别、表格格式等要求不得散落写死在入口代码中。

正式规范仍是规则真源；机器配置 / preset 只负责映射和执行。

### 3.4 基于语义角色执行

禁止采用“全文统一成一个字体/字号”的粗粒度方案。

至少考虑以下角色：

- Title
- Subtitle
- Heading 1
- Heading 2
- Heading 3
- Body
- Table Header
- Table Body
- Caption
- Quote
- Header
- Footer

只有识别结果足够确定时才自动修改；不确定对象保留原状并进入 Validation Report。

### 3.5 AI 负责意图，不负责底层排版

AI 可以决定使用哪个 preset、要求执行哪种规范化任务，并解释审计结果；实际 OOXML 修改应由可测试、确定性的 DocumentFactory Core 完成。

### 3.6 WPS / Word 不作为核心依赖

当前用户主要使用 WPS，但核心仍优先采用 OOXML/Python 实现。

只有遇到 OOXML 层难以安全实现或必须依赖排版引擎的功能时，才引入 Word/WPS 作为可选高级后端。

### 3.7 修复后必须验证

“文件成功生成”不等于“格式正确”。

每次规范化至少输出：

- 输入文件
- 输出文件
- 使用的规则 / preset
- 已修改对象数量与类型
- 修复前问题
- 修复后剩余 ERROR / WARNING / UNSUPPORTED
- 无法自动确定的对象
- 输入与输出哈希

## 4. 外部项目参考策略

Word-Formatter-Pro 等现有工具可作为参考实现，重点研究：

- Core 与 GUI / CLI / Agent 入口分离
- 配置驱动
- 原始文档保护
- 批量格式处理
- CLI 可调用性

DocumentFactory 不以“复制第三方工具”为目标，也不把其作为强制依赖。若未来复用任何第三方代码，必须单独核对许可证、版权声明和适用范围。

## 5. 下一阶段：TASK_DOC_002

TASK_DOC_002 的目标不是完成一个完整排版软件，而是先打通一个可验证的最小闭环：

```text
输入 DOCX
→ 识别正文 / 标题 / 表格
→ 读取 preset / rules
→ 规范化可确定的字体、字号等基础格式
→ 生成 *_formatted.docx
→ 再次 lint / audit
→ 生成 Validation Report
```

TASK_DOC_002 暂不优先实现：

- GUI
- WPS 插件
- Word 插件
- LLM 直接修改 OOXML
- 复杂视觉审美调整
- 无法验证的“智能美化”

## 6. 预期结果

完成该方向后，DocumentFactory 应支持类似以下调用：

```text
documentfactory normalize input.docx --preset grid_tech_v1_4
```

未来 Agent 的自然语言调用可简化为：

> 把这个文档按“电网科技项目实施方案 V1.4”统一格式，并告诉我还有哪些格式无法自动修复。

核心价值由“检查文档”升级为：

**检查 → 规范化 → 再检查 → 给出可追踪结果。**
