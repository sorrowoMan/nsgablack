"""
偏置效果分析框架模块

该模块提供全面的偏置效果量化分析能力，用于：
- 客观评估偏置对优化性能的实际贡献
- 多维度性能指标分析和跟踪
- 偏置有效性的科学量化方法
- 支持元学习系统的数据基础

分析框架能够：
1. 量化偏置对收敛速度、解质量、多样性等方面的影响
2. 计算偏置引入的计算开销和资源消耗
3. 评估偏置在不同问题上的稳定性和一致性
4. 生成详细的性能报告和可视化分析

该框架是偏置系统智能化的基础，为自动偏置选择和参数调优
提供客观数据支持。
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
import logging
from enum import Enum

from ..core.base import AlgorithmicBias, DomainBias


class MetricType(Enum):
    """
    评估指标类型枚举

    定义偏置效果评估中使用的各类指标，用于从不同角度
    量化分析偏置对优化过程的影响。
    """
    CONVERGENCE_SPEED = "convergence_speed"           # 收敛速度指标
    SOLUTION_QUALITY = "solution_quality"            # 解质量指标
    DIVERSITY_MAINTENANCE = "diversity_maintenance"  # 多样性维护指标
    COMPUTATIONAL_OVERHEAD = "computational_overhead" # 计算开销指标
    ROBUSTNESS = "robustness"                        # 稳定性指标
    CONSISTENCY = "consistency"                      # 一致性指标


@dataclass
class BiasEffectivenessMetrics:
    """
    偏置效果指标数据类

    封装单个偏置在多个维度上的量化评估结果，
    提供全面的偏置性能分析数据。

    Attributes:
        bias_name: 偏置名称
        bias_type: 偏置类型 ('algorithmic' 或 'domain')
        convergence_improvement: 收敛速度提升百分比（相对于无偏置基线）
        solution_quality_boost: 解质量提升百分比（相对于无偏置基线）
        diversity_score: 多样性维护得分 (0-1，越高越好)
        computational_overhead: 计算开销百分比（相对于无偏置基线）
        memory_usage: 内存使用百分比（相对于无偏置基线）
        robustness_score: 稳定性得分 (0-1，衡量在不同运行中的一致性)
        consistency_score: 一致性得分 (0-1，衡量在不同问题上的一致性)
        performance_history: 性能历史记录（用于趋势分析）
    """
    bias_name: str                                    # 偏置名称
    bias_type: str                                    # 偏置类型 ('algorithmic' or 'domain')

    # 核心性能指标（相对于无偏置基线的提升）
    convergence_improvement: float = 0.0              # 收敛速度提升百分比
    solution_quality_boost: float = 0.0               # 解质量提升百分比
    diversity_score: float = 0.0                      # 多样性维护得分 (0-1)

    # 计算成本指标（相对于无偏置基线的开销）
    computational_overhead: float = 0.0               # 计算开销百分比
    memory_usage: float = 0.0                         # 内存使用百分比

    # 稳定性指标（衡量偏置的可靠性）
    robustness_score: float = 0.0                     # 稳定性得分 (0-1)
    consistency_score: float = 0.0                    # 一致性得分 (0-1)

    # 时间序列数据（用于趋势分析和可视化）
    performance_history: List[float] = field(default_factory=list)

    # 统计显著性
    p_value: float = 1.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)


class BiasEffectivenessAnalyzer:
    """偏置效果分析器"""

    def __init__(self, baseline_runs: int = 10, significance_level: float = 0.05):
        """
        Args:
            baseline_runs: 基线运行次数（无偏置）
            significance_level: 显著性水平
        """
        self.baseline_runs = baseline_runs
        self.significance_level = significance_level
        self.bias_metrics: Dict[str, BiasEffectivenessMetrics] = {}
        self.run_data: List[Dict] = []

        # 评估配置
        self.evaluation_config = {
            'max_generations': 1000,
            'convergence_threshold': 1e-6,
            'diversity_window': 50,
            'overhead_threshold': 0.1  # 10%开销阈值
        }

        self.logger = logging.getLogger(__name__)

    def evaluate_bias(self, bias_name: str, bias_type: str,
                     biased_runs: List[Dict], baseline_runs: List[Dict]) -> BiasEffectivenessMetrics:
        """
        评估单个偏置的效果

        Args:
            bias_name: 偏置名称
            bias_type: 偏置类型 ('algorithmic' or 'domain')
            biased_runs: 使用偏置的运行结果
            baseline_runs: 基线运行结果（无偏置）
        """
        metrics = BiasEffectivenessMetrics(bias_name=bias_name, bias_type=bias_type)

        # 1. 计算收敛速度改进
        metrics.convergence_improvement = self._compute_convergence_improvement(
            biased_runs, baseline_runs)

        # 2. 计算解质量提升
        metrics.solution_quality_boost = self._compute_solution_quality_improvement(
            biased_runs, baseline_runs)

        # 3. 计算多样性维护得分
        metrics.diversity_score = self._compute_diversity_score(biased_runs)

        # 4. 计算计算开销
        metrics.computational_overhead = self._compute_computational_overhead(
            biased_runs, baseline_runs)

        # 5. 计算稳定性得分
        metrics.robustness_score = self._compute_robustness_score(biased_runs)

        # 6. 计算一致性得分
        metrics.consistency_score = self._compute_consistency_score(biased_runs)

        # 7. 计算统计显著性
        metrics.p_value, metrics.confidence_interval = self._compute_statistical_significance(
            biased_runs, baseline_runs)

        # 8. 记录性能历史
        metrics.performance_history = self._extract_performance_history(biased_runs)

        self.bias_metrics[bias_name] = metrics
        return metrics

    def _compute_convergence_improvement(self, biased_runs: List[Dict],
                                       baseline_runs: List[Dict]) -> float:
        """计算收敛速度改进百分比"""
        biased_generations = []
        baseline_generations = []

        for run in biased_runs:
            gen_to_converge = self._find_convergence_generation(run)
            if gen_to_converge is not None:
                biased_generations.append(gen_to_converge)

        for run in baseline_runs:
            gen_to_converge = self._find_convergence_generation(run)
            if gen_to_converge is not None:
                baseline_generations.append(gen_to_converge)

        if not biased_generations or not baseline_generations:
            return 0.0

        avg_biased = np.mean(biased_generations)
        avg_baseline = np.mean(baseline_generations)

        # 改进百分比：(baseline - biased) / baseline
        improvement = (avg_baseline - avg_biased) / avg_baseline * 100
        return improvement

    def _compute_solution_quality_improvement(self, biased_runs: List[Dict],
                                            baseline_runs: List[Dict]) -> float:
        """计算解质量提升百分比"""
        biased_best = []
        baseline_best = []

        for run in biased_runs:
            best_fitness = min(run.get('fitness_history', []))
            biased_best.append(best_fitness)

        for run in baseline_runs:
            best_fitness = min(run.get('fitness_history', []))
            baseline_best.append(best_fitness)

        if not biased_best or not baseline_best:
            return 0.0

        avg_biased = np.mean(biased_best)
        avg_baseline = np.mean(baseline_best)

        # 对于最小化问题，改进为负值，我们取绝对值并转换为正的百分比
        if avg_baseline != 0:
            improvement = (avg_baseline - avg_biased) / abs(avg_baseline) * 100
        else:
            improvement = 0.0

        return improvement

    def _compute_diversity_score(self, biased_runs: List[Dict]) -> float:
        """计算多样性维护得分 (0-1)"""
        diversity_scores = []

        for run in biased_runs:
            diversity_history = run.get('diversity_history', [])
            if diversity_history:
                # 计算平均多样性和多样性保持率
                avg_diversity = np.mean(diversity_history)
                final_diversity = diversity_history[-1] if diversity_history else 0
                initial_diversity = diversity_history[0] if diversity_history else 0

                # 多样性得分考虑平均值和保持程度
                if initial_diversity > 0:
                    retention_rate = final_diversity / initial_diversity
                else:
                    retention_rate = 0

                score = (avg_diversity + retention_rate) / 2
                diversity_scores.append(score)

        return np.mean(diversity_scores) if diversity_scores else 0.0

    def _compute_computational_overhead(self, biased_runs: List[Dict],
                                      baseline_runs: List[Dict]) -> float:
        """计算计算开销百分比"""
        biased_times = []
        baseline_times = []

        for run in biased_runs:
            biased_times.append(run.get('computation_time', 0))

        for run in baseline_runs:
            baseline_times.append(run.get('computation_time', 0))

        if not biased_times or not baseline_times:
            return 0.0

        avg_biased = np.mean(biased_times)
        avg_baseline = np.mean(baseline_times)

        if avg_baseline > 0:
            overhead = (avg_biased - avg_baseline) / avg_baseline * 100
        else:
            overhead = 0.0

        return overhead

    def _compute_robustness_score(self, biased_runs: List[Dict]) -> float:
        """计算稳定性得分 (0-1)"""
        if len(biased_runs) < 2:
            return 0.0

        # 计算最终解的方差
        final_fitnesses = []
        for run in biased_runs:
            fitness_history = run.get('fitness_history', [])
            if fitness_history:
                final_fitnesses.append(fitness_history[-1])

        if len(final_fitnesses) < 2:
            return 0.0

        # 标准化方差：方差越小，稳定性越高
        variance = np.var(final_fitnesses)
        mean_fitness = np.mean(final_fitnesses)

        if mean_fitness != 0:
            cv = np.sqrt(variance) / abs(mean_fitness)  # 变异系数
            robustness = 1 / (1 + cv)  # 转换为0-1得分
        else:
            robustness = 1.0 if variance == 0 else 0.0

        return robustness

    def _compute_consistency_score(self, biased_runs: List[Dict]) -> float:
        """计算一致性得分 (0-1)"""
        if len(biased_runs) < 2:
            return 0.0

        # 计算收敛轨迹的相似性
        similarity_scores = []

        for i in range(len(biased_runs)):
            for j in range(i + 1, len(biased_runs)):
                hist1 = biased_runs[i].get('fitness_history', [])
                hist2 = biased_runs[j].get('fitness_history', [])

                if len(hist1) > 0 and len(hist2) > 0:
                    # 计算相关系数
                    min_len = min(len(hist1), len(hist2))
                    corr = np.corrcoef(hist1[:min_len], hist2[:min_len])[0, 1]
                    if not np.isnan(corr):
                        similarity_scores.append(abs(corr))

        return np.mean(similarity_scores) if similarity_scores else 0.0

    def _compute_statistical_significance(self, biased_runs: List[Dict],
                                        baseline_runs: List[Dict]) -> Tuple[float, Tuple[float, float]]:
        """计算统计显著性和置信区间"""
        # 提取最终性能数据
        biased_final = [run.get('fitness_history', [])[-1]
                       for run in biased_runs if run.get('fitness_history')]
        baseline_final = [run.get('fitness_history', [])[-1]
                         for run in baseline_runs if run.get('fitness_history')]

        if len(biased_final) < 3 or len(baseline_final) < 3:
            return 1.0, (0.0, 0.0)  # 样本不足，无法计算

        # 简化的t检验（实际应使用scipy.stats）
        mean_biased = np.mean(biased_final)
        mean_baseline = np.mean(baseline_final)
        std_biased = np.std(biased_final, ddof=1)
        std_baseline = np.std(baseline_final, ddof=1)

        n_biased = len(biased_final)
        n_baseline = len(baseline_final)

        # 计算标准误差
        se = np.sqrt((std_biased**2 / n_biased) + (std_baseline**2 / n_baseline))

        # 计算t统计量
        if se > 0:
            t_stat = abs(mean_biased - mean_baseline) / se
            # 简化的p值计算（实际应查t分布表）
            p_value = 2 * (1 - self._normal_cdf(t_stat))
        else:
            p_value = 1.0

        # 计算95%置信区间
        margin_error = 1.96 * se
        confidence_interval = (mean_biased - margin_error, mean_biased + margin_error)

        return p_value, confidence_interval

    def _normal_cdf(self, x):
        """标准正态分布的累积分布函数（近似）"""
        return 0.5 * (1 + np.tanh(np.sqrt(2/np.pi) * (x + 0.044715 * x**3)))

    def _find_convergence_generation(self, run: Dict) -> Optional[int]:
        """找到收敛的代数"""
        fitness_history = run.get('fitness_history', [])
        if not fitness_history:
            return None

        threshold = self.evaluation_config['convergence_threshold']

        # 简单的收敛检测：连续N代改进小于阈值
        window_size = 20
        for i in range(window_size, len(fitness_history)):
            window = fitness_history[i-window_size:i]
            if max(window) - min(window) < threshold:
                return i

        return len(fitness_history) - 1  # 未完全收敛，返回最后一代

    def _extract_performance_history(self, biased_runs: List[Dict]) -> List[float]:
        """提取平均性能历史"""
        if not biased_runs:
            return []

        # 找到最短的运行历史
        min_length = min(len(run.get('fitness_history', [])) for run in biased_runs)

        if min_length == 0:
            return []

        # 计算每代的平均性能
        avg_history = []
        for gen in range(min_length):
            gen_values = [run.get('fitness_history', [])[gen] for run in biased_runs
                         if gen < len(run.get('fitness_history', []))]
            if gen_values:
                avg_history.append(np.mean(gen_values))

        return avg_history

    def generate_report(self, output_file: str = None) -> Dict[str, Any]:
        """生成偏置效果报告"""
        report = {
            'summary': self._generate_summary(),
            'detailed_metrics': {},
            'recommendations': self._generate_recommendations(),
            'timestamp': pd.Timestamp.now().isoformat()
        }

        for bias_name, metrics in self.bias_metrics.items():
            report['detailed_metrics'][bias_name] = {
                'bias_type': metrics.bias_type,
                'convergence_improvement': metrics.convergence_improvement,
                'solution_quality_boost': metrics.solution_quality_boost,
                'diversity_score': metrics.diversity_score,
                'computational_overhead': metrics.computational_overhead,
                'robustness_score': metrics.robustness_score,
                'consistency_score': metrics.consistency_score,
                'p_value': metrics.p_value,
                'is_significant': metrics.p_value < self.significance_level,
                'overall_score': self._compute_overall_score(metrics)
            }

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)

        return report

    def _generate_summary(self) -> Dict[str, Any]:
        """生成总结信息"""
        if not self.bias_metrics:
            return {'total_biases': 0, 'message': 'No bias metrics available'}

        # 按类型统计
        algorithmic_count = sum(1 for m in self.bias_metrics.values()
                              if m.bias_type == 'algorithmic')
        domain_count = sum(1 for m in self.bias_metrics.values()
                          if m.bias_type == 'domain')

        # 计算平均指标
        significant_biases = [m for m in self.bias_metrics.values()
                            if m.p_value < self.significance_level]

        return {
            'total_biases': len(self.bias_metrics),
            'algorithmic_biases': algorithmic_count,
            'domain_biases': domain_count,
            'significant_improvements': len(significant_biases),
            'avg_convergence_improvement': np.mean([m.convergence_improvement
                                                   for m in significant_biases]) if significant_biases else 0,
            'avg_quality_boost': np.mean([m.solution_quality_boost
                                        for m in significant_biases]) if significant_biases else 0,
            'avg_overhead': np.mean([m.computational_overhead
                                   for m in self.bias_metrics.values()])
        }

    def _generate_recommendations(self) -> List[str]:
        """生成改进建议"""
        recommendations = []

        if not self.bias_metrics:
            return ["No bias evaluation data available for recommendations."]

        # 分析高开销偏置
        high_overhead_biases = [name for name, m in self.bias_metrics.items()
                              if m.computational_overhead > self.evaluation_config['overhead_threshold'] * 100]
        if high_overhead_biases:
            recommendations.append(
                f"Consider optimizing high-overhead biases: {', '.join(high_overhead_biases)}"
            )

        # 分析无效偏置
        ineffective_biases = [name for name, m in self.bias_metrics.items()
                            if m.convergence_improvement < 0 and m.solution_quality_boost < 0]
        if ineffective_biases:
            recommendations.append(
                f"The following biases may be detrimental: {', '.join(ineffective_biases)}"
            )

        # 分析显著改进的偏置
        effective_biases = [(name, m.convergence_improvement + m.solution_quality_boost)
                           for name, m in self.bias_metrics.items()
                           if m.p_value < self.significance_level]
        if effective_biases:
            best_biases = sorted(effective_biases, key=lambda x: x[1], reverse=True)[:3]
            recommendations.append(
                f"Most effective biases: {', '.join([b[0] for b in best_biases])}"
            )

        # 多样性建议
        low_diversity_biases = [name for name, m in self.bias_metrics.items()
                              if m.diversity_score < 0.3]
        if low_diversity_biases:
            recommendations.append(
                f"Consider combining with diversity-enhancing biases for: {', '.join(low_diversity_biases)}"
            )

        return recommendations

    def _compute_overall_score(self, metrics: BiasEffectivenessMetrics) -> float:
        """计算综合得分 (0-100)"""
        # 权重配置
        weights = {
            'convergence': 0.3,
            'quality': 0.3,
            'diversity': 0.15,
            'robustness': 0.15,
            'consistency': 0.1
        }

        # 标准化各指标到0-1范围
        convergence_score = min(max(metrics.convergence_improvement / 100, 0), 1)
        quality_score = min(max(metrics.solution_quality_boost / 100, 0), 1)
        diversity_score = metrics.diversity_score
        robustness_score = metrics.robustness_score
        consistency_score = metrics.consistency_score

        # 扣除计算开销
        overhead_penalty = min(metrics.computational_overhead / 100, 0.2)

        overall = (weights['convergence'] * convergence_score +
                  weights['quality'] * quality_score +
                  weights['diversity'] * diversity_score +
                  weights['robustness'] * robustness_score +
                  weights['consistency'] * consistency_score)

        overall = max(overall - overhead_penalty, 0)
        return overall * 100

    def plot_bias_comparison(self, save_path: str = None):
        """绘制偏置效果对比图"""
        if not self.bias_metrics:
            print("No bias metrics available for plotting")
            return

        # 创建子图
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 偏置名称和类型
        names = list(self.bias_metrics.keys())
        types = [self.bias_metrics[name].bias_type for name in names]

        # 1. 收敛速度和解质量改进
        convergence_improvements = [self.bias_metrics[name].convergence_improvement for name in names]
        quality_improvements = [self.bias_metrics[name].solution_quality_boost for name in names]

        axes[0, 0].scatter(convergence_improvements, quality_improvements, alpha=0.7)
        axes[0, 0].set_xlabel('Convergence Improvement (%)')
        axes[0, 0].set_ylabel('Solution Quality Boost (%)')
        axes[0, 0].set_title('Convergence vs Quality Improvement')
        axes[0, 0].grid(True, alpha=0.3)

        # 添加标签
        for i, name in enumerate(names):
            axes[0, 0].annotate(name, (convergence_improvements[i], quality_improvements[i]),
                              fontsize=8, alpha=0.7)

        # 2. 多样性和开销
        diversity_scores = [self.bias_metrics[name].diversity_score for name in names]
        overheads = [self.bias_metrics[name].computational_overhead for name in names]

        axes[0, 1].scatter(diversity_scores, overheads, alpha=0.7)
        axes[0, 1].set_xlabel('Diversity Score')
        axes[0, 1].set_ylabel('Computational Overhead (%)')
        axes[0, 1].set_title('Diversity vs Overhead')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 稳定性和一致性
        robustness_scores = [self.bias_metrics[name].robustness_score for name in names]
        consistency_scores = [self.bias_metrics[name].consistency_score for name in names]

        axes[1, 0].scatter(robustness_scores, consistency_scores, alpha=0.7)
        axes[1, 0].set_xlabel('Robustness Score')
        axes[1, 0].set_ylabel('Consistency Score')
        axes[1, 0].set_title('Robustness vs Consistency')
        axes[1, 0].grid(True, alpha=0.3)

        # 4. 综合得分
        overall_scores = [self._compute_overall_score(self.bias_metrics[name]) for name in names]
        colors = ['red' if t == 'domain' else 'blue' for t in types]

        bars = axes[1, 1].bar(names, overall_scores, color=colors, alpha=0.7)
        axes[1, 1].set_ylabel('Overall Score')
        axes[1, 1].set_title('Overall Bias Effectiveness Score')
        axes[1, 1].tick_params(axis='x', rotation=45)

        # 添加图例
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor='blue', alpha=0.7, label='Algorithmic'),
                          Patch(facecolor='red', alpha=0.7, label='Domain')]
        axes[1, 1].legend(handles=legend_elements)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        plt.show()

    def export_metrics_to_csv(self, filename: str):
        """导出指标到CSV文件"""
        data = []
        for bias_name, metrics in self.bias_metrics.items():
            data.append({
                'bias_name': bias_name,
                'bias_type': metrics.bias_type,
                'convergence_improvement': metrics.convergence_improvement,
                'solution_quality_boost': metrics.solution_quality_boost,
                'diversity_score': metrics.diversity_score,
                'computational_overhead': metrics.computational_overhead,
                'robustness_score': metrics.robustness_score,
                'consistency_score': metrics.consistency_score,
                'p_value': metrics.p_value,
                'overall_score': self._compute_overall_score(metrics)
            })

        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        self.logger.info(f"Metrics exported to {filename}")