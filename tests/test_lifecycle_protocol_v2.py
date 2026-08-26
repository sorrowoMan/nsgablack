from __future__ import annotations

import copy
import threading
import time

import numpy as np
import pytest

from blackbase.project import ExecutionControl
from blackbase.resources import CancellationRef
from blackbase.plugin import ATTEMPT_END, GENERATION_END
from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter, PopulationPartition
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.control_plane import BaseController, StopController
from nsgablack.core.interfaces import BaseController as InterfaceBaseController
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


def test_interfaces_reexports_the_canonical_controller_protocol() -> None:
    assert InterfaceBaseController is BaseController


class _CompletionRecorder(Plugin):
    def __init__(self) -> None:
        super().__init__(name="completion_recorder")
        self.completed: list[int] = []

    def on_generation_committed(self, generation: int, outcome):
        del outcome
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

    assert result["step_attempts"] == 3
    assert result["steps_executed"] == 2
    assert result["steps"] == 2
    assert result["termination_reason"] == "step_limit"
    assert recorder.completed == [0, 1]


class _AttemptLifecycleRecorder(Plugin):
    def __init__(self) -> None:
        super().__init__(name="attempt_lifecycle")
        self.events: list[tuple[str, int, str | None]] = []

    def on_step_attempt_start(self, attempt: int, logical_step: int):
        self.events.append(("attempt_start", int(attempt), str(logical_step)))

    def on_generation_start(self, generation: int):
        self.events.append(("generation_start", int(generation), None))

    def on_generation_end(self, generation: int):
        self.events.append(("generation_end", int(generation), None))

    def on_step_attempt_end(self, attempt: int, logical_step: int, outcome):
        self.events.append(("attempt_end", int(attempt), str(outcome["status"])))

    def on_generation_committed(self, generation: int, outcome):
        self.events.append(("committed", int(generation), str(outcome["status"])))


def test_idle_attempt_has_balanced_transaction_hooks_without_commit_event() -> None:
    solver = _IdleThenCommitSolver()
    recorder = _AttemptLifecycleRecorder()
    solver.add_plugin(recorder)

    result = solver.run(max_steps=1)

    assert result["step_attempts"] == 2
    assert [event[0] for event in recorder.events] == [
        "attempt_start",
        "attempt_end",
        "attempt_start",
        "generation_start",
        "committed",
        "generation_end",
        "attempt_end",
    ]
    assert recorder.events[1][2] == "idle"
    assert recorder.events[-1][2] == "committed"


class _AlwaysIdleSolver(SolverBase):
    def step(self) -> StepOutcome:
        return StepOutcome(status="idle", reason="backpressure")


def test_attempt_budget_is_distinct_from_logical_step_budget() -> None:
    solver = _AlwaysIdleSolver(_Problem())

    result = solver.run(max_steps=2, max_step_attempts=3)

    assert result["status"] == "stopped"
    assert result["termination_reason"] == "attempt_limit"
    assert result["steps"] == 0
    assert result["step_attempts"] == 3
    assert solver.export_run_progress_state()["attempts_completed"] == 3


class _LegacyNoneSolver(SolverBase):
    def step(self):
        return None


def test_legacy_none_step_outcome_is_fail_closed_unless_explicitly_enabled() -> None:
    with pytest.raises(TypeError, match="must return StepOutcome"):
        _LegacyNoneSolver(_Problem()).run(max_steps=1)

    compatible = _LegacyNoneSolver(_Problem())
    compatible.set_legacy_step_outcome_compatibility(True)
    with pytest.warns(DeprecationWarning):
        result = compatible.run(max_steps=1)
    assert result["steps"] == 1


class _CommitAndStopSolver(SolverBase):
    def step(self) -> StepOutcome:
        return StepOutcome(
            status="committed",
            evaluations=1,
            stop_requested=True,
            reason="converged",
        )


def test_committed_step_stop_request_is_applied_after_commit_hooks() -> None:
    solver = _CommitAndStopSolver(_Problem())
    recorder = _CompletionRecorder()
    solver.add_plugin(recorder)

    result = solver.run(max_steps=5)

    assert result["status"] == "stopped"
    assert result["termination_reason"] == "converged"
    assert result["steps_executed"] == 1
    assert recorder.completed == [0]


class _CancelledWithoutFlagSolver(SolverBase):
    def step(self) -> StepOutcome:
        return StepOutcome(status="cancelled")


def test_cancelled_outcome_is_normalized_to_terminal_failure_semantics() -> None:
    outcome = StepOutcome(status="cancelled")
    assert outcome.stop_requested is True
    assert outcome.reason == "cancelled"

    result = _CancelledWithoutFlagSolver(_Problem()).run(max_steps=3)
    assert result["status"] == "stopped"
    assert result["termination_reason"] == "cancelled"
    assert result["steps_executed"] == 0


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
    assert payload["schema"] == "nsgablack.checkpoint.v9"
    assert state["population_authority_mode"] == "partitioned"
    assert state["population"] is None
    assert state["last_evaluated_batch"]["population"] is not None

    no_event_state = copy.deepcopy(state)
    no_event_state["last_evaluated_batch"] = {
        "population": None,
        "objectives": None,
        "constraint_violations": None,
    }
    no_event_state["evaluation_event"] = None
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


class _FailingEndPlugin(Plugin):
    def __init__(self) -> None:
        super().__init__(name="failing_end")
        self.attempt_ended = False

    def on_generation_end(self, generation: int):
        del generation
        raise RuntimeError("plugin generation cleanup failed")

    def on_step_attempt_end(self, attempt: int, logical_step: int, outcome):
        del attempt, logical_step, outcome
        self.attempt_ended = True


class _FailingAttemptEndController(BaseController):
    slots = (GENERATION_END, ATTEMPT_END)

    def __init__(self) -> None:
        super().__init__(name="failing_attempt_end")
        self.seen: list[str] = []

    def propose(self, solver, slot, context):
        del solver, context
        self.seen.append(slot)
        if slot == ATTEMPT_END:
            raise RuntimeError("controller attempt cleanup failed")
        return None


class _OneCommitSolver(SolverBase):
    def step(self) -> StepOutcome:
        return StepOutcome(status="committed")


def test_strict_lifecycle_end_failures_do_not_skip_other_participants() -> None:
    solver = _OneCommitSolver(_Problem(), plugin_strict=True)
    plugin = _FailingEndPlugin()
    controller = _FailingAttemptEndController()
    solver.add_plugin(plugin)
    solver.register_controller(controller)

    with pytest.raises(RuntimeError, match="lifecycle cleanup failed") as caught:
        solver.run(max_steps=1)

    assert controller.seen == [GENERATION_END, ATTEMPT_END]
    assert plugin.attempt_ended is True
    assert len(caught.value.errors) == 2


def test_stop_controller_state_roundtrips_through_checkpoint_components() -> None:
    source = SolverBase(_Problem())
    source_stop = StopController(patience=10)
    source.register_controller(source_stop)
    for _ in range(8):
        source_stop.propose(source, GENERATION_END, {"best_objective": 1.0})

    writer = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False)
    )
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="controller-state")
    controller_payload = payload["stateful_components"]["runtime_controller"]

    target = SolverBase(_Problem())
    target_stop = StopController(patience=10)
    target.register_controller(target_stop)
    reader = CheckpointResumePlugin(
        config=CheckpointResumeConfig(save_on_finish=False, strict=True)
    )
    reader.attach(target)
    restored = reader._apply_component_states(
        target,
        {"runtime_controller": controller_payload},
    )

    assert restored == {"runtime_controller"}
    assert target_stop._best == source_stop._best
    assert target_stop._stale == source_stop._stale == 7


class _LockHoldingAdapter(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__(name="lock_holder")
        self.lock = threading.RLock()
        self.value = 1

    def propose(self, control, context):
        del control, context
        return ()

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context

    def get_state(self):
        return {"value": self.value}

    def set_state(self, state):
        self.value = int(state["value"])


def test_adapter_transaction_uses_explicit_state_not_live_object_deepcopy() -> None:
    adapter = _LockHoldingAdapter()
    original_lock = adapter.lock
    transaction = adapter.begin_step_transaction()
    adapter.value = 9
    transaction.rollback()

    assert adapter.value == 1
    assert adapter.lock is original_lock


class _GenerationReceiptPlugin(Plugin):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        fail_start: bool = False,
    ) -> None:
        super().__init__(name=name)
        self.events = events
        self.fail_start = fail_start

    def on_generation_start(self, generation: int) -> None:
        self.events.append(f"{self.name}:start:{generation}")
        if self.fail_start:
            raise RuntimeError("generation start failed")

    def on_generation_end(self, generation: int) -> None:
        self.events.append(f"{self.name}:end:{generation}")


def test_solver_closes_only_plugins_present_in_the_generation_receipt() -> None:
    events: list[str] = []
    solver = _OneCommitSolver(_Problem(), plugin_strict=True)
    solver.add_plugin(_GenerationReceiptPlugin("first", events))
    solver.add_plugin(
        _GenerationReceiptPlugin("broken", events, fail_start=True)
    )
    solver.add_plugin(_GenerationReceiptPlugin("never-started", events))

    with pytest.raises(RuntimeError, match="generation start failed"):
        solver.run(max_steps=1)

    assert events == [
        "first:start:0",
        "broken:start:0",
        "first:end:0",
    ]


class _FinalizationRecorder(Plugin):
    def __init__(self, events: list[str]) -> None:
        super().__init__(name="finalization_recorder")
        self.events = events

    def on_solver_finish(self, result) -> None:
        del result
        self.events.append("finishing")

    def on_solver_finalized(self, result) -> None:
        del result
        self.events.append("finalized")


class _TeardownFailureSolver(_OneCommitSolver):
    def teardown(self) -> None:
        raise RuntimeError("teardown failed")


def test_teardown_failure_never_publishes_finalized_result() -> None:
    events: list[str] = []
    solver = _TeardownFailureSolver(_Problem(), plugin_strict=True)
    solver.add_plugin(_FinalizationRecorder(events))

    with pytest.raises(RuntimeError, match="teardown failed"):
        solver.run(max_steps=1)

    assert events == ["finishing"]
    assert solver.last_result is None


def test_successful_teardown_publishes_finalized_result_after_finishing() -> None:
    events: list[str] = []
    solver = _OneCommitSolver(_Problem(), plugin_strict=True)
    solver.add_plugin(_FinalizationRecorder(events))

    result = solver.run(max_steps=1)

    assert events == ["finishing", "finalized"]
    assert solver.last_result is result


class _FinalizationFailureRecorder(Plugin):
    def __init__(self) -> None:
        super().__init__(name="finalization_failure_recorder")
        self.error_phases: list[str | None] = []

    def on_solver_finalized(self, result) -> None:
        del result
        raise RuntimeError("final publication failed")

    def on_error(self, error, context=None) -> None:
        del error
        self.error_phases.append(dict(context or {}).get("error_phase"))


def test_finalized_observer_failure_preserves_authoritative_last_result() -> None:
    solver = _OneCommitSolver(_Problem(), plugin_strict=True)
    recorder = _FinalizationFailureRecorder()
    solver.add_plugin(recorder)

    result = solver.run(max_steps=1)

    assert recorder.error_phases == []
    assert result["status"] == "ok"
    assert solver.last_result is result
    failures = solver._finalization_observer_failures
    assert len(failures) == 1
    assert failures[0]["observer"] == (
        "nsgablack.plugin_manager.on_solver_finalized"
    )
    assert failures[0]["error_type"] == "PluginLifecycleCleanupError"
    assert "final publication failed" in failures[0]["message"]


class _RunLifecycleProbe(Plugin):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        fail_init: bool = False,
        fail_error: bool = False,
        fail_finalized: bool = False,
    ) -> None:
        super().__init__(name=name)
        self.events = events
        self.fail_init = fail_init
        self.fail_error = fail_error
        self.fail_finalized = fail_finalized

    def on_solver_init(self, solver) -> None:
        del solver
        self.events.append(f"{self.name}:init")
        if self.fail_init:
            raise RuntimeError("run init failed")

    def on_solver_finish(self, result) -> None:
        self.events.append(f"{self.name}:finish:{result.get('status')}")

    def on_solver_finalized(self, result) -> None:
        del result
        self.events.append(f"{self.name}:finalized")
        if self.fail_finalized:
            raise RuntimeError("run finalized failed")

    def on_error(self, error, context=None) -> None:
        del error, context
        self.events.append(f"{self.name}:error")
        if self.fail_error:
            raise RuntimeError("error observer failed")


class _PrimaryFailureSolver(SolverBase):
    def step(self) -> StepOutcome:
        raise ValueError("primary step failure")


def test_run_init_failure_closes_only_plugins_that_completed_init() -> None:
    events: list[str] = []
    solver = _OneCommitSolver(_Problem(), plugin_strict=True)
    solver.add_plugin(_RunLifecycleProbe("first", events))
    solver.add_plugin(_RunLifecycleProbe("broken", events, fail_init=True))
    solver.add_plugin(_RunLifecycleProbe("never", events))

    with pytest.raises(RuntimeError, match="run init failed"):
        solver.run(max_steps=1)

    assert events == [
        "first:init",
        "broken:init",
        "first:error",
        "first:finish:failed",
    ]


def test_failing_on_error_observer_never_replaces_primary_and_fanout_continues() -> None:
    events: list[str] = []
    solver = _PrimaryFailureSolver(_Problem(), plugin_strict=True)
    solver.add_plugin(_RunLifecycleProbe("broken", events, fail_error=True))
    solver.add_plugin(_RunLifecycleProbe("second", events))

    with pytest.raises(ValueError, match="primary step failure") as captured:
        solver.run(max_steps=1)

    assert "broken:error" in events
    assert "second:error" in events
    assert "broken:finish:failed" in events
    assert "second:finish:failed" in events
    assert captured.value._nsgablack_on_error_failures[0]["plugin"] == "broken"


def test_finalization_failure_still_notifies_every_run_participant() -> None:
    events: list[str] = []
    solver = _OneCommitSolver(_Problem(), plugin_strict=True)
    solver.add_plugin(
        _RunLifecycleProbe("broken", events, fail_finalized=True)
    )
    solver.add_plugin(_RunLifecycleProbe("second", events))

    result = solver.run(max_steps=1)

    assert "broken:finalized" in events
    assert "second:finalized" in events
    assert "broken:error" not in events
    assert "second:error" not in events
    assert result is solver.last_result
    failures = solver._finalization_observer_failures
    assert len(failures) == 1
    assert "run finalized failed" in failures[0]["message"]
