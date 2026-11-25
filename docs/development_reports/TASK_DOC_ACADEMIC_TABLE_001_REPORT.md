# DocumentFactory 学术三线表 V1 开发报告

任务 `TASK_DOC_ACADEMIC_TABLE_001`，执行日期 2026-11-25，执行 Agent Codex。

## Summary

结果 PASS。通过现有 `lint`、`normalize` 和 `audit` 增加学术三线表规则。目标由显式表格标记定位。三条边框由单元格边沿绘制，表级和行级清理旧样式冲突。文档写出、内容完整性和规范化前后检查继续使用 Core。旧规则与 MCP 默认入口保留原行为。

期刊参考配置从 DOI `10.1093/ijlct/ctae052` 印刷第 1095 页提取。Word COM 渲染两表各一页，均保留三条横线及内容。原 PDF 的三线为 0.504 pt，Word OOXML 量化为 0.5 pt，导出 PDF 实测 0.48 pt。两个样本的表宽偏差分别为 0.052 和 0.062 pt，基线的最大偏差分别为 0.335 和 0.443 pt。Excel 中 27 个节点和九模型 27 个数值已读回核验。样本和原表裁剪保存在项目交付目录。

## Changed Files

- `src/document_factory/operations/academic_table.py` 实现边线、冲突修复、列宽、行距、题注和保留数学 run 的表格操作。
- `src/document_factory/academic_tables.py` 验证配置、按标记定位表格、拒绝不支持类型并复用相同属性规则审计。
- `src/document_factory/lint_engine.py` 接入学术规则范围及同目录继承。
- `src/document_factory/normalizer.py` 将学术规则接入共用规范化、内容完整性与报告，保留继承规则散列。
- `src/document_factory/report_writer.py` 输出继承规则散列。
- `rules/academic_three_line_v1.yaml` 和 `rules/academic_ijlct_oup_v1.yaml` 提供通用样式与期刊参考样式。
- `tests/test_academic_tables.py` 新增正常路径、作用范围、重复执行、样式冲突、数学和不支持边界测试。
- `specs/academic_three_line_v1.md`、`README.md` 说明入口、标记和限制。

## Test Result

Test Command `python -X utf8 -m pytest -q --tb=short --junitxml=reports/academic/pytest_complete.xml`。

Result `241 passed in 27.22s`。新增 8 个测试，全部通过。Table 1 审计 ERROR 从 892 降至 0，Table 2 从 1386 降至 0。两表 WARNING 都为 0。第二次规范化均无变更，DOCX 包散列与第一次一致。

Failed Cases 最终无失败。开发过程中的不支持用例曾因变更警告的字段命名不符合现有报告契约而失败。首次在受限会话运行全量套件时，MCP stdio 子进程测试未能完成。

Resolution 改为报告契约要求的 `reason` 字段。经完整 Windows 会话重跑全部测试，包含 MCP stdio 测试。

## Git Commit

分支 `feat/academic-three-line-table`，从与远端 `master` 一致的 `7f7b7801d6e24af1168337f62eccba80546ed628` 建立独立开发副本。项目执行报告记录实际提交及 SSH 推送回读结果。

## Remaining Risks

合并、嵌套、浮动表、多行表头和结构修订报告为不支持。原刊 Sabon 和 Univers 字体未安装。使用 Georgia 和 Arial 还原字族特征，数字字形、表头字重和下标尺寸有可见差异。列边界来自 PDF 中可见列中心的反推。

## Next Suggestion

广东项目可直接引用本次交付的 Word 和 Excel 表格。其余 SVG 精修按后续任务范围执行。
