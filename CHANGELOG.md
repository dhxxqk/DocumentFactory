# 更新记录

## Unreleased — 2026-09-19

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
