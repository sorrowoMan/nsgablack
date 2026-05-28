"""Multi-objective template (setObjectiveN)."""

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


def _quadratic_expr(cp: Any, vars_list: list[Any], Q: Any | None) -> Any:
    if Q is None:
        return 0.0
    q_arr = np.asarray(Q, dtype=float)
    if q_arr.ndim != 2 or q_arr.shape[0] != q_arr.shape[1]:
        raise ValueError("Q must be a square matrix")
    n = q_arr.shape[0]
    if n != len(vars_list):
        raise ValueError("Q dimension mismatch with variables")
    expr = 0.0
    for i in range(n):
        for j in range(n):
            coef = q_arr[i, j]
            if coef == 0.0:
                continue
            expr += float(coef) * vars_list[i] * vars_list[j]
    return expr


def solve_multiobj_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "multiobj_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("multiobj_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_multiobj_spec_builder", "copt_spec_builder"),
        inline_keys=("objectives", "vars", "lb", "ub", "vtype"),
    )

    env = cp.Envr()
    model = env.createModel(str(spec.get("name") or "nsgablack_copt_multiobj"))

    vars_list, name_map = build_variables(model, cp, spec)
    add_linear_constraints(model, cp, vars_list, spec)
    add_indicator_constraints(model, cp, vars_list, name_map, spec.get("indicator_constraints"))
    add_gen_constraints(model, cp, vars_list, name_map, spec.get("gen_constrs") or spec.get("gen_constraints"))

    objectives = spec.get("objectives") or []
    if not objectives:
        raise ValueError("multiobj template requires objectives list")

    for idx, entry in enumerate(objectives):
        data = dict(entry or {})
        c = data.get("c")
        Q = data.get("Q")
        weight = float(data.get("weight", 1.0))
        sense = str(data.get("sense", data.get("objective_sense", "min"))).lower()
        expr = 0.0
        if c is not None:
            c_arr = np.asarray(c, dtype=float).reshape(-1)
            if len(c_arr) != len(vars_list):
                raise ValueError("objective c length mismatch with variables")
            expr = expr + build_linear_expr(cp, vars_list, c_arr)
        if Q is not None:
            expr = expr + _quadratic_expr(cp, vars_list, Q)
        expr = float(weight) * expr
        copt_sense = cp.COPT.MINIMIZE if sense != "max" else cp.COPT.MAXIMIZE
        priority = data.get("priority")
        if priority is None:
            model.setObjectiveN(idx, expr, copt_sense)
        else:
            model.setObjectiveN(idx, expr, copt_sense, priority=int(priority))

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
            "copt.mode": "multiobj_spec",
            "copt.status_raw": None if status_raw is None else int(status_raw),
            "copt.nvars": int(len(vars_list)),
            "copt.objectives": int(len(objectives)),
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
