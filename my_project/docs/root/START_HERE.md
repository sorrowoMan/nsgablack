# START_HERE

If you only read one file, read this one.

## Stage Gate 0 - Health Baseline
Run first:
```powershell
python -m nsgablack project doctor --path . --build
```
Pass criteria:
- Scaffold exists and doctor output is understandable.
- No unresolved structure errors before wiring.

## Stage Gate 1 - Problem Semantics
File: `problem/example_problem.py`
Deliverable:
- `evaluate(x)` returns objective vector (`numpy.ndarray`).
- `evaluate_constraints(x)` returns violation vector.
Pass criteria:
- Problem file contains only business semantics.
- No repair logic, no plugin logic, no strategy logic.

## Stage Gate 2 - Layer Placement (Most Important)
Split requirements into layers:
- Problem: semantics only
- Pipeline: init/mutate/repair/encode/decode
- Bias: soft preference only
- Solver/Adapter: search strategy and orchestration
- Plugin: observability/engineering/runtime capability
Pass criteria:
- Each requirement is placed in one layer only.
- Any cross-layer decision has an explicit reason.

## Stage Gate 3 - Catalog Candidate Review
Search components:
```powershell
python -m nsgablack project catalog search <keyword> --path . --global
```
For each candidate, record:
- Why choose
- Why not choose alternatives
- Expected input/output shape
- Dependency and state behavior

## Stage Gate 4 - Assembly Wiring
File: `build_solver.py`
Wire by zone order:
1) problem
2) pipeline
3) bias
4) solver core
5) observability plugins
6) project plugins
7) optional checkpoint
Pass criteria:
- Assembly is explicit and traceable.
- No hidden side effects.

## Stage Gate 5 - Registration & Discoverability
Register metadata:
- `catalog/project_registry.py`
- `catalog/entries.toml`
Pass criteria:
- Teammates can understand what each component does from metadata only.

## Stage Gate 6 - Contract Verification
Run:
```powershell
python -m nsgablack project doctor --path . --build --strict
python -m nsgablack project catalog list --path .
```
Pass criteria:
- Context/snapshot/shape checks pass.
- Errors can be explained and fixed by file + line.

## Stage Gate 7 - Evidence Loop
Run minimal experiment:
```powershell
python build_solver.py
```
Optional inspection:
```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```
Pass criteria:
- New user can reproduce run and explain why this composition works.
