from __future__ import annotations

import numpy as np


def test_copt_backend_mock_when_module_unavailable(monkeypatch):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.copt_backend import CoptBackend, CoptBackendConfig

    backend = CoptBackend(config=CoptBackendConfig(mock_when_unavailable=True, mock_objective_scale=3.0))
    monkeypatch.setattr(backend, "_load_copt_module", lambda: (_ for _ in ()).throw(ImportError("no coptpy")))

    req = BackendSolveRequest(candidate=np.array([2.0], dtype=float), eval_context={})
    out = dict(backend.solve(req))
    assert out["status"] == "mock_unavailable"
    assert abs(float(out["objective"]) - 12.0) < 1e-12
    assert float(out["violation"]) == 0.0


def test_copt_backend_custom_solve_fn_path(monkeypatch):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.copt_backend import CoptBackend

    backend = CoptBackend()

    class _CP:
        pass

    monkeypatch.setattr(backend, "_load_copt_module", lambda: _CP())

    def _solve_fn(request, cp):
        _ = cp
        cand = np.asarray(request.candidate, dtype=float).reshape(-1)
        return {
            "status": "ok",
            "objective": float(np.sum(cand)),
            "violation": 0.0,
            "metrics": {"tag": "unit"},
        }

    req = BackendSolveRequest(
        candidate=np.array([1.0, 2.0, 3.0], dtype=float),
        eval_context={},
        payload={"copt_solve_fn": _solve_fn},
    )
    out = dict(backend.solve(req))
    assert out["status"] == "ok"
    assert abs(float(out["objective"]) - 6.0) < 1e-12
    assert out.get("metrics", {}).get("copt.mode") == "custom"


def test_copt_backend_template_linear_inline_spec(monkeypatch):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.copt_backend import CoptBackend

    class _FakeVar:
        def __init__(self):
            self.x = 0.0

        def __rmul__(self, other):
            return float(other) * float(self.x)

        def __mul__(self, other):
            return float(other) * float(self.x)

    class _FakeModel:
        def __init__(self):
            self.status = 1
            self.objval = 0.0

        def setParam(self, name, value):
            _ = name
            _ = value

        def addVar(self, lb, ub, vtype, name):
            _ = lb
            _ = ub
            _ = vtype
            _ = name
            return _FakeVar()

        def setObjective(self, expr, sense):
            _ = expr
            _ = sense

        def addConstr(self, expr):
            _ = expr

        def solve(self):
            return None

    class _FakeEnv:
        def createModel(self, name):
            _ = name
            return _FakeModel()

    class _FakeCOPT:
        INFINITY = 1e20
        CONTINUOUS = 0
        BINARY = 1
        INTEGER = 2
        MINIMIZE = 1
        MAXIMIZE = -1
        OPTIMAL = 1

    class _FakeCP:
        COPT = _FakeCOPT

        @staticmethod
        def Envr():
            return _FakeEnv()

        @staticmethod
        def quicksum(xs):
            return float(sum(xs))

    backend = CoptBackend()
    monkeypatch.setattr(backend, "_load_copt_module", lambda: _FakeCP())

    req = BackendSolveRequest(
        candidate=np.array([1.0, 2.0], dtype=float),
        eval_context={},
        payload={
            "copt_template": "linear",
            "copt_template_params": {
                "c": [1.0, 2.0],
                "lb": [0.0, 0.0],
                "ub": [1.0, 1.0],
            },
        },
    )

    out = dict(backend.solve(req))
    assert out["status"] == "ok"
    assert out.get("metrics", {}).get("copt.mode") == "template"
    assert out.get("metrics", {}).get("copt.template") == "linear"


def test_copt_backend_template_unknown_template_strict(monkeypatch):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.copt_backend import CoptBackend

    class _CP:
        pass

    backend = CoptBackend()
    monkeypatch.setattr(backend, "_load_copt_module", lambda: _CP())

    req = BackendSolveRequest(
        candidate=np.array([1.0], dtype=float),
        eval_context={},
        payload={"copt_template": "not_exists"},
    )

    try:
        backend.solve(req)
        assert False, "expect ValueError for unknown template in strict mode"
    except ValueError as exc:
        assert "unsupported copt template" in str(exc)


def test_copt_backend_template_qp_inline_spec(monkeypatch):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.copt_backend import CoptBackend

    class _FakeVar:
        def __init__(self):
            self.x = 0.0

        def __rmul__(self, other):
            return float(other) * float(self.x)

        def __mul__(self, other):
            return float(other) * float(self.x)

    class _FakeModel:
        def __init__(self):
            self.status = 1
            self.objval = 0.0

        def setParam(self, name, value):
            _ = name
            _ = value

        def addVar(self, lb, ub, vtype, name):
            _ = lb
            _ = ub
            _ = vtype
            _ = name
            return _FakeVar()

        def setObjective(self, expr, sense):
            _ = expr
            _ = sense

        def addConstr(self, expr):
            _ = expr

        def solve(self):
            return None

    class _FakeEnv:
        def createModel(self, name):
            _ = name
            return _FakeModel()

    class _FakeCOPT:
        INFINITY = 1e20
        CONTINUOUS = 0
        BINARY = 1
        INTEGER = 2
        MINIMIZE = 1
        MAXIMIZE = -1
        OPTIMAL = 1

    class _FakeCP:
        COPT = _FakeCOPT

        @staticmethod
        def Envr():
            return _FakeEnv()

        @staticmethod
        def quicksum(xs):
            return float(sum(xs))

    backend = CoptBackend()
    monkeypatch.setattr(backend, "_load_copt_module", lambda: _FakeCP())

    req = BackendSolveRequest(
        candidate=np.array([1.0, 2.0], dtype=float),
        eval_context={},
        payload={
            "copt_template": "qp",
            "copt_template_params": {
                "c": [1.0, 2.0],
                "lb": [0.0, 0.0],
                "ub": [1.0, 1.0],
            },
        },
    )

    out = dict(backend.solve(req))
    assert out["status"] == "ok"
    assert out.get("metrics", {}).get("copt.mode") == "template"
    assert out.get("metrics", {}).get("copt.template") == "qp"
    assert out.get("metrics", {}).get("copt.template_mode") == "qp_spec"
