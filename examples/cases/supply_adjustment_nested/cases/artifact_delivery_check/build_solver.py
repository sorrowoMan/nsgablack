"""数据验证 Case 的唯一装配入口。"""
from .solver.case import ArtifactDeliveryCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("artifact delivery accepts explicit component_overrides only")
    options = dict(component_overrides or {})
    node = options.pop("expected_node", None)
    if options:
        raise ValueError(f"unsupported artifact delivery options: {sorted(options)}")
    return ArtifactDeliveryCase(resource_context=resource_context, expected_node=node)
