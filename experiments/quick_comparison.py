"""
快速运行对比实验的脚本

这是一个便捷的入口，可以快速运行整个对比实验
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_comparison import ComparisonExperiment

# 运行实验
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("NSGABlack vs HybridSATS Comparison Experiment")
    print("=" * 70)
    print("\n这个实验将对比两种算法在多个测试问题上的性能：")
    print("  1. NSGABlack（偏置化组合）")
    print("  2. HybridSATS（手工混合算法）")
    print("\n测试问题：")
    print("  - Sphere (10维，简单单峰)")
    print("  - Rastrigin (10维，多峰)")
    print("  - Rosenbrock (10维，弯曲山谷)")
    print("\n每个问题运行5次（不同随机种子），进行统计分析")
    print("\n" + "=" * 70)

    input("\n按Enter键开始实验...")

    # 创建实验运行器
    experiment = ComparisonExperiment(output_dir="results/comparison")

    # 运行完整对比
    experiment.run_full_comparison()

    print("\n" + "=" * 70)
    print("实验完成！")
    print("=" * 70)
    print("\n结果文件：")
    print("  - results/comparison/comparison_results.json (详细数据)")
    print("  - results/comparison/comparison_report.txt (总结报告)")
    print("\n运行以下命令生成可视化：")
    print("  python experiments/visualize_comparison.py")
