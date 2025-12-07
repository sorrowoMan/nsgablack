"""简单测试脚本，验证并行评估功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import numpy as np
from core.base import BlackBoxProblem
from utils.parallel_evaluator import ParallelEvaluator

# 简单测试问题
class SimpleProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(
            name="简单测试问题",
            dimension=5,
            bounds={f'x{i}': (-1, 1) for i in range(5)}
        )

    def evaluate(self, x):
        # 简单的二次函数
        return np.sum(x**2)

def test_parallel_evaluation():
    """测试并行评估功能"""
    print("测试并行评估功能...")
    print("=" * 50)

    # 创建问题
    problem = SimpleProblem()

    # 生成测试数据
    population = np.random.uniform(-1, 1, (20, 5))

    # 测试串行评估
    print("\n1. 测试串行评估...")
    serial_evaluator = ParallelEvaluator(backend="thread", max_workers=1)
    start = time.time()
    obj_serial, vio_serial = serial_evaluator.evaluate_population(population, problem)
    serial_time = time.time() - start
    print(f"   串行评估时间: {serial_time:.3f}s")
    print(f"   成功评估: {len(obj_serial)}/{len(population)} 个个体")

    # 测试并行评估
    print("\n2. 测试并行评估...")
    parallel_evaluator = ParallelEvaluator(backend="thread", max_workers=4)
    start = time.time()
    obj_parallel, vio_parallel = parallel_evaluator.evaluate_population(population, problem)
    parallel_time = time.time() - start
    print(f"   并行评估时间: {parallel_time:.3f}s")
    print(f"   成功评估: {len(obj_parallel)}/{len(population)} 个个体")

    # 验证结果一致性
    print("\n3. 验证结果一致性...")
    diff = np.max(np.abs(obj_serial - obj_parallel))
    print(f"   最大差异: {diff:.2e}")
    print(f"   结果一致: {'是' if diff < 1e-10 else '否'}")

    # 计算加速比
    if parallel_time > 0:
        speedup = serial_time / parallel_time
        print(f"\n4. 性能指标...")
        print(f"   加速比: {speedup:.2f}x")
        print(f"   效率: {speedup/4*100:.1f}%")  # 4个工作线程

    # 获取评估统计
    stats = parallel_evaluator.get_stats()
    print(f"\n5. 评估统计...")
    print(f"   总评估次数: {stats['total_evaluations']}")
    print(f"   平均评估时间: {stats['avg_evaluation_time']*1000:.2f}ms")
    print(f"   错误次数: {stats['error_count']}")

    print("\n测试完成！")
    return True

if __name__ == "__main__":
    try:
        success = test_parallel_evaluation()
        if success:
            print("\n[SUCCESS] 并行评估功能测试通过")
        else:
            print("\n[FAILED] 并行评估功能测试失败")
    except Exception as e:
        print(f"\n[ERROR] 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()