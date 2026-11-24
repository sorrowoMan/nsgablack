"""Pool versions survive selection, bootstrap admission, restore and reuse."""
import copy
import json

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch

from nsgablack.adapters import (MOEADAdapter, NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, DifferentialEvolutionAdapter,
    VNSAdapter, SimulatedAnnealingAdapter, PatternSearchAdapter,
    PoolTaskSpec, RoleSpec, StrategyRouterAdapter, MultiStrategyConfig, subpools)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.adapters.population_pool_refs import _semantic_binding_digest, publish_population_view
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline
from dataclasses import replace


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-50., 50.)])
        self.calls = 0

    def evaluate(self, x):
        self.calls += 1
        return [float(x[0] ** 2), float((x[0] - 1.) ** 2)]


class Operator:
    def initialize(self, problem, context):
        return np.array([10.])

    def mutate(self, candidate, context):
        return candidate - 1.


def make(kind=MOEADAdapter, *, capacity=4, intake=4, budget=10, setup=True):
    adapter = kind(population_size=capacity)
    router = StrategyRouterAdapter(name="pool", roles=[RoleSpec("search", adapter,
        pool_task=PoolTaskSpec("seeds", mode="initialize", count=intake, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=budget, adapt_weights=False))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    if setup:
        solver.setup()
        refs = solver.store_solutions(CandidateBatch.from_candidates(
            [[float(i + 2)] for i in range(intake)], candidate_tokens=tuple(f"seed:{i}" for i in range(intake))))
        solver.solution_pool.create_subpool("pool/seeds", refs)
    return solver, adapter


def test_moead_setup_does_not_evaluate_or_publish_candidates():
    adapter = MOEADAdapter(population_size=4)
    solver = ComposableSolver(Problem(), adapter=adapter)
    solver.setup()
    assert solver.problem.calls == solver.evaluation_count == 0
    assert solver.solution_pool.record_count == 0
    assert adapter.pop_X is None and not adapter.pool_views_ready
    assert solver.solution_pool.projection_subpools(adapter_path(adapter, adapter)) == ()
    assert solver.step().committed
    assert solver.problem.calls == 4 and adapter.pool_views_ready


def test_moead_selected_intake_and_partial_admission_bootstrap_without_hidden_evaluation():
    solver, adapter = make()
    class Select:
        policy_id = "bootstrap_subset"
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1, 3))
    solver.set_evaluation_acceptance_policy(Select())
    assert solver.step().committed
    assert solver.problem.calls == 4
    np.testing.assert_array_equal(adapter.pop_X[:, 0], [3., 5.])
    assert not adapter.pool_views_ready
    assert solver.solution_pool.projection_subpools(adapter_path(solver.adapter, adapter)) == ()
    before = adapter.get_solution_pool_roots(solver)
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert solver.problem.calls == 6 and adapter.pool_views_ready
    np.testing.assert_array_equal(adapter.pop_X[:, 0], [3., 5., 2., 4.])
    assert adapter.get_solution_pool_roots(solver)[:2] == before
    assert len(solver.solution_pool.projection_subpools(adapter_path(solver.adapter, adapter))) == 4


def test_moead_intake_smaller_than_capacity_does_not_synthesize_seeds():
    solver, adapter = make(capacity=10, intake=3)
    assert solver.step().committed
    assert solver.problem.calls == 3
    assert adapter.pop_X.shape == (3, 1) and adapter.pool_views_ready
    assert len(adapter.weights) == 3


def test_moead_one_seed_is_explicitly_insufficient_before_evaluation():
    solver, adapter = make(intake=1)
    with pytest.raises(ValueError, match="at least two"):
        solver.step()
    assert solver.problem.calls == 0 and adapter.pop_X is None


def test_moead_delayed_start_uses_published_mother_pool_after_empty_partition():
    adapter = MOEADAdapter(population_size=4)
    router = StrategyRouterAdapter(name="delayed", roles=[
        RoleSpec("prepare", NSGA2Adapter(population_size=4, offspring_size=4)),
        RoleSpec("search", adapter, pool_task=PoolTaskSpec(mode="initialize", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False,
        phase_policy=lambda context: "prepare" if context["step"] == 0 else "search",
        phase_roles={"prepare": ["prepare"], "search": ["search"]}))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    solver.setup()
    assert solver.step().committed
    # Observing an unscheduled role must not instantiate an empty Unit.
    assert adapter.algorithm_unit is None and adapter.pop_X is None
    assert solver.step().committed and adapter.pool_views_ready
    assert len(adapter.get_solution_pool_roots(solver)) == 4


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter])
@pytest.mark.parametrize("changed_field", ["values", "metadata"])
def test_members_keep_exact_versions_after_same_token_republication_and_checkpoint(kind, changed_field):
    solver, adapter = make(kind)
    assert solver.step().committed
    refs = adapter.get_solution_pool_roots(solver)
    original_batch = solver.solution_pool.read(refs)
    original = original_batch.numeric_matrix.copy()
    changed = (original_batch.semantic_states[0].with_values(original[0] + 20.) if changed_field == "values"
               else original_batch.semantic_states[0].with_meta(meaning="different candidate", nested={"version": [2]}))
    newer = solver.solution_pool.put(CandidateBatch.from_candidates([changed],
        candidate_tokens=(refs[0].candidate_token,)), stage="accepted",
        feedback=OptimizationFeedbackBatch.from_arrays([solver.problem.evaluate(changed.as_array())], [0.]))
    assert newer[0] != refs[0]
    assert adapter.get_solution_pool_roots(solver) == refs
    if kind is MOEADAdapter:
        adapter._publish_direction_views(solver)
        names = solver.solution_pool.projection_subpools(adapter_path(solver.adapter, adapter))
        by_slot = {solver.solution_pool.subpool_metadata(name)["slot"]:
                   solver.solution_pool.subpool_refs(name)[0] for name in names}
        assert tuple(by_slot[i] for i in range(4)) == refs
    target, restored = make(kind, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(solver)
    reader.attach(target)
    payload = writer._build_payload(solver=solver, reason="exact-members")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert restored.get_solution_pool_roots(target) == refs
    np.testing.assert_array_equal(target.solution_pool.read(refs).numeric_matrix, original)
    assert [state.as_dict() for state in target.solution_pool.read(refs).semantic_states] == [
        state.as_dict() for state in original_batch.semantic_states]


@pytest.mark.parametrize("kind", [NSGA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter])
def test_population_rejects_receipt_for_same_token_and_values_with_other_metadata(kind):
    solver, adapter = make(kind)
    store = solver.store_solutions
    def wrong_receipt(batch, **kwargs):
        if kwargs.get("stage") == "accepted":
            batch = CandidateBatch(tuple(state.with_meta(meaning="other candidate") for state in batch.semantic_states),
                                   batch.numeric_matrix, batch.candidate_tokens)
        return store(batch, **kwargs)
    solver.store_solutions = wrong_receipt
    with pytest.raises(ValueError, match="receipt differs from candidate semantic content"):
        solver.step()
    assert adapter.get_solution_pool_roots(solver) == ()


@pytest.mark.parametrize("kind", [NSGA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter])
def test_restore_rejects_reference_swapped_to_metadata_only_version(kind):
    solver, adapter = make(kind)
    assert solver.step().committed
    ref = adapter.get_solution_pool_roots(solver)[0]
    original = solver.solution_pool.read((ref,)).semantic_states[0]
    newer, = solver.solution_pool.put(CandidateBatch.from_candidates(
        [original.with_meta(meaning="other candidate")], candidate_tokens=(ref.candidate_token,)))
    state = json.loads(json.dumps(adapter.get_state()))
    state["population_pool_bindings"][0]["ref"] = newer.as_dict()
    with pytest.raises(ValueError, match="pool binding semantic content/reference"):
        kind(population_size=4).set_state(state)


@pytest.mark.parametrize("kind", [NSGA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter])
def test_pool_roots_check_restored_semantics_against_actual_referenced_version(kind):
    solver, adapter = make(kind)
    assert solver.step().committed
    ref = adapter.get_solution_pool_roots(solver)[0]
    wrong_semantic = solver.solution_pool.read((ref,)).semantic_states[0].with_meta(meaning="other candidate").as_dict()
    state = json.loads(json.dumps(adapter.get_state()))
    binding = state["population_pool_bindings"][0]
    binding["candidate_metadata"] = wrong_semantic["metadata"]
    binding["semantic_digest"] = _semantic_binding_digest(ref, wrong_semantic)
    restored = kind(population_size=4)
    restored.set_state(state)
    with pytest.raises(ValueError, match="semantic content differs from its exact pool version"):
        restored.get_solution_pool_roots(solver)


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter])
def test_nsga_family_initializes_its_own_population_without_implicit_snapshot_intake(kind):
    calls = {"init": 0, "mutate": 0, "repair": 0}
    class Pipeline:
        def initialize(self, problem, context):
            calls["init"] += 1
            return np.array([10.])
        def mutate(self, candidate, context):
            calls["mutate"] += 1
            return candidate - 1.
        def repair(self, candidate, context):
            calls["repair"] += 1
            return candidate - 1.
    adapter = kind(population_size=4, offspring_size=3, crossover_rate=0.)
    pipeline = Pipeline()
    solver = ComposableSolver(Problem(), adapter=adapter, representation_pipeline=RepresentationPipeline(
        initializer=pipeline, mutator=pipeline, repair=pipeline))
    solver.setup()
    # A valid previous algorithm's projection is present in both old fallback
    # locations. It is not an explicit assignment to this Adapter's Unit.
    solver.population = np.full((4, 1), 40.)
    solver.objectives = np.zeros((4, 2))
    solver.constraint_violations = np.zeros(4)
    reader = solver.read_snapshot
    def unrelated_snapshot(key=None):
        return {"population": solver.population, "objectives": solver.objectives,
                "constraint_violations": solver.constraint_violations}
    solver.read_snapshot = unrelated_snapshot
    candidates = adapter.propose(solver, solver.build_context())
    if kind is NSGA3Adapter:
        # Canonical NSGA-III sends its initial population for evaluation before
        # CV-based mating; an uncommitted manual proposal is not membership.
        from nsgablack.units.contracts import candidate_array
        np.testing.assert_array_equal(np.vstack([candidate_array(x) for x in candidates]), np.full((4, 1), 9.))
        assert calls == {"init":4,"mutate":0,"repair":4}
        solver.read_snapshot = reader
        assert solver.step().committed
        assert calls == {"init":8,"mutate":0,"repair":12}
        np.testing.assert_array_equal(adapter.population, np.full((4,1),8.))
        assert len(adapter.get_solution_pool_roots(solver)) == 4
        return
    # The ordinary initializer's own repair still runs once per seed. No
    # additional proposal repair is performed by Adapter.propose().
    np.testing.assert_array_equal(candidates, np.full((3, 1), 8.))
    assert calls == {"init": 4, "mutate": 3, "repair": 4}
    solver.read_snapshot = reader
    # The next normal step reuses the owned initial Unit, repairs only its
    # three offspring, and publishes exact references for accepted members.
    assert solver.step().committed
    assert calls == {"init": 4, "mutate": 6, "repair": 7}
    np.testing.assert_array_equal(adapter.population, np.full((3, 1), 7.))
    assert len(adapter.get_solution_pool_roots(solver)) == 3


@pytest.mark.parametrize("kind", [NSGA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter])
@pytest.mark.parametrize("damage", ["length", "token", "content"])
def test_restore_rejects_pool_binding_member_mismatch(kind, damage):
    solver, adapter = make(kind)
    assert solver.step().committed
    state = json.loads(json.dumps(adapter.get_state()))
    if damage == "length":
        state["population_pool_bindings"].pop()
    elif damage == "token":
        state["population_pool_bindings"][0]["ref"]["candidate_token"] = "other"
    else:
        state["population_pool_bindings"][0]["candidate_digest"] = "different-content"
    with pytest.raises(ValueError, match="pool binding"):
        kind(population_size=4).set_state(state)


def test_bootstrap_failure_restores_members_and_exact_bindings():
    solver, adapter = make(budget=2)
    assert solver.step().committed
    refs = adapter.get_solution_pool_roots(solver)
    snapshot = copy.deepcopy(adapter.get_state())
    original = adapter._sync_population_snapshot
    def fail(control):
        original(control)
        raise RuntimeError("bootstrap publication failure")
    adapter._sync_population_snapshot = fail
    with pytest.raises(RuntimeError, match="bootstrap publication failure"):
        solver.step()
    assert adapter.get_state() == snapshot
    assert adapter.get_solution_pool_roots(solver) == refs
    assert not adapter.pool_views_ready
    adapter._sync_population_snapshot = original
    assert solver.step().committed and adapter.pool_views_ready


def test_moead_one_admitted_ref_can_replace_multiple_direction_slots():
    solver, adapter = make()
    assert solver.step().committed
    adapter.cfg.nr = 4
    pool = solver.solution_pool
    seed = solver.store_solutions(CandidateBatch.from_candidates([[.5]], candidate_tokens=("better",)))
    from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
    context = {KEY_SOLUTION_INPUT_REF: pool.bind_input(seed)}
    candidates = adapter.propose(solver, context)
    tokens = adapter.candidate_tokens_for(solver, candidates)
    feedback = OptimizationFeedbackBatch.from_arrays([[.25, .25]], [0.])
    refs = solver.store_solutions(CandidateBatch.from_candidates(candidates, candidate_tokens=tokens),
                                 stage="accepted", feedback=feedback)
    feedback = OptimizationFeedbackBatch.from_feedback(
        [replace(feedback.items[0], info={"accepted_solution_ref": refs[0].as_dict()})],
        violations=feedback.violations)
    adapter.update(solver, candidates, feedback, context)
    assert adapter.get_solution_pool_roots(solver) == refs * 4
    for name in pool.projection_subpools(adapter_path(solver.adapter, adapter)):
        assert pool.subpool_refs(name) == refs


def test_de_evaluates_initial_members_before_targeted_trials():
    adapter = DifferentialEvolutionAdapter(population_size=4, batch_size=2)
    solver = ComposableSolver(Problem(), adapter=adapter)
    solver.setup()
    assert solver.evaluation_count == 0 and adapter.population is None
    assert solver.step().committed
    assert solver.evaluation_count == 4
    assert adapter._last_target_indices == []
    roots = adapter.get_solution_pool_roots(solver)
    np.testing.assert_array_equal(solver.solution_pool.read(roots).numeric_matrix, adapter.population)
    assert solver.step().committed
    assert solver.evaluation_count == 6
    assert len(adapter._last_target_indices) == len(adapter._last_target_scores) == 2
    assert adapter.population.shape == (4, 1)
    adapter.get_solution_pool_roots(solver)


def test_de_partial_bootstrap_resumes_before_creating_target_indices():
    source, adapter = make(DifferentialEvolutionAdapter, budget=2)
    assert source.step().committed
    assert len(adapter.population) == 2 and adapter._last_target_indices == []
    before = adapter.get_solution_pool_roots(source)
    target, restored = make(DifferentialEvolutionAdapter, budget=2, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="de-partial-baseline")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert target.step().committed and source.step().committed
    assert len(restored.population) == 4 and restored._last_target_indices == []
    assert restored.get_solution_pool_roots(target)[:2] == adapter.get_solution_pool_roots(source)[:2] == before
    np.testing.assert_array_equal(restored.population, adapter.population)
    assert target.step().committed and source.step().committed
    assert restored._last_target_indices == adapter._last_target_indices
    np.testing.assert_array_equal(restored.population, adapter.population)


def test_de_larger_initial_intake_selects_members_without_inventing_targets():
    solver, adapter = make(DifferentialEvolutionAdapter, capacity=4, intake=6)
    assert solver.step().committed
    assert solver.problem.calls == 6 and len(adapter.population) == 4
    assert adapter._last_target_indices == []
    assert solver.adapter.units[0].adapter.task_status["status"] == "done"
    assert len(adapter.get_solution_pool_roots(solver)) == 4


@pytest.mark.parametrize("producer_type,consumer_type", [
    (NSGA2Adapter, VNSAdapter), (NSGA3Adapter, SimulatedAnnealingAdapter),
    (SPEA2Adapter, VNSAdapter), (DifferentialEvolutionAdapter, PatternSearchAdapter),
])
def test_population_view_drives_per_member_refinement_without_copying_records(producer_type, consumer_type):
    options = {"batch_size": 4} if producer_type is DifferentialEvolutionAdapter else {"offspring_size": 4}
    producer = producer_type(name="source", population_size=4, **options)
    consumer = consumer_type(name="refiner")
    router = StrategyRouterAdapter(name="ordinary", roles=[
        RoleSpec("produce", producer),
        RoleSpec("refine", consumer, pool_task=PoolTaskSpec(subpools.all(producer),
            count="all", steps=2, output="refined", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False,
        phase_policy=lambda ctx: "produce" if ctx["step"] < 2 else "refine",
        phase_roles={"produce": ["produce"], "refine": ["refine"]}))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    solver.set_random_seed(23)
    solver.setup()
    pool = solver.solution_pool
    creator = adapter_path(router, producer)
    name = "/".join((*creator, "population"))
    published = []
    publish = pool.publish_subpool_view
    def observe_publication(view, refs, **kwargs):
        count = pool.record_count
        publish(view, refs, **kwargs)
        assert pool.record_count == count
        if view == name:
            published.append(tuple(refs))
            assert pool.subpools_created_by(creator) == ()  # staged, not visible
    pool.publish_subpool_view = observe_publication
    assert pool.subpools_created_by(creator) == ()
    assert solver.step().committed
    first = pool.subpool_descriptor(name)
    assert pool.subpools_created_by(creator) == (name,)
    assert solver.step().committed
    current = pool.subpool_descriptor(name)
    assert current["view_id"] == first["view_id"] and current["revision"] > first["revision"]
    refs = producer.get_solution_pool_roots(solver)
    assert pool.subpool_refs(name) == refs == published[-1]
    assert len(refs) == 4 and pool.subpool_metadata(name)["kind"] == "candidate_view"
    assert not producer.supports_objective_projection
    worker = router.units[1].adapter
    for _ in range(10):
        if worker.task_status.get("status") == "done":
            break
        assert solver.step().committed
    assert worker.task_status["status"] == "done"
    jobs = worker._local["jobs"]
    assert tuple(job["ref"] for job in jobs) == tuple(ref.as_dict() for ref in refs)
    assert all(job["created_by"] == list(creator) and job["projection"] is None for job in jobs)
    results = pool.subpools_created_by(adapter_path(router, consumer))
    assert len(results) == 4
    for result in results:
        metadata = pool.subpool_metadata(result)
        assert metadata["kind"] == "candidate_view" and "projection" not in metadata
        assert metadata["parent"] == current
        assert pool.read_raw_feedback(pool.subpool_refs(result))[0].shape == (1, 2)
    assert pool.subpool_refs(name) == refs


def test_ordinary_population_view_waits_for_complete_exact_bindings():
    adapter = NSGA2Adapter(population_size=4, offspring_size=1)
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=Operator()))
    solver.setup()
    # The legacy explicit numerical setter has no exact-ref input. A later
    # accepted proposal cannot certify the unbound retained members for it.
    adapter.set_population_snapshot(np.zeros((3, 1)), np.zeros((3, 2)), np.zeros(3))
    assert solver.step().committed
    assert len(adapter._population_pool_bindings) == 4
    assert sum(binding is not None for binding in adapter._population_pool_bindings) == 1
    assert solver.solution_pool.subpools_created_by(adapter_path(adapter, adapter)) == ()
    with pytest.raises(ValueError, match="requires exact pool versions"):
        adapter.get_solution_pool_roots(solver)


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, DifferentialEvolutionAdapter])
@pytest.mark.parametrize("replace_with", ["different", "empty"])
def test_numeric_setter_cannot_replace_or_clear_published_members(kind, replace_with):
    solver, adapter = make(kind)
    assert solver.step().committed
    pool = solver.solution_pool
    creator = adapter_path(solver.adapter, adapter)
    name, = pool.subpools_created_by(creator)
    before = copy.deepcopy(adapter.get_state())
    descriptor, refs = pool.subpool_descriptor(name), pool.subpool_refs(name)
    x, f, v = adapter.get_population_snapshot()
    replacement = (x + 10., f, v) if replace_with == "different" else (
        np.empty((0, x.shape[1])), np.empty((0, f.shape[1])), np.empty(0))
    with pytest.raises(ValueError, match="requires explicit pool input"):
        adapter.set_population_snapshot(*replacement)
    assert adapter.get_state() == before
    assert pool.subpool_descriptor(name) == descriptor
    assert pool.subpool_refs(name) == adapter.get_solution_pool_roots(solver) == refs


@pytest.mark.parametrize("kind", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter, DifferentialEvolutionAdapter])
def test_numeric_setter_refreshes_feedback_without_changing_member_view(kind):
    solver, adapter = make(kind)
    assert solver.step().committed
    name, = solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, adapter))
    descriptor = solver.solution_pool.subpool_descriptor(name)
    refs = adapter.get_solution_pool_roots(solver)
    x, f, v = adapter.get_population_snapshot()
    adapter.set_population_snapshot(x.copy(), f + 1., v.copy())
    np.testing.assert_array_equal(adapter.objectives, f + 1.)
    assert adapter.get_solution_pool_roots(solver) == refs
    assert solver.solution_pool.subpool_refs(name) == refs
    assert solver.solution_pool.subpool_descriptor(name) == descriptor


@pytest.mark.parametrize("kind", [NSGA2Adapter, DifferentialEvolutionAdapter])
def test_manual_update_with_missing_receipts_withdraws_only_its_native_view(kind):
    solver, adapter = make(kind)
    assert solver.step().committed
    pool = solver.solution_pool
    creator = adapter_path(solver.adapter, adapter)
    name, = pool.subpools_created_by(creator)
    refs = pool.subpool_refs(name)
    if kind is DifferentialEvolutionAdapter:
        adapter._last_target_indices = [0]
        adapter._last_target_scores = np.array([100.])
    adapter.update(solver, np.array([[.5]]), (np.array([[.25, .25]]), np.zeros(1)), {})
    assert not pool.has_subpool(name) and pool.subpools_created_by(creator) == ()
    with pytest.raises(ValueError, match="requires exact pool versions"):
        adapter.get_solution_pool_roots(solver)
    # An unrelated user collection with the same name must not be removed.
    pool.create_subpool(name, refs)
    publish_population_view(adapter, solver)
    assert pool.subpool_refs(name) == refs
    assert pool.subpool_metadata(name)["kind"] == "candidate_collection"


@pytest.mark.parametrize("kind", [NSGA2Adapter, DifferentialEvolutionAdapter])
def test_failed_attempt_restores_withdrawn_view_and_exact_member_refs(kind):
    options = {"batch_size": 4} if kind is DifferentialEvolutionAdapter else {"offspring_size": 4}
    adapter = kind(population_size=4, **options)
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    solver.set_random_seed(17)
    solver.setup()
    assert solver.step().committed
    pool = solver.solution_pool
    creator = adapter_path(adapter, adapter)
    name, = pool.subpools_created_by(creator)
    descriptor, refs = pool.subpool_descriptor(name), pool.subpool_refs(name)
    before = copy.deepcopy(adapter.get_state())
    evaluated = solver.evaluation_count
    update = adapter.update
    def fail_after_manual_update(control, candidates, feedback, context):
        update(control, candidates, (feedback.objectives, feedback.violations), context)
        assert not pool.has_subpool(name)
        raise RuntimeError("failure after withdrawing population view")
    adapter.update = fail_after_manual_update
    with pytest.raises(RuntimeError, match="failure after withdrawing population view"):
        solver.step()
    assert adapter.get_state() == before
    assert pool.subpool_descriptor(name) == descriptor
    assert pool.subpool_refs(name) == adapter.get_solution_pool_roots(solver) == refs
    assert solver.evaluation_count > evaluated
    adapter.update = update
    assert solver.step().committed


def test_evolution_normal_initialization_and_steps_preserve_explicit_sync():
    from nsgablack.core.evolution_solver import EvolutionSolver
    solver = EvolutionSolver(Problem(), pop_size=4, max_generations=3, random_seed=19,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator()))
    result = solver.run(return_dict=True)
    assert result["generation"] == 3
    assert solver.evaluation_count == solver.problem.calls == 16
    np.testing.assert_array_equal(solver.population, solver.adapter.population)
    assert len(solver.adapter.get_solution_pool_roots(solver)) == 4
