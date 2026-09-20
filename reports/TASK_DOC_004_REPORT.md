# TASK_DOC_004 执行报告

## 1. 基础信息

- 实际生成时间（含时区）：2026-09-20T23:47:34+08:00
- RESULT：PASS
- DocumentFactory 版本：0.4.0a1（产品标识 0.4.0-alpha）
- 任务：Template Engine 基础架构设计
- Git 目标分支：`master`

## 2. 实现结果

Template Engine 已形成以下确定性链路：

```text
Template DOCX
    ↓ read_docx + StyleResolver
Template Analyzer / Extractor
    ↓
Template Profile schema 1.0 (JSON)
    ↓ existing normalizer format writer
Template Apply
    ↓ existing lint + profile validation
new DOCX + Markdown migration report
```

为保持现有导入契约，本任务保留 `normalizer.py`，没有同时创建会与其冲突的 `normalizer/` package。模板层通过 `normalizer.apply_format_profile`、现有属性记录器、原子 DOCX 写入和 lint 接入原 Core；没有复制 `StyleResolver` 级联解析或另建审计体系。MCP 仍只暴露 v0.3 的三个工具，本任务未新增 MCP tool。

### Template Analyzer

- 读取真实 DOCX，并提取 section 页面大小、方向、页边距和可确定的页码设置。
- 记录页眉/页脚部件、段落数、使用的 style 和字段类型。
- 通过现有 `StyleResolver` 提取 Paragraph Style 的中西文字体、字号、粗体、斜体、颜色、对齐、行距、段前后和缩进。
- 提取 Table Style 名称、可确定边框、条件样式事实，以及真实首表中的表头/表体可见格式。
- 只分析编号是否存在、实例数量和相关 style；不迁移复杂编号。

### Template Profile

- schema 版本：1.0。
- 支持 JSON 序列化、原子保存、读取、字段校验和人工修改。
- 保存模板来源、SHA-256、生成时间、页面、页眉页脚、styles、roles、table styles/defaults、numbering 和 diagnostics。

### Template Apply

- 映射目标文档中已经明确存在的 `Normal`、`Title`、`Heading 1/2/3`。
- 应用上述样式的字体、字号、粗斜体、颜色、对齐、行距、段前后和缩进。
- 对表格首行/表体应用可确定的字体、字号和对齐。
- 输出新 DOCX 和 Markdown Template Apply Report；拒绝覆盖输入或模板。
- 写入前后校验模板和输入 SHA-256；输出再次由 `read_docx` 读取，并执行 Profile 精确验证与现有 lint。
- 不修改文本内容、段落数量、章节顺序和编号 XML。

## 3. CLI 与 Python 接口

新增 CLI：

```text
document-factory template analyze TEMPLATE [--output PROFILE]
document-factory template apply --template TEMPLATE --input TARGET [--output DOCX] [--report MD]
```

新增 Python 接口：

- `analyze_template(...)`
- `TemplateProfile.save(...)` / `TemplateProfile.load(...)`
- `apply_template(...) -> TemplateApplyResult`

## 4. 自动测试

执行命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q --junitxml=reports\pytest.xml
```

结果：

```text
80 passed in 4.20s
```

新增 4 项模板测试，覆盖：

- Analyzer 读取、Profile JSON、往返读取、字体、style 数量、页面、页眉页脚、表格和编号事实。
- Apply 新文件输出、输入/模板哈希保护、文本与顺序不变、格式符合 Profile、编号 XML 不变、输出可读及 lint 可执行。
- 覆盖输入保护和无效 Profile 拒绝。
- `template analyze` / `template apply` 真实 CLI。

既有 normalize、lint、render、audit、MCP 和 DSH 相关自动测试全部通过；未降低 severity、跳过检查或删除检查逻辑。

## 5. Demo 结果

Demo 输入：

- `testcases/template/template_demo.docx`
- `testcases/template/target_demo.docx`

生成：

- `reports/template_demo_profile.json`
- `output/template/target_demo_formatted.docx`
- `reports/template_apply_report.md`

实测结果：

| 项目 | 结果 |
|---|---|
| `template analyze` | PASS，退出码 0 |
| Profile schema | 1.0 |
| Paragraph Style 数量 | 7 |
| Table Style 数量 | 1 |
| `template apply` | PASS，退出码 0 |
| Style 映射 | 5 |
| 属性修改记录 | 70 |
| Profile 验证不一致 | 0 |
| 输出可由 DocumentFactory 读取 | PASS |
| 输入/模板未变化 | PASS |

哈希：

| 文件 | SHA-256 |
|---|---|
| `template_demo.docx` | `d4dd7faf0ac4d56ce13d1e28b5813ae7cd6f3e59b223f78f7adfce319ad39909` |
| `target_demo.docx` | `40b99ea3b5691477fca55f82cf1551fae09f443e75ce9249890a375ddeabafb2` |
| `target_demo_formatted.docx` | `35bc70cf6b2d84fac5b9f7bfa8e30c3decce764519d791c06b0cd7ba4ddd9a68` |

现有电网 V1.4 lint 对 Demo 的计数为 ERROR `45 → 31`、WARNING `3 → 3`。该 Demo 用于验证模板迁移，不是完整电网项目文档，因此既有 lint 的结果仍为 FAIL；报告未将 Template Apply 的 PASS 误述为电网规范全部合格，也未改变任何 lint 规则或 severity。

## 6. 新增与修改文件

新增：

- `src/document_factory/template/__init__.py`
- `src/document_factory/template/analyzer.py`
- `src/document_factory/template/profile.py`
- `src/document_factory/template/extractor.py`
- `src/document_factory/template/applier.py`
- `tests/test_template_engine.py`
- `testcases/template/template_demo.docx`
- `testcases/template/target_demo.docx`
- `reports/template_demo_profile.json`
- `reports/template_apply_report.md`
- `reports/TASK_DOC_004_REPORT.md`

修改：

- `.gitignore`
- `src/document_factory/normalizer.py`
- `src/document_factory/models.py`
- `src/document_factory/cli.py`
- `src/document_factory/__init__.py`
- `tests/conftest.py`
- `README.md`
- `CHANGELOG.md`
- `pyproject.toml`
- `reports/pytest.xml`

## 7. 当前不支持范围

- AI 理解文档语义、自动判断标题或自动重写文字。
- 添加、删除或重排段落与章节。
- 复杂编号迁移、TOC 创建/刷新和编号自动修复。
- 图片、浮动对象、文本框或视觉布局迁移。
- 页面、页眉、页脚和表格边框的实际迁移；本版只分析并写入 Profile。
- 自动生成 Word 模板。
- Template MCP tool、HTTP MCP、WorkBuddy、GUI、WPS/Word 插件或 LLM API。

## 8. 结论

TASK_DOC_004 的 PASS 标准已满足：模板可分析为版本化 Profile，Profile 可保存/读取，最小 Apply 可在保护输入的前提下生成可读取的新 DOCX，输出可由现有 lint 验证，既有 Core 回归全部通过。Template Engine Core 已具备后续单独评估薄 MCP 适配的基础，但本任务按范围未新增 MCP tool。
