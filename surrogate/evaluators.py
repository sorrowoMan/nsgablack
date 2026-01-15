"""
代理模型评估器

提供各种评估代理模型性能的工具和指标。
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    mean_squared_error, r2_score, mean_absolute_error,
    explained_variance_score
)
from ..core.base import BlackBoxProblem
from .utils import get_problem_bounds, get_num_objectives


class SurrogateEvaluator:
    """代理模型评估器"""

    def __init__(self, problem: BlackBoxProblem, **kwargs):
        """
        初始化评估器

        Args:
            problem: 优化问题
            **kwargs: 额外参数
        """
        self.problem = problem
        self.evaluation_results = {}

    def evaluate_accuracy(
        self,
        surrogate,
        test_X: np.ndarray,
        test_y: Optional[np.ndarray] = None,
        n_samples: int = 100
    ) -> Dict[str, float]:
        """

        评估代理模型的准确性

        Args:
            surrogate: 代理模型
            test_X: 测试输入
            test_y: 测试目标值（可选）
            n_samples: 如果没有测试数据，生成的样本数

        Returns:
            评估指标
        """
        lower_bounds, upper_bounds = get_problem_bounds(self.problem)
        n_objectives = get_num_objectives(self.problem)

        # 如果没有测试数据，生成随机测试集
        if test_y is None:
            test_X = np.random.uniform(
                lower_bounds,
                upper_bounds,
                (n_samples, len(lower_bounds))
            )
            test_y = np.array([self.problem.evaluate(x) for x in test_X])

        # 预测
        predictions = surrogate.predict(test_X)

        # 计算指标
        metrics = {}

        if n_objectives == 1:
            # 单目标
            metrics['mse'] = mean_squared_error(test_y, predictions)
            metrics['rmse'] = np.sqrt(metrics['mse'])
            metrics['mae'] = mean_absolute_error(test_y, predictions)
            metrics['r2'] = r2_score(test_y, predictions)
            metrics['explained_variance'] = explained_variance_score(test_y, predictions)
        else:
            # 多目标：计算每个目标的指标
            for i in range(n_objectives):
                prefix = f'obj_{i}_'
                metrics[f'{prefix}mse'] = mean_squared_error(test_y[:, i], predictions[:, i])
                metrics[f'{prefix}rmse'] = np.sqrt(metrics[f'{prefix}mse'])
                metrics[f'{prefix}mae'] = mean_absolute_error(test_y[:, i], predictions[:, i])
                metrics[f'{prefix}r2'] = r2_score(test_y[:, i], predictions[:, i])

        self.evaluation_results['accuracy'] = metrics
        return metrics

    def evaluate_efficiency(
        self,
        surrogate,
        n_evaluations: int = 100,
        time_budget: Optional[float] = None
    ) -> Dict[str, float]:
        """

        评估代理模型的效率

        Args:
            surrogate: 代理模型
            n_evaluations: 评估次数
            time_budget: 时间预算（秒）

        Returns:
            效率指标
        """
        lower_bounds, upper_bounds = get_problem_bounds(self.problem)
        n_objectives = get_num_objectives(self.problem)

        import time

        # 生成随机测试点
        test_X = np.random.uniform(
            lower_bounds,
            upper_bounds,
            (n_evaluations, len(lower_bounds))
        )

        # 评估代理模型速度
        start_time = time.time()
        for x in test_X:
            surrogate.predict(x.reshape(1, -1))
        surrogate_time = time.time() - start_time

        # 评估真实函数速度（仅部分，避免太慢）
        n_true_eval = min(10, n_evaluations)
        start_time = time.time()
        for x in test_X[:n_true_eval]:
            self.problem.evaluate(x)
        true_time = time.time() - start_time
        true_time_per_eval = true_time / n_true_eval
        estimated_true_time = true_time_per_eval * n_evaluations

        metrics = {
            'surrogate_time': surrogate_time,
            'surrogate_time_per_eval': surrogate_time / n_evaluations,
            'true_estimated_time': estimated_true_time,
            'true_time_per_eval': true_time_per_eval,
            'speedup_ratio': estimated_true_time / surrogate_time,
            'evaluations_per_second': n_evaluations / surrogate_time
        }

        self.evaluation_results['efficiency'] = metrics
        return metrics

    def evaluate_convergence(
        self,
        surrogate,
        initial_samples: int = 20,
        max_samples: int = 200,
        sample_step: int = 20
    ) -> Dict[str, Any]:
        """

        评估代理模型的收敛性

        Args:
            surrogate: 代理模型
            initial_samples: 初始样本数
            max_samples: 最大样本数
            sample_step: 采样步长

        Returns:
            收敛性分析结果
        """
        lower_bounds, upper_bounds = get_problem_bounds(self.problem)
        n_objectives = get_num_objectives(self.problem)

        # 生成训练数据
        train_X = []
        train_y = []

        # 初始样本
        for _ in range(initial_samples):
            x = np.random.uniform(
                lower_bounds,
                upper_bounds,
                len(lower_bounds)
            )
            y = self.problem.evaluate(x)
            train_X.append(x)
            train_y.append(y)

        convergence_data = {
            'sample_counts': [],
            'errors': [],
            'r2_scores': []
        }

        # 逐步增加训练样本
        for n_samples in range(initial_samples, max_samples + 1, sample_step):
            # 添加新样本
            while len(train_X) < n_samples:
                x = np.random.uniform(
                    lower_bounds,
                    upper_bounds,
                    len(lower_bounds)
                )
                y = self.problem.evaluate(x)
                train_X.append(x)
                train_y.append(y)

            # 训练代理模型
            surrogate.fit(np.array(train_X[:n_samples]), np.array(train_y[:n_samples]))

            # 评估性能
            test_X = np.random.uniform(
                lower_bounds,
                upper_bounds,
                (50, len(lower_bounds))
            )
            test_y = np.array([self.problem.evaluate(x) for x in test_X])
            pred_y = surrogate.predict(test_X)

            # 计算指标
            if n_objectives == 1:
                error = mean_squared_error(test_y, pred_y)
                r2 = r2_score(test_y, pred_y)
            else:
                error = mean_squared_error(test_y.flatten(), pred_y.flatten())
                r2 = r2_score(test_y.flatten(), pred_y.flatten())

            convergence_data['sample_counts'].append(n_samples)
            convergence_data['errors'].append(error)
            convergence_data['r2_scores'].append(r2)

        self.evaluation_results['convergence'] = convergence_data
        return convergence_data

    def evaluate_sampling_strategy(
        self,
        surrogate,
        strategies: List[str],
        n_iterations: int = 100,
        samples_per_iteration: int = 10
    ) -> Dict[str, Any]:
        """

        评估不同的采样策略

        Args:
            surrogate: 代理模型
            strategies: 策略列表
            n_iterations: 迭代次数
            samples_per_iteration: 每次迭代采样数

        Returns:
            策略比较结果
        """
        lower_bounds, upper_bounds = get_problem_bounds(self.problem)
        n_objectives = get_num_objectives(self.problem)

        from .strategies import SurrogateStrategyFactory

        results = {}

        for strategy_name in strategies:
            # 创建策略
            strategy = SurrogateStrategyFactory.create_strategy(
                strategy_name,
                surrogate
            )

            # 初始化
            train_X = []
            train_y = []

            # 初始样本
            for _ in range(20):
                x = np.random.uniform(
                    lower_bounds,
                    upper_bounds,
                    len(lower_bounds)
                )
                y = self.problem.evaluate(x)
                train_X.append(x)
                train_y.append(y)

            surrogate.fit(np.array(train_X), np.array(train_y))

            # 迭代评估
            errors = []
            true_evaluations = []

            for _ in range(n_iterations):
                # 生成候选解
                candidates = np.random.uniform(
                    lower_bounds,
                    upper_bounds,
                    (100, len(lower_bounds))
                )

                # 选择样本
                selected = strategy.select_next_samples(
                    candidates,
                    samples_per_iteration
                )

                # 评估选中的样本
                for x in selected:
                    y = self.problem.evaluate(x)
                    train_X.append(x)
                    train_y.append(y)
                    true_evaluations.append(1)

                # 更新模型
                surrogate.fit(np.array(train_X), np.array(train_y))

                # 评估当前模型
                test_X = np.random.uniform(
                    lower_bounds,
                    upper_bounds,
                    (30, len(lower_bounds))
                )
                test_y = np.array([self.problem.evaluate(x) for x in test_X])
                pred_y = surrogate.predict(test_X)

                if n_objectives == 1:
                    error = mean_squared_error(test_y, pred_y)
                else:
                    error = mean_squared_error(test_y.flatten(), pred_y.flatten())

                errors.append(error)

            results[strategy_name] = {
                'final_error': errors[-1],
                'errors': errors,
                'total_true_evaluations': sum(true_evaluations)
            }

        self.evaluation_results['sampling_strategies'] = results
        return results

    def plot_convergence(self, save_path: Optional[str] = None):
        """绘制收敛曲线"""
        if 'convergence' not in self.evaluation_results:
            print("请先运行收敛性评估")
            return

        data = self.evaluation_results['convergence']

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # 误差曲线
        ax1.plot(data['sample_counts'], data['errors'], 'bo-')
        ax1.set_xlabel('训练样本数')
        ax1.set_ylabel('MSE')
        ax1.set_title('代理模型误差收敛')
        ax1.grid(True)

        # R²分数曲线
        ax2.plot(data['sample_counts'], data['r2_scores'], 'ro-')
        ax2.set_xlabel('训练样本数')
        ax2.set_ylabel('R²')
        ax2.set_title('代理模型R²收敛')
        ax2.grid(True)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def plot_strategy_comparison(self, save_path: Optional[str] = None):
        """绘制策略比较图"""
        if 'sampling_strategies' not in self.evaluation_results:
            print("请先运行采样策略评估")
            return

        results = self.evaluation_results['sampling_strategies']

        plt.figure(figsize=(10, 6))

        for strategy_name, data in results.items():
            plt.plot(data['errors'], label=strategy_name)

        plt.xlabel('迭代次数')
        plt.ylabel('MSE')
        plt.title('不同采样策略的性能比较')
        plt.legend()
        plt.grid(True)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()

    def generate_report(self) -> str:
        """
        生成评估报告

        Returns:
            报告文本
        """
        report = []
        report.append("=== 代理模型评估报告 ===\n")

        # 准确性报告
        if 'accuracy' in self.evaluation_results:
            report.append("1. 准确性评估")
            report.append("-" * 30)
            acc = self.evaluation_results['accuracy']
            for metric, value in acc.items():
                report.append(f"{metric}: {value:.4f}")
            report.append("")

        # 效率报告
        if 'efficiency' in self.evaluation_results:
            report.append("2. 效率评估")
            report.append("-" * 30)
            eff = self.evaluation_results['efficiency']
            report.append(f"代理模型评估速度: {eff['evaluations_per_second']:.2f} 次/秒")
            report.append(f"加速比: {eff['speedup_ratio']:.2f}x")
            report.append("")

        # 采样策略报告
        if 'sampling_strategies' in self.evaluation_results:
            report.append("3. 采样策略比较")
            report.append("-" * 30)
            strategies = self.evaluation_results['sampling_strategies']
            report.append("策略\t\t最终误差\t真实评估次数")
            for name, data in strategies.items():
                report.append(f"{name:<15}\t{data['final_error']:.4f}\t\t{data['total_true_evaluations']}")
            report.append("")

        # 总结
        report.append("4. 总结")
        report.append("-" * 30)
        if 'accuracy' in self.evaluation_results:
            avg_r2 = np.mean([v for k, v in acc.items() if 'r2' in k])
            if avg_r2 > 0.8:
                report.append("代理模型性能：优秀")
            elif avg_r2 > 0.6:
                report.append("代理模型性能：良好")
            else:
                report.append("代理模型性能：需要改进")

        if 'efficiency' in self.evaluation_results:
            if eff['speedup_ratio'] > 10:
                report.append("效率提升：显著")
            elif eff['speedup_ratio'] > 2:
                report.append("效率提升：中等")
            else:
                report.append("效率提升：有限")

        return "\n".join(report)
