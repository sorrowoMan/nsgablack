from __future__ import annotations

from typing import Any, Mapping, Optional

from .backend_contract import CallbackSpec, DiagnosticSpec, SolutionPoolSpec, WarmStartSpec


def _coerce_warm_start(raw: Any) -> Optional[WarmStartSpec]:
    if raw is None:
        return None
    if isinstance(raw, WarmStartSpec):
        return raw
    if isinstance(raw, Mapping):
        return WarmStartSpec(**raw)
    return WarmStartSpec(data=raw)


def _coerce_solution_pool(raw: Any) -> Optional[SolutionPoolSpec]:
    if raw is None:
        return None
    if isinstance(raw, SolutionPoolSpec):
        return raw
    if isinstance(raw, Mapping):
        return SolutionPoolSpec(**raw)
    raise TypeError("solution_pool must be mapping or SolutionPoolSpec")


def _coerce_callback(raw: Any) -> Optional[CallbackSpec]:
    if raw is None:
        return None
    if isinstance(raw, CallbackSpec):
        return raw
    if isinstance(raw, Mapping):
        return CallbackSpec(**raw)
    raise TypeError("callback must be mapping or CallbackSpec")


def _coerce_diagnostics(raw: Any) -> Optional[DiagnosticSpec]:
    if raw is None:
        return None
    if isinstance(raw, DiagnosticSpec):
        return raw
    if isinstance(raw, Mapping):
        return DiagnosticSpec(**raw)
    raise TypeError("diagnostics must be mapping or DiagnosticSpec")


def resolve_warm_start(request, payload: Mapping[str, Any]) -> Optional[WarmStartSpec]:
    spec = getattr(request, "warm_start", None)
    if spec is not None:
        return _coerce_warm_start(spec)
    for key in ("warm_start", "backend_warm_start", "copt_warm_start"):
        if key in payload:
            return _coerce_warm_start(payload.get(key))
    template_params = payload.get("copt_template_params")
    if isinstance(template_params, Mapping) and "warm_start" in template_params:
        return _coerce_warm_start(template_params.get("warm_start"))
    return None


def resolve_solution_pool(request, payload: Mapping[str, Any]) -> Optional[SolutionPoolSpec]:
    spec = getattr(request, "solution_pool", None)
    if spec is not None:
        return _coerce_solution_pool(spec)
    for key in ("solution_pool", "backend_solution_pool", "copt_solution_pool"):
        if key in payload:
            return _coerce_solution_pool(payload.get(key))
    template_params = payload.get("copt_template_params")
    if isinstance(template_params, Mapping) and "solution_pool" in template_params:
        return _coerce_solution_pool(template_params.get("solution_pool"))
    return None


def resolve_callback(request, payload: Mapping[str, Any]) -> Optional[CallbackSpec]:
    spec = getattr(request, "callback", None)
    if spec is not None:
        return _coerce_callback(spec)
    for key in ("callback", "backend_callback", "copt_callback"):
        if key in payload:
            return _coerce_callback(payload.get(key))
    template_params = payload.get("copt_template_params")
    if isinstance(template_params, Mapping) and "callback" in template_params:
        return _coerce_callback(template_params.get("callback"))
    return None


def resolve_diagnostics(request, payload: Mapping[str, Any]) -> Optional[DiagnosticSpec]:
    spec = getattr(request, "diagnostics", None)
    if spec is not None:
        return _coerce_diagnostics(spec)
    for key in ("diagnostics", "backend_diagnostics", "copt_diagnostics"):
        if key in payload:
            return _coerce_diagnostics(payload.get(key))
    template_params = payload.get("copt_template_params")
    if isinstance(template_params, Mapping) and "diagnostics" in template_params:
        return _coerce_diagnostics(template_params.get("diagnostics"))
    return None


def apply_warm_start(model: Any, cp: Any, spec: Optional[Any]) -> dict[str, Any]:
    spec = _coerce_warm_start(spec)
    if spec is None:
        return {"applied": False, "reason": "none"}
    if callable(spec.apply_fn):
        try:
            spec.apply_fn(model, cp, spec)
            return {"applied": True, "reason": "apply_fn"}
        except Exception as exc:
            return {"applied": False, "reason": f"apply_fn_error:{exc.__class__.__name__}"}

    data = spec.data
    if isinstance(data, Mapping):
        path = data.get("mst_path") or data.get("mip_start_path") or data.get("start_path")
        if path:
            for name in ("readMst", "readMST", "readMipStart", "readMIPStart"):
                fn = getattr(model, name, None)
                if callable(fn):
                    try:
                        fn(str(path))
                        return {"applied": True, "reason": name}
                    except Exception as exc:
                        return {"applied": False, "reason": f"{name}_error:{exc.__class__.__name__}"}
    return {"applied": False, "reason": "unsupported"}


def apply_solution_pool_params(model: Any, cp: Any, spec: Optional[Any]) -> dict[str, Any]:
    spec = _coerce_solution_pool(spec)
    if spec is None:
        return {"applied": False, "reason": "none"}
    params = dict(spec.params or {})
    if spec.max_solutions is not None:
        params.setdefault("PoolSols", int(spec.max_solutions))
    if not params:
        return {"applied": False, "reason": "no_params"}
    applied = 0
    for key, value in params.items():
        if value is None:
            continue
        try:
            model.setParam(key, value)
            applied += 1
        except Exception:
            try:
                model.setParam(str(key), value)
                applied += 1
            except Exception:
                continue
    return {"applied": bool(applied), "reason": "params" if applied else "no_effect"}


def register_callback(model: Any, cp: Any, spec: Optional[Any]) -> dict[str, Any]:
    spec = _coerce_callback(spec)
    if spec is None:
        return {"applied": False, "reason": "none"}
    if callable(spec.register_fn):
        try:
            spec.register_fn(model, cp, spec)
            return {"applied": True, "reason": "register_fn"}
        except Exception as exc:
            return {"applied": False, "reason": f"register_fn_error:{exc.__class__.__name__}"}
    if callable(spec.handler):
        setter = getattr(model, "setCallback", None)
        if callable(setter):
            try:
                setter(spec.handler)
                return {"applied": True, "reason": "setCallback"}
            except Exception as exc:
                return {"applied": False, "reason": f"setCallback_error:{exc.__class__.__name__}"}
    return {"applied": False, "reason": "unsupported"}


def extract_solution_pool(model: Any, cp: Any, spec: Optional[Any]) -> Optional[Mapping[str, Any]]:
    spec = _coerce_solution_pool(spec)
    if spec is None:
        return None
    if callable(spec.extract_fn):
        try:
            return dict(spec.extract_fn(model, cp, spec))
        except Exception:
            return None
    return None


def run_diagnostics(model: Any, cp: Any, spec: Optional[Any]) -> Optional[Mapping[str, Any]]:
    spec = _coerce_diagnostics(spec)
    if spec is None:
        return None
    if callable(spec.apply_fn):
        try:
            return dict(spec.apply_fn(model, cp, spec))
        except Exception:
            return None
    out: dict[str, Any] = {}
    if spec.iis:
        fn = getattr(model, "computeIIS", None)
        if callable(fn):
            try:
                fn()
                out["iis"] = True
            except Exception:
                out["iis"] = False
    if spec.feas_relax:
        relax_constr = bool(spec.meta.get("relax_constr", True))
        relax_var = bool(spec.meta.get("relax_var", True))
        mode = spec.meta.get("mode")
        if mode is not None:
            try:
                model.setParam(getattr(cp.COPT.Param, "FeasRelaxMode", "FeasRelaxMode"), mode)
            except Exception:
                try:
                    model.setParam("FeasRelaxMode", mode)
                except Exception:
                    pass
        fn = getattr(model, "feasRelaxS", None)
        if not callable(fn):
            fn = getattr(model, "feasRelax", None)
        if callable(fn):
            try:
                fn(relax_constr, relax_var)
                out["feas_relax"] = True
            except Exception:
                out["feas_relax"] = False
    return out or None
