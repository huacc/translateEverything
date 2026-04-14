# Spike 05: Annual Report Translation Control

Goal:

- create an independent spike for "annual report scenario lock + controlled translation"
- move stable rules out of prompt text and into explicit control assets
- validate whether glossary, pattern rules, and block-type policies can improve translation fidelity before layout fitting

Methodology:

- follow a minimal `Spec Stack` instead of treating prompt as the whole system
- keep stable constraints in config files, and render prompt from those configs
- separate deterministic controls from probabilistic LLM translation

Control assets:

- `configs/domain_spec.json`
  - scenario and register lock
- `configs/task_spec.json`
  - translation priorities, forbidden actions, block-type policies
- `configs/validation_spec.json`
  - protected token categories and compact-retry policy
- `configs/glossary_zh_en_seed.json`
  - exact mappings, line mappings, reusable term mappings
- `configs/patterns_zh_en.json`
  - preserve rules and regex templates

Script:

- `translate_with_controls.py`
  - classify each block as `heading`, `body`, `label`, `sidebar_nav`, `chart_label`, or `footer`
  - resolve deterministic translations first through glossary and pattern rules
  - send only unresolved blocks to the model
  - allow compact retry only for block types declared safe by `validation_spec`
  - write translation provenance into the report

Tooling:

- `tools/generate_glossary_candidates.py`
  - scan `blocks.jsonl`
  - extract repeated short texts and line-level candidates
  - generate candidate glossary JSON for iterative enrichment

Outputs:

- `output/<pdf_name>/translated_en.pdf`
- `output/<pdf_name>/native_redacted.pdf`
- `output/<pdf_name>/translations.json`
- `output/<pdf_name>/report.json`
- `output/<pdf_name>/comparison/page_XXXX_translation_comparison.png`
- `output/<pdf_name>/api_logs/*.json`

What this spike validates:

- whether annual-report context lock reduces "summary style" translations
- whether exact glossary and pattern preservation can stabilize headings, footers, and chart labels
- whether compact retry should be restricted to specific block types instead of applied globally
- whether the control dimensions are explicit enough to iterate without constantly rewriting prompts

Run:

```powershell
$env:ANTHROPIC_BASE_URL="..."
$env:ANTHROPIC_AUTH_TOKEN="..."

python spikes\05_annual_report_translation_control\translate_with_controls.py `
  --input 样本\中文\AIA_2021_Annual_Report_zh.pdf `
  --blocks-jsonl spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\blocks.jsonl `
  --output-dir spikes\05_annual_report_translation_control\output\AIA_2021_Annual_Report_zh_first20 `
  --pages 1-20 `
  --source-language "Traditional Chinese" `
  --target-language English
```

Generate glossary candidates:

```powershell
python spikes\05_annual_report_translation_control\tools\generate_glossary_candidates.py `
  --blocks-jsonl spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\blocks.jsonl `
  --output spikes\05_annual_report_translation_control\output\aia_glossary_candidates.json
```
