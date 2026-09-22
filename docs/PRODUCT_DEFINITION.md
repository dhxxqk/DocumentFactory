# DocumentFactory 产品定义 v1.0

状态：Accepted  
日期：2026-09-22（TASK_DOC_007）  
适用版本：v0.5-alpha 及后续版本

本文件是 DocumentFactory 的权威产品定义。历史方向讨论（如 `docs/DOCUMENTFACTORY_PRODUCT_DESIGN_V1.md`、`docs/ADR_001_DOCUMENTFACTORY_DIRECTION.md`）保留作为决策记录；与本文件冲突时，以本文件为准。

## 1. 产品定位

DocumentFactory 是一个面向 AI 生成内容的 **DOCX 文档生成、格式规范化和质量验证引擎**。

通过 OOXML 解析、规则驱动审计、模板迁移、确定性格式修复和渲染验证，解决 AI 生成 Word 文档过程中出现的格式漂移、模板失效和排版不一致问题。

一句话边界：

> **这是一个 DOCX 工厂，不是 PPT 工厂，不是图片工厂，也不是通用 AI 办公平台。**

分工模型：

- 内容由 GPT、DeepSeek 等 AI Agent（或人工）生产，DocumentFactory 不做内容创作。
- DocumentFactory 接收 DOCX、Markdown / 结构化内容、格式规则或参考模板，输出符合规范的新 DOCX 与可验证报告。
- AI 负责意图与编排；确定性 OOXML 修改只允许由 DocumentFactory Core 完成，Agent 不得绕过 Core 直接改 OOXML。

## 2. 用户痛点

- AI 生成的 Word 文档字体、字号、行距、标题层级不一致，人工返工成本高。
- 套用公司 / 项目模板时样式失效、编号错乱、表格格式不统一。
- “文件已生成”无法证明“格式正确”，缺少修复前后的可追踪证据。
- 同一内容源需要按不同单位、不同场景输出多种正式文档，重复排版。
- 现有办公软件操作依赖人工 GUI，无法进入 Agent 自动化工作流，也无法批量、可重复执行。

## 3. 核心能力

当前已具备（v0.5-alpha）：

| 能力 | 说明 |
|---|---|
| DOCX 结构解析 | 只读 OOXML 解析：节、段落、Run、样式、表格、编号、域、页眉页脚 |
| 规则驱动审计（lint / audit） | 基于 YAML 规则与正式 Markdown 规范，输出带 Rule ID、严重等级、定位与规范出处的 Markdown / JSON 报告 |
| 确定性格式修复（normalize） | lint before → 确定性修复 → lint after → Validation Report；绝不覆盖输入，修复幂等 |
| Word 模板分析（template analyze） | 提取页面、页眉页脚、样式、表格与编号事实，生成 schema 版本化、可人工编辑的 Template Profile |
| DOCX 模板迁移（template apply） | 按语义角色映射 Normal / Title / Heading 1-3 及表格字体与对齐，输出新 DOCX 并做 Profile 精确验证 |
| Formatting Operation Layer | 规则引擎与模板引擎共享的确定性格式执行底座（font / paragraph / style / table / document） |
| 渲染验证 | LibreOffice → Word COM 后端探测，导出 PDF / 逐页 PNG（依赖本机具备渲染后端） |
| MCP 接口 | 本地 stdio MCP，三个薄适配工具：`format_document`、`audit_document`、`list_presets`，供 AI Agent 调用 DOCX 格式治理能力 |

计划中（见第 6 节路线）：Markdown / 结构化内容 → DOCX 生成、模板驱动文档生成、企业规则包。

## 4. 非目标（Non-Goals）

以下能力明确不属于 DocumentFactory，将在独立项目中实现：

- **PPT 生成与模板设计**：不做幻灯片、演示模板、Presentation 处理。
- **图片生成**：不生成或编辑位图 / 图表素材。
- **内容创作**：不调用 LLM 写正文、不做语义改写、不做 OCR；内容来自外部 Agent 或人。
- **项目知识管理 / AI 知识库**：不做文档入库、检索、知识图谱。
- **通用 Agent 记忆系统**：不做跨会话记忆、上下文存储、Project Context。
- **通用办公 Agent / 工作流平台**：不做对话入口、任务编排、GUI 工作台（如 WorkBuddy 属于独立项目）；MCP 仅是 DOCX 能力的适配接口，不使本项目成为 Agent 平台。
- WPS / Word 插件、HTTP / 云服务形态不属于当前核心；渲染后端（LibreOffice / Word）只是可选验证手段，不是产品依赖。

判据：凡是不直接服务于“DOCX 的生成、格式治理与质量验证”的能力，默认不进入本项目。

## 5. 技术路线

- **确定性优先**：所有修改由规则或模板显式驱动，可重复、幂等、可被 lint 再验证；不确定对象保留原状并进入报告，不靠猜测修复。
- **审计与修复分离**：lint / audit 保持只读；修复默认输出新 DOCX，原始输入只读且受哈希保护。
- **规则配置化**：正式 Markdown 规范是规则真源，YAML 只是机器映射；规则修改先核对规范文本。
- **语义角色驱动**：按 Title / Heading / Body / Table 等角色处理，不做“全文统一一个字体”的粗粒度方案。
- **内容与排版解耦**：Markdown / 结构化内容作为内容母版，经“语义 → 角色 → 规则/模板映射 → DOCX → 验证”生成正式文档，支持一份内容切换多种模板。
- **薄入口、厚核心**：CLI 与 MCP 都是薄适配层；业务逻辑只在 Core 与 Formatting Operation Layer。
- **安全基座**：OOXML 解析禁用外部实体 / DTD / 网络，限制包大小与部件数，宏与外部内容不执行。

## 6. 后续规划（Roadmap）

### Phase 1：DOCX Core（已完成，v0.1–v0.5-alpha）

DOCX 解析、格式审计、规则驱动自动修复、模板分析与迁移、MCP 薄适配、Formatting Operation Layer。

### Phase 2：DOCX Generation（计划）

- Markdown / 结构化内容生成 DOCX（Semantic Parser → 统一 Document Structure Model）。
- 模板驱动文档生成：一份内容源切换公司模板、项目建议书、需求规格说明书等正式输出。
- 生成后自动验证闭环；可选 PDF / HTML 发布层。

### Phase 3：Enterprise Rule Packages（计划）

- 电网规范（现有 `grid_tech_v1_4` 持续完善）。
- 企业模板与企业规则包。
- 论文 / 院校格式等可分发规则包。

路线中**不包含** PPT 路线与通用 AI 工作流 / Agent 平台路线；相关能力在独立项目中发展。

### 近期任务序列

- TASK_DOC_008（建议）：Template Library + Registry。
- 其后：Document Structure Mapping，以及样式导入、页面 / 页眉页脚迁移深化（依赖渲染环境就绪）。

## 7. 验收标准

本产品定义在以下条件全部满足时视为落地：

1. README 第一屏明确说明：DocumentFactory 是 DOCX 工厂，不是 PPT 工厂或通用 AI 办公平台。
2. README 包含 Product Scope（支持范围 / 不支持范围）与三阶段 Roadmap。
3. MCP 相关描述被限定为“AI Agent 调用 DOCX 格式治理能力”的接口，不出现通用 Agent 平台表述。
4. 历史讨论文档保留原文，并加注记指向本文件、声明越界能力归属独立项目。
5. 本定义为纯文档调整，不修改任何业务代码；全量 pytest 保持通过（基线 89 项）。
6. 后续新任务的范围评审以本文件第 4 节非目标清单为准：越界需求默认拆到独立项目。
