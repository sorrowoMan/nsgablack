# my_project

NSGABlack scaffold project.

## Structure
- `problem/`: problem semantics
- `pipeline/`: representation + hard-constraint repair
- `bias/`: soft preferences
- `adapter/`: strategy orchestration (optional)
- `plugins/`: engineering/runtime capabilities (optional)
- `data/`: input data
- `assets/`: output artifacts

## Recommended Flow
1. Read `START_HERE.md`
2. Read `BUILD_SOLVER_REGISTRATION.md`
3. Read `COMPONENT_REGISTRATION.md`
4. Run `python -m nsgablack project doctor --path . --build`
5. Implement `build_solver.py` registration zones step by step

## Entry Files
- `build_solver.py`: standard assembly entry with explicit registration zones
- `BUILD_SOLVER_REGISTRATION.md`: where each component type should be registered
- `project_registry.py`: local catalog registry
- `COMPONENT_REGISTRATION.md`: registration metadata contract
