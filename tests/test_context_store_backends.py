from __future__ import annotations

import time

import numpy as np
import pytest

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.context.context_store import (
    InMemoryContextStore,
    create_context_store,
)


class _Sphere(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(name="sphere", dimension=2)

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr**2))


def test_inmemory_context_store_ttl_expires() -> None:
    store = InMemoryContextStore(default_ttl_seconds=0.05)
    store.set("a", 1)
    assert store.get("a") == 1
    time.sleep(0.08)
    assert store.get("a") is None


def test_blank_solver_context_store_roundtrip() -> None:
    solver = SolverBase(problem=_Sphere(), context_store_backend="memory")
    solver.context_store.set("project.signal", 123.0)
    ctx = solver.build_context()
    assert ctx["project.signal"] == 123.0
    assert "generation" in ctx


def test_create_context_store_rejects_unknown_backend() -> None:
    try:
        create_context_store(backend="unknown_backend")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_solver_runtime_uses_configured_context_store_backend_memory() -> None:
    solver = EvolutionSolver(_Sphere(), context_store_backend="memory")
    solver.runtime.context_store.set("k", "v")
    ctx = solver.get_context()
    assert solver.runtime.context_store.get("k") == "v"
    assert "generation" in ctx


@pytest.mark.slow
def test_redis_context_store_ttl_10s_smoke() -> None:
    redis = pytest.importorskip("redis")
    client = redis.Redis(host="127.0.0.1", port=6379, db=0)
    try:
        ok = bool(client.ping())
    except Exception:
        pytest.skip("redis server is not running on 127.0.0.1:6379")
    if not ok:
        pytest.skip("redis ping failed")

    store = create_context_store(
        backend="redis",
        redis_url="redis://127.0.0.1:6379/0",
        key_prefix="nsgablack:test_ttl10",
        ttl_seconds=10.0,
    )
    store.set("ttl_key", {"alive": True})
    assert store.get("ttl_key") == {"alive": True}
    time.sleep(11.0)
    assert store.get("ttl_key") is None
