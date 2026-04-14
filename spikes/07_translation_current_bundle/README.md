# 07 Translation Current Bundle

这个目录是当前可直接查看和复用的单一实验目录。

不要再看 `spikes/05_annual_report_translation_control` 和 `spikes/06_company_memory_learning` 作为主入口。
那两个目录现在只是历史来源目录。

当前应看
- 最终前 20 页译文 PDF: [outputs/first20_current/translated_en.pdf](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/outputs/first20_current/translated_en.pdf)
- 对照去字版 PDF: [outputs/first20_current/native_redacted.pdf](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/outputs/first20_current/native_redacted.pdf)
- 当前使用的公司记忆包: [memory/company_memory.json](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/memory/company_memory.json)
- 公司记忆调试映射: [memory/mapping_debug.json](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/memory/mapping_debug.json)
- 页级结果报告: [outputs/first20_current/report.json](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/outputs/first20_current/report.json)
- 全量块级译文: [outputs/first20_current/translations.json](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/outputs/first20_current/translations.json)
- LLM 提示词导出目录: [outputs/first20_current/prompt_exports/INDEX.txt](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/outputs/first20_current/prompt_exports/INDEX.txt)

当前采用的逻辑
- 翻译主脚本: [scripts/translate_with_controls.py](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/scripts/translate_with_controls.py)
- 公司记忆构建脚本: [scripts/build_company_memory.py](/D:/项目/开源项目/ontology-scenario/spikes/07_translation_current_bundle/scripts/build_company_memory.py)
- 运行版本:
  `company_memory = AIA_excl_2021_v4`
  `translation_output = AIA_2021_Annual_Report_zh_first20_v7_company_memory_batched`

目录说明
- `configs/`
  当前翻译实验使用的配置文件。
- `inputs/`
  当前实验直接输入。
  `AIA_2021_Annual_Report_zh.pdf` 是翻译输入。
  `AIA_2021_Annual_Report_en_reference.pdf` 是人工英文参考。
  `blocks.jsonl` 是 2021 中文 PDF 的块提取结果。
- `inputs/memory_source/`
  构建公司记忆包使用的历年 AIA 中英文年报样本。
- `memory/`
  当前选定的公司记忆包和调试映射。
- `outputs/first20_current/`
  当前选定的前 20 页输出。
  `api_logs/` 里保存了提示词输入和模型输出。
  `prompt_exports/` 里把每次 LLM 交互拆成了可直接阅读的 `system`、`user`、`response` 文本。
  `comparison/` 里是原图 / 去字图 / 回填图三联对照。

如何重跑
- 先设置环境变量:
  `ANTHROPIC_BASE_URL`
  `ANTHROPIC_AUTH_TOKEN`
- 重建公司记忆包:
  `powershell -ExecutionPolicy Bypass -File .\\run_build_memory.ps1`
- 重新翻译前 20 页:
  `powershell -ExecutionPolicy Bypass -File .\\run_translate_first20.ps1`

当前结论
- 现在统一看这个目录即可。
- 如果你问“最后用哪个”，答案就是:
  `memory/company_memory.json`
  `outputs/first20_current/translated_en.pdf`
