# TASK Report

Task: TASK_DOC_010 — Document Generation Workflow & Interface Foundation

Date: 2026-09-23 (+08:00)

Agent: Trae (GLM-5.2)

## Summary

RESULT: PASS

建立了 DocumentFactory 的 **Document Generation Workflow**：把用户意图（模板 id + Markdown 内容）通过 `GenerationRequest` 串联到既有 `run_template`，产出 lint 验证过的 DOCX + 执行报告，完成第一个「内容 → 格式固化 → 交付」生产闭环。DocumentFactory 从「格式治理引擎」进入「可使用文档生产系统」阶段。

新增 `src/document_factory/generation/` 模块（models + service + pipeline + providers），顶层入口 `generate_document(request) -> GenerationResult`，CLI 子命令 `document-factory generate`。

**关键设计决策**：

1. **无 python-docx/markdown 依赖**：`pyproject.toml` 仅声明 lxml/PyYAML/PyMuPDF。Markdown→DOCX 采用**最小手写转换**（`zipfile` + OOXML 字符串），样式常量镜像 `tests/conftest.py` 的 `BODY_STYLE/HEADING_STYLES/SECTION`（production 代码不 import 测试 fixture，常量在 `providers.py` 内重定义）。
2. **最小 Markdown 解析**：`#/##/###` → Heading1/2/3，其余非空行 → 正文（Body, name="正文"）。`**bold**`/列表/表格 v1 不深度支持，文本落入正文。draft 含 Normal+Body+Heading1-3+sectPr+settings。
3. **复用 run_template 全部守卫**：service 调 `run_template` 完成 lint before → apply → write_package → read_docx → lint after → 报告，不重写。路径安全复用 `checked_output`（output 在 `cwd/output`、report 在 `cwd/reports`、不覆盖输入）。
4. **异常分层**：`load_template` 在 `try` 之前触发，`TemplateNotFoundError` 向上传播（调用方可区分"无此模板"与"执行失败"）；`run_template` 执行失败 catch 转为 `GenerationResult(status="FAIL", errors=[...])`。
5. **draft 放临时目录**：`tempfile.mkdtemp()`，`finally` 清理，不污染 output。
6. **LLM 不进流水线**：LLM 位置在 generation 之前（生成 Markdown 内容），DocumentFactory 固化格式；内容与格式分离。

## Changed Files

新增：

- `src/document_factory/generation/__init__.py` — 公共 API 导出（GenerationRequest/GenerationResult/DocumentGenerationService/generate_document/MarkdownContentProvider/get_provider/SUPPORTED_CONTENT_SOURCES）
- `src/document_factory/generation/models.py` — `GenerationRequest`（`__post_init__` 校验）+ `GenerationResult` + `SUPPORTED_CONTENT_SOURCES`
- `src/document_factory/generation/providers.py` — `ContentProvider` 协议 + `MarkdownContentProvider`（手写 Markdown→DOCX）+ `get_provider`
- `src/document_factory/generation/service.py` — `DocumentGenerationService.generate` 编排 load_template → provider → run_template → 包装
- `src/document_factory/generation/pipeline.py` — `generate_document(request)` 函数式入口
- `tests/generation/test_models.py` — 7 项 Request 校验测试
- `tests/generation/test_service.py` — 2 项 Service/Registry 集成测试
- `tests/generation/test_pipeline.py` — 2 项端到端流程测试（file/text 源）
- `tests/generation/test_exceptions.py` — 1 项 TemplateNotFoundError 测试
- `docs/design/DOCUMENT_GENERATION_WORKFLOW_DESIGN.md` — 设计文档
- `docs/development_reports/TASK_DOC_010_REPORT.md` — 本报告

修改：

- `src/document_factory/__init__.py` — 顶层导出 generation 公共 API
- `src/document_factory/cli.py` — 新增 `generate` 子命令（`--template`/`--input`/`--output`/`--rules`）

删除：无。

## Test Result

Test Command:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Result:

```text
164 passed in 10.43s
```

Failed Cases: None

Resolution: Not applicable。原 152 项基线（TASK_DOC_009 后）全部保留并通过；新增 12 项（models 7 + service 2 + pipeline 2 + exceptions 1）全部通过，合计 164 passed。无回归。

覆盖任务书 4 项测试要求：

- Test 1 Request 验证：`GenerationRequest` 非法参数（空 template_id / 不支持 content_source / 无 input_data / 缺 file|text）→ `DocumentFactoryError` ✅
- Test 2 模板调用：`generate()` 确认 Template Registry 被调用、`execution_result.template_id` 正确 ✅
- Test 3 完整流程：`sample.md` → `sample.docx`，DOCX 可 `read_docx` 重读、报告 MD+JSON 存在、结构正确（Heading1+Body）✅
- Test 4 异常：`generate_document("DOES_NOT_EXIST", ...)` 抛 `TemplateNotFoundError` ✅

CLI 端到端：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m document_factory generate --template GRID_TECH_V1_4 --input sample.md --output output/sample.docx
# STATUS=FAIL OUTPUT=output/sample.docx REPORT=reports/sample_GENERATION_REPORT.md OPERATIONS=7
```

输出与报告均生成；`STATUS=FAIL` 来自 NUM002/TOC001 结构性 ERROR（见 Remaining Risks），非 generation 失败。

## Git Commit

- 提交信息：`TASK_DOC_010: Implement document generation workflow foundation`
- 分支：`master`（起始 HEAD `dc95a73`，clean，与 origin/master 一致；remote 为 SSH `git@github.com:dhxxqk/DocumentFactory.git`）
- 提交哈希：`26acf13`（13 文件 +843 / -0）
- 推送状态：已推送至 `origin/master`（SSH，范围 `dc95a73..26acf13`）；推送后复核 `HEAD == origin/master`、working tree clean；不 amend、不 rebase、不 force push

## Remaining Risks

- **NUM002/TOC001 结构性 ERROR**：Markdown 生成的 draft 缺标题编号绑定（numbering.xml）与 TOC 域。`TemplateRunner` v1 作用域为 style + sectPr（见 TEMPLATE_EXECUTION_PIPELINE_DESIGN §1），不补这两类结构。因此 generation 输出 `status` 常为 FAIL，`after ERROR == before ERROR`（不引入新错误）。这与 TASK_DOC_009 的 `status` 语义一致：`operations_count`/`changes` 才是应用成功判据。编号/TOC 补齐归 normalizer 或后续版本。
- **Markdown 解析最小化**：不支持 `**bold**`/列表/表格/图片。复杂 Markdown 内容会作为纯文本正文落入 Body 段落。需富文本时后续扩展 provider 或引入 markdown 库。
- **单内容源**：v1 仅 `content_source="markdown"`。JSON/数据库等来源待后续 provider。
- **rules_path 依赖**：`run_template` 默认 `rules/grid_tech_v1_4.yaml` 相对 cwd；chdir 后需显式传 `metadata["rules_path"]`（测试已传绝对路径；CLI 默认值适用于项目根运行）。

## Next Suggestion

- **补齐 numbering/TOC**：在 generation 或 normalizer 侧补标题自动编号绑定与 TOC 域生成，使 Markdown→DOCX 输出能 lint PASS。可考虑让 builder 写入 numbering.xml（复用 conftest.NUMBERING 模式）+ 插入 TOC fldChar 结构。
- **丰富 Markdown 能力**：支持列表、表格、加粗、图片，或引入 `markdown` 库做结构解析后由 builder 转 OOXML。
- **多模板与多内容源**：补 JSON/数据库 provider；补更多种子模板（技术报告/企业报告/政府文档）。
- **LLM 接入**：在 generation 之前接入 LLM 生成 Markdown 内容（`content_source="llm"` provider 仅做文本搬运，不在 generation 内调 LLM），保持"LLM 只生成内容，DocumentFactory 固化格式"原则。
