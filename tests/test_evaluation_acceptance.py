from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from nsgablack.adapters import AlgorithmAdapter, PopulationPartition
from nsgablack.core import (
    BlackBoxProblem,
    ComposableSolver,
    FeasibleEvaluationAcceptance,
)
from nsgablack.plugins.system.checkpoint_resume import (
    CheckpointResumeConfig,
    CheckpointResumePlugin,
)
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch


def test_feedback_subset_normalizes_tuple_and_empty_row_selectors() -> None:
    feedback = OptimizationFeedbackBatch.from_arrays(
        [[1.0], [2.0], [3.0]],
        [0.0, 0.0, 0.0],
    )
    assert feedback.subset((0, 2)).objectives[:, 0].tolist() == [1.0, 3.0]
    assert feedback.subset(()).candidate_count == 0


class _ConstraintProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-2.0, 2.0)])

    def evaluate(self, candidate):
        return float(np.asarray(candidate, dtype=float)[0] ** 2)

    def evaluate_constraints(self, candidate):
        return max(0.0, float(np.asarray(candidate, dtype=float)[0]))


class _RecordingAdapter(AlgorithmAdapter):
    def __init__(self, proposals) -> None:
        super().__init__(name="recording")
        self.proposals = tuple(np.asarray(item, dtype=float) for item in proposals)
        self.updated: list[np.ndarray] = []
        self.dispositions = []

    def propose(self, control: Any, context):
        del control, context
        return self.proposals

    def update(self, control: Any, candidates, feedback, context) -> None:
        del control, feedback, context
        self.updated.append(np.asarray(candidates, dtype=float).copy())

    def on_proposal_disposition(self, control, disposition, context) -> None:
        del control, context
        self.dispositions.append(disposition)

    def get_state(self):
        return {
            "updated": [item.tolist() for item in self.updated],
            "dispositions": list(self.dispositions),
            "update_count": int(getattr(self, "update_count", 0)),
        }

    def set_state(self, state):
        self.updated = [np.asarray(item, dtype=float) for item in state["updated"]]
        self.dispositions = list(state["dispositions"])
        if hasattr(self, "update_count"):
            self.update_count = int(state["update_count"])


def test_feasible_acceptance_subsets_adapter_update_and_preserves_evaluation_count() -> None:
    adapter = _RecordingAdapter(([-1.0], [1.0]))
    solver = ComposableSolver(
        _ConstraintProblem(),
        adapter=adapter,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
    )

    outcome = solver.step()

    assert outcome.status == "committed"
    assert outcome.evaluations == 2
    assert outcome.metadata["accepted_evaluations"] == 1
    assert len(adapter.updated) == 1
    assert adapter.updated[0].tolist() == [[-1.0]]
    assert adapter.dispositions[0].accepted_indices == (0,)
    assert solver.last_step_summary["num_evaluated"] == 2
    disposition = dict(outcome.metadata["evaluation_disposition"])
    assert disposition["status"] == "committed"
    assert disposition["event_id"] == outcome.metadata["evaluation_event"]["event_id"]
    assert disposition["authority_snapshot_key"] == solver._latest_snapshot_handle.key
    authority = solver.read_snapshot(disposition["authority_snapshot_key"])
    assert authority["last_evaluation_disposition"]["event_id"] == disposition["event_id"]


def test_zero_feasible_candidates_is_rejected_without_adapter_update() -> None:
    adapter = _RecordingAdapter(([0.5], [1.0]))
    solver = ComposableSolver(
        _ConstraintProblem(),
        adapter=adapter,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
    )

    outcome = solver.step()

    assert outcome.status == "rejected"
    assert outcome.evaluations == 2
    assert outcome.reason == "feasible_evaluation_filter"
    assert adapter.updated == []
    assert adapter.dispositions[0].accepted_indices == ()
    assert solver.get_incumbent() is None


class _SequencedAdapter(_RecordingAdapter):
    def __init__(self, proposal_batches) -> None:
        super().__init__(())
        self.proposal_batches = tuple(
            tuple(np.asarray(item, dtype=float) for item in batch)
            for batch in proposal_batches
        )
        self.proposal_index = 0

    def propose(self, control: Any, context):
        del control, context
        batch = self.proposal_batches[self.proposal_index]
        self.proposal_index += 1
        return batch


class _AcceptThenReject:
    def __init__(self) -> None:
        self.contexts: list[dict[str, Any]] = []

    def select(self, candidates, feedback, context):
        del feedback
        self.contexts.append(dict(context))
        count = len(candidates.semantic_states)
        accepted = count if len(self.contexts) == 1 else 0
        return BatchDisposition.prefix(
            proposed_count=count,
            accepted_count=accepted,
            reason="test_acceptance",
        )


def test_zero_acceptance_restores_authority_but_keeps_full_evaluation_event() -> None:
    adapter = _SequencedAdapter((([-1.0], [-0.5]), ([0.5], [1.0])))
    policy = _AcceptThenReject()
    solver = ComposableSolver(
        _ConstraintProblem(),
        adapter=adapter,
        evaluation_acceptance_policy=policy,
    )

    first = solver.step()
    first_authority_key = str(solver._latest_snapshot_handle.key)
    old_population = np.array(solver.population, copy=True)
    old_batch = solver.get_candidate_population_batch()
    second = solver.step()

    assert first.status == "committed"
    assert second.status == "rejected"
    assert len(adapter.updated) == 1
    assert np.array_equal(solver.population, old_population)
    restored_batch = solver.get_candidate_population_batch()
    assert restored_batch is not None
    assert old_batch is not None
    assert restored_batch.candidate_tokens == old_batch.candidate_tokens
    assert np.array_equal(restored_batch.numeric_matrix, old_batch.numeric_matrix)
    event_population, event_objectives, event_violations = (
        solver.get_last_evaluated_batch_snapshot()
    )
    assert event_population.tolist() == [[0.5], [1.0]]
    assert event_objectives.shape == (2, 1)
    assert event_violations.tolist() == [0.5, 1.0]

    snapshot = solver.read_snapshot()
    assert snapshot is not None
    assert np.array_equal(snapshot["population"], old_population)
    event_snapshot_key = policy.contexts[-1]["metadata"]["evaluation_event"][
        "snapshot_key"
    ]
    event_snapshot = solver.read_snapshot(event_snapshot_key)
    assert event_snapshot is not None
    assert event_snapshot["last_evaluation_event"]["population"].tolist() == [
        [0.5],
        [1.0],
    ]
    # The policy sees post-evaluation counters and the staged event snapshot.
    assert policy.contexts[-1]["evaluation_count"] == 4
    assert policy.contexts[-1]["snapshot_key"]
    event_context = policy.contexts[-1]["metadata"]["evaluation_event"]
    assert event_context["best_objective"] == 0.25
    assert event_context["best_constraint_violation"] == 0.5
    assert event_context["best_index"] == 0
    assert event_context["num_candidates"] == 2
    assert event_context["evaluation_count"] == 4
    assert event_context["candidate_token"]
    assert event_context["snapshot_key"] == policy.contexts[-1]["snapshot_key"]
    rejected = dict(second.metadata["evaluation_disposition"])
    assert rejected["status"] == "rejected"
    assert rejected["authority_snapshot_key"] == first_authority_key
    disposition_record = solver.read_snapshot(
        rejected["disposition_snapshot_key"]
    )
    assert disposition_record["last_evaluation_disposition"]["status"] == "rejected"


def test_partial_acceptance_snapshot_separates_event_from_committed_batch() -> None:
    adapter = _RecordingAdapter(([-1.0], [1.0]))
    solver = ComposableSolver(
        _ConstraintProblem(),
        adapter=adapter,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
    )

    solver.step()
    snapshot = solver.read_snapshot()

    assert snapshot is not None
    assert snapshot["population"].tolist() == [[-1.0]]
    assert snapshot["last_evaluation_event"]["population"].tolist() == [
        [-1.0],
        [1.0],
    ]

    writer = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False)
    )
    writer.attach(solver)
    payload = writer._build_payload(solver=solver, reason="acceptance-event")
    state = payload["solver_state"]
    assert state["population"].tolist() == [[-1.0]]
    assert state["last_evaluated_batch"]["population"].tolist() == [
        [-1.0],
        [1.0],
    ]
    assert state["evaluation_disposition"]["status"] == "committed"

    restored = ComposableSolver(_ConstraintProblem(), adapter=_RecordingAdapter(()))
    reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False)
    )
    reader.attach(restored)
    reader._apply_solver_state(restored, state, 0)
    restored_event, _, _ = restored.get_last_evaluated_batch_snapshot()
    assert restored.population.tolist() == [[-1.0]]
    assert restored_event.tolist() == [[-1.0], [1.0]]
    assert (
        restored.export_evaluation_disposition_checkpoint_state()
        == state["evaluation_disposition"]
    )


def test_partial_acceptance_scores_each_evaluated_candidate_once() -> None:
    calls: list[tuple[float, ...]] = []

    def scalarizer(row, violation, context):
        del violation, context
        values = tuple(float(value) for value in np.asarray(row).reshape(-1))
        calls.append(values)
        return float(sum(values))

    solver = ComposableSolver(
        _ConstraintProblem(),
        adapter=_RecordingAdapter(([-1.0], [1.0])),
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
    )
    solver.set_incumbent_scalarizer(
        scalarizer,
        policy_id="test-counting/v1",
    )

    outcome = solver.step()

    assert outcome.metadata["accepted_evaluations"] == 1
    assert calls == [(1.0,), (1.0,)]


class _PartitionedRecordingAdapter(_RecordingAdapter):
    population_state_mode = "partitioned"

    def __init__(self, proposals) -> None:
        super().__init__(proposals)
        self.partitions = ()

    def update(self, control: Any, candidates, feedback, context) -> None:
        super().update(control, candidates, feedback, context)
        objectives, violations = feedback
        self.partitions = (
            PopulationPartition(
                partition_id="accepted",
                population=np.asarray(candidates, dtype=float),
                objectives=np.asarray(objectives, dtype=float),
                violations=np.asarray(violations, dtype=float),
                owner=self.name,
            ),
        )

    def get_population_partitions(self):
        return self.partitions


class _FailingAuthorityAdapter(_RecordingAdapter):
    population_state_mode = "single"

    def __init__(self) -> None:
        super().__init__(([-1.0],))
        self.update_count = 0

    def update(self, control: Any, candidates, feedback, context) -> None:
        super().update(control, candidates, feedback, context)
        self.update_count += 1

    def get_population_snapshot(self):
        raise RuntimeError("authority commit failed")


def test_step_transaction_rolls_back_adapter_and_solver_authority_on_commit_error() -> None:
    adapter = _FailingAuthorityAdapter()
    solver = ComposableSolver(_ConstraintProblem(), adapter=adapter)

    with pytest.raises(RuntimeError, match="authority commit failed") as captured:
        solver.step()

    assert adapter.update_count == 0
    assert adapter.updated == []
    assert adapter.dispositions == []
    assert solver.population is None
    assert solver.get_incumbent() is None
    # Completed evaluation evidence is immutable history, not authority, and
    # therefore survives the aborted authority commit.
    event_population, _, _ = solver.get_last_evaluated_batch_snapshot()
    assert event_population.tolist() == [[-1.0]]
    failed = captured.value._nsgablack_error_context["evaluation_disposition"]
    assert failed["status"] == "failed"
    assert failed["event_id"] == solver._last_evaluation_event_id
    record = solver.read_snapshot(failed["disposition_snapshot_key"])
    assert record["last_evaluation_disposition"]["status"] == "failed"


def test_partitioned_snapshot_preserves_full_event_after_partial_acceptance() -> None:
    adapter = _PartitionedRecordingAdapter(([-1.0], [1.0]))
    solver = ComposableSolver(
        _ConstraintProblem(),
        adapter=adapter,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
    )

    solver.step()
    snapshot = solver.read_snapshot()

    assert snapshot is not None
    assert snapshot["population_authority"]["authority_mode"] == "partitioned"
    partition = snapshot["population_partitions"]["partitions"][0]["partition"]
    assert partition["population"] == [[-1.0]]
    assert snapshot["last_evaluated_batch"]["population"].tolist() == [
        [-1.0],
        [1.0],
    ]
