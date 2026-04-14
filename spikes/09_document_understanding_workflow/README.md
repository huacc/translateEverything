# Spike 09: Document Understanding Workflow

目标：

- 验证“文档级一次理解 -> 页面/组级标签 -> 最终翻译前上下文选择”这条 workflow 是否可行。
- 本轮不做最终翻译质量结论，先验证第二层标签是否能稳定产出、并被工程消费。

边界：

- 文档级：允许 LLM 基于整份年报证据做一次结构化理解。
- 组级：只输出标签，不输出译文。
- 工程侧：根据标签从文档背景中选择上下文包。

主要输出：

- `document_evidence.json`
- `document_background.json`
- `units.json`
- `group_labels.json`
- `selected_context_packs.json`
- `report.json`
- `prompt_exports/`
- `api_logs/`

默认实验页：

- `10,13,19,20`
