"""Nonlinear programming (NLP) template.

Notes:
- Nonlinear objective/constraints are supplied as callables in spec.
"""

from __future__ import annotations

import inspect
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
    build_variables,
    resolve_template_spec,
)


def _call_expr(fn: Any, vars_list: list[Any], cp: Any, model: Any) -> Any:
    if not callable(fn):
        raise TypeError("nonlinear expression must be callable")
    try:
        argc = len(inspect.signature(fn).parameters)
    except Exception:
        argc = 2
    if argc <= 2:
        return fn(vars_list, cp)
    return fn(vars_list, cp, model)


def solve_nlp_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "nlp_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("nlp_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_nlp_spec_builder", "copt_spec_builder"),
        inline_keys=("nl_objective", "nl_constrs", "vars", "lb", "ub", "vtype"),
    )

    env = cp.Envr()
    model = env.createModel(str(spec.get("name") or "nsgablack_copt_nlp"))

    vars_list, name_map = build_variables(model, cp, spec)
    add_linear_constraints(model, cp, vars_list, spec)
    add_indicator_constraints(model, cp, vars_list, name_map, spec.get("indicator_constraints"))
    add_gen_constraints(model, cp, vars_list, name_map, spec.get("gen_constrs") or spec.get("gen_constraints"))

    nl_constrs = spec.get("nl_constrs") or spec.get("nonlinear_constraints") or []
    for entry in nl_constrs:
        data = dict(entry or {})
        expr = _call_expr(data.get("expr"), vars_list, cp, model)
        rhs = data.get("rhs", 0.0)
        sense = str(data.get("sense", "<=")).strip()
        if isinstance(rhs, (list, tuple)) and len(rhs) == 2:
            model.addNlConstr(expr == [float(rhs[0]), float(rhs[1])])
        elif sense == "<=":
            model.addNlConstr(expr <= float(rhs))
        elif sense == ">=":
            model.addNlConstr(expr >= float(rhs))
        elif sense in {"=", "=="}:
            model.addNlConstr(expr == float(rhs))
        else:
            raise ValueError(f"unsupported nonlinear constraint sense: {sense}")

    obj_spec = dict(spec.get("nl_objective") or spec.get("objective") or {})
    obj_expr = _call_expr(obj_spec.get("expr"), vars_list, cp, model)
    sense = str(obj_spec.get("sense", obj_spec.get("objective_sense", "min"))).lower()
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
            "copt.mode": "nlp_spec",
            "copt.status_raw": None if status_raw is None else int(status_raw),
            "copt.nvars": int(len(vars_list)),
            "copt.nl_constrs": int(len(nl_constrs)),
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
