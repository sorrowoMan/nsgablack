# plugins

Plugin layer for optional engineering/runtime capabilities.

## Purpose
- Extend solver lifecycle with reporting, profiling, storage, runtime control, and safety guards.
- Keep Problem/Pipeline/Bias/Adapter focused on core optimization semantics.

## Trigger Timing
- Triggered by lifecycle hooks in PluginManager:
  `on_solver_init`, `on_population_init`, `on_generation_start`,
  `on_generation_end`, `on_solver_finish`.

## Input
- Solver state (population/objectives/violations/generation/etc.).
- Optional context fields (declare with `context_requires`).

## Output
- Run artifacts/reports/metrics.
- Optional context writes (`context_provides` / `context_mutates`).

## Side Effects
- May write files, DB records, logs, and console output.

## Failure Policy
- Default should be non-blocking for optimization loop.
- Strict mode can be fail-fast when needed.

## Subdirectories
- `evaluation/`: evaluation protocol and acceleration
- `models/`: model/subspace related plugins
- `ops/`: benchmark/report/profiling/sensitivity
- `runtime/`: runtime behavior plugins
- `storage/`: external storage integrations
- `system/`: system guard plugins

## Selection Guide
- See `docs/user_guide/PLUGIN_SELECTION.md` for scenario-based plugin choices.
