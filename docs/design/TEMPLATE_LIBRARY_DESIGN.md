# TASK_DOC_008 — Template Library & Registry 设计文档

任务编号: TASK_DOC_008

日期: 2026-09-23 (+08:00)

Agent: Trae

状态: 设计阶段（等待确认）

---

## 1. 为什么需要 Template Registry

### 1.1 当前架构

DocumentFactory 已具备：

- **DOCX 解析**（`docx_reader.py`）：只读提取 OOXML 结构
- **格式规则检查**（`lint_engine.py` + `rules/*.yaml`）：判定文档是否符合规范
- **格式化操作层**（`operations/`）：确定性的 font / paragraph / style / table / document 原子操作
- **模板分析与应用**（`template/`）：从 DOCX 模板提取样式 Profile，迁移到目标文档

### 1.2 核心问题

> 格式规则来自哪里？

当前有两条路径，但都缺少"模板即数据"的确定性事实源：

- **Lint 规则路径**：`rules/grid_tech_v1_4.yaml` 定义检查规则，但这是**审计规则**（判对错），不是**生成模板**（定义输出长什么样）
- **TemplateProfile 路径**：`template/profile.py` 从现有 DOCX **提取**样式事实，但这是**描述性的**（record what is），不是**规定性的**（prescribe what should be）

结果：每次生成 Word 时如果由 AI 临时决定格式，仍会产生字体漂移、标题层级漂移、页眉页脚漂移。

### 1.3 解决方案

建立 **Template Library + Registry**：

```text
模板 ID（如 TECH_REPORT_V1）
        ↓
Template Registry 查找
        ↓
TemplateDefinition（规定性格式定义）
        ↓
Formatting Operation Layer（确定性执行）
        ↓
DOCX Output
```

TemplateDefinition 是**规定性的**（prescriptive）：它定义"一份技术报告的正文应该是仿宋 12pt、一级标题应该是黑体 16pt"，由 operations 层确定性执行，不依赖 LLM 判断。

### 1.4 与现有系统的关系

| 概念 | 性质 | 来源 | 消费方 |
|---|---|---|---|
| Lint 规则 (`rules/*.yaml`) | 检查规则 | 人工编写 | lint_engine（审计） |
| TemplateProfile (`template/profile.py`) | 描述性 | 从 DOCX 提取 | template/applier + operations（迁移） |
| **TemplateDefinition**（本任务） | **规定性** | **YAML 数据文件** | **operations 层（生成）** |

三者互补：TemplateDefinition 定义目标格式 → operations 层执行 → lint 规则验证结果。

---

## 2. 数据模型

### 2.1 TemplateDefinition

```python
@dataclass
class TemplateDefinition:
    id: str                        # "TECH_REPORT_V1"
    name: str                      # "技术报告模板"
    version: str                   # "1.0"
    category: list[str]            # ["report"]
    description: str               # 模板用途说明
    rules: TemplateRules           # 格式规则（供 operations 层消费）
    metadata: dict[str, Any]       # source / author / created_at 等
```

### 2.2 TemplateRules

TemplateRules 是 TemplateDefinition 的核心，定义文档各部分的格式。字段名与 operations 层参数对齐，使 operations 层可直接消费：

```python
@dataclass
class TemplateRules:
    page: dict[str, Any]                      # page_size / margins / orientation
    body: BodyRule                            # 正文格式
    headings: dict[str, HeadingRule]          # "h1" / "h2" / "h3"
    tables: TableRule | None                  # 表格格式（可选）
    font_aliases: dict[str, list[str]]        # 字体别名映射
```

### 2.3 BodyRule

字段直接映射到 `operations.font.FontProfile` 和 `operations.paragraph.ParagraphProfile`：

```python
@dataclass
class BodyRule:
    style_name: str               # "正文"（Word 样式名）
    chinese_font: str             # "仿宋"
    latin_font: str               # "Times New Roman"
    font_size_pt: float           # 12
    first_line_indent_chars: int   # 2
    line_spacing: float            # 1.5
    space_before_pt: float         # 0
    space_after_pt: float          # 0
    alignment: str                 # "both"（两端对齐）
```

### 2.4 HeadingRule

```python
@dataclass
class HeadingRule:
    word_style: str               # "Heading 1"
    chinese_font: str              # "黑体"
    latin_font: str                # "Times New Roman"
    size_pt: float                 # 16
    color: str                      # "000000"
    bold: bool                      # True
    alignment: str                  # "left"
```

### 2.5 TableRule

```python
@dataclass
class TableRule:
    header_font: str              # "黑体"
    body_font: str                 # "仿宋"
    latin_font: str               # "Times New Roman"
    font_size_pt: float           # 10.5
    alignment: str                # "center"
```

---

## 3. YAML 模板格式

模板以 YAML 文件存储在 `templates/` 目录下。每个模板一个子目录，内含 `template.yaml`：

```text
templates/
├── grid_tech_v1_4/
│   └── template.yaml
├── technical_report/
│   └── template.yaml
└── README.md
```

YAML 结构示例（`templates/grid_tech_v1_4/template.yaml`）：

```yaml
id: GRID_TECH_V1_4
name: 电网科技项目实施方案模板
version: "1.0"
category:
  - report
  - government
description: 基于电网科技项目实施方案文档格式规范 V1.4 的确定性模板
metadata:
  source: specs/电网科技项目实施方案文档格式规范_V1.4.md
  spec_version: V1.4
  author: dhxxqk
  created_at: "2026-09-23"

rules:
  page:
    page_size: A4
    orientation: portrait
    margins_cm:
      top: 2.8
      bottom: 2.6
      left: 2.8
      right: 2.6

  body:
    style_name: 正文
    chinese_font: 仿宋
    latin_font: Times New Roman
    font_size_pt: 12
    first_line_indent_chars: 2
    line_spacing: 1.5
    space_before_pt: 0
    space_after_pt: 0
    alignment: both

  headings:
    h1:
      word_style: Heading 1
      chinese_font: 黑体
      latin_font: Times New Roman
      size_pt: 16
      color: "000000"
      bold: true
      alignment: left
    h2:
      word_style: Heading 2
      chinese_font: 黑体
      latin_font: Times New Roman
      size_pt: 14
      color: "000000"
      bold: true
      alignment: left
    h3:
      word_style: Heading 3
      chinese_font: 黑体
      latin_font: Times New Roman
      size_pt: 12
      color: "000000"
      bold: true
      alignment: left

  tables:
    header_font: 黑体
    body_font: 仿宋
    latin_font: Times New Roman
    font_size_pt: 10.5
    alignment: center

  font_aliases:
    仿宋: [仿宋, FangSong]
    黑体: [黑体, SimHei]
    Times New Roman: [Times New Roman]
```

---

## 4. API 设计

### 4.1 Registry API

```python
class TemplateRegistry:
    """模板注册表。启动时扫描 templates/ 目录自动加载。"""

    def register_template(self, definition: TemplateDefinition) -> None
        """注册模板。ID 重复时抛 TemplateAlreadyRegisteredError。"""

    def get_template(self, template_id: str) -> TemplateDefinition
        """按 ID 获取模板。不存在时抛 TemplateNotFoundError。"""

    def list_templates(self) -> list[TemplateSummary]
        """列出所有已注册模板的摘要（id / name / version / category）。"""

    def has_template(self, template_id: str) -> bool
        """检查模板是否存在。"""
```

### 4.2 Loader API

```python
def load_template(template_id: str) -> TemplateDefinition
    """从默认 Registry 加载模板。便捷函数，等价于 default_registry.get_template()。"""

def load_template_from_yaml(path: str | Path) -> TemplateDefinition
    """从 YAML 文件直接加载单个模板（不走 Registry）。"""
```

### 4.3 异常

```python
class TemplateNotFoundError(DocumentFactoryError):
    """模板 ID 在 Registry 中不存在。"""

class TemplateAlreadyRegisteredError(DocumentFactoryError):
    """模板 ID 已被注册。"""

class TemplateSchemaError(DocumentFactoryError):
    """模板 YAML 缺少必需字段或类型不符。"""
```

---

## 5. 代码结构

```text
src/document_factory/
├── templates/                  # NEW: Template Library & Registry
│   ├── __init__.py             # 公共 API 导出
│   ├── schema.py               # TemplateDefinition / TemplateRules / BodyRule / HeadingRule / TableRule
│   ├── registry.py             # TemplateRegistry / TemplateNotFoundError / TemplateAlreadyRegisteredError
│   └── loader.py               # load_template() / load_template_from_yaml() / TemplateSchemaError
├── template/                   # EXISTING: DOCX 模板分析与迁移（不动）
├── operations/                 # EXISTING: Formatting Operation Layer（不动）
└── ...
```

说明：

- 任务书建议的 `template_models/` 独立目录不再单独建立——schema 数据类放在 `templates/schema.py` 中更内聚，避免过度拆分
- 现有 `template/`（单数）模块不做任何改动，`templates/`（复数）是新模块，两者职责不同
- `src/document_factory/__init__.py` 将新增导出 `load_template`、`TemplateDefinition`、`list_templates`

### 测试结构

```text
tests/
├── templates/                  # NEW
│   ├── __init__.py
│   ├── test_registry.py        # 注册 / 查找 / 重复 / 不存在
│   ├── test_loader.py          # YAML 加载 / 缺字段 / 类型校验
│   └── test_schema.py          # dataclass 序列化 / 字段默认值
└── ...（现有测试不动）
```

---

## 6. 与 Formatting Operation Layer 的关系

TemplateDefinition.rules 的字段设计直接对齐 operations 层的入参：

| TemplateDefinition 字段 | 对应 operations 层 API |
|---|---|
| `rules.body` | `FontProfile` + `ParagraphProfile` → `apply_font` / `apply_paragraph_format` |
| `rules.headings["h1"]` | `FontProfile` + `apply_style` / `find_style_element` |
| `rules.page` | `PageFormat` → `apply_section_properties` |
| `rules.tables` | `apply_table_font` / `apply_table_alignment` |
| `rules.font_aliases` | 字体名称解析（operations 层内部使用） |

本任务**只实现 Template Library + Registry + Loader**，不实现"从 TemplateDefinition 驱动 operations 层生成 DOCX"的完整 pipeline。后者是后续任务（TASK_DOC_009+）的范围。但 TemplateDefinition 的 rules 字段结构已为 operations 层消费做好准备。

---

## 7. 初始模板

随本任务提供一个种子模板 `GRID_TECH_V1_4`，内容直接来自现有 `rules/grid_tech_v1_4.yaml` 的格式参数。这确保：

1. Registry 启动即有可用模板
2. 与现有 lint 规则体系一致
3. 为后续模板（技术报告、企业报告等）提供参考格式

---

## 8. 验收标准

- [ ] `templates/` 目录建立，含种子模板 YAML
- [ ] `src/document_factory/templates/` 模块建立（schema / registry / loader）
- [ ] TemplateDefinition / TemplateRules / BodyRule / HeadingRule / TableRule 定义完成
- [ ] Registry API（register / get / list / has）实现完成
- [ ] load_template() / load_template_from_yaml() 实现完成
- [ ] 异常体系（TemplateNotFoundError / TemplateAlreadyRegisteredError / TemplateSchemaError）定义
- [ ] 单元测试覆盖注册、查找、不存在异常、YAML 加载、缺字段校验
- [ ] 原有 89 项测试不下降
- [ ] `__init__.py` 导出新增公共 API
- [ ] 本设计文档提交并经确认
