# Spike 04: Block Translation Layout

Goal:

- translate extracted PDF text blocks with a Claude-compatible API
- keep translation page-local and layout-aware
- retry compact rewrites for blocks that do not fit well
- write translated text back into the original PDF without damaging backgrounds

Inputs:

- source PDF
- `blocks.jsonl` from `spikes/01_text_block_extraction`
- Anthropic-compatible environment variables:
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_AUTH_TOKEN`
  - optional: `ANTHROPIC_MODEL`

Pipeline:

1. load one page of text blocks
2. send page-local block translation request to Claude
3. estimate fit for each translated block
4. send a second compact-rewrite request only for problem blocks
5. remove source text natively at the PDF object level
6. insert translated text back into the same rectangles

Outputs:

- `output/<pdf_name>/translated_en.pdf`
- `output/<pdf_name>/native_redacted.pdf`
- `output/<pdf_name>/translations.json`
- `output/<pdf_name>/report.json`
- `output/<pdf_name>/comparison/page_XXXX_translation_comparison.png`
- `output/<pdf_name>/api_logs/*.json`

What this spike validates:

- whether block-level LLM translation is controllable enough for page restoration
- whether a second compacting pass can reduce overflow risk
- whether native PDF redaction + translation overlay is good enough for a practical MVP

Known limits:

- built-in PDF fonts are used in this spike for English validation, so exact font fidelity is not solved yet
- dense body-text pages may still need smarter paragraph reflow than single-box shrink-to-fit
- English-to-Chinese will likely need explicit CJK font embedding in a later spike
