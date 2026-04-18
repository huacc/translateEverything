# Spike 13 验收报告

- 总体结论：通过
- 输出目录：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_smoke_v6`
- 阶段门通过数：8/8

## 机制核验
- 正文 prompt 审计：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_smoke_v6\prompt_audit.json`
- lane 路由证据：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_smoke_v6\lane_records.json`
- 组级上下文：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_smoke_v6\group_context_records.json`
- 回填片段：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_smoke_v6\render_fragments.json`
- fragment 到 anchor 映射：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_smoke_v6\fragment_anchor_maps.json`

## 平均指标
- token_f1：0.6979（相对基线 +0.0167）
- content_f1：0.6722（相对基线 +0.0660）
- sequence_ratio：0.5282（相对基线 +0.0366）
- number_recall：0.6583（相对基线 +0.0176）

## 页级观察
- 页 13：退化；token_f1 -0.0684，content_f1 -0.0611，sequence_ratio -0.0203，number_recall +0.0000
- 页 19：提升；token_f1 +0.0121，content_f1 +0.0423，sequence_ratio +0.0230，number_recall +0.0364
- 页 20：提升；token_f1 +0.1066，content_f1 +0.2168，sequence_ratio +0.1072，number_recall +0.0164

## 关键问题核验
- p19 尾句并组：是
- `US$19.97 billion` 硬错误：0
- `regarding dividend payments` 残句：0
- 末期股息/全年股息串位：0
- 侧边栏进入主链路：0

## 结论说明
- 若正文 prompt 审计仍显示模型看到原始 blocks 文本数组，则本轮不应视为机制达标。
- 若页 20 表格区指标或版面退化，应优先复盘 table lane，而不是继续调正文提示词。
