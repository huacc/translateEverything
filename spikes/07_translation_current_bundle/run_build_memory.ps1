$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

python "$Root\scripts\build_company_memory.py" `
  --zh-dir "$Root\inputs\memory_source\zh" `
  --en-dir "$Root\inputs\memory_source\en" `
  --output-dir "$Root\memory\rebuilt_from_bundle" `
  --exclude-year 2021 `
  --company-name "AIA Group" `
  --max-pages 80
