# 更新记录

## 0.5.0-alpha — 2026-09-22

- 新增 Formatting Operation Layer（`src/document_factory/operations/`）：确定性、只执行、输入显式的公共格式操作底座，供规则引擎、模板引擎及未来 AI 调用方共享。
- 操作按对象分为 font（中西文字体、字号、粗体、斜体、下划线、颜色）、paragraph（对齐、行距、段前后、缩进）、style（Normal/Title/Heading1-3）、table（表格字体与对齐）、document（页面属性；页眉页脚预留未迁移）。
- 私有 OOXML 写入内核（有序元素插入、属性/开关写入、变更记录）与原子落盘（`write_package` / `atomic_text`）从 normalizer 下沉到 operations 层；normalizer 只保留规则判定与引擎编排，不再承担底层格式操作。
- Template Applier / Template Profile 不再导入 normalizer 任何私有函数，同时移除 `TEMPLATE_RULES` 伪规则 hack；规则流与模板流的变更记录结构、Rule 归属、报告字段保持不变。
- 纯架构重构：CLI 命令、MCP 三个工具、Template Profile schema、退出码与输出契约均未改变；既有 80 项测试全部通过，Template Demo 文本/段落/编号 XML 保持一致。
- 版本更新为 Python `0.5.0a1`（产品标识 v0.5-alpha）。

## Product direction update — 2026-09-21

- 明确采用“内容源 + 发布层”双层模型：Markdown 用于 AI、Git、结构化内容母版，不作为面向普通同事的最终交付格式。
- 正式交付以 DOCX 为主，PDF 用于只读发布与归档，HTML 作为可选浏览器预览格式。
- 明确 DocumentFactory 不应做简单 Markdown → Word 语法转换，而应执行“Markdown 语义 → 文档语义角色 → 规则/模板映射 → DOCX → Validation”的确定性流程。
- 长期支持同一份内容源切换公司模板、项目建议书模板、需求规格说明书模板等多种正式输出，保持内容与排版解耦。
- 后续架构增加 Semantic Parser、统一 Document Structure Model 与 Publisher 方向；现阶段不改变 v0.4-alpha 已有 Core 行为。

## 0.4.0-alpha — 2026-09-20

- 新增 Template Analyzer，提取页面、页眉页脚、Paragraph Style、表格样式/默认格式和编号使用事实。
- 新增 schema 1.0 `TemplateProfile`，支持 JSON 序列化、保存、读取、人工修改与版本控制。
- 新增最小 Template Apply：映射现有 Normal、Title、Heading 1/2/3，并迁移表格字体、字号和对齐。
- 复用现有 OOXML、`StyleResolver`、normalizer 写入与 lint 能力；不复制格式级联和审计逻辑。
- 新增 `template analyze` / `template apply` CLI、Python 结构化接口、迁移报告、真实 Demo 与自动测试。
- 保留输入与模板文件，输出新的 DOCX；不改文字、段落顺序、复杂编号、图片布局或页眉页脚。
- MCP 仍保持 v0.3-alpha 的三个工具，本版本不新增模板 MCP tool。
- 版本更新为 Python `0.4.0a1`（产品标识 v0.4-alpha）。

## 0.3.0-alpha — 2026-09-20

- 新增基于官方 MCP Python SDK 2.x 的本地 stdio Server 与 `document-factory-mcp` 入口。
- 第一版仅暴露 `format_document`、`audit_document`、`list_presets`，作为既有 Core 的薄适配层。
- MCP 返回简洁结构化计数、摘要与 deliverables，不复制 OOXML/lint/normalize 逻辑或返回完整 findings。
- 增加官方 MCP client 的真实 subprocess 协议测试，覆盖 initialize、tools/list、三个工具、中文/空格路径、产物、输入保护和错误传播。
- 增加 DSH 官方 `@deepseek-ai/dsh-mcp-client` stdio patch 模板及 web/headless 配置说明。
- 正式样本通过 MCP 实测 ERROR 42→3、WARNING 20→20，并生成新 DOCX 与 Markdown Validation Report。
- 本机 DSH headless 因缺少 `DEEPSEEK_API_KEY` 在模型回合前返回 `MISSING_CREDENTIAL`；Agent 自动调用与 present 验收据实保留为条件项。
- 版本更新为 Python `0.3.0a1`（产品标识 v0.3-alpha）。

## 0.2.0-alpha — 2026-09-20

- 新增规则驱动的确定性 DOCX normalization Core 与 Python `normalize(...)` 结构化接口。
- 新增 `document-factory normalize` CLI、机器友好摘要，以及中文 Markdown + JSON Validation Report。
- 规范化明确的 Heading 1/2/3、正文和表格段落样式/Run；不重分类疑似语义，不修改编号或 TOC。
- 使用临时 ZIP 与原子替换生成新 DOCX，禁止覆盖输入，前后验证输入 SHA-256，并逐项保留未修改 ZIP 部件。
- 每次规范化自动执行 lint before / lint after，完整返回修改明细和剩余 ERROR/WARNING/UNSUPPORTED。
- TEST_CASE_001 实测 ERROR 由 42 降至 3，WARNING 保持 20；FONT001 37 和 STYLE005 2 均归零，保留范围外 NUM002 3。
- 自动测试增至 74 项，覆盖输入保护、未知部件、允许的三类语义对象、禁止重分类、编号/TOC 保持、幂等性、旧规则 lint 兼容和报告契约。
- 版本更新为 Python `0.2.0a1`（产品标识 v0.2-alpha），为 TASK_DOC_003 的薄 MCP 适配提供稳定 Core 契约。

## Direction decision — 2026-09-19

- 确认 DocumentFactory 的长期定位：从只读 DOCX 审计工具演进为“文档分析 + 规范化 + 验证”核心引擎。
- 明确核心引擎与 CLI、DeepSeek Harness、Codex、WPS/Word 插件等入口分离，避免绑定单一办公软件。
- 决定后续采用规则 / preset 驱动，先识别 Title、Heading、Body、Table、Caption 等语义角色，再进行确定性的格式规范化。
- 保留 v0.1 只读 lint / audit 作为安全基座；未来自动修复默认输出新 DOCX，并在修复后重新审计生成 Validation Report。
- Word-Formatter-Pro 等项目仅作为架构参考实现，不作为 DocumentFactory 的产品定位或强制运行时依赖。
- 下一阶段 TASK_DOC_002 聚焦最小闭环：识别结构 → 读取规则 → 规范化字体/字号等可确定格式 → 输出新 DOCX → 再审计验证。

## 0.1.0 — 2026-09-19

- 建立分层 Python 工程与 `lint`、`render`、`audit` CLI。
- 原样导入 V1.4 正式规范和 TEST_CASE_001，记录源文件与项目副本 SHA-256。
- 从 OOXML 解析节、段落、Run、样式、表格、合并单元格、域、关系、页眉页脚和脚注。
- 实现样式继承、字符样式、直接格式、主题字体、字体脚本及属性来源分析。
- 实现多级编号、真实 TOC、正文、表格、标题颜色、页面及前置标题的结构检查。
- 增加中文 Markdown / JSON 报告和可追踪的 YAML 规则配置。
- 实现 LibreOffice / Word COM 私有副本导出、PyMuPDF 逐页 PNG、超时和明确失败状态。
- 排除 WPS 兼容注册造成的 Word 后端误判；无后端时返回 RENDER_UNAVAILABLE。
- 增加自动回归测试和正式样本实际审计报告；原生 DOCX 渲染仍待具备 Office 后端的环境验收。
- 未实现自动修复、母版、字体修改、编号修复、AI 视觉审美或模型 API 接入。
