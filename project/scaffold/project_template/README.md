# Project Scaffold

Multi-case project. Each subdirectory under `cases/` is one independent solver/trainer case.

## Structure

```text
project_config.py
run_project.py
cases/
  <case_name>/
    build_solver.py or build_trainer.py
    run_solver.py or run_trainer.py
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

- One case has one primary build/run entry by `.case kind`.
- One case has one pipeline primary entry (`pipeline/main.py` recommended).
- Fine-grained pipeline logic goes to `pipeline/operators/*`.
- Formal orchestration starts at `run_project.py`.
