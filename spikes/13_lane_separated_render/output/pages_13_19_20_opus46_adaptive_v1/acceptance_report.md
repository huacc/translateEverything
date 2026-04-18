# Spike 13 验收报告

- 总体结论：通过
- 输出目录：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_opus46_adaptive_v1`
- 阶段门通过数：8/8

## 机制核验
- 正文 prompt 审计：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_opus46_adaptive_v1\prompt_audit.json`
- lane 路由证据：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_opus46_adaptive_v1\lane_records.json`
- 组级上下文：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_opus46_adaptive_v1\group_context_records.json`
- 回填片段：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_opus46_adaptive_v1\render_fragments.json`
- fragment 到 anchor 映射：`D:\项目\开源项目\ontology-scenario\spikes\13_lane_separated_render\output\pages_13_19_20_opus46_adaptive_v1\fragment_anchor_maps.json`

## 平均指标
- token_f1：0.7554（相对基线 +0.0742）
- content_f1：0.7376（相对基线 +0.1314）
- sequence_ratio：0.6037（相对基线 +0.1121）
- number_recall：0.7106（相对基线 +0.0699）

## 页级观察
- 页 13：退化；token_f1 -0.0225，content_f1 -0.0086，sequence_ratio +0.0227，number_recall +0.0476
- 页 19：提升；token_f1 +0.0591，content_f1 +0.0823，sequence_ratio +0.1070，number_recall +0.1455
- 页 20：提升；token_f1 +0.1860，content_f1 +0.3204，sequence_ratio +0.2065，number_recall +0.0164

## 关键问题核验
- p19 尾句并组：是
- `US$19.97 billion` 硬错误：0
- `regarding dividend payments` 残句：0
- 末期股息/全年股息串位：0
- 侧边栏进入主链路：0

## 结论说明
- 若正文 prompt 审计仍显示模型看到原始 blocks 文本数组，则本轮不应视为机制达标。
- 若页 20 表格区指标或版面退化，应优先复盘 table lane，而不是继续调正文提示词。
