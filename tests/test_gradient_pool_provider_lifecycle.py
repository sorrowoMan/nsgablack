"""Exercise Provider-owned slots through actual Solver and pool-task lifecycles."""
from __future__ import annotations

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.evaluation import StateMaterializationResult, StateReleaseResult, StateTransitionResult
from blackbase.resources import ResourceContext
from blackbase.state_ref import StateRef
from blackbase.types import CandidateBatch, Feedback, UnknownState
from nsgablack.adapters import GradientOptimizerAdapter, PoolTaskSpec, RoleSpec, StrategyRouterAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline


class LiveGateway:
    """Small stateful backend: using a released slot is an observable error.

    This intentionally does not reimplement Adam. The Provider applies a fixed
    move; the tests concern ownership, copy-on-write lifetime and exact IDs.
    """

    def __init__(self):
        self.states = {}
        self.next_id = 0
        self.transitions = []
        self.releases = []
        self.release_failure = None

    def put(self, kind, values):
        self.next_id += 1
        ref = StateRef(provider_id="test-gradient/v1", state_id=f"state-{self.next_id}",
                       state_kind=kind, scope_id="case.fit", trajectory_id="trajectory")
        self.states[ref.state_id] = (ref, np.asarray(values, dtype=float).copy())
        return ref

    def transition(self, request, resource):
        for ref in request.slot_refs.values():
            assert ref.state_id in self.states, "optimizer attempted to reuse a released slot"
        self.transitions.append(request)
        values = self.states[request.state_ref.state_id][1]
        index = len(self.transitions)
        successor = self.put("model_parameters", values - .1)
        slots = {"m": self.put("optimizer_slot.m", np.full_like(values, index * .1)),
                 "v": self.put("optimizer_slot.v", np.full_like(values, index * .01))}
        return StateTransitionResult(request_id=request.request_id, method_id=request.method_id,
            status="applied", state_ref=successor, slot_refs=slots, metrics={"gradient_norm": 1.})

    def materialize(self, request, resource):
        assert request.state_ref.state_id in self.states, "materialized a released state"
        value = self.states[request.state_ref.state_id][1].copy()
        if request.release_after:
            del self.states[request.state_ref.state_id]
        return StateMaterializationResult(request_id=request.request_id, state_ref=request.state_ref,
            target=request.target, value=UnknownState(value, {"provider": True}))

    def release(self, request, resource):
        self.releases.append((request, resource))
        if self.release_failure == "raise":
            raise RuntimeError("release temporarily unavailable")
        # Partial success deliberately returns incomplete evidence. The Adapter
        # must retain debt, even for IDs that the backend already released.
        requested = request.state_ids[:1] if self.release_failure == "partial" else request.state_ids
        released, absent = [], []
        for state_id in requested:
            if state_id in self.states:
                del self.states[state_id]
                released.append(state_id)
            else:
                absent.append(state_id)
        return StateReleaseResult(request_id=request.request_id, provider_id=request.provider_id,
            status="released" if released else "not_found", released_count=len(released),
            released_state_ids=tuple(released), not_found_state_ids=tuple(absent))

    @property
    def live_slot_ids(self):
        return {key for key, (ref, _) in self.states.items() if ref.state_kind.startswith("optimizer_slot.")}


class ProviderProblem(BlackBoxProblem):
    def __init__(self, gateway):
        super().__init__(name="provider-pool", dimension=1, objectives=["min"], bounds=[(-100., 100.)])
        self.gateway = gateway
        self.violation = 0.

    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float)
        return Feedback(objectives=[float(np.sum(values**2))], gradients=2.*values,
            gradient_ref=self.gateway.put("gradient", 2.*values),
            info={"evaluation_state_ref": self.gateway.put("model_parameters", values),
                  "constraint_violation": self.violation})


class Initializer:
    def initialize(self, problem, context):
        return UnknownState([2.], {"seed": "initializer"})


class RejectAll:
    def select(self, candidates, feedback, context):
        return BatchDisposition(len(candidates.semantic_states), ())


def make_solver(*, pool_tasks=False):
    gateway = LiveGateway()
    adapter = GradientOptimizerAdapter(optimizer="adam", state_gateway=gateway, prefer_provider_transition=True)
    root = adapter
    if pool_tasks:
        root = StrategyRouterAdapter(name="provider_tasks", roles=[RoleSpec("fit", adapter,
            pool_task=PoolTaskSpec("seeds", mode="refine", count=2, steps=1,
                                  output="results", shuffle=False))])
    solver = ComposableSolver(ProviderProblem(gateway), adapter=root,
        resource_context=ResourceContext(namespace="case.fit", grant={"threads": 1}),
        representation_pipeline=RepresentationPipeline(initializer=Initializer()))
    solver.setup()
    if pool_tasks:
        refs = solver.store_solutions(CandidateBatch.from_candidates(
            [UnknownState([2.], {"seed": "first"}), UnknownState([4.], {"seed": "second"})],
            candidate_tokens=("seed-first", "seed-second")))
        solver.solution_pool.create_subpool("provider_tasks/seeds", refs)
    return solver, adapter, gateway


@pytest.mark.parametrize("mode", ("skip_infeasible", "zero_admitted"))
def test_no_transition_keeps_existing_slots_live_and_reusable(mode):
    solver, adapter, gateway = make_solver()
    assert solver.step().committed
    old = dict(adapter._provider_slot_refs)
    old_ids = {ref.state_id for ref in old.values()}
    assert gateway.live_slot_ids == old_ids
    if mode == "skip_infeasible":
        solver.problem.violation = 1.
    else:
        solver.set_evaluation_acceptance_policy(RejectAll())
    outcome = solver.step()
    assert outcome.committed is (mode == "skip_infeasible")
    assert len(gateway.transitions) == 1
    assert gateway.releases == []
    assert adapter._provider_slot_refs == old
    assert gateway.live_slot_ids == old_ids
    solver.problem.violation = 0.
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert dict(gateway.transitions[-1].slot_refs) == old
    assert gateway.live_slot_ids == {ref.state_id for ref in adapter._provider_slot_refs.values()}


def test_pool_restart_commit_retires_previous_task_slots_and_returns_evaluated_seed():
    solver, adapter, gateway = make_solver(pool_tasks=True)
    assert solver.step().committed
    old_ids = set(gateway.live_slot_ids)
    first, = adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((first,)).numeric_matrix, [[2.]])
    np.testing.assert_allclose(adapter.current_x, [1.9])  # Unevaluated successor is not the result.
    assert solver.step().committed
    assert dict(gateway.transitions[-1].slot_refs) == {}  # New task has fresh optimizer moments.
    assert old_ids.isdisjoint(gateway.live_slot_ids)
    assert len(gateway.releases) == 1
    assert set(gateway.releases[0][0].state_ids) == old_ids
    result, = adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((result,)).numeric_matrix, [[4.]])
    np.testing.assert_allclose(adapter.current_x, [3.9])


@pytest.mark.parametrize("fail_after_transition", (False, True))
def test_pool_restart_rollback_restores_previous_task_without_releasing_its_slots(monkeypatch, fail_after_transition):
    solver, adapter, gateway = make_solver(pool_tasks=True)
    assert solver.step().committed
    old = dict(adapter._provider_slot_refs)
    old_ids = set(gateway.live_slot_ids)
    old_result = adapter.get_pool_refinement_results(solver)
    old_x = adapter.current_x.copy()
    original_update = adapter.update
    original_propose = adapter.propose

    if fail_after_transition:
        def fail_update(*args, **kwargs):
            original_update(*args, **kwargs)
            raise RuntimeError("abort restarted task")
        monkeypatch.setattr(adapter, "update", fail_update)
    else:
        def fail_propose(*args, **kwargs):
            # PoolTask already called restart_search. No new Provider effect exists.
            original_propose(*args, **kwargs)
            raise RuntimeError("abort restarted task")
        monkeypatch.setattr(adapter, "propose", fail_propose)
    with pytest.raises(RuntimeError, match="abort restarted task"):
        solver.step()
    assert adapter._provider_slot_refs == old
    assert gateway.live_slot_ids == old_ids
    assert adapter.get_pool_refinement_results(solver) == old_result
    np.testing.assert_array_equal(adapter.current_x, old_x)
    for request, _ in gateway.releases:
        assert old_ids.isdisjoint(request.state_ids)
    assert len(gateway.releases) == int(fail_after_transition)
    monkeypatch.setattr(adapter, "update", original_update)
    monkeypatch.setattr(adapter, "propose", original_propose)
    assert solver.step().committed
    assert dict(gateway.transitions[-1].slot_refs) == {}
    assert old_ids.isdisjoint(gateway.live_slot_ids)


@pytest.mark.parametrize("release_failure", ("raise", "partial"))
def test_failed_rollback_release_keeps_exact_debt_and_retries_without_releasing_live_predecessors(monkeypatch, release_failure):
    solver, adapter, gateway = make_solver()
    assert solver.step().committed
    old = dict(adapter._provider_slot_refs)
    old_ids = set(gateway.live_slot_ids)
    before = adapter.current_x.copy()
    original = adapter.update

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("abort after transition")

    gateway.release_failure = release_failure
    monkeypatch.setattr(adapter, "update", fail)
    with pytest.raises(RuntimeError, match="abort after transition"):
        solver.step()
    assert adapter._provider_slot_refs == old
    np.testing.assert_array_equal(adapter.current_x, before)
    assert old_ids.issubset(gateway.live_slot_ids)
    failed_ids = set(gateway.releases[-1][0].state_ids)
    assert len(failed_ids) == 2 and old_ids.isdisjoint(failed_ids)
    assert set(adapter._provider_cleanup_refs) == failed_ids
    # A no-transition attempt can retry cleanup; current slots remain live.
    gateway.release_failure = None
    monkeypatch.setattr(adapter, "update", original)
    solver.set_evaluation_acceptance_policy(RejectAll())
    assert not solver.step().committed
    assert set(gateway.releases[-1][0].state_ids) == failed_ids
    assert len(gateway.releases) == 2
    assert adapter._provider_cleanup_refs == {}
    assert gateway.live_slot_ids == old_ids
    assert adapter._provider_slot_refs == old
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert dict(gateway.transitions[-1].slot_refs) == old
