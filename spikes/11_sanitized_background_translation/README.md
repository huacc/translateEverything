# Spike 11: Sanitized Background Translation

目标：
- 在 `10_background_context_translation` 基础上，加一层可控的背景清洗与闭集控制。
- 不让 `document_background.json` 中的模糊规则直接进入翻译提示词。
- 把结构性表头、章节名、财务指标缩写优先交给工程层处理。

核心变化：
- 使用 `spikes/06_company_memory_learning/output/AIA_excl_2021_v4/company_memory.json` 作为历史公司记忆输入。
- 生成 `document_background_sanitized.json`。
- 合并 `glossary_spike11_merged.json`，补充结构性 exact/line map。
- 对 narrative / table / heading 三类单元使用不同术语输出模式。
- 保留 prompt 导出和 API 日志，便于检查。

主要输出：
- `translated_en.pdf`
- `native_redacted.pdf`
- `document_background_sanitized.json`
- `glossary_spike11_merged.json`
- `selected_context_packs.json`
- `translations.json`
- `report.json`
- `prompt_exports/`
- `api_logs/`
