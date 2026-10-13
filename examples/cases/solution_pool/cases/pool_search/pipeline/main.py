"""Case-level pipeline primary entry.

One pipeline entry per case. Slot orchestration is delegated to the shared
representation pipeline kernel.
"""

from typing import Any, Mapping

from nsgablack.representation import PipelineSpec, build_pipeline_kernel
from nsgablack.representation import UniformInitializer, GaussianMutation, ClipRepair


def build_pipeline(
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
):
    """Build one case-level pipeline entry.

    Edit `spec` and `registry` below, then keep this file as the single
    orchestration entry.
    """
    del resource_context
    overrides = dict(component_overrides or {})

    registry = {
        "initialize": UniformInitializer(low=-0.05, high=0.05),
        "mutate": GaussianMutation(sigma=0.01, low=-2.0, high=2.0),
        "repair": ClipRepair(low=-2.0, high=2.0),
    }
    registry.update(dict(overrides.get("pipeline_operators", {}) or {}))
    spec = PipelineSpec.from_value(
        overrides.get(
            "pipeline_spec",
            {
                "key": "default",
                "slots": (
                    {"slot": "init", "operators": ("initialize",)},
                    {"slot": "mutate", "operators": ("mutate",)},
                    {"slot": "repair", "operators": ("repair",)},
                ),
            },
        )
    )
    kernel = build_pipeline_kernel(spec, operator_registry=registry)
    return kernel.representation_pipeline


# Optional helper: expose slot runner for ad-hoc orchestration in the case.
def build_unit_binding(builder, *, name: str, component_overrides: Mapping[str, Any] | None = None):
    """构建算法结构绑定；在 build_solver 中传给对应 Adapter。

    pipeline_spec 需声明 build_unit 槽，并指定 method='build'。
    name 是稳定且带版本的管线标识；恢复走 builder codec，不重跑构建管线。
    各子 Adapter 独立绑定，不改写 Solver 的全局问题管线。
    """
    overrides = dict(component_overrides or {})
    registry = dict(overrides.get("pipeline_operators", {}) or {})
    spec = PipelineSpec.from_value(overrides.get("pipeline_spec", {"key": "default", "slots": ()}))
    kernel = build_pipeline_kernel(spec, operator_registry=registry)
    return kernel.bind_units(builder, name=name)


def run_pipeline_slot(slot: str, value, *, component_overrides: Mapping[str, Any] | None = None, context: Mapping[str, Any] | None = None):
    overrides = dict(component_overrides or {})
    registry = dict(overrides.get("pipeline_operators", {}) or {})
    spec = PipelineSpec.from_value(overrides.get("pipeline_spec", {"key": "default", "slots": ()}))
    kernel = build_pipeline_kernel(spec, operator_registry=registry)
    return kernel.run_slot(slot, value, dict(context or {}))
