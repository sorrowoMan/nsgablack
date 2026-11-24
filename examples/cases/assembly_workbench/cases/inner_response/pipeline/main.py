"""唯一问题管线入口；初始化、变化和可行性修复保持分离。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline
from .operators import ResponseOperators

def build_pipeline():
    operator = ResponseOperators()
    return RepresentationPipeline(initializer=operator, mutator=operator,
                                  repair=ClipRepair(low=-3., high=3.))
