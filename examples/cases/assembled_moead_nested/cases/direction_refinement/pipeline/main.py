"""各算法共享问题修复；搜索初始化和变化在实际叶 Adapter 上装配。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
