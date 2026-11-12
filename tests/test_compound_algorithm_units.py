from __future__ import annotations

import json
import importlib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.project import case_import_context
from nsgablack import adapters
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.units import UnitBinding, StructureBuildRequest, PopulationUnit
from nsgablack.representation import (
    PopulationUnitBuilder, ReferencePopulationBuilder, RegionUnitBuilder,
    ParameterUnitBuilder, NeighborhoodUnitBuilder,
)
from nsgablack.representation.structure_builders import encode_unit_value


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, objectives=["minimize", "minimize"], bounds=[(-5, 5)] * 2)

    def evaluate(self, x):
        return np.array([np.sum(np.asarray(x) ** 2), np.sum((np.asarray(x) - 1) ** 2)])


FACTORIES = [
    lambda: adapters.SimulatedAnnealingAdapter(batch_size=2),
    lambda: adapters.SingleTrajectoryAdaptiveAdapter(batch_size=2),
    lambda: adapters.PatternSearchAdapter(max_directions=2),
    lambda: adapters.GradientDescentAdapter(max_directions=2),
    lambda: adapters.GaussianSearchAdapter(population_size=4),
    lambda: adapters.FixedCandidateAdapter(),
    lambda: adapters.VNSAdapter(batch_size=2),
    lambda: adapters.NSGA2Adapter(population_size=4, offspring_size=4),
    lambda: adapters.NSGA3Adapter(population_size=4, offspring_size=4, divisions=2),
    lambda: adapters.SPEA2Adapter(population_size=4, offspring_size=4),
    lambda: adapters.DifferentialEvolutionAdapter(population_size=4, batch_size=2),
    lambda: adapters.MOEADAdapter(population_size=4, batch_size=2, neighborhood_size=2),
    lambda: adapters.TrustRegionDFOAdapter(batch_size=2),
    lambda: adapters.TrustRegionMODFOAdapter(batch_size=2),
    lambda: adapters.TrustRegionNonSmoothAdapter(batch_size=2),
    lambda: adapters.TrustRegionSubspaceAdapter(batch_size=2, subspace_dim=1),
    lambda: adapters.MASAdapter(batch_size=2, enable_surrogate=False),
]


@pytest.mark.parametrize("factory", FACTORIES)
def test_core_families_operate_units_and_roundtrip_after_real_steps(factory):
    adapter = factory()
    solver = ComposableSolver(problem=Problem(), adapter=adapter)
    result = solver.run(max_steps=2)
    assert result["status"] == "ok"
    assert adapter.get_unit_contracts()
    saved = adapter.get_state()
    # Real serialization boundary, not merely deepcopy of Python instances.
    saved = json.loads(json.dumps(saved))
    clone = factory()
    clone.set_state(saved)
    assert clone.get_unit_contract() == adapter.get_unit_contract()
    assert encode_unit_value(clone.get_state()) == encode_unit_value(adapter.get_state())


@dataclass
class TaggedPopulation(PopulationUnit):
    tag: str = "pipeline-defined"


class TaggedPopulationBuilder(PopulationUnitBuilder):
    unit_type = TaggedPopulation


def test_population_unit_is_the_only_adapter_array_authority_and_restores_custom_fields():
    binding = UnitBinding(TaggedPopulationBuilder())
    adapter = adapters.NSGA2Adapter(unit_binding=binding)
    adapter.set_population_snapshot(np.array([[1., 2.]]), np.array([[3.]]), np.array([0.]))
    adapter.set_population_candidate_tokens(("semantic-row-a",))
    assert adapter.population is adapter.algorithm_unit.population
    adapter.algorithm_unit.population[0, 0] = 7
    assert adapter.get_population_snapshot()[0][0, 0] == 7
    # Candidate replacement invalidates the old evaluation; attach feedback
    # for the new row before asking a restored Adapter to rank it.
    adapter.objectives = np.array([[53.]])
    adapter.violations = np.array([0.])
    checkpoint = json.loads(json.dumps(adapter.get_state()))
    clone = adapters.NSGA2Adapter(unit_binding=binding)
    clone.set_state(checkpoint)
    assert clone.algorithm_unit.tag == "pipeline-defined"
    assert clone.get_population_candidate_tokens() == ("semantic-row-a",)
    transaction = clone.begin_step_transaction()
    clone.algorithm_unit.tag = "changed"
    clone.population[0] = 99
    transaction.rollback()
    assert clone.algorithm_unit.tag == "pipeline-defined"
    assert clone.population[0, 0] == 7


def test_compound_builder_cannot_mutate_previous_population_on_failure():
    class Broken(PopulationUnitBuilder):
        def build(self, request, context=None):
            request.parameters["values"]["population"][0, 0] = -99
    adapter = adapters.NSGA2Adapter()
    adapter.population = np.array([[1., 2.]])
    with pytest.raises(ValueError, match="read-only"):
        adapter.set_unit_binding(UnitBinding(Broken()))
    assert adapter.population.tolist() == [[1., 2.]]


def test_nsga3_consumes_pipeline_directions_and_restores_without_reconstruction():
    class Directions(ReferencePopulationBuilder):
        def construct(self, values, operation, parameters, context):
            super().construct(values, operation, parameters, context)
            if operation == "reference_directions":
                values["reference_points"] = np.array([[0.25, 0.75], [0.75, 0.25]])
    binding = UnitBinding(Directions(), name="custom/directions/v1")
    adapter = adapters.NSGA3Adapter(unit_binding=binding, divisions=2)
    control = ComposableSolver(problem=Problem(), adapter=adapter)
    control.setup()
    assert adapter.algorithm_unit is None
    adapter.propose(control, {})
    assert adapter.reference_points.tolist() == [[0.25, 0.75], [0.75, 0.25]]
    saved = adapter.get_state()
    clone = adapters.NSGA3Adapter(unit_binding=binding)
    clone.unit_binding = UnitBinding(Directions(), runner=lambda *a: pytest.fail("restore rebuilt directions"), name="custom/directions/v1")
    clone.set_state(saved)
    np.testing.assert_array_equal(clone.reference_points, adapter.reference_points)
    from nsgablack.context_keys import KEY_MO_WEIGHTS
    np.testing.assert_array_equal(clone.get_runtime_context_projection(None)[KEY_MO_WEIGHTS], adapter.reference_points)


def test_optimizer_pipeline_allocates_slots_but_adapter_executes_adam_formula():
    class Slots(ParameterUnitBuilder):
        def construct(self, values, operation, parameters, context):
            super().construct(values, operation, parameters, context)
            if operation == "optimizer_slots":
                values["first_moment"][:] = 1
                values["second_moment"][:] = 2
    adapter = adapters.GradientOptimizerAdapter(optimizer="adam", unit_binding=UnitBinding(Slots()))
    adapter.current_x = np.array([1., 2.])
    adapter._optimizer_delta(adapter.current_x, np.array([2., 3.]))
    np.testing.assert_allclose(adapter.algorithm_unit.first_moment, [1.1, 1.2])
    np.testing.assert_allclose(adapter.algorithm_unit.second_moment, [2.002, 2.007])


def test_subspace_adapter_uses_pipeline_basis_and_unit_codec():
    class Basis(RegionUnitBuilder):
        def make_basis(self, parameters):
            return np.array([[1.], [0.]]), "custom-axis"
    adapter = adapters.TrustRegionSubspaceAdapter(unit_binding=UnitBinding(Basis()), subspace_dim=1, batch_size=3)
    control = SimpleNamespace(dimension=2, init_candidate=lambda context: np.zeros(2), problem=Problem())
    baseline = adapter.propose(control, {})
    assert len(baseline) == 1 and adapter.algorithm_unit.basis is None
    adapter._best_score = 1.  # The following call exercises geometry after baseline feedback.
    proposals = adapter.propose(control, {})
    assert all(row[1] == 0 for row in proposals)
    assert adapter.algorithm_unit.basis_method == "custom-axis"
    clone = adapters.TrustRegionSubspaceAdapter(unit_binding=UnitBinding(Basis()))
    clone.set_state(json.loads(json.dumps(adapter.get_state())))
    np.testing.assert_array_equal(clone.algorithm_unit.basis, [[1.], [0.]])


def test_vns_neighborhood_builder_changes_geometry_without_changing_acceptance():
    class Neighborhoods(NeighborhoodUnitBuilder):
        def construct(self, values, operation, parameters, context):
            values["scales"] = (0.1, 0.7)
    adapter = adapters.VNSAdapter(k_max=1, neighborhood_binding=UnitBinding(Neighborhoods()))
    adapter.k = 1
    assert adapter._current_sigma() == 0.7
    saved = adapter.get_state()
    clone = adapters.VNSAdapter(k_max=1, neighborhood_binding=UnitBinding(Neighborhoods()))
    clone.set_state(saved)
    assert clone._current_sigma() == 0.7


def test_finite_difference_uses_repaired_coordinate_distance_and_rejects_coupled_repair():
    control = SimpleNamespace(init_candidate=lambda c: np.array([0.]),
                              repair_candidate=lambda x, c: np.maximum(x, 0))
    adapter = adapters.GradientDescentAdapter(epsilon=0.5, learning_rate=0.1)
    baseline = adapter.propose(control, {})
    adapter.update(control, baseline, (np.zeros((1, 1)), np.zeros(1)), {})
    candidates = adapter.propose(control, {})
    candidates = [control.repair_candidate(x, {}) for x in candidates]
    adapter.update(control, candidates, (np.array([[1.], [0.]]), np.zeros(2)), {})
    # One-sided difference is 1/0.5, so the unrepaired step would be -0.2.
    assert adapter.algorithm_unit.displacements.tolist() == [[0.5], [0.0]]
    assert adapter.current_x[0] == 0.0 and adapter.current_score == 0.0
    assert adapter._trial_values[0] == -0.2  # Still unassessed, not a proxy-scored center.
    adapter = adapters.GradientDescentAdapter(epsilon=0.5)
    adapter.current_x = np.zeros(2)
    adapter._pending_probes = [(0, 1), (0, -1)]
    with pytest.raises(ValueError, match="coordinate geometry"):
        adapter.update(control, [np.array([0.5, 1.]), np.array([-0.5, 0.])],
                       (np.ones((2, 1)), np.zeros(2)), {})


def test_elite_replacement_rejects_nested_structural_proposals_before_propose():
    inner = adapters.CompositeAdapter([adapters.GradientDescentAdapter()])
    elite = adapters.EliteRetentionAdapter(inner)
    with pytest.raises(ValueError, match="structurally bound"):
        ComposableSolver(problem=Problem(), adapter=elite)


def test_moa_label_parent_identity_and_full_durable_restore():
    factory = lambda: adapters.MOAStarAdapter(neighbors=lambda x, c: [x + 1], start_state=np.zeros(2))
    adapter = factory()
    adapter.setup(SimpleNamespace(num_objectives=2))
    parent_id = adapter._labels[1].unit_id
    candidates = adapter.propose(None, {})
    adapter.update(None, candidates, (np.array([[0., 2.]]), np.zeros(1)), {})
    assert adapter._labels[2].parent_id == parent_id
    clone = factory()
    clone.set_state(json.loads(json.dumps(adapter.get_state())))
    assert clone._labels[2].parent_id == parent_id
    assert clone._open == adapter._open


def test_renamed_strategy_instance_preserves_compatibility_alias():
    from nsgablack.adapters.multi_strategy import StrategyInstanceSpec, UnitSpec
    assert UnitSpec is StrategyInstanceSpec


def test_formal_unit_cases_assemble_real_builders_and_run():
    from nsgablack.examples.cases.algorithm_units.cases.candidate_search.build_solver import build_solver as candidates
    from nsgablack.examples.cases.algorithm_units.cases.symbolic_beam.build_solver import build_solver as beam
    for solver in (candidates({"max_steps": 1}), beam({"generations": 1, "n_train": 16, "n_valid": 8,
                     "n_candidates": 8, "true_terms": 2, "beam_width": 2, "max_candidates": 4})):
        assert "algorithm_units." in str(solver.adapter.get_unit_contract())
        result = solver.run(max_steps=1)
        assert solver.best_x is not None
        if isinstance(result, dict):
            assert result["status"] == "ok"


def test_schedule_pipeline_builds_pheromone_and_adapter_updates_it_then_restores():
    root = Path(__file__).resolve().parents[1] / "examples" / "cases" / "production_scheduling"
    with case_import_context(root, "production_scheduling"):
        ProductionACOBaselineAdapter = importlib.import_module(
            "cases.production_scheduling.adapter.search_adapters").ProductionACOBaselineAdapter
    problem = SimpleNamespace(machines=2, days=2, machine_weights=np.ones(2),
        data=SimpleNamespace(machines=2, days=2, bom_matrix=np.eye(2), supply_matrix=np.full((2, 2), 5)),
        constraints=SimpleNamespace(max_machines_per_day=2, min_machines_per_day=1,
            min_production_per_machine=1, max_production_per_machine=5))
    control = SimpleNamespace(problem=problem, repair_candidate=lambda x, c: x)
    adapter = ProductionACOBaselineAdapter(ants=2)
    assert adapter.algorithm_unit is None
    candidates = adapter.propose(control, {})
    np.testing.assert_array_equal(adapter.algorithm_unit.pheromone, np.ones((2, 2)))
    adapter.update(control, candidates, (np.array([[1.], [2.]]), np.zeros(2)), {})
    np.testing.assert_allclose(adapter.algorithm_unit.pheromone, np.full((2, 2), 1.3))
    clone = ProductionACOBaselineAdapter(ants=2)
    clone.set_state(json.loads(json.dumps(adapter.get_state())))
    np.testing.assert_array_equal(clone._pheromone, adapter._pheromone)


def test_gmm_warm_start_reads_previous_phase_result_at_first_proposal():
    root = Path(__file__).resolve().parents[1] / "examples" / "cases" / "gmm_em_vs_de"
    with case_import_context(root, "gmm_em_vs_de"):
        WarmStartVNSAdapter = importlib.import_module(
            "cases.gmm_em_vs_de.adapter.warm_start").WarmStartVNSAdapter
    control = SimpleNamespace(best_x=None, init_candidate=lambda c: np.array([-9.]),
        mutate_candidate=lambda x, c: x, repair_candidate=lambda x, c: x)
    adapter = WarmStartVNSAdapter(batch_size=1)
    adapter.setup(control)
    assert adapter.current_unit is None
    control.best_x = np.array([4.])
    np.testing.assert_array_equal(adapter.propose(control, {})[0], [4.])
    assert adapter.current_unit is not None
