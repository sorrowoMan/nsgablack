"""Safe component overrides for canonical nsgablack Cases."""

from __future__ import annotations

from typing import Any, Mapping


_SUPPORTED_OVERRIDE_KEYS = frozenset(
    {"adapter", "bias_module", "pipeline", "representation_pipeline"}
)


def apply_solver_component_overrides(
    solver: Any,
    component_overrides: Mapping[str, Any] | None,
) -> Any:
    """Apply safe post-construction component overrides and publish an audit.

    Problem replacement is deliberately excluded because Solver construction
    derives dimension/objective state from the problem.  Cases that support
    data/problem overrides must resolve those inputs before constructing the
    Solver.
    """

    overrides = dict(component_overrides or {})
    unknown = sorted(set(overrides) - _SUPPORTED_OVERRIDE_KEYS)
    if unknown:
        raise ValueError(
            "unsupported post-construction component_overrides keys="
            f"{unknown}; supported={sorted(_SUPPORTED_OVERRIDE_KEYS)}"
        )
    if "pipeline" in overrides and "representation_pipeline" in overrides:
        raise ValueError(
            "component_overrides cannot provide both 'pipeline' and "
            "'representation_pipeline'"
        )

    applied: list[str] = []
    if "adapter" in overrides:
        setter = getattr(solver, "set_adapter", None)
        if not callable(setter):
            raise TypeError("Case does not expose set_adapter() for component override")
        setter(overrides["adapter"])
        applied.append("adapter")

    pipeline_key = (
        "representation_pipeline"
        if "representation_pipeline" in overrides
        else "pipeline"
        if "pipeline" in overrides
        else None
    )
    if pipeline_key is not None:
        setter = getattr(solver, "set_representation_pipeline", None)
        if not callable(setter):
            raise TypeError(
                "Case does not expose set_representation_pipeline() for component override"
            )
        setter(overrides[pipeline_key])
        applied.append(pipeline_key)

    if "bias_module" in overrides:
        setter = getattr(solver, "set_bias_module", None)
        if not callable(setter):
            raise TypeError("Case does not expose set_bias_module() for component override")
        setter(overrides["bias_module"])
        applied.append("bias_module")

    solver.component_override_audit = {
        "schema_version": 1,
        "status": "applied" if applied else "not_requested",
        "current": True,
        "requested": sorted(overrides),
        "applied": sorted(applied),
        "supported": sorted(_SUPPORTED_OVERRIDE_KEYS),
    }
    return solver


__all__ = ["apply_solver_component_overrides"]
