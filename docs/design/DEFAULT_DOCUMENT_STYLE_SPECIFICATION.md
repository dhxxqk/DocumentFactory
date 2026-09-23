# Default Document Style Specification 设计文档（TASK_DOC_012）

## 1. 为什么建立默认规范

TASK_DOC_011 建立了第一个真实模板资产 `GRID_RESEARCH_IMPLEMENTATION_PLAN_V1`，
但它的模板规则全部内嵌在单个 `template.yaml` 中，且天然绑定一份具体业务
文档。如果沿用这种方式，每来一类业务文档就要复制一份完整模板：

```
模板1：科研实施方案     （内嵌 页面/正文/标题/表格 全套规则）
模板2：某项目技术方案   （再复制一套，绝大多数参数完全相同）
模板3：验收报告         （再复制一套……）
模板4：研究报告         （再复制一套……）
```

这会带来三个问题：

1. **规则重复**：A4 页面、仿宋正文、黑体多级标题等通用事实被复制 N 份，
   规范一旦调整（例如正文行距改为固定值），需要逐模板修改且极易漏改；
2. **业务与格式耦合**：具体项目名称、编号、章节结构混在格式模板里，
   模板无法跨项目复用；
3. **资产定位错误**：DocumentFactory 的核心资产不应是"某个 Word 模板"，
   而应是一套可继承的企业文档规范体系——这才符合"文件丢进去自动处理"
   的产品方向：来稿无论是方案、报告还是验收材料，都先落到同一套默认
   格式基准上，再叠加业务差异。

因此本任务在业务模板之下抽出一层统一父规范：

```
DEFAULT_TECHNICAL_DOCUMENT_V1（默认技术文档规范，只含通用格式事实）
        │
        ├── GRID_RESEARCH_IMPLEMENTATION_PLAN_V1（科研实施方案：继承 + 业务扩展）
        ├── 技术方案（未来）
        ├── 验收报告（未来）
        └── 项目总结报告（未来）
```

编号说明：原"Word 格式转换流水线"任务编号 TASK_DOC_012 已顺延为
TASK_DOC_013（见其设计文档编号说明），本任务占用 TASK_DOC_012。

## 2. 规范来源

默认规范不是凭空新造，而是对 TASK_DOC_011 已提取、已验证的真实格式事实
做**抽象化**处理：

- 参数口径与通用技术报告实践一致，与既有《文档格式规范 V1.4》同构：
  A4 纵向、页边距 上2.8 / 下2.6 / 左2.8 / 右2.6 cm；正文仿宋 12pt、
  1.5 倍行距、首行缩进 2 字符、两端对齐；标题黑体 16/14/12pt；
  表格表头黑体、表体仿宋、10.5pt；
- 题注（caption）事实由源文档样式表提取：黑体 + Times New Roman、
  五号、居中、单倍行距、段前后 6pt，编号采用"章-序"图N-M / 表N-M；
- 页眉页脚提取出抽象策略：页脚 PAGE 域居中、页眉页脚距边界 1.4cm、
  首页可不同；**页眉文本不进入默认规范**。

抽象过程中严格执行去业务化原则：

| 删除（业务信息） | 保留（格式/样式/结构规则） |
| --- | --- |
| 具体项目名称、项目编号 | 页面大小、页边距、页眉页脚距离 |
| 具体单位/公司名称 | 默认字体、字号、行距、缩进、对齐 |
| 特定章节名（如"1 课题概述"） | Heading Level 1/2/3 的样式事实 |
| 固定页眉业务文本 | 页眉策略（business_defined）、页脚页码域规则 |
| 只能用于单一项目的固定文字 | 表格/题注的字体、字号、编号模式 |

默认规范的规范性来源（lint 契约 `source`）指向规范定义文件本身，
而非任何一份业务 DOCX：

```
templates/default_technical_document_v1/definition/style_definition.yaml
```

## 3. 资产结构与规则组织

```
templates/default_technical_document_v1/
├── template.yaml                 # 模板身份 + rules_include 组装声明
├── definition/
│   └── style_definition.yaml     # 规范主源：人可读的完整规范定义
├── rules/                        # 机器消费的规则分片（唯一人工编辑源）
│   ├── page_rules.yaml           # 页面 / 分节 / 页眉页脚策略
│   ├── paragraph_rules.yaml      # 正文 / Normal / 字体别名 / 字号映射
│   ├── heading_rules.yaml        # Heading 1-3 样式与大纲策略
│   ├── table_rules.yaml          # 表格字体、边框样式、表头策略
│   └── figure_rules.yaml         # 图表题注样式与章-序编号
├── examples/
│   ├── default_test.md           # 最小验证输入
│   └── default_test.docx         # 规范驱动生成的验证产物
└── validation/
    └── VALIDATION_CHECKLIST.md   # 验收清单

rules/default_technical_document_v1.yaml   # 扁平 lint 契约（lint_engine 消费）
```

### 3.1 分片与契约的分工

系统中存在两种规则形态，职责不同、不可互相替代：

- **模板分片规则**（`templates/.../rules/*.yaml`）：嵌套结构，由 loader
  组装成 `TemplateRules`，经 TemplateRunner 驱动**生成/执行**
  （OperationPlan：改样式、改 sectPr）；
- **扁平 lint 契约**（`rules/default_technical_document_v1.yaml`）：
  lint_engine 直接加载，用于**校验/诊断**既有 DOCX（PAGE001、BODY001、
  TABLE001…… 全部规则的 severity 与 source）。

两者参数保持同构；业务模板可各自携带自己的 lint 契约（011 模板仍使用
`rules/grid_research_implementation_plan_v1.yaml`，其 source 仍指向
业务源文档），互不影响。

### 3.2 rules_include 组装

`template.yaml` 通过 `rules_include` 声明分片：

```yaml
rules_include:
  - rules/page_rules.yaml
  - rules/paragraph_rules.yaml
  - rules/heading_rules.yaml
  - rules/table_rules.yaml
  - rules/figure_rules.yaml
```

loader 按序读取并**深合并**为一份完整 rules 映射，再交给 schema 校验；
同文件内联 `rules`（若有）优先级最高。这样规范可以按维度分文件维护，
而运行时仍看到单一完整规则对象。

## 4. 继承机制（extends）

### 4.1 模板侧

`TemplateDefinition` 新增可选字段 `extends: PARENT_TEMPLATE_ID`。
loader 的 `build_registry` 改为两阶段：

1. 扫描全部 `*/template.yaml`，组装各自的 rules_include 分片；
2. 按 `extends` 做依赖解析（拓扑顺序与目录名无关），父规则先解析，
   再与子数据**递归深合并**后统一校验。

合并语义：

- dict 递归按键合并；
- list 与标量由子模板整体替换（例如 `category` 不做拼接）；
- 身份字段（id/name/version/category/description）以子模板为准，
  因此子模板必须自带完整身份信息；
- 缺失父模板、继承循环在构建期直接报 `TemplateSchemaError`；
- 单独调用 `load_template_from_yaml` 加载带 extends 的模板时，
  按 `<templates>/<id>/template.yaml` 目录约定向兄弟目录解析父模板。

### 4.2 业务模板改造结果

`GRID_RESEARCH_IMPLEMENTATION_PLAN_V1` 删除了全部内嵌重复规则，
只保留：

```yaml
extends: DEFAULT_TECHNICAL_DOCUMENT_V1
# + 业务身份（id/name/category/description）
# + 业务 metadata（业务源文档路径、业务 lint 契约、提取方式）
```

其格式事实在合并后与父规范逐项一致（011 既有资产测试全部保持通过），
业务 metadata（源文档、rule_file、kind=business_extension）完整保留。

## 5. 后续扩展方式

新增一类业务文档时，只需：

1. 建立 `templates/<business_template>/template.yaml`，声明
   `extends: DEFAULT_TECHNICAL_DOCUMENT_V1`；
2. 只写差异：业务身份、业务来源、需要收紧/扩展的规则（内联 rules
   深合并覆盖父规范对应键，未覆盖处全部继承）；
3. 需要业务专属校验时，在项目根 `rules/` 提供该模板自己的扁平
   lint 契约，并在 metadata.rule_file 指向它；
4. 不需要再复制页面/正文/标题/表格等通用规则。

当默认规范本身升级（例如新增"脚注规则分片"）时：

- 在默认模板的 `rules/` 增加分片并登记到 `rules_include`；
- 所有业务模板**自动继承**新规则，无需逐模板改动；
- 某业务模板若需豁免，显式内联覆盖对应键即可。

## 6. 当前边界

TemplateRunner v1 的 OperationPlan 只治理样式（styles.xml）与节属性
（sectPr）。默认规范中的下列事实已作为**资产层储备**落盘，但暂不被
执行链路消费：

- 图表题注样式与图N-M / 表N-M 编号（figure_rules.yaml）；
- 页眉业务文本、页脚 PAGE 域、首页不同的部件级写入；
- 分节符与页码格式的自动套用。

这些分片先把规范事实固定下来，后续页眉页脚/题注引擎可直接读取消费，
不需要再回头从业务文档逆向提取。

## 7. 验证

- `tests/templates/test_default_specification.py`：注册、去业务化扫描、
  格式事实、extends 继承一致性、缺失父/循环/子覆盖优先级、
  Markdown 生成、扁平 DOCX 转换，共 12 项；
- `tests/test_template_asset_grid_research.py`：011 业务模板改造后
  全部既有断言保持通过；
- `examples/default_test.docx`：由默认规范实际驱动生成，可重新读取，
  Heading1/2/3 与正文样式、页面页边距符合规范。
