$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

python "$Root\scripts\translate_with_controls.py" `
  --input "$Root\inputs\AIA_2021_Annual_Report_zh.pdf" `
  --blocks-jsonl "$Root\inputs\blocks.jsonl" `
  --output-dir "$Root\outputs\first20_rerun" `
  --pages "1-20" `
  --company-memory "$Root\memory\company_memory.json" `
  --domain-spec "$Root\configs\domain_spec.json" `
  --task-spec "$Root\configs\task_spec.json" `
  --validation-spec "$Root\configs\validation_spec.json" `
  --glossary "$Root\configs\glossary_zh_en_seed.json" `
  --patterns "$Root\configs\patterns_zh_en.json"
