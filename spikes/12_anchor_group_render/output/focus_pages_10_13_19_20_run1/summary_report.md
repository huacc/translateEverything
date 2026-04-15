# Spike 12 总结报告

## 已打通的关键链路
- 基线冻结、资产快照、执行配置快照已落盘。
- AnchorBlock / SemanticGroup / GroupContext / FactLock / RenderPlan 全链路已落盘。
- 侧边栏对象已从主翻译与主回填链路排除。
- 页级评估、阶段门验收、提示词与 API 日志已同步输出。

## 本轮结果
- 相对 v11，token_f1 +0.0008，content_f1 -0.0022，sequence_ratio +0.0083，number_recall +0.0090。
- Spike 12 对人工参考的平均指标：token_f1 0.7011，content_f1 0.6653，sequence_ratio 0.5154，number_recall 0.6407。
- 第 19 页尾句并组：已解决。
- 股息与金额硬错误：scale=0，dividend_mixup=0。

## 残余风险
- 本轮仍基于 PDF 锚点回填，复杂版面与长段落 shrink 风险没有根除。
- 事实锁定当前主要覆盖高风险金额、股息和关键比率，尚未扩展到全部财务口径。
- 侧边栏本轮明确降级，不作为翻译目标。

## 阶段状态
- 阶段 0 冻结基线：通过
- 阶段 0.5 冻结学习资产与执行输入：通过
- 阶段 1 建立 Anchor IR：通过
- 阶段 2 组装 SemanticGroup：通过
- 阶段 3 Fact Lock 与 Mapping Hit：通过
- 阶段 4 按组翻译：通过
- 阶段 5 生成 RenderPlan 并回填：通过
- 阶段 6 页级质量验收：通过
