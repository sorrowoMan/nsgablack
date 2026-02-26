from __future__ import annotations

import numpy as np


def test_ngspice_backend_mock_mode_runs_without_binary():
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.ngspice_backend import NgspiceBackend, NgspiceBackendConfig

    backend = NgspiceBackend(
        config=NgspiceBackendConfig(
            command="__definitely_missing_ngspice__",
            mock_when_unavailable=True,
            mock_objective_scale=2.0,
        )
    )
    req = BackendSolveRequest(candidate=np.array([3.0], dtype=float), eval_context={})
    out = dict(backend.solve(req))
    assert out["status"] == "mock_unavailable"
    assert abs(float(out["objective"]) - 18.0) < 1e-12
    assert float(out["violation"]) == 0.0

