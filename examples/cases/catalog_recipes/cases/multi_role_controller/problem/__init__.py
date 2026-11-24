"""替换这个工厂即可接入自己的问题；默认示例可直接运行。"""
from nsgablack.project.starter import QuadraticProblem


def build_problem():
    return QuadraticProblem()
