"""问题管线主入口与 Beam 结构构建绑定。"""
from nsgablack.representation import RepresentationPipeline, build_pipeline_kernel
from .operators import SparseBinaryInitializer, SparseBinaryMutation, SparseBinaryRepair
from .beam_units import BeamUnitBuilder

def build_pipeline(args, *, resource_context=None, component_overrides=None):
    pipeline = RepresentationPipeline(
        initializer=SparseBinaryInitializer(max_active=int(args.max_terms), seed=int(args.seed)),
        mutator=SparseBinaryMutation(flip_prob=float(args.flip_prob), seed=int(args.seed) + 1),
        repair=SparseBinaryRepair(max_active=int(args.max_terms)),
        encoder=None,
    )
    return pipeline


def build_unit_binding(builder=None):
    builder = builder or BeamUnitBuilder()
    kernel = build_pipeline_kernel({"slots": [
        {"slot": "build_unit", "operators": ["beam"], "method": "build"}]},
        operator_registry={"beam": builder})
    return kernel.bind_units(builder, name="algorithm_units.beam/v1")
