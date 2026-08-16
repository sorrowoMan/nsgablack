# Production Scheduling Case

`production_scheduling` is a formal Project-wrapped nsgablack Case.

Authority lives here:

- Project root: `examples/cases/production_scheduling/`
- Formal entry: `python examples/cases/production_scheduling/run_project.py --check`
- Case scaffold: `examples/cases/production_scheduling/cases/production_scheduling/`

## Shape

```text
examples/cases/production_scheduling/
  project_config.py
  run_project.py
  cases/
    production_scheduling/
      build_solver.py
      run_solver.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      solver/
```

`working_integrated_optimizer.py` and similar single-file entries are
compatibility material only. New orchestration and resources belong at the
Project layer.

## Run

From the repository root:

```powershell
python examples\cases\production_scheduling\run_project.py --check
```

Scenario-specific commands are documented in the Project and Case README files.
