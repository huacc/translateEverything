# Spike 03: PDF Native Text Replace

Goal:

- verify a higher-fidelity route than image masking / inpainting
- remove source text at the PDF object level, instead of painting over pixels
- reinsert placeholder translated text into the original text rectangles

Why this spike exists:

- Spike 01 proved that rectangle masking damages photo / design backgrounds
- Spike 02 showed that OpenCV inpaint still creates visible artifacts on complex pages
- many PDF pages already separate background image / vector graphics / text objects
- if we remove only text objects before rendering, the background can stay intact

Strategy:

1. read text block rectangles from `spikes/01_text_block_extraction/output/.../blocks.jsonl`
2. apply PDF redactions with:
   - `images=0`
   - `graphics=0`
   - `text=0`
3. this removes text only and keeps image / vector background objects
4. infer a simple text style per block from the original page
5. write placeholder English back into the same rectangles

Outputs:

- `output/<pdf_name>/native_redacted.pdf`
- `output/<pdf_name>/native_translated_placeholder.pdf`
- `output/<pdf_name>/original/page_XXXX_original.png`
- `output/<pdf_name>/redacted/page_XXXX_redacted.png`
- `output/<pdf_name>/translated/page_XXXX_translated.png`
- `output/<pdf_name>/comparison/page_XXXX_native_replace_comparison.png`
- `output/<pdf_name>/report.json`

Key expectation:

- no source / translated text overlap
- much cleaner background than image masking or inpainting
- still page-local and compatible with multi-page processing

Known limits:

- if the source PDF stores text as outlines, paths, or embedded inside images, this spike will not remove it
- translation reflow is still approximate because English / Chinese expansion differs
- fonts are not preserved exactly in this spike; it uses a safe built-in font for verification
