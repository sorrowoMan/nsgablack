from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import numpy as np

from .backend_contract import BackendSolveRequest
from .copt_templates import TemplateSolveFn, build_default_templates

try:
    import coptpy as _COPT_MODULE
except Exception:
    _COPT_MODULE = None


CoptSolveFn = Callable[[BackendSolveRequest, Any], Mapping[str, Any]]
LinearSpecBuilder = Callable[[BackendSolveRequest], Mapping[str, Any]]
QpSpecBuilder = Callable[[BackendSolveRequest], Mapping[str, Any]]


@dataclass
class CoptBackendConfig:
    mock_when_unavailable: bool = True
    mock_objective_scale: float = 1.0
    mock_violation: float = 0.0
    default_time_limit_sec: Optional[float] = None
    default_mip_gap: Optional[float] = None
    verbose: bool = False
    strict_template_selection: bool = True


class CoptBackend:
    """COPT backend implementing BackendSolver.solve(request).

    Supported paths (priority high -> low):
    1) custom solve fn: request.payload['copt_solve_fn'] or constructor `solve_fn`
    2) template solve: request.payload['copt_template'] + request.payload['copt_template_params']
    3) linear spec builder: request.payload['copt_linear_spec_builder'] or constructor `linear_spec_builder`
    4) fallback mock result when coptpy unavailable or no builder provided
    """

    def __init__(
        self,
        *,
        config: Optional[CoptBackendConfig] = None,
        solve_fn: Optional[CoptSolveFn] = None,
        linear_spec_builder: Optional[LinearSpecBuilder] = None,
        qp_spec_builder: Optional[QpSpecBuilder] = None,
        template_solvers: Optional[Mapping[str, TemplateSolveFn]] = None,
    ) -> None:
        self.cfg = config or CoptBackendConfig()
        self.solve_fn = solve_fn
        self.linear_spec_builder = linear_spec_builder
        self.qp_spec_builder = qp_spec_builder
        self.template_solvers: Dict[str, TemplateSolveFn] = dict(
            build_default_templates(
                solve_linear_spec=self._solve_linear_spec,
                default_linear_builder=self.linear_spec_builder,
                solve_qp_spec=self._solve_qp_spec,
                default_qp_builder=self.qp_spec_builder,
            )
        )
        if isinstance(template_solvers, Mapping):
            for key, fn in template_solvers.items():
                if callable(fn):
                    self.template_solvers[str(key).strip().lower()] = fn

    def _build_mock(self, request: BackendSolveRequest, status: str, reason: str) -> Dict[str, Any]:
        cand = np.asarray(request.candidate, dtype=float).reshape(-1)
        objective = float(np.sum(cand * cand) * float(self.cfg.mock_objective_scale))
        return {
            "status": status,
            "objective": objective,
            "violation": float(self.cfg.mock_violation),
            "metrics": {
                "copt.mode": "mock",
                "copt.reason": str(reason),
            },
        }

    @staticmethod
    def _resolve_callable(payload: Mapping[str, Any], key: str, fallback: Optional[Callable]) -> Optional[Callable]:
        candidate = payload.get(key)
        if callable(candidate):
            return candidate
        return fallback

    @staticmethod
    def _resolve_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = payload.get(key)
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise TypeError(f"payload['{key}'] must be a mapping")
        return value

    @staticmethod
    def _as_1d(value: Any, *, name: str, dtype=float) -> np.ndarray:
        arr = np.asarray(value, dtype=dtype).reshape(-1)
        if arr.size == 0:
            raise ValueError(f"linear spec '{name}' must be non-empty")
        return arr

    def _load_copt_module(self) -> Any:
        if _COPT_MODULE is not None:
            return _COPT_MODULE
        raise ImportError("coptpy not importable")

    @staticmethod
    def _set_parameter(model: Any, name: str, value: Any) -> None:
        if value is None:
            return
        setter = getattr(model, "setParam", None)
        if callable(setter):
            setter(str(name), value)

    @staticmethod
    def _resolve_template_name(payload: Mapping[str, Any]) -> Optional[str]:
        raw = payload.get("copt_template")
        if raw is None:
            return None
        name = str(raw).strip().lower()
        if not name:
            return None
        return name

    def _solve_linear_spec(self, request: BackendSolveRequest, cp: Any, builder: Callable) -> Mapping[str, Any]:
        spec = dict(builder(request) or {})
        c = self._as_1d(spec.get("c"), name="c", dtype=float)
        n = int(c.size)
        A = spec.get("A")
        rhs = spec.get("rhs")
        sense = spec.get("sense", "<=")
        lb = np.asarray(spec.get("lb", np.full((n,), -cp.COPT.INFINITY)), dtype=float).reshape(-1)
        ub = np.asarray(spec.get("ub", np.full((n,), cp.COPT.INFINITY)), dtype=float).reshape(-1)
        if lb.size != n or ub.size != n:
            raise ValueError("linear spec lb/ub size mismatch with c")

        objective_sense = str(spec.get("objective_sense", "min")).strip().lower()
        vtypes: Sequence[str] = list(spec.get("vtype", ["C"] * n))
        if len(vtypes) != n:
            raise ValueError("linear spec vtype length mismatch with c")

        env = cp.Envr()
        model = env.createModel("nsgablack_copt")
        self._set_parameter(model, "Logging", int(bool(self.cfg.verbose)))
        self._set_parameter(model, "TimeLimit", self.cfg.default_time_limit_sec)
        self._set_parameter(model, "RelGap", self.cfg.default_mip_gap)

        vars_ = []
        for i in range(n):
            vtype_i = str(vtypes[i]).upper()
            copt_vtype = cp.COPT.CONTINUOUS
            if vtype_i in {"B", "BIN", "BINARY"}:
                copt_vtype = cp.COPT.BINARY
            elif vtype_i in {"I", "INT", "INTEGER"}:
                copt_vtype = cp.COPT.INTEGER
            var = model.addVar(lb=float(lb[i]), ub=float(ub[i]), vtype=copt_vtype, name=f"x_{i}")
            vars_.append(var)

        obj_expr = cp.quicksum(float(c[i]) * vars_[i] for i in range(n))
        copt_sense = cp.COPT.MINIMIZE if objective_sense != "max" else cp.COPT.MAXIMIZE
        model.setObjective(obj_expr, copt_sense)

        if A is not None and rhs is not None:
            A_arr = np.asarray(A, dtype=float)
            rhs_arr = np.asarray(rhs, dtype=float).reshape(-1)
            if A_arr.ndim != 2:
                raise ValueError("linear spec A must be 2D")
            if A_arr.shape[1] != n:
                raise ValueError("linear spec A columns mismatch with c")
            if A_arr.shape[0] != rhs_arr.size:
                raise ValueError("linear spec A rows mismatch with rhs")

            if isinstance(sense, (list, tuple)):
                sense_list = [str(x).strip() for x in sense]
            else:
                sense_list = [str(sense).strip()] * int(A_arr.shape[0])
            if len(sense_list) != int(A_arr.shape[0]):
                raise ValueError("linear spec sense length mismatch with constraint rows")

            for r in range(int(A_arr.shape[0])):
                expr = cp.quicksum(float(A_arr[r, i]) * vars_[i] for i in range(n))
                rhs_r = float(rhs_arr[r])
                mark = sense_list[r]
                if mark == "<=":
                    model.addConstr(expr <= rhs_r)
                elif mark == ">=":
                    model.addConstr(expr >= rhs_r)
                elif mark in {"=", "=="}:
                    model.addConstr(expr == rhs_r)
                else:
                    raise ValueError(f"unsupported constraint sense: {mark}")

        model.solve()
        status_raw = getattr(model, "status", None)
        obj_val = getattr(model, "objval", None)
        try:
            x_val = np.asarray([float(getattr(v, "x", 0.0)) for v in vars_], dtype=float)
        except Exception:
            x_val = np.zeros((n,), dtype=float)

        status = "ok"
        if status_raw is not None and status_raw != getattr(cp.COPT, "OPTIMAL", status_raw):
            status = "non_optimal"

        if obj_val is None:
            obj_val = float(np.dot(c, x_val))

        return {
            "status": status,
            "objective": float(obj_val),
            "violation": float(spec.get("violation", 0.0)),
            "metrics": {
                "copt.mode": "linear_spec",
                "copt.status_raw": None if status_raw is None else int(status_raw),
                "copt.nvars": int(n),
            },
            "solution": x_val,
        }

    def _solve_qp_spec(self, request: BackendSolveRequest, cp: Any, builder: Callable) -> Mapping[str, Any]:
        spec = dict(builder(request) or {})
        c = self._as_1d(spec.get("c"), name="c", dtype=float)
        n = int(c.size)
        A = spec.get("A")
        rhs = spec.get("rhs")
        sense = spec.get("sense", "<=")
        Q = spec.get("Q")
        quadratic_scale = float(spec.get("quadratic_scale", 0.5))

        lb = np.asarray(spec.get("lb", np.full((n,), -cp.COPT.INFINITY)), dtype=float).reshape(-1)
        ub = np.asarray(spec.get("ub", np.full((n,), cp.COPT.INFINITY)), dtype=float).reshape(-1)
        if lb.size != n or ub.size != n:
            raise ValueError("qp spec lb/ub size mismatch with c")

        objective_sense = str(spec.get("objective_sense", "min")).strip().lower()
        vtypes: Sequence[str] = list(spec.get("vtype", ["C"] * n))
        if len(vtypes) != n:
            raise ValueError("qp spec vtype length mismatch with c")

        env = cp.Envr()
        model = env.createModel("nsgablack_copt_qp")
        self._set_parameter(model, "Logging", int(bool(self.cfg.verbose)))
        self._set_parameter(model, "TimeLimit", self.cfg.default_time_limit_sec)
        self._set_parameter(model, "RelGap", self.cfg.default_mip_gap)

        vars_ = []
        for i in range(n):
            vtype_i = str(vtypes[i]).upper()
            copt_vtype = cp.COPT.CONTINUOUS
            if vtype_i in {"B", "BIN", "BINARY"}:
                copt_vtype = cp.COPT.BINARY
            elif vtype_i in {"I", "INT", "INTEGER"}:
                copt_vtype = cp.COPT.INTEGER
            var = model.addVar(lb=float(lb[i]), ub=float(ub[i]), vtype=copt_vtype, name=f"x_{i}")
            vars_.append(var)

        obj_expr = cp.quicksum(float(c[i]) * vars_[i] for i in range(n))
        has_quadratic = Q is not None
        if has_quadratic:
            q_arr = np.asarray(Q, dtype=float)
            if q_arr.ndim != 2 or q_arr.shape[0] != n or q_arr.shape[1] != n:
                raise ValueError("qp spec Q must be 2D with shape (n, n)")
            q_expr = 0.0
            for i in range(n):
                for j in range(n):
                    coeff = float(q_arr[i, j])
                    if coeff == 0.0:
                        continue
                    q_expr = q_expr + coeff * vars_[i] * vars_[j]
            obj_expr = obj_expr + quadratic_scale * q_expr

        copt_sense = cp.COPT.MINIMIZE if objective_sense != "max" else cp.COPT.MAXIMIZE
        model.setObjective(obj_expr, copt_sense)

        if A is not None and rhs is not None:
            A_arr = np.asarray(A, dtype=float)
            rhs_arr = np.asarray(rhs, dtype=float).reshape(-1)
            if A_arr.ndim != 2:
                raise ValueError("qp spec A must be 2D")
            if A_arr.shape[1] != n:
                raise ValueError("qp spec A columns mismatch with c")
            if A_arr.shape[0] != rhs_arr.size:
                raise ValueError("qp spec A rows mismatch with rhs")

            if isinstance(sense, (list, tuple)):
                sense_list = [str(x).strip() for x in sense]
            else:
                sense_list = [str(sense).strip()] * int(A_arr.shape[0])
            if len(sense_list) != int(A_arr.shape[0]):
                raise ValueError("qp spec sense length mismatch with constraint rows")

            for r in range(int(A_arr.shape[0])):
                expr = cp.quicksum(float(A_arr[r, i]) * vars_[i] for i in range(n))
                rhs_r = float(rhs_arr[r])
                mark = sense_list[r]
                if mark == "<=":
                    model.addConstr(expr <= rhs_r)
                elif mark == ">=":
                    model.addConstr(expr >= rhs_r)
                elif mark in {"=", "=="}:
                    model.addConstr(expr == rhs_r)
                else:
                    raise ValueError(f"unsupported constraint sense: {mark}")

        model.solve()
        status_raw = getattr(model, "status", None)
        obj_val = getattr(model, "objval", None)
        try:
            x_val = np.asarray([float(getattr(v, "x", 0.0)) for v in vars_], dtype=float)
        except Exception:
            x_val = np.zeros((n,), dtype=float)

        status = "ok"
        if status_raw is not None and status_raw != getattr(cp.COPT, "OPTIMAL", status_raw):
            status = "non_optimal"

        if obj_val is None:
            quad_term = 0.0
            if has_quadratic:
                q_arr = np.asarray(Q, dtype=float)
                quad_term = quadratic_scale * float(x_val.T @ q_arr @ x_val)
            obj_val = float(np.dot(c, x_val) + quad_term)

        return {
            "status": status,
            "objective": float(obj_val),
            "violation": float(spec.get("violation", 0.0)),
            "metrics": {
                "copt.mode": "qp_spec",
                "copt.status_raw": None if status_raw is None else int(status_raw),
                "copt.nvars": int(n),
                "copt.has_quadratic": bool(has_quadratic),
            },
            "solution": x_val,
        }

    def _solve_by_template(self, request: BackendSolveRequest, cp: Any, payload: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        template_name = self._resolve_template_name(payload)
        if template_name is None:
            return None

        template_solver = self.template_solvers.get(template_name)
        if not callable(template_solver):
            if bool(self.cfg.strict_template_selection):
                raise ValueError(f"unsupported copt template: {template_name}")
            return self._build_mock(request, status="mock_unknown_template", reason=f"template={template_name}")

        template_params = self._resolve_mapping(payload, "copt_template_params")
        out = dict(template_solver(request, cp, template_params))
        metrics = out.get("metrics")
        out["metrics"] = dict(metrics) if isinstance(metrics, Mapping) else {}
        existing_mode = out["metrics"].get("copt.mode")
        if existing_mode is not None:
            out["metrics"].setdefault("copt.template_mode", existing_mode)
        out["metrics"]["copt.mode"] = "template"
        out["metrics"].setdefault("copt.template", template_name)
        return out

    def solve(self, request: BackendSolveRequest) -> Mapping[str, Any]:
        payload = dict(request.payload or {})
        custom_solve = self._resolve_callable(payload, "copt_solve_fn", self.solve_fn)
        linear_builder = self._resolve_callable(payload, "copt_linear_spec_builder", self.linear_spec_builder)

        try:
            cp = self._load_copt_module()
        except Exception as exc:
            if self.cfg.mock_when_unavailable:
                return self._build_mock(request, status="mock_unavailable", reason=str(exc))
            raise RuntimeError(f"coptpy unavailable: {exc}") from exc

        if callable(custom_solve):
            out = dict(custom_solve(request, cp))
            metrics = out.get("metrics")
            out["metrics"] = dict(metrics) if isinstance(metrics, Mapping) else {}
            out["metrics"].setdefault("copt.mode", "custom")
            return out

        template_out = self._solve_by_template(request, cp, payload)
        if isinstance(template_out, Mapping):
            return dict(template_out)

        if callable(linear_builder):
            return self._solve_linear_spec(request, cp, linear_builder)

        if self.cfg.mock_when_unavailable:
            return self._build_mock(request, status="mock_no_builder", reason="no copt solver callback configured")
        raise RuntimeError("CoptBackend requires copt_solve_fn or copt_linear_spec_builder")
