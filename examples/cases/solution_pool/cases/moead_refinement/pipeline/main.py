"""问题管线由所有搜索角色共享。"""
from nsgablack.representation import (
    RepresentationPipeline, UniformInitializer, ContextGaussianMutation, ClipRepair,
)


def build_pipeline():
    return RepresentationPipeline(
        initializer=UniformInitializer(low=-2., high=2.),
        mutator=ContextGaussianMutation(base_sigma=0.1, low=-2., high=2.),
        repair=ClipRepair(low=-2., high=2.),
    )
