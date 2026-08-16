# Depth And Breadth Patterns

This page replaces the old workflow wording with the current Project / Case / Scaffold substrate.

Depth means nested Case evaluation. Breadth means same-level cooperation between adapters, solvers, or Cases.

## Depth

```text
Project
  -> outer Case
     -> candidate evaluation
        -> inner Case
           -> optional lower-level numerical backend
```

Use depth when one candidate needs another runnable unit to produce metrics, artifacts, or constraints.

Typical surfaces:

- `problem.inner_runtime_evaluator`
- nested request/result payload
- artifact refs for large outputs
- `ResourceContext` derived from Project L0
- strict or soft failure policy

## Breadth

Breadth is same-level cooperation:

- multi-adapter search inside one solver
- solver fanout across multiple Cases
- multiple bias components
- multiple plugins for observation and audit
- Project-level parallel stages

Adapter cooperation remains search semantics. Cross-Case fanout belongs to Project orchestration.

## Standard Loop

1. Create a standard Project.
2. Add one or more standard Cases.
3. Implement problem, pipeline, adapter, bias, plugin, and runtime request inside each Case.
4. Declare stage order and L0 resources in `project_config.py`.
5. Run through `run_project.py`.
6. Inspect with doctor, catalog, run reports, snapshots, and artifacts.

## Design Boundary

- `plugins/evaluation` provide evaluation capabilities.
- `plugins/solver_backends` provide bridge surfaces.
- Adapter owns search flow.
- Project owns cross-Case order and resource grants.
- Context stores lightweight refs and signals.
- Snapshot and Artifact stores carry large data.
