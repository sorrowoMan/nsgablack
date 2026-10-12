"""问题管线处理向量；算法管线构建候选 Unit。"""
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.representation import CandidateUnitBuilder, build_pipeline_kernel


def build_pipeline(*, resource_context=None, component_overrides=None):
    return RepresentationPipeline(initializer=UniformInitializer(low=-5, high=5),
        mutator=GaussianMutation(sigma=0.2, low=-5, high=5), repair=ClipRepair(low=-5, high=5))


def build_unit_binding(builder=None):
    builder = builder or CandidateUnitBuilder()
    kernel = build_pipeline_kernel({"slots": [
        {"slot": "build_unit", "operators": ["candidate"], "method": "build"}]},
        operator_registry={"candidate": builder})
    return kernel.bind_units(builder, name="algorithm_units.candidate/v1")
