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


class _Problem:
    def __init__(self, dim: int = 4) -> None:
        self.bounds = [(-2.0, 2.0) for _ in range(dim)]


class _Solver:
    def __init__(self, dim: int = 4, n_obj: int = 2) -> None:
        self.dimension = int(dim)
        self.num_objectives = int(n_obj)
        self.problem = _Problem(dim=dim)
        self.best_x = np.zeros((dim,), dtype=float)
        self.representation_pipeline = None


def test_trust_region_dfo_basic_cycle() -> None:
    solver = _Solver(dim=5, n_obj=2)
    adapter = TrustRegionDFOAdapter(
        TrustRegionDFOConfig(batch_size=4, include_center=True, initial_radius=0.5, random_seed=0)
    )
    adapter.setup(solver)
    cands = adapter.propose(solver, context={})
    assert len(cands) == 4
    objectives = np.array([[5.0, 5.0], [4.0, 4.0], [3.0, 3.0], [2.0, 2.0]], dtype=float)
    violations = np.zeros(4, dtype=float)
    adapter.update(solver, cands, objectives, violations, context={})
    state = adapter.get_state()
    assert state["center"] is not None
    assert float(state["radius"]) > 0.5


def test_trust_region_nonsmooth_scores_linf() -> None:
    solver = _Solver(dim=3, n_obj=2)
    adapter = TrustRegionNonSmoothAdapter(
        TrustRegionNonSmoothConfig(batch_size=3, score_mode="linf", random_seed=1)
    )
    adapter.setup(solver)
    cands = adapter.propose(solver, context={})
    objectives = np.array([[2.0, 1.0], [1.0, 3.0], [0.5, 0.5]], dtype=float)
    violations = np.zeros(3, dtype=float)
    adapter.update(solver, cands, objectives, violations, context={})
    state = adapter.get_state()
    assert state["best_score"] is not None


def test_trust_region_subspace_state_roundtrip_keeps_basis_and_steps() -> None:
    solver = _Solver(dim=6, n_obj=2)
    adapter = TrustRegionSubspaceAdapter(
        TrustRegionSubspaceConfig(batch_size=4, subspace_dim=3, resample_every=1, random_seed=2)
    )
    adapter.setup(solver)
    adapter.propose(solver, context={})
    state = adapter.get_state()
    assert state.get("basis") is not None
    assert int(state.get("steps", 0)) >= 1

    clone = TrustRegionSubspaceAdapter(TrustRegionSubspaceConfig(random_seed=3))
    clone.set_state(state)
    clone_state = clone.get_state()
    assert clone_state.get("basis") is not None
    assert int(clone_state.get("steps", 0)) == int(state.get("steps", 0))


def test_trust_region_mo_dfo_uses_context_weights_and_persists_them() -> None:
    solver = _Solver(dim=4, n_obj=3)
    adapter = TrustRegionMODFOAdapter(TrustRegionMODFOConfig(batch_size=4, weight_method="fixed", random_seed=4))
    adapter.setup(solver)
    cands = adapter.propose(solver, context={})
    objectives = np.array(
        [
            [3.0, 2.0, 1.0],
            [1.0, 2.0, 3.0],
            [2.0, 1.0, 3.0],
            [3.0, 1.0, 2.0],
        ],
        dtype=float,
    )
    violations = np.zeros(4, dtype=float)
    context = {KEY_MO_WEIGHTS: np.array([0.6, 0.3, 0.1], dtype=float)}
    adapter.update(solver, cands, objectives, violations, context=context)
    state = adapter.get_state()
    weights = np.asarray(state.get("weights"), dtype=float)
    assert weights.shape == (3,)
    assert np.isclose(float(np.sum(weights)), 1.0)
