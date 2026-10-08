# INTERNAL_TRAINING_DOCUMENT_V1 验证清单

验证对象仅为格式；正文文本由 Content Integrity Gate 逐字守卫。

- [ ] 模板无 `extends`，Registry 中独立注册（id 唯一）。
- [ ] 三 section 结构保持：portrait → landscape → portrait，分节类型与宽高/边距符合 §2。
- [ ] （MVP 暂缓）首页【第X周】段落的独立「文档标题」样式；MVP 中该段按 Heading 1 规范化（字号归一为 16pt，24pt 外观不保留），文本不变。
- [ ] 普通 Heading 1/2 保持内置样式与 numId=1 自动编号：华文中宋 16/15pt 加粗黑色。
- [ ] 正文 Normal：宋体 12pt、1.5 倍行距、首行缩进 2 字符、两端对齐。
- [ ] 表头：宋体 10.5pt 加粗、水平居中、黑色、底纹 D7D7D7（显式 fill，无 themeFill*）。
- [ ] 表体：宋体 10.5pt；单元格水平对齐 before/after 分布逐格一致。
- [ ] media 部件 SHA-256 集合、嵌入 rId 顺序、document.xml.rels 图片目标不变。
- [ ] 输入文件 SHA-256 全程不变；输出为新文件，绝不覆盖输入。
- [ ] 脱敏 synthetic fixture 测试通过后，才允许对用户显式指定真实文档 Pilot。
