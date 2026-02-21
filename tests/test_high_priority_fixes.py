from __future__ import annotations

import numpy as np

from nsgablack.core.adapters.differential_evolution import DEConfig, DifferentialEvolutionAdapter
from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationConfig,
    MonteCarloEvaluationPlugin,
)
from nsgablack.plugins.storage.mysql_run_logger import MySQLRunLoggerPlugin
from nsgablack.utils.context.context_keys import KEY_ADAPTER_BEST_SCORE, KEY_GENERATION


class _DummyMCProblem:
    def __init__(self, dim: int) -> None:
        self.dimension = int(dim)

    def evaluate(self, x):
        _ = x
        # Deliberately consumes global numpy RNG.
        return np.array([float(np.random.random())], dtype=float)

    def evaluate_constraints(self, x):
        _ = x
        return np.zeros((0,), dtype=float)


class _DummyMCSolver:
    def __init__(self, dim: int = 4) -> None:
        self.dimension = int(dim)
        self.num_objectives = 1
        self.problem = _DummyMCProblem(dim)
        self.enable_bias = False
        self.bias_module = None

    def build_context(self, individual_id=None, constraints=None, violation=None):
        _ = individual_id, constraints, violation
        return {}

    def _apply_bias(self, reduced, x, i, ctx):  # pragma: no cover - not used in this test
        _ = x, i, ctx
        return reduced


def _rng_states_equal(a, b) -> bool:
    if a[0] != b[0]:
        return False
    if not np.array_equal(a[1], b[1]):
        return False
    if a[2:] != b[2:]:
        return False
    return True


def test_monte_carlo_plugin_does_not_pollute_global_numpy_rng():
    np.random.seed(12345)
    before = np.random.get_state()

    solver = _DummyMCSolver(dim=4)
    plugin = MonteCarloEvaluationPlugin(
        config=MonteCarloEvaluationConfig(mc_samples=8, random_seed=42)
    )
    population = np.zeros((3, solver.dimension), dtype=float)
    objectives, violations = plugin.evaluate_population(solver, population)

    after = np.random.get_state()
    assert objectives.shape == (3, 1)
    assert violations.shape == (3,)
    assert _rng_states_equal(before, after)


def test_differential_evolution_adapter_tracks_best_score_in_projection():
    class _Solver:
        def repair_candidate(self, x, context):
            _ = context
            return np.asarray(x, dtype=float)

    adapter = DifferentialEvolutionAdapter(DEConfig(population_size=4, batch_size=2))
    adapter.setup(_Solver())
    pop = np.array(
        [
            [0.2, 0.3, 0.4],
            [0.3, 0.4, 0.5],
            [0.4, 0.5, 0.6],
            [0.5, 0.6, 0.7],
        ],
        dtype=float,
    )
    obj = np.array([[4.0], [3.0], [2.0], [1.0]], dtype=float)
    vio = np.zeros(4, dtype=float)
    assert adapter.set_population(pop, obj, vio) is True

    projection = adapter.get_runtime_context_projection(_Solver())
    assert KEY_ADAPTER_BEST_SCORE in projection
    assert float(projection[KEY_ADAPTER_BEST_SCORE]) >= 0.0
    assert KEY_GENERATION not in projection


class _Cfg:
    def __init__(self, run_id):
        self.run_id = run_id


class _PluginWithRunId:
    def __init__(self, run_id):
        self.cfg = _Cfg(run_id)


class _PM:
    def __init__(self, plugins):
        self._plugins = list(plugins)

    def list_plugins(self, enabled_only=False):
        _ = enabled_only
        return list(self._plugins)


class _Solver:
    def __init__(self):
        self.plugin_manager = _PM([_PluginWithRunId("bench_001")])


def test_mysql_run_logger_resolves_run_id_from_plugin_configs():
    plugin = MySQLRunLoggerPlugin()
    solver = _Solver()
    rid = plugin._resolve_run_id(solver=solver, result={}, artifacts={})
    assert rid == "bench_001"
