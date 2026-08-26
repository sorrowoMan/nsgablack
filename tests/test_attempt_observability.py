from __future__ import annotations

import json
import threading

import numpy as np
import pytest

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.state import StepOutcome
from nsgablack.plugins.ops.profiler import ProfilerConfig, ProfilerPlugin
from nsgablack.plugins.system.async_event_hub import (
    AsyncEventHubConfig,
    AsyncEventHubPlugin,
)
import nsgablack.plugins.system.async_event_hub as async_event_hub_module


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=1, bounds=[(-1.0, 1.0)], objectives=["min"])

    def evaluate(self, candidate):
        return float(np.asarray(candidate, dtype=float).reshape(-1)[0] ** 2)


class _RejectedThenCommittedSolver(SolverBase):
    def __init__(self, hub: AsyncEventHubPlugin | None = None) -> None:
        super().__init__(_Problem())
        self.attempt_index = 0
        self.hub = hub

    def step(self) -> StepOutcome:
        self.attempt_index += 1
        if self.hub is not None:
            self.hub.record_event(
                kind="set",
                key="attempt_value",
                value=self.attempt_index,
                source="test",
            )
        if self.attempt_index == 1:
            self.evaluation_count += 2
            return StepOutcome(status="rejected", evaluations=2, reason="filtered")
        self.evaluation_count += 1
        return StepOutcome(status="committed", evaluations=1)


def test_profiler_accounts_each_attempt_without_cross_attempt_eval_delta(tmp_path) -> None:
    profiler = ProfilerPlugin(
        config=ProfilerConfig(
            output_dir=str(tmp_path),
            run_id="attempts",
            overwrite=True,
        )
    )
    solver = _RejectedThenCommittedSolver()
    solver.add_plugin(profiler)

    result = solver.run(max_steps=1)
    payload = json.loads((tmp_path / "attempts.profile.json").read_text("utf-8"))

    assert result["step_attempts"] == 2
    assert [item["status"] for item in payload["per_attempt"]] == [
        "rejected",
        "committed",
    ]
    assert [item["eval_delta"] for item in payload["per_attempt"]] == [2, 1]
    assert payload["per_generation"][0]["eval_delta"] == 1


def test_async_event_hub_does_not_merge_rejected_events_into_generation() -> None:
    hub = AsyncEventHubPlugin()
    solver = _RejectedThenCommittedSolver(hub)
    solver.add_plugin(hub)

    solver.run(max_steps=1)

    assert len(hub.noncommitted_events) == 1
    assert hub.noncommitted_events[0]["value"] == 1
    assert hub.noncommitted_events[0]["attempt_status"] == "rejected"
    assert len(hub.committed_events) == 1
    assert hub.committed_events[0]["value"] == 2
    assert hub.committed_events[0]["attempt_status"] == "committed"
    assert hub.pending_events == []
    assert [item["event_count"] for item in hub.attempt_audit] == [1, 1]


def test_async_event_hub_commits_preexisting_background_events() -> None:
    hub = AsyncEventHubPlugin()
    solver = _RejectedThenCommittedSolver()
    solver.add_plugin(hub)
    hub.record_event(kind="set", key="background", value=7, source="thread")

    solver.run(max_steps=1)

    assert hub.pending_events == []
    assert [item["key"] for item in hub.committed_events] == ["background"]


def test_sync_event_is_transactional_inside_rejected_attempt() -> None:
    hub = AsyncEventHubPlugin(AsyncEventHubConfig(mode="sync"))
    context: dict[str, object] = {}
    hub.on_step_attempt_start(1, 0)
    hub.record_event(
        context=context,
        kind="set",
        key="must_not_leak",
        value=1,
    )
    assert "must_not_leak" not in context

    hub.on_step_attempt_end(
        1,
        0,
        {"status": "rejected", "committed": False},
    )
    assert "must_not_leak" not in context
    assert hub.pending_events == []
    assert hub.noncommitted_events[0]["key"] == "must_not_leak"


def test_async_event_commit_detaches_exact_queue_under_drop_old(monkeypatch) -> None:
    hub = AsyncEventHubPlugin(AsyncEventHubConfig(max_pending=1, drop_policy="drop_old"))
    hub.record_event(kind="set", key="a", value=1)
    detached = threading.Event()
    resume = threading.Event()

    def blocking_replay(context, events, strict=False):
        del strict
        detached.set()
        assert resume.wait(timeout=2.0)
        return {**context, "replayed": [event["key"] for event in events]}

    monkeypatch.setattr(async_event_hub_module, "replay_context", blocking_replay)
    worker = threading.Thread(target=lambda: hub.commit(context={}))
    worker.start()
    assert detached.wait(timeout=1.0)
    hub.record_event(kind="set", key="b", value=2)
    resume.set()
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert [event["key"] for event in hub.committed_events] == ["a"]
    assert [event["key"] for event in hub.pending_events] == ["b"]


def test_async_event_reads_attempt_identity_under_the_queue_lock() -> None:
    hub = AsyncEventHubPlugin()
    with hub._lock:
        hub.current_attempt = 2
        hub.current_generation = 4
        hub._attempt_active = True
        worker = threading.Thread(
            target=lambda: hub.record_event(kind="set", key="x", value=1)
        )
        worker.start()
        hub.current_attempt = 3
        hub.current_generation = 5
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert hub.attempt_events[0]["attempt"] == 3
    assert hub.attempt_events[0]["generation"] == 5


def test_async_event_hub_detaches_values_and_committed_context_results() -> None:
    hub = AsyncEventHubPlugin()
    source = {"items": [1], "array": np.asarray([2.0])}
    hub.record_event(kind="set", key="payload", value=source)

    source["items"].append(9)
    source["array"][0] = 7.0
    hub.commit(context={})
    first = hub.get_committed_context()
    assert first["payload"]["items"] == [1]
    assert first["payload"]["array"].tolist() == [2.0]

    first["payload"]["items"].append(3)
    first["payload"]["array"][0] = 5.0
    second = hub.get_committed_context()
    assert second["payload"]["items"] == [1]
    assert second["payload"]["array"].tolist() == [2.0]


def test_async_event_hub_strict_commit_restores_invalid_detached_batch() -> None:
    hub = AsyncEventHubPlugin()
    hub.pending_events = [{"kind": "unknown", "key": "value", "value": 1}]

    with pytest.raises(ValueError, match="unsupported context event kind"):
        hub.commit(context={})

    assert hub.pending_events == [
        {"kind": "unknown", "key": "value", "value": 1}
    ]
