from dataclasses import FrozenInstanceError
import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, UnknownState

from nsgablack.adapters import (
    AlgorithmAdapter, MultiStrategyConfig, ProposalRepair, RoleSpec,
    StrategyOrigin, StrategyRouterAdapter, StrategySpec, StrategyTask,
)
from nsgablack.adapters.strategy_task import TASK_CONTEXT_KEYS
from nsgablack.core import ComposableSolver


class Recorder(AlgorithmAdapter):
    def __init__(self, name="recorder"):
        super().__init__(name=name)
        self.calls = {}

    def propose(self, control, context):
        self.calls["propose"] = copy.deepcopy(context)
        return [UnknownState([1., 2.], {"tag": str(i)}) for i in range(2)]

    def on_proposal_repair(self, control, repair, context):
        self.calls["repair"] = copy.deepcopy(context)

    def on_proposal_disposition(self, control, disposition, context):
        self.calls["disposition"] = copy.deepcopy(context)
        self.calls["indices"] = disposition.accepted_indices

    def update(self, control, candidates, feedback, context):
        self.calls["update"] = copy.deepcopy(context)

    def get_runtime_context_projection(self, control):
        return {"strategy_id": "DE/rand/1", "region_id": 999, "task": {"fake": True}}


def router(*adapters):
    return StrategyRouterAdapter(
        strategies=[StrategySpec(adapter=a, name=f"role{i}") for i, a in enumerate(adapters)],
        config=MultiStrategyConfig(total_batch_size=2 * len(adapters), adapt_weights=False),
    )


def test_local_task_survives_poisoned_observation_and_nonprefix_admission(sample_problem):
    children = [Recorder(), Recorder()]
    adapter = router(*children)
    solver = ComposableSolver(sample_problem, adapter=adapter)
    adapter.setup(solver)
    proposed = adapter.propose(solver, {"generation": 0})
    requests = [StrategyTask.from_context(child.calls["propose"]) for child in children]
    poisoned = dict(children[-1].calls["propose"])
    poisoned.update(region_id=999, role_adapter="wrong", seeds=[[999.]], generation=12)
    before = CandidateBatch.from_candidates(proposed, candidate_tokens=("a", "b", "c", "d"))
    adapter.on_proposal_repair(solver, ProposalRepair(4, (0, 1, 2, 3), before, before), poisoned)
    adapter.on_proposal_disposition(solver, BatchDisposition(4, (1, 2)), poisoned)
    adapter.update(solver, [np.array([1., 2.]), np.array([1., 2.])],
                   (np.zeros((2, 1)), np.zeros(2)), poisoned)
    for child, request in zip(children, requests):
        for stage in ("repair", "disposition", "update"):
            observed = child.calls[stage]
            assert StrategyTask.from_context(observed) == request
            assert observed["generation"] == 12
            assert observed["region_id"] is None and observed["seeds"] == ()
            assert observed["role_adapter"] == request.adapter_name
        assert child.calls["update"]["task"]["budget"] == 2
    assert children[0].calls["indices"] == (1,)
    assert children[1].calls["indices"] == (0,)
    projection = adapter.get_runtime_context_projection(solver)
    assert not (set(TASK_CONTEXT_KEYS) - {"phase"}) & projection.keys()
    assert projection["candidate_roles"] == ["role0", "role1"]
    assert len(projection["strategy_instances"]) == 2
    assert all(v["strategy_id"] == "DE/rand/1" for v in projection["strategy_instances"].values())


def test_task_is_detached_and_readonly():
    seeds = [[1., 2.]]
    task = StrategyTask(("unit:search:0",), "search", 0, 0, "a", 0, "explore", 0, 2, seeds=seeds)
    seeds[0][0] = 999.
    assert task.seeds == ((1., 2.),)
    with pytest.raises(FrozenInstanceError):
        task.budget = 0
    context = task.bind({})
    context["task"]["budget"] = 999
    assert task.budget == 2
    assert StrategyTask.from_dict(task.as_dict()) == task
    with pytest.raises(ValueError, match="schema"):
        StrategyTask.from_dict({"budget": 2})


def test_nested_same_type_origins_follow_tokens_through_snapshot(sample_problem):
    leaves = [Recorder(), Recorder()]
    inner = router(*leaves)
    outer = router(inner)
    outer.cfg.total_batch_size = 4
    solver = ComposableSolver(sample_problem, adapter=outer)
    outer.setup(solver)
    proposed = outer.propose(solver, {})
    records = solver.prepare_candidate_provenance(proposed)
    batch = CandidateBatch.from_candidates(proposed, candidate_tokens=[r.candidate_token for r in records])
    # Equal numeric candidates still have distinct source row and token.
    assert len(set(batch.candidate_tokens)) == len(proposed)
    for i, state in enumerate(batch.semantic_states):
        route = StrategyOrigin.from_candidate(state)
        assert len(route) == 2
        assert route[1].parent_task_id == route[0].task_id
        assert route[1].owner_path[:1] == route[0].owner_path
        assert state.metadata["tag"] == str(i % 2)
    selected = batch.subset((1,))
    handle = solver.snapshot_store.write(selected.as_dict())
    restored = CandidateBatch.from_dict(solver.read_snapshot(handle.key))
    assert restored.candidate_tokens == (batch.candidate_tokens[1],)
    assert StrategyOrigin.from_candidate(restored.semantic_states[0]) == StrategyOrigin.from_candidate(proposed[1])
    # Replaying the same numeric candidate in another attempt gets a new task.
    next_proposed = outer.propose(solver, {})
    assert StrategyOrigin.from_candidate(next_proposed[0])[0].task_id != StrategyOrigin.from_candidate(proposed[0])[0].task_id


def test_step_evidence_keeps_origin_with_candidate_provenance(sample_problem):
    child = Recorder()
    adapter = router(child)
    solver = ComposableSolver(sample_problem, adapter=adapter)
    adapter.setup(solver)
    assert solver.step().committed
    # Partitioned trajectory children have no population; evaluation evidence
    # remains the source even when no L2 population is published.
    provenance = solver._active_candidate_provenance
    assert provenance
    state = solver.semantic_candidate_state(solver.population[0], candidate_index=0)
    assert StrategyOrigin.from_candidate(state)[0].role == "role0"
    assert provenance[0].candidate_token


@pytest.mark.parametrize("mode", ["role_name", "factory", "strategy"])
def test_invalid_instance_ownership_rejected_at_assembly(mode):
    child = Recorder()
    if mode == "role_name":
        adapter = StrategyRouterAdapter(roles=[RoleSpec("same", lambda: Recorder()), RoleSpec("same", lambda: Recorder())])
    elif mode == "factory":
        adapter = StrategyRouterAdapter(roles=[RoleSpec("same", lambda uid: child, n_units=2)])
    else:
        adapter = router(child, child)
    with pytest.raises(ValueError, match="unique|independent"):
        adapter._build_units()


def test_transaction_restores_task_and_empty_proposal_clears_projection(sample_problem):
    adapter = router(Recorder())
    solver = ComposableSolver(sample_problem, adapter=adapter)
    adapter.setup(solver)
    adapter.propose(solver, {})
    before = adapter.snapshot_step_state()
    adapter.propose(solver, {})
    adapter.restore_step_state(before)
    assert adapter.snapshot_step_state() == before
    for spec in adapter.strategies:
        spec.enabled = False
    assert adapter.propose(solver, {}) == []
    projection = adapter.get_runtime_context_projection(solver)
    assert not projection.get("candidate_roles")
    assert not projection.get("unit_tasks")


def test_checkpoint_rejects_duplicate_owners_and_invalid_task(sample_problem):
    adapter = router(Recorder("first"), Recorder("second"))
    solver = ComposableSolver(sample_problem, adapter=adapter)
    adapter.setup(solver)
    adapter.propose(solver, {})
    saved = adapter.get_state()
    restored = router(Recorder("first"), Recorder("second"))
    restored.set_state(saved)
    assert restored.get_state()["unit_tasks"] == saved["unit_tasks"]
    invalid = copy.deepcopy(saved)
    invalid["units"][1] = invalid["units"][0]
    with pytest.raises(ValueError, match="identities"):
        restored.set_state(invalid)
    key = next(iter(adapter._unit_tasks))
    adapter._unit_tasks[key]["role"] = "wrong"
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    assert "strategy-task-contract-invalid" in dict(inspect_runtime_contracts(solver))


def test_origin_attachment_preserves_preexisting_token(sample_problem):
    from nsgablack.adapters.strategy_task import attach_strategy_origin
    solver = ComposableSolver(sample_problem)
    candidate = UnknownState([1., 2.], {"tag": "existing"})
    existing = solver.prepare_candidate_provenance([candidate])[0]
    task = StrategyTask(("unit:search:0",), "search", 0, 0, "a", 0, "explore", 0, 1)
    result = attach_strategy_origin(candidate, task, 0, solver)
    actual = solver.prepare_candidate_provenance([result])[0]
    assert actual.candidate_token == existing.candidate_token
    assert result.metadata["tag"] == "existing"


def test_nested_paths_cannot_alias_same_mutable_child(sample_problem):
    leaf = Recorder()
    adapter = router(router(leaf), router(leaf))
    solver = ComposableSolver(sample_problem, adapter=adapter)
    with pytest.raises(ValueError, match="across nested paths"):
        adapter.setup(solver)
