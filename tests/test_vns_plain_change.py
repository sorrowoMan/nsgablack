"""A Project can supply VNS a plain composed change without a component class."""
import copy
import warnings

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import UnknownState
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PoolTaskSpec, RoleSpec, StrategyRouterAdapter,
    VNSAdapter, subpools,
)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import (
    ClipRepair, GaussianMutation, RepresentationPipeline, UniformInitializer,
)
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(np.asarray(candidate).copy())
        return [float(np.sum(np.asarray(candidate) ** 2))]


class SemanticInitializer:
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "plain_change_semantic_seed"}

    def initialize(self, problem, context):
        return UnknownState([4.], {"domain": "kept"})


def halve(candidate):
    return np.asarray(candidate) * .5


def shift(candidate):
    return np.asarray(candidate) + .25


def composed_change(request, *, rng):
    del rng
    assert request.parents.shape == (1, 1)
    assert not request.parents.flags.writeable
    assert len(request.source_refs) == 1
    assert request.unit_id
    assert request.parameters["sigma"] > 0
    with pytest.raises(ValueError):
        request.candidate[0] = 99.
    with pytest.raises(TypeError):
        request.parameters["k"] = 99
    return shift(halve(request.candidate))


def random_worsening_change(request, *, rng):
    return request.candidate + 1. + np.abs(rng.normal(size=request.candidate.shape))


def random_improving_change(request, *, rng):
    return request.candidate - .5 - rng.uniform(0., .25, size=request.candidate.shape)


def wrong_dimension_change(request, *, rng):
    del request, rng
    return np.zeros(2)


def make_solver(change=composed_change, *, semantic=False, pipeline_mutator=None, batch_size=2):
    pipeline = RepresentationPipeline(initializer=UniformInitializer(low=4., high=4.),
                                      mutator=pipeline_mutator, repair=ClipRepair(low=-100., high=100.))
    adapter = VNSAdapter(change=change, batch_size=batch_size, k_max=3,
                         restart_on_stagnation=False,
                         initializer=SemanticInitializer() if semantic else None)
    solver = ComposableSolver(problem=Sphere(), adapter=adapter, representation_pipeline=pipeline)
    solver.set_random_seed(91)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        solver.setup()
    assert not [item for item in caught if "mutat" in str(item.message).lower()]
    return solver


def test_plain_composition_runs_after_baseline_and_overrides_only_this_leaf_pipeline_mutator():
    solver = make_solver(pipeline_mutator=GaussianMutation(sigma=25.))
    assert solver.adapter.current_unit is None and solver.adapter.neighborhood_unit is None
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls, [[4.]])
    assert solver.evaluation_count == 1
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls, [[4.], [2.25], [2.25]])
    np.testing.assert_array_equal(solver.adapter.current_x, [2.25])
    assert solver.adapter.current_score == 2.25 ** 2


def test_plain_change_dimension_error_rejects_before_evaluation_and_keeps_current_unit():
    solver = make_solver(wrong_dimension_change)
    assert solver.step().committed
    adapter = solver.adapter
    unit_id, counter = adapter.current_unit.unit_id, adapter._unit_counter
    before_rng = copy.deepcopy(adapter._operator_rng.bit_generator.state)
    with pytest.raises((ValueError, TypeError), match="got 2 != expected 1"):
        solver.step()
    assert solver.evaluation_count == 1 and len(solver.problem.calls) == 1
    assert adapter.current_unit.unit_id == unit_id and adapter._unit_counter == counter
    assert adapter._pending_units == [] and adapter.k == 0
    assert adapter._operator_rng.bit_generator.state == before_rng


def test_plain_change_failure_restores_rng_neighborhood_pending_and_retry_proposals(monkeypatch):
    solver = make_solver(random_worsening_change)
    assert solver.step().committed
    adapter = solver.adapter
    adapter.k = 1
    before_rng = copy.deepcopy(adapter._operator_rng.bit_generator.state)
    before_id, before_counter = adapter.current_unit.unit_id, adapter._unit_counter
    original_update_best = solver._update_best

    def fail_after_algorithm_update(*args, **kwargs):
        raise RuntimeError("after VNS feedback")

    monkeypatch.setattr(solver, "_update_best", fail_after_algorithm_update)
    with pytest.raises(RuntimeError, match="after VNS feedback"):
        solver.step()
    failed_proposals = np.array(solver.problem.calls[-2:], copy=True)
    assert adapter._operator_rng.bit_generator.state == before_rng
    assert adapter.k == 1 and adapter._pending_units == []
    assert adapter.current_unit.unit_id == before_id and adapter._unit_counter == before_counter
    np.testing.assert_array_equal(adapter.current_x, [4.])
    monkeypatch.setattr(solver, "_update_best", original_update_best)
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls[-2:], failed_proposals)
    assert adapter.k == 2
    # Already consumed evaluations survive rollback; the retry is another batch.
    assert solver.evaluation_count == 5


def test_plain_numeric_change_preserves_semantics_and_derives_child_identity():
    solver = make_solver(semantic=True)
    assert solver.step().committed
    baseline, = solver.adapter.get_pool_refinement_results(solver)
    assert solver.step().committed
    selected, = solver.adapter.get_pool_refinement_results(solver)
    assert selected.candidate_token != baseline.candidate_token
    state, = solver.read_solutions((selected,)).semantic_states
    assert isinstance(state, UnknownState) and state.metadata["domain"] == "kept"
    np.testing.assert_array_equal(state.values, [2.25])
    provenance, = solver.solution_pool.read_provenance((selected,))
    assert provenance["parent_token"] == baseline.candidate_token
    assert provenance["metadata"]["change_input_refs"] == [baseline.as_dict()]
    assert solver.adapter._current_pool_ref == selected


def test_plain_change_partial_admission_uses_admitted_pending_unit_and_exact_result():
    solver = make_solver(random_improving_change)
    assert solver.step().committed

    class SecondOnly:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1,))

    solver.set_evaluation_acceptance_policy(SecondOnly())
    assert solver.step().committed
    assert solver.adapter._pending_units == []
    assert solver.adapter.k == 0
    selected, = solver.adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((selected,)).numeric_matrix,
                                  [solver.problem.calls[-1]])
    assert not np.array_equal(solver.problem.calls[-2], solver.problem.calls[-1])


def test_plain_change_formal_checkpoint_restores_rng_and_next_evaluated_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "vns-plain-change-test-key")
    source = make_solver(random_improving_change)
    assert source.step().committed and source.step().committed
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    path = writer.save_checkpoint(reason="plain-change")
    restored = make_solver(random_improving_change)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(path))
    restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.adapter._operator_rng.bit_generator.state == source.adapter._operator_rng.bit_generator.state
    assert source.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[-2:])
    np.testing.assert_array_equal(restored.adapter.current_x, source.adapter.current_x)
    assert restored.adapter.current_score == source.adapter.current_score


def test_plain_change_needs_no_default_mutation_when_shared_pipeline_only_has_named_operators():
    pipeline = RepresentationPipeline(initializer=UniformInitializer(low=4., high=4.),
                                      mutation_operators={"other_leaf": GaussianMutation(sigma=25.)})
    adapter = VNSAdapter(change=composed_change, batch_size=1, restart_on_stagnation=False)
    solver = ComposableSolver(problem=Sphere(), adapter=adapter, representation_pipeline=pipeline)
    solver.set_random_seed(91)
    solver.setup()
    assert not adapter.uses_pipeline_mutation
    assert not any(code == "unit-operator-contract-invalid" for code, _ in inspect_runtime_contracts(solver))
    assert solver.step().committed and solver.step().committed
    np.testing.assert_array_equal(adapter.current_x, [2.25])


def test_plain_change_refines_moead_views_without_overwriting_raw_objectives():
    class TwoObjectives(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=1, objectives=["minimize", "minimize"], bounds=[(-100., 100.)])

        def evaluate(self, candidate):
            x = float(candidate[0])
            return [x * x, (x - 10.) ** 2]

    source = MOEADAdapter(name="directions", population_size=2, neighborhood_size=2,
                          batch_size=2, decomposition="weighted_sum")
    local = VNSAdapter(name="local", change=composed_change, batch_size=1, restart_on_stagnation=False)
    router = StrategyRouterAdapter(name="views", roles=[
        RoleSpec("source", source),
        RoleSpec("refine", local, pool_task=PoolTaskSpec(subpools.all(source),
            steps=2, output="refined", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False,
        phase_schedule=(("bootstrap", 1), ("refine", -1)),
        phase_roles={"bootstrap": ["source"], "refine": ["refine"]}))
    solver = ComposableSolver(problem=TwoObjectives(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(low=4., high=4.)))
    solver.set_random_seed(91)
    solver.setup()
    for _ in range(5):
        assert solver.step().committed
    task = router.units[1].adapter
    assert task.task_status["status"] == "done"
    names = solver.solution_pool.projection_subpools(adapter_path(router, local))
    assert len(names) == 2
    values = []
    for name in names:
        refs = solver.solution_pool.subpool_refs(name)
        x = solver.read_solutions(refs).numeric_matrix[:, 0]
        raw, violation = solver.solution_pool.read_raw_feedback(refs)
        np.testing.assert_array_equal(raw, np.stack((x*x, (x-10.)**2), axis=1))
        np.testing.assert_array_equal(violation, [0.])
        values.extend(x.tolist())
    # The same change helps the first objective and hurts the second; each
    # task keeps its own frozen direction rather than summing the raw vector.
    assert sorted(values) == [2.25, 4.]
