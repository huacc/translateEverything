# Spike 08: Semantic Group Reflow

目标：验证“跨块理解 + 工程化合并 + 按原始槽位回填”是否能比单块翻译更稳定。

边界：

- 语义分组只用于翻译理解，不改变原始 `source_block`。
- 回填仍然按原始 raw line slot 逐行写回，不允许跨组乱写。
- 提示词只保留必要约束：语言方向、年报场景、组内跨块、数字专名准确、JSON 输出。
- 术语锁定优先走确定性 `glossary/patterns`，其余再交给模型。

输出：

- `native_redacted.pdf`
- `translated_grouped.pdf`
- `semantic_groups.json`
- `translations.json`
- `report.json`
- `prompt_exports/`
- `api_logs/`

默认测试页：

- `10,13,19,20`

运行示例：

```powershell
$env:ANTHROPIC_BASE_URL="https://ccvibe.cc"
$env:ANTHROPIC_AUTH_TOKEN="..."
python .\spikes\08_semantic_group_reflow\semantic_group_reflow.py
```
