# DocumentFactory 产品设计方向 V1

状态：Accepted（历史讨论文档，原文保留）  
首次日期：2026-09-20  
最近更新：2026-09-21

> **边界注记（2026-09-22，TASK_DOC_007）：** 本文档为历史方向讨论，保留原文以记录决策演进。当前权威产品定义以 [PRODUCT_DEFINITION.md](PRODUCT_DEFINITION.md) v1.0 为准：DocumentFactory 只解决 Word / DOCX 的生成、转换与格式治理。本文档第 4 节出现的 WorkBuddy 等通用 Agent 入口，以及 PPT 生成、图片生成、项目知识管理、通用 Agent 记忆系统等能力，**均不属于本项目，未来在独立项目中实现**。第 6 节的 TASK 编号为当时的历史规划，已不代表当前编号序列。

## 1. 产品定位

DocumentFactory 不定位为传统 Word 排版软件，而定位为：

> AI 工作流中的文档格式迁移、规范化与发布引擎。

用户可以提供原始 DOCX，也可以提供 Markdown / 结构化内容，以及格式要求或参考模板。DocumentFactory 负责把“内容语义”与“最终排版”解耦，自动输出符合要求的新文档。

核心体验：

输入：
- 原始 DOCX；或 Markdown / 结构化内容
- 格式规则，或模板 DOCX

输出：
- 规范化后的 DOCX
- 格式验证报告
- 可选 PDF / HTML 发布件

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

## 3. 内容源与发布层：双层模型

### 3.1 核心原则

**Markdown 是内容源 / AI 工作格式，不是面向普通同事的最终交付格式。**

DocumentFactory 采用“源文件 + 发布文件”的双层模型：

- Markdown：作为内容母版、AI 上下文、Git 版本管理和结构化编辑格式。
- DOCX：作为同事协作修改、批注、正式流转和办公场景交付格式。
- PDF：作为只读查看、领导汇报、归档和正式发布格式。
- HTML：作为可选的浏览器快速预览与轻量发布格式。

不因为最终用户难以直接打开 Markdown 而放弃 Markdown；应由 DocumentFactory 解决发布层转换与排版质量问题。

### 3.2 与普通 Markdown → Word 转换的区别

DocumentFactory 不做简单的“语法格式转换”，而做：

> Markdown 语义 → 文档语义角色 → 模板 / 规则映射 → 正式 DOCX → 验证。

示例映射：

- `#` → Title / Heading 1
- `##` → Heading 2
- `###` → Heading 3
- 普通段落 → Body
- Markdown 表格 → Table Header / Table Body
- 图片说明 → Caption

字体、字号、行距、段前段后、首行缩进、编号、页边距、页眉页脚、表格样式等最终表现，不由 Markdown 自身决定，而由规则或目标 DOCX 模板决定。

### 3.3 推荐转换链路

```text
Markdown / Structured Content
        ↓
Semantic Parser
        ↓
Document Structure Model
        ↓
Formatting Rules / Template Profile
        ↓
DOCX Generator / Normalizer
        ↓
Validation
        ↓
DOCX
        ├── PDF
        └── HTML（可选）
```

### 3.4 一份内容，多种正式模板

长期目标应支持同一份内容源直接生成不同正式文档：

```text
content.md
   ├── 公司内部报告模板 → report_internal.docx
   ├── 国网项目建议书模板 → project_proposal.docx
   ├── 需求规格说明书模板 → srs.docx
   └── 投标技术方案模板 → bid_solution.docx
```

内容与排版分离，避免为了换模板而重新编辑正文。

## 4. 推荐用户工作流

用户不直接操作 DocumentFactory。

最终体验：

用户 → DSH / WorkBuddy → DocumentFactory → 新 DOCX + Report

示例：

“请按照去年项目建议书模板整理这个文档。”

Agent 自动：
1. 识别内容源与模板
2. 调用 DocumentFactory
3. 将 Markdown / DOCX 中的结构映射为文档语义角色
4. 应用目标模板或格式规则
5. 输出正式版 DOCX
6. 返回格式检查结果
7. 需要时继续生成 PDF / HTML 发布件

## 5. 长期架构

DocumentFactory：

- Analyzer：文档结构分析
- Semantic Parser：Markdown / 结构化内容语义解析
- Document Structure Model：统一文档语义模型
- Rules Engine：规则解析
- Template Engine：模板解析
- Normalizer / Generator：格式执行与 DOCX 生成
- Validator：结果验证
- Publisher：DOCX → PDF / HTML 等发布输出
- MCP Layer：Agent调用接口

## 6. 开发优先级

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

后续新增方向：
- Markdown / Structured Content → Document Structure Model
- 基于语义角色生成高质量 DOCX
- 同一内容源切换多个模板
- DOCX → PDF / HTML 发布层

## 7. 产品目标

DocumentFactory 最终目标不是“统一字体”，也不是一个简单的 Markdown → Word 转换器，而是：

> 将任意来源的文档内容，转换为符合指定组织规范或参考模板的正式文档，并提供可验证、可重复、可版本管理的发布结果。

最终应形成：

> **内容母版与发布格式解耦：Markdown 管内容，DocumentFactory 管正式文档。**
