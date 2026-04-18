# Spike 13 总结报告

## 本轮确认有效的点
- 已把 lane separation 提升为独立设计约束，而不是仅靠后验观察。
- 正文、表格、短标签和侧边栏已在工程侧区分处理。
- `prompt_audit.json`、`lane_records.json`、`render_fragments.json`、`fragment_anchor_maps.json` 已作为证据文件补入输出。

## 本轮结果
- 相对基线，token_f1 +0.0742，content_f1 +0.1314，sequence_ratio +0.1121，number_recall +0.0699。
- 内容页提升页：19, 20。
- 内容页退化页：13。
- 第 19 页尾句并组：已保持。

## 反思
- 只看平均指标仍然不够，必须回到页级和 lane 级看退化点。
- 正文 prompt 如果已经去块化，而结果仍不稳，下一步应优先复盘 context 和 render，而不是再把工程职责塞回 prompt。
- 表格 lane 如果仍退化，说明单块原位回填只是过渡方案，后续需要继续走 cell/row 级 TableIR。

## 后续动作
- 先检查 `prompt_audit.json` 中正文 lane 是否还有原始块暴露。
- 重点复盘页 20 的 `table lane` 输出和版面结果。
- 在确认前 20 页没有新增硬错误后，再决定是否扩页。

## 阶段状态
- 阶段 0 冻结基线：通过
- 阶段 0.5 冻结学习资产与执行输入：通过
- 阶段 1 建立 Anchor IR：通过
- 阶段 2 组装 SemanticGroup：通过
- 阶段 3 Fact Lock 与 Mapping Hit：通过
- 阶段 4 按组翻译：通过
- 阶段 5 生成 RenderPlan 并回填：通过
- 阶段 6 页级质量验收：通过
