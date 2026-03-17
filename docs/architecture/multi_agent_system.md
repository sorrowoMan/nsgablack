# Multi-Strategy Cooperation (Roles + Many Units)

NSGABlack models "multi-agent / multi-algorithm cooperation" as a *framework
application*, not a new solver mode.

Core idea:

- macro-serial phases (explore -> exploit -> refine)
- micro-parallel units inside each phase
- communication via shared facts (archive / telemetry / seeds), not mutual calls

## Building blocks

- Solver base: `core/composable_solver.py` (`ComposableSolver`)
- Controller: `adapters/multi_strategy/adapter.py` (`StrategyRouterAdapter`)
- Role wrapper + contracts: `adapters/role_adapters/adapter.py` (`RoleAdapter`)
- Wiring pattern: direct `solver.set_adapter(...)` + optional `solver.add_plugin(ParetoArchivePlugin())`
- Shared archive (recommended): `plugins/runtime/pareto_archive.py`

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

