"""Quadratic optimization template for CoptBackend.

中文说明：
- 该模板用于二次规划场景（QP，可含线性约束与变量类型约束）。
- 输入来自 `copt_template_params`（推荐）或 builder 回调，常用字段包括
    `c/Q/A/rhs/sense/lb/ub/vtype/objective_sense/quadratic_scale`。
- 模板负责统一参数入口，并委托 backend 的 QP 规格求解实现执行建模与求解。

English:
- This template targets quadratic optimization problems (QP) with optional
    linear constraints and variable type controls.
- Inputs are provided via `copt_template_params` (recommended) or builder
    callback, with common fields such as
    `c/Q/A/rhs/sense/lb/ub/vtype/objective_sense/quadratic_scale`.
- The template normalizes input entry and delegates actual model build/solve
    to backend QP-spec execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..backend_contract import BackendSolveRequest


def solve_qp_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
    *,
    solve_qp_spec,
    default_qp_builder,
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})

    if "spec" in params:
        spec_obj = params.get("spec")
        if not isinstance(spec_obj, Mapping):
            raise TypeError("qp template params['spec'] must be a mapping")
        return solve_qp_spec(request, cp, lambda _req: dict(spec_obj))

    local_builder = params.get("qp_spec_builder")
    if not callable(local_builder):
        local_builder = payload.get("copt_qp_spec_builder")
    if not callable(local_builder):
        local_builder = default_qp_builder
    if callable(local_builder):
        return solve_qp_spec(request, cp, local_builder)

    if "c" in params:
        return solve_qp_spec(request, cp, lambda _req: dict(params))

    raise ValueError(
        "qp template requires one of: template_params['spec'], "
        "template_params['qp_spec_builder'], payload['copt_qp_spec_builder'], "
        "constructor qp_spec_builder, or inline template_params with key 'c'"
    )
