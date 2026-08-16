# examples

Purpose: runnable demonstrations, from lightweight compatibility snippets to
formal Project / Case / Scaffold examples.

Boundary: examples are not framework API. New mechanisms should become formal
examples only when they can be expressed through the shared substrate.

## Current Example Surface

- Formal examples live under `examples/cases/<project>/`.
- Each formal example exposes `project_config.py` and `run_project.py` at the
  Project root.
- Runnable solver/trainer units live under
  `examples/cases/<project>/cases/<case>/`.
- `examples/_misc_examples/` is compatibility and teaching material, not the
  preferred landing zone for new mechanisms.
- Runtime/artifact surface inspection should be wired through standard Case
  plugins and Project reports.

## Migration Workshops

- `migration_lab/README.md`: traditional script -> framework migration labs
- `migration_lab/ga_single_objective/`: first workshop (single-objective GA)
