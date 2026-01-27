# Multi-Strategy Cooperation (Roles + Many Units)

NSGABlack models "multi-agent / multi-algorithm cooperation" as a *framework
application*, not a new solver mode.

Core idea:

- macro-serial phases (explore -> exploit -> refine)
- micro-parallel units inside each phase
- communication via shared facts (archive / telemetry / seeds), not mutual calls

## Building blocks

- Solver base: `core/composable_solver.py` (`ComposableSolver`)
- Controller: `core/adapters/multi_strategy.py` (`MultiStrategyControllerAdapter`)
- Role wrapper + contracts: `core/adapters/role_adapters.py` (`RoleAdapter`)
- Authoritative wiring: `utils/suites/multi_strategy.py` (`attach_multi_strategy_coop`)
- Shared archive (recommended): `utils/plugins/pareto_archive.py`

## Task / report contract

Controller -> role unit (via `context["task"]`):

- `budget` (how many candidates to propose)
- `phase` / `phase_step`
- `region_id` / `region_bounds` (optional)
- `seeds` (optional)

Role unit -> controller (via shared facts):

- role/unit reports (best score, throughput, etc.)
- archive updates (via plugins)

## Why this replaces classic "multi-agent solver"

- no special loop in solver bases
- roles stay isolated; only controller owns global decisions
- coordination strategies can evolve without touching role implementations

