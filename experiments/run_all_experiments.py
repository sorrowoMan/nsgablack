"""
高级实验统一运行脚本

运行所有4个高级实验：
1. 昂贵黑箱优化
2. 混合变量优化
3. 复杂约束优化
4. 动态优化
"""

import sys
import os
import time
from pathlib import Path

# 添加父目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_exp1():
    """实验1：昂贵黑箱优化"""
    print("\n" + "=" * 70)
    print("实验1：昂贵黑箱优化（代理偏置）")
    print("=" * 70)

    from exp1_runner import ExpensiveOptimizationExperiment

    experiment = ExpensiveOptimizationExperiment(output_dir="results/exp1_expensive")
    experiment.run_full_experiment()

    print("\n✅ 实验1完成！")


def run_exp2():
    """实验2：混合变量优化"""
    print("\n" + "=" * 70)
    print("实验2：混合变量优化（混合Pipeline）")
    print("=" * 70)

    from exp2_mixed_variable import MixedVariableExperiment

    experiment = MixedVariableExperiment()
    experiment.run_quick_test()

    print("\n✅ 实验2完成！")


def run_exp3():
    """实验3：复杂约束优化"""
    print("\n" + "=" * 70)
    print("实验3：复杂约束优化（领域偏置）")
    print("=" * 70)

    from exp3_complex_constraint import ComplexConstraintExperiment

    experiment = ComplexConstraintExperiment()
    experiment.run_quick_test()

    print("\n✅ 实验3完成！")


def run_exp4():
    """实验4：动态优化"""
    print("\n" + "=" * 70)
    print("实验4：动态优化（自适应偏置）")
    print("=" * 70)

    from exp4_dynamic import DynamicOptimizationExperiment

    experiment = DynamicOptimizationExperiment()
    experiment.run_quick_test()

    print("\n✅ 实验4完成！")


def run_all():
    """运行所有实验"""
    print("\n" + "=" * 70)
    print("NSGABlack 高级实验套件")
    print("=" * 70)
    print("\n将运行4个高级实验，验证框架在复杂问题上的优势")

    experiments = [
        ("实验1：昂贵黑箱优化", run_exp1),
        ("实验2：混合变量优化", run_exp2),
        ("实验3：复杂约束优化", run_exp3),
        ("实验4：动态优化", run_exp4),
    ]

    total_start = time.time()

    for i, (name, func) in enumerate(experiments, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/4] 开始: {name}")
        print(f"{'=' * 70}")

        try:
            start = time.time()
            func()
            elapsed = time.time() - start
            print(f"\n⏱️  耗时: {elapsed:.2f}秒")
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 70)
    print("🎉 所有实验完成！")
    print("=" * 70)
    print(f"\n总耗时: {total_elapsed:.2f}秒")
    print("\n结果文件:")
    print("  - results/exp1_expensive/exp1_results.json")
    print("\n下一步:")
    print("  python experiments/visualize_advanced_experiments.py")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="运行NSGABlack高级实验")
    parser.add_argument('--exp', type=int, choices=[1, 2, 3, 4],
                       help='指定运行的实验（1-4），不指定则运行所有')
    parser.add_argument('--quick', action='store_true',
                       help='快速模式（仅测试，不完整运行）')

    args = parser.parse_args()

    if args.exp:
        # 运行单个实验
        exp_map = {
            1: run_exp1,
            2: run_exp2,
            3: run_exp3,
            4: run_exp4
        }
        exp_map[args.exp]()
    else:
        # 运行所有实验
        run_all()
