# DocumentFactory v0.2-alpha

确定性的 DOCX 文档质量核心：OOXML 解析 → 结构审计 → 可确定格式规范化 → 修复后验证 → 中文 Markdown / JSON 报告，并保留 v0.1 的 PDF / PNG 可选渲染能力。`lint`、`render`、`audit` 继续只读；`normalize` 绝不覆盖输入，只生成新的 DOCX。不调用 LLM、OCR 或自动排版服务。

本项目位于任务书指定的 `G:\Workflows\DocumentFactory`。规范主源为 `specs/电网科技项目实施方案文档格式规范_V1.4.md`；`rules/grid_tech_v1_4.yaml` 是人工核对后的机器映射，每条规则记录规范章节和严重等级。规则修改应先核对 Markdown，不能把机器配置作为新的格式规范。

## Windows PowerShell 运行

需要 Python 3.10 或更新版本。以下命令不要求激活虚拟环境，也无需修改 PowerShell 执行策略。首次安装需要访问 Python 包源。

```powershell
Set-Location 'G:\Workflows\DocumentFactory'
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[test,word]'
& .\.venv\Scripts\python.exe -X utf8 -m document_factory --version
```

当前交付已安装项目虚拟环境，可直接执行后续命令。`-X utf8` 用于防止 Windows 终端中文乱码。

```powershell
# 结构审计及中文 Markdown / JSON 报告
& .\.venv\Scripts\python.exe -X utf8 -m document_factory lint `
  'testcases\第三周_规划管理能力_培训材料_格式规范V1.4.docx' `
  --rules 'rules\grid_tech_v1_4.yaml' `
  --report 'reports\TEST_CASE_001_LINT_REPORT.md'

# 确定性规范化：lint before → normalize → lint after → Validation Report
& .\.venv\Scripts\python.exe -X utf8 -m document_factory normalize `
  'testcases\第三周_规划管理能力_培训材料_格式规范V1.4.docx' `
  --rules 'rules\grid_tech_v1_4.yaml' `
  --output 'output\normalized\TEST_CASE_001_formatted.docx' `
  --report 'reports\TEST_CASE_001_NORMALIZATION_REPORT.md'

# 只渲染，不进行结构检查
& .\.venv\Scripts\python.exe -X utf8 -m document_factory render `
  'testcases\第三周_规划管理能力_培训材料_格式规范V1.4.docx' `
  --output-dir 'output\render\TEST_CASE_001'

# 完整审计：lint + render + report
& .\.venv\Scripts\python.exe -X utf8 -m document_factory audit `
  'testcases\第三周_规划管理能力_培训材料_格式规范V1.4.docx' `
  --rules 'rules\grid_tech_v1_4.yaml' `
  --report 'reports\TEST_CASE_001_LINT_REPORT.md' `
  --output-dir 'output\render\TEST_CASE_001' `
  --timeout 120 --dpi 144
$LASTEXITCODE

# 自动测试，测试文档和渲染 fixture 放在 output 下的独立目录
& .\.venv\Scripts\python.exe -X utf8 -m pytest -q --junitxml=reports/pytest.xml
```

所有 CLI 输出路径以当前目录为工程根目录。报告路径必须位于 `reports/`，渲染路径必须位于 `output/`；越界路径和覆盖输入的路径会被拒绝。应从工程根目录运行，不要在 `testcases/` 内执行命令。

| 退出码 | 含义 |
|---:|---|
| 0 | 请求的操作完成，结构审计无 ERROR（仍可能有 WARNING） |
| 1 | 结构审计 FAIL，报告已生成 |
| 2 | 输入、规则、路径或执行错误 |
| 3 | 渲染不可用或失败；audit 仍生成结构报告。优先于结构 FAIL 的退出码 |

`normalize` 的退出码 1 表示新 DOCX 和 Validation Report 已安全生成，但修复后 lint 仍有 ERROR；不能把“成功输出”误报为文档完全合规。CLI 同时打印 `STATUS`、`OUTPUT`、`REPORT`、`BEFORE_ERROR`、`AFTER_ERROR` 和 `CHANGED`。

## Python 结构化接口

核心逻辑不依赖 CLI 文本，可直接供后续 Agent / MCP 薄适配层调用：

```python
from document_factory import normalize

result = normalize(
    "input.docx",
    "rules/grid_tech_v1_4.yaml",
    output_path="output/normalized/input_formatted.docx",
    report_path="reports/input_NORMALIZATION_REPORT.md",
)

print(result.status, result.before_counts, result.after_counts)
print(result.output_path, result.report_path, result.source_unchanged)
```

`NormalizationResult` 提供 `status`、输入/输出/报告路径、输入/输出 SHA-256、前后计数、逐项 `changes`、剩余问题和 `source_unchanged`；`to_dict()` 可直接用于 MCP/Agent 的 JSON 序列化。

## 渲染后端

按 LibreOffice → Microsoft Word COM 的顺序尝试，支持 `--backend 'LibreOffice'` 或 `--backend 'Word COM'` 指定后端。

- LibreOffice：通过 PATH、标准 Windows 安装目录或 `DOCUMENT_FACTORY_SOFFICE` 环境变量查找。每次使用独立用户配置目录和私有 DOCX 副本。
- Word COM：需要真正的 Microsoft Word、有效 COM 注册和 `pywin32`。独立进程打开私有副本，`ReadOnly=True`，禁用宏和自动链接更新，导出后关闭且不保存。超时只清理该次工作进程，不结束用户已有 Word 会话。
- 本机当前没有检出可用 LibreOffice / Microsoft Word。WPS 兼容的 `Word.Application` 注册不能作为 Word 后端成功的证据。实际样本返回 **RENDER_UNAVAILABLE**，未生成正式样本 PDF / PNG。
- 有可用后端时，PyMuPDF 将导出 PDF 逐页转 PNG。每次成功结果位于 `output/render/<名称>/run_<唯一标识>/document.pdf` 和 `page_001.png` 等文件中；`render_result.json` 指向本次结果，避免混入旧页。
- 原文档的目录缓存可能与不同排版引擎的导出结果有差异。v0.1 不承诺刷新全部域，不对图片作视觉质量判定。

如已有非标准路径的 LibreOffice，可设置后重跑 audit：

```powershell
$env:DOCUMENT_FACTORY_SOFFICE = 'D:\Apps\LibreOffice\program\soffice.exe'
```

## 项目结构

```text
specs/                         正式 Markdown 规范（原样复制）
rules/grid_tech_v1_4.yaml        规则、阈值、字体别名、规范出处
testcases/                     正式回归样本（60624 字节，纳入 Git）
templates/                     预留目录，无模板生成能力
src/document_factory/
  models.py                    文档、段落、样式、检查结果数据模型
  docx_reader.py               ZIP / OOXML、部件、节、段落、Run、表格、域
  style_resolver.py            basedOn、字符样式、直接格式、主题、属性来源
  numbering_analyzer.py        numPr、pStyle、numStyleLink、级别覆盖及 numId=0
  toc_analyzer.py              简单域/复杂域、级别、额外来源与手写目录迹象
  section_analyzer.py          A4、方向、页边距、前置标题及首章分页证据
  table_analyzer.py            表格专用样式、继承、缩进、间距、行距及字体
  lint_engine.py              规则加载、正文/标题/Run 检查及结果聚合
  normalizer.py               确定性 OOXML 规范化、原子落盘、前后 lint 与 Validation Report
  renderer.py                 后端探测、私有副本、PDF 和 PNG、失败状态
  _word_export.py             有界 Word COM 工作进程
  report_writer.py            中文 Markdown 和完整机器可读 JSON
  output_paths.py             输出路径边界检查
  cli.py / __main__.py        lint / render / audit 命令
tests/                         最小 OOXML fixtures 与正式样本回归
output/                        逐页渲染、隔离临时文件、测试 fixtures（不纳入 Git）
reports/                       审计报告、任务报告、基线 SHA-256、pytest 结果
```

## 规则与判定

规则目录见 `reports/TASK_DOC_001_REPORT.md`，每条结果提供 Rule ID、Severity、对象类型、部件、Paragraph 或 Table/Row/Cell/Run、实际值、预期值、说明、规范出处。定位不依赖无法从 XML 可靠取得的 Word 页码。

`ERROR > 0` 即 `RESULT=FAIL`。通过的检查以 `INFO / PASS` 记录；`INFO` 总数包括 PASS 记录。`WARNING / UNSUPPORTED` 表示仍需人工验证，不能据此宣布全部格式合格。JSON 保存全部检查，Markdown 明细只列非 PASS 记录，避免数千条通过记录掩盖问题。

- 真实标题：段落样式类型、内置样式名及 customStyle 属性共同判定；标题大纲级别、基于标题的自定义样式、短编号加粗段落作为候选报警，不能只因看起来像标题就判合规。
- 自动编号：查找具体 numId、abstractNum、级别、pStyle、样式绑定、numStyleLink 和 lvlOverride；`numId=0` 是取消编号。样式内 ilvl 不替代编号定义的 pStyle 级别关联。
- 字体：按中文、ASCII 和非 ASCII 拉丁文字检查；每个脚本的直接字体/主题字体作为同一个继承槽处理。主题取值追溯 `themeFontLang`；无法确定时报 UNSUPPORTED。不把纯英文 Run 的 eastAsia 属性当作中文错误。
- 正文：已应用专用正文样式的段落执行明确检查；长 Normal 段落仅标疑似正文 WARNING，封面、目录结果、图表题、表格不强制套正文规则。
- 表头：重复表头标记可确定；首行只是默认候选，不符合时为 WARNING。识别专用封面样式的表格，报告 §3.2 / §6.1 语义冲突供人工判断，不把封面信息表直接判为普通内容表。
- 物理长度首行缩进不擅自换算成字符缩进；横向节只提示确认用途；“页面结构有分页依据”不等同于实际页面经过视觉验收。

## 基线与可复现性

两份正式基线从 `G:\文档修改测试` 原样复制，SHA-256 见 `reports/BASELINE_HASHES.json`。规范 Markdown 和体积较小的正式 DOCX 均纳入 Git。解析、审计、渲染均使用只读输入；规范化也只读取输入，通过同目录临时 ZIP 和原子替换生成新文件，并在操作前后校验输入哈希。未修改的 ZIP 部件逐项原样复制。测试不会改写正式样本。

如正式规范缺失，规则加载会拒绝审计；如正式样本缺失，对应回归测试明确 skip，不能将其作为完整验收通过。允许生成的最小 OOXML fixtures 仅用于自动测试，不是规范或 TEST_CASE_001 的替代品。

已验证依赖版本记录在 `reports/ENVIRONMENT.json`。可用 `python -m pip install -e '.[test,word]'` 在另一 Windows 环境重建依赖；原生 Office 后端和字体必须另行具备。

## 已知边界

规范化只处理现有 StyleResolver 明确认定的 Heading 1/2/3、明确使用“正文”样式的段落/Run，以及明确使用表格表头、表格正文、表格正文-居中样式的对象。不会把 Normal、疑似标题或疑似表头自动重分类，不会修改编号和 TOC。

不完整模拟 Word 排版、条件表格样式、复杂文字脚本、全部主题语言映射、浮动对象、文本框阅读顺序、修订结构、AlternateContent 和所有字段语法。遇到相关对象时输出诊断；条件表格格式可能影响字体，须结合后续渲染复核。支持标准 `word/document.xml` 包布局，不支持重定位的主文档 part；不会执行包中的宏、关系目标或外部导入内容。

不判定封面实际占几页、表格是否实际跨页、重复表头在视觉上是否出现、字体是否在排版引擎中被替换、图片中的字体与清晰度。本文档的结构检查结果不等同于视觉质量合格。

本机原生 Office 导出端到端验证受环境限制；测试中的 PDF→PNG 使用程序生成 PDF 验证栅格化，不伪称为正式 DOCX 渲染成功。

## 实现依据

格式要求只来自本地 V1.4 Markdown。OOXML 行为核对参考 Microsoft 官方文档：

- [numPr 与样式 pStyle 级别关联](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.numberingproperties?view=openxml-3.0.1)
- [rFonts 脚本和主题字体的跨样式覆盖规则](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/aef3c9a6-5d6c-434b-90b7-85e761fd8e62)
- [ThemeFontLanguages 与东亚主题语言](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.themefontlanguages?view=openxml-3.0.1)
- [Word Documents.Open 的 ReadOnly 参数](https://learn.microsoft.com/en-us/office/vba/api/word.documents.open)


## TASK_DOC_003 MCP 接入准备

v0.2-alpha 已完成入口无关的 `normalize(...)` Core 和稳定结构化结果，可在 TASK_DOC_003 中增加薄 MCP 适配：参数校验后调用 Core，将 `NormalizationResult.to_dict()` 返回给调用方即可。MCP 层不应复制 OOXML 判断、格式目标、lint 或报告逻辑，也不应让 Agent 直接决定底层 XML 修改。

当前版本没有实现 MCP Server、GUI、WPS/Word 插件、HTTP API、云服务或 LLM API；这些能力不属于 TASK_DOC_002。
