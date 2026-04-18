# Spike 14: Bilingual Prompt Reverse Engineering

目标：

- 从人工英文 PDF 与中文原版 PDF 中提取文本。
- 以当前前 20 页翻译实验为边界，整理双语材料与现有提示词样例。
- 将 PDF 材料与抽取文本一起提交给 Claude，反向分析“人工译文风格”对应的提示词设计。
- 输出第 14 轮提示词优化建议，重点判断哪些提示词内容应删除、保留、下沉到工程层。

核心脚本：

- `scripts/run_spike14_bilingual_prompt_reverse.py`

主要输出：

- `output/<run_name>/extracted/zh_pages.json`
- `output/<run_name>/extracted/en_pages.json`
- `output/<run_name>/extracted/zh_full.txt`
- `output/<run_name>/extracted/en_full.txt`
- `output/<run_name>/consultation/zh_first20.pdf`
- `output/<run_name>/consultation/en_first20.pdf`
- `output/<run_name>/consultation/current_prompt_examples.md`
- `output/<run_name>/consultation/bilingual_consultation_material.md`
- `output/<run_name>/consultation/api_logs/*.json`
- `output/<run_name>/consultation/claude_prompt_advice.md`

说明：

- 默认提取整本中英 PDF 文本。
- 默认向 Claude 提交前 20 页 PDF 子集，以对齐当前翻译基线与成本边界。
- 如果网关不支持 PDF 文档输入，脚本会退化为文本材料咨询，并保留失败日志。
