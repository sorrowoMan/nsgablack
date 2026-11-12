"""所有 Adapter 共用的问题候选管线；行为组件另行绑定给实际所有者。"""
from nsgablack.representation import RepresentationPipeline

from .operators import BoxRepair


def build_pipeline():
    return RepresentationPipeline(repair=BoxRepair())
