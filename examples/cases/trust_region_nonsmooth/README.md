# trust_region_nonsmooth

NSGABlack scaffold (my_project-style layout).

## Quickstart
1. `python -m nsgablack project doctor --path . --build`
2. `python run_solver.py --check`
3. `python run_solver.py`

## Structure
- `build_solver.py`: main assembly entry
- `assembly.py`: attach/build helpers
- `config.py`: project registries
- `problem/`, `pipeline/`, `bias/`, `adapter/`, `solver/`
- `runtime/` (L0), `evaluation/` (L4)
- `plugins/` (governance/ops/observability)
- `catalog/entries.toml`: local catalog entries

## Notes
- Parameters live in registries; selection happens in `build_solver.py`.
- Use `project doctor` to validate contracts early.
