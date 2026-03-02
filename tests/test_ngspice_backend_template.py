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


def test_ngspice_backend_error_output_decode_fallback(monkeypatch):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.ngspice_backend import NgspiceBackend, NgspiceBackendConfig
    import nsgablack.plugins.solver_backends.ngspice_backend as ng_mod

    class _Proc:
        returncode = 1
        stdout = b""
        stderr = "中文错误".encode("gbk")

    monkeypatch.setattr(ng_mod.shutil, "which", lambda _cmd: "ngspice")
    monkeypatch.setattr(ng_mod.subprocess, "run", lambda *args, **kwargs: _Proc())

    backend = NgspiceBackend(
        config=NgspiceBackendConfig(
            command="ngspice",
            mock_when_unavailable=False,
        )
    )
    req = BackendSolveRequest(candidate=np.array([1.0], dtype=float), eval_context={})
    try:
        backend.solve(req)
    except RuntimeError as exc:
        text = str(exc)
        assert "returncode=1" in text
        assert "中文" in text
        return
    raise AssertionError("Expected RuntimeError from mocked ngspice failure")
