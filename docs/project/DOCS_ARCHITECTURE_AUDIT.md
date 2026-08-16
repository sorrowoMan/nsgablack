# Documentation Architecture Cleanup Log

This file records the current documentation cleanup baseline. It is not a substitute for the authoritative architecture docs.

Current rule:

- `nsgablack` and `mlblack` share the Project / Case / Scaffold / L0 substrate.
- `nsgablack` is the optimization and search semantic layer.
- `mlblack` is the machine-learning semantic layer.
- orchestration, resource grants, and nested Case execution belong to the shared substrate.

## Cleanup Policy

When a document conflicts with the current architecture, prefer one of these actions:

1. Rewrite it around Project / Case / Scaffold / L0.
2. Replace it with a short migration note that points to the current tutorial.
3. Delete it if it only duplicates a stale example entry.

Do not keep long historical explanations beside current rules. They look like supported behavior and confuse users.

## Canonical References

- `docs/standard_scaffold_tutorial/README.md`
- `docs/standard_scaffold_tutorial/01_create_and_run.md`
- `docs/standard_scaffold_tutorial/03_orchestration_language.md`
- `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`
- `docs/user_guide/PROJECT_SCAFFOLD.md`
- `docs/architecture/L0_RESOURCE_ORCHESTRATION.md`

## Directory Decisions

| Directory | Decision | Reason |
| --- | --- | --- |
| `docs/` root | keep only navigation / Sphinx / quickstart | avoid mixed authority docs at root |
| `architecture/` | keep architecture rules only | no concrete backend manuals or historical reports |
| `integrations/` | keep external backend integration docs | COPT, ML tools, DB/backend integration live here |
| `standard_scaffold_tutorial/` | keep as primary tutorial | current Project / Case / Scaffold / L0 path |
| `user_guide/` | keep current recommended operations only | legacy paths must be rewritten or marked compatibility |
| `guides/` | keep component-boundary and hands-on guides | learning notes and research material moved out |
| `concepts/` | keep conceptual summaries and current concept-alignment docs | no operational step-by-step, governance, or backend integration |
| `indexes/` | keep index/navigation docs only | no long conceptual or tutorial body |
| `project/` | keep governance, stability, ADR, catalog DB protocol, run surface, cleanup policy | research narratives and concept-alignment docs moved out |
| `cases/` | keep case summaries and reproduction pointers | executable authority remains `examples/cases/<project>/run_project.py` |
| `research/` | keep non-authoritative research, learning, narrative, ML pattern notes | not architecture authority |
| `archive/` | keep read-only historical material | not referenced as current facts |
| `changelog/` | keep change logs and redirects | canonical project changelog remains under `project/` |

## Migrations In This Cleanup

- Root docs were moved into their owning directories:
  - `ALGORITHM_DECOMPOSITION_HANDS_ON.md` -> `guides/`
  - `AUTHORITATIVE_EXAMPLES.md`, `CATALOG_DB_PROTOCOL.md`, `CORE_STABILITY.md`, `TODO.md` -> `project/`
  - `COMPONENT_EXAMPLES_INDEX.md`, `INDEX_MANUAL.md` -> `indexes/`
  - `COMPUTE_FLOW_GUIDE_CN.md` -> `user_guide/`
  - `COPT_Python_Only_CN.md` -> `integrations/`
  - `FEATURES_OVERVIEW.md` -> `concepts/`
- `architecture/COPT_INTEGRATION.md` moved to `integrations/COPT_INTEGRATION.md`.
- `guides/LEARNING_ROADMAP.md` and `guides/ML_PATTERN_REFERENCE.md` moved to `research/`.
- `project/FRAMEWORK_CONCEPT_MAPPING.zh-CN.md` and `project/code_concept_alignment/` moved to `concepts/`.
- stale research redirect files under `project/` were removed after the real documents moved to `research/`.
- `project/TECH_STACK_ALIGNED.md` moved to `archive/`; current engineering facts live in `project/ENGINEERING_SURFACE.md`.
- `archive/README.md` now marks archived material as non-authoritative.

## Next Example Refactor Queue

Documentation now points users toward the current substrate. The remaining implementation cleanup is to migrate or mark compatibility examples so every formal example lives as a Project with one or more standard Cases.
