"""共享候选管线；VNS 通过局部 context 提供自己的邻域尺度。"""
from nsgablack.representation import (
    RepresentationPipeline, UniformInitializer, ContextGaussianMutation, ClipRepair,
)


def build_pipeline(*, resource_context=None, component_overrides=None):
    del resource_context
    operators = dict((component_overrides or {}).get("pipeline_operators", {}) or {})
    return RepresentationPipeline(
        initializer=operators.get("initialize", UniformInitializer(low=-2.0, high=2.0)),
        mutator=operators.get("mutate", ContextGaussianMutation(base_sigma=0.1, low=-2.0, high=2.0)),
        repair=operators.get("repair", ClipRepair(low=-2.0, high=2.0)),
    )
