"""初始候选源和问题修复；变化函数装配给实际 Adapter。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


def build_pipeline(*, resource_context=None, component_overrides=None):
    del resource_context, component_overrides
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
                                  repair=ClipRepair(-2., 2.))
