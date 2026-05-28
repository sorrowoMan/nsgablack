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
from .utils import resolve_template_spec


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
    if "qp_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("qp_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        default_builder=default_qp_builder,
        payload_builder_keys=("copt_qp_spec_builder", "copt_spec_builder"),
        inline_keys=("c", "Q", "A", "rhs", "sense", "lb", "ub", "vtype", "objective_sense", "quadratic_scale"),
    )
    return solve_qp_spec(request, cp, lambda _req: dict(spec))
