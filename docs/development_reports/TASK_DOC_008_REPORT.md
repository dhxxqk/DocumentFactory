# TASK Report

Task: TASK_DOC_008 — Template Library & Registry

Date: 2026-09-23 (+08:00)

Agent: Trae (GLM-5.2)

## Summary

RESULT: PASS

建立了 DocumentFactory 的 **规定性模板资产层**：`templates/` 数据目录 +
`src/document_factory/templates/` 代码模块（schema / registry / loader）+ 种子模板
`GRID_TECH_V1_4`。完成后，系统获得「按模板 ID 查找确定性格式事实」的能力，格式
来源不再依赖 LLM 临时判断：

```text
template_id (GRID_TECH_V1_4)
        ↓
TemplateRegistry.get_template
        ↓
TemplateDefinition（规定性事实）
        ↓
（后续 TASK_DOC_009+）Formatting Operation Layer 执行
        ↓
DOCX Output
```

**与现有体系互补（非替代）**：

| 来源 | 性质 | 消费方 |
|---|---|---|
| `rules/grid_tech_v1_4.yaml`（lint 规则） | 审计（判对错） | lint_engine |
| `template/profile.py`（TemplateProfile） | 描述性（从 DOCX 提取） | template/applier |
| **`templates/*/template.yaml`**（本任务） | **规定性（目标事实）** | **operations 层** |

TemplateDefinition.rules 的字段对齐 `FontProfile` / `ParagraphProfile` /
`PageFormat` / 表格 operations，为后续 TemplateRunner 直接消费做好准备。本任务
**不**实现「从 TemplateDefinition 驱动 operations 层生成 DOCX」的完整 pipeline；
该 pipeline 属后续任务范围。

## Changed Files

新增：

- `src/document_factory/templates/__init__.py` — 模块公共 API 导出（TemplateDefinition / TemplateRegistry / load_template / list_templates 等）
- `src/document_factory/templates/schema.py` — 数据模型：TemplateDefinition / TemplateRules / BodyRule / HeadingRule / TableRule / TemplateSummary（frozen dataclass + from_dict 校验）
- `src/document_factory/templates/registry.py` — TemplateRegistry（register / get / list / has）+ TemplateNotFoundError / TemplateAlreadyRegisteredError
- `src/document_factory/templates/loader.py` — load_template / load_template_from_yaml / build_registry / default_registry + TemplateSchemaError；默认 Registry 懒加载项目根 `templates/` 下所有 `*/template.yaml`
- `templates/grid_tech_v1_4/template.yaml` — 种子模板，内容对齐 `rules/grid_tech_v1_4.yaml` 的确定性参数（正文仿宋 12pt、一/二/三级标题黑体 16/14/12pt、表格 10.5pt）
- `templates/README.md` — 模板目录说明、YAML 结构、与其他格式源的关系
- `tests/templates/__init__.py` — 包标识
- `tests/templates/test_schema.py` — schema 字段、from_dict、缺字段、类型校验、frozen、version 强制 str 等
- `tests/templates/test_registry.py` — register / get / has / list / 重复 / 不存在 / 异常继承关系
- `tests/templates/test_loader.py` — YAML 加载 / 缺字段 / 非 mapping / 非法 YAML / 缺文件 / build_registry 跳过空目录 / 默认 Registry 加载种子模板 / list_templates 含种子

修改：

- `src/document_factory/__init__.py` — 新增导出 `TemplateDefinition` /
  `TemplateNotFoundError` / `TemplateAlreadyRegisteredError` /
  `TemplateSchemaError` / `list_templates` / `load_template` /
  `load_template_from_yaml`，并入 `__all__`

删除：无。

## Test Result

Test Command:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Result:

```text
133 passed in 15.57s
```

Failed Cases: None

Resolution: Not applicable。原 89 项基线（TASK_DOC_007 报告记录）全部保留并
通过；新增 44 项（schema 16 + registry 11 + loader 17）全部通过，合计 133 passed。
覆盖验收标准全部测试要求：

- Test 1 注册模板 `register_template()` 成功 ✅
- Test 2 读取模板 `get_template()` 返回正确 ✅
- Test 3 不存在模板返回明确异常（TemplateNotFoundError）✅
- 额外覆盖：YAML schema 校验、default Registry 自动加载种子模板、
  `list_templates()` 排序与摘要字段、frozen dataclass 不可变、异常继承
  DocumentFactoryError

## Git Commit

- 提交信息：`TASK_DOC_008: Implement Template Library and Registry foundation`
- 分支：`master`（起始 HEAD `723e9b2`，clean，与 origin/master 一致；remote 为 SSH `git@github.com:dhxxqk/DocumentFactory.git`）
- 提交哈希：`646f9c4`（`646f9c4...`，12 文件 +1301 / -1）
- 推送状态：已推送至 `origin/master`（SSH，范围 `723e9b2..646f9c4`）；推送后复核 `HEAD == origin/master`、working tree clean；不 amend、不 rebase、不 force push

## Remaining Risks

- **TemplateRunner 未实现**：TemplateDefinition.rules 字段已对齐 operations 层入参，
  但尚未实现「TemplateDefinition → operations 调用 → DOCX」的执行器；属 TASK_DOC_009+
  范围，本任务刻意不越界。
- **默认 Registry 仅扫描项目根 `templates/`**：若未来需要支持用户自定义模板路径
  （如环境变量、CLI 参数），需扩展 `default_templates_dir()` 或在 CLI 层传入自定义
  Registry；当前实现已通过 `build_registry(templates_dir)` 暴露该能力。
- **种子模板覆盖范围有限**：`GRID_TECH_V1_4` 是唯一内置模板；技术报告 / 企业报告 /
  政府文档模板需在后续任务按真实规范补齐。本任务仅建立机制与一个种子样本。
- **YAML 编码**：使用 `utf-8-sig` 读取以兼容 BOM（与 lint_engine.load_rules 一致）；
  若后续编辑器使用纯 UTF-8 无 BOM 也能正常读取。
- **默认 Registry 懒加载**：首次调用 `load_template` / `list_templates` 时才扫描
  文件系统；若种子模板 YAML 有 bug，错误会在首次调用而非 import 时暴露——这是有意
  设计，避免 import 期副作用。

## Next Suggestion

- 下一阶段实现 **TemplateRunner**（建议任务编号 TASK_DOC_009）：给定 TemplateDefinition
  + 目标 DOCX（或空文档），调用 operations 层按 rules 逐项应用字体 / 段落 / 页面 /
  表格格式，产出符合模板的 DOCX。这是 TemplateDefinition 真正发挥作用的关键一环。
- 在补齐 TemplateRunner 后，可考虑增加 lint 规则验证「输出 DOCX 是否符合某
  TemplateDefinition」，形成「定义 → 执行 → 验证」闭环。
- 后续可补齐更多种子模板（技术报告、企业报告、政府文档），每个模板对应一份规范
  文档（specs/）与 lint 规则文件（rules/）。
