from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.plugins.runtime.companion_orchestrator import (
    CompanionEventRules,
    CompanionOrchestratorConfig,
    CompanionOrchestratorPlugin,
    CompanionPhaseScheduler,
)


class _LineMOProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="line_mo",
            dimension=1,
            objectives=["f1", "f2"],
            bounds=[(0.0, 1.0)],
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float).reshape(-1)
        v = float(arr[0])
        return np.asarray([v, 1.0 - v], dtype=float)


class _FixedAdapter(AlgorithmAdapter):
    def __init__(self, candidates: Sequence[float]) -> None:
        super().__init__(name="fixed_adapter")
        self._candidates = [float(v) for v in candidates]
        self.update_calls = 0

    def propose(self, solver: Any, context: Dict[str, Any]):
        _ = solver, context
        return [np.asarray([v], dtype=float) for v in self._candidates]

    def update(self, solver, candidates, objectives, violations, context):
        _ = solver, candidates, objectives, violations, context
        self.update_calls += 1


def _make_solver() -> ComposableSolver:
    problem = _LineMOProblem()
    adapter = _FixedAdapter(candidates=[0.0, 1.0])
    solver = ComposableSolver(problem=problem, adapter=adapter)
    init_x = np.asarray([[0.0], [1.0]], dtype=float)
    init_f, init_v = solver.evaluate_population(init_x)
    assert solver.write_population_snapshot(init_x, init_f, init_v)
    return solver


def _contains_ndarray(value: Any) -> bool:
    if isinstance(value, np.ndarray):
        return True
    if isinstance(value, dict):
        return any(_contains_ndarray(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_ndarray(v) for v in value)
    return False


def test_scheduler_mixed_periodic_event_cooldown_and_cap() -> None:
    cfg = CompanionOrchestratorConfig(
        trigger_mode="mixed",
        phase_min_generation=30,
        period_generations=20,
        phase_max_count=3,
        phase_cooldown_generations=15,
    )
    scheduler = CompanionPhaseScheduler(cfg)

    should, reason, cool = scheduler.should_trigger(
        generation=30,
        phase_count_used=0,
        last_return_generation=None,
        event_due=False,
    )
    assert should is True
    assert reason == "periodic"
    assert cool is False

    should, reason, cool = scheduler.should_trigger(
        generation=31,
        phase_count_used=0,
        last_return_generation=None,
        event_due=True,
    )
    assert should is True
    assert reason == "event"
    assert cool is False

    should, reason, cool = scheduler.should_trigger(
        generation=40,
        phase_count_used=1,
        last_return_generation=31,
        event_due=True,
    )
    assert should is False
    assert reason == "none"
    assert cool is True

    should, reason, cool = scheduler.should_trigger(
        generation=50,
        phase_count_used=1,
        last_return_generation=31,
        event_due=False,
    )
    assert should is True
    assert reason == "periodic"
    assert cool is False

    should, reason, cool = scheduler.should_trigger(
        generation=90,
        phase_count_used=3,
        last_return_generation=70,
        event_due=True,
    )
    assert should is False
    assert reason == "none"
    assert cool is False


def test_companion_blocking_phase_does_not_advance_generation() -> None:
    solver = _make_solver()
    cfg = CompanionOrchestratorConfig(
        trigger_mode="periodic",
        phase_min_generation=0,
        period_generations=1,
        phase_max_count=1,
        phase_cooldown_generations=0,
        max_injected_per_phase=0,
        levelset_eps=2.0,
        per_task_budget=1,
        global_budget=8,
    )
    plugin = CompanionOrchestratorPlugin(config=cfg)
    plugin.attach(solver)
    plugin.on_solver_init(solver)

    solver.generation = 0
    plugin.on_generation_end(0)

    assert int(solver.generation) == 0
    assert int(plugin.phase_count_used) == 1
    assert len(plugin.phase_runs) == 1
    assert int(plugin.phase_runs[0].return_generation) == 0


def test_multi_phase_lineage_has_versioned_entries() -> None:
    solver = _make_solver()
    cfg = CompanionOrchestratorConfig(
        trigger_mode="periodic",
        phase_min_generation=0,
        period_generations=1,
        phase_max_count=2,
        phase_cooldown_generations=0,
        max_injected_per_phase=0,
        levelset_eps=2.0,
        per_task_budget=1,
        global_budget=8,
    )
    plugin = CompanionOrchestratorPlugin(config=cfg)
    plugin.attach(solver)
    plugin.on_solver_init(solver)

    plugin.on_generation_end(0)
    plugin.on_generation_end(1)

    assert int(plugin.phase_count_used) == 2
    assert len(plugin.phase_runs) == 2
    assert plugin.lineage_index
    for entries in plugin.lineage_index.values():
        phases = sorted(int(item["phase_index"]) for item in entries)
        assert 1 in phases
        assert 2 in phases


def test_phase_end_injection_consistency() -> None:
    solver = _make_solver()
    cfg = CompanionOrchestratorConfig(
        trigger_mode="periodic",
        phase_min_generation=0,
        period_generations=1,
        phase_max_count=1,
        phase_cooldown_generations=0,
        max_injected_per_phase=10,
        levelset_eps=2.0,
        per_task_budget=1,
        global_budget=8,
        event_rules=CompanionEventRules(enable_stagnation=False, enable_diversity_drop=False),
    )
    plugin = CompanionOrchestratorPlugin(config=cfg)
    plugin.attach(solver)
    plugin.on_solver_init(solver)

    before_x, _, _ = plugin.resolve_population_snapshot(solver)
    before_n = int(before_x.shape[0])

    plugin.on_generation_end(0)
    assert len(plugin.phase_runs) == 1
    run = plugin.phase_runs[0]

    after_x, _, _ = plugin.resolve_population_snapshot(solver)
    after_n = int(after_x.shape[0])
    delta = after_n - before_n

    assert delta == int(run.injected_count)
    assert delta > 0
    assert int(run.success_count) == int(run.task_count)


def test_storage_writes_small_context_and_large_snapshot_refs() -> None:
    solver = _make_solver()
    cfg = CompanionOrchestratorConfig(
        trigger_mode="periodic",
        phase_min_generation=0,
        period_generations=1,
        phase_max_count=1,
        phase_cooldown_generations=0,
        max_injected_per_phase=2,
        levelset_eps=2.0,
        per_task_budget=1,
        global_budget=8,
    )
    plugin = CompanionOrchestratorPlugin(config=cfg)
    plugin.attach(solver)
    plugin.on_solver_init(solver)

    plugin.on_generation_end(0)
    snapshot = solver.context_store.snapshot()

    summary_key = f"{cfg.store_prefix}.phase.1.summary"
    assert summary_key in snapshot
    assert not _contains_ndarray(snapshot[summary_key])
    phase_snapshot_key = str(snapshot[summary_key].get("phase_snapshot_key") or "")
    assert phase_snapshot_key != ""
    assert solver.read_snapshot(phase_snapshot_key) is not None

    task_refs = []
    for entries in plugin.lineage_index.values():
        for entry in entries:
            key = str(entry.get("task_snapshot_key") or "")
            if key:
                task_refs.append(key)
    assert task_refs
    payload = solver.read_snapshot(task_refs[0])
    assert payload is not None
    assert "companion_population" in payload
