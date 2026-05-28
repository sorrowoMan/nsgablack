from __future__ import annotations

from typing import Any, Dict, Mapping

from .contracts import TemplateSolveFn
from .expcone import solve_expcone_template
from .linear import solve_linear_template
from .matrix import solve_matrix_template
from .multiobj import solve_multiobj_template
from .nlp import solve_nlp_template
from .qcp import solve_qcp_template
from .qp import solve_qp_template
from .sdp import solve_sdp_template
from .socp import solve_socp_template


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
    def _qcp(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_qcp_template(request, cp, template_params)

    def _socp(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_socp_template(request, cp, template_params)

    def _sdp(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_sdp_template(request, cp, template_params)

    def _nlp(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_nlp_template(request, cp, template_params)

    def _expcone(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_expcone_template(request, cp, template_params)

    def _multiobj(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_multiobj_template(request, cp, template_params)

    def _matrix(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_matrix_template(request, cp, template_params)

    def _dw(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_decomposition_template("dw", request, cp, template_params)

    def _cg(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_decomposition_template("cg", request, cp, template_params)

    def _bd(request: Any, cp: Any, template_params: Mapping[str, Any]):
        return solve_decomposition_template("bd", request, cp, template_params)

    return {
        "linear": _linear,
        "lp": _linear,
        "mip": _linear,
        "milp": _linear,
        "qp": _qp,
        "miqp": _qp,
        "qcp": _qcp,
        "qcqp": _qcp,
        "miqcp": _qcp,
        "socp": _socp,
        "rsocp": _socp,
        "sdp": _sdp,
        "nlp": _nlp,
        "expcone": _expcone,
        "multiobj": _multiobj,
        "matrix": _matrix,
        "matrix_lp": _matrix,
        "matrix_mip": _matrix,
        "dw": _dw,
        "cg": _cg,
        "bd": _bd,
        "dantzig_wolfe": _dw,
        "column_generation": _cg,
        "benders": _bd,
    }
from .decomposition import solve_decomposition_template
