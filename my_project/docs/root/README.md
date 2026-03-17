# my_project

NSGABlack scaffold project.

## Structure
- `problem/`: problem semantics
- `problem/data/`: input data (problem-local)
- `problem/evaluation/`: evaluation runtime assets (L4, config is in `problem/config.py`)
- `pipeline/`: representation + hard-constraint repair
- `bias/algorithmic/`: algorithmic bias
- `bias/domain/`: domain/business bias
- `adapter/`: strategy orchestration (optional)
- `plugins/observability/`: L1/L2 observability assets (config in `plugins/config.py`)
- `plugins/checkpoint/`: L1/L2 checkpoint assets (config in `plugins/config.py`)
- `plugins/`: other engineering/runtime capabilities (optional)
- `assets/`: output artifacts (includes `assets/runs/`)
- `*/config.py`: per-layer parameter summaries (avoid hardcoding in build_solver)
- `config.py`: project-level config aggregator (minimize imports in build_solver)

## Recommended Flow
1. Read `START_HERE.md`
2. Read `BUILD_SOLVER_REGISTRATION.md`
3. Read `COMPONENT_REGISTRATION.md`
4. Run `python -m nsgablack project doctor --path . --build`
5. Implement `build_solver.py` registration zones step by step

## Entry Files
- `build_solver.py`: standard assembly entry with explicit registration zones
- `BUILD_SOLVER_REGISTRATION.md`: where each component type should be registered
- `catalog/project_registry.py`: local catalog registry
- `COMPONENT_REGISTRATION.md`: registration metadata contract
