# 学术三线表 V1

适用于明确标记的 Word 原生矩形表格。其余页面、标题和段落保留文档原设置，默认电网规范沿用原规则。

## 使用

在 Word 表格属性中填写替换文字标题 `AcademicThreeLine`，对应 `w:tblPr/w:tblCaption/@w:val`。不同表需要不同格式时，在 `academic_tables.targets` 声明唯一标记和覆盖值。期刊参考规则可在单份文档中只匹配一个标记。无匹配、重复标记或不支持结构会产生 ERROR。

```powershell
python -m document_factory lint sample.docx --rules rules/academic_three_line_v1.yaml
python -m document_factory normalize sample.docx --rules rules/academic_three_line_v1.yaml --output output/academic.docx --report reports/academic.md
python -m document_factory audit output/academic.docx --rules rules/academic_three_line_v1.yaml --backend "Word COM"
```

`academic_ijlct_oup_v1.yaml` 对应 Duan 等（DOI 10.1093/ijlct/ctae052）印刷第 1095 页 Table 1 和 Table 2，角色标记为 `IJLCT-Table-1` 和 `IJLCT-Table-2`。紧邻表格之前的一段可通过 `caption_text` 精确匹配。表题局部加粗由内容层标记。

## 规则

- 一行表头和至少一行表体。表头跨页重复，单行保持完整，表格允许跨页。多行表头、合并、嵌套、浮动或含表结构修订的表格报告为不支持。
- 顶线、表头底线和底线可各自配置颜色、样式与宽度。磅值四舍五入至最邻近的 1/8 pt。表级边线使用 `nil` 抑制继承，三个可见边线各由一组单元格边缘绘制。去除行级冲突覆盖，并清空其余边线。支持实线、双线、虚线、点线。
- 明确宽度采用固定网格。通用规则缺省时保留输入列网格。对齐、边距、至少行高和段落间距按规则配置。字号使用半磅。局部斜体、上下标与 OMML 保留。数值文字精度由内容层提供。
- 使用现有 lint、normalize、audit 入口。规则支持同目录继承，目标数组替换，公共设置与逐表覆盖合并。报告记录规则散列，输出经过原子写入及内容完整性核验。

样本的三条 PDF 路径线宽均为 0.504 pt，表宽均为 240.948 pt，正文基线间距约 9.46 pt。列边界由可见列中心估计。正文 Sabon 8 pt，表题 Univers 7.5 pt。该样本规则使用 Georgia 和 Arial 替代字库。
