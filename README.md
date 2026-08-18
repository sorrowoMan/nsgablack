# NSGABlack

`nsgablack` is the optimization and search semantic layer in a shared framework stack. It is not just an NSGA-II wrapper; it is an engineering framework for building auditable optimization systems with clear boundaries between problem semantics, candidate representation, search strategy, runtime capabilities, state, and reports.

Current architecture rule:

- `nsgablack` and `mlblack` share the Project / Case / Scaffold / L0 substrate.
- `nsgablack` is responsible for optimization/search semantics: Solver lifecycle, Adapter search policy, candidate representation, Pareto/frontier governance, objective/constraint evaluation, and search audit.
- `mlblack` is responsible for machine-learning semantics: DataView, Spec, Codec, Head, Trainer, Provider, Artifact, and ML reports.
- Orchestration and resource grants belong to the shared substrate, not to either semantic layer privately.

Shared substrate baseline: `blackbase>=0.3.0,<0.4.0`.
Version 0.3 removes the former resource/context forwarders and uses BlackBase
directly for Case orchestration, L0 grants, call binding, Catalog primitives,
runtime projection envelopes, and atomic ContextStore semantics.

## What It Solves

Complex optimization projects usually fail because boundaries blur:

- business constraints, repair, logging, checkpointing, and search logic get mixed into one loop
- nested evaluation and multi-solver execution become ad hoc scripts
- GPU/thread settings are hidden inside examples or trainers
- large runtime objects leak into context
- examples drift away from framework contracts

`nsgablack` makes those boundaries explicit:

| Layer | Responsibility |
| --- | --- |
| `Problem` | Objectives, constraints, bounds, and evaluation semantics |
| `Solver` | Lifecycle, evaluation entrypoints, state access, plugin dispatch |
| `Adapter` | Search policy through `propose/update` |
| `RepresentationPipeline` | Candidate init/mutate/repair/encode/decode |
| `BiasModule` | Soft guidance, priors, and preference signals |
| `Plugin` | Runtime capabilities such as trace, checkpoint, report, backend, and short-circuit evaluation |
| `ContextStore` | Lightweight state, canonical keys, and refs |
| `SnapshotStore` | Large objects such as population, objectives, violations, history, and trace |
| `Catalog` | Discoverability and profile-filtered component index |
| `Project / Case / L0` | Top-level orchestration, standard scaffold shape, and resource grants |

## Standard Project Shape

Formal projects use three layers:

```text
project_root/
  project_config.py
  run_project.py
  README.md
  cases/
    __init__.py
    case_a/
      __init__.py
      build_solver.py
      run_solver.py
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/
      solver/
```

Rules:

- `run_project.py` is the formal project entry.
- `project_config.py` declares cross-case order and Project L0 resources.
- each Case is independently runnable and inspectable.
- `build_solver.py` is the canonical Case assembly entry.
- `build_trainer.py`, when present for ML naming ergonomics, is only a thin alias.
- Case-level `runtime/` declares requirements and audit behavior; it does not own the global pool.

## Nested Optimization

Nested optimization is not a special side-channel. It is standard Case composition:

```text
outer Project
  -> outer Case
     -> evaluates candidate
        -> calls inner Case through a standard request/result payload
```

The outer Case does not import inner private implementation details. It passes candidates, component overrides, budget, artifact refs, and `ResourceContext`; the inner Case returns objectives, violations, metrics, artifact refs, and audit payload.

At the standard Case boundary, Solver outputs are encoded as a versioned
`SolverResult`; direct `Solver.run()` return conventions remain unchanged.
The result boundary never scalarizes a population to invent a best solution:
best solution/objectives/violation must be declared by the Solver's own
algorithm semantics.  Execution status and solve status remain separate, and
oversized Pareto fronts are published through the Project artifact authority
instead of being copied into the Case envelope.
The same inline-size policy applies to large best solutions, which are returned
as real `best_solution_ref` artifacts rather than oversized inline payloads.
Composable and evolutionary Solvers maintain one run-wide incumbent through a
feasibility-first comparator; the configured objective scalarizer is then used
inside the same feasibility class. Direct tuple/dict results and `SolverResult`
all read that incumbent, while the current population remains separate runtime
state. The incumbent is an atomic `IncumbentState` record, fresh runs clear it,
checkpoint resume restores it in one operation, and explicit warm starts are
reevaluated before they may become authoritative. Custom incumbent scalarizers
are pointwise policies; failures raise by default, while explicit fallback is
audited as degraded result quality. Checkpoint v2 persists that audit state and
rejects a resume when the builder reconstructed a different scalarizer policy.
Large incumbent candidates are stored in SnapshotStore and exposed through the
canonical `best_candidate_ref`; only candidates below the configured serialized
size limit remain inline in ContextStore. Oversized candidates are persisted
before the authoritative incumbent commit, so a strict Snapshot failure cannot
partially replace the in-memory best. Context is a derived atomic projection;
projection failures keep the committed incumbent and are recorded as stale
projection audit state instead of being silently swallowed. Candidate tokens travel beside batch
rows through repair and evaluation, so warm-start lineage is never inferred by
comparing candidate values.

This also covers multi-solver and multi-trainer projects: put each runnable unit in its own Case and let the Project substrate coordinate order, parallelism, and resources.

## L0 Resource Model

Resources are declared at Project level and granted to Cases:

```python
L0 = {
    "backend": "local",
    "resource_pool": {
        "threads": 16,
        "device_tokens": ("logical-gpu-a", "logical-gpu-b"),
    },
}

resource_requests = {
    "outer_search": {"threads": 4},
    "inner_learning": {"threads": 4, "device_tokens": ("logical-gpu-a",)},
}
```

Case code consumes the effective `ResourceContext` injected by the Project runtime. It should not hard-code machine-local devices, thread counts, or backend internals.

## Quick Start

```powershell
python -m nsgablack project new my_project
cd my_project
python -m nsgablack project add-case my_case --type solver
python -m nsgablack project doctor --path . --build --strict
python run_project.py
```

For current tutorial flow, start with:

- `docs/standard_scaffold_tutorial/README.md`
- `docs/standard_scaffold_tutorial/01_create_and_run.md`
- `docs/standard_scaffold_tutorial/02_component_configuration.md`
- `docs/standard_scaffold_tutorial/03_orchestration_language.md`
- `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`

## Catalog Profiles

Use `framework-core` when auditing framework architecture:

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
```

Use `default` only when examples and documentation entries should be included.

## Example Policy

Formal examples belong under `examples/cases/<case>/` or a documented Project example namespace.

Repository-root `my_project/` is a starter template, reference skeleton, compatibility layer, or private incubation workspace. New formal examples, demos, benchmark runners, and cross-framework cases should not be parked there long term.

Compatibility demos may remain while being migrated, but new mechanisms should be implemented through the standard Project / Case / Scaffold surface.
