"""Semidefinite programming (SDP) template."""

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


def _build_psd_matrix(model: Any, spec: Mapping[str, Any]) -> Any:
    kind = str(spec.get("kind", spec.get("type", "sparse"))).strip().lower()
    dim = int(spec.get("dim") or spec.get("n") or 0)
    if dim <= 0:
        raise ValueError("psd matrix requires dim")
    if kind == "eye":
        return model.addEyeMat(dim)
    if kind == "ones":
        return model.addOnesMat(dim)
    if kind == "dense":
        values = np.asarray(spec.get("values"), dtype=float)
        if values.ndim != 2 or values.shape[0] != values.shape[1]:
            raise ValueError("dense psd matrix must be square")
        rows, cols = np.nonzero(values)
        vals = values[rows, cols]
        return model.addSparseMat(dim, rows.tolist(), cols.tolist(), vals.tolist())
    if kind != "sparse":
        raise ValueError(f"unsupported psd matrix kind: {kind}")
    rows = spec.get("rows") or []
    cols = spec.get("cols") or []
    vals = spec.get("vals") or spec.get("values") or []
    return model.addSparseMat(dim, list(rows), list(cols), list(vals))


def _resolve_psd_mat(psd_mats: list[Any], entry: Any, model: Any) -> Any:
    if isinstance(entry, (int, np.integer)):
        return psd_mats[int(entry)]
    if isinstance(entry, Mapping):
        return _build_psd_matrix(model, entry)
    raise ValueError("psd constraint mat must be index or matrix spec")


def _linear_terms_expr(cp: Any, vars_list: list[Any], name_map: Mapping[str, Any], data: Any) -> Any:
    if data is None:
        return 0.0
    if isinstance(data, Mapping):
        terms = []
        for key, coef in data.items():
            terms.append({"name": key, "coef": coef})
    else:
        terms = list(data)
    expr = 0.0
    for term in terms:
        if isinstance(term, Mapping):
            coef = term.get("coef", term.get("value", 0.0))
            if "index" in term:
                var = vars_list[int(term["index"])]
            else:
                name = str(term.get("name"))
                var = name_map[name]
        else:
            if len(term) < 2:
                raise ValueError("linear term must be (index/name, coef)")
            ref, coef = term[0], term[1]
            if isinstance(ref, (int, np.integer)):
                var = vars_list[int(ref)]
            else:
                var = name_map[str(ref)]
        expr += float(coef) * var
    return expr


def solve_sdp_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "sdp_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("sdp_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_sdp_spec_builder", "copt_spec_builder"),
        inline_keys=("psd_vars", "psd_mats", "psd_constrs", "c", "A", "rhs", "sense"),
    )

    env = cp.Envr()
    model = env.createModel(str(spec.get("name") or "nsgablack_copt_sdp"))

    has_linear_vars = any(key in spec for key in ("vars", "lb", "ub", "vtype", "c", "A", "rhs", "sense"))
    if has_linear_vars:
        vars_list, name_map = build_variables(model, cp, spec)
        add_linear_constraints(model, cp, vars_list, spec)
        add_indicator_constraints(model, cp, vars_list, name_map, spec.get("indicator_constraints"))
        add_gen_constraints(model, cp, vars_list, name_map, spec.get("gen_constrs") or spec.get("gen_constraints"))
    else:
        vars_list = []
        name_map = {}

    psd_vars_spec = spec.get("psd_vars") or []
    psd_vars: list[Any] = []
    for idx, entry in enumerate(psd_vars_spec):
        data = dict(entry or {})
        dim = int(data.get("dim") or data.get("n") or 0)
        if dim <= 0:
            raise ValueError("psd_vars entry requires dim")
        name = str(data.get("name") or f"PSD_{idx}")
        psd_var = model.addPsdVars(dim, name)
        psd_vars.append(psd_var)

    psd_mats_spec = spec.get("psd_mats") or []
    psd_mats = []
    for entry in psd_mats_spec:
        psd_mats.append(_build_psd_matrix(model, dict(entry or {})))

    psd_constrs = spec.get("psd_constrs") or spec.get("psd_constraints") or []
    for entry in psd_constrs:
        data = dict(entry or {})
        mat = _resolve_psd_mat(psd_mats, data.get("mat"), model)
        var_idx = data.get("var", data.get("psd_var", 0))
        psd_var = psd_vars[int(var_idx)]
        expr = mat * psd_var
        expr = expr + _linear_terms_expr(cp, vars_list, name_map, data.get("linear_terms") or data.get("linear"))
        rhs = data.get("rhs", 0.0)
        sense = str(data.get("sense", "<=")).strip()
        if isinstance(rhs, (list, tuple)) and len(rhs) == 2:
            model.addConstr(expr == [float(rhs[0]), float(rhs[1])])
        elif sense == "<=":
            model.addConstr(expr <= float(rhs))
        elif sense == ">=":
            model.addConstr(expr >= float(rhs))
        elif sense in {"=", "=="}:
            model.addConstr(expr == float(rhs))
        else:
            raise ValueError(f"unsupported PSD constraint sense: {sense}")

    obj_expr = 0.0
    c = spec.get("c")
    if c is not None:
        c_arr = np.asarray(c, dtype=float).reshape(-1)
        if len(c_arr) != len(vars_list):
            raise ValueError("objective c length mismatch with variables")
        obj_expr = obj_expr + build_linear_expr(cp, vars_list, c_arr)

    psd_obj = spec.get("psd_objective") or spec.get("psd_objectives")
    if psd_obj:
        if isinstance(psd_obj, Mapping):
            psd_items = [psd_obj]
        else:
            psd_items = list(psd_obj)
        for entry in psd_items:
            data = dict(entry or {})
            mat = _resolve_psd_mat(psd_mats, data.get("mat"), model)
            var_idx = data.get("var", data.get("psd_var", 0))
            psd_var = psd_vars[int(var_idx)]
            coef = float(data.get("coef", 1.0))
            obj_expr = obj_expr + coef * (mat * psd_var)

    sense = str(spec.get("objective_sense", spec.get("sense", "min"))).lower()
    copt_sense = cp.COPT.MINIMIZE if sense != "max" else cp.COPT.MAXIMIZE
    model.setObjective(obj_expr, copt_sense)

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
            "copt.mode": "sdp_spec",
            "copt.status_raw": None if status_raw is None else int(status_raw),
            "copt.nvars": int(len(vars_list)),
            "copt.psd_vars": int(len(psd_vars)),
            "copt.psd_constrs": int(len(psd_constrs)),
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
