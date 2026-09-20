# DocumentFactory 产品设计方向 V1

状态：Accepted
日期：2026-09-20

## 1. 产品定位

DocumentFactory 不定位为传统 Word 排版软件，而定位为：

> AI 工作流中的文档格式迁移与规范化引擎。

用户提供原始文档，以及格式要求或参考模板，DocumentFactory 自动输出符合要求的新文档。

核心体验：

输入：
- 原始 DOCX
- 格式规则，或模板 DOCX

输出：
- 规范化后的 DOCX
- 格式验证报告

## 2. 两种工作模式

### 2.1 规则驱动模式（Rule Based）

输入：

原始文档 + 规则规范

例如：
- 国网项目建议书规范
- 电网需求规格说明书规范
- 科技论文格式规范

规则定义：
- 字体
- 字号
- 标题层级
- 段落格式
- 表格格式
- 页面布局要求

适用于固定标准场景。

### 2.2 模板驱动模式（Template Based）

输入：

原始文档 + 模板 DOCX

DocumentFactory 从模板中提取：
- Styles
- Heading体系
- 字体
- 段落规则
- 表格样式
- 页面布局
- 页眉页脚
- 编号体系

然后迁移到目标文档。

适用于：
- 公司模板
- 客户模板
- 历史优秀文档

## 3. 推荐用户工作流

用户不直接操作 DocumentFactory。

最终体验：

用户 → DSH / WorkBuddy → DocumentFactory → 新 DOCX + Report

示例：

“请按照去年项目建议书模板整理这个文档。”

Agent 自动：
1. 识别模板
2. 调用 DocumentFactory
3. 输出正式版 DOCX
4. 返回格式检查结果

## 4. 长期架构

DocumentFactory：

- Analyzer：文档结构分析
- Rules Engine：规则解析
- Template Engine：模板解析
- Normalizer：格式执行
- Validator：结果验证
- MCP Layer：Agent调用接口

## 5. 开发优先级

当前：

TASK_DOC_003_FIX
- 完成 DSH E2E 闭环

后续：

TASK_DOC_004
- 模板解析与模板驱动格式迁移设计

TASK_DOC_005
- 多规范管理与 preset 系统

TASK_DOC_006
- 工作流自动化

## 6. 产品目标

DocumentFactory 最终目标不是“统一字体”，而是：

> 将任何来源的 Word 文档，自动转换为符合指定组织规范或参考模板的正式文档。
