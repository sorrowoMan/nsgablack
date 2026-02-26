from __future__ import annotations

from types import SimpleNamespace

from nsgablack.plugins.ops.otel_tracing import OpenTelemetryTracingConfig, OpenTelemetryTracingPlugin


def test_otel_tracing_plugin_wraps_and_restores_methods():
    calls = {"eval_i": 0, "eval_p": 0, "propose": 0, "update": 0, "trigger": 0}

    class _Adapter:
        def propose(self, solver):
            calls["propose"] += 1
            return [1.0]

        def update(self, solver, new_population, new_objectives):
            calls["update"] += 1
            return True

    class _PM:
        def trigger(self, event_name, *args, **kwargs):
            calls["trigger"] += 1
            return None

    class _Solver:
        def __init__(self):
            self.adapter = _Adapter()
            self.plugin_manager = _PM()

        def evaluate_individual(self, x, individual_id=None):
            calls["eval_i"] += 1
            return 1.23, 0.0

        def evaluate_population(self, population):
            calls["eval_p"] += 1
            return [1.0], [0.0]

    solver = _Solver()
    plugin = OpenTelemetryTracingPlugin(config=OpenTelemetryTracingConfig(configure_provider=False, console_export=False))

    # Force-enable tracing path without depending on installed otel packages.
    def _fake_setup():
        plugin._tracer = SimpleNamespace(start_as_current_span=lambda _name: __import__("contextlib").nullcontext())

    plugin._setup_tracer = _fake_setup  # type: ignore[method-assign]
    plugin.on_solver_init(solver)

    solver.evaluate_individual([0.0], individual_id=1)
    solver.evaluate_population([[0.0]])
    solver.adapter.propose(solver)
    solver.adapter.update(solver, [[0.0]], [[1.0]])
    solver.plugin_manager.trigger("on_generation_end", 0)

    assert calls == {"eval_i": 1, "eval_p": 1, "propose": 1, "update": 1, "trigger": 1}

    result = {}
    plugin.on_solver_finish(result)
    artifacts = result.get("artifacts", {})
    assert "otel_tracing" in artifacts
