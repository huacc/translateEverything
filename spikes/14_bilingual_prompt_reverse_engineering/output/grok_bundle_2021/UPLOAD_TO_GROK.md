# Upload To Grok

建议优先上传这 3 个文件：

- `AIA_2021_Annual_Report_zh_extracted_full.txt`
- `AIA_2021_Annual_Report_en_extracted_full.txt`
- `current_prompt_examples.md`

如果 Grok 支持更多附件，再补这 2 个：

- `AIA_2021_Annual_Report_zh_pages.json`
- `AIA_2021_Annual_Report_en_pages.json`

建议直接问 Grok：

1. 你会收到 AIA 2021 年报的中文原版全文抽取、人工英文版全文抽取、以及当前系统 prompt 样例。
2. 目标不是直接翻译文档，而是反向分析：怎样设计 prompt，才能让中文到英文翻译更接近人工英文版的表达、术语和文风。
3. 请重点回答：
   - 当前 prompt 中哪些字段应删除，为什么。
   - 哪些字段必须保留，为什么。
   - 哪些约束应由工程层处理，而不是放进 prompt。
   - 请分别给出标签、正文、表格三类 lane 的最小有效 prompt 模板。
   - 模板输入主体请使用 Markdown 风格文本，不要把内部 JSON 结构直接塞给模型。

本目录位置：

- `D:\项目\开源项目\ontology-scenario\spikes\14_bilingual_prompt_reverse_engineering\output\grok_bundle_2021`
