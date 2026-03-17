# L0-L3-L4 Refactor Tasks

## Goal
- Lift L0 acceleration into runtime infrastructure.
- Keep L3 for runtime control (controller + arbiter).
- Keep L4 for semantic evaluation replacement via a single mediation entry.
- Promote inner-solver evaluation to solver-runtime semantics (next phase).

## Phase 1 (started in this commit)
- [x] Add L0 runtime primitives (`AccelerationRegistry`, `AccelerationFacade`).
- [x] Add L3 control primitives (`BaseController`, `ControlDecision`, `ControlArbiter`, `RuntimeController`).
- [x] Add L4 mediation primitives (`EvaluationMediator`, provider protocol, semantic guard).
- [x] Expose new primitives from `core` package.
- [x] Wire solver runtime slots (`gen_start`, `gen_end`) to runtime controller resolution.
- [x] Add mediator-aware evaluation helper path (fallback preserved).

## Phase 2 (next)
- [ ] Convert existing L3 runtime plugins into controller providers (proposal only).
- [ ] Move stop semantics to unified `request_stop()` usage (remove direct `running=False`).
- [ ] Convert L4 plugins to evaluation providers under `EvaluationMediator`.
- [ ] Enforce single owner for evaluation short-circuit (doctor + runtime guard).

## Phase 3 (next)
- [ ] Introduce `NestedSolverEvaluator` contract (`InnerSolveRequest/Result`).
- [ ] Migrate inner-solver plugin path to nested runtime evaluator.
- [ ] Add parent/child contract handshake validation.
- [ ] Add budget propagation + cost accounting contract.

## Test Gate
- [ ] runtime control slot order and stopping arbitration.
- [ ] mediator conflict detection + fallback correctness.
- [ ] evaluation count and bias single-apply invariants.
- [ ] nested solver depth=2 smoke (after Phase 3).
