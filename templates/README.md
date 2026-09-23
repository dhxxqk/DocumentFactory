# Template Library

This directory holds the **prescriptive** Word format templates used by
DocumentFactory. Each subdirectory contains a single `template.yaml` that
describes the target format facts for one class of documents.

## Layout

```
templates/
├── README.md            (this file)
└── grid_tech_v1_4/
    └── template.yaml    电网科技项目实施方案模板 (GRID_TECH_V1_4)
```

## Adding a template

1. Create a subdirectory named after the template, e.g. `technical_report/`.
2. Add a `template.yaml` inside it. See `grid_tech_v1_4/template.yaml` for
   the canonical structure.
3. The default Registry auto-discovers any `*/template.yaml` on first access;
   no manual registration step is required.

## Template YAML structure

```yaml
id: UNIQUE_ID           # e.g. TECH_REPORT_V1
name: 技术报告模板
version: "1.0"
category: [report]
description: 用途说明
metadata:
  source: ...
  author: ...
  created_at: "YYYY-MM-DD"

rules:
  page:        { page_size, orientation, margins_cm, ... }
  body:        { style_name, chinese_font, latin_font, font_size_pt, ... }
  headings:
    h1: { word_style, chinese_font, latin_font, size_pt, color, bold, alignment }
    h2: { ... }
    h3: { ... }
  tables:      { header_font, body_font, latin_font, font_size_pt, alignment }
  font_aliases: { 仿宋: [仿宋, FangSong], ... }
```

## Relationship to other format sources

| Source | Nature | Consumer |
|---|---|---|
| `rules/*.yaml` (lint rules) | Audit (does it pass?) | lint_engine |
| `template/profile.py` (TemplateProfile) | Descriptive (extracted from DOCX) | template/applier |
| **`templates/*/template.yaml`** | **Prescriptive (target facts)** | **operations layer** |

TemplateDefinitions define *what the output should look like*; the operations
layer applies them deterministically; lint rules verify the result.
