# Spike 02: Background Restoration

Goal:

- test high-fidelity strategies for removing source text from complex PDF pages
- avoid the low-quality rectangular fill result from Spike 01 on photo/background pages

Strategies:

1. `image_only`: rebuild the page from PDF image blocks only, ignoring text.
2. `opencv_inpaint`: render the full page, build a text mask from extracted bbox
   data, then run OpenCV inpainting.

Inputs:

- source PDF
- `blocks.jsonl` from `spikes/01_text_block_extraction`

Outputs:

- `original/page_XXXX.png`
- `mask/page_XXXX_mask.png`
- `image_only/page_XXXX_image_only.png`
- `inpaint/page_XXXX_inpaint.png`
- `comparison/page_XXXX_background_restoration_comparison.png`
- `report.json`

Example:

```powershell
spikes\pdf_conversion_spike\.venv\Scripts\python.exe -X utf8 `
  spikes\02_background_restoration\restore_background.py `
  --input 样本\中文\AIA_2021_Annual_Report_zh.pdf `
  --blocks-jsonl spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\blocks.jsonl `
  --output-dir spikes\02_background_restoration\output\AIA_2021_Annual_Report_zh `
  --pages 3,294 `
  --render-dpi 96
```
