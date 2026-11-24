"""Selected occurrences reach complete changes without field-specific glue."""
from dataclasses import dataclass

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from nsgablack.adapters import NSGA2Adapter, NSGA3Adapter, SPEA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
from nsgablack.representation import RepresentationPipeline, UniformInitializer
from nsgablack.units import UnitBinding
from benchmarks.modification_tasks import AgeBuilder
from tests.test_population_member_operations import AgeReferenceBuilder
from tests.test_pool_parent_selection import Sphere, publish_elites


@dataclass(frozen=True)
class SlotParents:
    slots: tuple = (1, 0)
    stateless = True

    def checkpoint_identity(self):
        return {"slots": self.slots}

    def select(self, request, *, pool, rng):
        return request.members.take(tuple(self.slots[i % len(self.slots)] for i in range(request.count)))


@dataclass(frozen=True)
class ReferenceParents:
    external: bool = False
    stateless = True

    def checkpoint_identity(self):
        return {"external": self.external}

    def select(self, request, *, pool, rng):
        second = pool.subpool_refs("elite")[0] if self.external else request.population_refs[0]
        return (request.population_refs[0], second)


def age_aware_change(request, *, rng):
    ages = request.parent_pool.member_field("age", default=-1)
    # Deliberately order-sensitive: equal candidate values with different
    # member ages produce different proposals for (slot1, slot0) vs (slot0, slot1).
    return request.parents[0] + (10*ages[0] + ages[1]) / 100


def make_solver(selector=None, adapter_type=NSGA2Adapter):
    adapter = adapter_type(population_size=4, offspring_size=2,
        parent_selector=selector or SlotParents(), change=age_aware_change,
        unit_binding=UnitBinding(AgeReferenceBuilder() if adapter_type is NSGA3Adapter else AgeBuilder()))
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(2., 2.)))
    solver.set_random_seed(47)
    return solver


def install_repeated_members(solver):
    refs = solver.adapter.get_population_solution_refs(solver)
    refs = (refs[0], refs[0], refs[1], refs[2])
    f, v = solver.solution_pool.read_raw_feedback(refs)
    solver.adapter.set_population_state(solver, solver.read_solutions(refs),
        OptimizationFeedbackBatch.from_arrays(f, v), solution_refs=refs,
        provenance=solver.solution_pool.read_provenance(refs))
    solver.adapter.algorithm_unit.age = np.array([1, 5, 2, 3])
    return refs


@pytest.mark.parametrize("adapter_type", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter])
def test_repeat_slots_deliver_ordered_attributes_and_scopes_close(adapter_type, monkeypatch):
    solver = make_solver(adapter_type=adapter_type)
    solver.setup()
    try:
        assert solver.step().committed
        refs = install_repeated_members(solver)
        operation = solver.adapter.get_bound_change()
        original = operation.change
        seen = []
        def observe(request, *, rng):
            from dataclasses import replace
            seen.append(request)
            assert request.parent_member_indices == (1, 0)
            assert request.parent_pool.refs == (refs[0], refs[0])
            assert request.parent_pool.member_field("age").tolist() == [5, 1]
            with pytest.raises(ValueError):
                request.parent_pool.member_field("age").setflags(write=True)
            with pytest.raises(ValueError, match="disagree with parent_pool"):
                replace(request, parent_member_indices=(0, 1))
            return original(request, rng=rng)
        monkeypatch.setattr(operation, "change", observe)
        assert solver.step().committed
        assert len(seen) == 2
        np.testing.assert_allclose(solver._last_evaluated_event_batch.numeric_matrix, [[2.51], [2.51]])
        for record in solver._last_evaluated_event_provenance:
            assert tuple(record.metadata["parent_member_indices"]) == (1, 0)
        for request in seen:
            with pytest.raises(RuntimeError, match="ended"):
                request.parent_pool.member_field("age")
    finally:
        solver.teardown()


def test_legacy_ambiguous_refs_fail_before_evaluation_and_rollback():
    solver = make_solver(selector=ReferenceParents())
    solver.setup()
    try:
        assert solver.step().committed
        install_repeated_members(solver)
        before = solver.adapter.get_state()
        count = solver.evaluation_count
        with pytest.raises(ValueError, match="multiple member slots"):
            solver.step()
        assert solver.adapter.get_state() == before
        assert solver.evaluation_count == count
    finally:
        solver.teardown()


def test_native_tournament_keeps_slots_and_numeric_variation_keeps_provenance(monkeypatch):
    solver = make_solver()
    solver.adapter.set_parent_selector(None)
    solver.setup()
    try:
        assert solver.step().committed
        install_repeated_members(solver)
        positions = iter((1, 0, 0, 1))
        monkeypatch.setattr(solver.adapter, "_tournament_pick", lambda: next(positions))
        assert solver.step().committed
        np.testing.assert_allclose(solver._last_evaluated_event_batch.numeric_matrix, [[2.51], [2.15]])
        # The ordinary crossover/mutator path accepts the same explicit member
        # Pool result and retains the selected slots in proposal provenance.
        solver.adapter.set_change(None)
        solver.adapter.set_parent_selector(SlotParents())
        assert solver.step().committed
        for record in solver._last_evaluated_event_provenance:
            assert tuple(record.metadata["parent_member_indices"]) == (1, 0)
    finally:
        solver.teardown()


def test_external_parent_default_and_nonprefix_admission(monkeypatch):
    solver = make_solver(selector=ReferenceParents(external=True))
    solver.setup()
    try:
        assert solver.step().committed
        publish_elites(solver)
        solver.adapter.algorithm_unit.age[:] = 3
        operation = solver.adapter.get_bound_change()
        original = operation.change
        def observe(request, *, rng):
            assert request.parent_member_indices == (0, None)
            with pytest.raises(ValueError, match="specify default"):
                request.parent_pool.member_field("age")
            assert request.parent_pool.member_field("age", default=-1).tolist() == [3, -1]
            return original(request, rng=rng)
        monkeypatch.setattr(operation, "change", observe)
        class SecondOnly:
            def select(self, candidates, feedback, context):
                return BatchDisposition(len(candidates.semantic_states), (1,))
        solver.set_evaluation_acceptance_policy(SecondOnly())
        assert solver.step().committed
        assert solver.evaluation_count == 6
        assert solver._last_evaluated_event_batch.numeric_matrix.shape == (2, 1)
    finally:
        solver.teardown()


def test_parent_field_handoff_restores_without_replaying_and_failure_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "parent-member-test")
    source, restored = make_solver(), make_solver()
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer, reader = CheckpointResumePlugin(config=config), CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    restored.add_plugin(reader)
    source.setup()
    try:
        assert source.step().committed
        install_repeated_members(source)
        saved_ages = source.adapter.algorithm_unit.age.copy()
        path = writer.save_checkpoint(reason="parent-slots")
        assert reader.resume(str(path))
        restored.run(max_steps=0)
        assert restored.problem.seen == []
        np.testing.assert_array_equal(restored.adapter.algorithm_unit.age, saved_ages)
        before = source.adapter.get_state()
        source.problem.fail = True
        with pytest.raises(RuntimeError, match="intentionally failed"):
            source.step()
        assert source.adapter.get_state() == before
        source.problem.fail = False
        assert source.step().committed and restored.step().committed
        np.testing.assert_allclose(source._last_evaluated_event_batch.numeric_matrix,
                                   restored._last_evaluated_event_batch.numeric_matrix)
        np.testing.assert_array_equal(source.adapter.algorithm_unit.age, restored.adapter.algorithm_unit.age)
    finally:
        source.teardown()
        restored.teardown()


def test_standard_scaffold_age_recipe_assembles_and_runs():
    from tests.test_operation_catalog_and_scaffold import load_example
    example = load_example()
    solver = make_solver()
    solver.adapter.set_parent_selector(example.YoungMemberParents())
    solver.adapter.set_change(example.age_scaled_change)
    solver.setup()
    try:
        assert solver.step().committed
        solver.adapter.algorithm_unit.age[:] = 3  # Exercise no-young fallback.
        assert solver.step().committed
        assert solver.evaluation_count == 6
        for record in solver._last_evaluated_event_provenance:
            assert len(record.metadata["parent_member_indices"]) == 2
    finally:
        solver.teardown()
