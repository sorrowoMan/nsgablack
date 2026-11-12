"""所有算法复用同一问题修复；不复制整条 Pipeline。"""
from nsgablack.representation import ClipRepair, RepresentationPipeline


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
