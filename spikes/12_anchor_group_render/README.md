# Spike 12: Anchor Group Render

## 目标

本目录用于承载 Spike 12 的实验设计、后续实现与实验产物，主题是：

- 保留原始 PDF `block` 作为锚点
- 在锚点之上构建 `semantic group`
- 先按组翻译，再按组内锚点回填
- 验证语义完整性与版面稳定性是否能同时提升

## 与总体设计的对齐

Spike 12 不是独立路线，而是对 `docs/DESIGN.md` 中以下方向的局部技术穿刺：

- `Document IR` 需要继续细化到可承载 PDF 锚点、分组与回填计划
- 翻译主链路需要把“翻译单元”和“渲染单元”解耦
- 长任务需要可恢复、可追踪的中间产物，而不是只保留最终页面输出
- 质量校验需要同时覆盖内容正确性与版面稳定性
- 一期仍遵循“单编排器 + 可恢复后台任务 + 确定性子流水线”，Spike 12 只是其中 PDF 子链路的实验增强

直接对应总体设计中的模块边界：

- `Prompt Bundle Store`：持久化 group 级上下文与版本引用
- `Segment Translator`：把当前 block 翻译提升为 group 翻译
- `Quality Checks`：同时验收内容指标与版面指标
- `Document Renderer`：把组译文按 anchor slots 回填，而不是把整段暴力写回单块

## 本轮实验边界

本轮仍然是 spike，不是主线重构。重点是验证：

1. `group translation` 是否优于 `block translation`
2. `anchor-based render` 是否能保住当前回填能力
3. 第 19 页这类尾句金额块问题，是否能从结构层系统性缓解

本轮不直接承诺：

- 进入 DOCX 主链路
- 覆盖全部页型
- 解决所有表格与复杂对象问题
- 形成最终可交付产品方案
- 改变顶层的单编排器架构

## 与问题根因的对齐

Spike 12 不是为了推翻前面的正确结论，而是要在保留已有有效能力的前提下，对齐 `docs/问题反馈/问题3.md` 中的根因：

- **直接要打的工程问题**：翻译单元过碎、残句/尾句挂接错误、中间对象不可追溯
- **要补强的上下文问题**：上一段/下一段只读上下文、全文背景抽取维度、mapping 命中层
- **暂不单独解决的问题**：财务事实锁定、特殊块渲染、所有 shrink 问题——这些需要在 Spike 12 中预留接口，但不能假设“组更大”后自动消失

因此 Spike 12 的定位是：

> 保留 Spike 08/10/11 已验证正确能力，用 `AnchorBlock + SemanticGroup + RenderPlan + Cache/Context/Mapping` 把 PDF 子链路做成更稳的工程底座。

## 与前序 spike 的关系

- Spike 08 提供了第一版 `semantic group` 与 slot 回填基础
- Spike 10 引入文档背景注入
- Spike 11 在背景注入前增加了清洗与闭集控制
- Spike 12 要验证：在保留这些已有能力的前提下，是否应该把 `AnchorBlock + SemanticGroup + RenderPlan` 作为下一阶段 PDF 高保真子链路的核心 IR

## 建议目录

后续建议在本目录下逐步补齐：

- `README.md`
- `SPIKE12_ANCHOR_GROUP_RENDER_DESIGN.md`
- `scripts/`
- `output/`
- `eval/`

其中：

- `scripts/` 放实验脚本
- `output/` 放中间 JSON、渲染结果、评估结果
- `eval/` 放样本页、人工结论、对照记录

## 建议中间产物

为了和总体设计中的 checkpoint、Prompt Bundle、质量追溯机制保持一致，Spike 12 应优先沉淀这些中间对象：

- `anchor_blocks.json`
- `semantic_groups.json`
- `group_context_records.json`
- `render_plans.json`
- `selected_context_packs.json`
- `translations.json`
- `report.json`

这几类产物分别对应：

- 结构化 IR
- 分组决策
- group 级上下文快照
- 回填决策
- 翻译结果
- 页级验收

## 阶段门建议

建议继续沿用设计稿中的阶段门，而不是一口气改完整链路：

1. 冻结基线
2. 建立 Anchor IR
3. 组装 Semantic Group
4. 按组翻译
5. 生成 Render Plan 并回填
6. 做页级质量验收

若任一阶段未达标，应先停下复盘，不继续扩页。

## 当前状态

- 当前已完成实验目录与设计文档落位
- 设计文档已与顶层 `docs/DESIGN.md` 的模块边界和主链路约束对齐
- 尚未开始实现
