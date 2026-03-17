from __future__ import annotations

import numpy as np

from nsgablack.plugins.evaluation.gpu_evaluation_template import GpuEvaluationTemplateProviderPlugin


class _DummyProblem:
    def evaluate_gpu_batch(self, population, *, backend, device="cuda:0"):
        _ = (backend, device)
        pop = np.asarray(population, dtype=float)
        return np.sum(pop * pop, axis=1, keepdims=True)


class _DummySolver:
    def __init__(self, problem):
        self.problem = problem
        self.num_objectives = 1
        self._ctx = {}

    def get_context(self):
        return dict(self._ctx)

    def set_context(self, ctx):
        self._ctx = dict(ctx)


def test_gpu_eval_template_returns_none_when_backend_unavailable(monkeypatch):
    plugin = GpuEvaluationTemplateProviderPlugin()
    solver = _DummySolver(problem=_DummyProblem())
    pop = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)

    monkeypatch.setattr(plugin, "_select_backend", lambda: None)
    out = plugin.evaluate_population_runtime(solver, pop)
    assert out is None


def test_gpu_eval_template_short_circuit_path(monkeypatch):
    plugin = GpuEvaluationTemplateProviderPlugin()
    solver = _DummySolver(problem=_DummyProblem())
    pop = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)

    monkeypatch.setattr(plugin, "_select_backend", lambda: "torch")
    out = plugin.evaluate_population_runtime(solver, pop)
    assert out is not None
    objectives, violations = out
    assert objectives.shape == (2, 1)
    assert violations.shape == (2,)
    assert np.allclose(objectives.ravel(), np.array([5.0, 25.0], dtype=float))
