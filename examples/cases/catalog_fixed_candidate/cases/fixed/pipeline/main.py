"""同一问题管线提供默认随机初值和 [0,1] 问题修复。"""
from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair


def build_pipeline():
    return RepresentationPipeline(
        initializer=UniformInitializer(low=0.0, high=1.0),
        repair=ClipRepair(low=0.0, high=1.0),
    )
