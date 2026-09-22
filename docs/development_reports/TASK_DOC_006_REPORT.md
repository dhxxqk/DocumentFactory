# TASK Report

Task: TASK_DOC_006 — Formatting Operation Layer 设计与实现（任务书原编号 TASK_DOC_005，见 Summary 冲突记录）

Date: 2026-09-22 (+08:00)

Agent: Trae + Doubao-Seed-Evolving

## Summary

RESULT: PASS

建立 DocumentFactory 的 Formatting Operation Layer（`src/document_factory/operations/`），作为规则引擎、模板引擎与未来 AI 调用方共享的确定性格式执行底座。操作层遵循三原则：确定性（无 LLM/无语义判断）、只执行（不判断是否需要修改）、输入显式（当前对象 + 目标格式 → 修改结果）。

重构后依赖方向：

```text
Before:
  Rule Engine     → normalizer（规则判定与底层 OOXML 写入混在一起）
  Template Engine → normalizer 私有函数（_atomic_text / _style_element /
                    _write_package / apply_format_profile + TEMPLATE_RULES hack）

After:
  Rule Engine (normalizer 判定)
  Template Engine (applier 判定)
  Future AI Agent
        │ 只传入已解析的目标格式
        ▼
  operations/（font / paragraph / style / table / document + 写入内核）
        ▼
  Validator（既有 lint / Profile 精确验证，未改动）
```

任务书与仓库事实冲突及裁定（按 CORE_RULES「仓库是唯一事实源」执行，开工前经任务提出者确认）：

1. **任务编号**：任务书编号 TASK_DOC_005 已被 2026-09-22 推送的 Agent Governance Layer 任务占用（提交 `3087334`）。裁定本任务顺延为 **TASK_DOC_006**；路线图相应顺延：Template Library + Registry → TASK_DOC_007，Document Structure Mapping → TASK_DOC_008。
2. **报告路径**：任务书写 `reports/TASK_DOC_005_REPORT.md`，按新生效的 REPORTING_STANDARD 放 `docs/development_reports/TASK_DOC_006_REPORT.md`（本文件）。
3. **提交规范**：任务书写 `refactor: ...` + `git add .`，按新生效的 GIT_WORKFLOW 使用 `TASK_DOC_006:` 前缀与逐文件显式暂存。
4. **版本号**：按任务书版本目标升级 `0.4.0a1 → 0.5.0a1`（无测试硬编码版本字符串）。

## Changed Files

新增：

- `src/document_factory/operations/__init__.py` — 公共 API 导出
- `src/document_factory/operations/_oxml.py` — 私有 OOXML 内核：Schema 顺序表、有序元素插入、属性/开关写入、`OperationContext` 变更记录
- `src/document_factory/operations/_package.py` — 私有原子落盘：`write_package`（未改部件字节复制 + 变更部件序列化 + temp/os.replace）、`atomic_text`
- `src/document_factory/operations/font.py` — `FontProfile`、`apply_font` 及中西文字体/字号/颜色/粗体/斜体/下划线细粒度操作
- `src/document_factory/operations/paragraph.py` — `ParagraphProfile`、`apply_paragraph_format` 及对齐/行距/缩进细粒度操作
- `src/document_factory/operations/style.py` — `STYLE_ROLES`（Normal/Title/Heading1-3）、`find_style_element`、`apply_style`
- `src/document_factory/operations/table.py` — `apply_table_font`、`apply_table_alignment`、`apply_table_format`（仅字体与对齐）
- `src/document_factory/operations/document.py` — `PageFormat`、`apply_section_properties`（w:pgSz/w:pgMar）；页眉页脚以 `HEADER_FOOTER_MIGRATION_SUPPORTED = False` 显式预留
- `tests/test_operations.py` — 9 个操作层单元测试

修改：

- `src/document_factory/normalizer.py` — 删除全部底层 XML 写入代码（lxml/etree/zipfile/tempfile 依赖、`_ensure`/`_set_properties`/`_set_toggle`/`apply_format_profile`/`_style_element`/`_write_package`/`_atomic_text`）；仅保留规则判定（角色选择、直接覆盖保护、别名校验等）与引擎编排，修改全部委托 operations；规则流变更记录的 property 名、Rule ID、规范出处逐条保持不变
- `src/document_factory/template/applier.py` — 不再导入 normalizer 任何符号；改用 operations；删除 `TEMPLATE_RULES` 伪规则 hack，改由 `OperationContext(rule_id="TEMPLATE", source="Template Profile 1.0")` 归属
- `src/document_factory/template/profile.py` — `_atomic_text` 改 `operations.atomic_text`
- `src/document_factory/__init__.py`、`pyproject.toml` — 版本 `0.5.0a1`
- `CHANGELOG.md` — 0.5.0-alpha 条目
- `README.md` — 标题 v0.5-alpha、项目结构增加 operations/、模板层复用描述改为 operations（最小文档同步）

删除：无。

说明：任务书规定的 6 个文件全部存在；另增 2 个下划线私有支撑模块（`_oxml.py`、`_package.py`）承载跨操作共享的 XML 内核与落盘原语，避免把底层细节塞进五个业务模块。

## Test Result

Test Command:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Result:

```text
89 passed in 4.28s
```

（基线 80 项全部通过，新增 9 项 operations 单元测试：字体整组应用与主题字体清除、字号半磅换算、bold/italic 开关、下划线与主题颜色清除、对齐生成有序 pPr、行距/缩进及属性移除、真实 DOCX 上的 Heading style 映射、表格字体与对齐、sectPr 页面属性顺序与页眉页脚预留。）

Failed Cases: None

Resolution: Not applicable。

端到端行为一致性补充验证（验证产物已清理）：

| 验证项 | 结果 |
|---|---|
| `--version` | `0.5.0a1` |
| `template apply` 真实 Demo | `STATUS=PASS MAPPINGS=5 CHANGED=70`，与 TASK_DOC_004 基线完全一致 |
| `normalize` 正式样本 | `STATUS=FAIL BEFORE_ERROR=42 AFTER_ERROR=3 CHANGED=6`，退出码 1（剩余 NUM002），与历史基线一致 |
| MCP 工具枚举 | 精确为 `['audit_document', 'format_document', 'list_presets']`，协议测试 2 passed |
| Template Demo 契约 | 文本/段落/编号 XML 字节保持由 `test_template_apply_preserves_inputs_and_applies_profile` 覆盖通过 |
| 架构红线 | `src/` 内不存在 template → normalizer 导入；不存在 `from normalizer import _xxx`；`TEMPLATE_RULES` 已删除；normalizer.py 无 lxml/etree/zipfile/q 等底层写入引用 |

## Git Commit

- 提交信息：`TASK_DOC_006: refactor: introduce formatting operation layer`
- 分支：`master`（起始 HEAD `2f3a809`，clean，与 origin/master 一致；remote 为 SSH `git@github.com:dhxxqk/DocumentFactory.git`）
- 提交哈希：`41510621fe240738e4ec8bcc149e97ead92ae411`（短哈希 `4151062`，经独立 docs 提交回填）
- 推送状态：已推送至 `origin/master`（SSH，范围 `2f3a809..`）；任务主提交 `4151062` 及其后 docs 回填提交均在远端，推送后复核 `HEAD == origin/master`、working tree clean；不 amend、不 rebase、不 force push

## Remaining Risks

- `apply_section_properties`（document.py）目前没有生产调用方：页面属性迁移仍按禁止事项未接入任何 CLI 流程，该操作仅由单元测试覆盖；它是后续任务的预留基础设施，不改变当前用户可见行为。
- FontProfile 新增 `underline` 能力（w:u），但规则 YAML 与 Template Profile schema 1.0 均不产生该字段，现有流程输出不受影响；待未来任务显式启用。
- 重构追求字节级行为等价并由 89 项测试守护，但 lxml 序列化在极端空白/属性顺序场景理论上可能产生差异；正式样本的 42→3 计数、70 条变更记录与 Demo 哈希级测试已显著降低该风险。
- normalizer 与 template 的角色判定逻辑仍各有一份（TASK_DOC_TRAE_001 报告 P1-1），本任务按「纯架构重构、不扩大范围」未合并，留给后续 Structure Mapping 任务统一。

## Next Suggestion

- TASK_DOC_007：Template Library + Registry（编号已因本次顺延）。
- 在 TASK_DOC_007 之前或同期，可让第一个真实迁移场景开始消费 `apply_section_properties`，把页面属性从「仅分析」推进到「可验证迁移」（需渲染环境就绪）。
- 后续可考虑把 normalizer 的规则组合函数与 template 的角色判定收敛为统一策略层（Structure Mapping 的前置）。
