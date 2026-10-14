"""Graph search admits an explicit new root; pool objectives never imply edges."""
import copy

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (
    AStarAdapter, MOAStarAdapter, MultiStrategyConfig, PoolTaskSpec,
    RoleSpec, StrategyRouterAdapter,
)
from nsgablack.adapters.pool_tasks import PoolTaskAdapter
from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
from nsgablack.core import BlackBoxProblem, ComposableSolver, PoolRetentionPolicy
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.structure_builders import decode_unit_value, encode_unit_value


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, x):
        self.calls.append(float(x[0]))
        return [float(x[0] ** 2), float((x[0] + 1.) ** 2)]


class Initializer:
    def __init__(self):
        self.calls = 0

    def initialize(self, problem, context):
        self.calls += 1
        return UnknownState(np.array([7.]), {"origin": "initializer"})


class ShiftRepair:
    def __init__(self, delta=1.):
        self.delta = delta

    def repair(self, candidate, context):
        return candidate + self.delta


class Admission:
    policy_id = "graph-test-admission"

    def __init__(self, indices):
        self.indices = indices

    def select(self, candidates, feedback, context):
        return BatchDisposition(len(candidates.semantic_states), self.indices)


def make_adapter(kind, **options):
    cls = AStarAdapter if kind == "astar" else MOAStarAdapter
    kwargs = dict(neighbors=lambda x, _: [x - 1., x - 2.],
        edge_cost=lambda parent, child, _: float(abs(parent[0] - child[0])),
        start_state=np.array([91.]), pool_start_policy="new_root",
        path_cost_mode="edge", objective_weight=0., max_candidates_per_step=2)
    kwargs.update(options)
    return cls(**kwargs)


def build(kind, *, task=True, repair=None, retention=False, count=None, setup=True, **options):
    leaf = make_adapter(kind, **options)
    root = (StrategyRouterAdapter(name="graph", roles=[RoleSpec("search", leaf,
        pool_task=PoolTaskSpec(mode="initialize", count=count, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False)) if task else leaf)
    initializer = Initializer()
    problem = Problem()
    solver = ComposableSolver(problem, adapter=root,
        representation_pipeline=RepresentationPipeline(initializer=initializer, repair=repair))
    solver.set_random_seed(11)
    if retention:
        solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    if setup:
        solver.setup()
    return solver, leaf, initializer


def seed(solver, values=(5.,)):
    return solver.store_solutions(CandidateBatch.from_candidates(
        [UnknownState(np.array([x]), {"origin": "seed", "position": i}) for i, x in enumerate(values)],
        candidate_tokens=tuple(f"seed:{i}" for i in range(len(values)))))


def nodes(leaf):
    return ([node for _, _, node in leaf._open] if isinstance(leaf, AStarAdapter)
            else list(leaf._labels.values()))


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_pool_seed_is_admitted_as_zero_edge_root_before_any_expansion(kind):
    solver, leaf, initializer = build(kind)
    assert initializer.calls == 0
    assert solver.problem.calls == []
    assert not nodes(leaf)
    original, = seed(solver)
    assert solver.step().committed
    assert solver.problem.calls == [5.]
    assert initializer.calls == 0
    root, = nodes(leaf)
    np.testing.assert_array_equal(root.state, [5.])
    assert np.all(np.asarray(root.g) == 0.)
    assert root.parent_id is None
    refs = leaf.get_solution_pool_roots(solver)
    assert len(refs) == 1 and refs[0].candidate_token != original.candidate_token
    provenance, = solver.solution_pool.read_provenance(refs)
    assert provenance["parent_token"] == original.candidate_token
    assert provenance["metadata"]["solution_source_ref"] == original.as_dict()
    np.testing.assert_array_equal(solver.solution_pool.read_raw_feedback(refs)[0], [[25., 36.]])
    assert solver.adapter.units[0].adapter.task_status["status"] == "done"


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_objective_mode_root_uses_current_problem_feedback_without_inventing_edge(kind):
    solver, leaf, _ = build(kind, path_cost_mode="objective",
        edge_cost=lambda *args: pytest.fail("a new root has no edge"))
    seed(solver)
    assert solver.step().committed
    node, = nodes(leaf)
    np.testing.assert_array_equal(node.g, 61. if kind == "astar" else [25., 36.])


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_root_repair_precedes_heuristic_without_reinterpreting_an_edge(kind):
    seen = []
    solver, leaf, _ = build(kind, repair=ShiftRepair(),
        heuristic=lambda x, _: seen.append(float(x[0])) or 0.,
        edge_cost=lambda *args: pytest.fail("root repair must not calculate parent edge"))
    seed(solver)
    assert solver.step().committed
    assert solver.problem.calls == [6.]
    assert seen == [6.]
    node, = nodes(leaf)
    assert np.all(np.asarray(node.g) == 0.)
    np.testing.assert_array_equal(solver.read_solutions(leaf.get_solution_pool_roots(solver)).numeric_matrix, [[6.]])


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_zero_admission_retries_original_pool_root_and_failure_rolls_back(kind, monkeypatch):
    solver, leaf, initializer = build(kind)
    seed(solver)
    solver.set_evaluation_acceptance_policy(Admission(()))
    assert not solver.step().committed
    assert not leaf._root_initialized and not nodes(leaf)
    assert leaf.get_solution_pool_roots(solver) == ()
    solver.set_evaluation_acceptance_policy(None)
    original_update = leaf.update
    def failed(*args, **kwargs):
        original_update(*args, **kwargs)
        raise RuntimeError("after graph update")
    monkeypatch.setattr(leaf, "update", failed)
    with pytest.raises(RuntimeError, match="after graph update"):
        solver.step()
    assert not leaf._root_initialized and not nodes(leaf)
    monkeypatch.setattr(leaf, "update", original_update)
    assert solver.step().committed
    assert solver.problem.calls == [5., 5., 5.]
    assert initializer.calls == 0
    assert leaf._root_initialized


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_partial_child_acceptance_keeps_parent_identity_and_exact_results(kind):
    solver, leaf, _ = build(kind, retention=True)
    original, = seed(solver)
    assert solver.step().committed
    root_ref, = leaf.get_solution_pool_roots(solver)
    solver.set_evaluation_acceptance_policy(Admission((1,)))
    assert solver.step().committed
    assert solver.problem.calls == [5., 4., 3.]
    selected, = leaf.get_pool_refinement_results(solver)
    assert selected.candidate_token != original.candidate_token
    batch = solver.read_solutions((selected,))
    np.testing.assert_array_equal(batch.numeric_matrix, [[3.]])
    assert batch.semantic_states[0].metadata["origin"] == "seed"
    provenance, = solver.solution_pool.read_provenance((selected,))
    assert provenance["parent_token"] == root_ref.candidate_token
    assert provenance["metadata"]["solution_source_ref"] == original.as_dict()
    np.testing.assert_array_equal(solver.solution_pool.read_raw_feedback((selected,))[0], [[9., 16.]])
    children = [node for node in nodes(leaf) if node.parent_id is not None]
    assert len(children) == 1
    assert np.all(np.asarray(children[0].g) == 2.)
    assert not leaf._pending
    assert selected in leaf.get_solution_pool_roots(solver)


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_live_refs_and_results_are_pinned_after_same_token_is_republished(kind):
    solver, leaf, _ = build(kind)
    seed(solver)
    solver.step()
    solver.step()
    retained = leaf.get_solution_pool_roots(solver)
    selected = leaf.get_pool_refinement_results(solver)
    assert selected
    expected = solver.read_solutions(selected).numeric_matrix.copy()
    state = copy.deepcopy(leaf.get_state())
    newer = solver.store_solutions(CandidateBatch.from_candidates([np.array([99.])],
        candidate_tokens=(selected[0].candidate_token,)))
    assert newer[0] != selected[0]
    clone = make_adapter(kind)
    clone.set_state(state)
    assert clone.get_pool_refinement_results(solver) == selected
    assert clone.get_solution_pool_roots(solver) == retained
    np.testing.assert_array_equal(solver.read_solutions(selected).numeric_matrix, expected)


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_pending_edges_retain_popped_parent_and_checkpoint_requires_exact_parent(kind):
    solver, leaf, _ = build(kind)
    seed(solver)
    solver.step()
    root_ref, = leaf.get_solution_pool_roots(solver)
    leaf.propose(solver, {"generation": 1})
    assert root_ref in leaf.get_solution_pool_roots(solver)
    state = copy.deepcopy(leaf.get_state())
    key = "frontier_state" if kind == "astar" else "runtime"
    data = decode_unit_value(state[key])
    data["pending"][0]["parent_receipt"] = None
    state[key] = encode_unit_value(data)
    with pytest.raises(ValueError, match="exact parent"):
        make_adapter(kind).set_state(state)


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_checkpoint_restores_graph_and_pool_without_reevaluating_then_continues(kind):
    source, leaf, _ = build(kind)
    seed(source)
    source.step()
    source.step()
    payload = CheckpointResumePlugin()._build_payload(solver=source, reason="graph")
    target, restored, initializer = build(kind, setup=False)
    reader = CheckpointResumePlugin()
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert target.problem.calls == [] and initializer.calls == 0
    assert restored.get_pool_refinement_results(target) == leaf.get_pool_refinement_results(source)
    assert restored.get_solution_pool_roots(target) == leaf.get_solution_pool_roots(source)
    assert source.step().committed
    assert target.step().committed
    np.testing.assert_array_equal(target.read_solutions(restored.get_pool_refinement_results(target)).numeric_matrix,
                                  source.read_solutions(leaf.get_pool_refinement_results(source)).numeric_matrix)


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_root_mode_cannot_silently_import_multiple_seeds_replace_tree_or_restart(kind):
    solver, leaf, _ = build(kind, count=2)
    seed(solver, (5., 6.))
    with pytest.raises(ValueError, match="exactly one root"):
        solver.step()
    assert solver.problem.calls == []
    assert not leaf._root_initialized
    with pytest.raises(ValueError, match="explicit search restart"):
        PoolTaskAdapter(leaf, PoolTaskSpec(mode="refine"), role="refiner")
    other, active, _ = build(kind)
    refs = seed(other)
    other.step()
    input_ref = other.solution_pool.bind_input(refs)
    with pytest.raises(ValueError, match="active search path"):
        active.propose(other, {KEY_SOLUTION_INPUT_REF: input_ref})
    assert other.solution_pool.input_remaining(input_ref) == 1


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_projection_feedback_is_not_accepted_as_graph_cost(kind):
    solver, leaf, _ = build(kind)
    feedback = ObjectiveProjection("weighted_sum", (1., 0.)).apply(
        OptimizationFeedbackBatch.coerce((np.array([[1., 2.]]), np.zeros(1))))
    with pytest.raises(ValueError, match="projection feedback"):
        leaf.update(solver, [np.array([1.])], feedback, {})
    assert not leaf.supports_objective_projection


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_legacy_unbound_tree_is_honest_about_missing_receipts_and_policy_restore(kind):
    solver, leaf, _ = build(kind, task=False, pool_start_policy=None)
    assert leaf.get_solution_pool_roots(solver) is None
    assert leaf.pool_input_modes == ()
    with pytest.raises(ValueError, match="root interpretation"):
        make_adapter(kind).set_state(leaf.get_state())
    with pytest.raises(ValueError, match="pool initialize"):
        PoolTaskAdapter(leaf, PoolTaskSpec(mode="initialize"), role="search")


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_plain_new_root_preserves_initializer_semantics_and_exhaustion_does_not_restart(kind):
    solver, leaf, initializer = build(kind, task=False, start_state=None,
                                    neighbors=lambda x, context: [])
    assert initializer.calls == 0
    assert solver.step().committed
    refs = leaf.get_solution_pool_roots(solver)
    assert solver.read_solutions(refs).semantic_states[0].metadata["origin"] == "initializer"
    assert solver.step().status == "terminal"
    assert initializer.calls == 1
    assert solver.problem.calls == [7.]


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_repaired_edges_still_require_opt_in_and_rollback_before_evaluation(kind):
    solver, leaf, _ = build(kind, repair=ShiftRepair(.25))
    seed(solver)
    solver.step()
    before = copy.deepcopy(leaf.get_state())
    roots = leaf.get_solution_pool_roots(solver)
    with pytest.raises(ValueError, match="repair_policy='reject'"):
        solver.step()
    assert solver.problem.calls == [5.25]
    assert leaf.get_state() == before
    assert leaf.get_solution_pool_roots(solver) == roots


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_recomputed_edges_keep_path_order_distinct_from_raw_objectives(kind):
    solver, leaf, _ = build(kind, repair=ShiftRepair(.25), repair_policy="recompute")
    seed(solver)
    solver.step()
    solver.step()
    children = [node for node in nodes(leaf) if node.parent_id is not None]
    assert sorted(float(node.state[0]) for node in children) == [3.5, 4.5]
    for node in children:
        np.testing.assert_array_equal(node.g, (5.25 - node.state[0]) *
            (1. if kind == "astar" else np.ones(2)))
    # A* reports best_evaluated; MOA* reports nondominated_path_labels.
    result, = leaf.get_pool_refinement_results(solver)
    chosen = 3.5 if kind == "astar" else 4.5
    np.testing.assert_array_equal(solver.read_solutions((result,)).numeric_matrix, [[chosen]])
    np.testing.assert_array_equal(solver.solution_pool.read_raw_feedback((result,))[0],
                                  [[chosen ** 2, (chosen + 1.) ** 2]])


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_failure_after_expansion_restores_frontier_and_selected_receipts(kind, monkeypatch):
    solver, leaf, _ = build(kind)
    seed(solver)
    solver.step()
    before = copy.deepcopy(leaf.get_state())
    roots = leaf.get_solution_pool_roots(solver)
    original = leaf.update
    def failed(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after edge update")
    monkeypatch.setattr(leaf, "update", failed)
    with pytest.raises(RuntimeError, match="after edge update"):
        solver.step()
    assert leaf.get_state() == before
    assert leaf.get_solution_pool_roots(solver) == roots
    assert solver.evaluation_count == 3  # Evaluation cost survives graph rollback.


@pytest.mark.parametrize("kind", ["astar", "moa"])
@pytest.mark.parametrize("corruption", ["receipt", "root_flag"])
def test_corrupt_checkpoint_cannot_rebind_node_values_or_readmit_root(kind, corruption):
    solver, leaf, _ = build(kind)
    seed(solver)
    solver.step()
    state = copy.deepcopy(leaf.get_state())
    key = "frontier_state" if kind == "astar" else "runtime"
    data = decode_unit_value(state[key])
    if corruption == "receipt":
        next(iter(data["node_receipts"].values()))["candidate"] = [99.]
    else:
        data["root_initialized"] = False
    state[key] = encode_unit_value(data)
    with pytest.raises(ValueError, match="receipt|uninitialized"):
        make_adapter(kind).set_state(state)
    assert solver.problem.calls == [5.]


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_named_projection_pool_cannot_bypass_graph_cost_boundary(kind):
    leaf = make_adapter(kind)
    router = StrategyRouterAdapter(name="graph", roles=[RoleSpec("search", leaf,
        pool_task=PoolTaskSpec("direction", mode="initialize"))])
    solver = ComposableSolver(Problem(), adapter=router)
    solver.setup()
    refs = seed(solver)
    solver.solution_pool.publish_projection_subpool("graph/direction", refs,
        created_by=("producer",), slot=0, projection=ObjectiveProjection("weighted_sum", (.8, .2)))
    with pytest.raises(ValueError, match="refiner supporting objective projections"):
        solver.step()
    assert solver.problem.calls == [] and not leaf._root_initialized


@pytest.mark.parametrize("kind", ["astar", "moa"])
def test_terminal_goal_keeps_exact_candidate_after_removal_from_frontier(kind):
    solver, leaf, _ = build(kind, goal_test=lambda x, _: float(x[0]) == 5.,
        **({"stop_on_goal": True} if kind == "moa" else {}))
    seed(solver)
    solver.step()
    root_refs = leaf.get_solution_pool_roots(solver)
    assert solver.step().status == "terminal"
    assert leaf.found
    assert leaf.get_solution_pool_roots(solver) == root_refs
    clone = make_adapter(kind, **({"stop_on_goal": True} if kind == "moa" else {}))
    clone.set_state(leaf.get_state())
    assert clone.get_solution_pool_roots(solver) == root_refs
