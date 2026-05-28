# _misc_examples — 状态说明

这些是轻量演示文件，分为三类：

## 已迁移到标准脚手架 (19)

| 原始文件 | 迁移目标 |
|---|---|
| `nsga2_solver_demo.py` | `cases/nsga2_basic/` |
| `bias_gallery_demo.py` | `cases/bias_gallery/` |
| `surrogate_assisted_ea_demo.py` | `cases/surrogate_ea/` |
| `trust_region_dfo_demo.py` | `cases/trust_region_dfo/` |
| `multi_strategy_coop_demo.py` | `cases/multi_strategy/` |
| `mas_demo.py` | `cases/mas_search/` |
| `single_trajectory_adaptive_demo.py` | `cases/single_trajectory/` |
| `dynamic_multi_strategy_demo.py` | `cases/dynamic_strategy/` |
| `dynamic_repair_demo.py` | `cases/dynamic_repair/` |
| `robust_dfo_demo.py` | `cases/robust_dfo/` |
| `trust_region_mo_dfo_demo.py` | `cases/trust_region_mo/` |
| `trust_region_nonsmooth_demo.py` | `cases/trust_region_nonsmooth/` |
| `trust_region_subspace_demo.py` | `cases/trust_region_subspace/` |
| `trust_region_subspace_frontier_demo.py` | `cases/tr_subspace_frontier/` |
| `risk_bias_demo.py` | `cases/risk_bias/` |
| `parallel_repair_demo.py` | `cases/parallel_repair/` |
| `structure_prior_mo_demo.py` | `cases/structure_prior/` |
| `surrogate_model_lab_demo.py` | `cases/surrogate_lab/` |
| `async_event_driven_demo.py` | `cases/async_event/` |

## 保留扁平 — 教程代码 (14)

这些文件定义自定义 Adapter/Plugin 类，是教学代码，不适合标准脚手架：

`astar_demo.py`, `blank_solver_plugin_demo.py`, `blank_vs_composable_demo.py`,
`composable_solver_fusion_demo.py`, `decision_trace_demo.py`, `gpu_ray_mysql_stack_demo.py`,
`inner_three_layer_multi_strategy_ui_demo.py`, `moa_star_demo.py`, `monte_carlo_dp_robust_demo.py`,
`multi_fidelity_demo.py`, `nested_three_layer_demo.py`, `ngspice_inner_demo.py`,
`role_adapters_demo.py`, `symbolic_joint_bundle_beam_demo.py`

## 保留扁平 — 基础设施展示 (9)

这些演示框架能力（日志、指标、上下文等），不是优化案例：

`benchmark_harness_demo.py`, `context_keys_demo.py`, `context_schema_demo.py`,
`logging_demo.py`, `metrics_demo.py`, `otel_tracing_demo.py`, `parallel_evaluator_demo.py`,
`ray_parallel_demo.py`, `sequence_graph_demo.py`

## 保留扁平 — 需自定义 Problem

`active_learning_surrogate_demo.py`, `dynamic_penalty_projection_demo.py`, `solver_manager_minimal_demo.py`, `end_to_end_workflow_demo.py`, `dynamic_cli_signal_demo.py`, `copt_qp_template_demo.py`, `surrogate_plugin_demo.py`, `plugin_gallery_demo.py`
