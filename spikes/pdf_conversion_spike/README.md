# PDF Conversion Spike

This spike isolates PDF conversion experiments from the rest of the repo.

Current focus:
- evaluate `MarkItDown` on the sample annual reports under `../../样本`
- keep a repeatable `PDF -> Markdown -> DOCX` pipeline
- keep a repeatable `PDF -> DOCX -> PDF` restore pipeline
- capture outputs in one place for manual review

This project is not a promise of layout fidelity.
`MarkItDown` is useful for text and structure extraction, but complex PDF layouts
do not round-trip cleanly through Markdown.

## Inputs

The runner reads PDF files from the repo sample directory:

- `../../样本/中文/*.pdf`
- `../../样本/英文/*.pdf`

It does not copy the sample files.

## Outputs

Generated files go under:

- `output/markitdown/<lang>/<document>/raw.md`
- `output/markitdown/<lang>/<document>/cleaned.md`
- `output/markitdown/<lang>/<document>/<document>_from_markdown.docx`
- `output/markitdown/summary.json`
- `output/pdf2docx/<lang>/<document>/<document>_via_pdf2docx.docx`
- `output/pdf2docx/summary.json`

## Install

```powershell
python -m pip install -r spikes\pdf_conversion_spike\requirements.txt
```

## Run

Convert one sample and also emit a DOCX rebuilt from Markdown:

```powershell
python -X utf8 spikes\pdf_conversion_spike\run_markitdown_batch.py --sample AIA_2021_Annual_Report_zh --docx
```

Convert all Chinese PDFs:

```powershell
python -X utf8 spikes\pdf_conversion_spike\run_markitdown_batch.py --lang zh --docx
```

Convert every sample PDF:

```powershell
python -X utf8 spikes\pdf_conversion_spike\run_markitdown_batch.py --docx
```

Restore one sample PDF directly to DOCX with `pdf2docx`:

```powershell
spikes\pdf_conversion_spike\.venv\Scripts\python.exe -X utf8 spikes\pdf_conversion_spike\run_pdf2docx_restore.py --sample AIA_2021_Annual_Report_zh
```

Export a restored DOCX back to PDF with local Word:

```powershell
powershell -ExecutionPolicy Bypass -File spikes\pdf_conversion_spike\export_docx_to_pdf.ps1 -InputDocx spikes\pdf_conversion_spike\output\pdf2docx\zh\AIA_2021_Annual_Report_zh\AIA_2021_Annual_Report_zh_via_pdf2docx.docx
```

## Notes

- `raw.md` is the untouched `MarkItDown` output.
- `cleaned.md` only normalizes line endings and page breaks.
- The generated DOCX is for inspection only. It is expected to lose layout on
  visually complex pages such as covers, multi-column spreads, charts, and
  heavily designed sections.
- In current testing, `Word` is reliable for `DOCX -> PDF`, but not reliable as
  a headless `PDF -> DOCX` batch engine on these large sample PDFs.
