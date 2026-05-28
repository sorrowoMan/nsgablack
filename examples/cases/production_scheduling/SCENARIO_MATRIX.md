# Production Scheduling Scenario Matrix

This case is no longer treated as a toy optimizer. It is a production-planning scaffold with explicit problem semantics, representation repair, algorithm adapters, observability plugins, and business audit exports.

## Problem Boundary

- Decision object: machine-by-day production schedule.
- Hard checks: material availability, daily active machine limits, min/max production bounds.
- Solver objectives: total output, penalty/smoothness/fullness objectives depending on CLI flags.
- Business audit metrics: feasibility, material shortage, utilization, switching, daily stability, exported schedule credibility.

## Serious Comparison Matrix

| Scenario | Purpose | Entry | Preset |
| --- | --- | --- | --- |
| Greedy baseline | Fast lower-bound/reference plan | `python solver/run_case.py` | `config/baseline_greedy_single_objective.json` |
| ACO baseline | Constructive heuristic baseline | `python solver/run_case.py` | `config/baseline_aco_single_objective.json` |
| MOEA/D + VNS | Main multi-agent Pareto search | `python solver/run_case.py` | `config/multi_agent_moead_vns_realistic.json` |
| Ablation without repair | Stress test representation importance | same entry with `--no-pipeline` | ad hoc, compare audit feasibility |
| Ablation without bias | Stress test soft guidance importance | same entry with `--no-bias` | ad hoc, compare convergence logs |

## Metrics To Compare

- `production.total`: total feasible output, not just solver score.
- `feasible` and `max_positive_violation`: whether the exported plan is actually executable.
- `material_flow.shortage_total`: shortage after simulating day-by-day stock flow.
- `production.daily_cv`: stability of daily production.
- `machine_usage.switches_total`: operational churn.
- `machine_usage.active_daily_mean/min/max`: utilization pressure.
- `run_logs/benchmark`: convergence and runtime profile.
- `decision_trace`: whether adapters, repair and bias made auditable decisions.

## Recommended Workflow

1. Run the greedy baseline to establish a stable reference.
2. Run the ACO baseline to compare constructive search.
3. Run the multi-agent preset to produce a Pareto batch.
4. Compare `.audit.json` files instead of only comparing raw objective vectors.
5. Only then tune repair/bias parameters, because raw output without feasibility is misleading.

## Why This Is A Real Case

The case is not a single objective toy search. It combines:

- problem-level constraints,
- representation-level repair,
- adapter-level multi-strategy search,
- plugin-level export/audit/trace,
- Pareto batch selection,
- operational scorecards separated from solver objectives.
