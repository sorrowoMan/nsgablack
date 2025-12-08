"""
贝叶斯优化快速测试
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solvers.bayesian_optimizer import BayesianOptimizer


def test_function(x):
    """测试函数"""
    return np.sum((x - 2)**2)


def test():
    """测试贝叶斯优化"""
    print("贝叶斯优化测试")
    print("-" * 40)

    # 创建优化器
    bo = BayesianOptimizer(acquisition='ei', kernel='rbf')

    # 设置边界
    bounds = [(0, 5), (0, 5)]

    # 运行优化
    result = bo.optimize(
        objective_func=test_function,
        bounds=bounds,
        budget=30
    )

    print(f"最优解: {result['best_x']}")
    print(f"最优值: {result['best_y']:.6f}")
    print(f"理论最优: [2.0, 2.0], 0.0")

    # 计算误差
    error = np.linalg.norm(result['best_x'] - np.array([2.0, 2.0]))
    print(f"误差: {error:.4f}")

    if error < 0.5:
        print("✓ 测试通过!")
        return True
    else:
        print("✗ 测试失败!")
        return False


if __name__ == "__main__":
    success = test()
    exit(0 if success else 1)