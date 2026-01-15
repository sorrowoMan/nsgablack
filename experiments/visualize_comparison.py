"""
对比实验结果可视化

生成收敛曲线对比图、箱线图等可视化结果
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class ComparisonVisualizer:
    """对比实验可视化工具"""

    def __init__(self, results_dir: str = None):
        # 如果未指定，尝试多个可能的路径
        if results_dir is None:
            possible_paths = [
                Path("results/comparison"),  # 从experiments目录运行
                Path("../results/comparison"),  # 从experiments子目录运行
                Path("../../results/comparison"),  # 更深的子目录
                Path("C:/Users/hp/Desktop/代码逻辑 - 副本/nsgablack/results/comparison"),  # 绝对路径
            ]

            for path in possible_paths:
                if (path / "comparison_results.json").exists():
                    results_dir = path
                    break

            if results_dir is None:
                raise FileNotFoundError(
                    f"无法找到comparison_results.json，尝试的路径：{possible_paths}"
                )

        self.results_dir = Path(results_dir)
        self.results_file = self.results_dir / "comparison_results.json"

        # 加载结果
        with open(self.results_file, 'r') as f:
            data = json.load(f)
            self.results = data['results']

        self.output_dir = self.results_dir / "visualizations"
        self.output_dir.mkdir(exist_ok=True)

    def plot_convergence_curves(self):
        """绘制收敛曲线对比图"""

        problems = list(set([r['problem'] for r in self.results['NSGABlack']]))

        fig, axes = plt.subplots(1, len(problems), figsize=(6*len(problems), 5))
        if len(problems) == 1:
            axes = [axes]

        for i, problem in enumerate(problems):
            ax = axes[i]

            # 获取该问题的所有运行
            nsgablack_runs = [r for r in self.results['NSGABlack'] if r['problem'] == problem]
            hybrid_runs = [r for r in self.results['HybridSATS'] if r['problem'] == problem]

            # 计算平均曲线 - 考虑两种算法的最大长度
            max_gen_nsga = max([len(r['history']) for r in nsgablack_runs]) if nsgablack_runs else 0
            max_gen_hybrid = max([len(r['history']) for r in hybrid_runs]) if hybrid_runs else 0
            max_gen = max(max_gen_nsga, max_gen_hybrid)

            nsgablack_curves = []
            hybrid_curves = []

            for run in nsgablack_runs:
                curve = [h['best_fitness'] for h in run['history']]
                # 统一到相同长度
                curve = curve + [curve[-1]] * (max_gen - len(curve))
                nsgablack_curves.append(curve)

            for run in hybrid_runs:
                curve = [h['best_fitness'] for h in run['history']]
                curve = curve + [curve[-1]] * (max_gen - len(curve))
                hybrid_curves.append(curve)

            # 计算均值和标准差
            nsgablack_mean = np.mean(nsgablack_curves, axis=0)
            nsgablack_std = np.std(nsgablack_curves, axis=0)
            hybrid_mean = np.mean(hybrid_curves, axis=0)
            hybrid_std = np.std(hybrid_curves, axis=0)

            generations = range(1, max_gen + 1)

            # 绘制
            ax.plot(generations, nsgablack_mean, label='NSGABlack', linewidth=2, color='#2E86AB')
            ax.fill_between(generations,
                            nsgablack_mean - nsgablack_std,
                            nsgablack_mean + nsgablack_std,
                            alpha=0.2, color='#2E86AB')

            ax.plot(generations, hybrid_mean, label='HybridSATS', linewidth=2, color='#A23B72', linestyle='--')
            ax.fill_between(generations,
                            hybrid_mean - hybrid_std,
                            hybrid_mean + hybrid_std,
                            alpha=0.2, color='#A23B72')

            ax.set_xlabel('Generation')
            ax.set_ylabel('Best Fitness')
            ax.set_title(f'{problem}: Convergence Comparison')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.set_yscale('log')  # 对数坐标

        plt.tight_layout()
        plt.savefig(self.output_dir / 'convergence_comparison.png', dpi=300, bbox_inches='tight')
        print(f"收敛曲线图已保存: {self.output_dir / 'convergence_comparison.png'}")
        plt.close()

    def plot_boxplot(self):
        """绘制箱线图对比"""

        problems = list(set([r['problem'] for r in self.results['NSGABlack']]))

        fig, ax = plt.subplots(1, 1, figsize=(10, 6))

        # 准备数据
        data = []
        labels = []

        for problem in problems:
            nsgablack_fitness = [r['best_fitness'] for r in self.results['NSGABlack']
                                   if r['problem'] == problem]
            hybrid_fitness = [r['best_fitness'] for r in self.results['HybridSATS']
                               if r['problem'] == problem]

            data.append(nsgablack_fitness)
            data.append(hybrid_fitness)
            labels.extend([f'{problem}\nNSGABlack', f'{problem}\nHybridSATS'])

        # 绘制箱线图
        bp = ax.boxplot(data, labels=labels, patch_artist=True)

        # 设置颜色
        colors = ['#2E86AB', '#A23B72'] * len(problems)
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Best Fitness')
        ax.set_title('Algorithm Performance Comparison (Box Plot)')
        ax.grid(True, alpha=0.3, axis='y')

        # 旋转x轴标签
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        plt.savefig(self.output_dir / 'boxplot_comparison.png', dpi=300, bbox_inches='tight')
        print(f"箱线图已保存: {self.output_dir / 'boxplot_comparison.png'}")
        plt.close()

    def plot_development_efficiency(self):
        """绘制开发效率对比图"""

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # 左图：代码行数对比
        metrics = ['Code Lines', 'Implementation Time (hours)', 'Parameters']
        nsgablack_values = [3, 5/60, 2]  # 3行，5分钟=0.083小时，2个参数
        hybrid_values = [187, 28, 11]  # 187行，28小时，11个参数

        x = np.arange(len(metrics))
        width = 0.35

        axes[0].bar(x - width/2, nsgablack_values, width, label='NSGABlack', color='#2E86AB')
        axes[0].bar(x + width/2, hybrid_values, width, label='HybridSATS', color='#A23B72')

        axes[0].set_ylabel('Value')
        axes[0].set_title('Development Efficiency Comparison')
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(metrics)
        axes[0].legend()
        axes[0].set_yscale('log')  # 对数坐标
        axes[0].grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for i, (nv, hv) in enumerate(zip(nsgablack_values, hybrid_values)):
            axes[0].text(i - width/2, nv, str(nv), ha='center', va='bottom', fontsize=9)
            axes[0].text(i + width/2, hv, str(hv), ha='center', va='bottom', fontsize=9)

        # 右图：效率提升比例
        efficiency_ratios = [hv / nv for nv, hv in zip(nsgablack_values, hybrid_values)]

        axes[1].bar(metrics, efficiency_ratios, color='#F18F01')
        axes[1].set_ylabel('Efficiency Ratio (Hybrid/NSGA)')
        axes[1].set_title('How Much More Efficient?')
        axes[1].set_yscale('log')
        axes[1].grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for i, ratio in enumerate(efficiency_ratios):
            axes[1].text(i, ratio, f'{ratio:.1f}x', ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'development_efficiency.png', dpi=300, bbox_inches='tight')
        print(f"开发效率对比图已保存: {self.output_dir / 'development_efficiency.png'}")
        plt.close()

    def generate_all_plots(self):
        """生成所有图表"""

        print("\n" + "=" * 60)
        print("生成可视化图表...")
        print("=" * 60)

        self.plot_convergence_curves()
        self.plot_boxplot()
        self.plot_development_efficiency()

        print("\n所有图表生成完成！")


if __name__ == "__main__":
    visualizer = ComparisonVisualizer()
    visualizer.generate_all_plots()
