"""多个外层提案共用候选处理管线，内层条件不写入共享 context。"""
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair

def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(low=-1., high=1.),
        mutator=GaussianMutation(sigma=.15, low=-2., high=2.),
        repair=ClipRepair(low=-2., high=2.))
