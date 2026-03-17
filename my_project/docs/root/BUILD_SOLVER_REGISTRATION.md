# BUILD_SOLVER_REGISTRATION

Goal: after searching from catalog, you should know exactly where to place each component.

## Zone Rule (must follow)
Each zone only handles wiring and coordination.
Component parameters live in layer config registries; `build_solver.py` only selects keys.

## Zone Order
1. Problem / Pipeline / Bias
   - `reg_modeling(cfg, problem_key=..., pipeline_key=..., bias_key=...)`

2. Solver Core
   - `reg_solver_core(solver, cfg, key=...)`

3. Search Layer (Adapter + L3)
   - `reg_search(solver, adapter)`

4. L3 Flow Plugins
   - `reg_flow(solver, cfg, keys=[...])`

5. L0 Acceleration
   - `reg_acceleration(solver, cfg, keys=[...])`

6. L4 Evaluation Runtime
   - `reg_evaluation(solver, cfg, keys=[...])`

7. Observability Profile
   - `reg_observability(solver, cfg, run_id, key=...)`

8. Ops Plugins (L1/L2)
   - `reg_ops(solver, cfg, keys=[...])`

9. Checkpoint (Optional)
   - `reg_checkpoint(solver, cfg, key=...)`

## Catalog Kind -> Zone Mapping
- `problem` -> Problem zone
- `pipeline` / `representation` -> Pipeline zone
- `bias` -> Bias zone
- `adapter` / `solver` -> Search Layer zone
- `plugin`:
  - observability/runtime plugin -> Observability zone
  - domain/business plugin -> Project Plugins zone

## Folder Placement Notes
- L4 evaluation registry lives in `evaluation/config.py` (problem-owned assets can live under `problem/evaluation/`)
- L1/L2 ops/observability + checkpoint registries live in `plugins/config.py`
- problem-local data lives under `problem/data/`

## Example: VNS Wiring (Registry + Selection)
Select the adapter in `build_solver.py`:
- `primary_adapter = "vns"`
- Required context behavior: mutator reads `mutation_sigma` / `vns_k`
- Adapter instance is resolved from registry in `adapter/config.py`

## Selection Checklist (before wiring)
For each chosen component, answer in one line:
- Why this component fits this problem
- Which alternatives were rejected and why
- Expected input/output shape
- Required context keys and side effects

## Validation Checklist (after wiring)
- Run `python -m nsgablack project doctor --path . --build --strict`
- Ensure no layer misuse (wrong-zone logic)
- Ensure shape/context contract is explainable by file and line

## Guardrails
- Keep `build_solver(run_id=None)` as the only assembly entrypoint.
- Prefer `solver.add_plugin(...)` only in project plugin zone.
- Do not put repair logic into problem/bias.
- Do not put business semantics into plugins.
