# solvers/nsga2.py
#
# 这个文件现在是一个包装器，实际的 NSGA-II 实现在 core/solver.py
# 这样做是为了统一代码库，避免重复实现
#
# 使用示例：
#   from solvers.nsga2 import BlackBoxSolverNSGAII
#   或者
#   from core.solver import BlackBoxSolverNSGAII

from core.solver import BlackBoxSolverNSGAII

__all__ = ['BlackBoxSolverNSGAII']
