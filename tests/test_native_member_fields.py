"""One member rule through unmodified native propose/update and file restore."""
from dataclasses import dataclass, field
import numpy as np
import pytest
from blackbase.types import UnknownState
from nsgablack.adapters import NSGA2Adapter, DifferentialEvolutionAdapter, MOEADAdapter
from nsgablack.core import ComposableSolver
from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
from nsgablack.representation import (RepresentationPipeline, UniformInitializer, ContextGaussianMutation,
    ClipRepair, PopulationUnitBuilder, DifferentialPopulationBuilder, DecompositionUnitBuilder)
from nsgablack.units import PopulationUnit, DifferentialPopulationUnit, DecompositionUnit, UnitSchema, UnitBinding
from tests.test_pool_final_members_maintenance import MaintenanceSphere


class TaggedInitializer(UniformInitializer):
    def initialize(self, problem, context=None):
        x = super().initialize(problem, context)
        return UnknownState(x, {"source_label": int(abs(x[0]) * 1000000)})


class SemanticClipRepair(ClipRepair):
    def repair(self, x, context=None):
        if isinstance(x, UnknownState):
            return UnknownState(super().repair(x.values, context), dict(x.metadata))
        return super().repair(x, context)


@dataclass
class TrackedPopulation(PopulationUnit):
    origin_labels: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    birth_values: np.ndarray = field(default_factory=lambda: np.zeros(0))
    member_fields = ("origin_labels", "birth_values")
    schema = UnitSchema("test.tracked_population", required_fields=(
        *PopulationUnit.schema.required_fields, *member_fields), candidate_projection=False)

    def on_members_changed(self, change):
        labels, values = [], []
        for old, incoming in zip(change.previous_member_indices, change.incoming_member_indices):
            labels.append(self.origin_labels[old] if old is not None
                          else change.incoming_metadata[incoming]["source_label"])
            values.append(self.birth_values[old] if old is not None
                          else change.incoming_population[incoming, 0])
        return {"origin_labels": np.asarray(labels, dtype=int), "birth_values": np.asarray(values)}


@dataclass
class TrackedDE(DifferentialPopulationUnit, TrackedPopulation):
    schema = UnitSchema("test.tracked_de", required_fields=(
        *DifferentialPopulationUnit.schema.required_fields, *TrackedPopulation.member_fields), candidate_projection=False)


@dataclass
class TrackedMOEAD(DecompositionUnit, TrackedPopulation):
    schema = UnitSchema("test.tracked_moead", required_fields=(
        *DecompositionUnit.schema.required_fields, *TrackedPopulation.member_fields), candidate_projection=False)


class TrackedBuilder(PopulationUnitBuilder):
    unit_type = TrackedPopulation
    compatible_schemas = (PopulationUnit.schema,)


class TrackedDEBuilder(DifferentialPopulationBuilder):
    unit_type = TrackedDE
    compatible_schemas = (DifferentialPopulationUnit.schema,)


class TrackedMOEADBuilder(DecompositionUnitBuilder):
    unit_type = TrackedMOEAD
    compatible_schemas = (DecompositionUnit.schema,)


def assert_members(solver):
    adapter, unit = solver.adapter, solver.adapter.algorithm_unit
    members = solver.read_solutions(adapter.get_population_solution_refs(solver))
    np.testing.assert_array_equal(unit.origin_labels,
        [state.metadata["source_label"] for state in members.semantic_states])
    np.testing.assert_array_equal(unit.birth_values, members.numeric_matrix[:, 0])
    assert np.any(unit.origin_labels != 0)
    unit.validate()


@pytest.mark.parametrize("adapter_type,builder", [
    (NSGA2Adapter, TrackedBuilder), (DifferentialEvolutionAdapter, TrackedDEBuilder),
    (MOEADAdapter, TrackedMOEADBuilder)])
def test_native_search_preserves_custom_fields_through_file_restore(adapter_type, builder, tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "native-members-test")
    def make():
        adapter = adapter_type(population_size=4, unit_binding=UnitBinding(builder()))
        pipeline = RepresentationPipeline(initializer=TaggedInitializer(.25, .75),
            mutator=ContextGaussianMutation(base_sigma=.1), repair=SemanticClipRepair(0., 1.))
        control = ComposableSolver(MaintenanceSphere(objectives=2), adapter=adapter, representation_pipeline=pipeline)
        control.set_random_seed(53)
        return control
    source, target = make(), make()
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer, reader = CheckpointResumePlugin(config=config), CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    target.add_plugin(reader)
    source.setup()
    try:
        for _ in range(4):
            assert source.step().committed
            assert_members(source)
        checkpoint = writer.save_checkpoint(reason="native-members")
        assert reader.resume(str(checkpoint))
        target.run(max_steps=1)
        assert source.step().committed
        assert_members(source)
        assert_members(target)
        for name in ("population", "origin_labels", "birth_values"):
            np.testing.assert_array_equal(getattr(source.adapter.algorithm_unit, name),
                                          getattr(target.adapter.algorithm_unit, name))
    finally:
        source.teardown()
