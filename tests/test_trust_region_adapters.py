from __future__ import annotations

import numpy as np

from nsgablack.adapters.trust_region_dfo import TrustRegionDFOAdapter, TrustRegionDFOConfig
from nsgablack.adapters.trust_region_mo_dfo import TrustRegionMODFOAdapter, TrustRegionMODFOConfig
from nsgablack.adapters.trust_region_nonsmooth import (
    TrustRegionNonSmoothAdapter,
    TrustRegionNonSmoothConfig,
)
from nsgablack.adapters.trust_region_subspace import (
    TrustRegionSubspaceAdapter,
    TrustRegionSubspaceConfig,
)
from nsgablack.core.state.context_keys import KEY_MO_WEIGHTS
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline


class _Problem(BlackBoxProblem):
    def __init__(self, dim=4, n_obj=2):
        super().__init__(dimension=dim, objectives=["min"] * n_obj, bounds=[(-2., 2.)] * dim)
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        return [float(np.sum(np.asarray(candidate)**2))] * self.get_num_objectives()


def _solver(adapter, dim=4, n_obj=2):
    class Initializer:
        def initialize(self, problem, context):
            return np.ones(dim)
    solver = ComposableSolver(_Problem(dim, n_obj), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Initializer()))
    solver.setup()
    return solver


def test_trust_region_dfo_basic_cycle() -> None:
    adapter = TrustRegionDFOAdapter(
        TrustRegionDFOConfig(batch_size=4, include_center=True, initial_radius=0.5, random_seed=0)
    )
    solver = _solver(adapter, dim=5)
    assert solver.step().committed
    assert solver.problem.calls == 1 and adapter._radius == .5
    assert solver.step().committed
    assert solver.problem.calls == 5
    state = adapter.get_state()
    assert state["center"] is not None
    assert float(state["radius"]) != 0.5


def test_trust_region_nonsmooth_scores_linf() -> None:
    adapter = TrustRegionNonSmoothAdapter(
        TrustRegionNonSmoothConfig(batch_size=3, score_mode="linf", random_seed=1)
    )
    solver = _solver(adapter, dim=3)
    objectives = np.array([[2.0, 1.0], [1.0, 3.0], [0.5, 0.5]], dtype=float)
    violations = np.zeros(3, dtype=float)
    np.testing.assert_array_equal(adapter._score(solver, objectives, violations, {}), [2., 3., .5])
    assert solver.step().committed and solver.step().committed
    state = adapter.get_state()
    assert state["best_score"] is not None


def test_trust_region_subspace_state_roundtrip_keeps_basis_and_steps() -> None:
    adapter = TrustRegionSubspaceAdapter(
        TrustRegionSubspaceConfig(batch_size=4, subspace_dim=3, resample_every=1, random_seed=2)
    )
    solver = _solver(adapter, dim=6)
    assert solver.step().committed and solver.step().committed
    state = adapter.get_state()
    assert state.get("basis") is not None
    assert int(state.get("steps", 0)) >= 1

    clone = TrustRegionSubspaceAdapter(TrustRegionSubspaceConfig(random_seed=3))
    clone.set_state(state)
    clone_state = clone.get_state()
    assert clone_state.get("basis") is not None
    assert int(clone_state.get("steps", 0)) == int(state.get("steps", 0))


def test_trust_region_mo_dfo_uses_context_weights_and_persists_them(monkeypatch) -> None:
    adapter = TrustRegionMODFOAdapter(TrustRegionMODFOConfig(batch_size=4, weight_method="fixed", random_seed=4))
    solver = _solver(adapter, n_obj=3)
    context = {KEY_MO_WEIGHTS: np.array([0.6, 0.3, 0.1], dtype=float)}
    original = adapter.update
    monkeypatch.setattr(adapter, "update", lambda c, x, f, ctx: original(c, x, f, {**ctx, **context}))
    assert solver.step().committed and solver.step().committed
    state = adapter.get_state()
    weights = np.asarray(state.get("weights"), dtype=float)
    assert weights.shape == (3,)
    assert np.isclose(float(np.sum(weights)), 1.0)
