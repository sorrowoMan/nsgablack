"""问题管线只做边界修复；DE 变化由自己的差分规则负责。"""
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-4.0, 4.0))
