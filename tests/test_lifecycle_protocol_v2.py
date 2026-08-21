from __future__ import annotations

import copy
import time

import numpy as np
import pytest

from blackbase.project import ExecutionControl
from blackbase.resources import CancellationRef
from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter, PopulationPartition
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.runtime_governance import (
    resolve_population_partitions,
    resolve_population_snapshot,
)
from nsgablack.core.state import StepOutcome
from nsgablack.core.solver_helpers import PartitionedPopulationSnapshotError
from nsgablack.core.solver_helpers import population_snapshot_authority_mode
from nsgablack.plugins.base import Plugin
from nsgablack.plugins.system.checkpoint_resume import (
    CheckpointResumeConfig,
    CheckpointResumePlugin,
)


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=1, bounds=[(-10.0, 10.0)], objectives=["min"])

    def evaluate(self, candidate):
        value = float(np.asarray(candidate, dtype=float).reshape(-1)[0])
        return value * value


class _CompletionRecorder(Plugin):
    def __init__(self) -> None:
        super().__init__(name="completion_recorder")
        self.completed: list[int] = []

    def on_generation_end(self, generation: int):
        self.completed.append(int(generation))


class _IdleThenCommitSolver(SolverBase):
    def __init__(self) -> None:
        super().__init__(_Problem())
        self.attempts = 0

    def step(self) -> StepOutcome:
        self.attempts += 1
        if self.attempts == 1:
            return StepOutcome(status="idle", reason="no_candidate")
        return StepOutcome(status="committed", evaluations=1, proposals=1)


def test_idle_step_does_not_create_a_completed_generation() -> None:
    solver = _IdleThenCommitSolver()
    recorder = _CompletionRecorder()
    solver.add_plugin(recorder)

    result = solver.run(max_steps=2)

    assert result["step_attempts"] == 2
    assert result["steps_executed"] == 1
    assert result["steps"] == 1
    assert result["termination_reason"] == "attempt_limit"
    assert recorder.completed == [0]


class _PartitionedAdapter(AlgorithmAdapter):
    population_state_mode = "partitioned"

    def __init__(self) -> None:
        super().__init__(name="partitioned")
        self._partitions: tuple[PopulationPartition, ...] = ()

    def propose(self, control, context):
        del control, context
        return (np.asarray([2.0]),)

    def update(self, control, candidates, feedback, context):
        del control, context
        objectives, violations = feedback
        self._partitions = (
            PopulationPartition(
                partition_id="worker-a",
                population=np.asarray(candidates, dtype=float),
                objectives=np.asarray(objectives, dtype=float),
                violations=np.asarray(violations, dtype=float),
                owner=self.name,
            ),
        )

    def get_population_partitions(self):
        return self._partitions


def test_partitioned_snapshot_never_exposes_last_batch_as_one_population(tmp_path) -> None:
    solver = ComposableSolver(_Problem(), adapter=_PartitionedAdapter())
    solver.run(max_steps=1)

    snapshot = solver.read_snapshot()
    assert snapshot is not None
    assert snapshot["population_authority"]["authority_mode"] == "partitioned"
    assert "population" not in snapshot
    assert "objectives" not in snapshot
    assert "constraint_violations" not in snapshot
    assert "last_evaluated_batch" in snapshot
    assert snapshot["population_partitions"]["partitions"]
    with pytest.raises(PartitionedPopulationSnapshotError):
        resolve_population_snapshot(solver)
    solver.population_authority_mode = "single"
    with pytest.raises(PartitionedPopulationSnapshotError):
        resolve_population_snapshot(solver)
    with pytest.raises(PartitionedPopulationSnapshotError):
        Plugin(name="legacy_reader").get_population_snapshot(solver)
    solver.population_authority_mode = "partitioned"
    partitions = resolve_population_partitions(solver)
    assert tuple(item.partition_id for item in partitions) == ("worker-a",)
    context = solver.get_context()
    assert "population_ref" not in context
    assert "objectives_ref" not in context
    assert "constraint_violations_ref" not in context

    checkpoint = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path),
            save_on_finish=False,
        )
    )
    checkpoint.attach(solver)
    payload = checkpoint._build_payload(solver=solver, reason="partitioned")
    state = payload["solver_state"]
    assert payload["schema"] == "nsgablack.checkpoint.v6"
    assert state["population_authority_mode"] == "partitioned"
    assert state["population"] is None
    assert state["last_evaluated_batch"]["population"] is not None

    no_event_state = copy.deepcopy(state)
    no_event_state["last_evaluated_batch"] = {
        "population": None,
        "objectives": None,
        "constraint_violations": None,
    }
    no_event_state["candidate_population"] = None
    no_event_target = ComposableSolver(_Problem(), adapter=_PartitionedAdapter())
    no_event_reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False)
    )
    no_event_reader.attach(no_event_target)
    no_event_reader._apply_solver_state(no_event_target, no_event_state, 1)
    no_event_snapshot = no_event_target.read_snapshot()
    assert no_event_snapshot is not None
    assert no_event_snapshot["population_authority"]["authority_mode"] == "partitioned"
    assert no_event_snapshot["population_partitions"]["partitions"]
    assert no_event_snapshot["last_evaluated_batch"] == {}

    path = checkpoint.save_checkpoint(reason="partitioned-roundtrip")
    assert path is not None
    restored = ComposableSolver(_Problem(), adapter=_PartitionedAdapter())
    reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path),
            save_on_finish=False,
        )
    )
    restored.add_plugin(reader)
    assert reader.resume(str(path)) is True
    restored.run(max_steps=1)
    assert restored.population_authority_mode == "partitioned"
    restored_snapshot = restored.read_snapshot()
    assert restored_snapshot is not None
    assert "population" not in restored_snapshot
    assert resolve_population_partitions(restored)[0].partition_id == "worker-a"


def test_population_snapshot_authority_rejects_contradictory_envelopes() -> None:
    with pytest.raises(ValueError, match="must not expose top-level"):
        population_snapshot_authority_mode(
            {
                "population_authority": {"authority_mode": "partitioned"},
                "population": [[1.0]],
            }
        )
    assert population_snapshot_authority_mode(
        {"last_evaluated_batch": {"population": [[1.0]]}}
    ) == "partitioned"


class _InitObserver(Plugin):
    def __init__(self) -> None:
        super().__init__(name="init_observer")
        self.seen_generation: int | None = None

    def on_solver_init(self, solver):
        self.seen_generation = int(solver.generation)


def test_auto_resume_applies_before_ordinary_init_hooks(tmp_path) -> None:
    source = ComposableSolver(_Problem())
    source.set_generation(3)
    writer = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path),
            save_on_finish=False,
        )
    )
    source.add_plugin(writer)
    assert writer.save_checkpoint(reason="restore-order") is not None

    target = ComposableSolver(_Problem())
    reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(
            checkpoint_dir=str(tmp_path),
            save_on_finish=False,
            auto_resume=True,
            resume_from="latest",
        )
    )
    observer = _InitObserver()
    target.add_plugin(reader)
    target.add_plugin(observer)
    target.run(max_steps=3)

    assert reader.last_loaded_path is not None
    assert observer.seen_generation == 3


class _DeadlineRuntime:
    def __init__(self) -> None:
        self.control = ExecutionControl(
            cancellation=CancellationRef(deadline_at=time.time() - 1.0)
        )

    def checkpoint(self) -> None:
        return None


def test_parent_deadline_clamps_run_progress_before_first_step() -> None:
    solver = _IdleThenCommitSolver()
    solver.set_case_runtime(_DeadlineRuntime())

    result = solver.run(max_steps=2)

    assert result["status"] == "stopped"
    assert result["termination_reason"] == "logical_deadline"
    assert result["step_attempts"] == 0
    assert result["steps_executed"] == 0
