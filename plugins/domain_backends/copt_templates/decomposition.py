"""Decomposition templates: DW / BD / CG (callback-driven skeletons)."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from ..backend_contract import BackendSolveRequest
from .utils import resolve_template_spec


def _default_solve(model: Any, *_args, **_kwargs) -> Any:
    model.solve()
    return model


def _default_obj(model: Any) -> float | None:
    return getattr(model, "objval", None)


def _default_status(model: Any) -> Any:
    return getattr(model, "status", None)


def _as_callable(value: Any, name: str) -> Callable:
    if not callable(value):
        raise ValueError(f"decomposition template requires callable '{name}'")
    return value


def _build_context(kind: str, spec: Mapping[str, Any]) -> dict:
    return {
        "kind": kind,
        "iter": 0,
        "max_iters": int(spec.get("max_iters", 20)),
        "history": [],
        "columns_added": 0,
        "cuts_added": 0,
    }


def _run_dw_cg(kind: str, request: BackendSolveRequest, cp: Any, spec: Mapping[str, Any]) -> Mapping[str, Any]:
    ctx = _build_context(kind, spec)
    master_builder = _as_callable(spec.get("master_builder") or spec.get("build_master"), "master_builder")
    master_solve = spec.get("master_solve") or _default_solve
    sub_builder = _as_callable(spec.get("subproblem_builder") or spec.get("build_subproblem"), "subproblem_builder")
    sub_solve = spec.get("subproblem_solve") or _default_solve
    column_generator = _as_callable(spec.get("column_generator") or spec.get("generate_columns"), "column_generator")
    add_columns = _as_callable(spec.get("add_columns") or spec.get("add_column"), "add_columns")
    stop_condition = spec.get("stop_condition")
    extract_obj = spec.get("objective_extractor") or _default_obj
    extract_status = spec.get("status_extractor") or _default_status

    master = master_builder(request, cp, ctx)
    init_hook = spec.get("init")
    if callable(init_hook):
        init_hook(request, cp, ctx, master)

    best_obj = None
    for k in range(ctx["max_iters"]):
        ctx["iter"] = k
        master_solve(master, ctx)
        obj = extract_obj(master)
        status = extract_status(master)
        ctx["history"].append({"iter": k, "objective": obj, "status": status})
        if best_obj is None or (obj is not None and obj < best_obj):
            best_obj = obj

        if callable(stop_condition) and stop_condition(ctx, master):
            break

        sub = sub_builder(request, cp, ctx, master)
        sub_res = sub_solve(sub, ctx, master)
        columns = column_generator(ctx, master, sub, sub_res)
        if not columns:
            break
        added = add_columns(master, columns, ctx)
        if isinstance(added, int):
            ctx["columns_added"] += int(added)
        else:
            try:
                ctx["columns_added"] += len(columns)
            except Exception:
                ctx["columns_added"] += 0

    return {
        "status": "ok",
        "objective": float(best_obj) if best_obj is not None else 0.0,
        "violation": float(spec.get("violation", 0.0)),
        "metrics": {
            "copt.mode": f"{kind}_decomposition",
            "decomp.iters": int(ctx["iter"] + 1),
            "decomp.columns_added": int(ctx["columns_added"]),
        },
    }


def _run_bd(request: BackendSolveRequest, cp: Any, spec: Mapping[str, Any]) -> Mapping[str, Any]:
    ctx = _build_context("bd", spec)
    master_builder = _as_callable(spec.get("master_builder") or spec.get("build_master"), "master_builder")
    master_solve = spec.get("master_solve") or _default_solve
    sub_builder = _as_callable(spec.get("subproblem_builder") or spec.get("build_subproblem"), "subproblem_builder")
    sub_solve = spec.get("subproblem_solve") or _default_solve
    cut_generator = _as_callable(spec.get("cut_generator") or spec.get("generate_cuts"), "cut_generator")
    add_cuts = _as_callable(spec.get("add_cuts") or spec.get("add_cut"), "add_cuts")
    stop_condition = spec.get("stop_condition")
    extract_obj = spec.get("objective_extractor") or _default_obj
    extract_status = spec.get("status_extractor") or _default_status

    master = master_builder(request, cp, ctx)
    init_hook = spec.get("init")
    if callable(init_hook):
        init_hook(request, cp, ctx, master)

    best_obj = None
    for k in range(ctx["max_iters"]):
        ctx["iter"] = k
        master_solve(master, ctx)
        obj = extract_obj(master)
        status = extract_status(master)
        ctx["history"].append({"iter": k, "objective": obj, "status": status})
        if best_obj is None or (obj is not None and obj < best_obj):
            best_obj = obj

        if callable(stop_condition) and stop_condition(ctx, master):
            break

        sub = sub_builder(request, cp, ctx, master)
        sub_res = sub_solve(sub, ctx, master)
        cuts = cut_generator(ctx, master, sub, sub_res)
        if not cuts:
            break
        added = add_cuts(master, cuts, ctx)
        if isinstance(added, int):
            ctx["cuts_added"] += int(added)
        else:
            try:
                ctx["cuts_added"] += len(cuts)
            except Exception:
                ctx["cuts_added"] += 0

    return {
        "status": "ok",
        "objective": float(best_obj) if best_obj is not None else 0.0,
        "violation": float(spec.get("violation", 0.0)),
        "metrics": {
            "copt.mode": "bd_decomposition",
            "decomp.iters": int(ctx["iter"] + 1),
            "decomp.cuts_added": int(ctx["cuts_added"]),
        },
    }


def solve_decomposition_template(
    kind: str,
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "decomp_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("decomp_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        payload_builder_keys=("copt_decomp_spec_builder", "copt_spec_builder"),
        inline_keys=("master_builder", "subproblem_builder"),
    )

    kind_norm = str(kind).strip().lower()
    if kind_norm in {"dw", "cg"}:
        return _run_dw_cg(kind_norm, request, cp, spec)
    if kind_norm == "bd":
        return _run_bd(request, cp, spec)
    raise ValueError(f"unsupported decomposition kind: {kind_norm}")
