from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from ..backend_contract import BackendSolveRequest


def resolve_template_spec(
    request: BackendSolveRequest,
    template_params: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    default_builder: Callable[[BackendSolveRequest], Mapping[str, Any]] | None = None,
    payload_builder_keys: Sequence[str] = (),
    inline_keys: Sequence[str] = (),
) -> Mapping[str, Any]:
    params = dict(template_params or {})
    if "spec" in params:
        spec_obj = params.get("spec")
        if not isinstance(spec_obj, Mapping):
            raise TypeError("template params['spec'] must be a mapping")
        return dict(spec_obj)
    if "params" in params:
        spec_obj = params.get("params")
        if not isinstance(spec_obj, Mapping):
            raise TypeError("template params['params'] must be a mapping")
        return dict(spec_obj)

    builder = params.get("spec_builder") or params.get("builder")
    if not callable(builder):
        for key in payload_builder_keys:
            candidate = payload.get(key)
            if callable(candidate):
                builder = candidate
                break
    if not callable(builder):
        builder = default_builder
    if callable(builder):
        spec_obj = builder(request)
        if not isinstance(spec_obj, Mapping):
            raise TypeError("template spec_builder must return a mapping")
        return dict(spec_obj)

    if inline_keys and any(key in params for key in inline_keys):
        return params

    raise ValueError(
        "template requires one of: template_params['spec'], template_params['params'], "
        "template_params['spec_builder'], payload spec builder, or inline parameters"
    )


def coerce_vtype(value: Any, cp: Any) -> Any:
    if value is None:
        return cp.COPT.CONTINUOUS
    if isinstance(value, str):
        mark = value.strip().upper()
        if mark in {"B", "BIN", "BINARY"}:
            return cp.COPT.BINARY
        if mark in {"I", "INT", "INTEGER"}:
            return cp.COPT.INTEGER
        return cp.COPT.CONTINUOUS
    return value


def _infer_n(spec: Mapping[str, Any]) -> int | None:
    for key in ("n", "num_vars", "num_variables"):
        if key in spec and spec[key] is not None:
            return int(spec[key])
    for key in ("c", "lb", "ub", "vtype"):
        value = spec.get(key)
        if isinstance(value, (list, tuple, np.ndarray)):
            return int(len(value))
    Q = spec.get("Q")
    if Q is not None:
        try:
            return int(np.asarray(Q).shape[0])
        except Exception:
            return None
    A = spec.get("A")
    if A is not None:
        try:
            return int(np.asarray(A).shape[1])
        except Exception:
            return None
    return None


def _broadcast_values(value: Any, n: int, default_value: float) -> list[float]:
    if value is None:
        return [float(default_value)] * n
    if isinstance(value, (int, float, np.floating)):
        return [float(value)] * n
    seq = list(value)
    if len(seq) != n:
        raise ValueError("value length mismatch with variable count")
    return [float(v) for v in seq]


def build_variables(model: Any, cp: Any, spec: Mapping[str, Any], *, default_name: str = "x"):
    vars_spec = spec.get("vars")
    vars_list = []
    name_map: dict[str, Any] = {}
    if isinstance(vars_spec, Iterable) and not isinstance(vars_spec, (str, bytes, Mapping)):
        for idx, entry in enumerate(list(vars_spec)):
            data = dict(entry or {})
            lb = float(data.get("lb", -cp.COPT.INFINITY))
            ub = float(data.get("ub", cp.COPT.INFINITY))
            vtype = coerce_vtype(data.get("vtype"), cp)
            name = str(data.get("name") or f"{default_name}_{idx}")
            var = model.addVar(lb=lb, ub=ub, vtype=vtype, name=name)
            vars_list.append(var)
            name_map[name] = var
        return vars_list, name_map

    n = _infer_n(spec)
    if n is None:
        raise ValueError("unable to infer variable count from template spec")
    lb = _broadcast_values(spec.get("lb"), n, -cp.COPT.INFINITY)
    ub = _broadcast_values(spec.get("ub"), n, cp.COPT.INFINITY)
    vtypes = spec.get("vtype")
    if vtypes is None:
        vtypes_list = [cp.COPT.CONTINUOUS] * n
    elif isinstance(vtypes, (list, tuple, np.ndarray)):
        if len(vtypes) != n:
            raise ValueError("vtype length mismatch with variable count")
        vtypes_list = [coerce_vtype(v, cp) for v in vtypes]
    else:
        vtypes_list = [coerce_vtype(vtypes, cp)] * n

    for idx in range(n):
        name = f"{default_name}_{idx}"
        var = model.addVar(lb=float(lb[idx]), ub=float(ub[idx]), vtype=vtypes_list[idx], name=name)
        vars_list.append(var)
        name_map[name] = var
    return vars_list, name_map


def resolve_var_refs(refs: Sequence[Any], vars_list: Sequence[Any], name_map: Mapping[str, Any]) -> list[Any]:
    out: list[Any] = []
    for ref in refs:
        if isinstance(ref, (int, np.integer)):
            out.append(vars_list[int(ref)])
            continue
        if isinstance(ref, Mapping):
            if "index" in ref:
                out.append(vars_list[int(ref["index"])])
                continue
            if "name" in ref:
                name = str(ref["name"])
                out.append(name_map[name])
                continue
        name = str(ref)
        if name in name_map:
            out.append(name_map[name])
            continue
        raise KeyError(f"unknown variable reference: {ref}")
    return out


def resolve_var_ref(ref: Any, vars_list: Sequence[Any], name_map: Mapping[str, Any]) -> Any:
    if isinstance(ref, (int, np.integer)):
        return vars_list[int(ref)]
    if isinstance(ref, Mapping):
        if "index" in ref:
            return vars_list[int(ref["index"])]
        if "name" in ref:
            name = str(ref["name"])
            return name_map[name]
    name = str(ref)
    if name in name_map:
        return name_map[name]
    raise KeyError(f"unknown variable reference: {ref}")


def build_linear_expr(cp: Any, vars_list: Sequence[Any], coeffs: Sequence[float]) -> Any:
    return cp.quicksum(float(coeffs[i]) * vars_list[i] for i in range(len(coeffs)))


def add_linear_constraints(model: Any, cp: Any, vars_list: Sequence[Any], spec: Mapping[str, Any]) -> None:
    if "linear_constraints" in spec:
        for entry in spec.get("linear_constraints") or []:
            data = dict(entry or {})
            coeffs = data.get("coeffs") or data.get("coefs") or data.get("a")
            if coeffs is None:
                raise ValueError("linear constraint missing coeffs")
            coeffs_arr = np.asarray(coeffs, dtype=float).reshape(-1)
            expr = build_linear_expr(cp, vars_list, coeffs_arr)
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
                raise ValueError(f"unsupported linear constraint sense: {sense}")
        return

    A = spec.get("A")
    rhs = spec.get("rhs")
    if A is None or rhs is None:
        return
    A_arr = np.asarray(A, dtype=float)
    rhs_arr = np.asarray(rhs, dtype=float).reshape(-1)
    if A_arr.ndim != 2:
        raise ValueError("linear spec A must be 2D")
    if A_arr.shape[1] != len(vars_list):
        raise ValueError("linear spec A columns mismatch with variables")
    if A_arr.shape[0] != rhs_arr.size:
        raise ValueError("linear spec A rows mismatch with rhs")

    sense = spec.get("sense", "<=")
    if isinstance(sense, (list, tuple)):
        sense_list = [str(s).strip() for s in sense]
    else:
        sense_list = [str(sense).strip()] * int(A_arr.shape[0])
    if len(sense_list) != int(A_arr.shape[0]):
        raise ValueError("linear spec sense length mismatch with rows")

    for r in range(int(A_arr.shape[0])):
        expr = build_linear_expr(cp, vars_list, A_arr[r])
        rhs_r = rhs_arr[r]
        mark = sense_list[r]
        if isinstance(rhs_r, (list, tuple)) and len(rhs_r) == 2:
            model.addConstr(expr == [float(rhs_r[0]), float(rhs_r[1])])
        elif mark == "<=":
            model.addConstr(expr <= float(rhs_r))
        elif mark == ">=":
            model.addConstr(expr >= float(rhs_r))
        elif mark in {"=", "=="}:
            model.addConstr(expr == float(rhs_r))
        else:
            raise ValueError(f"unsupported constraint sense: {mark}")


def apply_model_params(model: Any, cp: Any, params: Mapping[str, Any] | None) -> None:
    if not params:
        return
    for key, value in dict(params).items():
        if value is None:
            continue
        try:
            model.setParam(key, value)
        except Exception:
            try:
                model.setParam(str(key), value)
            except Exception:
                continue


def _resolve_indicator_type(cp: Any, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    name = str(value).strip().upper()
    mapping = {
        "IFTHEN": "INDICATOR_IFTHEN",
        "ONLYIF": "INDICATOR_ONLYIF",
        "IFF": "INDICATOR_IFANDONLYIF",
        "IFANDONLYIF": "INDICATOR_IFANDONLYIF",
    }
    const_name = mapping.get(name, name)
    return getattr(cp.COPT, const_name, None)


def _build_linear_expr_from_spec(
    cp: Any,
    vars_list: Sequence[Any],
    name_map: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> Any:
    coeffs = spec.get("coeffs") or spec.get("coefs") or spec.get("a")
    if coeffs is None:
        raise ValueError("indicator constraint expr missing coeffs")
    coeffs_arr = np.asarray(coeffs, dtype=float).reshape(-1)
    if len(coeffs_arr) != len(vars_list):
        raise ValueError("indicator constraint coeffs length mismatch with variables")
    return build_linear_expr(cp, vars_list, coeffs_arr)


def add_indicator_constraints(
    model: Any,
    cp: Any,
    vars_list: Sequence[Any],
    name_map: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]] | None,
) -> None:
    if not entries:
        return
    for entry in entries:
        data = dict(entry or {})
        if "binvar" in data:
            binvar_ref = data.get("binvar")
        else:
            binvar_ref = data.get("indicator")
        if binvar_ref is None:
            raise ValueError("indicator constraint requires 'binvar'")
        binvar = resolve_var_ref(binvar_ref, vars_list, name_map)
        binval = data.get("binval", True)
        expr_builder = data.get("expr_builder") or data.get("expr")
        if callable(expr_builder):
            expr = expr_builder(vars_list, cp, model)  # type: ignore[misc]
        else:
            expr_spec = data.get("expr_spec") or data.get("expr") or {}
            if not isinstance(expr_spec, Mapping):
                raise TypeError("indicator constraint expr must be mapping or callable")
            expr = _build_linear_expr_from_spec(cp, vars_list, name_map, expr_spec)
            rhs = expr_spec.get("rhs", 0.0)
            sense = str(expr_spec.get("sense", "<=")).strip()
            if sense == "<=":
                expr = expr <= float(rhs)
            elif sense == ">=":
                expr = expr >= float(rhs)
            elif sense in {"=", "=="}:
                expr = expr == float(rhs)
            else:
                raise ValueError(f"unsupported indicator constraint sense: {sense}")

        indicator_type = _resolve_indicator_type(cp, data.get("indicator_type") or data.get("type"))
        name = data.get("name")
        add_indicator = getattr(model, "addGenConstrIndicator", None)
        if callable(add_indicator):
            if indicator_type is None:
                add_indicator(binvar, bool(binval), expr, name=name)
            else:
                add_indicator(binvar, bool(binval), expr, indicator_type, name=name)
        else:
            model.addConstr((binvar == int(bool(binval))) >> expr, name=name)


def add_gen_constraints(
    model: Any,
    cp: Any,
    vars_list: Sequence[Any],
    name_map: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]] | None,
) -> None:
    if not entries:
        return
    for entry in entries:
        data = dict(entry or {})
        kind = str(data.get("kind") or data.get("type") or "").strip().lower()
        name = data.get("name")
        if kind in {"and", "or"}:
            y_ref = data.get("y") if "y" in data else (data.get("out") if "out" in data else data.get("target"))
            xs = data.get("vars") if "vars" in data else (data.get("x") if "x" in data else [])
            y = resolve_var_ref(y_ref, vars_list, name_map)
            xs_resolved = resolve_var_refs(list(xs), vars_list, name_map)
            if kind == "and":
                model.addGenConstrAnd(y, xs_resolved, name=name)
            else:
                model.addGenConstrOr(y, xs_resolved, name=name)
            continue
        if kind == "abs":
            y_ref = data.get("y") if "y" in data else (data.get("out") if "out" in data else data.get("target"))
            x_ref = data.get("x") if "x" in data else data.get("var")
            y = resolve_var_ref(y_ref, vars_list, name_map)
            x = resolve_var_ref(x_ref, vars_list, name_map)
            model.addGenConstrAbs(y, x, name=name)
            continue
        if kind in {"max", "min"}:
            y_ref = data.get("y") if "y" in data else (data.get("out") if "out" in data else data.get("target"))
            xs = data.get("vars") if "vars" in data else (data.get("x") if "x" in data else [])
            y = resolve_var_ref(y_ref, vars_list, name_map)
            xs_resolved = resolve_var_refs(list(xs), vars_list, name_map)
            if kind == "max":
                model.addGenConstrMax(y, xs_resolved, name=name)
            else:
                model.addGenConstrMin(y, xs_resolved, name=name)
            continue
        if kind == "pwl":
            x_ref = data.get("x") if "x" in data else data.get("var")
            y_ref = data.get("y") if "y" in data else data.get("out")
            x = resolve_var_ref(x_ref, vars_list, name_map)
            y = resolve_var_ref(y_ref, vars_list, name_map)
            x_pts = data.get("x_pts") or data.get("x_points")
            y_pts = data.get("y_pts") or data.get("y_points")
            if x_pts is None or y_pts is None:
                raise ValueError("pwl constraint requires x_pts and y_pts")
            model.addGenConstrPWL(x, y, list(x_pts), list(y_pts), name=name)
            continue
        raise ValueError(f"unsupported gen constraint kind: {kind}")


def apply_feas_relaxation(model: Any, cp: Any, spec: Mapping[str, Any] | None) -> bool:
    if not spec:
        return False
    cfg = dict(spec)
    force = bool(cfg.get("force", False))
    on_infeasible = bool(cfg.get("on_infeasible", True))
    status = getattr(model, "status", None)
    infeasible_flag = False
    if status is not None:
        infeasible_const = getattr(cp.COPT, "INFEASIBLE", None)
        if infeasible_const is not None:
            infeasible_flag = status == infeasible_const
    if (on_infeasible and not infeasible_flag and not force):
        return False

    mode = cfg.get("mode")
    if mode is not None:
        try:
            model.setParam(getattr(cp.COPT.Param, "FeasRelaxMode", "FeasRelaxMode"), mode)
        except Exception:
            try:
                model.setParam("FeasRelaxMode", mode)
            except Exception:
                pass

    relax_constr = cfg.get("relax_constr", cfg.get("relax_constraints", True))
    relax_var = cfg.get("relax_var", cfg.get("relax_variables", True))
    method = str(cfg.get("method", "feasRelaxS")).strip()
    if method == "feasRelax":
        model.feasRelax(bool(relax_constr), bool(relax_var))
    else:
        model.feasRelaxS(bool(relax_constr), bool(relax_var))
    return True
