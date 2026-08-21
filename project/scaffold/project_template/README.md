# Project Scaffold

Multi-case project. Each subdirectory under `cases/` is one independent solver/trainer case.

## Structure

```text
project_config.py
run_project.py
cases/
  <case_name>/
    README.md
    build_solver.py
    build_trainer.py  # trainer Case only; thin alias
    run_solver.py
    run_trainer.py    # trainer Case only; thin alias
    config.py
    problem/
    pipeline/
      main.py
      operators/
    adapter/
    bias/
    plugins/
```

## Key rules

- Every Case has one canonical build/run entry: `build_solver.py` and `run_solver.py`.
- Every Project and Case has one documentation entry: `README.md`.
- Do not duplicate `START_HERE.md`, registration guides, or contract templates.
- Trainer aliases never contain a second assembly or CLI implementation.
- One case has one pipeline primary entry (`pipeline/main.py` recommended).
- Fine-grained pipeline logic goes to `pipeline/operators/*`.
- Formal orchestration starts at `run_project.py`.
