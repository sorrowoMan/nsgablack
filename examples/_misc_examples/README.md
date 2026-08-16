# _misc_examples

These files are compatibility and teaching material. They are useful for
reading small mechanisms in isolation, but they are not the current formal
example surface.

## Migrated To Formal Projects

The old demo scripts below have been migrated to
`examples/cases/<project>/run_project.py`, with runnable units under
`examples/cases/<project>/cases/<case>/`:

| Old file | Formal Project |
| --- | --- |
| `nsga2_solver_demo.py` | `examples/cases/nsga2_basic/` |
| `bias_gallery_demo.py` | `examples/cases/bias_gallery/` |
| `surrogate_assisted_ea_demo.py` | `examples/cases/surrogate_ea/` |
| `trust_region_dfo_demo.py` | `examples/cases/trust_region_dfo/` |
| `multi_strategy_coop_demo.py` | `examples/cases/multi_strategy/` |
| `mas_demo.py` | `examples/cases/mas_search/` |
| `single_trajectory_adaptive_demo.py` | `examples/cases/single_trajectory/` |
| `dynamic_multi_strategy_demo.py` | `examples/cases/dynamic_strategy/` |
| `dynamic_repair_demo.py` | `examples/cases/dynamic_repair/` |
| `robust_dfo_demo.py` | `examples/cases/robust_dfo/` |
| `trust_region_mo_dfo_demo.py` | `examples/cases/trust_region_mo/` |
| `trust_region_nonsmooth_demo.py` | `examples/cases/trust_region_nonsmooth/` |
| `trust_region_subspace_demo.py` | `examples/cases/trust_region_subspace/` |
| `trust_region_subspace_frontier_demo.py` | `examples/cases/tr_subspace_frontier/` |
| `risk_bias_demo.py` | `examples/cases/risk_bias/` |
| `parallel_repair_demo.py` | `examples/cases/parallel_repair/` |
| `structure_prior_mo_demo.py` | `examples/cases/structure_prior/` |
| `surrogate_model_lab_demo.py` | `examples/cases/surrogate_lab/` |
| `async_event_driven_demo.py` | `examples/cases/async_event/` |

## Teaching-Only Scripts

These files define small custom adapters/plugins or infrastructure probes. Keep
them thin, and do not add new architecture through them:

`astar_demo.py`, `blank_solver_plugin_demo.py`, `blank_vs_composable_demo.py`,
`composable_solver_fusion_demo.py`, `decision_trace_demo.py`,
`gpu_ray_mysql_stack_demo.py`, `inner_three_layer_multi_strategy_ui_demo.py`,
`moa_star_demo.py`, `monte_carlo_dp_robust_demo.py`, `multi_fidelity_demo.py`,
`nested_three_layer_demo.py`, `ngspice_inner_demo.py`, `role_adapters_demo.py`,
`symbolic_joint_bundle_beam_demo.py`.

## Rule For New Work

New runnable examples should start in `examples/cases/<project>/` and use
Project / Case / Scaffold / L0. A single-file script may remain only as a
thin compatibility wrapper or a teaching note.
