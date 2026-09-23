# TASK Report

Task: TASK_DOC_009 — Template Execution Pipeline Foundation

Date: 2026-09-23 (+08:00)

Agent: Trae (GLM-5.2)

## Summary

RESULT: PASS

建立了 DocumentFactory 的 **Template Execution Pipeline**：把规定性 `TemplateDefinition`（TASK_DOC_008）驱动到 Formatting Operation Layer，产出可被 lint 再验证的 DOCX，完成第一个「定义→执行→验证」闭环。

新增 `src/document_factory/template_runner/` 模块（mapper + runner + models），公共入口 `run_template(template_id, input_path, output_path, ...)`。镜像 `normalizer.normalize` 全流程与守卫（lint before → apply → write_package → read_docx 有效性检查 → lint after → MD+JSON 报告）。

**关键设计决策**（经 Plan agent 压测修订）：

1. **命名 `run_template`**（非 `apply_template`）避免与既有描述性 `apply_template(template_path, ...)` 碰撞；CLI 子命令嵌套为 `template run`。
2. **不造并行类型**：OperationPlan 直接复用既有 `FontProfile`/`ParagraphProfile`/`PageFormat`，无 FontOperation 等。
3. **作用域 v1**：只应用样式元素 + sectPr（确定性根基）；直接 run 级修复仍归 normalizer。
4. **body 用粒度操作**：`apply_indent`/`apply_spacing`/`apply_alignment` + remove 列表（镜像 normalizer._normalize_body_ppr），以清理冲突属性（hanging/beforeLines 等），产出 lint-clean 正文。
5. **schema 微调**：`TableRule` 增加可选 `style_names: list[str]`（默认 `[]`，向后兼容），种子模板补 `style_names`。
6. **PAGE_SIZES 常量**放 `operations/document.py`（A4/A3/Letter），供 mapper 与未来 extractor 共用。

## Changed Files

新增：

- `src/document_factory/template_runner/__init__.py` — 公共 API 导出
- `src/document_factory/template_runner/models.py` — `OperationPlan`（复用 FontProfile/ParagraphProfile/PageFormat）+ `operations_count` 属性
- `src/document_factory/template_runner/mapper.py` — `build_operation_plan(template) -> OperationPlan`，纯函数，单位换算（chars*100 / line_spacing*240 / pt*20 / cm→twips）
- `src/document_factory/template_runner/runner.py` — `TemplateRunner.run(template, document)` + `run_template(...)` 编排器 + `_write_report`
- `tests/template_runner/__init__.py` — 包标识
- `tests/template_runner/test_mapper.py` — 11 项纯函数测试（字段/单位换算/landscape 交换/未知 page_size/operations_count=7/纯函数无文件系统）
- `tests/template_runner/test_runner.py` — 8 项端到端测试（产出有效输出/body+heading+page 变更/ERROR 下降/幂等/报告计数/不存在模板/缺失 body 样式/输出不可覆盖输入）
- `docs/design/TEMPLATE_EXECUTION_PIPELINE_DESIGN.md` — 设计文档
- `docs/development_reports/TASK_DOC_009_REPORT.md` — 本报告

修改：

- `src/document_factory/models.py` — 追加 `ExecutionResult` dataclass + `to_dict()`
- `src/document_factory/operations/document.py` — 新增 `PAGE_SIZES` 常量
- `src/document_factory/operations/__init__.py` — 导出 `PAGE_SIZES`
- `src/document_factory/templates/schema.py` — `TableRule` 增加可选 `style_names: list[str]` + `from_dict` 读取
- `templates/grid_tech_v1_4/template.yaml` — `tables` 下补 `style_names: [表格表头, 表格正文]`
- `src/document_factory/cli.py` — `template` 子命令组下新增 `run`（`--template-id`/`--input`/`--output`/`--report`/`--rules`）
- `src/document_factory/__init__.py` — 顶层导出 `run_template`、`ExecutionResult`

删除：无。

## Test Result

Test Command:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

Result:

```text
152 passed in 10.82s
```

Failed Cases: None

Resolution: Not applicable。原 133 项基线（TASK_DOC_008 后）全部保留并通过；新增 19 项（mapper 11 + runner 8）全部通过，合计 152 passed。无回归。

覆盖任务书 4 项测试要求：

- Test 1 模板加载：`load_template("GRID_TECH_V1_4")` 成功 ✅
- Test 2 转换数量：`build_operation_plan` 纯函数，断言字段 + `operations_count == 7` ✅
- Test 3 执行 pipeline：产出 DOCX 文件存在 + 可 `read_docx` 重读 + 报告 MD+JSON 存在 + `source_unchanged` + ERROR 下降 + 幂等（二次 run `changes==[]`）✅
- Test 4 异常：`run_template("DOES_NOT_EXIST", ...)` 抛 `TemplateNotFoundError` ✅

额外覆盖：landscape 维度交换、未知 page_size 仅应用 margins、缺失 body 样式记录 ERROR、输出不可覆盖输入、报告 counts 与真实 lint 一致。

## Git Commit

- 提交信息：`TASK_DOC_009: Implement template execution pipeline foundation`
- 分支：`master`（起始 HEAD `9ad07bd`，clean，与 origin/master 一致；remote 为 SSH `git@github.com:dhxxqk/DocumentFactory.git`）
- 提交哈希：（提交后回填）
- 推送状态：（提交后回填）

## Remaining Risks

- **Direct run-level 应用未实现**：当前只 stamp 样式元素 + sectPr。若文档有直接格式覆盖（run 级 rFonts/sz/color 直接格式），样式级应用后 run 仍可能显示旧直接格式。直接 run 修复归 normalizer（repair 语义）；如需 template_runner 也覆盖直接格式，后续扩展。
- **多 section 策略**：当前对所有非 sectPrChange sectPr 统一应用页面规则。若文档有多 section 且需差异化页面规则，当前不支持。
- **Header/Footer 未应用**：`HEADER_FOOTER_MIGRATION_SUPPORTED=False` 不变；页眉页脚仅分析不迁移。
- **status=PASS 的语义**：`ExecutionResult.status` 来自输出 DOCX 的真实 lint。若输入缺 TOC/封面等（lint ERROR 但 template_runner 不修复），输出 status 仍为 FAIL——这是设计如此（template_runner 只负责模板定义的格式事实，TOC/封面等结构属后续任务），用户不应把 status=FAIL 误解为模板应用失败。`operations_count>0` 与 `changes` 才是应用成功的判据。
- **table 仅应用 rPr**：表格样式只应用字体（rPr），不应用段落对齐（TableRule.alignment 是 cell 段落级，需 run 级应用，当前作用域外）。

## Next Suggestion

- **TASK_DOC_010 — Document Generation Interface**：实现"用户需求 → 选模板 → 生成 DOCX → 格式验证 → 交付"完整生产流程。TemplateRunner 将作为生成 pipeline 的格式固化环节（从空文档或结构化内容生成 → run_template 固化格式 → lint 验证 → 交付）。
- 可补齐 Direct run-level application，使 template_runner 也能覆盖有直接格式冲突的 run（向 normalizer 的 repair 能力靠拢，但保持 template-driven 语义）。
- 后续可补齐更多种子模板（技术报告、企业报告、政府文档），每个对应一份 specs/ 规范与 rules/ lint 规则。
