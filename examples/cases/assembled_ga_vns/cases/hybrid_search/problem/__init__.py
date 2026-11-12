"""本 Case 的问题定义与工厂。"""
from .quadratic import QuadraticProblem


def build_problem():
    return QuadraticProblem()


__all__ = ["QuadraticProblem", "build_problem"]
