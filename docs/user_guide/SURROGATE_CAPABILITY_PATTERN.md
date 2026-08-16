# Surrogate Capability Pattern

Surrogate evaluation is an optional capability layer. In the unified stack, the
short-circuit hook can be a `Plugin` or provider surface, while ML training and
artifact production should live in an `mlblack` standard Case or another formal
inner Case surface.

Do not fold surrogate logic into Solver or Adapter semantics, and do not let a
nsgablack plugin become a private trainer orchestration system.

## Inputs

- real problem: `BlackBoxProblem.evaluate(x)`
- solver: `ComposableSolver` or `EvolutionSolver`
- representation pipeline
- optional bias module
- Project L0 `ResourceContext` or parent-derived child grant
- optional inner ML Case / artifact references

## Outputs

- fewer real evaluations or lower wall time under the same budget
- audit logs showing when surrogate short-circuited evaluation
- comparable metrics against a non-surrogate baseline

## Recommended Assembly

1. Build the baseline Case.
2. Attach `BenchmarkHarnessPlugin` or equivalent report surface.
3. Attach a surrogate short-circuit Plugin or provider.
4. If training is needed, call a standard inner ML Case and store model artifacts through Artifact/Snapshot refs.
5. Keep seed, budget, pipeline, bias, and adapter unchanged for comparison.
6. Report surrogate hit rate, fallback count, true-evaluation count, inner Case surface, artifact refs, and effective ResourceContext.

## Critical Bias Rule

Bias must apply exactly once in the evaluation lifecycle.

`SurrogateEvaluationProviderPlugin._true_evaluate()` must return raw objectives. It must not call `bias_module.compute_bias()` internally.

When the plugin calls a parallel evaluator, pass:

```python
enable_bias=False
bias_module=None
```

The unified evaluation chain applies bias after raw objectives are obtained. This avoids double-bias and keeps surrogate training data clean.

## RNG Rule

If the plugin needs randomness, use an instance RNG such as:

```python
self._rng = np.random.default_rng()
```

Do not use global `np.random`.

## Boundary

Surrogate logic may short-circuit evaluation, cache data, request an inner trainer Case, and emit artifacts. It must not change adapter search semantics, own cross-Case orchestration, allocate global resources, or parse trainer-private objects.
