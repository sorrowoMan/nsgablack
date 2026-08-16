# Component Example Index

This page no longer maintains a hand-written map from components to legacy
single-file demos. That map drifted from the current architecture and made old
`examples/*.py` compatibility scripts look authoritative.

## Current Rule

Formal examples are standard Projects containing standard Cases:

```text
examples/cases/<project>/
  project_config.py
  run_project.py
  cases/
    <case>/
      build_solver.py
      run_solver.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      runtime/
```

Use Project entrypoints first:

```powershell
python examples/cases/<project>/run_project.py --check
python examples/cases/<project>/run_project.py --check --build-check
```

Case-level `run_solver.py` is a debug entry. It may not exist as a full
reproduction command for every historical case.

## How To Find Component Usage

Use Catalog and inspect the formal Project/Case README:

```powershell
python -m nsgablack catalog search bias --profile default
python -m nsgablack catalog search adapter --profile framework-core
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

For framework-core conclusions, always use `--profile framework-core`.

## Compatibility Material

Old scripts under `examples/_misc_examples/` may remain useful for migration
or quick comparison, but they are compatibility material. New mechanisms and
new documentation should point to `examples/cases/<project>/run_project.py`.
