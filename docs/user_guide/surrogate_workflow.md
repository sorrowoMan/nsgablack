# Surrogate Workflow (Capability Layer)

This workflow keeps solver bases pure. Surrogate logic is injected as a plugin.

## Inputs

- A real problem: `BlackBoxProblem.evaluate(x)` (ground truth)
- A solver: `ComposableSolver` or `BlackBoxSolverNSGAII`
- A representation: `RepresentationPipeline` (feasibility first)
- Optional biases: `BiasModule`

## Output

- Faster runs (fewer real evaluations) *or* lower wall-time under same budget
- Unified logs for fair comparison: CSV + summary JSON

## Recommended wiring

1) Build the baseline (no surrogate)

- attach strategy (Adapter/Suite)
- attach `BenchmarkHarnessPlugin` so every run has the same protocol output

2) Enable surrogate short-circuit

- attach `SurrogateEvaluationPlugin`
- keep `BenchmarkHarnessPlugin` unchanged

3) Compare fairly

- same seed/budget/pipeline/bias/adapter
- only swap surrogate plugin on/off

## Notes

- Surrogate is not a "core goal" of the framework; it is an optional capability.
- Older experimental surrogate implementations were removed to reduce maintenance
  cost; use git history if you need to inspect them.

