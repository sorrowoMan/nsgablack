import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    AlgorithmAdapter, AStarAdapter, AStarConfig, MOAStarAdapter, MOAStarConfig,
    CandidateProposerAdapter, CompositeAdapter, ProposalRepair, RoleAdapter,
    RoleRouterAdapter, TrustRegionDFOAdapter, TrustRegionDFOConfig,
    TrustRegionSubspaceAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.representation import RepresentationPipeline


class Problem(BlackBoxProblem):
    def __init__(self, objectives=1):
        super().__init__(dimension=1, objectives=["minimize"] * objectives, bounds=[(-10, 10)])
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(np.asarray(candidate).copy())
        return np.zeros(self.get_num_objectives())


class ShiftRepair:
    def repair(self, candidate, context=None):
        # Deliberately mutate numeric input; before evidence must stay detached.
        result = np.asarray(candidate)
        result[0] += 2
        return result


def graph(kind, policy="reject"):
    common = dict(neighbors=lambda state, context: [np.array([1.]), np.array([2.])],
                  start_state=np.array([0.]))
    if kind == "astar":
        return AStarAdapter(**common, config=AStarConfig(repair_policy=policy, objective_weight=0),
                            edge_cost=lambda a, b, c: float(abs(b[0] - a[0])),
                            heuristic=lambda x, c: float(x[0] * 10))
    return MOAStarAdapter(**common, config=MOAStarConfig(repair_policy=policy, objective_weight=0, path_cost_mode="edge"),
                          edge_cost=lambda a, b, c: np.array([abs(b[0]-a[0]), 2*abs(b[0]-a[0])]),
                          heuristic=lambda x, c: np.array([x[0]*10, x[0]*20]))


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_graph_repair_rejects_before_evaluation_and_restores_frontier(kind):
    adapter = graph(kind)
    problem = Problem(1 if kind == "astar" else 2)
    solver = ComposableSolver(problem, adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    adapter.setup(solver)
    before = adapter.get_state()
    with pytest.raises(ValueError, match="repair_policy='reject'"):
        solver.step()
    assert problem.calls == []
    assert solver.evaluation_count == 0
    assert adapter.get_state() == before
    assert solver._latest_snapshot_handle is None


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_graph_recompute_rebuilds_cost_heuristic_parent_and_checkpoint(kind):
    adapter = graph(kind, "recompute")
    solver = ComposableSolver(Problem(1 if kind == "astar" else 2), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    adapter.setup(solver)
    outcome = solver.step()
    assert outcome.committed
    if kind == "astar":
        nodes = {float(node.state[0]): node for _, _, node in adapter._open}
        assert set(nodes) == {3., 4.}
        assert nodes[3.].g == 3. and nodes[3.].h == 30.
    else:
        nodes = {float(node.state[0]): node for node in adapter._labels.values()}
        np.testing.assert_array_equal(nodes[3.].g, [3., 6.])
        np.testing.assert_array_equal(nodes[3.].h, [30., 60.])
    assert nodes[3.].parent_id is not None
    clone = graph(kind, "recompute")
    clone.set_state(adapter.get_state())
    assert clone.get_state() == adapter.get_state()
    snapshot = solver.read_snapshot(solver._latest_snapshot_handle.key)
    assert snapshot is not None
    np.testing.assert_array_equal(solver.population[:, 0], [3., 4.])


class UnitProposer(CandidateProposerAdapter):
    def propose(self, control, context):
        return self.build_candidate_units([UnknownState([1.], {"tag": "a"}),
                                           UnknownState([1.], {"tag": "b"})], context)

    def update(self, control, candidates, feedback, context):
        pass


def test_metadata_only_repair_rebuilds_unit_and_preserves_distinct_identity():
    adapter = UnitProposer()
    proposed = adapter.propose(None, {})
    ids = [u.unit_id for u in adapter.proposal_units]
    before = CandidateBatch.from_candidates(proposed, candidate_tokens=("a", "b"))
    after = CandidateBatch.from_candidates([s.with_meta(repaired=True) for s in proposed],
                                            candidate_tokens=("a", "b"))
    repair = ProposalRepair(2, (0, 1), before, after)
    assert repair.changed_indices == (0, 1)
    adapter.on_proposal_repair(None, repair, {})
    assert [u.unit_id for u in adapter.proposal_units] == ids
    assert adapter.proposal_units[1].to_candidate().metadata["tag"] == "b"
    assert adapter.proposal_units[0].to_candidate().metadata["repaired"] is True


def test_repair_rejects_changed_tokens_and_maps_nonprefix_wrapper_selection():
    before = CandidateBatch.from_candidates([[1.], [2.]], candidate_tokens=("a", "b"))
    after = CandidateBatch.from_candidates([[3.], [4.]], candidate_tokens=("a", "b"))
    repair = ProposalRepair(3, (0, 2), before, after)
    child = repair.for_range(1, 3).through(BatchDisposition(4, (1, 3)))
    assert child.proposed_count == 4 and child.proposal_indices == (3,)
    assert child.before.candidate_tokens == ("b",)
    with pytest.raises(ValueError, match="tokens"):
        ProposalRepair(2, (0, 1), before,
                       CandidateBatch.from_candidates([[1.], [2.]], candidate_tokens=("b", "a")))


class Probe(AlgorithmAdapter):
    def __init__(self, name, rows, seen):
        super().__init__(name=name)
        self.rows, self.seen = rows, seen

    def propose(self, control, context):
        return [np.array([x], dtype=float) for x in self.rows]

    def on_proposal_repair(self, control, repair, context):
        self.seen.append((self.name, repair, dict(context)))

    def update(self, control, candidates, feedback, context):
        self.updated = np.asarray(candidates).copy()


@pytest.mark.parametrize("router", [False, True])
def test_nested_repair_routing_keeps_pending_indices_until_acceptance(router):
    seen = []
    left, right = Probe("left", [1., 2., 3.], seen), Probe("right", [-5., -4.], seen)
    role = RoleAdapter("left_role", left, max_candidates=2)
    adapter = RoleRouterAdapter([role, RoleAdapter("right_role", right)]) if router else CompositeAdapter([role, right])
    class Constrained(Problem):
        def evaluate_constraints(self, candidate):
            return max(0., float(candidate[0]))
    solver = ComposableSolver(Constrained(), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()),
                              evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    # Global budget clipping happens before repair, local role clipping before that.
    solver.evaluation_batch_allowance = lambda count, context: 3
    assert solver.step().committed
    assert len(seen) == 2
    first, second = seen[0][1], seen[1][1]
    assert first.proposed_count == 3 and first.proposal_indices == (0, 1)
    assert second.proposed_count == 2 and second.proposal_indices == (0,)
    assert first.before.numeric_matrix[:, 0].tolist() == [1., 2.]
    assert first.after.numeric_matrix[:, 0].tolist() == [3., 4.]
    assert right.updated.tolist() == [[-3.]]


def test_trust_region_repair_rejects_outside_radius_before_evaluation():
    adapter = TrustRegionDFOAdapter(TrustRegionDFOConfig(batch_size=1, initial_radius=.5))
    adapter._center = np.array([0.])
    problem = Problem()
    solver = ComposableSolver(problem, adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    with pytest.raises(ValueError, match="outside the trust region"):
        solver.step()
    assert not problem.calls
    np.testing.assert_array_equal(adapter._center, [0.])
    assert adapter._radius == .5


def test_trust_region_uses_sampling_metric_and_subspace_membership():
    adapter = TrustRegionDFOAdapter(initial_radius=1.)
    adapter._center = np.zeros(2)
    assert adapter._repair_within_region(np.array([.9, .9]))  # box, not Euclidean ball
    subspace = TrustRegionSubspaceAdapter(initial_radius=1.)
    subspace._center = np.zeros(2)
    subspace._basis = np.array([[1.], [0.]])
    assert subspace._repair_within_region(np.array([.5, 0.]))
    assert not subspace._repair_within_region(np.array([.5, .1]))


def test_structured_adapter_without_reconciliation_fails_closed():
    class Structured(Probe):
        accepts_proposal_replacement = False
        on_proposal_repair = AlgorithmAdapter.on_proposal_repair
    adapter = Structured("structured", [1.], [])
    problem = Problem()
    solver = ComposableSolver(problem, adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    with pytest.raises(ValueError, match="explicit owner reconciliation"):
        solver.step()
    assert not problem.calls


def test_doctor_checks_repair_hook_on_nested_owner():
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    adapter = Probe("invalid", [1.], [])
    adapter.on_proposal_repair = None
    solver = ComposableSolver(Problem(), adapter=CompositeAdapter([adapter]))
    assert any(code == "adapter-repair-hook-invalid" for code, _ in inspect_runtime_contracts(solver))


@pytest.mark.parametrize("wrapper", ["serial", "event", "strategy", "elite"])
def test_other_composites_route_repair_before_final_disposition(wrapper):
    from nsgablack.adapters import (
        StrategyChainAdapter, SerialPhaseSpec, AsyncEventDrivenAdapter,
        AsyncEventDrivenConfig, EventStrategySpec, StrategyRouterAdapter,
        MultiStrategyConfig, StrategySpec, EliteRetentionAdapter, EliteRetentionConfig,
    )
    seen = []
    inner = Probe("worker", [1., 2., 3.], seen)
    if wrapper == "serial":
        adapter = StrategyChainAdapter(phases=[SerialPhaseSpec("search", inner)])
    elif wrapper == "event":
        adapter = AsyncEventDrivenAdapter(strategies=[EventStrategySpec(inner, name="worker")],
            config=AsyncEventDrivenConfig(total_batch_size=2, target_queue_size=2))
    elif wrapper == "strategy":
        adapter = StrategyRouterAdapter(strategies=[StrategySpec(inner, name="worker")],
            config=MultiStrategyConfig(total_batch_size=2))
    else:
        adapter = EliteRetentionAdapter(inner, EliteRetentionConfig(retention_ratio=0.))
    solver = ComposableSolver(Problem(), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    adapter.setup(solver)
    assert solver.step().committed
    assert len(seen) == 1
    evidence = seen[0][1]
    assert evidence.proposed_count == 3
    assert evidence.proposal_indices == ((0, 1) if wrapper in {"event", "strategy"} else (0, 1, 2))
    assert evidence.changed_indices == evidence.proposal_indices
    np.testing.assert_array_equal(evidence.after.numeric_matrix, evidence.before.numeric_matrix + 2)


def test_moa_repaired_cost_drives_same_state_dominance():
    adapter = MOAStarAdapter(
        start_state=np.array([0.]), neighbors=lambda state, context: [np.array([1.]), np.array([2.])],
        config=MOAStarConfig(path_cost_mode="edge", repair_policy="recompute", objective_weight=0.),
        edge_cost=lambda a, b, context: [b[0], b[0] * 2],
    )
    class Collapse:
        def repair(self, candidate, context=None):
            return np.array([3.])
    solver = ComposableSolver(Problem(2), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=Collapse()))
    adapter.setup(solver)
    solver.step()
    labels = [label for label in adapter._labels.values() if label.state[0] == 3. and label.valid]
    assert labels
    for label in labels:
        np.testing.assert_array_equal(label.g, [3., 6.])


def test_repair_veto_never_dispatches_evaluation_provider():
    from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin
    class Backend:
        def solve(self, request):
            pytest.fail("repair veto must precede provider dispatch")
    adapter = graph("astar")
    solver = ComposableSolver(Problem(), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(repair=ShiftRepair()))
    solver.register_evaluation_provider(EvaluationModelProviderPlugin(
        config=EvaluationModelConfig(scope="outer"),
        backend_factory=lambda problem, context: Backend(),
    ).create_provider())
    adapter.setup(solver)
    with pytest.raises(ValueError, match="repair_policy"):
        solver.step()
    assert solver.evaluation_count == 0


def test_new_proposal_repair_cannot_inherit_previous_individual_index():
    class SemanticProposer(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="semantic_steps")
            self.step_index = 0

        def propose(self, control, context):
            return [UnknownState([1.], {"step": self.step_index, "row": i}) for i in range(2)]

        def on_proposal_repair(self, control, repair, context):
            # Numeric equality must not rebind either row to a previous step.
            assert not repair.changed_rows
            assert "individual_id" not in context

        def update(self, control, candidates, feedback, context):
            self.step_index += 1

    from blackbase.representation import RepresentationCapabilities
    class SemanticPipeline:
        representation_capabilities = RepresentationCapabilities(frozenset({"repair", "repair_batch"}))

        def repair(self, candidate, context=None):
            return solver.semantic_candidate_state(candidate, candidate_index=context.get("individual_id"))

        def repair_batch(self, candidates, *, context):
            return [self.repair(candidate, context) for candidate in candidates]

    solver = ComposableSolver(Problem(), adapter=SemanticProposer(), representation_pipeline=SemanticPipeline())
    solver.context_store_update_on_build = True
    local = solver.build_context(individual_id=1, individual=np.array([0.]))
    assert local["individual_id"] == 1
    assert "individual_id" not in solver.context_store.snapshot()
    # Also ignore a stale value restored from an older ContextStore.
    solver.context_store.set("individual_id", 1)
    assert solver.step().committed
    assert solver.step().committed
    states = solver.get_candidate_population_batch().semantic_states
    assert [dict(state.metadata) for state in states] == [{"step": 1, "row": 0}, {"step": 1, "row": 1}]
