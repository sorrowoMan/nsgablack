# docs/ - Documentation Hub

If you are new:

- `START_HERE.md` (repo root): the entrance map
- `QUICKSTART.md` (repo root): 10-minute runnable path
- `WORKFLOW_END_TO_END.md` (repo root): end-to-end workflow (inputs/outputs per step)

Decoupling guides (recommended):

- `docs/guides/DECOUPLING_PROBLEM.md`: what belongs in Problem (evaluate/bounds/constraints)
- `docs/guides/DECOUPLING_REPRESENTATION.md`: representation pipeline (init/mutate/repair/codec)
- `docs/guides/DECOUPLING_BIAS.md`: bias system (domain/algorithmic/signal-driven)
- `docs/guides/DECOUPLING_CAPABILITIES.md`: capabilities layer (plugins/suites/catalog)

Core references:

- `docs/concepts/FRAMEWORK_OVERVIEW.md`: big picture overview
- `docs/concepts/FRAMEWORK_PHILOSOPHY.md`: design rationale
- `docs/project/PROJECT_DETAILED_OVERVIEW.md`: detailed engineering walkthrough
- `docs/CORE_STABILITY.md`: what is considered stable / boundaries
- `docs/project/API_STABILITY_POLICY.md`: stability tiers + deprecation rules (SemVer-aligned)
- `docs/project/RELEASE_PROCESS.md`: version semantics + release workflow (tag-driven)
- `docs/project/STABLE_API_SURFACE.md`: stable entrypoints list (what users can rely on)
- `docs/project/MIGRATION_GUIDE_TEMPLATE.md`: template for breaking/deprecation migrations
- `docs/project/TECH_STACK_RESUME.md`: resume-style tech stack highlights (with complexity proof)
- `docs/project/TECH_STACK_ALIGNED.md`: implementation details map (deeper engineering notes)
- `docs/architecture/LOCAL_OPTIMIZATION_INTEGRATION_REPORT.md`: local optimization integration report
- `docs/architecture/FRONTIER_ALGOS_INTEGRATION.md`: frontier algorithm suites + demos

Discoverability:

- `docs/user_guide/catalog.md`: Catalog + Suites usage
- `docs/user_guide/RUN_INSPECTOR.md`: Run Inspector usage manual
- `utils/viz/visualizer_tk.py`: Run Inspector UI (review wiring before run)
  - `python -m nsgablack run_inspector --entry path/to/script.py:build_solver`
- `docs/AUTHORITATIVE_EXAMPLES.md`: 2-4 authoritative runnable examples (fact standard)
- `docs/cases/production_scheduling.md`: authoritative real-world case (production scheduling)

Project snapshots:

- `docs/FEATURES_OVERVIEW.md`: feature map / capability overview
- `docs/PROJECT_COLLAB_RESEARCH_PLAN.md`: academic-style collaboration plan
- `docs/TODO.md`: near-term roadmap and idea pool

Indexes:

- `docs/indexes/API_INDEX.md`: strict API entrypoints map
- `docs/indexes/REPRESENTATION_INDEX.md`: representation pipeline index
- `docs/indexes/TOOLS_INDEX.md`: tools + utilities
- `docs/indexes/TAGGED_INDEX.md`: tagged module index
- `docs/indexes/BIAS_INDEX.md`: bias index
- `docs/indexes/EXAMPLES_INDEX.md`: examples entrypoint (redirect)

Note:

Historical/experimental directories were removed to reduce maintenance pressure.
If you need to inspect old explorations, use git history.
