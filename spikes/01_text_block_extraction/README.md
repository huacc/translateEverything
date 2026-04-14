# Spike 01: Text Block Extraction

Goal:

- extract page-level text blocks and bounding boxes from a digital PDF
- preserve page size and block order
- render page PNG files for later visual review
- render text-masked page PNG files for later translation overlay experiments
- classify repeated top and bottom blocks as initial header/footer candidates
- write streaming JSONL output so large PDFs can be processed without loading
  the whole result into memory

Outputs:

- `blocks.jsonl`: one JSON record per page
- `summary.json`: aggregate statistics for the run
- `pages/*.png`: optional rendered page images
- `masked_pages/*.png`: optional pages where extracted text block regions are
  painted over with sampled local background colors

Example:

```powershell
python -m pip install -r spikes\01_text_block_extraction\requirements.txt

spikes\pdf_conversion_spike\.venv\Scripts\python.exe -X utf8 `
  spikes\01_text_block_extraction\extract_text_blocks.py `
  --input 样本\中文\AIA_2021_Annual_Report_zh.pdf `
  --output-jsonl spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\blocks.jsonl `
  --summary-json spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\summary.json `
  --render-pages-dir spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\pages `
  --masked-pages-dir spikes\01_text_block_extraction\output\AIA_2021_Annual_Report_zh\masked_pages `
  --render-dpi 96
```
