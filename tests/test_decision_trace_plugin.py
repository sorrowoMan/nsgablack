from __future__ import annotations

from pathlib import Path

from nsgablack.plugins.ops.decision_trace import DecisionTraceConfig, DecisionTracePlugin
from nsgablack.utils.runtime import DecisionReplayEngine, record_decision_event


class _PM:
    def trigger(self, event_name, *args, **kwargs):
        return None


class _Adapter:
    def propose(self, solver):
        return [0.0]

    def update(self, solver, new_population, new_objectives):
        return True


class _Solver:
    def __init__(self):
        self.generation = 0
        self.step_count = 0
        self.context = {}
        self.plugin_manager = _PM()
        self.adapter = _Adapter()

    def evaluate_individual(self, x, individual_id=None):
        return 1.0, 0.0

    def evaluate_population(self, pop):
        return [1.0], [0.0]


def test_decision_trace_plugin_records_and_replays(tmp_path: Path):
    solver = _Solver()
    plugin = DecisionTracePlugin(
        config=DecisionTraceConfig(
            output_dir=str(tmp_path),
            run_id="demo",
            overwrite=True,
            capture_plugin_events=True,
            capture_evaluate=True,
            capture_adapter=True,
        )
    )
    plugin.on_solver_init(solver)

    solver.evaluate_individual([0.0], individual_id=1)
    solver.evaluate_population([[0.0]])
    solver.adapter.propose(solver)
    solver.adapter.update(solver, [[0.0]], [[1.0]])
    solver.plugin_manager.trigger("on_generation_end", 0)

    record_decision_event(
        solver,
        event_type="fallback",
        component="plugin.test",
        decision="fallback_to_truth",
        reason_code="confidence_low",
        inputs={"confidence": 0.2},
        thresholds={"min_confidence": 0.8},
    )

    result = {}
    plugin.on_solver_finish(result)
    jsonl = tmp_path / "demo.decision_trace.jsonl"
    assert jsonl.is_file()
    engine = DecisionReplayEngine.from_jsonl(jsonl)
    summary = engine.summary()
    assert int(summary["count"]) >= 6
    assert any(e.get("event_type") == "fallback" for e in engine.events)
