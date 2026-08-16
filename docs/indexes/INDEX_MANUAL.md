# Manual Index Policy

This repository no longer maintains a large hand-written component index. The previous manual index mixed framework-core entries with compatibility examples and could drift away from the current Project / Case / Scaffold substrate.

Use the catalog as the source of truth:

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
python -m nsgablack catalog show <key> --profile framework-core
```

Use `framework-core` when you are auditing architecture, runtime contracts, or public component surfaces. Use `default` only when you intentionally want documentation and example entries included.

## Current Structure

| Surface | Source of Truth |
| --- | --- |
| Solver lifecycle | `core/blank_solver.py`, `core/composable_solver.py`, `core/evolution_solver.py` |
| Search strategy | `adapters/` |
| Candidate representation | `representation/` and Case `pipeline/` |
| Runtime capability | `plugins/` |
| State protocol | `core/state/`, `utils/context/` |
| Project substrate | `project/`, `project/runtime.py`, `project/scaffold/` |
| Formal examples | `examples/cases/<project>/run_project.py` |
| Compatibility demos | explicitly marked compatibility wrappers |

## Regeneration Rule

If a static index is needed for a release artifact, generate it from catalog output and record the profile used. Do not manually copy example registry entries into this file.
