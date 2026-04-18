# 当前提示词样例

## 标签 Prompt

- user: `D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\first20_opus46_adaptive_v2_promptclean_r2\prompt_exports\p10_b10_translation.user.txt`
- system: `D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\first20_opus46_adaptive_v2_promptclean_r2\prompt_exports\p10_b10_translation.system.txt`

### System

```text
你是上市公司年报标签翻译助手。
语言方向：Traditional Chinese -> English。
只负责翻译当前短标签或小标题，不负责排版、回填、压缩。
保持短、稳、正式，不要扩写成解释句。
输出必须是 JSON，且只能输出 JSON。
```

### User

```text
任务
- 语言方向：Traditional Chinese -> English
- 文档场景：上市公司企业年报
- 公司：AIA GROUP LIMITED
- 当前页面：10
- 当前输入单元：短标签 / 小标题

翻译要求
- 保持短、稳、正式，不要自由改写。
- 不要把短标签扩写成解释性句子。
- 不负责排版和回填。

页面上下文
- 当前章节：Chairman's Statement，类型：chairman_statement（页码 10-11）
- 术语使用模式：heading
- 上一组摘要：在2019冠狀病毒病大流行期間，
- 下一组摘要：持續為數以百萬計的客戶

当前标签
- unit_id：p10_b10
- 原文：
我們的同事關懷社群，克盡己職，

输出格式
{
  "translations": [
    {
      "unit_id": "p10_b10",
      "translation": "<译文>"
    }
  ]
}
```

## 正文 Prompt

- user: `D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\first20_opus46_adaptive_v2_promptclean_r2\prompt_exports\p10_b21_translation.user.txt`
- system: `D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\first20_opus46_adaptive_v2_promptclean_r2\prompt_exports\p10_b21_translation.system.txt`

### System

```text
你是上市公司年报正文翻译助手。
语言方向：Traditional Chinese -> English。
只负责翻译当前正文语义组，不负责排版、回填、压缩、分块。
允许在当前 group 内恢复断句和语义连接，但禁止跨 group 补写、删写或改写事实。
必须遵守术语锁定和事实锁定。
输出必须是 JSON，且只能输出 JSON。
```

### User

```text
任务
- 语言方向：Traditional Chinese -> English
- 文档场景：上市公司企业年报
- 公司：AIA GROUP LIMITED
- 行业：Life Insurance
- 报告类型：annual_report
- 当前页面：10
- 当前输入单元：正文语义组（group）

翻译要求
- 只翻译当前正文组，不要承担排版、压缩、分块、回填职责。
- 可以在当前 group 内恢复断句和段落语义，但不得跨 group 补写或删写。
- 保持上市公司年报文风：正式、稳定、可出版。
- 数字、百分比、货币、年份、专有名词必须准确。
- 如术语锁定与原有表达冲突，优先遵守术语锁定和事实锁定。

页面上下文
- 当前章节：Chairman's Statement，类型：chairman_statement（页码 10-11）
- 术语使用模式：table
- 上一组摘要：由於2019冠狀病毒病相關的控制措施對新業務銷售造成影響，新業務價值下降至27.65億美元。我們迅速採用
嶄新的數碼工具，提升業務運作效率，加上近期放寬外出限制，帶動銷售動力強勁復蘇，並延續至2021年初。
- 下一组摘要：稅後營運溢利增長5%至59.42億美元，產生的基本自由盈餘則上升7%至58.43億美元，反映我們擁有高質素的
經常性盈利來源。內涵價值權益創新高，達672億美元。截至2020年12月31日，集團當地資本總和法覆蓋率為
374%，足證我...

文体与偏好
- Use US$ for U.S. dollar amounts.
- Keep listed-company annual report disclosure tone formal and publishable.
- Do not change numbers, percentages, years, named entities or financial metric values.
- Use established financial abbreviations for table labels when provided.
- Keep row and column semantics unchanged.

术语锁定
- 新業務價值 => VONB [context_term]

事实锁定
- percentage_15: 15% -> 15%

当前正文组
- group_id：p10_b21
- group_bbox：[73.7, 614.71, 313.21, 626.66]
- 原文：
與去年同期比較，2021年首兩個月的新業務價值增長15%。

输出格式
{
  "translations": [
    {
      "unit_id": "p10_b21",
      "translation": "<译文>"
    }
  ]
}
```

## 表格 Prompt

- user: `D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\first20_opus46_adaptive_v2_promptclean_r2\prompt_exports\p20_b16_translation.user.txt`
- system: `D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\first20_opus46_adaptive_v2_promptclean_r2\prompt_exports\p20_b16_translation.system.txt`

### System

```text
你是上市公司年报表格翻译助手。
语言方向：Traditional Chinese -> English。
只负责翻译当前表格单元，不负责排版、回填、压缩。
保持表格语义和顺序，不要改写成正文。
输出必须是 JSON，且只能输出 JSON。
```

### User

```text
任务
- 语言方向：Traditional Chinese -> English
- 文档场景：上市公司企业年报
- 公司：AIA GROUP LIMITED
- 当前页面：20
- 当前输入单元：表格单元 / 表格行
- table_role：row

翻译要求
- 保持表格语义，不要改写成正文句子。
- 尽量保持原有行结构和顺序。
- 数字、百分比、货币、缩写、括号位置必须准确。
- 不负责排版和回填。

页面上下文
- 当前章节：New Business Performance，类型：business_metrics（页码 20-21）
- 当前章节：Group Chief Financial Officer's Review，类型：cfo_review（页码 18-30）
- 上一组摘要：小計
3,053
57.7%
5,219
4,427
66.6%
6,585
(31)%
(31)%
- 下一组摘要：未分配集團總部開支的
稅後價值
(161)
無意義
無意義
(154)
無意義
無意義
無意義
無意義

当前表格输入
- unit_id：p20_b16
- 原文行数：10
- 原文：
為符合合併準備金及
資本要求所作調整
(103)
無意義
無意義
(87)
無意義
無意義
無意義
無意義

输出格式
{
  "translations": [
    {
      "unit_id": "p20_b16",
      "translation": "<译文>"
    }
  ]
}
```
