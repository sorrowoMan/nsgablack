from __future__ import annotations

import numpy as np
import pytest

from blackbase import CandidateBatch, UnknownState
from blackbase.context import SnapshotIdentity
from nsgablack.adapters import AlgorithmAdapter, PopulationPartition
from nsgablack.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_OBJECTIVES_REF,
    KEY_POPULATION_REF,
    KEY_SNAPSHOT_KEY,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.core.solver_helpers import validate_population_snapshot_v2
from nsgablack.core.state import StepOutcome
from nsgablack.core.state.incumbent import CandidateProvenance


def _sample_context_reads(control, observations, phase):
    for _ in range(2):
        for reader in (control.build_context, control.get_context):
            context = reader()
            observations.append({
                "phase": phase,
                "key": context.get(KEY_SNAPSHOT_KEY),
                "pending_key": control.pending_snapshot_step_key(),
                "transaction_active": control._snapshot_step_transaction is not None,
            })


class _Problem(BlackBoxProblem):
    def __init__(self, observations, *, infeasible=False):
        super().__init__(dimension=2, objectives=["minimize"], bounds=[(-1.0, 1.0)] * 2)
        self.observations = observations
        self.infeasible = infeasible
        self.control = None
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        _sample_context_reads(self.control, self.observations, "evaluate")
        values = np.asarray(candidate, dtype=float)
        return float(np.dot(values, values))

    def evaluate_constraints(self, candidate):
        return 1.0 if self.infeasible else 0.0


class _Adapter(AlgorithmAdapter):
    def __init__(self, observations, *, mode="step_batch", empty_status=None, fail_update=False):
        super().__init__(name="context-read-flow")
        self.observations = observations
        self.population_state_mode = "none" if mode == "step_batch" else mode
        self.state_recovery_level = "L0" if mode == "step_batch" else "L2"
        self.empty_status = empty_status
        self.fail_update = fail_update
        self.updates = 0
        self.snapshot = None
        self.tokens = ()
        self.partitions = ()

    def propose(self, control, context):
        _sample_context_reads(control, self.observations, "propose")
        if self.empty_status is not None:
            return ()
        return tuple(
            UnknownState(values=values, metadata={"read_flow_seed": index})
            for index, values in enumerate(([0.25, 0.5], [-0.25, 0.75]))
        )

    def get_empty_proposal_outcome(self, control, context):
        if self.empty_status is None:
            return None
        return StepOutcome(status=self.empty_status, reason="synthetic-empty-proposal")

    def update(self, control, candidates, feedback, context):
        _sample_context_reads(control, self.observations, "update")
        self.updates += 1
        if self.fail_update:
            raise RuntimeError("synthetic update failure")
        self.tokens = self.candidate_tokens_for(control, candidates)
        if self.population_state_mode == "single":
            self.set_population_snapshot(candidates, feedback.objectives, feedback.violations)
        elif self.population_state_mode == "partitioned":
            self.partitions = (PopulationPartition(
                partition_id="worker-a",
                population=np.asarray(candidates),
                objectives=feedback.objectives,
                violations=feedback.violations,
                candidate_tokens=self.tokens,
            ),)

    def get_population_snapshot(self):
        return self.snapshot

    def set_population_snapshot(self, population, objectives, violations):
        self.snapshot = self.validate_population_snapshot(population, objectives, violations)
        return True

    def get_population_candidate_tokens(self):
        return self.tokens

    def set_population_candidate_tokens(self, tokens):
        self.tokens = tuple(tokens)
        return True

    def get_population_partitions(self):
        return self.partitions

    def set_population_partitions(self, partitions):
        self.partitions = tuple(partitions)
        return True

    def get_state(self):
        return {
            "updates": self.updates,
            "snapshot": None if self.snapshot is None else [value.tolist() for value in self.snapshot],
            "tokens": list(self.tokens),
            "partitions": [partition.as_dict() for partition in self.partitions],
        }

    def set_state(self, state):
        self.updates = int(state["updates"])
        raw_snapshot = state["snapshot"]
        self.snapshot = None if raw_snapshot is None else tuple(np.asarray(value) for value in raw_snapshot)
        self.tokens = tuple(state["tokens"])
        self.partitions = tuple(PopulationPartition.from_dict(value) for value in state["partitions"])


def _solver(*, mode="step_batch", empty_status=None, fail_update=False, infeasible=False):
    observations = []
    problem = _Problem(observations, infeasible=infeasible)
    adapter = _Adapter(
        observations, mode=mode, empty_status=empty_status, fail_update=fail_update,
    )
    solver = ComposableSolver(
        problem,
        adapter=adapter,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance() if infeasible else None,
        snapshot_strict=True,
        snapshot_store_key_prefix="context-read-flow",
    )
    problem.control = solver
    return solver, problem, adapter, observations


def _seed_working_arrays(solver, *, value=0.5):
    solver.population = np.asarray([[value, value]])
    solver.objectives = np.asarray([[2.0 * value * value]])
    solver.constraint_violations = np.asarray([0.0])


def _spy_persist(solver, monkeypatch):
    calls = []
    persist = solver._persist_snapshot

    def counted(*args, **kwargs):
        call = {
            "publication": kwargs.get("publication", "authority"),
            "transaction_active": solver._snapshot_step_transaction is not None,
            "generation": solver.generation,
        }
        calls.append(call)
        result = persist(*args, **kwargs)
        transaction = solver._snapshot_step_transaction
        pending = None if transaction is None else transaction.get("pending")
        call["pending"] = pending
        if pending is not None:
            call["pending_was_unpublished"] = solver.snapshot_store.read(pending["key"]) is None
        return result

    monkeypatch.setattr(solver, "_persist_snapshot", counted)
    return calls


def _assert_no_authority(solver):
    assert solver.get_population_authority_identity() is None
    assert solver._latest_snapshot_handle is None
    assert solver.pending_snapshot_step_key() is None


def test_active_snapshot_transaction_context_reads_do_not_prepare_or_publish(monkeypatch):
    solver, _, _, observations = _solver()
    _seed_working_arrays(solver)
    calls = _spy_persist(solver, monkeypatch)
    solver.begin_snapshot_step_transaction()

    _sample_context_reads(solver, observations, "direct-transaction")

    assert calls == []
    assert solver._snapshot_step_transaction["pending"] is None
    assert all(item["transaction_active"] for item in observations)
    assert all(item["key"] is None and item["pending_key"] is None for item in observations)
    _assert_no_authority(solver)

    assert solver.write_population_snapshot(
        solver.population, solver.objectives, solver.constraint_violations
    )
    pending = solver._snapshot_step_transaction["pending"]
    pending_key = pending["key"]
    offset = len(observations)
    _sample_context_reads(solver, observations, "direct-formal-pending")
    assert len(calls) == 1
    assert solver._snapshot_step_transaction["pending"] is pending
    assert solver.pending_snapshot_step_key() == pending_key
    assert solver.snapshot_store.read(pending_key) is None
    assert all(item["key"] is None for item in observations[offset:])
    assert all(item["pending_key"] == pending_key for item in observations[offset:])
    solver.rollback_snapshot_step_transaction()
    _assert_no_authority(solver)
    assert solver.snapshot_store.read(pending_key) is None


@pytest.mark.parametrize("mode", ["step_batch", "single", "partitioned"])
def test_real_composable_step_reads_context_but_prepares_authority_only_once(mode, monkeypatch):
    solver, problem, adapter, observations = _solver(mode=mode)
    calls = _spy_persist(solver, monkeypatch)

    outcome = solver.step()

    assert outcome.committed
    assert problem.calls == outcome.evaluations == 2
    assert adapter.updates == 1
    assert solver.generation == 0
    assert {item["phase"] for item in observations} == {"propose", "evaluate", "update"}
    assert all(item["transaction_active"] for item in observations)
    assert all(item["key"] is None and item["pending_key"] is None for item in observations)
    assert len(calls) == 1
    assert calls[0]["publication"] == "authority"
    assert calls[0]["transaction_active"] is True
    assert calls[0]["generation"] == calls[0]["pending"]["generation"] == 0
    assert calls[0]["pending_was_unpublished"] is True
    assert solver._snapshot_step_transaction is None

    edge = solver.get_population_authority_identity()
    assert edge is not None
    assert edge.snapshot.key == calls[0]["pending"]["key"]
    authority = solver.snapshot_store.read_verified(edge.snapshot)
    validate_population_snapshot_v2(
        authority.data, snapshot_schema=authority.schema, expected_authority_mode=mode,
    )
    if mode == "partitioned":
        entry = authority.data["population_partitions"]["partitions"][0]
        batch_payload, lineage_payload = entry["batch"], entry["provenance"]
    else:
        batch_payload = authority.data["candidate_batch"]
        lineage_payload = authority.data["candidate_provenance"]
    batch = CandidateBatch.from_dict(batch_payload)
    provenance = tuple(CandidateProvenance.from_dict(value) for value in lineage_payload)
    assert len(set(batch.candidate_tokens)) == len(provenance) == 2
    assert tuple(record.candidate_token for record in provenance) == batch.candidate_tokens
    assert [state.metadata["read_flow_seed"] for state in batch.semantic_states] == [0, 1]
    accepted_refs = solver.solution_pool.select(stage="accepted")
    assert tuple(ref.candidate_token for ref in accepted_refs) == batch.candidate_tokens
    pooled = solver.solution_pool.read(accepted_refs)
    assert pooled.candidate_tokens == batch.candidate_tokens
    assert all(value is not None for value in solver.solution_pool.read_provenance(accepted_refs))
    manifest_identity = SnapshotIdentity.from_dict(authority.data["solution_pool_ref"])
    manifest = solver.snapshot_store.read_verified(manifest_identity)
    assert manifest.data["pool_id"] == solver.solution_pool.pool_id
    assert authority.data["solution_pool_ref"] == solver.solution_pool.publication_ref()
    evidence = outcome.metadata["evaluation_disposition"]
    assert evidence["authority_snapshot_key"] == edge.snapshot.key
    assert authority.data["last_evaluation_disposition"]["event_id"] == evidence["event_id"]


def test_context_keeps_published_reference_while_a_new_authority_is_pending(monkeypatch):
    solver, _, _, observations = _solver()
    _seed_working_arrays(solver, value=0.25)
    assert solver.write_population_snapshot(
        solver.population, solver.objectives, solver.constraint_violations
    )
    old_edge = solver.get_population_authority_identity()
    old_population = solver.population.copy()
    solver.begin_snapshot_step_transaction()
    _seed_working_arrays(solver, value=0.75)
    assert solver.write_population_snapshot(
        solver.population, solver.objectives, solver.constraint_violations
    )
    pending = solver._snapshot_step_transaction["pending"]
    assert pending["key"] != old_edge.snapshot.key
    calls = _spy_persist(solver, monkeypatch)

    _sample_context_reads(solver, observations, "pending-authority")

    assert calls == []
    assert solver._snapshot_step_transaction["pending"] is pending
    assert all(item["key"] == old_edge.snapshot.key for item in observations)
    assert all(item["pending_key"] == pending["key"] for item in observations)
    assert solver.snapshot_store.read(pending["key"]) is None
    assert solver.get_population_authority_identity() == old_edge
    for reader in (solver.build_context, solver.get_context):
        context = reader()
        assert context[KEY_POPULATION_REF] == old_edge.snapshot.key
        assert context[KEY_OBJECTIVES_REF] == old_edge.snapshot.key
        assert context[KEY_CONSTRAINT_VIOLATIONS_REF] == old_edge.snapshot.key
        np.testing.assert_array_equal(solver.read_snapshot(context[KEY_SNAPSHOT_KEY])["population"], old_population)
    solver.rollback_snapshot_step_transaction()
    assert solver.get_population_authority_identity() == old_edge
    assert solver.snapshot_store.read(pending["key"]) is None


@pytest.mark.parametrize("status", ["idle", "rejected", "cancelled"])
def test_noncommitting_empty_attempt_context_reads_never_prepare_authority(status, monkeypatch):
    solver, problem, _, observations = _solver(empty_status=status)
    _seed_working_arrays(solver)
    calls = _spy_persist(solver, monkeypatch)

    outcome = solver.step()

    assert outcome.status == status
    assert outcome.committed is False
    assert outcome.evaluations == problem.calls == 0
    assert calls == []
    assert observations
    assert all(item["key"] is None and item["pending_key"] is None for item in observations)
    assert solver._snapshot_step_transaction is None
    _assert_no_authority(solver)


def test_evaluated_rejection_keeps_event_without_preparing_authority(monkeypatch):
    solver, problem, adapter, observations = _solver(infeasible=True)
    calls = _spy_persist(solver, monkeypatch)

    outcome = solver.step()

    assert outcome.status == "rejected"
    assert outcome.evaluations == problem.calls == solver.evaluation_count == 2
    assert adapter.updates == 0
    assert calls == []
    assert {item["phase"] for item in observations} == {"propose", "evaluate"}
    assert all(item["key"] is None and item["pending_key"] is None for item in observations)
    assert solver._snapshot_step_transaction is None
    _assert_no_authority(solver)
    event_key = outcome.metadata["evaluation_event"]["snapshot_key"]
    assert solver.read_evaluation_event_snapshot(event_key).semantic_complete is True


@pytest.mark.parametrize("failure", ["update", "after-writer"])
def test_step_failure_discards_authority_draft_without_publishing_it(failure, monkeypatch):
    solver, problem, adapter, observations = _solver(fail_update=failure == "update")
    calls = _spy_persist(solver, monkeypatch)
    if failure == "after-writer":
        def fail_after_writer(*args, **kwargs):
            raise RuntimeError("synthetic failure after writer")

        monkeypatch.setattr(solver, "_update_best", fail_after_writer)

    with pytest.raises(RuntimeError, match="synthetic .*failure"):
        solver.step()

    assert problem.calls == solver.evaluation_count == 2
    assert adapter.updates == 0
    assert solver._snapshot_step_transaction is None
    _assert_no_authority(solver)
    assert all(item["key"] is None and item["pending_key"] is None for item in observations)
    if failure == "update":
        assert calls == []
    else:
        assert len(calls) == 1
        assert calls[0]["pending_was_unpublished"] is True
        assert solver.snapshot_store.read(calls[0]["pending"]["key"]) is None


def test_public_context_outside_transaction_preserves_one_time_initial_snapshot(monkeypatch):
    solver, _, _, _ = _solver()
    _seed_working_arrays(solver)
    calls = _spy_persist(solver, monkeypatch)

    first = solver.build_context()
    contexts = [solver.build_context(), solver.get_context(), solver.build_context()]

    assert len(calls) == 1
    assert calls[0]["transaction_active"] is False
    assert calls[0]["pending"] is None
    edge = solver.get_population_authority_identity()
    assert edge is not None
    assert first[KEY_SNAPSHOT_KEY] == edge.snapshot.key
    assert all(context[KEY_SNAPSHOT_KEY] == edge.snapshot.key for context in contexts)
    record = solver.snapshot_store.read_verified(edge.snapshot)
    np.testing.assert_array_equal(record.data["population"], solver.population)
    assert solver._snapshot_step_transaction is None
