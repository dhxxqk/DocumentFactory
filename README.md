# DocumentFactory v0.1

只读的 DOCX 文档质量工具：OOXML 解析 → 结构审计 → 中文报告 → PDF / PNG 渲染。不会修改、修复、重建或保存输入 DOCX，不调用 LLM、OCR 或自动排版服务。

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

两份正式基线从 `G:\文档修改测试` 原样复制，SHA-256 见 `reports/BASELINE_HASHES.json`。规范 Markdown 和体积较小的正式 DOCX 均纳入 Git。解析、审计、渲染均使用只读输入；审计与渲染在操作结束时校验输入哈希。测试不会改写正式样本。

如正式规范缺失，规则加载会拒绝审计；如正式样本缺失，对应回归测试明确 skip，不能将其作为完整验收通过。允许生成的最小 OOXML fixtures 仅用于自动测试，不是规范或 TEST_CASE_001 的替代品。

已验证依赖版本记录在 `reports/ENVIRONMENT.json`。可用 `python -m pip install -e '.[test,word]'` 在另一 Windows 环境重建依赖；原生 Office 后端和字体必须另行具备。

## 已知边界

不完整模拟 Word 排版、条件表格样式、复杂文字脚本、全部主题语言映射、浮动对象、文本框阅读顺序、修订结构、AlternateContent 和所有字段语法。遇到相关对象时输出诊断；条件表格格式可能影响字体，须结合后续渲染复核。支持标准 `word/document.xml` 包布局，不支持重定位的主文档 part；不会执行包中的宏、关系目标或外部导入内容。

不判定封面实际占几页、表格是否实际跨页、重复表头在视觉上是否出现、字体是否在排版引擎中被替换、图片中的字体与清晰度。本文档的结构检查结果不等同于视觉质量合格。

本机原生 Office 导出端到端验证受环境限制；测试中的 PDF→PNG 使用程序生成 PDF 验证栅格化，不伪称为正式 DOCX 渲染成功。

## 实现依据

格式要求只来自本地 V1.4 Markdown。OOXML 行为核对参考 Microsoft 官方文档：

- [numPr 与样式 pStyle 级别关联](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.numberingproperties?view=openxml-3.0.1)
- [rFonts 脚本和主题字体的跨样式覆盖规则](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/aef3c9a6-5d6c-434b-90b7-85e761fd8e62)
- [ThemeFontLanguages 与东亚主题语言](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.themefontlanguages?view=openxml-3.0.1)
- [Word Documents.Open 的 ReadOnly 参数](https://learn.microsoft.com/en-us/office/vba/api/word.documents.open)


## 下一阶段方向：从审计器演进为文档规范化引擎

> 架构决策日期：2026-09-19。当前 `v0.1` 能力边界保持不变；以下内容是后续版本的正式演进方向，不代表当前版本已经具备自动修复能力。

DocumentFactory 的长期定位不是 WPS / Word 的单一插件，而是一个可被 AI、CLI、桌面工具以及 Office/WPS 入口共同调用的 **文档分析、规范化与验证核心引擎**。

目标调用链：

```text
输入 DOCX
  ↓
Document Analyzer
  ↓
Document Structure Model
  ↓
Formatting Rules / Preset
  ↓
Normalization Engine
  ↓
Validation
  ↓
输出 DOCX + Validation Report
```

### 架构原则

1. **Core 与入口分离**：核心能力不绑定 WPS、Word、GUI 或任何单一 Agent。CLI、DeepSeek Harness、Codex、未来 WPS 插件都只是调用入口。
2. **规则配置化**：格式要求继续由正式规范和机器规则共同驱动，后续增加可复用的 preset/profile，不把字体、字号、段落等规则写死在入口代码中。
3. **先识别语义角色，再修改格式**：对 Title、Heading 1/2/3、Body、Table、Caption、Header、Footer 等结构分别归一化，而不是对全文进行无差别字体替换。
4. **保留只读审计能力**：现有 lint / audit 是后续自动修复的安全基座。修复前必须能够识别问题，修复后必须再次验证。
5. **不覆盖原始文档**：未来 normalization/fix 操作默认生成新文件，不直接改写输入 DOCX；必要时继续使用哈希校验与输出路径保护。
6. **验证闭环优先**：自动修改完成后生成机器可读和中文报告，明确列出修复项、剩余异常、无法确定项，禁止只因“成功保存文件”就宣称格式合格。
7. **Office/WPS 是可选高级后端**：优先保持 OOXML/Python 核心独立；只有 python-docx/OOXML 难以安全实现的能力，再考虑调用 Word/WPS 作为高级后端。
8. **AI 不直接控制底层格式细节**：AI 负责选择规范、解释意图和调用工具；确定性的排版修改由 DocumentFactory Core 执行。

### 外部参考实现

后续实现可参考 Word-Formatter-Pro 一类项目的工程思路，重点吸收“核心排版逻辑独立、CLI/Agent 作为薄入口、配置驱动、原文件保护”等模式。参考的目的是减少重复试错，不把 DocumentFactory 绑定为其 fork，也不把第三方项目作为运行时依赖。

### 下一阶段最小闭环

后续 `TASK_DOC_002` 应围绕以下最小闭环展开：

```text
输入 DOCX
→ 识别正文 / 标题 / 表格等语义角色
→ 读取 preset / rules
→ 对可确定对象执行字体、字号等规范化
→ 输出新的 DOCX
→ 重新运行 lint / audit
→ 生成 Validation Report
```

首阶段不做 GUI，不优先做 WPS 插件。WPS/Word 插件仅作为未来入口层；只有在核心引擎稳定后再评估实现。
