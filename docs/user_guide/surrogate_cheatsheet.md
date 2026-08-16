# Surrogate Cheatsheet (Capability Layer)

In NSGABlack, surrogate support is treated as a *capability layer*:

- it should not change solver bases
- it integrates via Plugin / provider / Wiring
- ML training, if needed, should be exposed by an `mlblack` standard Case or another formal inner Case surface

## Recommended entrypoints

- Short-circuit plugin/provider: `plugins/evaluation/surrogate_evaluation.py` (`SurrogateEvaluationProviderPlugin`)
- Cross-framework integration: `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`
- Docs: `docs/user_guide/SURROGATE_CAPABILITY_PATTERN.md`

## Typical usage pattern

1) Keep your real `BlackBoxProblem.evaluate(x)` as the source of truth
2) Attach surrogate plugin/provider to short-circuit / prefilter expensive evaluations
3) Use an inner ML Case for training/artifact production when the surrogate is learned
4) Record unified experiment outputs via `BenchmarkHarnessPlugin`
5) Report effective `ResourceContext`, artifact refs, hit rate, fallback count, and true-evaluation count

## Why this design

- You can enable/disable surrogate logic without touching algorithms
- You can fairly compare runs (same pipeline/bias/adapter, only swap plugins)

Note: older experimental surrogate subsystems were removed to reduce maintenance
cost; use git history if you need to inspect them.

