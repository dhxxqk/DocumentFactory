# 学术三线表字体精修 R2 开发报告

任务 `TASK_DOC_ACADEMIC_TABLE_001 R2`，日期 2026-11-26，执行 Agent Codex。基线 `bef7b82098b7f86f4e0a087adf8f53da8a9aed58`。

## Summary

`ENGINE_PASS`，`FONT_SUBSTITUTED`，`VISUAL_REVIEW_PENDING`。通过既有学术表规范化和渲染链增加可选字体检查。预检验证 Word COM、注册字体文件、原生字重或斜体和本地字形覆盖。实际 Word PDF 审计逐字核对嵌入证据、字体名称、字形变体、字号及坐标，报告不能唯一确认的结果。Georgia／Arial 基线继续可运行。

实际样本的下标从 R1 5.04 pt 调整至 6.00 pt，原文约 6.08 pt。相对变量基线下移由 0.48 pt 改为 1.56 pt，原文约 1.36 pt。原生下标和局部斜体继续可编辑。两件样本的最大表宽差 0.062 pt、列中心差 0.065 pt、基线差 0.441 pt。原表三条 0.504 pt 线在 Word 中量化到 0.50 pt，实际 PDF 仍为 0.48 pt。论文表格和字体对照证据位于项目交付目录。

## Changed Files

- `academic_font_audit.py` 加入后端、已安装字形和 PDF 资源核验。
- `academic_tables.py` 与 `operations/academic_table.py` 增加按角色选择字体、原生下标定位及可选段落行距。
- `lint_engine.py`、`normalizer.py`、`report_writer.py` 接入预检结果、输出闸门和实际渲染字体报告。
- `rules/academic_ijlct_oup_r2.yaml` 记录实测替代样式及允许的 PDF 名称，独立于 R1。
- `tests/test_academic_font_audit.py` 覆盖字体或变体缺失、缺字、后端不可核实、PDF 字重、斜体、尺寸、替换和无法定位。
- `specs/academic_three_line_v1.md` 说明运行方式、识别边界和报告状态。

## Test Result

Test Command `python -X utf8 -m pytest -q --tb=short --junitxml=reports/academic-r2/pytest.xml`。

Result `252 passed in 31.36s`，其中 11 项为本轮新增。两份 Word 正常通过预检及实渲染字体核对，规范化后 ERROR 和 WARNING 均为零，重复执行均零变更。逐格校核内容并复用经过散列校核的 R1 Excel。

Failed Cases 最终无失败。原字体的授权或本机安装无法确认，状态为替代。

Resolution 完成八组同环境对照后，以 Book Antiqua 正文和数学斜体、Times New Roman Bold 表头、Century Schoolbook 指标数字及 Segoe UI 系列表题进行交付。原 PDF 的 MTMI 只用于省略点。验收对照按同一物理比例生成。

## Git Commit

分支 `feat/academic-three-line-table-r2`。远端提交与分支核验记录随项目执行报告交付。

## Remaining Risks

字形仍有替代痕迹，包括衬线端点、小数点、表题间距和下标约 0.20 pt 的额外下移。R2 参考配置的精确段落行距仅针对测量样本。规范化的字体预检需要能确定 Windows 安装字体和 Word COM，PDF 核验的 UNKNOWN 会作为错误返回。视觉确认仍由用户完成。

## Next Suggestion

以三方对照供用户确认，确认后再进入实验 SVG 的后续工作。
