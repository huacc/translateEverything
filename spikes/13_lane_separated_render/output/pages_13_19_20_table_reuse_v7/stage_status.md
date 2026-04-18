# Spike 13 阶段状态

## 阶段 0 冻结基线
- 状态：通过
- 结论：基线页、人工参考、v11 对照和问题反馈已冻结。
- 详情：`{"focus_pages": [13, 19, 20]}`

## 阶段 0.5 冻结学习资产与执行输入
- 状态：通过
- 结论：资产快照与执行配置快照已落盘。
- 详情：`{"model": "claude-3-5-sonnet-20241022", "compact_threshold": 0.84, "render_dpi": 110}`

## 阶段 1 建立 Anchor IR
- 状态：通过
- 结论：AnchorBlock 数量与原始块数量一致，且均可追溯。
- 详情：`{"anchor_count": 92, "source_block_count": 92}`

## 阶段 2 组装 SemanticGroup
- 状态：通过
- 结论：第 19 页尾句并组已打通，侧边栏未混入正文组。
- 详情：`{"tail_group_merged": true, "sidebar_intrusion_count": 0}`

## 阶段 3 Fact Lock 与 Mapping Hit
- 状态：通过
- 结论：关键股息与金额事实已锁定。
- 详情：`{"final_dividend": ["100.30"], "total_dividend": ["135.30"], "dividend_paid_usd": ["US$1.997 billion", "US$1997 million", "US$1,997 million"]}`

## 阶段 4 按组翻译
- 状态：通过
- 结论：关键金额、股息和尾句残缺问题已在组翻译阶段受控。
- 详情：`{"bad_scale_count": 0, "broken_fragment_count": 0, "dividend_mixup_count": 0}`

## 阶段 5 生成 RenderPlan 并回填
- 状态：通过
- 结论：RenderPlan 已生成，未出现侧边栏回填，且版面指标未明显差于 v11。
- 详情：`{"overflow_count": 0, "sidebar_render_count": 0, "layout_not_worse": true}`

## 阶段 6 页级质量验收
- 状态：通过
- 结论：相对 v11 的内容指标已对比完成，硬错误与侧边栏污染已复核。
- 详情：`{"delta_spike12_minus_v11": {"token_f1": 0.0149, "content_f1": 0.0651, "sequence_ratio": 0.0324, "number_recall": 0.0176}, "hard_error_count": 0, "sidebar_intrusion_count": 0}`
