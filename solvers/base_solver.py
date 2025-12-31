# Import the actual base_solver from core directory
import sys
import os

# 添加 core 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
core_dir = os.path.join(parent_dir, 'core')
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

# 尝试多种导入方式，按优先级排序
try:
    # 方式 1: 通过 nsgablack 包导入（推荐）
    from nsgablack.core.base_solver import BaseSolver, SolverConfig, OptimizationResult
except (ImportError, ModuleNotFoundError):
    try:
        # 方式 2: 直接从 core_dir 导入（core_dir 已在 sys.path）
        from base_solver import BaseSolver, SolverConfig, OptimizationResult
    except ImportError as e:
        # 如果都失败了，抛出清晰的错误信息
        raise ImportError(
            f"无法从 core.base_solver 导入 BaseSolver。"
            f"请确保 core/base_solver.py 存在且可访问。\n"
            f"core_dir: {core_dir}\n"
            f"sys.path: {sys.path}\n"
            f"原始错误: {e}"
        ) from e

__all__ = ['BaseSolver', 'SolverConfig', 'OptimizationResult']
