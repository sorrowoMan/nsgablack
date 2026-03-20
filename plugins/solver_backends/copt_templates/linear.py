"""Linear optimization template for CoptBackend.

中文说明：
- 该模板用于线性规划/线性整数规划（LP/MILP）场景。
- 输入来自 `copt_template_params`（推荐）或 builder 回调，核心字段包括
    `c/A/rhs/sense/lb/ub/vtype`。
- 模板本身只负责解析模板参数并委托给 backend 的线性建模求解实现。

English:
- This template is for linear and mixed-integer linear optimization (LP/MILP).
- Inputs come from `copt_template_params` (recommended) or a builder callback,
    with key fields such as `c/A/rhs/sense/lb/ub/vtype`.
- The template only resolves parameters and delegates model construction/solve
    to backend linear-spec execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..backend_contract import BackendSolveRequest
from .utils import resolve_template_spec


def solve_linear_template(
    request: BackendSolveRequest,
    cp: Any,
    template_params: Mapping[str, Any],
    *,
    solve_linear_spec,
    default_linear_builder,
) -> Mapping[str, Any]:
    payload = dict(request.payload or {})
    params = dict(template_params or {})
    if "linear_spec_builder" in params and "spec_builder" not in params:
        params["spec_builder"] = params.get("linear_spec_builder")

    spec = resolve_template_spec(
        request,
        params,
        payload,
        default_builder=default_linear_builder,
        payload_builder_keys=("copt_linear_spec_builder", "copt_spec_builder"),
        inline_keys=("c", "A", "rhs", "sense", "lb", "ub", "vtype", "objective_sense"),
    )
    return solve_linear_spec(request, cp, lambda _req: dict(spec))
