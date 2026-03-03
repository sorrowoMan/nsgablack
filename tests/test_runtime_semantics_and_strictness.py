from __future__ import annotations

import numpy as np
import pytest


def test_composable_solver_always_triggers_on_step():
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import Plugin

    class _Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="p", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            arr = np.asarray(x, dtype=float).reshape(-1)
            return np.array([float(arr[0] ** 2)], dtype=float)

    class _Adapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="a")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.2], dtype=float)]

    class _StepCounter(Plugin):
        def __init__(self):
            super().__init__(name="step_counter")
            self.steps = 0

        def on_step(self, solver, generation):
            _ = (solver, generation)
            self.steps += 1
            return None

    solver = ComposableSolver(problem=_Problem(), adapter=_Adapter())
    solver.max_steps = 3
    solver.pop_size = 1
    counter = _StepCounter()
    solver.add_plugin(counter)
    solver.run()
    assert counter.steps == 3


def test_plugin_manager_strict_mode_fails_fast():
    from nsgablack.plugins.base import Plugin, PluginManager

    class _Boom(Plugin):
        def __init__(self):
            super().__init__(name="boom")

        def on_generation_start(self, generation):
            _ = generation
            raise RuntimeError("boom")

    mgr = PluginManager(strict=True)
    mgr.register(_Boom())
    with pytest.raises(RuntimeError):
        mgr.on_generation_start(0)


def test_parallel_repair_per_item_fallback_and_error_report():
    from nsgablack.representation.base import ParallelRepair

    class _Repair:
        def repair(self, x, context=None):
            _ = context
            arr = np.asarray(x, dtype=float).reshape(-1)
            if float(arr[0]) == 3.0:
                raise ValueError("bad candidate")
            return arr

    wrapper = ParallelRepair(_Repair(), backend="thread", max_workers=4, min_batch_size=1, strict=False)
    xs = [np.array([1.0]), np.array([3.0]), np.array([2.0])]
    with pytest.raises(ValueError):
        # serial fallback should still surface persistent failing item
        wrapper.repair_batch(xs)
    assert wrapper.last_batch_errors
    assert any(int(rec.get("index", -1)) == 1 for rec in wrapper.last_batch_errors)


def test_parallel_repair_reports_errors_to_context_metrics():
    from nsgablack.representation.base import ParallelRepair

    class _Repair:
        def repair(self, x, context=None):
            _ = context
            arr = np.asarray(x, dtype=float).reshape(-1)
            if float(arr[0]) == 2.0:
                raise ValueError("bad candidate")
            return arr

    wrapper = ParallelRepair(
        _Repair(),
        backend="thread",
        max_workers=2,
        min_batch_size=1,
        strict=False,
        report_errors_to_context=True,
    )
    ctxs = [{}, {}, {}]
    xs = [np.array([1.0]), np.array([2.0]), np.array([3.0])]
    with pytest.raises(ValueError):
        wrapper.repair_batch(xs, contexts=ctxs)
    metrics = ctxs[1].get("metrics", {})
    assert isinstance(metrics, dict)
    errs = metrics.get("parallel_repair_errors", [])
    assert isinstance(errs, list) and errs
