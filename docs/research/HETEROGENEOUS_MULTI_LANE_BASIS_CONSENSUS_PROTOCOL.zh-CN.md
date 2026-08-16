`HeterogeneousMultiLaneBasisConsensusProtocol` 的正式协议稿。

---

## 1. 目标

这套协议把原来“同质的 unlocked batch”升级成“异构多 lane 挑战体系”。

每条 lane 使用同一份 benchmark 数据，但在以下方面施加不同偏置：

1. screening
2. challenger objective
3. pool expansion bias
4. locked 阶段 refinement 风格

最后只对跨 lane 依然稳定的 basis 做锁核。

---

## 2. 核心思想

系统不应该只信任一条搜索线。

更合理的做法是：

1. 并行跑多条 symbolic lane
2. 让不同 lane 强调不同的机制先验
3. 同时统计“跨 run 支持度”和“跨 lane 稳定度”
4. 基于联合共识锁定 core basis
5. 再在 locked-core 条件下做 refinement

这不是 trainer 内部的一点小技巧，而是系统级协议。

---

## 3. Lane Spec

每条 lane 由一个 `lane_spec` 描述。

当前正式字段：

- `lane_id`
- `lane_family`
- `repeat_count`
- `locked_repeat_count`
- `screening_protocol`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `trainer_params_overrides`

建议补充的说明字段：

- `lane_label`
- `description`
- `lane_weight`

---

## 4. Cycle 流程

单个共识周期仍然保持三段：

1. `unlocked_batch`
2. `consensus`
3. `locked_core_refinement`

多 lane 协议下的含义是：

1. `unlocked_batch` 按 lane 分线运行
2. `consensus` 用所有 unlocked runs 一起构建联合 core table
3. `locked_core_refinement` 再按 lane 用同一份 locked seed genome 做 refinement

---

## 5. Joint Core Score

旧的同质场景只看：

- `support_rate`
- `exact_stability`
- `support_weight_rate`

多 lane 协议新增：

- `cross_lane_stability`

当前策略：

1. 没有 lane 结构时，保持旧公式不变
2. 存在多 lane 时，把 `cross_lane_stability` 纳入 `joint_core_score`

这样既保留旧协议兼容性，又让多 lane 真正影响锁核压力。

---

## 6. Cross-Lane Stability

`cross_lane_stability` 用来衡量一个 basis class 是否能跨不同 lane 生存下来。

当前派生字段：

- `cross_lane_support_count`
- `cross_lane_support_rate`
- `cross_lane_family_count`
- `cross_lane_family_support_rate`
- `cross_lane_stability`

解释方式：

1. 如果跨 run 很稳定，但跨 lane 不稳定，说明它可能只是某条线特有偏好
2. 如果跨 lane 也稳定，说明它更像真正的核心 basis

---

## 7. Artifact Schema 投影

symbolic artifact schema 现在正式新增：

- `heterogeneous_lane_consensus`

其中重点字段包括：

- `lane_id`
- `lane_family`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `joint_core_score`
- `cross_lane_stability`
- `consensus_prior_row_count`
- `lane_spec`

这意味着多 lane 共识不再只是运行时细节，而是正式 artifact 合同的一部分。

---

## 8. Experiment Surface 投影

runtime run surface 现在会派生并暴露：

- `lane_id`
- `lane_family`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `joint_core_score`
- `cross_lane_stability`

experiment dashboard 也可以直接：

1. 按这些字段筛选
2. 在详情卡中查看 lane 协议摘要

---

## 9. 第一批正式场景

第一版正式 multi-lane 场景先落在：

1. `arrhenius_gate_like`
2. `redundant_proxy_control`

原因：

1. `arrhenius_gate_like` 重点考机制性交叉特征和 gate 项能不能保住
2. `redundant_proxy_control` 重点考 proxy 抑制和语义去重能不能保住真值项

---

## 10. 当前状态

这一版的正式落地范围是：

1. lane-aware 共识打分
2. lane-aware artifact metadata
3. lane-aware runtime surface 投影
4. lane-aware 的 `nsgablack` cycle 编排
5. 在两个目标 benchmark 上跑第一版真实实验

这是第一版正式协议，不是最终机制终稿。
