"""Evolution population handoff preserves evaluated identity from initialization."""
import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, Feedback, UnknownState

from nsgablack.adapters import (NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, DifferentialEvolutionAdapter,
    MOEADAdapter, RoleAdapter, EliteRetentionAdapter, StrategyChainAdapter, SerialPhaseSpec, CompositeAdapter)
from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.core.semantic_extension import SolverSemanticExtension
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.core.state.pool_retention import PoolRetentionPolicy
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-20., 20.)])
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        x = float(np.asarray(candidate)[0])
        return [x * x, (x - 1.) ** 2]


class Operator:
    def __init__(self):
        self.serial = 0

    def initialize(self, problem, context):
        self.serial += 1
        return UnknownState(values=[4.], metadata={"seed": self.serial})

    def mutate(self, candidate, context):
        return np.asarray(candidate) - .5


def make(kind=NSGA2Adapter, *, adapter=None, setup=True):
    operator = Operator()
    solver = EvolutionSolver(Problem(), adapter=adapter or kind(population_size=4),
        pop_size=4, max_generations=2, random_seed=71,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    if setup:
        solver.setup()
    return solver


def receipt_feedback(solver, refs):
    raw_f, raw_v = solver.solution_pool.read_raw_feedback(refs)
    return OptimizationFeedbackBatch.from_arrays(raw_f, raw_v)


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, DifferentialEvolutionAdapter])
def test_initialization_publishes_exact_members_before_any_generation(kind):
    solver = make(kind)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1, retained_publications=1))
    progress = solver.export_run_progress_state()
    solver.initialize_population()
    refs = solver.adapter.get_solution_pool_roots(solver)
    assert len(refs) == len(set(refs)) == 4
    batch = solver.solution_pool.read(refs)
    assert [state.metadata["seed"] for state in batch.semantic_states] == [1, 2, 3, 4]
    assert solver.get_candidate_population_batch().candidate_tokens == batch.candidate_tokens
    assert solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, solver.adapter)) == (
        "/".join((*adapter_path(solver.adapter, solver.adapter), "population")),)
    assert solver.solution_pool.subpool_refs("/".join((solver.adapter.name, "population"))) == refs
    np.testing.assert_array_equal(batch.numeric_matrix, solver.adapter.population)
    assert solver.generation == 0
    after = solver.export_run_progress_state()
    assert after["steps_completed"] == progress["steps_completed"] == 0
    assert after["attempts_completed"] == progress["attempts_completed"] == 0
    assert solver.problem.calls == solver.evaluation_count == 4
    assert solver.step().committed
    assert len(solver.adapter.get_solution_pool_roots(solver)) == 4


def test_initialization_does_not_invoke_step_extensions():
    class Extension(SolverSemanticExtension):
        def before_step(self, solver):
            raise AssertionError("initialization is not a step")
        def after_step_committed(self, solver, outcome):
            raise AssertionError("initialization is not a committed generation")
    solver = make()
    solver.register_semantic_extension(Extension())
    solver.initialize_population()
    assert solver.generation == 0 and solver.evaluation_count == 4


def test_partial_initial_acceptance_preserves_selected_nonprefix_identities():
    class Select:
        policy_id = "initial_even"
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1, 3))
    solver = make()
    solver.set_evaluation_acceptance_policy(Select())
    solver.initialize_population()
    refs = solver.adapter.get_solution_pool_roots(solver)
    assert [s.metadata["seed"] for s in solver.solution_pool.read(refs).semantic_states] == [2, 4]
    assert len(solver.population) == 2 and solver.evaluation_count == 4
    assert solver.get_candidate_population_batch().candidate_tokens == tuple(r.candidate_token for r in refs)


def test_initial_budget_truncation_and_rejection_do_not_create_ghost_members():
    from nsgablack.core.control_plane import BudgetController
    solver = make()
    solver.register_controller(BudgetController(max_evaluations=2))
    solver.initialize_population()
    assert len(solver.adapter.get_solution_pool_roots(solver)) == 2
    assert solver.evaluation_count == 2 and solver.generation == 0
    class Reject:
        policy_id = "reject_initial"
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())
    rejected = make()
    rejected.set_evaluation_acceptance_policy(Reject())
    rejected.initialize_population()
    assert rejected.population is None
    assert rejected.adapter.get_solution_pool_roots(rejected) == ()
    assert rejected.solution_pool.select(stage="accepted") == ()
    assert rejected.evaluation_count == 4 and rejected.generation == 0


def test_failed_initial_publication_rolls_back_members_and_view_but_keeps_cost(monkeypatch):
    solver = make()
    original = solver._finish_population_publication
    before = copy.deepcopy(solver.adapter.get_state())
    def fail(**kwargs):
        assert len(solver.adapter.get_solution_pool_roots(solver)) == 4
        raise RuntimeError("after identity handoff")
    monkeypatch.setattr(solver, "_finish_population_publication", fail)
    with pytest.raises(RuntimeError, match="after identity handoff"):
        solver.initialize_population()
    assert solver.adapter.get_state() == before and solver.population is None
    assert solver.solution_pool.select(stage="accepted") == ()
    assert solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, solver.adapter)) == ()
    assert solver.evaluation_count == 4
    monkeypatch.setattr(solver, "_finish_population_publication", original)
    solver.initialize_population()
    assert len(solver.adapter.get_solution_pool_roots(solver)) == 4 and solver.evaluation_count == 8


@pytest.mark.parametrize("kind", [NSGA2Adapter, DifferentialEvolutionAdapter])
@pytest.mark.parametrize("partial", [False, True])
def test_initial_checkpoint_restores_exact_members_and_sync_does_not_reinitialize(kind, partial):
    source = make(kind)
    if partial:
        class Select:
            policy_id = "checkpoint_initial_subset"
            def select(self, candidates, feedback, context):
                return BatchDisposition(len(candidates.semantic_states), (1, 3))
        source.set_evaluation_acceptance_policy(Select())
    source.initialize_population()
    refs = source.adapter.get_solution_pool_roots(source)
    target = make(kind, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="exact-initial-population")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    def unexpected(*args, **kwargs):
        raise AssertionError("sync must not replay member initialization")
    initialize = target.adapter.algorithm_unit.initialize_population
    target.adapter.algorithm_unit.initialize_population = unexpected
    target._sync_adapter_from_solver()
    assert target.adapter.get_solution_pool_roots(target) == refs
    assert target.problem.calls == 0 and target.generation == 0
    assert [s.metadata["seed"] for s in target.solution_pool.read(refs).semantic_states] == ([2, 4] if partial else [1, 2, 3, 4])
    target.adapter.algorithm_unit.initialize_population = initialize
    assert target.step().committed


def test_identified_environmental_selection_retains_versions_and_raw_evidence():
    solver = make()
    solver.initialize_population()
    refs = solver.adapter.get_solution_pool_roots(solver)
    batch = solver.solution_pool.read(refs)
    raw_f, raw_v = solver.solution_pool.read_raw_feedback(refs)
    selected_f = np.array([[9., 9.], [0., 0.], [5., 5.], [1., 1.]])
    feedback = OptimizationFeedbackBatch.from_arrays(selected_f, np.zeros(4), items=tuple(
        Feedback(objectives=selected_f[i], info={"raw_evaluation": {
            "objectives": raw_f[i].tolist(), "constraint_violation": float(raw_v[i])}}) for i in range(4)))
    records_before = solver.solution_pool.record_count
    solver.pop_size = 2
    solver.environmental_selection(batch, feedback, solution_refs=refs)
    assert solver.adapter.get_solution_pool_roots(solver) == (refs[1], refs[3])
    assert [s.metadata["seed"] for s in solver.get_candidate_population_batch().semantic_states] == [2, 4]
    assert solver.evaluation_count == solver.problem.calls == 4
    assert solver.solution_pool.record_count == records_before
    np.testing.assert_array_equal(solver.solution_pool.read_raw_feedback((refs[1], refs[3]))[0], raw_f[[1, 3]])
    np.testing.assert_array_equal(solver.objectives, selected_f[[1, 3]])


def test_environmental_array_import_requires_explicit_new_evaluation_assertion():
    solver = make()
    solver.initialize_population()
    before = solver.adapter.get_solution_pool_roots(solver)
    x = solver.population.copy()
    f, v = solver.objectives.copy(), solver.constraint_violations.copy()
    with pytest.raises(ValueError, match="external_evaluation=True"):
        solver.environmental_selection(x, f, v)
    assert solver.adapter.get_solution_pool_roots(solver) == before
    solver.environmental_selection(x, f, v, external_evaluation=True)
    after = solver.adapter.get_solution_pool_roots(solver)
    assert set(r.candidate_token for r in before).isdisjoint(r.candidate_token for r in after)
    assert all(p["source_kind"] == "external_evaluation" for p in solver.solution_pool.read_provenance(after))
    assert solver.evaluation_count == 4


@pytest.mark.parametrize("invalid", ["raw", "metadata", "scope", "length", "provenance"])
def test_complete_delivery_rejects_mismatched_receipts_before_mutation(invalid):
    solver = make()
    solver.initialize_population()
    refs = solver.adapter.get_solution_pool_roots(solver)
    batch = solver.solution_pool.read(refs)
    feedback = receipt_feedback(solver, refs)
    provenance = tuple(CandidateProvenance.from_dict(p) for p in solver.solution_pool.read_provenance(refs))
    if invalid == "raw":
        feedback = OptimizationFeedbackBatch.from_arrays(feedback.objectives + 1., feedback.violations)
    elif invalid == "metadata":
        batch = CandidateBatch.from_candidates([s.with_meta(seed=999) for s in batch.semantic_states],
                                               candidate_tokens=batch.candidate_tokens)
    elif invalid == "scope":
        other = make()
        other.initialize_population()
        refs = other.adapter.get_solution_pool_roots(other)
    elif invalid == "length":
        refs = refs[:1]
    else:
        provenance = tuple(CandidateProvenance.from_dict({**p.as_dict(), "source_kind": "wrong-origin"}) for p in provenance)
    before = copy.deepcopy(solver.adapter.get_state())
    with pytest.raises((ValueError, KeyError)):
        solver.adapter.set_population_state(solver, batch, feedback, solution_refs=refs, provenance=provenance)
    assert solver.adapter.get_state() == before


def test_failed_environmental_selection_restores_prior_population_and_view(monkeypatch):
    solver = make()
    solver.initialize_population()
    refs = solver.adapter.get_solution_pool_roots(solver)
    name, = solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, solver.adapter))
    view = solver.solution_pool.subpool_descriptor(name)
    state = copy.deepcopy(solver.adapter.get_state())
    batch = solver.get_candidate_population_batch()
    def fail(**kwargs):
        assert solver.adapter.get_solution_pool_roots(solver) != refs
        raise RuntimeError("failed external import")
    monkeypatch.setattr(solver, "_finish_population_publication", fail)
    with pytest.raises(RuntimeError, match="failed external import"):
        solver.environmental_selection(np.array([[0.], [1.]]), np.array([[0., 1.], [1., 0.]]),
                                       np.zeros(2), external_evaluation=True)
    assert solver.adapter.get_state() == state
    assert solver.adapter.get_solution_pool_roots(solver) == refs
    assert solver.solution_pool.subpool_descriptor(name) == view
    assert solver.get_candidate_population_batch().candidate_tokens == batch.candidate_tokens
    assert solver.evaluation_count == 4


@pytest.mark.parametrize("feedback,violations", [(np.ones((2, 2)), np.zeros(2)), (np.ones((4, 2)), np.zeros(2))])
def test_external_import_rejects_misaligned_rows_before_mutation(feedback, violations):
    solver = make()
    solver.initialize_population()
    refs = solver.adapter.get_solution_pool_roots(solver)
    with pytest.raises(ValueError):
        solver.environmental_selection(np.ones((4, 1)), feedback, violations, external_evaluation=True)
    assert solver.adapter.get_solution_pool_roots(solver) == refs


def test_nonpopulation_adapter_keeps_solver_batch_without_fake_population_roots():
    class Trajectory(AlgorithmAdapter):
        def propose(self, control, context):
            return [np.array([1.])]
        def update(self, control, candidates, feedback, context):
            pass
    solver = make(adapter=Trajectory("trajectory"))
    solver.initialize_population()
    assert len(solver.get_candidate_population_batch().semantic_states) == 4
    assert solver.population_authority_mode == "step_batch"
    assert solver.adapter.get_solution_pool_roots(solver) is None
    assert solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, solver.adapter)) == ()
    solver._sync_adapter_from_solver()
    assert solver.step().committed


def test_evolution_initial_population_is_immediately_consumable_by_bounded_vns():
    from nsgablack.adapters import VNSAdapter, PoolTaskSpec, subpools
    from nsgablack.adapters.pool_tasks import PoolTaskAdapter
    from nsgablack.adapters.strategy_task import StrategyTask

    class RefinedPopulation(NSGA2Adapter):
        """A single population owner explicitly delegates a bounded search."""
        def __init__(self):
            super().__init__(population_size=4)
            self.worker = PoolTaskAdapter(VNSAdapter(name="vns", batch_size=1),
                PoolTaskSpec(subpools.all(self), count="all", steps=2, output="refined", shuffle=False),
                role="refine")

        def step_transaction_children(self):
            return (self.worker,)

        def setup(self, control):
            super().setup(control)
            self.worker.setup(control)

        def propose(self, control, context):
            self.task_context = StrategyTask(owner_path=(self.name, "refine"), role="refine",
                unit_id=0, role_index=0, adapter_name=self.worker.name, step=control.generation,
                phase="refine", phase_step=0, budget=4).bind(context)
            return self.worker.propose(control, self.task_context)

        def _proposal_contexts(self, count, context):
            return self.worker.get_proposal_contexts(count, self.task_context)

        def proposal_repair_children(self, repair, context):
            return ((self.worker, repair, self.task_context),)

        def on_proposal_repair(self, control, repair, context):
            self._forward_proposal_repair(control, repair, context)

        def on_proposal_disposition(self, control, disposition, context):
            self.worker.on_proposal_disposition(control, disposition, self.task_context)

        def update(self, control, candidates, feedback, context):
            self.worker.update(control, candidates, feedback, self.task_context)

    adapter = RefinedPopulation()
    solver = make(adapter=adapter)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1, retained_publications=1))
    solver.initialize_population()
    original = adapter.get_solution_pool_roots(solver)
    before = solver.evaluation_count
    for _ in range(8):
        assert solver.step().committed
    assert adapter.worker.task_status["status"] == "done"
    creator = adapter_path(adapter, adapter.worker.inner)
    names = solver.solution_pool.subpools_created_by(creator)
    assert len(names) == 4
    final_refs = tuple(solver.solution_pool.subpool_refs(name)[0] for name in names)
    final = solver.solution_pool.read(final_refs)
    np.testing.assert_array_equal(final.numeric_matrix, np.full((4, 1), 3.5))
    assert solver.evaluation_count - before == 8
    assert adapter.get_solution_pool_roots(solver) == original
    assert all(solver.solution_pool.subpool_metadata(name)["parent"]["name"] == "nsga2/population" for name in names)


def wrapped_population(kind):
    leaf = NSGA2Adapter(population_size=4, offspring_size=4)
    if kind == "role":
        return RoleAdapter("search", leaf), leaf
    if kind == "elite":
        return EliteRetentionAdapter(leaf), leaf
    if kind == "chain":
        return StrategyChainAdapter([SerialPhaseSpec("search", leaf)]), leaf
    if kind == "composite":
        return CompositeAdapter([leaf]), leaf
    if kind == "nested":
        return RoleAdapter("search", EliteRetentionAdapter(CompositeAdapter([
            StrategyChainAdapter([SerialPhaseSpec("search", leaf)])]))), leaf
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["role", "elite", "chain", "composite", "nested"])
def test_transparent_population_delivery_and_checkpoint_keep_ordered_refs_separate_from_roots(kind):
    wrapper, leaf = wrapped_population(kind)
    source = make(adapter=wrapper)
    source.initialize_population()
    refs = leaf.get_population_solution_refs(source)
    assert wrapper.get_population_solution_refs(source) == refs
    assert wrapper.get_solution_pool_roots(source) == ()
    source._sync_adapter_from_solver()
    assert source.step().committed
    refs = leaf.get_population_solution_refs(source)
    assert tuple(r.candidate_token for r in refs) == wrapper.get_population_candidate_tokens()
    restored, restored_leaf = wrapped_population(kind)
    target = make(adapter=restored, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="wrapped-population")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    target._sync_adapter_from_solver()
    assert restored.get_population_solution_refs(target) == restored_leaf.get_population_solution_refs(target) == refs
    assert target.problem.calls == 0
    assert target.step().committed


def test_evolution_moead_initialization_creates_directions_and_preserves_restored_ideal():
    source = make(MOEADAdapter)
    source.initialize_population()
    refs = source.adapter.get_population_solution_refs(source)
    assert source.adapter.pool_views_ready and len(refs) == 4
    names = source.solution_pool.subpools_created_by(adapter_path(source.adapter, source.adapter))
    assert len(names) == 4
    assert tuple(source.solution_pool.subpool_refs(name)[0] for name in names) == refs
    assert source.step().committed
    current_refs = source.adapter.get_population_solution_refs(source)
    assert len(set(current_refs)) < len(current_refs)
    assert tuple(ref.candidate_token for ref in current_refs) == source.adapter.get_population_candidate_tokens()
    # Historical ideal may no longer occur in current rows. Identity sync must
    # not rebuild this algorithm state from today's population minimum.
    source.adapter.ideal = np.array([-1., -2.])
    target = make(MOEADAdapter, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="moead-evolution")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    restored_state = copy.deepcopy(target.adapter.get_state())
    target._sync_adapter_from_solver()
    np.testing.assert_array_equal(target.adapter.ideal, [-1., -2.])
    assert target.adapter.get_state() == restored_state
    assert target.adapter.get_population_solution_refs(target) == source.adapter.get_population_solution_refs(source)
    assert target.step().committed


def test_de_population_sync_preserves_restored_pending_target_coordinates():
    source = make(DifferentialEvolutionAdapter)
    source.initialize_population()
    assert source.step().committed
    assert source.adapter._last_target_indices
    target = make(DifferentialEvolutionAdapter, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="de-pending-targets")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    restored_state = copy.deepcopy(target.adapter.get_state())
    target._sync_adapter_from_solver()
    assert target.adapter.get_state() == restored_state
    assert target.step().committed


@pytest.mark.parametrize("wrapper", [lambda a: a, lambda a: RoleAdapter("unsupported", a),
    lambda a: CompositeAdapter([a]), lambda a: StrategyChainAdapter([SerialPhaseSpec("unsupported", a)])])
def test_unsupported_population_delivery_fails_during_setup_without_evaluation(wrapper):
    class Unsupported(AlgorithmAdapter):
        population_state_mode = "single"
        def propose(self, control, context):
            return []
        def update(self, control, candidates, feedback, context):
            pass
    solver = make(adapter=wrapper(Unsupported("unsupported")), setup=False)
    with pytest.raises(TypeError, match="complete population identity delivery"):
        solver.setup()
    assert solver.evaluation_count == solver.problem.calls == 0


@pytest.mark.parametrize("race", [False, True])
def test_pool_initialization_settles_original_intake_after_budget_and_nonprefix_acceptance(race, monkeypatch):
    from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
    from nsgablack.core.control_plane import BudgetController, EvaluationBudgetExceeded
    solver = make()
    seeds = solver.store_solutions(CandidateBatch.from_candidates(
        [UnknownState(values=[float(i)], metadata={"source": i}) for i in range(4)],
        candidate_tokens=tuple(f"source:{i}" for i in range(4))))
    key = solver.solution_pool.bind_input(seeds)
    class Select:
        policy_id = "pool_initial_partial"
        def select(self, candidates, feedback, context):
            assert len(candidates.semantic_states) == 2
            return BatchDisposition(2, (1,))
    solver.set_evaluation_acceptance_policy(Select())
    if race:
        evaluate = solver.evaluate_population
        lost = [False]
        def evaluate_after_race(population):
            if not lost[0]:
                lost[0] = True
                solver.register_controller(BudgetController(max_evaluations=2))
                raise EvaluationBudgetExceeded("another case reserved the remaining budget")
            return evaluate(population)
        monkeypatch.setattr(solver, "evaluate_population", evaluate_after_race)
    else:
        solver.register_controller(BudgetController(max_evaluations=2))
    solver.initialize_population(context={KEY_SOLUTION_INPUT_REF: key})
    assert solver.solution_pool.input_remaining(key) == 3
    assert solver.solution_pool.read(solver.adapter.get_population_solution_refs(solver)).semantic_states[0].metadata["source"] == 1
    assert solver.evaluation_count == 2
    target = make(setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(solver)
    reader.attach(target)
    payload = writer._build_payload(solver=solver, reason="partial-pool-input")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert target.solution_pool.input_remaining(key) == 3
    assert target.solution_pool.take_inputs(key, 3) == (seeds[0], seeds[2], seeds[3])


def test_rejected_and_failed_pool_initialization_restore_entire_input(monkeypatch):
    from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
    solver = make()
    seeds = solver.store_solutions(CandidateBatch.from_candidates([[1.], [2.], [3.], [4.]],
        candidate_tokens=("a", "b", "c", "d")))
    key = solver.solution_pool.bind_input(seeds)
    class Reject:
        policy_id = "no_initial_pool_members"
        def select(self, candidates, feedback, context):
            return BatchDisposition(4, ())
    solver.set_evaluation_acceptance_policy(Reject())
    solver.initialize_population(context={KEY_SOLUTION_INPUT_REF: key})
    assert solver.solution_pool.input_remaining(key) == 4
    solver.set_evaluation_acceptance_policy(None)
    def fail(**kwargs):
        raise RuntimeError("publication failed after settling input")
    monkeypatch.setattr(solver, "_finish_population_publication", fail)
    with pytest.raises(RuntimeError, match="after settling"):
        solver.initialize_population(context={KEY_SOLUTION_INPUT_REF: key})
    assert solver.solution_pool.take_inputs(key, 4) == seeds


@pytest.mark.parametrize("pooled", [False, True])
def test_evolution_initialization_repairs_each_seed_once_without_changing_proposal_token(pooled, monkeypatch):
    from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
    class Repair:
        def __init__(self):
            self.calls = 0
        def repair(self, candidate, context):
            self.calls += 1
            if isinstance(candidate, UnknownState):
                return candidate.with_values(np.clip(candidate.as_array(), -2., 2.))
            return np.clip(np.asarray(candidate), -2., 2.)
    repair, operator = Repair(), Operator()
    solver = EvolutionSolver(Problem(), pop_size=4, random_seed=71,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator, repair=repair))
    solver.setup()
    context = None
    if pooled:
        seeds = solver.store_solutions(CandidateBatch.from_candidates(
            [UnknownState([i + 30.], {"source": i}) for i in range(4)],
            candidate_tokens=tuple(f"source:{i}" for i in range(4))))
        context = {KEY_SOLUTION_INPUT_REF: solver.solution_pool.bind_input(seeds)}
        original = solver.repair_candidate
        def preserve_token(candidate, context):
            token = solver.candidate_provenance_for(candidate).candidate_token
            repaired = original(candidate, context)
            assert solver.candidate_provenance_for(repaired).candidate_token == token
            return repaired
        monkeypatch.setattr(solver, "repair_candidate", preserve_token)
    solver.initialize_population(context=context)
    assert repair.calls == solver.problem.calls == 4
    refs = solver.adapter.get_population_solution_refs(solver)
    np.testing.assert_array_equal(solver.solution_pool.read(refs).numeric_matrix, np.full((4, 1), 2.))
    if pooled:
        assert [s.metadata["source"] for s in solver.solution_pool.read(refs).semantic_states] == [0, 1, 2, 3]
        assert [p["parent_token"] for p in solver.solution_pool.read_provenance(refs)] == [s.candidate_token for s in seeds]


def test_pool_initialization_repair_rejects_invalid_metadata_before_evaluation():
    from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
    class InvalidMetadataRepair:
        def repair(self, candidate, context):
            return UnknownState([2.], {"not_portable": object()})
    solver = EvolutionSolver(Problem(), pop_size=4,
        representation_pipeline=RepresentationPipeline(repair=InvalidMetadataRepair()))
    solver.setup()
    seeds = solver.store_solutions(CandidateBatch.from_candidates(
        [UnknownState([30.], {"source": i}) for i in range(4)],
        candidate_tokens=tuple(f"source:{i}" for i in range(4))))
    key = solver.solution_pool.bind_input(seeds)
    with pytest.raises((TypeError, ValueError)):
        solver.initialize_population(context={KEY_SOLUTION_INPUT_REF: key})
    assert solver.evaluation_count == solver.problem.calls == 0
    assert solver.population is None and solver.adapter.get_population_solution_refs(solver) == ()
    assert solver.solution_pool.input_remaining(key) == 4
    assert [s.metadata["source"] for s in solver.solution_pool.read(seeds).semantic_states] == [0, 1, 2, 3]
