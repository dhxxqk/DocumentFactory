# TASK_DOC_010 — Document Generation Workflow 设计文档

## 1. Workflow 定位

### 1.1 当前架构缺口

TASK_DOC_009 完成后，DocumentFactory 已具备「格式治理引擎」闭环：

```
Template ID → Registry → TemplateDefinition → TemplateRunner → Operations → DOCX → Lint
```

但 [`run_template`](../../src/document_factory/template_runner/runner.py) 的入口要求输入是**已存在的 DOCX**。用户侧仍缺一个完整生产入口：

> 用户从一个任务开始（一段 Markdown 内容 + 一个模板选择），如何得到最终规范 DOCX？

本任务补齐这一层：

```
用户需求 → GenerationRequest → 选 Template → 加载 Markdown → 构建 DOCX
        → run_template(执行 + lint 验证) → 输出 DOCX + 报告
```

### 1.2 Workflow 职责

- **GenerationRequest**：承载用户意图（模板 id + 内容来源 + 输出位置）。
- **Content Provider**：把源内容（v1 仅 Markdown）结构化为可被 `run_template` 消费的 draft DOCX。
- **DocumentGenerationService**：编排 provider 构建 draft → 调 `run_template` → 包装结果。
- **CLI `generate`**：最小可用调用入口。

### 1.3 与既有体系的关系

| 既有模块 | 关系 |
| --- | --- |
| `templates/`（Registry/Loader） | service 在 `generate` 入口先 `load_template(template_id)` 早验证；`TemplateNotFoundError` 直接传播 |
| `template_runner.run_template` | service 调用它完成 lint before → apply → write → read_docx → lint after → 报告，**复用其全部守卫**，不重写 |
| `operations/` | 不可见；generation 不直接调 Formatting Operation Layer |
| `lint_engine` | 不可见；lint 验证由 `run_template` 内置 |
| `docx_reader` | service 不直接读；`read_docx` 由 `run_template` 内部用于有效性检查 |

## 2. 数据模型

### 2.1 GenerationRequest

```python
@dataclass
class GenerationRequest:
    template_id: str               # 必填，如 "GRID_TECH_V1_4"
    content_source: str            # v1 仅 "markdown"
    input_data: dict               # {"file": "x.md"} 或 {"text": "..."}
    output_path: str | None = None # None → output/{stem}.docx
    metadata: dict = field(default_factory=dict)  # {"rules_path": ...} 可选
```

`__post_init__` 校验：`template_id` 非空、`content_source` 受 `SUPPORTED_CONTENT_SOURCES` 约束、`input_data` 必须含 `file` 或 `text`，否则抛 `DocumentFactoryError`。

### 2.2 GenerationResult

```python
@dataclass
class GenerationResult:
    status: str                          # 镜像 ExecutionResult.status
    output_path: str
    template_id: str
    execution_result: ExecutionResult | None  # 成功时携带完整 run_template 结果
    report_path: str
    errors: list[str]                    # generation 级错误；成功路径为空
```

## 3. Content Provider 设计（Markdown → DOCX）

V1 仅 `MarkdownContentProvider`。**无 python-docx / markdown / pandoc 依赖**（`pyproject.toml` 仅声明 lxml/PyYAML/PyMuPDF），采用最小手写转换：

- `#/##/### ` → Heading1/2/3 段落（`<w:pStyle w:val="HeadingN"/>`）
- 空行 → 段落分隔（不生成空段）
- 其余行 → Body 段落（`<w:pStyle w:val="Body"/>`，name="正文"）
- `**bold**` / 列表 / 表格 v1 不深度支持，文本落入正文段落

生成的 draft DOCX 含 `word/document.xml` + `word/styles.xml`（Normal + Body + Heading1-3）+ `word/settings.xml`。样式字符串镜像 `tests/conftest.py` 的 `BODY_STYLE/HEADING_STYLES/SECTION`（值已贴近 GRID_TECH_V1_4 目标，使 draft 既有效又被 `run_template` 低成本归一）。**Production 代码不 import 测试 fixture**，常量在 `providers.py` 内重定义。

draft 写入 `tempfile.mkdtemp()` 目录，`finally` 清理，不污染 output。

## 4. Service 设计

```python
class DocumentGenerationService:
    def generate(self, request) -> GenerationResult:
        load_template(request.template_id)   # 早验证，TemplateNotFoundError 传播
        provider = get_provider(request.content_source)
        stem = file stem or "generated"
        output = request.output_path or output/{stem}.docx
        report = reports/{stem}_GENERATION_REPORT.md
        rules_path = request.metadata.get("rules_path")
        mkdir output/reports
        draft = tempfile / {stem}_draft.docx
        try:
            provider.build(input_data, draft)
            exec = run_template(template_id, draft, output, report, rules_path)
            return GenerationResult(status=exec.status, ..., errors=[])
        except DocumentFactoryError as exc:
            return GenerationResult(status="FAIL", execution_result=None, errors=[str(exc)])
        finally:
            shutil.rmtree(draft_dir)
```

**路径安全**：复用 [`checked_output`](../../src/document_factory/output_paths.py)（`run_template` 内部）——output 必须在 `cwd/output` 下、report 在 `cwd/reports` 下、不可覆盖输入。

**异常分层**：`TemplateNotFoundError` 在 `try` 之前触发，向上传播（调用方可区分"无此模板"与"执行失败"）；`run_template` 的执行失败被 catch 转为 `GenerationResult(status="FAIL", errors=[...])`。

## 5. Pipeline 编排

`pipeline.py` 提供函数式入口：

```python
def generate_document(request: GenerationRequest) -> GenerationResult:
    return DocumentGenerationService().generate(request)
```

对应任务书 Pipeline Orchestrator。CLI 与测试均通过此入口。

## 6. 与 Template Runner / Formatting Layer 的关系

generation **不重新发明格式执行**。它的角色是"把内容送进 `run_template`"：

```
Markdown ──provider──→ draft.docx ──run_template──→ final.docx + 报告
                          │
                   ┌──────┴──────┐
            TemplateRunner    lint before/after
                   │
            Formatting Operations（style + sectPr）
```

- 格式事实由 `TemplateDefinition` 决定（LLM 不进流水线）。
- 内容由 provider 结构化（内容与格式分离）。
- 验证由 `run_template` 内置 lint 完成（输出可验证）。

**作用域边界**：`TemplateRunner` v1 只应用样式元素 + sectPr（见其设计文档 §1）。因此 Markdown 生成的 draft 若缺编号绑定（`NUM002`）或 TOC 域（`TOC001`），`run_template` 不修复——这两类结构性规则归 normalizer。generation 的验收以"流程完整 + 不引入新 ERROR（`after <= before`）"为判据，`status` 字段语义同 TASK_DOC_009：`status=FAIL` 不代表模板应用失败，`operations_count`/`changes` 才是应用成功判据。

## 7. 后续 LLM 接入位置

LLM 的位置在 generation **之前**，绝不进入格式流水线：

```
LLM 生成 Markdown 内容
        │
        ↓
GenerationRequest(content_source="markdown", input_data={"text": <LLM 输出>})
        │
        ↓
DocumentFactory 固化格式（本任务）
```

后续可加 `content_source="llm"` provider，但其职责仅是把 LLM 文本送进同一 pipeline，不在 generation 内部调 LLM。这与任务书原则一致：LLM 只生成内容，DocumentFactory 固化格式。

## 8. 验收对照

| 任务书验收项 | 落实 |
| --- | --- |
| generation 模块建立 | `src/document_factory/generation/{__init__,models,service,pipeline,providers}.py` |
| Request 模型完成 | `GenerationRequest` + `__post_init__` 校验 |
| Result 模型完成 | `GenerationResult` |
| Service 完成 | `DocumentGenerationService.generate` |
| Markdown 输入支持 | `MarkdownContentProvider`（file/text） |
| Template 选择支持 | `load_template(template_id)` 早验证 |
| DOCX 生成支持 | provider 构建 draft + `run_template` write_package |
| Template Runner 集成 | service 调 `run_template` |
| Lint 验证集成 | `run_template` 内置 lint before/after |
| 新增测试通过 | `tests/generation/` 12 项 |
| 原 152 测试不下降 | 164 passed（152 + 12） |
| Generation Workflow 设计完成 | 本文档 |
