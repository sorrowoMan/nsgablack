# Surrogate Cheatsheet (Capability Layer)

In NSGABlack, surrogate support is treated as a *capability layer*:

- it should not change solver bases
- it integrates via Plugin / Suite

## Recommended entrypoints

- Plugin: `utils/plugins/surrogate_evaluation.py` (`SurrogateEvaluationPlugin`)
- Docs: `docs/user_guide/surrogate_workflow.md`

## Typical usage pattern

1) Keep your real `BlackBoxProblem.evaluate(x)` as the source of truth
2) Attach surrogate plugin to short-circuit / prefilter expensive evaluations
3) Record unified experiment outputs via `BenchmarkHarnessPlugin`

## Why this design

- You can enable/disable surrogate logic without touching algorithms
- You can fairly compare runs (same pipeline/bias/adapter, only swap plugins)

Note: older experimental surrogate subsystems were removed to reduce maintenance
cost; use git history if you need to inspect them.

