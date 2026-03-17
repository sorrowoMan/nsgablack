from __future__ import annotations

from typing import Any, Dict, Mapping

from .contracts import TemplateSolveFn
from .linear import solve_linear_template
from .qp import solve_qp_template


def build_default_templates(
    *,
    solve_linear_spec,
    default_linear_builder,
    solve_qp_spec,
    default_qp_builder,
) -> Mapping[str, TemplateSolveFn]:
    def _linear(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_linear_template(
            request,
            cp,
            template_params,
            solve_linear_spec=solve_linear_spec,
            default_linear_builder=default_linear_builder,
        )

    def _qp(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_qp_template(
            request,
            cp,
            template_params,
            solve_qp_spec=solve_qp_spec,
            default_qp_builder=default_qp_builder,
        )

    return {"linear": _linear, "qp": _qp}
