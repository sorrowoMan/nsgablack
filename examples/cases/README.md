# examples/cases

This directory stores runnable example Projects. Each direct child is a
Project wrapper, and each runnable Solver/Trainer lives inside that Project as
a standard Case scaffold.

## Current Rule

Formal examples use the shared Project / Case / Scaffold / L0 substrate:

```text
examples/cases/<project>/
  project_config.py
  run_project.py
  README.md
  cases/
    __init__.py
    <case>/
      __init__.py
      README.md
      build_solver.py
      run_solver.py
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/
      solver/
```

`run_project.py` is the formal entrypoint. It reads `project_config.py`, asks
Project-level L0 for a `ResourceContext`, and then runs the selected Case(s).

Case-level `build_solver.py` remains the canonical assembly entry for one
Solver/Trainer. Case-level `run_solver.py` is a debug/inspection entry only.
Project and Case guidance lives in their respective `README.md`; duplicated
onboarding and registration documents are not part of the scaffold.

## Multi-Case Projects

Nested optimization, multi-solver, multi-trainer, and cross-framework workflows
must be expressed as multiple standard Cases under one Project:

```text
examples/cases/<project>/
  project_config.py      # stages, groups, resource requests
  run_project.py         # only formal run entry
  cases/
    outer_search/
    inner_trainer/
```

Project L0 owns resource authorization and grants. Cases declare requirements
and consume the effective grant; they do not allocate global resources by
themselves.
