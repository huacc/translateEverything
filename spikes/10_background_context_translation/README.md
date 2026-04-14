# Spike 10: Background Context Translation

目标：

- 直接把文档背景注入每个翻译单元。
- 不依赖开放式组级标签，不引入本体。
- 验证 `全局背景 + 页级章节背景 + 命中术语 + 风格规则` 是否能提升语义稳定性。

输入：

- `document_background.json` 来自 Spike 09
- `blocks.jsonl` 来自 Spike 01

输出：

- `translated_en.pdf`
- `native_redacted.pdf`
- `selected_context_packs.json`
- `translations.json`
- `report.json`
- `prompt_exports/`
- `api_logs/`
