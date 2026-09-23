# DEFAULT_TECHNICAL_DOCUMENT_V1 验证清单（TASK_DOC_012）

本清单对应默认技术文档规范的验收项，自动化验证见
`tests/templates/test_default_specification.py`。

## 资产结构

- [x] `template.yaml` 声明 id/name/version/category/description，身份为默认规范
- [x] `definition/style_definition.yaml` 为规范性来源（页面/正文/标题/表格/题注/扩展策略）
- [x] `rules/` 分片：page_rules / paragraph_rules / heading_rules / table_rules / figure_rules
- [x] 项目根 `rules/default_technical_document_v1.yaml` 扁平 lint 契约可被 lint_engine 加载
- [x] `examples/default_test.md` 最小验证输入

## 去业务化

- [x] 全资产不含具体项目名称、编号、特定单位名称
- [x] 不包含特定业务章节名（仅 Heading Level 1/2/3）
- [x] 页眉策略为 `business_defined`，默认规范不提供固定页眉文本
- [x] lint 契约 `source` 指向规范定义文件而非任何业务文档

## 格式事实

- [x] A4 纵向，页边距 上2.8 / 下2.6 / 左2.8 / 右2.6 cm，页眉页脚距边界 1.4 cm
- [x] 正文仿宋 + Times New Roman，小四 12pt，1.5 倍行距，首行缩进 2 字符，两端对齐
- [x] H1/H2/H3 黑体 16 / 14 / 12pt，黑色，加粗，左对齐
- [x] 表头黑体、表体仿宋、五号 10.5pt，表头居中
- [x] 题注：黑体五号居中，图N-M / 表N-M 章-序编号（资产层事实，Runner v1 暂不执行）

## 继承与可消费性

- [x] `DEFAULT_TECHNICAL_DOCUMENT_V1` 被默认 Registry 注册，`extends` 为空
- [x] 科研实施方案模板经 `extends` 继承默认规范后，格式事实与父规范逐项一致
- [x] 子模板保留自身业务身份（id/name/category/source/rule_file）
- [x] 缺失父模板、继承循环在 build_registry 阶段报错
- [x] 默认规范可驱动 Markdown → DOCX 生成（标题/正文/页面正确）
- [x] 默认规范可驱动扁平 DOCX → 规范 DOCX 转换（正文/标题/表格样式正确）

## 已知边界（Runner v1）

- 题注（figure/caption）、页眉页脚部件、页码域不参与当前 OperationPlan，
  规范分片保留事实，待后续引擎扩展消费。
