# mlblack_symbolic_consensus_scaffold

First formal "nsgablack orchestrates mlblack" scaffold.

This case is intentionally organized as a standard project shape. The files under
`examples/cases/...` are allowed to be an example location, but the assembly must
still follow the same responsibility split as `my_project`.

## Layers

- `L1 / nsgablack`
  - owns the outer solver, multi-strategy candidate search, timeout budget, bias, constraints, and bridge-back metrics
  - chooses symbolic consensus/search-budget knobs as the outer decision vector
- `L2 / mlblack`
  - owns the actual symbolic orthogonal-basis runs
  - executes multi-run consensus plus locked-core refinement
  - emits truth-recovery, rmse, and core-basis summaries

## Contract path

1. `TaskInnerRuntimeEvaluator`
2. `EvaluationModelProviderPlugin(scope="inner")`
3. `MlblackSymbolicConsensusBackend.solve(request)`
4. `mlblack.workflow.run_semantic_train_flow(...)`

## Project Shape

- `case_scaffold/problem/`: outer decision-vector decoding, objectives, constraints, and inner-task contract
- `case_scaffold/pipeline/`: representation pipeline for the outer genome
- `case_scaffold/config/`: CLI/config surface
- `case_scaffold/orchestration/`: solver assembly and adapter strategy selection
- `case_scaffold/bias/`: symbolic structure/domain bias assembly
- `case_scaffold/plugins/`: runtime provider, bridge, timeout, tracking, and observability wiring
- `case_scaffold/reporting/`: result projection from inner mlblack runs back to the outer run result
- `build_solver.py`: thin compatibility/entry wrapper only
- `run_benchmark_suite.py`: suite runner that calls the formal scaffold entrypoint

`case_scaffold/` is a deliberate namespace boundary. It prevents generic project-layer names
such as `config`, `plugins`, or `pipeline` from shadowing top-level imports used by `mlblack`.

## Run

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\build_solver.py `
  --benchmark-key ohm_like `
  --outer-adapter complex `
  --generations 3 `
  --pop-size 6 `
  --vanilla-runs 3 `
  --locked-runs 2
```

`--outer-adapter complex` is the default. It uses a `StrategyRouterAdapter` with NSGA-II,
SPEA2, differential evolution, VNS, non-smooth trust region, and pattern search roles.
Use `--outer-adapter vns` only for legacy single-adapter comparisons.

## Output

- outer run logs: `examples/cases/mlblack_symbolic_consensus_scaffold/runs/...`
- inner mlblack summaries: `inner_mlblack/<benchmark>/<signature>/summary.json`
- mlblack experiment tracker DB: `mlblack_experiment_tracker.sqlite3`
