# Supply Adjustment Nested Scenario Matrix

This case models a nested operations problem, not a flat ML demo. The outer solver changes the supply arrival calendar; each candidate can be evaluated by an inner production scheduler.

## Layers

| Layer | Meaning | Decision |
| --- | --- | --- |
| L0 | Design/search-control layer | Which materials are allowed into the adjustable set through blacklist design |
| L1 | Supply adjustment layer | How many days each non-zero supply event moves earlier |
| L2 | Production scheduling layer | Feasible production schedule under the adjusted supply table |

## Problem Boundary

- Day 0 supply is fixed.
- Events can move earlier only; delays are forbidden.
- Events move as whole units; splitting is forbidden.
- Supply conservation is audited per material.
- Optional hard cap controls number of moved events.
- Inner production evaluation uses the production scheduling scaffold, not a detached toy score.

## Serious Comparison Matrix

| Scenario | Purpose | Entry | Preset |
| --- | --- | --- | --- |
| L1/L2 nested supply shift | Direct supply timing optimization evaluated by inner production solver | `python solver/run_case.py` | `config/l1_supply_shift_l2_production_realistic.json` |
| L0/L1/L2 blacklist design | Search the adjustable material domain before final nested supply optimization | `python solver/run_blacklist_case.py` | `config/l0_blacklist_l1_l2_design_realistic.json` |
| No movement cap | Stress test unconstrained supply pull-forward | `python solver/run_case.py --max-moved-events 0` | ad hoc |
| Tight movement cap | Test operationally conservative plans | `python solver/run_case.py --max-moved-events 50` | ad hoc |
| Final L1 rerun after L0 | Validate that the selected material domain survives a larger final budget | built into blacklist entry | compare exported final supply/moves |

## Metrics To Compare

- `objectives[0]`: negative production output from nested evaluation.
- `move_summary.moved_events`: operational intervention count.
- `move_summary.moved_days_total`: total timing disruption.
- `move_summary.moved_quantity_days`: quantity-weighted timing disruption.
- `supply_conservation.material_total_max_abs_delta`: should remain zero or near-zero.
- `supply_conservation.day0_delta`: should remain zero.
- `timing_profile.daily_supply_delta`: whether the plan creates unrealistic front-loading.
- L0 `quality_gap`: quality loss caused by blacklist simplification.
- L0 `runtime`: nested runtime pressure.

## Recommended Workflow

1. Generate or choose a production baseline with `production_scheduling`.
2. Run L1/L2 nested supply shift with a moderate movement cap.
3. Inspect adjusted supply, move log and `adjusted_supply_audit_*.json`.
4. Run L0/L1/L2 blacklist design when the adjustable event space is too large.
5. Use the final L1 export from the L0 run as the operational candidate, not only the L0 best mask.

## Why This Is A Real Case

The case composes multiple formal surfaces:

- `problem/`: supply event shift semantics and blacklist design problem.
- `pipeline/`: binary representation for L0 material-domain search.
- `solver/assembly.py`: L1/L2 nested supply optimization.
- `solver/blacklist_assembly.py`: L0/L1/L2 design optimization.
- `plugins/`: export and budget controls.
- `reporting/`: supply conservation and movement audit.

The important distinction is that the nested case optimizes a decision process. It is not just a table transformation: it searches intervention policies, calls inner production scheduling, audits feasibility and exports operational artifacts.
