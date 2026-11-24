from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import UnknownState
from blackbase.representation import RepresentationCapabilities

from nsgablack.adapters import AStarAdapter, AStarConfig, VNSAdapter, VNSConfig, CompositeAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import CandidateUnitBuilder, SearchNodeBuilder, build_pipeline_kernel
from nsgablack.units import UnitBinding, UnitBuildRequest, SearchNodeUnit


@dataclass(frozen=True)
class TaggedNode(SearchNodeUnit):
    tag: str = "custom"


class TaggedNodeBuilder(SearchNodeBuilder):
    def build(self, request, context=None):
        node = super().build(request, context)
        return TaggedNode(**node.__dict__, tag="domain-node")

    def dump(self, unit):
        return {**super().dump(unit), "tag": unit.tag}

    def restore(self, payload):
        node = super().restore(payload)
        return TaggedNode(**node.__dict__, tag=payload["tag"])


class Control:
    representation_pipeline = SimpleNamespace(
        representation_capabilities=RepresentationCapabilities(frozenset({"mutate"})),
        mutate=lambda value, context=None: value,
        mutator=SimpleNamespace(sigma_key="mutation_sigma"),
    )

    def init_candidate(self, context):
        return np.array([2.0])

    def mutate_candidate(self, candidate, context):
        return np.asarray(candidate) - 0.1

    def repair_candidate(self, candidate, context):
        return candidate


def graph_adapter(**kwargs):
    return AStarAdapter(neighbors=lambda x, ctx: [x + 1, x + 2],
                        start_state=np.array([0.0]), **kwargs)


def test_candidate_unit_preserves_ml_semantics_and_codec():
    binding = UnitBinding(CandidateUnitBuilder())
    state = UnknownState([1.0, 2.0], {"layout": {"layers": [2, 1]}, "kind": "model"})
    unit = binding.build(UnitBuildRequest("candidate:1", state))
    restored = binding.restore(binding.dump(unit))
    assert restored.to_candidate().as_dict() == state.as_dict()
    assert restored.unit_id == unit.unit_id
    np.testing.assert_array_equal(state.as_array(), [1, 2])


def test_unit_builder_cannot_repair_candidate_or_drop_semantics():
    class ChangingBuilder(CandidateUnitBuilder):
        def build(self, request, context=None):
            return super().build(replace(request, candidate=np.array([9.0])))

    with pytest.raises(ValueError, match="preserve the candidate"):
        UnitBinding(ChangingBuilder()).build(UnitBuildRequest("x", np.array([1.0])))

    class DroppingBuilder(CandidateUnitBuilder):
        def build(self, request, context=None):
            return super().build(replace(request, candidate=request.candidate.as_array()))

    with pytest.raises(ValueError, match="semantic metadata"):
        UnitBinding(DroppingBuilder()).build(UnitBuildRequest("x", UnknownState([1], {"kind": "model"})))


def test_schema_mismatch_fails_at_adapter_assembly():
    with pytest.raises(ValueError, match="schema mismatch"):
        graph_adapter(unit_binding=UnitBinding(CandidateUnitBuilder()))


def test_kernel_build_slot_constructs_nodes_and_restore_does_not_run_pipeline():
    builder = TaggedNodeBuilder()
    kernel = build_pipeline_kernel(
        {"slots": [{"slot": "build_unit", "operators": ["node"], "method": "build"}]},
        operator_registry={"node": builder},
    )
    binding = kernel.bind_units(builder, name="test.node-pipeline/v1")
    adapter = graph_adapter(unit_binding=binding)
    adapter.setup(Control())
    node = adapter._open[0][2]
    assert isinstance(node, TaggedNode)
    assert node.tag == "domain-node"
    saved = binding.dump(node)
    # Restore uses the codec, so an unavailable construction runner is harmless.
    restored_binding = UnitBinding(builder, runner=lambda *a: pytest.fail("reconstructed during restore"),
                                   name="test.node-pipeline/v1")
    assert restored_binding.restore(saved).tag == "domain-node"


def test_missing_kernel_slot_and_changed_restore_binding_fail_closed():
    kernel = build_pipeline_kernel({"slots": []}, operator_registry={})
    with pytest.raises(ValueError, match="Missing Unit"):
        kernel.bind_units(CandidateUnitBuilder(), name="missing/v1")
    binding = UnitBinding(CandidateUnitBuilder(), name="original/v1")
    unit = binding.build(UnitBuildRequest("x", np.array([1.])))
    with pytest.raises(ValueError, match="differs"):
        UnitBinding(CandidateUnitBuilder(), name="changed/v2").restore(binding.dump(unit))


def test_astar_rollback_preserves_custom_node_frontier_and_identity():
    adapter = graph_adapter(unit_binding=UnitBinding(TaggedNodeBuilder()))
    control = Control()
    adapter.setup(control)
    before_id = adapter._open[0][2].unit_id
    transaction = adapter.begin_step_transaction()
    candidates = adapter.propose(control, {})
    adapter.update(control, candidates, (np.zeros((2, 1)), np.zeros(2)), {})
    assert adapter._closed
    transaction.rollback()
    assert not adapter._closed
    assert not adapter._pending
    assert len(adapter._open) == 1
    assert adapter._open[0][2].unit_id == before_id
    assert adapter._open[0][2].tag == "domain-node"
    assert adapter.best_state is None
    assert adapter._counter == 1


def test_astar_repair_requires_explicit_edge_policy():
    control = Control()
    adapter = graph_adapter()
    adapter.setup(control)
    adapter.propose(control, {})
    with pytest.raises(ValueError, match="parent edge"):
        adapter.update(control, [np.array([3.]), np.array([2.])],
                       (np.zeros((2, 1)), np.zeros(2)), {})
    recompute = graph_adapter(config=AStarConfig(repair_policy="recompute"),
                             edge_cost=lambda a, b, ctx: float(abs(b[0] - a[0])))
    recompute.setup(control)
    recompute.propose(control, {})
    recompute.update(control, [np.array([3.]), np.array([2.])],
                     (np.zeros((2, 1)), np.zeros(2)), {})
    costs = {node.state[0]: node.g for _, _, node in recompute._open}
    assert costs == {2.0: 2.0, 3.0: 3.0}


def test_astar_disposition_keeps_parent_unit_association():
    adapter = graph_adapter()
    control = Control()
    adapter.setup(control)
    parent_id = adapter._open[0][2].unit_id
    candidates = adapter.propose(control, {})
    adapter.on_proposal_disposition(control, BatchDisposition(proposed_count=2, accepted_indices=(1,)), {})
    adapter.update(control, candidates[1:], (np.zeros((1, 1)), np.zeros(1)), {})
    child = adapter._open[0][2]
    assert child.parent_id == parent_id
    np.testing.assert_array_equal(child.state, [2.0])


def test_vns_adopts_mapped_unit_and_checkpoint_preserves_semantics():
    control = Control()
    adapter = VNSAdapter(VNSConfig(batch_size=3))
    adapter.setup(control)
    adapter.current_x = UnknownState([2.0], {"layout": "linear"})
    baseline = adapter.propose(control, {})
    assert len(baseline) == 1
    adapter.update(control, baseline, (np.array([[4.]]), np.zeros(1)), {})
    candidates = adapter.propose(control, {})
    expected = adapter._pending_units[2]
    adapter.on_proposal_disposition(control, BatchDisposition(proposed_count=3, accepted_indices=(0, 2)), {})
    adapter.update(control, [candidates[0], candidates[2]], (np.array([[2.], [1.]]), np.zeros(2)), {})
    assert adapter.current_unit is expected
    restored = VNSAdapter(VNSConfig(batch_size=3))
    restored.setup(control)
    restored.set_state(adapter.get_state())
    assert restored.current_unit.unit_id == expected.unit_id
    assert restored.current_unit.to_candidate().as_dict()["metadata"] == {"layout": "linear"}


def test_vns_rollback_can_clear_fresh_unit():
    adapter = VNSAdapter(VNSConfig(batch_size=2))
    adapter.setup(Control())
    transaction = adapter.begin_step_transaction()
    adapter.propose(Control(), {})
    transaction.rollback()
    assert adapter.current_unit is None
    assert adapter._unit_counter == 0
    assert adapter._pending_units == []


def test_composite_operates_heterogeneous_unit_bindings(sample_problem):
    from nsgablack.representation import RepresentationPipeline, UniformInitializer, ContextGaussianMutation

    graph = AStarAdapter(neighbors=lambda x, ctx: [x + 1], start_state=np.array([0., 0.]),
                        unit_binding=UnitBinding(TaggedNodeBuilder()))
    trajectory = VNSAdapter(VNSConfig(batch_size=2))
    root = CompositeAdapter([graph, trajectory])
    solver = ComposableSolver(problem=sample_problem, adapter=root, representation_pipeline=RepresentationPipeline(
        initializer=UniformInitializer(low=-2, high=2), mutator=ContextGaussianMutation(base_sigma=0.1),
    ))
    result = solver.run(max_steps=2)
    assert result["status"] == "ok"
    assert isinstance(graph._open[0][2], TaggedNode)
    assert trajectory.current_unit.schema != graph.unit_schema
    assert graph.get_unit_contract()["binding"].endswith("TaggedNodeBuilder")
    assert len(root.get_unit_contracts()) == 2


def test_solver_failure_rolls_back_astar_unit(sample_problem):
    adapter = AStarAdapter(neighbors=lambda x, ctx: [x + 1], start_state=np.array([0., 0.]))
    solver = ComposableSolver(problem=sample_problem, adapter=adapter)
    def fail(candidate):
        raise RuntimeError("deliberate evaluation failure")
    sample_problem.evaluate = fail
    with pytest.raises(RuntimeError, match="deliberate evaluation"):
        solver.run(max_steps=1)
    assert len(adapter._open) == 1
    np.testing.assert_array_equal(adapter._open[0][2].state, [0, 0])
    assert not adapter._closed
    assert adapter._counter == 1


def test_doctor_and_solver_share_nested_binding_validation(sample_problem):
    from nsgablack.project.doctor_core.rules.build_solver import check_unit_bindings
    from nsgablack.project.doctor_core.model import add_diagnostic
    from nsgablack.utils.extension_contracts import ContractError

    child = graph_adapter()
    child.unit_binding = UnitBinding(CandidateUnitBuilder())  # simulate broken assembly
    root = CompositeAdapter([child])
    diagnostics = []
    check_unit_bindings(solver=SimpleNamespace(adapter=root), build_file=None,
                        diags=diagnostics, add=add_diagnostic)
    assert diagnostics[0].code == "adapter-unit-binding-invalid"
    solver = ComposableSolver(problem=sample_problem)
    with pytest.raises(ContractError, match="schema mismatch"):
        solver.set_adapter(root)


def test_builder_cannot_mutate_request_candidate_in_place():
    class InPlaceBuilder(CandidateUnitBuilder):
        def build(self, request, context=None):
            request.candidate[0] = 9.0
            return super().build(request, context)

    original = np.array([1.0])
    with pytest.raises(ValueError, match="read-only"):
        UnitBinding(InPlaceBuilder()).build(UnitBuildRequest("x", original))
    np.testing.assert_array_equal(original, [1.0])


def test_candidate_build_request_detaches_costs_and_nested_data():
    costs = np.array([1.0, 2.0])
    metadata = {"path": ["start"]}
    request = UnitBuildRequest("label:1", np.array([0.0]), parameters={
        "g": costs, "metadata": metadata, "parent_key": b"start"})
    with pytest.raises(ValueError, match="read-only"):
        request.parameters["g"][0] = 99.0
    request.parameters["metadata"]["path"].append("child")
    np.testing.assert_array_equal(costs, [1.0, 2.0])
    assert metadata == {"path": ["start"]}
    assert request.parameters["parent_key"] == b"start"


def test_vns_failed_restore_leaves_current_unit_unchanged():
    adapter = VNSAdapter(VNSConfig(batch_size=1))
    adapter.setup(Control())
    adapter.current_x = np.array([4.0])
    before = adapter.current_unit
    saved = adapter.get_state()
    saved["unit_counter"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        adapter.set_state(saved)
    assert adapter.current_unit is before
    assert adapter._unit_counter == 1
