"""Quadratically constrained quadratic programming (QCP/MIQCP) template.

Spec fields (template_params['spec']):
- vars: list of variable specs {lb, ub, vtype, name}
- n/lb/ub/vtype: vector-style variable definition (fallback)
- c: linear objective coefficients
- Q: quadratic objective matrix (n x n)
- quadratic_scale: scale for quadratic term (default 0.5)
- objective_sense: "min" or "max"
- A/rhs/sense or linear_constraints: linear constraints
- qconstrs: list of quadratic constraint specs
    each with Q/terms, a/coeffs, rhs, sense
- params: model parameters passed to setParam
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from ..backend_contract import BackendSolveRequest
from ..backend_utils import (
    apply_solution_pool_params,
    apply_warm_start,
    extract_solution_pool,
    register_callback,
    run_diagnostics,
)
from .utils import (
    add_linear_constraints,
    add_gen_constraints,
    add_indicator_constraints,
    apply_feas_relaxation,
    apply_model_params,
    build_linear_expr,
    build_variables,
    resolve_template_spec,
)


def _quadratic_expr(cp: Any, vars_list: list[Any], *, Q=None, terms=None) -> Any:
    expr = 0.0
    if terms is not None:
        for term in terms:
            if isinstance(term, (list, tuple)) and len(term) >= 3:
                i, j, coef = term[0], term[1], term[2]
            elif isinstance(term, Mapping):
                i = term.get("i")
                j = term.get("j")
                coef = term.get("coef", term.get("value", 0.0))
            else:
                raise ValueError("quadratic term must be tuple(i, j, coef) or mapping")
            expr += float(coef) * vars_list[int(i)] * vars_list[int(j)]
        return expr
    if Q is None:
        return expr
    q_arr = np.asarray(Q, dtype=float)
    if q_arr.ndim != 2 or q_arr.shape[0] != q_arr.shape[1]:
        raise ValueError("Q must be a square matrix")
    n = q_arr.shape[0]
    if n != len(vars_list):
        raise ValueError("Q dimension mismatch with variables")
    for i in range(n):
        for j in range(n):
            coef = q_arr[i, j]
            if coef == 0.0:
                continue
            expr += float(coef) * vars_list[i] * vars_list[j]
    return expr


def _add_constraint(model: Any, expr: Any, sense: str, rhs: Any) -> None:
    if isinstance(rhs, (list, tuple)) and len(rhs) == 2:
        model.addConstr(expr == [float(rhs[0]), float(rhs[1])])
        return
    if sense == "<=":
        model.addConstr(expr <= float(rhs))
    elif sense == ">=":
        model.addConstr(expr >= float(rhs))
    elif sense in {"=", "=="}:
        model.addConstr(expr == float(rhs))
    else:
        raise ValueError(f"unsupported constraint sense: {sense}")


def solve_qcp_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "qcp_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("qcp_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_qcp_spec_builder", "copt_spec_builder"),
        inline_keys=(
            "c",
            "Q",
            "A",
            "rhs",
            "sense",
            "lb",
            "ub",
            "vtype",
            "qconstrs",
            "quadratic_constraints",
            "objective_sense",
            "quadratic_scale",
        ),
    )

    env = cp.Envr()
    model = env.createModel(str(spec.get("name") or "nsgablack_copt_qcp"))

    vars_list, name_map = build_variables(model, cp, spec)
    add_linear_constraints(model, cp, vars_list, spec)
    add_indicator_constraints(model, cp, vars_list, name_map, spec.get("indicator_constraints"))
    add_gen_constraints(model, cp, vars_list, name_map, spec.get("gen_constrs") or spec.get("gen_constraints"))

    obj_spec = dict(spec.get("objective") or {})
    c = obj_spec.get("c", spec.get("c"))
    Q = obj_spec.get("Q", spec.get("Q"))
    quadratic_scale = float(obj_spec.get("quadratic_scale", spec.get("quadratic_scale", 0.5)))
    sense = str(obj_spec.get("sense", obj_spec.get("objective_sense", spec.get("objective_sense", "min")))).lower()

    obj_expr = 0.0
    if c is not None:
        c_arr = np.asarray(c, dtype=float).reshape(-1)
        if len(c_arr) != len(vars_list):
            raise ValueError("objective c length mismatch with variables")
        obj_expr = obj_expr + build_linear_expr(cp, vars_list, c_arr)
    if Q is not None or obj_spec.get("terms") is not None:
        quad_expr = _quadratic_expr(cp, vars_list, Q=Q, terms=obj_spec.get("terms"))
        obj_expr = obj_expr + float(quadratic_scale) * quad_expr

    copt_sense = cp.COPT.MINIMIZE if sense != "max" else cp.COPT.MAXIMIZE
    model.setObjective(obj_expr, copt_sense)

    qconstrs = spec.get("qconstrs") or spec.get("quadratic_constraints") or []
    for entry in qconstrs:
        data = dict(entry or {})
        expr_builder = data.get("expr") or data.get("builder")
        if callable(expr_builder):
            expr = expr_builder(vars_list, cp, model)  # type: ignore[misc]
        else:
            q_terms = data.get("terms")
            q_Q = data.get("Q")
            q_scale = float(data.get("quadratic_scale", 1.0))
            expr = q_scale * _quadratic_expr(cp, vars_list, Q=q_Q, terms=q_terms)
            a = data.get("a") or data.get("coeffs") or data.get("linear")
            if a is not None:
                a_arr = np.asarray(a, dtype=float).reshape(-1)
                if len(a_arr) != len(vars_list):
                    raise ValueError("quadratic constraint linear coeff length mismatch")
                expr = expr + build_linear_expr(cp, vars_list, a_arr)
        rhs = data.get("rhs", 0.0)
        sense = str(data.get("sense", "<=")).strip()
        add_q = getattr(model, "addQConstr", None)
        if callable(add_q):
            if isinstance(rhs, (list, tuple)) and len(rhs) == 2:
                add_q(expr == [float(rhs[0]), float(rhs[1])])
            elif sense == "<=":
                add_q(expr <= float(rhs))
            elif sense == ">=":
                add_q(expr >= float(rhs))
            elif sense in {"=", "=="}:
                add_q(expr == float(rhs))
            else:
                raise ValueError(f"unsupported constraint sense: {sense}")
        else:
            _add_constraint(model, expr, sense, rhs)

    apply_model_params(model, cp, spec.get("params") or spec.get("model_params"))
    warm_meta = apply_warm_start(model, cp, spec.get("warm_start"))
    cb_meta = register_callback(model, cp, spec.get("callback"))
    pool_meta = apply_solution_pool_params(model, cp, spec.get("solution_pool"))
    model.solve()
    apply_feas_relaxation(model, cp, spec.get("feas_relax"))
    diag_out = run_diagnostics(model, cp, spec.get("diagnostics"))
    pool_out = extract_solution_pool(model, cp, spec.get("solution_pool"))

    status_raw = getattr(model, "status", None)
    obj_val = getattr(model, "objval", None)
    try:
        x_val = np.asarray([float(getattr(v, "x", 0.0)) for v in vars_list], dtype=float)
    except Exception:
        x_val = np.zeros((len(vars_list),), dtype=float)

    status = "ok"
    if status_raw is not None and status_raw != getattr(cp.COPT, "OPTIMAL", status_raw):
        status = "non_optimal"
    if obj_val is None:
        obj_val = float(np.sum(x_val))

    out = {
        "status": status,
        "objective": float(obj_val),
        "violation": float(spec.get("violation", 0.0)),
        "metrics": {
            "copt.mode": "qcp_spec",
            "copt.status_raw": None if status_raw is None else int(status_raw),
            "copt.nvars": int(len(vars_list)),
            "copt.qconstrs": int(len(qconstrs)),
            "copt.warm_start": warm_meta,
            "copt.callback": cb_meta,
            "copt.solution_pool": pool_meta,
        },
        "solution": x_val,
    }
    if diag_out is not None:
        out["diagnostics"] = diag_out
    if pool_out is not None:
        out["solution_pool"] = dict(pool_out)
    return out
