"""Unit construction follows actual use, including nested scheduling and restore."""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pytest

from nsgablack.adapters import (
    DifferentialEvolutionAdapter,
    MultiStrategyConfig,
    NSGA2Adapter,
    NSGA3Adapter,
    PoolTaskSpec,
    RoleSpec,
    SerialPhaseSpec,
    StrategyChainAdapter,
    StrategyRouterAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import PopulationUnitBuilder, ReferencePopulationBuilder, RepresentationPipeline
from nsgablack.representation.structure_builders import decode_unit_value, encode_unit_value
from nsgablack.units import PopulationUnit, UnitBinding, UnitSchema
from nsgablack.adapters.unit_backed import UnitBackedAdapter


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimum"], bounds=[(-20.0, 20.0)])
        self.fail = False

    def evaluate(self, candidate):
        if self.fail:
            raise RuntimeError("intentional lazy activation failure")
        return [float(np.asarray(candidate)[0] ** 2)]


class Seeds:
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "lazy-activation-seed/v1"}

    def initialize(self, problem, context):
        return np.array([3.0])

    def mutate(self, candidate, context):
        return np.asarray(candidate) - 0.25


class ObservedPopulationBuilder(PopulationUnitBuilder):
    """Record construction/codec calls without putting services in Unit data."""

    def __init__(self, events):
        self.events = events

    def build(self, request, context=None):
        self.events.append(("build", request.operation, request.unit_id))
        return super().build(request, context)

    def restore(self, payload):
        self.events.append(("restore",))
        return super().restore(payload)


def population(name="ga"):
    events = []
    adapter = NSGA2Adapter(name=name, population_size=4, offspring_size=2,
        crossover_rate=0.0, initializer=Seeds(),
        unit_binding=UnitBinding(ObservedPopulationBuilder(events)))
    return adapter, events


def solver_for(adapter):
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Seeds(), mutator=Seeds()))
    solver.set_random_seed(123)
    solver.setup()
    return solver


def build_calls(events):
    return tuple(event for event in events if event[0] == "build")


def portable(state):
    return decode_unit_value(json.loads(json.dumps(encode_unit_value(state))))


def observe(adapter, control):
    """Supported reporting and snapshots must not start a search structure."""
    adapter.get_unit_contracts()
    adapter.get_operation_contract()
    adapter.get_population_snapshot()
    adapter.get_runtime_context_projection(control)
    adapter.preference_view(owner_path=(adapter.name,))
    adapter.get_state()
    adapter.snapshot_step_state()
    adapter.validate_local_unit_contract()


def test_construction_setup_and_readonly_reporting_leave_unit_absent():
    adapter, events = population()
    assert adapter.algorithm_unit is None
    assert events == []
    solver = solver_for(adapter)
    observe(adapter, solver)
    assert adapter.population is None
    assert adapter.objectives is None
    assert adapter.violations is None
    assert adapter.get_operator_unit() is None
    assert adapter.preference_view(owner_path=(adapter.name,)) is None
    assert adapter.get_unit_id() == "ga:structure"
    assert adapter.algorithm_unit is None
    assert events == []


def test_binding_an_inactive_adapter_changes_only_its_construction_rule():
    adapter, old_events = population()
    new_events = []
    adapter.set_unit_binding(UnitBinding(ObservedPopulationBuilder(new_events)))
    assert adapter.algorithm_unit is None
    assert old_events == new_events == []
    solver = solver_for(adapter)
    observe(adapter, solver)
    assert old_events == new_events == []
    assert solver.step().committed
    assert old_events == []
    assert len(build_calls(new_events)) == 1


def test_first_use_constructs_once_and_later_steps_reuse_the_unit():
    adapter, events = population()
    solver = solver_for(adapter)
    assert solver.step().committed
    unit = adapter.algorithm_unit
    assert unit is not None
    assert len(build_calls(events)) == 1
    assert adapter.ensure_unit() is unit
    for _ in range(3):
        assert solver.step().committed
        assert adapter.algorithm_unit is unit
    assert len(build_calls(events)) == 1


def test_reset_discards_unit_and_preserves_identity_until_next_use():
    adapter, events = population()
    solver = solver_for(adapter)
    assert solver.step().committed
    original_unit = adapter.algorithm_unit
    original_id = original_unit.unit_id
    adapter.reset_unit()
    assert adapter.algorithm_unit is None
    observe(adapter, solver)
    assert len(build_calls(events)) == 1
    fresh = adapter.ensure_unit()
    assert fresh is not original_unit
    assert fresh.unit_id == original_id
    assert fresh.population is None
    assert adapter.ensure_unit() is fresh
    assert len(build_calls(events)) == 2


def test_uncreated_fields_cannot_silently_discard_in_place_writes():
    adapter = DifferentialEvolutionAdapter()
    assert adapter._last_target_indices == []
    with pytest.raises(RuntimeError, match="ensure_unit"):
        adapter._last_target_indices.append(0)
    with pytest.raises(ValueError):
        adapter._last_target_scores.setflags(write=True)
    assert adapter.algorithm_unit is None


def test_default_setup_for_custom_adapter_discards_old_structure_without_building():
    class CustomAdapter(UnitBackedAdapter):
        unit_builder_type = PopulationUnitBuilder
        unit_schema = PopulationUnitBuilder.unit_type.schema

        def propose(self, control, context):
            return ()

        def update(self, control, candidates, feedback, context):
            return None

    events = []
    adapter = CustomAdapter("custom", unit_binding=UnitBinding(ObservedPopulationBuilder(events)))
    adapter.setup(None)
    assert adapter.algorithm_unit is None and events == []
    adapter.ensure_unit().initialize_population([[1.]], [[1.]], [0.])
    original_id = adapter.get_unit_id()
    adapter.setup(None)
    assert adapter.algorithm_unit is None
    assert adapter.get_unit_id() == original_id
    assert len(build_calls(events)) == 1


def test_uncreated_checkpoint_preserves_identity_after_explicit_reset():
    adapter, events = population()
    adapter.ensure_unit().unit_id = "restored:population"
    adapter.reset_unit()
    saved = portable(adapter.get_state())
    assert saved["unit_id"] == "restored:population"
    clone, clone_events = population()
    clone.set_state(saved)
    assert clone.algorithm_unit is None
    assert clone.get_unit_id() == "restored:population"
    assert clone_events == []
    assert clone.ensure_unit().unit_id == "restored:population"
    assert len(build_calls(events)) == len(build_calls(clone_events)) == 1


def test_absent_unit_envelope_rejects_active_population_without_building():
    adapter, events = population()
    saved = portable(adapter.get_state())
    saved.update(population=[[1.]], objectives=[[1.]], violations=[0.], candidate_tokens=["invalid"])
    with pytest.raises(ValueError, match="absent Unit checkpoint"):
        adapter.set_state(saved)
    assert adapter.algorithm_unit is None
    assert events == []


def test_uncreated_checkpoint_and_step_snapshot_restore_without_construction():
    adapter, events = population()
    solver = solver_for(adapter)
    saved = portable(adapter.get_state())
    step = portable(adapter.snapshot_step_state())
    assert saved["algorithm_unit"] is None
    assert saved["unit_contract"]
    adapter.set_state(saved)
    adapter.restore_step_state(step)
    assert adapter.algorithm_unit is None
    assert events == []
    adapter.ensure_unit()
    assert len(build_calls(events)) == 1
    adapter.restore_step_state(step)
    assert adapter.algorithm_unit is None
    assert len(build_calls(events)) == 1


def test_created_checkpoint_uses_codec_without_replaying_builder():
    adapter, events = population()
    solver = solver_for(adapter)
    assert solver.step().committed
    saved = portable(adapter.get_state())
    clone, clone_events = population()
    solver_for(clone)
    clone.set_state(saved)
    assert clone_events == [("restore",)]
    assert clone.algorithm_unit.unit_id == adapter.algorithm_unit.unit_id
    np.testing.assert_array_equal(clone.population, adapter.population)
    assert clone.ensure_unit() is clone.algorithm_unit
    observe(clone, solver)
    assert build_calls(clone_events) == ()
    assert len(build_calls(events)) == 1


def test_failed_first_attempt_rolls_back_to_no_unit_and_retry_builds_once():
    adapter, events = population()
    solver = solver_for(adapter)
    solver.problem.fail = True
    with pytest.raises(RuntimeError, match="intentional lazy activation failure"):
        solver.step()
    assert adapter.algorithm_unit is None
    assert len(build_calls(events)) == 1
    observe(adapter, solver)
    assert len(build_calls(events)) == 1
    solver.problem.fail = False
    assert solver.step().committed
    assert adapter.algorithm_unit is not None
    assert len(build_calls(events)) == 2


def test_serial_phase_setup_and_checkpoint_do_not_construct_later_phase_unit():
    first, first_events = population("first")
    later, later_events = population("later")
    chain = StrategyChainAdapter(phases=[
        SerialPhaseSpec("early", first, steps=1),
        SerialPhaseSpec("late", later),
    ])
    solver = solver_for(chain)
    assert first.algorithm_unit is None and later.algorithm_unit is None
    chain.get_state()
    chain.snapshot_step_state()
    chain.get_unit_contracts()
    chain.get_runtime_context_projection(solver)
    assert first_events == later_events == []
    assert solver.step().committed
    assert len(build_calls(first_events)) == 1
    assert later.algorithm_unit is None
    saved = portable(chain.get_state())
    assert saved["adapters"][1]["algorithm_unit"] is None
    assert later_events == []
    assert solver.step().committed
    assert len(build_calls(later_events)) == 1
    assert solver.step().committed
    assert len(build_calls(later_events)) == 1


def router_with_delayed_role():
    first, first_events = population("first")
    later, later_events = population("later")
    router = StrategyRouterAdapter(roles=[RoleSpec("early", first), RoleSpec("late", later)],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False,
            phase_schedule=(("early_phase", 2), ("late_phase", -1)),
            phase_roles={"early_phase": ["early"], "late_phase": ["late"]}))
    return router, first, later, first_events, later_events


def test_router_role_remains_uncreated_until_dispatched_and_after_portable_restore():
    router, first, later, first_events, later_events = router_with_delayed_role()
    solver = solver_for(router)
    assert first_events == later_events == []
    assert solver.step().committed
    assert len(build_calls(first_events)) == 1
    assert later.algorithm_unit is None
    router.get_unit_contracts()
    router.get_population_partitions()
    router.snapshot_step_state()
    saved = portable(router.get_state())
    assert saved["units"][1]["state"]["algorithm_unit"] is None
    assert later_events == []
    restored, restored_first, restored_later, restored_first_events, restored_later_events = router_with_delayed_role()
    restored_solver = solver_for(restored)
    restored.set_state(saved)
    assert restored_first_events == [("restore",)]
    assert restored_later_events == []
    assert restored_later.algorithm_unit is None
    # Original run crosses the phase boundary; the delayed role builds once.
    assert solver.step().committed
    assert later.algorithm_unit is None
    assert solver.step().committed
    assert len(build_calls(later_events)) == 1
    assert restored_first.algorithm_unit is not None
    assert restored_later.algorithm_unit is None
    assert restored_solver.adapter is restored


def test_waiting_pool_task_does_not_construct_inner_unit_before_inputs_exist():
    source, source_events = population("source")
    worker, worker_events = population("worker")
    router = StrategyRouterAdapter(roles=[
        RoleSpec("source", source),
        RoleSpec("worker", worker, pool_task=PoolTaskSpec(mode="initialize", count=4,
            on_insufficient="wait", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False,
        phase_schedule=(("search", -1),)))
    solver = solver_for(router)
    assert source_events == worker_events == []
    assert solver.step().committed
    assert len(build_calls(source_events)) == 1
    assert worker.algorithm_unit is None
    wrapper = router.units[1].adapter
    wrapper.get_state()
    wrapper.snapshot_step_state()
    assert worker_events == []
    assert solver.step().committed
    assert len(build_calls(worker_events)) == 1


def test_nsga3_reference_geometry_waits_for_first_proposal_and_then_is_reused():
    events = []

    class ReferenceBuilder(ReferencePopulationBuilder):
        def build(self, request, context=None):
            events.append(("build", request.operation, request.unit_id))
            return super().build(request, context)

    adapter = NSGA3Adapter(population_size=4, offspring_size=2, divisions=2,
        initializer=Seeds(), unit_binding=UnitBinding(ReferenceBuilder()))
    solver = solver_for(adapter)
    observe(adapter, solver)
    assert adapter.algorithm_unit is None
    assert adapter.reference_points.shape == (0, 0)
    assert events == []
    assert solver.step().committed
    assert [event[1] for event in events] == ["reference_directions"]
    reference_points = np.array(adapter.reference_points, copy=True)
    assert solver.step().committed
    assert [event[1] for event in events] == ["reference_directions"]
    np.testing.assert_array_equal(adapter.reference_points, reference_points)


def test_custom_member_maintenance_starts_only_when_members_are_installed():
    changes, events = [], []

    @dataclass
    class CustomPopulation(PopulationUnit):
        member_age: tuple = ()
        member_fields = ("member_age",)
        schema = UnitSchema("test.lazy-custom-population", required_fields=(
            *PopulationUnit.schema.required_fields, "member_age"), candidate_projection=False)

        def on_members_changed(self, change):
            changes.append(change.operation)
            return {"member_age": tuple(0 for _ in range(change.count))}

    class CustomBuilder(ObservedPopulationBuilder):
        unit_type = CustomPopulation
        compatible_schemas = (PopulationUnit.schema,)

    adapter = NSGA2Adapter(population_size=4, offspring_size=2, initializer=Seeds(),
        unit_binding=UnitBinding(CustomBuilder(events)))
    solver = solver_for(adapter)
    observe(adapter, solver)
    assert changes == events == []
    assert solver.step().committed
    assert changes == ["initialize"]
    assert len(build_calls(events)) == 1
    assert adapter.algorithm_unit.member_age == (0, 0, 0, 0)
    assert solver.step().committed
    assert changes == ["initialize", "selection"]
    assert len(build_calls(events)) == 1
