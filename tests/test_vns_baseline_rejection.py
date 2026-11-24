"""A real admission rejection must not trap VNS on an unscored baseline."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch
from nsgablack.adapters import (
    MultiStrategyConfig, PoolTaskSpec, RoleSpec, StrategyRouterAdapter, VNSAdapter,
)
from nsgablack.adapters.proposal_repair import ProposalRepair
from nsgablack.context_keys import KEY_METADATA
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.evaluation_acceptance import FeasibleEvaluationAcceptance
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.representation import (
    ClipRepair, ContextGaussianMutation, RepresentationPipeline, UniformInitializer,
)
from nsgablack.representation.base import RepresentationComponentContract
from nsgablack.units.contracts import candidate_array


class NonnegativeProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=['minimize'], bounds=[(-10., 10.)])
        self.calls = []

    def evaluate(self, candidate):
        value = float(candidate[0])
        self.calls.append(value)
        return [value * value], float(value < 0)


class SequenceInitializer(RepresentationComponentContract):
    def __init__(self, values=(-1., 2.)):
        self.values = tuple(values)
        self.index = 0

    def initialize(self, problem, context):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return np.asarray([value])

    def checkpoint_identity(self):
        return {'schema': 'test.vns_baseline_sequence/v1', 'values': self.values}

    def get_state(self):
        return {'index': self.index}

    def set_state(self, state):
        self.index = state['index']


def make_solver(values=(-1., 2.), *, adapter_type=VNSAdapter, repair=None):
    initializer = SequenceInitializer(values)
    adapter = adapter_type(initializer=initializer, batch_size=1, restart_on_stagnation=False)
    solver = ComposableSolver(NonnegativeProblem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(
            mutator=ContextGaussianMutation(), repair=repair or ClipRepair(low=-10., high=10.)),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_random_seed(17)
    return solver, adapter, initializer


def repair_evidence(adapter, candidates):
    token = adapter._pending_baseline_token or 'baseline-token'
    batch = CandidateBatch.from_candidates(candidates, candidate_tokens=(token,))
    adapter.on_proposal_repair(None, ProposalRepair(1, (0,), batch, batch), {})


def initial_refs(control, context):
    return control.solution_pool.select(stage='initial')


def test_rejected_generated_seed_reinitializes_on_next_attempt_without_ghost_step():
    solver, adapter, initializer = make_solver()
    solver.max_steps = 1
    output = solver.run()
    assert solver.problem.calls == [-1., 2.]
    assert initializer.index == 2
    assert solver.generation == solver.run_session.steps == 1
    assert solver.run_session.attempts == 2
    assert solver.evaluation_count == 2
    assert output['termination_reason'] == 'step_limit'
    np.testing.assert_array_equal(adapter.current_x, [2.])
    assert adapter.current_score == 4.


@pytest.mark.parametrize('reason', ['evaluation_budget_allowance', 'sibling_cancelled'])
def test_zero_disposition_without_fresh_evaluation_keeps_baseline(reason):
    solver, adapter, initializer = make_solver()
    solver.setup()
    context = solver.build_context()
    candidates = adapter.propose(solver, context)
    repair_evidence(adapter, candidates)
    unit_id = adapter.current_unit.unit_id
    adapter.on_proposal_disposition(solver,
        BatchDisposition.prefix(proposed_count=1, accepted_count=0, reason=reason), context)
    assert initializer.index == 1 and solver.evaluation_count == 0 and solver.problem.calls == []
    assert adapter.current_unit.unit_id == unit_id and adapter.current_score is None
    np.testing.assert_array_equal(adapter.current_x, [-1.])


def test_exhausted_budget_does_not_initialize_or_evaluate():
    solver, adapter, initializer = make_solver()
    solver.register_controller(BudgetController(max_evaluations=0))
    solver.max_steps = 1
    solver.run()
    assert initializer.index == 0 and solver.problem.calls == [] and solver.evaluation_count == 0
    assert adapter.current_unit is None and solver.run_session.steps == 0


def test_stale_evaluation_context_cannot_reinitialize_an_unevaluated_new_seed():
    solver, adapter, initializer = make_solver((1., -1.))
    solver.setup()
    assert solver.step().committed
    previous = solver.get_last_evaluation_event()
    adapter.restart_search(solver, {})
    candidates = adapter.propose(solver, solver.build_context())
    repair_evidence(adapter, candidates)
    context = {KEY_METADATA: {'evaluation_event': {'event_id': previous.event_id}}}
    adapter.on_proposal_disposition(solver,
        BatchDisposition.prefix(proposed_count=1, accepted_count=0, reason='sibling_cancelled'), context)
    assert solver.problem.calls == [1.] and solver.evaluation_count == 1 and initializer.index == 2
    np.testing.assert_array_equal(adapter.current_x, [-1.])


def test_composite_only_reinitializes_the_baseline_that_was_really_evaluated():
    first = VNSAdapter(initializer=SequenceInitializer((-1., 2.)), name='first')
    second = VNSAdapter(initializer=SequenceInitializer((-2., 3.)), name='second')
    router = StrategyRouterAdapter(roles=[RoleSpec('a', lambda _: first), RoleSpec('b', lambda _: second)],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False))
    solver = ComposableSolver(NonnegativeProblem(), adapter=router,
        representation_pipeline=RepresentationPipeline(mutator=ContextGaussianMutation(),
            repair=ClipRepair(low=-10., high=10.)),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.register_controller(BudgetController(max_evaluations=1))
    solver.setup()
    outcome = solver.step()
    assert outcome.status == 'rejected' and outcome.evaluations == 1
    assert solver.problem.calls == [-1.]
    assert first.current_unit is None
    np.testing.assert_array_equal(second.current_x, [-2.])
    assert second.current_score is None


def test_frozen_pool_task_seed_is_retried_without_random_initialization():
    initializer = SequenceInitializer((5.,))
    inner = VNSAdapter(initializer=initializer, name='refiner')
    router = StrategyRouterAdapter(roles=[RoleSpec('refine', lambda _: inner,
        pool_task=PoolTaskSpec(select=initial_refs, count=1, steps=1, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    solver = ComposableSolver(NonnegativeProblem(), adapter=router,
        representation_pipeline=RepresentationPipeline(mutator=ContextGaussianMutation(),
            repair=ClipRepair(low=-10., high=10.)),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.setup()
    refs = solver.store_solutions(CandidateBatch.from_candidates([np.array([-1.])],
        candidate_tokens=('frozen-seed',)))
    assert solver.step().status == 'rejected'
    assert solver.evaluation_count == 1 and solver.problem.calls == [-1.]
    assert initializer.index == 0 and solver.generation == 0
    assert solver.solution_pool.select(stage='initial') == refs
    np.testing.assert_array_equal(solver.read_solutions(refs).numeric_matrix, [[-1.]])
    task = router.units[0].adapter
    assert task.task_status['status'] == 'running' and task.task_status['steps'] == 0
    # The policy owner may change admission. The task retries its same frozen
    # source; this toy change is not made in production assembly.
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert initializer.index == 0 and solver.problem.calls == [-1., -1.]
    np.testing.assert_array_equal(inner.current_x, [-1.])
    assert inner.current_score == 1_000_001.


def test_manual_seed_cannot_opt_in_by_forging_initialization_provenance():
    solver, adapter, initializer = make_solver()
    solver.setup()
    adapter.ensure_neighborhood_unit()
    adapter.current_x = np.array([-1.])
    adapter._current_provenance = CandidateProvenance('manual', source_kind='initialization')
    assert adapter._baseline_can_reinitialize is False
    assert solver.step().status == 'rejected'
    assert solver.step().status == 'rejected'
    assert initializer.index == 0 and solver.evaluation_count == 2
    np.testing.assert_array_equal(adapter.current_x, [-1.])


def test_manual_seed_without_provenance_gets_a_token_but_never_random_replacement():
    solver, adapter, initializer = make_solver()
    solver.setup()
    adapter.ensure_neighborhood_unit()
    adapter.current_x = np.array([-1.])
    assert solver.step().status == 'rejected'
    assert initializer.index == 0 and solver.evaluation_count == 1
    np.testing.assert_array_equal(adapter.current_x, [-1.])


def test_checkpoint_preserves_generated_origin_and_old_state_is_conservative():
    solver, adapter, _ = make_solver()
    solver.setup()
    adapter.propose(solver, solver.build_context())
    state = copy.deepcopy(adapter.get_state())
    assert state['baseline_can_reinitialize'] is True
    for legacy in (False, True):
        restored_solver, restored, initializer = make_solver()
        restored_solver.setup()
        saved = copy.deepcopy(state)
        if legacy:
            for name in ('baseline_can_reinitialize', 'baseline_event_id_before', 'pending_baseline_token'):
                saved.pop(name)
        restored.set_state(saved)
        assert restored._baseline_can_reinitialize is (not legacy)
        if legacy:
            assert restored_solver.step().status == 'rejected'
            assert restored_solver.step().status == 'rejected'
            assert initializer.index == 1
            np.testing.assert_array_equal(restored.current_x, [-1.])
        else:
            assert restored_solver.step().status == 'rejected'
            assert restored.current_unit is None and initializer.index == 1
            assert restored_solver.step().committed and initializer.index == 2
            np.testing.assert_array_equal(restored.current_x, [2.])


def test_exception_after_reset_rolls_back_adapter_but_not_consumed_evaluation():
    class RaisingAdapter(VNSAdapter):
        fail = True

        def on_proposal_disposition(self, control, disposition, context):
            super().on_proposal_disposition(control, disposition, context)
            if self.fail and not disposition.accepted_indices and context.get(KEY_METADATA):
                raise RuntimeError('injected after baseline recovery')

    solver, adapter, initializer = make_solver(adapter_type=RaisingAdapter)
    solver.setup()
    with pytest.raises(RuntimeError, match='injected after baseline recovery'):
        solver.step()
    assert solver.problem.calls == [-1.] and solver.evaluation_count == 1
    assert initializer.index == 0 and adapter.current_unit is None
    assert adapter._unit_counter == 0 and adapter._pending_baseline_token is None
    adapter.fail = False
    assert solver.step().status == 'rejected'
    assert solver.step().committed
    assert solver.problem.calls == [-1., -1., 2.] and solver.evaluation_count == 3


def test_repair_changes_do_not_assign_a_rejected_score_to_original_unit():
    class FlipOnce(RepresentationComponentContract):
        def __init__(self):
            self.count = 0

        def repair(self, candidate, context=None):
            self.count += 1
            return np.array([-1.]) if self.count == 1 else np.asarray(candidate).copy()

    solver, adapter, initializer = make_solver((1., 2.), repair=FlipOnce())
    solver.setup()
    assert solver.step().status == 'rejected'
    assert adapter.current_unit is None and adapter.current_score is None and initializer.index == 1
    assert solver.step().committed
    assert solver.problem.calls == [-1., 2.]
    np.testing.assert_array_equal(adapter.current_x, [2.])


def test_invalid_checkpoint_origin_is_rejected_before_state_changes():
    solver, adapter, _ = make_solver()
    solver.setup()
    state = adapter.get_state()
    state['baseline_can_reinitialize'] = 'yes'
    with pytest.raises(ValueError, match='origin must be boolean'):
        adapter.set_state(state)
    assert adapter.current_unit is None


class ConstantProblem(NonnegativeProblem):
    def evaluate(self, candidate):
        self.calls.append(float(candidate[0]))
        return [0.], 0.


def constant_solver(initializer):
    adapter = VNSAdapter(initializer=initializer, batch_size=1, k_max=1,
                         restart_on_stagnation=True)
    solver = ComposableSolver(ConstantProblem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=ContextGaussianMutation(),
            repair=ClipRepair(low=-10., high=10.)),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_random_seed(17)
    solver.setup()
    return solver, adapter


def test_pool_task_completing_on_stagnation_returns_evaluated_point_not_restart_draft():
    initializer = SequenceInitializer((9.,))
    inner = VNSAdapter(initializer=initializer, batch_size=1, k_max=1,
                       restart_on_stagnation=True)
    router = StrategyRouterAdapter(roles=[RoleSpec('refine', lambda _: inner,
        pool_task=PoolTaskSpec(select=initial_refs, count=1, steps=3, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    solver = ComposableSolver(ConstantProblem(), adapter=router,
        representation_pipeline=RepresentationPipeline(mutator=ContextGaussianMutation(),
            repair=ClipRepair(low=-10., high=10.)),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.setup()
    solver.store_solutions(CandidateBatch.from_candidates([np.array([2.])],
        candidate_tokens=('constant-seed',)))
    for _ in range(3):
        assert solver.step().committed
    task = router.units[0].adapter
    assert task.task_status['status'] == 'done' and task.task_status['steps'] == 3
    result = task.get_pool_task_results(solver)
    assert len(result) == 1 and result == inner.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions(result).numeric_matrix, [[2.]])
    assert inner.current_score == 0. and inner._restart_pending
    assert initializer.index == 0 and solver.evaluation_count == len(solver.problem.calls) == 3


def test_pending_restart_rng_replays_after_step_snapshot_without_double_initialization():
    solver, adapter = constant_solver(UniformInitializer(low=1., high=3.))
    for _ in range(3):
        assert solver.step().committed
    assert adapter._restart_pending and adapter.current_score == 0.
    selected = adapter.get_pool_refinement_results(solver)
    assert selected
    state = adapter.snapshot_step_state()
    first = adapter.propose(solver, solver.build_context())
    assert not adapter._restart_pending and adapter.current_score is None
    expected = candidate_array(first[0]).copy()
    operator_state = adapter.get_bound_initializer().get_state()
    adapter.restore_step_state(state)
    assert adapter._restart_pending and adapter.get_pool_refinement_results(solver) == selected
    second = adapter.propose(solver, solver.build_context())
    np.testing.assert_array_equal(candidate_array(second[0]), expected)
    assert adapter.get_bound_initializer().get_state() == operator_state
    assert solver.evaluation_count == 3  # Propose/restore never evaluate the new point.


def test_pending_restart_checkpoint_initializes_once_on_next_proposal():
    solver, adapter = constant_solver(SequenceInitializer((1., 5.)))
    for _ in range(3):
        assert solver.step().committed
    assert adapter.get_bound_initializer().index == 1
    saved = copy.deepcopy(adapter.get_state())
    restored_solver, restored = constant_solver(SequenceInitializer((1., 5.)))
    restored.set_state(saved)
    assert restored._restart_pending and restored.current_score == 0.
    assert restored_solver.step().committed
    assert restored_solver.problem.calls == [5.]
    assert restored.get_bound_initializer().index == 2 and not restored._restart_pending
    np.testing.assert_array_equal(restored.current_x, [5.])


def unchanged_change(request, *, rng):
    return request.candidate.copy()


class FirstSelector:
    stateless = True

    def checkpoint_identity(self):
        return {'schema': 'test.first_vns_selector/v1'}

    def select(self, request, *, rng):
        return (0,)


def test_rejected_restart_baseline_keeps_previously_evaluated_selector_result():
    initializer = SequenceInitializer((1., -1., 2.))
    adapter = VNSAdapter(initializer=initializer, selector=FirstSelector(),
        change=unchanged_change, batch_size=1, k_max=1, restart_on_stagnation=True)
    solver = ComposableSolver(NonnegativeProblem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(low=-10., high=10.)),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.setup()
    for _ in range(3):
        assert solver.step().committed
    selected = adapter.get_pool_refinement_results(solver)
    assert selected and adapter._restart_pending
    assert solver.step().status == 'rejected'  # The new internally generated point is -1.
    assert adapter.current_unit is None and adapter.current_score is None
    assert adapter.get_pool_refinement_results(solver) == selected
    assert solver.step().committed
    assert adapter.get_pool_refinement_results(solver) == selected
    np.testing.assert_array_equal(solver.read_solutions(selected).numeric_matrix, [[1.]])
    assert initializer.index == 3 and solver.evaluation_count == 5
