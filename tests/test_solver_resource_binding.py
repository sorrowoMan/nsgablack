from __future__ import annotations

import numpy as np
import pytest

from nsgablack.core.acceleration import ThreadPoolBackend
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(name="resource-binding", dimension=1, objectives=["f"])

    def evaluate(self, candidate):
        return np.asarray([float(np.asarray(candidate)[0])])


def test_acceleration_factory_is_capped_by_effective_resource_context() -> None:
    solver = SolverBase(_Problem(), resource_context={"threads": 2, "namespace": "p.c"})
    solver.register_acceleration_backend(
        scope="evaluation",
        backend="thread",
        factory=lambda: ThreadPoolBackend(max_workers=None),
    )

    backend = solver.get_acceleration_backend(scope="evaluation", backend="thread")

    assert backend.max_workers == 2


def test_solver_acceleration_registries_are_case_local() -> None:
    first = SolverBase(_Problem())
    second = SolverBase(_Problem())
    first.register_acceleration_backend(
        scope="evaluation",
        backend="thread",
        factory=lambda: ThreadPoolBackend(max_workers=1),
    )
    second.register_acceleration_backend(
        scope="evaluation",
        backend="thread",
        factory=lambda: ThreadPoolBackend(max_workers=4),
    )

    assert first.get_acceleration_backend(scope="evaluation", backend="thread").max_workers == 1
    assert second.get_acceleration_backend(scope="evaluation", backend="thread").max_workers == 4


def test_late_cpu_grant_rejects_preconfigured_gpu_default() -> None:
    solver = SolverBase(_Problem())
    solver.set_acceleration_default_backend(scope="evaluation", backend="gpu")

    with pytest.raises(RuntimeError, match="requires a GPU grant"):
        solver.set_resource_context(
            {
                "threads": 1,
                "device": "cpu",
                "compute_backend": "auto",
                "grant": {"threads": 1, "gpus": 0, "device_tokens": []},
            }
        )
