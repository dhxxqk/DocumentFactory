# TASK_DOC_012 — Default Technical Document Specification Extraction

## 1. 任务概述

将 TASK_DOC_011 的具体业务模板（科研实施方案）上抽一层，形成
DocumentFactory 的**默认技术文档格式规范** `DEFAULT_TECHNICAL_DOCUMENT_V1`：
只保留与业务无关的通用格式事实，业务模板通过 `extends` 继承并扩展。

```
DEFAULT_TECHNICAL_DOCUMENT_V1（默认规范：页面/正文/标题/表格/题注）
        │
        └── GRID_RESEARCH_IMPLEMENTATION_PLAN_V1（extends 继承 + 业务扩展）
```

核心原则（任务书硬性要求）：

1. **不绑定业务内容**：默认规范资产不得出现具体项目名称、编号、
   单位名称、特定章节名或固定页眉文本；
2. **可被继承**：模板体系新增 `extends` 继承机制（深合并），
   业务模板只保留差异；
3. **可驱动 DOCX**：默认规范既能驱动 Markdown → DOCX 生成，
   也能驱动扁平 DOCX → 规范 DOCX 转换；
4. **规则分片**：规范事实按维度拆分为 page / paragraph / heading /
   table / figure 五个 YAML 分片，由 loader 组装。

设计文档：`docs/design/DEFAULT_DOCUMENT_STYLE_SPECIFICATION.md`。

> 编号说明：原"Word 格式转换流水线"占用 TASK_DOC_012（已推送 commit
> `934ec2f`、`51494b1`），经路线调整顺延为 TASK_DOC_013（重编号
> commit `9461c87`），本任务占用 TASK_DOC_012。已推送历史不改写。

## 2. 交付物

### 2.1 新增默认规范资产

| 文件 | 职责 |
| --- | --- |
| `templates/default_technical_document_v1/template.yaml` | 默认规范身份 + `rules_include` 分片组装声明 |
| `templates/default_technical_document_v1/definition/style_definition.yaml` | 规范主源（完整、去业务化，lint 契约 source 锚点） |
| `templates/default_technical_document_v1/rules/page_rules.yaml` | A4 / 页边距 / 页眉页脚距离 / 分节与页码策略 |
| `templates/default_technical_document_v1/rules/paragraph_rules.yaml` | 正文仿宋小四 1.5 倍 / Normal / 字体别名 / 字号映射 |
| `templates/default_technical_document_v1/rules/heading_rules.yaml` | Heading 1-3 黑体 16/14/12pt（不含任何业务章节） |
| `templates/default_technical_document_v1/rules/table_rules.yaml` | 表头黑体 / 表体仿宋 / 五号 / TableGrid |
| `templates/default_technical_document_v1/rules/figure_rules.yaml` | 题注黑体五号居中、图N-M/表N-M 章-序编号（资产储备） |
| `templates/default_technical_document_v1/examples/default_test.md` | 任务书指定的最小验证输入 |
| `templates/default_technical_document_v1/examples/default_test.docx` | 默认规范实际驱动生成的验证产物（1469 字节，可复读） |
| `templates/default_technical_document_v1/validation/VALIDATION_CHECKLIST.md` | 验收清单 |
| `rules/default_technical_document_v1.yaml` | 去业务化扁平 lint 契约（lint_engine/converter 直接消费） |

### 2.2 代码改动

- `src/document_factory/templates/schema.py`：`TemplateDefinition`
  新增可选字段 `extends: str | None`（from_dict 读取）；
- `src/document_factory/templates/loader.py`：
  - 新增 `deep_merge`（dict 递归合并，list/标量子替换）；
  - 新增 `_compose_rules`：按 `rules_include` 顺序深合并分片，
    内联 rules 优先级最高；
  - `build_registry` 改两阶段：先组装全部条目，再按 extends
    拓扑解析（不依赖目录顺序），缺失父模板/继承循环报
    `TemplateSchemaError`，重复 id 仍报 `TemplateAlreadyRegisteredError`；
  - `load_template_from_yaml` 对带 extends 的模板按兄弟模板目录解析。
- `templates/grid_research_implementation_plan_v1/template.yaml`：
  删除全部内嵌重复规则，改为 `extends: DEFAULT_TECHNICAL_DOCUMENT_V1`
  + 业务身份/业务 metadata（kind=business_extension、业务源文档、
  业务 lint 契约）。

### 2.3 测试

- 新增 `tests/templates/test_default_specification.py`（12 项）：
  注册、资产去业务化扫描、目录结构、格式事实、题注/页眉页脚抽象事实、
  业务模板继承一致性、Markdown 生成（标题/正文 XML 字体字号 +
  sectPr 页边距 twips）、扁平 DOCX 转换（DFBody/DFHeading/
  DFTableHeader/DFTableBody 字体）、缺失父、继承循环、
  独立 YAML 解析、子覆盖优先级；
- 011 既有资产测试 `tests/test_template_asset_grid_research.py`
  未改一行，4 项全部继续通过。

## 3. 关键格式事实（默认规范）

| 维度 | 事实 |
| --- | --- |
| 页面 | A4 纵向 11906×16838；边距 上2.8 / 下2.6 / 左2.8 / 右2.6 cm；页眉页脚距边界 1.4 cm |
| 正文 | 仿宋 + Times New Roman，小四 12pt，1.5 倍行距，首行缩进 2 字符，两端对齐，段前后 0 |
| H1/H2/H3 | 黑体 + TNR，16 / 14 / 12pt，黑色加粗左对齐 |
| 表格 | 表头黑体、表体仿宋、TNR、五号 10.5pt，表头居中，TableGrid，首行或重复表头 |
| 题注 | caption 样式，黑体五号、非加粗、居中、单倍行距、段前后 6pt，图N-M / 表N-M 章-序 |
| 页眉页脚 | 页眉文本 business_defined（默认规范不固定）；页脚 PAGE 域居中；首页可不同 |

去业务化验证：测试对默认规范目录全部 `.yaml/.md` 及根 lint 契约做
禁用词扫描（具体项目名、编号、单位名等），资产中仅以"不含业务信息"
这类元表述出现，无任何具体绑定值。

## 4. 继承合并语义

- dict 递归按键合并；list / 标量由子模板整体替换；
- 身份字段（id/name/version/category/description）以子模板为准；
- metadata 深合并：子模板继承父元信息，自身键覆盖
  （业务模板以 kind=business_extension 覆盖父规范的
  kind=default_style_specification）；
- `rules_include` 分片先组装，内联 `rules` 后覆盖；
- 缺失父、循环继承在 registry 构建期失败，不产生半注册状态。

## 5. 验证结果

- 全量测试：**192 passed**（基线 180 + 新增 12）；
- 生成验证：以 `default_test.md` 为输入、默认规范为模板、
  `rules/default_technical_document_v1.yaml` 为 lint 契约，
  成功生成 `examples/default_test.docx`，执行期 `errors == []`，
  复读段落样式为 Heading1/Heading2/Heading3/Body；
- 转换验证：扁平来稿（宋体五号直接格式 + Word 默认页边距 +
  手工编号标题 + 表格）经默认规范转换后，脚手架样式字体正确
  （DFBody 仿宋、DFHeading1 黑体、DFTableHeader 黑体、
  DFTableBody 仿宋），ERROR 数不增加；
- 继承验证：业务子模板合并后 body/headings/tables/page/font_aliases
  与父规范逐项相等，业务 metadata（源文档路径、业务 rule_file）保留。

## 6. 已知限制

- TemplateRunner v1 的 OperationPlan 仅治理 styles.xml 与 sectPr；
  figure_rules 的题注样式/编号、页眉页脚部件、PAGE 域、分节符
  当前不被执行链路消费，属规范化事实储备，待后续引擎扩展；
- 继承目前为单父继承（一个 extends）；多 mixin 暂不需要，
  后续若出现可再扩展。

## 7. Commit 与哈希回填

- 实现 commit：`<TASK_DOC_012 实现哈希>`
- 回填 commit：提交后以独立 docs commit 回填本占位
  （消息：docs: backfill TASK_DOC_012 commit hash）
- 重编号 commit：`9461c87`（TASK_DOC_012→013，与本任务一同推送）
