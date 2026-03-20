"""Exponential cone programming template."""

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
    resolve_var_refs,
)


def _resolve_expcone_type(cp: Any, value: Any) -> Any:
    if value is None:
        return getattr(cp.COPT, "EXPCONE_PRIMAL", None)
    mark = str(value).strip().lower()
    if mark in {"primal", "p"}:
        return getattr(cp.COPT, "EXPCONE_PRIMAL", None)
    if mark in {"dual", "d"}:
        return getattr(cp.COPT, "EXPCONE_DUAL", None)
    return getattr(cp.COPT, "EXPCONE_PRIMAL", None)


def solve_expcone_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "expcone_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("expcone_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_expcone_spec_builder", "copt_spec_builder"),
        inline_keys=("c", "A", "rhs", "sense", "lb", "ub", "vtype", "exp_cones"),
    )

    env = cp.Envr()
    model = env.createModel(str(spec.get("name") or "nsgablack_copt_expcone"))

    vars_list, name_map = build_variables(model, cp, spec)
    add_linear_constraints(model, cp, vars_list, spec)
    add_indicator_constraints(model, cp, vars_list, name_map, spec.get("indicator_constraints"))
    add_gen_constraints(model, cp, vars_list, name_map, spec.get("gen_constrs") or spec.get("gen_constraints"))

    c = spec.get("c")
    if c is None:
        obj_expr = 0.0
    else:
        c_arr = np.asarray(c, dtype=float).reshape(-1)
        if len(c_arr) != len(vars_list):
            raise ValueError("objective c length mismatch with variables")
        obj_expr = build_linear_expr(cp, vars_list, c_arr)
    sense = str(spec.get("objective_sense", spec.get("sense", "min"))).lower()
    copt_sense = cp.COPT.MINIMIZE if sense != "max" else cp.COPT.MAXIMIZE
    model.setObjective(obj_expr, copt_sense)

    exp_cones = spec.get("exp_cones") or spec.get("expcone_cones") or []
    for cone in exp_cones:
        data = dict(cone or {})
        refs = data.get("vars") or data.get("indices") or data.get("var_refs")
        if refs is None:
            raise ValueError("exp cone entry requires 'vars' or 'indices'")
        vars_ref = resolve_var_refs(list(refs), vars_list, name_map)
        cone_type = _resolve_expcone_type(cp, data.get("type") or data.get("cone_type"))
        model.addExpCone(vars_ref, cone_type)

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
            "copt.mode": "expcone_spec",
            "copt.status_raw": None if status_raw is None else int(status_raw),
            "copt.nvars": int(len(vars_list)),
            "copt.expcones": int(len(exp_cones)),
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
