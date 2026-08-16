# Example / Case I/O Contracts

Formal examples are standard Projects containing one or more standard Cases.
The contract is the same whether a Case contains an optimization solver, an ML
trainer, or an evaluation proxy.

## Required Project Contract

Every formal example Project should document:

1. Project stages, groups, and case order in `project_config.py`
2. Project L0 offer, policy, and per-case resource requirements
3. formal entrypoint: `run_project.py`
4. expected `run_project.py --check --build-check` output
5. artifact/result routing between Cases, if any

## Required Case Contract

Every formal Case should document:

1. input payload, data refs, and config keys
2. output result payload, artifact refs, and snapshot refs
3. case-local `run_solver.py --check` output for debugging
4. effective `ResourceContext` fields it consumes
5. README component table matching the actual assembly

## Standard Output Surfaces

| Surface | Content |
| --- | --- |
| result payload | objectives, violations, metrics, summary |
| ArtifactRef / DataRef | model, report, checkpoint, large data |
| SnapshotStore | population, objectives, violations, history, trace |
| context | lightweight refs, signals, counters |
| runtime report | ResourceContext, lease id, worker/backend, fallback |

## Compatibility Wrappers

Old single-file demos may remain as thin wrappers during migration, but they
are not the formal contract. New examples start from Project / Case / Scaffold
and use `run_project.py` for cross-case orchestration and Project L0 grants.
