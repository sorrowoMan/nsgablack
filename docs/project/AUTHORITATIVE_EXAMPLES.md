# Authoritative Example Policy

Formal examples are standard Projects and Cases. A legacy single-file demo is not an authoritative example, even if it still exists for compatibility.

## Current Standard

A formal example must:

- live under `examples/cases/<project>/`
- expose `project_config.py` and `run_project.py` at the Project root
- keep runnable solvers/trainers under `cases/<case>/`
- expose `cases/<case>/build_solver.py` as the canonical Case assembly entry
- keep `cases/<case>/run_solver.py` as debug/inspection only
- declare Project L0 resources at Project level
- consume `ResourceContext` inside the Case
- keep README component tables consistent with Project `--check` / `--build-check`

## Migration Rule

Old demo scripts should be converted into standard Cases or marked as compatibility wrappers. New mechanisms must not be added to compatibility wrappers.

When a former demo becomes a formal example, document only the Project entry:
`examples/cases/<project>/run_project.py`. Do not keep a long mapping table of
old script paths in user-facing docs; it makes stale entrypoints look supported.

## Reference Entrypoints

- `docs/standard_scaffold_tutorial/README.md`
- `docs/standard_scaffold_tutorial/01_create_and_run.md`
- `examples/cases/README.md`
- `python -m nsgablack project doctor --path . --strict --format problem`
