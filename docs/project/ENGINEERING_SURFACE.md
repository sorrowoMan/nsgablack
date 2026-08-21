# Engineering Surface

This page keeps the current engineering surface compact and authoritative.
Historical technology-stack notes live in Git history and are not architecture
authority.

## Main Runtime Shape

- Project / Case / Scaffold is the formal runnable shape.
- `run_project.py` is the formal entrypoint.
- `project_config.py` declares stages, groups, dependencies, and Project L0
  resources.
- `cases/<case>/build_solver.py` is the canonical Case assembly entry.
- `run_solver.py --check` is only for Case-level debugging and wiring checks.

## Core Layers

| Layer | Entry | Boundary |
| --- | --- | --- |
| Solver | `core/blank_solver.py`, `core/composable_solver.py`, `core/evolution_solver.py` | lifecycle, evaluate, context/snapshot |
| Adapter | `adapters/` | `propose/update` search strategy |
| Representation | `representation/` and Case `pipeline/` | init/mutate/repair/encode/decode |
| Bias | `bias/` | soft guidance, not hard constraints |
| Plugin | `plugins/` | trace/checkpoint/report/short-circuit/backend audit |
| L0 | `core/resources/`, `project/` runtime | Project resource grant and transport |

## Resource Surface

Parallel evaluation, GPU, Ray, Redis, databases, object stores, and workers
must enter through L0/resource/runtime surfaces.

- Project declares the resource pool and service backends.
- Case declares requirements.
- `ResourceContext` is the effective fact.
- Local helpers may exist for debugging, but formal docs and new examples must
  start from Project L0 grants.

## Discoverability

- Use `catalog --profile framework-core` for framework-core audits.
- Use `catalog --profile default` for examples and docs.
- Stability boundaries live in `CORE_STABILITY.md`, `API_STABILITY_POLICY.md`,
  and `STABLE_API_SURFACE.md`.
- Documentation cleanup rules live in `DOCS_ARCHITECTURE_AUDIT.md`.
