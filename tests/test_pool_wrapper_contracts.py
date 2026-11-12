"""Pool references and intake boundaries survive algorithm wrappers."""
import copy

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, Feedback
from nsgablack.adapters import (
    AlgorithmAdapter, AsyncEventDrivenAdapter, AsyncEventDrivenConfig,
    CandidateProposerAdapter, EliteRetentionAdapter, EliteRetentionConfig,
    EventStrategySpec, FixedCandidateAdapter, MultiStrategyConfig, NSGA2Adapter,
    PoolTaskSpec, RoleAdapter, RoleRouterAdapter, RoleSpec, SerialPhaseSpec,
    StrategyChainAdapter, StrategyRouterAdapter, VNSAdapter, MOEADAdapter, subpools,
)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
from nsgablack.core import ComposableSolver, PoolRetentionPolicy
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import RepresentationPipeline
from tests.test_subpool_tasks import Operator, Sphere


class BatchLeaf(AlgorithmAdapter):
    """Stateless test strategy: the control owns accepted candidates."""
    def __init__(self):
        super().__init__("batch")

    def propose(self, control, context):
        return [np.array([x]) for x in (3., 1., 2.)]

    def update(self, control, candidates, feedback, context):
        pass

    def get_solution_pool_roots(self, control):
        return ()


def make_solver(adapter, *, retention=False):
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), mutator=Operator(1.)))
    solver.set_random_seed(27)
    if retention:
        solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    solver.setup()
    return solver


def source_refs(solver, count=5):
    return solver.store_solutions(CandidateBatch.from_candidates(
        [np.array([float(i + 1)]) for i in range(count)],
        candidate_tokens=tuple(f"source:{i}" for i in range(count))))


class Admission:
    policy_id = "wrapper_admission"

    def __init__(self, indices):
        self.indices = indices

    def select(self, candidates, feedback, context):
        return BatchDisposition(len(candidates.semantic_states), self.indices)


def test_role_intake_ignores_local_cap_and_partial_admission_keeps_remaining_seeds():
    leaf = NSGA2Adapter(population_size=5, offspring_size=5)
    wrapped = RoleAdapter("search", leaf, max_candidates=2)
    router = StrategyRouterAdapter(name="route", roles=[RoleSpec("search", wrapped,
        pool_task=PoolTaskSpec(mode="initialize", shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=5, adapt_weights=False))
    solver = make_solver(router, retention=True)
    source_refs(solver)
    solver.set_evaluation_acceptance_policy(Admission((0, 2, 4)))

    assert solver.step().committed
    assert solver.evaluation_count == 5  # All consumed inputs reached evaluation.
    task = router.units[0].adapter
    assert solver.solution_pool.input_remaining(task._local["input"]) == 2
    assert leaf.population.shape[0] == 3

    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert solver.evaluation_count == 7
    assert task.task_status["status"] == "done"
    assert solver.step().committed
    assert solver.evaluation_count == 9  # The ordinary proposal cap still applies.


def test_role_forwards_restart_and_selected_result_without_claiming_missing_capabilities():
    leaf = VNSAdapter(batch_size=1, restart_on_stagnation=False)
    wrapped = RoleAdapter("local", leaf)
    assert wrapped.pool_input_modes == leaf.pool_input_modes
    assert wrapped.default_pool_input_count() == leaf.default_pool_input_count()
    assert wrapped.supports_pool_restart and wrapped.supports_objective_projection
    elite = EliteRetentionAdapter(leaf, EliteRetentionConfig(retention_probability=0.))
    assert elite.pool_result_owner() is leaf
    assert elite.get_pool_refinement_results == leaf.get_pool_refinement_results
    assert elite.pool_input_modes == ()  # Search-altering wrappers do not become transparent intake owners.
    router = StrategyRouterAdapter(roles=[RoleSpec("local", wrapped,
        pool_task=PoolTaskSpec(steps=1, output="done"))])
    solver = make_solver(router, retention=True)
    source_refs(solver, 1)
    assert solver.step().committed
    assert wrapped.get_pool_refinement_results(solver) == leaf.get_pool_refinement_results(solver)
    assert wrapped.get_pool_refinement_results(solver)
    wrapped.restart_search(solver, {})
    assert leaf.current_score is None
    unsupported = RoleAdapter("plain", BatchLeaf())
    assert unsupported.pool_input_modes == ()
    assert not unsupported.supports_pool_restart
    assert not unsupported.supports_objective_projection
    assert unsupported.get_pool_refinement_results is None


@pytest.mark.parametrize("kind", ["role", "role_router", "chain"])
def test_pure_composition_retention_visits_child_owner(kind):
    leaf = FixedCandidateAdapter()
    if kind == "role":
        adapter = RoleAdapter("fixed", leaf)
    elif kind == "role_router":
        adapter = RoleRouterAdapter([RoleAdapter("fixed", leaf)])
    else:
        adapter = StrategyChainAdapter([SerialPhaseSpec("fixed", leaf)])
    solver = make_solver(adapter, retention=True)
    assert solver.step().committed
    assert adapter.get_solution_pool_roots(solver) == ()
    roots = solver.solution_pool_retention_roots()
    assert leaf.get_solution_pool_roots(solver)
    assert any(tuple(values) == leaf.get_solution_pool_roots(solver) for values in roots.values())


def archive_wrapper(kind):
    if kind == "elite":
        return EliteRetentionAdapter(BatchLeaf(), EliteRetentionConfig(
            retention_probability=0., history_size=2))
    return AsyncEventDrivenAdapter([EventStrategySpec(BatchLeaf(), "batch")],
        config=AsyncEventDrivenConfig(total_batch_size=3, target_queue_size=3,
            bootstrap_events_per_strategy=3, max_archive_size=2))


@pytest.mark.parametrize("kind", ["elite", "events"])
def test_archives_retain_only_accepted_exact_versions_through_checkpoint_and_failure(kind, monkeypatch):
    adapter = archive_wrapper(kind)
    solver = make_solver(adapter, retention=True)
    solver.set_evaluation_acceptance_policy(Admission((0, 2)))
    assert solver.step().committed
    retained = adapter.get_solution_pool_roots(solver)
    assert len(retained) == 2
    assert solver.read_solutions(retained).numeric_matrix[:, 0].tolist() == [2., 3.]
    saved = copy.deepcopy(adapter.get_state())
    restored = archive_wrapper(kind)
    restored.set_state(saved)
    assert restored.get_solution_pool_roots(solver) == retained

    # A later version with the same token must not redirect historical roots.
    later = solver.store_solutions(CandidateBatch.from_candidates([np.array([99.])],
        candidate_tokens=(retained[0].candidate_token,)))
    assert later[0] != retained[0]
    assert restored.get_solution_pool_roots(solver) == retained
    assert solver.read_solutions(retained).numeric_matrix[0, 0] == 2.

    solver.set_evaluation_acceptance_policy(None)
    original = adapter.update
    def fail_after_archive(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("archive failure")
    monkeypatch.setattr(adapter, "update", fail_after_archive)
    with pytest.raises(RuntimeError, match="archive failure"):
        solver.step()
    assert adapter.get_solution_pool_roots(solver) == retained


@pytest.mark.parametrize("kind", ["elite", "events"])
def test_unversioned_legacy_archive_does_not_silently_authorize_collection(kind):
    adapter = archive_wrapper(kind)
    entry = {"candidate": np.array([1.]), "x": np.array([1.]),
             "objectives": np.array([1.]), "objective": np.array([1.]),
             "score": 1., "violation": 0.}
    if kind == "elite":
        adapter.ensure_unit()
        adapter._archive.append(entry)
    else:
        adapter.archive.append(entry)
    assert adapter.get_solution_pool_roots(None) is None


def test_elite_intake_cannot_replace_consumed_seed_with_archive_candidate():
    class Intake(AlgorithmAdapter):
        def propose(self, control, context):
            return control.init_population(3, context)
        def update(self, control, candidates, feedback, context):
            pass
    adapter = EliteRetentionAdapter(Intake("intake"), EliteRetentionConfig(
        retention_probability=1., retention_ratio=1.))
    solver = make_solver(adapter)
    refs = source_refs(solver, 3)
    adapter.ensure_unit()
    adapter._archive.append({"candidate": np.array([90.]), "score": 0., "violation": 0.})
    key = solver.solution_pool.bind_input(refs)
    proposed = adapter.propose(solver, {KEY_SOLUTION_INPUT_REF: key})
    assert np.asarray(proposed).reshape(-1).tolist() == [1., 2., 3.]
    assert solver.solution_pool.input_remaining(key) == 0


def test_fixed_candidate_updates_repaired_unit_and_keeps_exact_ref_across_restore():
    class Repair:
        def repair(self, candidate, context):
            return candidate + 1.
    adapter = FixedCandidateAdapter()
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Operator(), repair=Repair()))
    solver.set_solution_pool_retention(PoolRetentionPolicy())
    solver.setup()
    assert solver.step().committed
    current = adapter.get_solution_pool_roots(solver)
    np.testing.assert_array_equal(adapter.current_unit.to_candidate().values,
                                  solver.read_solutions(current).numeric_matrix[0])
    restored = FixedCandidateAdapter()
    restored.set_state(adapter.get_state())
    assert restored.get_solution_pool_roots(solver) == current
    assert restored.pool_input_modes == ("initialize",)
    assert not restored.supports_pool_restart


def test_candidate_proposer_requires_explicit_subclass_retention_and_has_exact_ref_helper():
    class CaseProposer(CandidateProposerAdapter):
        def propose(self, control, context):
            return ()
        def update(self, control, candidates, feedback, context):
            pass
    adapter = CaseProposer()
    assert adapter.get_solution_pool_roots(None) is None
    ref = SolutionRef("pool", "record", 2, "token")
    rich = OptimizationFeedbackBatch.from_feedback([
        Feedback(objectives=np.array([1.]), info={"accepted_solution_ref": ref.as_dict()})])
    assert adapter.pool_refs_from_feedback(rich) == (ref,)
    with pytest.raises(ValueError, match="exact accepted"):
        adapter.pool_refs_from_feedback(OptimizationFeedbackBatch.from_arrays([[1.]], [0.]))


@pytest.mark.parametrize("kind", ["chain", "events"])
def test_chain_and_events_use_nested_router_for_formal_pool_tasks(kind):
    fixed = FixedCandidateAdapter()
    router = StrategyRouterAdapter(name="nested", roles=[RoleSpec("fixed", fixed,
        pool_task=PoolTaskSpec(mode="initialize", shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=1, adapt_weights=False))
    if kind == "chain":
        adapter = StrategyChainAdapter([SerialPhaseSpec("initial", router)])
    else:
        adapter = AsyncEventDrivenAdapter([EventStrategySpec(router, "nested")],
            config=AsyncEventDrivenConfig(total_batch_size=1, target_queue_size=1,
                bootstrap_events_per_strategy=1))
    solver = make_solver(adapter, retention=True)
    sources = source_refs(solver, 1)
    assert solver.step().committed
    result = fixed.get_solution_pool_roots(solver)
    provenance = solver.solution_pool.read_provenance(result)[0]
    assert provenance["metadata"]["solution_source_ref"] == sources[0].as_dict()
    assert router.units[0].adapter.task_status["status"] == "done"


def test_elite_injection_uses_exact_archived_parent_identity():
    adapter = EliteRetentionAdapter(FixedCandidateAdapter(), EliteRetentionConfig(
        retention_probability=1., retention_ratio=1.))
    solver = make_solver(adapter, retention=True)
    assert solver.step().committed
    parent = adapter.get_solution_pool_roots(solver)[0]
    assert solver.step().committed
    current = adapter.get_solution_pool_roots(solver)[0]
    assert solver.read_solutions((current,)).numeric_matrix[0, 0] == 9.
    assert solver.solution_pool.read_provenance((current,))[0]["parent_token"] == parent.candidate_token


@pytest.mark.parametrize("select_wrapped", [False, True])
def test_role_refinement_publishes_under_leaf_owner_for_recursive_selection(select_wrapped):
    from tests.test_nested_refinement_contracts import RouteProblem, RouteOperators
    producer = MOEADAdapter(name="producer", population_size=2, batch_size=1,
        neighborhood_size=2, decomposition="weighted_sum")
    coarse = VNSAdapter(name="coarse", batch_size=1, restart_on_stagnation=False)
    wrapped = RoleAdapter("polisher", coarse)
    fine = VNSAdapter(name="fine", batch_size=1, restart_on_stagnation=False)
    def phase(context):
        if context["step"] == 0:
            return "producer"
        return "coarse" if context["pool_tasks"]["coarse:0"]["status"] != "done" else "fine"
    router = StrategyRouterAdapter(name="nested_roles", roles=[
        RoleSpec("producer", producer),
        RoleSpec("coarse", wrapped, pool_task=PoolTaskSpec(subpools.all(producer),
            steps=1, output="coarse_results", shuffle=False)),
        RoleSpec("fine", fine, pool_task=PoolTaskSpec(
            subpools.all(wrapped if select_wrapped else coarse),
            steps=1, output="fine_results", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False,
        phase_policy=phase, phase_roles={"producer": ["producer"], "coarse": ["coarse"], "fine": ["fine"]}))
    solver = ComposableSolver(RouteProblem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=RouteOperators(), mutator=RouteOperators()))
    solver.setup()
    for _ in range(5):
        assert solver.step().committed
    assert wrapped.pool_result_owner() is coarse
    assert len(solver.solution_pool.projection_subpools(adapter_path(router, coarse))) == 2
    assert len(solver.solution_pool.projection_subpools(adapter_path(router, fine))) == 2
    assert router.units[2].adapter.task_status["status"] == "done"
