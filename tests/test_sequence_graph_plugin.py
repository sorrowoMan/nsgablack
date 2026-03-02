from __future__ import annotations

import json
from pathlib import Path

from nsgablack.plugins.base import PluginManager
from nsgablack.plugins.ops.sequence_graph import SequenceGraphConfig, SequenceGraphPlugin


class _Adapter:
    def propose(self, *args, **kwargs):
        return [0.0]

    def update(self, *args, **kwargs):
        return True


class _Solver:
    def __init__(self):
        self.generation = 0
        self.step_count = 0
        self.plugin_manager = PluginManager()
        self.adapter = _Adapter()

    def evaluate_population(self, pop):
        return [1.0], [0.0]


def test_sequence_graph_plugin_records_and_writes(tmp_path: Path):
    solver = _Solver()
    plugin = SequenceGraphPlugin(
        config=SequenceGraphConfig(
            output_dir=str(tmp_path),
            run_id="demo",
            overwrite=True,
            flush_every=0,
            capture_plugin_events=False,
            capture_adapter=True,
            capture_evaluate_population=True,
        )
    )
    plugin.on_solver_init(solver)

    solver.evaluate_population([[0.0]])
    solver.adapter.propose(solver, {})
    solver.adapter.update(solver, [], [], {})

    result = {}
    plugin.on_solver_finish(result)

    out_path = tmp_path / "demo.sequence_graph.json"
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload.get("schema_name") == "sequence_graph"
    assert int(payload.get("sequence_records", [])[0].get("count", 0)) >= 1


def test_sequence_graph_plugin_trace_fields(tmp_path: Path):
    solver = _Solver()
    plugin = SequenceGraphPlugin(
        config=SequenceGraphConfig(
            output_dir=str(tmp_path),
            run_id="trace_demo",
            overwrite=True,
            flush_every=0,
            capture_plugin_events=False,
            capture_adapter=True,
            capture_evaluate_population=True,
            trace_mode="full",
            trace_max_events=128,
        )
    )
    plugin.on_solver_init(solver)

    solver.evaluate_population([[0.0]])
    solver.adapter.propose(solver, {})
    solver.adapter.update(solver, [], [], {})

    result = {}
    plugin.on_solver_finish(result)

    out_path = tmp_path / "trace_demo.sequence_graph.json"
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload.get("schema_name") == "sequence_graph"
    assert int(payload.get("schema_version", 0)) >= 2
    assert payload.get("trace_mode") == "full"
    events = payload.get("trace_events", [])
    assert isinstance(events, list) and len(events) >= 1
    first = events[0]
    for key in (
        "start_ns",
        "end_ns",
        "thread_id",
        "task_id",
        "span_id",
        "parent_span_id",
    ):
        assert key in first
    assert int(payload.get("trace_event_count", 0)) == len(events)
