# 05. Cross-Framework Coordination

`nsgablack` and `mlblack` coordinate through the shared Project / Case / Scaffold / L0 substrate. The frameworks are not parent and child by definition; a standard Case can be outer or inner.

## Core Rule

| Concern | Owner |
| --- | --- |
| Project order, fanout, resources | shared substrate |
| optimization/search semantics | `nsgablack` |
| ML/data/training/artifact semantics | `mlblack` |
| nested request/result protocol | shared Case surface |
| global resource allocation | Project L0 |

## Standard Nested Shape

```text
project_root/
  project_config.py
  run_project.py
  cases/
    outer_search/
      build_solver.py
      problem/
      pipeline/
      runtime/
    inner_learning/
      build_solver.py
      problem/
      pipeline/
      runtime/
```

The outer Case evaluates a candidate by creating a standard inner request:

```python
request = {
    "candidate": decoded_candidate,
    "budget": {"steps": 20},
    "component_overrides": overrides,
    "resource_context": child_resource_context,
    "namespace": "outer_search.eval.0007",
}
```

The inner Case returns a standard result:

```python
result = {
    "objectives": [0.12, 3.4],
    "violations": [0.0],
    "metrics": {"fit_rmse": 0.12, "latency_ms": 842},
    "artifact_refs": ["artifact://runs/0007/model.json"],
    "audit": {"resource_context": child_resource_context},
}
```

The outer Case projects that result into its own objective space. It does not read inner private Trainer or Provider state.

## Resource Flow

```text
Project L0
  -> grant outer Case
  -> outer Case requests child grant for candidate evaluation
  -> inner Case consumes child ResourceContext
  -> inner Case reports effective runtime
```

If the inner Case cannot use a granted backend, it must report a fallback or fail according to policy. It should not silently switch to a larger resource scope.

## Anti-Patterns

| Anti-pattern | Replacement |
| --- | --- |
| outer Case imports inner private trainer class | call inner Case through standard build/run surface |
| example file sets machine-local device directly | Project L0 grants a logical device token |
| `mlblack` requires `nsgablack` to orchestrate | standalone `mlblack` Project uses shared substrate |
| multi-trainer run inside one Case script | Project with multiple standard Cases |
| cross-framework result is a bare float | structured result payload with metrics, artifacts, audit |

## Component Overrides

Outer candidates may control inner behavior through explicit payload:

```python
component_overrides = {
    "trainer.hidden_dims": [128, 64],
    "head.kind": "interval",
    "feature_source.enabled": True,
}
```

Overrides are data. They are not permission to mutate inner code or bypass the inner Case config contract.

## Audit Checklist

Every cross-framework run should record:

- outer Case assembly signature
- inner Case assembly signature
- candidate payload
- component overrides
- requested and effective `ResourceContext`
- result projection rule
- artifact refs
- fallback or failure policy

That is the minimum needed for reproducible nested optimization.
