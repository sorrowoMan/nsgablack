# BUILD_SOLVER_REGISTRATION

Goal: after searching from catalog, you should know exactly where to place each component.

## Zone Pair Rule (must follow)
Each zone keeps two functions together:
- `_extend_<zone>_args(parser)`: CLI flags for this zone.
- `_register_<zone>(...)`: component wiring for this zone.

## Zone Order
1. Problem
   - `_extend_problem_args(parser)`
   - `_register_problem(args)`

2. Pipeline
   - `_extend_pipeline_args(parser)`
   - `_register_pipeline(args)`

3. Bias
   - `_extend_bias_args(parser)`
   - `_register_bias(problem, args)`

4. Solver Core
   - `_extend_solver_args(parser)`
   - `_register_solver(problem, pipeline, bias_module, args)`

5. Observability Plugins
   - `_extend_observability_args(parser)`
   - `_register_observability_plugins(solver, args, run_id)`
   - Recommended: use `--observability-profile` first, then override with `--no-profiler` / `--no-decision-trace` only when needed.

6. Project Plugins
   - `_extend_project_plugin_args(parser)`
   - `_register_project_plugins(solver, args)`

7. Checkpoint (Optional)
   - `_extend_checkpoint_args(parser)`
   - `_register_optional_checkpoint(solver, args)`

## Catalog Kind -> Zone Mapping
- `problem` -> Problem zone
- `pipeline` / `representation` -> Pipeline zone
- `bias` -> Bias zone
- `adapter` / `solver` -> Solver Core zone
- `plugin`:
  - observability/runtime plugin -> Observability zone
  - domain/business plugin -> Project Plugins zone

## Example: VNS Chain Without Wiring Entrypoint
Use direct component wiring instead of `attach_vns(...)`:
- Seed component: `adapter.vns` (`--strategy vns`)
- Required context behavior: mutator reads `mutation_sigma` / `vns_k`
- Auto closure in this scaffold:
  - If pipeline mutator is `GaussianMutation`, it is upgraded to
    `ContextGaussianMutation` in `_register_pipeline(...)` when strategy is `vns`
  - Solver adapter is set to `VNSAdapter(...)` (inline config kwargs) in `_register_solver(...)`

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
- Keep `build_solver(argv=None)` as the only assembly entrypoint.
- Prefer `solver.add_plugin(...)` only in project plugin zone.
- Do not put repair logic into problem/bias.
- Do not put business semantics into plugins.
