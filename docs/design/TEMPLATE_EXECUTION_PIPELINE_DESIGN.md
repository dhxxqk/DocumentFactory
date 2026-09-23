# TASK_DOC_009 — Template Execution Pipeline 设计文档

任务编号: TASK_DOC_009

日期: 2026-09-23 (+08:00)

Agent: Trae (GLM-5.2)

状态: 已实现

---

## 1. Pipeline 定位

### 1.1 当前架构缺口

DocumentFactory 在 TASK_DOC_008 后具备规定性模板资产层 `TemplateDefinition`，但缺少中间执行层：

```text
TemplateDefinition
      ↓
??? （缺）
      ↓
Formatting Operation Layer
      ↓
DOCX
```

格式事实已定义，但没有人把它们驱动到 operations 层。

### 1.2 Pipeline 职责

Template Execution Pipeline 负责：

> 将 TemplateDefinition 中定义的规定性事实，转换为 Formatting Operation Layer 可执行的操作，并产出可被 lint 再验证的 DOCX。

```text
Template ID
   ↓
Template Registry → TemplateDefinition
   ↓
Template Runner （本任务）
   ↓
Operation Mapping （本任务）
   ↓
Formatting Operations （既有）
   ↓
DOCX Output
   ↓
Lint Validation （既有）
```

设计原则（任务书）：**Template 决定规则，Operation 执行规则。** LLM 不参与格式判断；只动 Word/DOCX。

### 1.3 与既有体系的关系

| 模块 | 性质 | 输入 | 输出 |
|---|---|---|---|
| `lint_engine` | 审计 | DOCX + 规则 | Findings（判对错） |
| `normalizer` | 修复（rule-engine repair） | DOCX + 规则 | 修复后 DOCX + 报告 |
| `template/applier` | 迁移（descriptive） | DOCX + 模板 DOCX | 迁移后 DOCX + 报告 |
| **`template_runner`**（本任务） | **执行（prescriptive）** | **DOCX + TemplateDefinition** | **应用后 DOCX + 报告** |

四者互补：`template_runner` 把模板规定性事实 stamp 到文档样式与页面；`normalizer` 在规则驱动下修复直接格式覆盖；`template/applier` 从已有 DOCX 提取描述性事实迁移；`lint_engine` 验证最终结果。

---

## 2. 数据模型

### 2.1 OperationPlan（复用既有 profile，不造并行类型）

```python
@dataclass(frozen=True)
class OperationPlan:
    body_font: FontProfile          # 复用 operations.font.FontProfile
    body_paragraph: ParagraphProfile # 复用 operations.paragraph.ParagraphProfile
    heading_fonts: dict[str, FontProfile]   # "h1"/"h2"/"h3"
    page: PageFormat | None         # 复用 operations.document.PageFormat
    table_font: FontProfile | None
    table_alignment: str | None
    table_style_names: list[str]

    @property
    def operations_count(self) -> int  # 计划的操作组数
```

**关键决策**：不新建 `FontOperation`/`ParagraphOperation` 等并行 dataclass。OperationPlan 直接持有 operations 层的 profile 实例，runner 直接传给 operations 调用，无翻译步骤。

### 2.2 ExecutionResult

```python
@dataclass
class ExecutionResult:  # 位于 src/document_factory/models.py，与既有 result 类型同模块
    status: str               # PASS / FAIL（来自输出 DOCX 的真实 lint）
    template_id: str
    input_path / output_path / report_path: str
    input_sha256 / output_sha256: str
    operations_count: int     # 实际变更记录数（len(changes)）
    before_counts / after_counts: dict   # lint ERROR/WARNING/INFO 计数
    changes: list[dict]        # OperationContext 记录的变更明细
    changed_parts: list[str]  # 变更的 ZIP 部件
    warnings: list[str]        # 缺失 heading/sectPr/table 样式
    errors: list[str]          # 缺失 body 样式（致命）
    source_unchanged: bool
```

---

## 3. Mapper 设计

`build_operation_plan(template: TemplateDefinition) -> OperationPlan` 是**纯函数**：无 DOCX、无文件系统。这使得 Test 2（转换数量）可在无文档环境下验证。

### 3.1 单位换算（镜像 normalizer 既有换算）

OOXML 使用 twips / 半磅 / 240 分之一行距，模板使用 cm / pt / 倍率。mapper 在边界处一次性换算：

| 模板字段 | OOXML 属性 | 换算 |
|---|---|---|
| `first_line_indent_chars` | `w:ind@firstLineChars` | `chars * 100` |
| `line_spacing` | `w:spacing@line` | `line_spacing * 240`（`lineRule="auto"`） |
| `space_before_pt` / `space_after_pt` | `w:spacing@before` / `@after` | `pt * 20` |
| `font_size_pt` | `w:sz@val` | `int(pt * 2)`（operations 内部处理） |
| `margins_cm` | `w:pgMar@top/right/...` | `int(round(cm * 1440 / 2.54))` |
| `page_size` | `w:pgSz@w/@h` | `PAGE_SIZES` 常量查表；landscape 交换宽高 |

换算与 `normalizer._normalize_body_ppr` 完全一致，确保 lint、normalizer、template_runner 三者对"2 字符缩进""1.5 倍行距"的理解统一。

### 3.2 PAGE_SIZES 常量

新增于 `operations/document.py`（与 `PageFormat` 同模块，单一事实源）：

```python
PAGE_SIZES = {"A4": (11906, 16838), "A3": (16838, 23811), "Letter": (12240, 15840)}
```

未知 page_size（如 B5）→ `width_twips=None, height_twips=None`，仅应用 margins。

---

## 4. Runner 设计

### 4.1 TemplateRunner.run(template, document) -> ExecutionResult

职责链：定位目标元素 → 调度 operations → 收集 changes/changed_parts → 记录 warnings/errors。

**目标定位策略**（复用既有工具，不写新检测逻辑）：

| 目标 | 定位方式 | 来源 |
|---|---|---|
| body 样式 | 扫描 `document.styles`，`style.name == body_rule.style_name and kind=="paragraph"` | 同 normalizer |
| heading 样式 | `re.fullmatch(r"(?:heading\s*\|标题\s*)([1-3])", style.name)` → `{"h1": styleId, ...}` | 同 StyleResolver.heading_level |
| sectPr 元素 | `parts["word/document.xml"].findall(".//w:sectPr", NS)`，过滤 `sectPrChange` 祖先 | 同 docx_reader |
| table 样式 | `style.name in plan.table_style_names` | 新增 `TableRule.style_names` |

**执行策略**（v1 作用域：样式元素 + sectPr）：

- body 样式 → `apply_indent`（remove firstLine/hanging/hangingChars）+ `apply_spacing`（remove auto-spacing 系列）+ `apply_alignment` + `apply_font`
- heading 样式 → `apply_font`（字体/字号/颜色/粗体，含 theme 清理）
- sectPr → `apply_section_properties`（页面尺寸 + 边距）
- table 样式 → `apply_font`

**为何 body 用粒度操作而非 `apply_paragraph_format`**：`apply_paragraph_format` 不携带 `remove` 列表，无法清理冲突属性（如 `hanging`、`beforeLines`）。runner 必须镜像 `normalizer._normalize_body_ppr` 的 remove 列表，才能产出 lint-clean 的正文（否则 `BODY002` 会因残留 `hanging` 失败）。remove 列表是确定性的"执行策略"，非格式判断。

**缺失目标严重度**：

- 缺 body 样式 → `errors`（无法有意义地应用模板，status=FAIL）
- 缺 heading/sectPr/table 样式 → `warnings`（跳过，不致命）

### 4.2 run_template 编排器

`run_template(template_id, input_path, output_path=None, report_path=None, rules_path=None) -> ExecutionResult`

镜像 `normalizer.normalize` 全流程与守卫：

```text
load_template(template_id)
   ↓
checked_output(output / report)  # 路径安全
   ↓
lint(source, rules) → before  # 含 input_hash
   ↓
TemplateRunner().run(template, before.document)
   ↓
sha256 守卫（INPUT_CHANGED）
   ↓
write_package(source, output, document, changed_parts)
   ↓
sha256 守卫
   ↓
read_docx(output)  # 有效性检查，corrupt ZIP 不能报成功
   ↓
lint(output, rules) → after
   ↓
写 MD + JSON 报告（atomic_text，后缀 _TEMPLATE_RUN_REPORT.md）
   ↓
ExecutionResult(status=after.result, ...)
```

报告后缀 `_TEMPLATE_RUN_REPORT.md`，区别于描述性 applier 的 `_TEMPLATE_REPORT.md`。

### 4.3 命名

新公共函数命名 `run_template`（动词对齐 runner 名词），避免与既有描述性 `apply_template(template_path, ...)` 碰撞。两者签名首参不同（template_id 字符串 vs template_path 路径），但同名同顶层命名空间会冲突，故：

- `run_template` 位于 `template_runner` 子模块，并从 `document_factory` 顶层导出
- 既有 `apply_template`（描述性）保留不动
- CLI 子命令嵌套为 `template run`（与 `template apply`/`template analyze` 一致）

---

## 5. 与 Formatting Layer 的关系

TemplateRunner 是 Formatting Operation Layer 的**确定性调度者**，不包含任何格式判断：

| TemplateRunner 职责 | Formatting Layer 职责 |
|---|---|
| 决定哪些元素是 body/heading/section | 设置 w:rFonts/w:sz/w:color |
| 把模板事实翻译成 OOXML 单位 | 写 w:ind/w:spacing/w:jc |
| 调度 apply_font/apply_spacing/apply_section_properties | 记录 change（OperationContext） |
| 收集 changes/changed_parts | 原子写 ZIP（write_package） |

TemplateRunner 不调用 LLM、不判断"这段是否需要改"、不重分类段落语义（Normal→Heading 等）。这些决策由模板（规定性事实）或后续 Semantic Parser 任务承担。

---

## 6. 后续扩展方向

1. **Direct run-level application**：当前只动样式元素与 sectPr。后续可像 `template/applier` 那样把模板事实应用到有直接格式覆盖的 run（覆盖冲突的直接格式）。直接 run 修复目前归 `normalizer`（rule-engine repair 语义）。
2. **多 section 策略**：当前对所有非 sectPrChange 的 sectPr 统一应用页面规则。后续可支持"仅 body section"或"不同 section 不同页面规则"。
3. **TemplateRunner + 生成 pipeline 集成**：TASK_DOC_010 计划实现"用户需求 → 选模板 → 生成 DOCX → 格式验证 → 交付"。TemplateRunner 将作为生成 pipeline 的格式固化环节。
4. **Header/Footer 应用**：当前 `HEADER_FOOTER_MIGRATION_SUPPORTED=False`，页眉页脚仅分析不迁移。后续可扩展。
5. **更多模板**：当前仅 `GRID_TECH_V1_4` 种子模板。后续按真实规范补齐技术报告、企业报告、政府文档模板。

---

## 7. 验收对照

- [x] Template Runner 模块建立（`template_runner/runner.py`）
- [x] Mapper 建立（`template_runner/mapper.py`）
- [x] Execution Result 建立（`models.py: ExecutionResult`）
- [x] TemplateDefinition 可驱动 Operation 生成（`build_operation_plan`）
- [x] Body 规则执行（body 样式 font + paragraph）
- [x] Heading 规则执行（h1/h2/h3 样式 font）
- [x] Page 规则执行（sectPr 尺寸 + 边距）
- [x] 新增测试通过（19 项）
- [x] 原 133 项测试不下降（共 152 passed）
- [x] Pipeline 设计文档完成（本文）
