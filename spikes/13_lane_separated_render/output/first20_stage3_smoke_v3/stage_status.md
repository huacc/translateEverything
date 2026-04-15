# Spike 13 阶段状态

## 阶段 0 冻结基线
- 状态：通过
- 结论：基线页、人工参考、v11 对照和问题反馈已冻结。
- 详情：`{"focus_pages": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]}`

## 阶段 0.5 冻结学习资产与执行输入
- 状态：通过
- 结论：资产快照与执行配置快照已落盘。
- 详情：`{"model": "claude-3-5-sonnet-20241022", "compact_threshold": 0.84, "render_dpi": 110}`

## 阶段 1 建立 Anchor IR
- 状态：通过
- 结论：AnchorBlock 数量与原始块数量一致，且均可追溯。
- 详情：`{"anchor_count": 552, "source_block_count": 552}`

## 阶段 2 组装 SemanticGroup
- 状态：通过
- 结论：第 19 页尾句并组已打通，侧边栏未混入正文组。
- 详情：`{"tail_group_merged": true, "sidebar_intrusion_count": 0}`

## 阶段 3 Fact Lock 与 Mapping Hit
- 状态：通过
- 结论：关键股息与金额事实已锁定。
- 详情：`{"final_dividend": ["100.30"], "total_dividend": ["135.30"], "dividend_paid_usd": ["US$1.997 billion", "US$1997 million", "US$1,997 million"]}`
