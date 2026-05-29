# Project Scaffold

Multi-case optimization project. Each subdirectory under `cases/` is an independent solver/trainer — a complete standard scaffold with its own `build_solver.py`, problem, pipeline, adapter, bias, plugins.

## Structure

```
project_config.py     — Stage/group orchestration (STAGES, GROUPS)
run_project.py        — Top-level entry point (DISCOVERS and RUNS cases)
cases/
  <case_name>/        — One solver/trainer per directory
    build_solver.py   — Canonical assembly entry
    build_trainer.py  — Alias (delegates to build_solver)
    run_solver.py     — Standalone debug CLI
    run_trainer.py    — Alias (delegates to run_solver)
    config.py         — Component registries
    problem/          — Problem definition
    pipeline/         — Encode/decode/init/mutate/repair + data
    adapter/          — Search/optimizer strategy
    bias/             — Soft guidance
    plugins/          — Lifecycle capabilities
```

## Quickstart

1. Add cases:
   ```powershell
   python -m nsgablack project add-case <name> --type solver
   python -m nsgablack project add-case <name> --type trainer
   ```

2. Edit each case's `build_solver.py` to wire in your problem, pipeline, adapter.

3. Run everything from the project root:
   ```powershell
   python run_project.py
   ```

4. Run a single case for debugging:
   ```powershell
   cd cases/<name>
   python run_solver.py
   ```

## Key Rule

**The top-level `run_project.py` is the official entry point.** Even for a single solver, run from the project root — not from inside the case directory. Cases are orchestrated through `project_config.py` (STAGES/GROUPS), not run individually.
