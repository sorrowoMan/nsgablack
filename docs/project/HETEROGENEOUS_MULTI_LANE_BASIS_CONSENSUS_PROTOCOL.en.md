Formal protocol draft for the multi-lane extension on top of the current `nsgablack -> mlblack` orthogonal symbolic consensus stack.

---

## 1. Goal

`HeterogeneousMultiLaneBasisConsensusProtocol` upgrades a single homogeneous unlocked batch into a heterogeneous set of challenger lanes.

Each lane runs the same benchmark data, but uses a different bias on:

1. screening
2. challenger objective
3. pool expansion bias
4. locked-stage refinement style

The protocol then locks only the basis terms that remain stable across lanes.

---

## 2. Core Idea

The system should not trust one search line.

Instead, it should:

1. run multiple symbolic lanes in parallel
2. let each lane emphasize a different mechanism prior
3. aggregate basis support across runs and across lanes
4. compute a cross-lane stability score
5. lock core basis from the joint consensus
6. refine again under locked-core conditions

This is a system-level protocol, not just a trainer heuristic.

---

## 3. Lane Spec

Each lane is described by a `lane_spec`.

Required practical fields:

- `lane_id`
- `lane_family`
- `repeat_count`
- `locked_repeat_count`
- `screening_protocol`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `trainer_params_overrides`

Recommended descriptive fields:

- `lane_label`
- `description`
- `lane_weight`

---

## 4. Cycle Flow

One consensus cycle is:

1. `unlocked_batch`
2. `consensus`
3. `locked_core_refinement`

Under this protocol:

1. `unlocked_batch` runs per lane
2. `consensus` builds joint core tables from all unlocked runs
3. `locked_core_refinement` re-runs per lane using the same locked seed genome

---

## 5. Joint Core Score

Legacy homogeneous score:

- `support_rate`
- `exact_stability`
- `support_weight_rate`

Multi-lane score adds:

- `cross_lane_stability`

Current behavior:

1. when no lane structure exists, keep the old score formula
2. when multiple lanes exist, extend `joint_core_score` with `cross_lane_stability`

This preserves backward compatibility while letting multi-lane consensus change selection pressure.

---

## 6. Cross-Lane Stability

`cross_lane_stability` summarizes whether a basis class survives across distinct lanes.

Current derived fields:

- `cross_lane_support_count`
- `cross_lane_support_rate`
- `cross_lane_family_count`
- `cross_lane_family_support_rate`
- `cross_lane_stability`

Interpretation:

1. high run support but low cross-lane stability means the term may be line-specific
2. high cross-lane stability means the term survives heterogeneous challenge pressure

---

## 7. Artifact Schema Projection

The symbolic artifact schema now carries a dedicated block:

- `heterogeneous_lane_consensus`

Important fields:

- `lane_id`
- `lane_family`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `joint_core_score`
- `cross_lane_stability`
- `consensus_prior_row_count`
- `lane_spec`

This makes lane-aware consensus part of the formal artifact contract instead of an implicit runtime detail.

---

## 8. Experiment Surface Projection

The runtime run surface now derives and exposes:

- `lane_id`
- `lane_family`
- `challenger_objective_protocol`
- `pool_expansion_bias_protocol`
- `joint_core_score`
- `cross_lane_stability`

The experiment dashboard can filter by these fields and inspect them in the detail view.

---

## 9. First Benchmarks

The first formal multi-lane scenarios are:

1. `arrhenius_gate_like`
2. `redundant_proxy_control`

Why these two:

1. `arrhenius_gate_like` stresses mechanistic cross-feature and gate recovery
2. `redundant_proxy_control` stresses proxy suppression and semantic de-duplication

---

## 10. Current Status

First implementation scope:

1. lane-aware consensus scoring
2. lane-aware artifact metadata
3. lane-aware runtime surface projection
4. lane-aware `nsgablack` cycle orchestration
5. first multi-lane benchmark runs on the two target scenarios

This is intentionally the first formal version, not the final mechanism.
