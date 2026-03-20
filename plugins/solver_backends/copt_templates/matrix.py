"""Matrix-mode template for linear models (LP/MIP) using addMVar/addMConstr."""

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
    add_gen_constraints,
    add_indicator_constraints,
    apply_feas_relaxation,
    apply_model_params,
    resolve_template_spec,
)


def _resolve_matrix_mode(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return "experimental" if value else None
    return value


def _sense_to_char(sense: str) -> str:
    mark = str(sense).strip()
    if mark == "<=":
        return "L"
    if mark == ">=":
        return "G"
    if mark in {"=", "=="}:
        return "E"
    return str(mark)


def solve_matrix_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "matrix_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("matrix_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_matrix_spec_builder", "copt_spec_builder"),
        inline_keys=("A", "rhs", "sense", "shape", "vtype", "lb", "ub", "objective"),
    )

    env = cp.Envr()
    model = env.createModel(str(spec.get("name") or "nsgablack_copt_matrix"))
    matrix_mode = _resolve_matrix_mode(spec.get("matrix_mode") or spec.get("matrixmodelmode"))
    if matrix_mode:
        try:
            model.matrixmodelmode = matrix_mode
        except Exception:
            pass

    builder = spec.get("matrix_builder") or spec.get("builder")
    mvar = None
    if not callable(builder):
        shape = spec.get("shape") or spec.get("mvar_shape")
        if shape is None:
            raise ValueError("matrix template requires shape when no builder is supplied")
        vtype = spec.get("vtype", cp.COPT.CONTINUOUS)
        lb = spec.get("lb")
        ub = spec.get("ub")
        nameprefix = spec.get("nameprefix", "x")
        mvar = model.addMVar(shape=shape, vtype=vtype, lb=lb, ub=ub, nameprefix=nameprefix)

        A = spec.get("A")
        rhs = spec.get("rhs")
        sense = spec.get("sense", "<=")
        if A is not None and rhs is not None:
            A_arr = np.asarray(A, dtype=float)
            rhs_arr = np.asarray(rhs, dtype=float).reshape(-1)
            if A_arr.ndim != 2:
                raise ValueError("matrix template A must be 2D")
            if A_arr.shape[1] != int(np.prod(mvar.shape)):
                raise ValueError("matrix template A columns mismatch with variable count")
            if A_arr.shape[0] != rhs_arr.size:
                raise ValueError("matrix template A rows mismatch with rhs")
            sense_char = _sense_to_char(sense)
            add_mconstr = getattr(model, "addMConstr", None)
            if callable(add_mconstr):
                add_mconstr(A_arr, mvar.reshape(-1), sense_char, rhs_arr)
            else:
                model.addConstrs(A_arr @ mvar.reshape(-1) <= rhs_arr)

        obj = spec.get("objective") or {}
        if callable(obj.get("expr_builder")):
            obj_expr = obj["expr_builder"](mvar, cp, model)
        else:
            cost = obj.get("cost") or spec.get("c") or spec.get("cost")
            if cost is None:
                obj_expr = 0.0
            else:
                cost_arr = np.asarray(cost, dtype=float)
                if cost_arr.shape != tuple(mvar.shape):
                    cost_arr = cost_arr.reshape(mvar.shape)
                obj_expr = (cost_arr * mvar).sum()
        sense = str(obj.get("sense", obj.get("objective_sense", spec.get("objective_sense", "min")))).lower()
        copt_sense = cp.COPT.MINIMIZE if sense != "max" else cp.COPT.MAXIMIZE
        model.setObjective(obj_expr, copt_sense)
    else:
        builder(model, cp, spec)  # type: ignore[misc]

    vars_list = []
    name_map: dict[str, Any] = {}
    try:
        vars_list = list(model.getVars())
        for var in vars_list:
            try:
                name_map[str(var.name)] = var
            except Exception:
                continue
    except Exception:
        vars_list = []
        name_map = {}

    add_indicator_constraints(model, cp, vars_list, name_map, spec.get("indicator_constraints"))
    add_gen_constraints(model, cp, vars_list, name_map, spec.get("gen_constrs") or spec.get("gen_constraints"))
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
            "copt.mode": "matrix_spec",
            "copt.status_raw": None if status_raw is None else int(status_raw),
            "copt.nvars": int(len(vars_list)),
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
