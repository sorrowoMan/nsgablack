# Cases

Each subdirectory is an independent solver/trainer case — a complete standard scaffold.

- Add a new case: `python -m nsgablack project add-case <name> --type solver`
- Run all cases: `python run_project.py` (from project root)
- Debug one case: `cd cases/<name> && python run_solver.py --check`
