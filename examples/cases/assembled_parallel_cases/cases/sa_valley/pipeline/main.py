"""与 DE 独立的管线实例；只装配问题边界修复。"""
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-4.0, 4.0))
