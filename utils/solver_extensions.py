"""求解器扩展模块

为现有求解器添加并行评估和其他增强功能，设计为混入类(Mixin)模式，
可以轻松集成到现有求解器中而不需要大幅修改原有代码。
"""

from __future__ import annotations

import warnings
from typing import Optional, Dict, Any, Literal

import numpy as np

try:
    # 当作为包导入时使用相对导入
    from .parallel_evaluator import ParallelEvaluator, SmartEvaluatorSelector
    from ..core.base import BlackBoxProblem
    from ..utils.bias import BiasModule
except ImportError:
    # 当作为脚本运行时使用绝对导入
    from utils.parallel_evaluator import ParallelEvaluator, SmartEvaluatorSelector
    from core.base import BlackBoxProblem
    from bias import BiasModule


class ParallelEvaluationMixin:
    """并行评估混入类

    为求解器添加并行评估功能。这个混入类可以被任何求解器继承或组合使用。

    使用方式：
    1. 继承：class MySolver(ParallelEvaluationMixin, BaseSolver)
    2. 组合：直接在现有求解器中混入这些方法
    """

    def __init__(self, *args, **kwargs):
        """初始化并行评估功能

        注意：这个初始化需要与原有求解器的__init__兼容。
        """
        # 调用父类的__init__
        super().__init__(*args, **kwargs)

        # 并行评估相关属性
        self.enable_parallel_evaluation = False
        self.parallel_evaluator: Optional[ParallelEvaluator] = None
        self.parallel_config = {
            'backend': 'process',
            'max_workers': None,
            'chunk_size': None,
            'enable_load_balancing': True,
            'retry_errors': True,
            'verbose': False
        }

    def enable_parallel(
        self,
        backend: Literal["process", "thread", "joblib"] = "process",
        max_workers: Optional[int] = None,
        auto_configure: bool = True,
        **parallel_kwargs
    ):
        """启用并行评估

        Args:
            backend: 并行后端
            max_workers: 最大工作进程数
            auto_configure: 是否自动配置最佳参数
            **parallel_kwargs: 传递给ParallelEvaluator的额外参数
        """
        self.enable_parallel_evaluation = True
        self.parallel_config.update({
            'backend': backend,
            'max_workers': max_workers,
            **parallel_kwargs
        })

        if auto_configure and hasattr(self, 'problem') and hasattr(self, 'pop_size'):
            # 智能自动配置
            if max_workers is None:
                # 根据种群大小和问题特性自动选择
                self.parallel_evaluator = SmartEvaluatorSelector.select_evaluator(
                    self.problem, self.pop_size
                )
            else:
                self.parallel_evaluator = ParallelEvaluator(
                    backend=backend,
                    max_workers=max_workers,
                    **parallel_kwargs
                )
        else:
            self.parallel_evaluator = ParallelEvaluator(
                backend=backend,
                max_workers=max_workers,
                **parallel_kwargs
            )

        if hasattr(self, 'verbose') and self.verbose:
            print(f"并行评估已启用，后端: {backend}, 工作进程: {max_workers or 'auto'}")

    def disable_parallel(self):
        """禁用并行评估"""
        self.enable_parallel_evaluation = False
        if self.parallel_evaluator:
            self.parallel_evaluator.reset_stats()
        self.parallel_evaluator = None

    def evaluate_population_parallel(
        self,
        population: np.ndarray,
        return_detailed: bool = False
    ) -> Any:
        """并行评估整个种群

        这个方法会替换原有的evaluate_population方法。

        Args:
            population: 待评估的种群
            return_detailed: 是否返回详细信息

        Returns:
            评估结果
        """
        if not self.enable_parallel_evaluation or self.parallel_evaluator is None:
            # 回退到原有的串行评估
            return self._evaluate_population_serial(population)

        # 确保有problem实例
        if not hasattr(self, 'problem') or self.problem is None:
            raise ValueError("Problem instance is required for parallel evaluation")

        # 执行并行评估
        return self.parallel_evaluator.evaluate_population(
            population=population,
            problem=self.problem,
            enable_bias=getattr(self, 'enable_bias', False),
            bias_module=getattr(self, 'bias_module', None),
            return_detailed=return_detailed
        )

    def _evaluate_population_serial(self, population: np.ndarray) -> Any:
        """串行评估（回退方案）"""
        # 调用原有的evaluate_population方法
        if hasattr(super(), 'evaluate_population'):
            return super().evaluate_population(population)
        else:
            # 如果没有原有方法，提供基本实现
            raise NotImplementedError("Original evaluate_population method not found")

    def get_parallel_stats(self) -> Optional[Dict[str, Any]]:
        """获取并行评估的统计信息"""
        if self.parallel_evaluator:
            return self.parallel_evaluator.get_stats()
        return None

    def reset_parallel_stats(self):
        """重置并行评估统计"""
        if self.parallel_evaluator:
            self.parallel_evaluator.reset_stats()


class SolverEnhancementMixin:
    """求解器增强功能混入类

    提供各种求解器增强功能，如自动调参、性能监控等。
    """

    def __init__(self, *args, **kwargs):
        """初始化增强功能"""
        super().__init__(*args, **kwargs)

        # 性能监控
        self.performance_stats = {
            'total_evaluations': 0,
            'evaluation_times': [],
            'convergence_history': [],
            'best_fitness_history': []
        }

        # 自动配置
        self.auto_config = {
            'enable_adaptive_params': False,
            'enable_early_stopping': False,
            'enable_performance_monitoring': True
        }

    def enable_auto_configuration(
        self,
        adaptive_params: bool = True,
        early_stopping: bool = True,
        performance_monitoring: bool = True
    ):
        """启用自动配置功能"""
        self.auto_config.update({
            'enable_adaptive_params': adaptive_params,
            'enable_early_stopping': early_stopping,
            'enable_performance_monitoring': performance_monitoring
        })

    def monitor_performance(self, generation: int, best_fitness: float, evaluation_time: float):
        """监控性能指标"""
        if self.auto_config['enable_performance_monitoring']:
            self.performance_stats['total_evaluations'] += getattr(self, 'pop_size', 0)
            self.performance_stats['evaluation_times'].append(evaluation_time)
            self.performance_stats['convergence_history'].append(generation)
            self.performance_stats['best_fitness_history'].append(best_fitness)

    def should_stop_early(self, patience: int = 20, tolerance: float = 1e-6) -> bool:
        """判断是否应该早停"""
        if not self.auto_config['enable_early_stopping']:
            return False

        if len(self.performance_stats['best_fitness_history']) < patience:
            return False

        recent_fitness = self.performance_stats['best_fitness_history'][-patience:]
        improvement = abs(recent_fitness[0] - recent_fitness[-1])

        return improvement < tolerance

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        stats = self.performance_stats.copy()

        if stats['evaluation_times']:
            stats.update({
                'avg_evaluation_time': np.mean(stats['evaluation_times']),
                'total_time': np.sum(stats['evaluation_times']),
                'evaluations_per_second': stats['total_evaluations'] / np.sum(stats['evaluation_times'])
            })

        if stats['best_fitness_history']:
            stats.update({
                'best_fitness': min(stats['best_fitness_history']),
                'convergence_rate': self._calculate_convergence_rate()
            })

        return stats

    def _calculate_convergence_rate(self) -> float:
        """计算收敛速率"""
        if len(self.performance_stats['best_fitness_history']) < 2:
            return 0.0

        fitness_history = self.performance_stats['best_fitness_history']
        # 计算改进率的绝对值的平均值
        improvements = []
        for i in range(1, len(fitness_history)):
            improvement = abs(fitness_history[i] - fitness_history[i-1])
            if improvement > 1e-12:  # 避免除零
                improvements.append(improvement)

        return np.mean(improvements) if improvements else 0.0


def integrate_parallel_evaluation(solver_class) -> type:
    """将并行评估功能集成到现有求解器类中

    这是一个装饰器函数，可以动态为求解器类添加并行评估功能。

    Args:
        solver_class: 要增强的求解器类

    Returns:
        增强后的求解器类
    """
    class EnhancedSolver(ParallelEvaluationMixin, SolverEnhancementMixin, solver_class):
        """增强版求解器，具有并行评估和其他增强功能"""

        def __init__(self, *args, **kwargs):
            # 提取并行相关参数
            parallel_kwargs = {}
            parallel_keys = ['enable_parallel', 'parallel_backend', 'max_workers', 'auto_configure']
            for key in list(kwargs.keys()):
                if key in parallel_keys:
                    parallel_kwargs[key] = kwargs.pop(key)

            # 初始化父类
            super().__init__(*args, **kwargs)

            # 配置并行评估
            if parallel_kwargs.get('enable_parallel', False):
                self.enable_parallel(
                    backend=parallel_kwargs.get('parallel_backend', 'process'),
                    max_workers=parallel_kwargs.get('max_workers', None),
                    auto_configure=parallel_kwargs.get('auto_configure', True)
                )

        # 重写evaluate_population方法以支持并行
        def evaluate_population(self, population, return_detailed=False):
            """评估种群，自动选择并行或串行"""
            if self.enable_parallel_evaluation and len(population) > 4:  # 小种群不值得并行
                return self.evaluate_population_parallel(population, return_detailed)
            else:
                return self._evaluate_population_serial(population)

        # 添加性能监控到原有的动画/迭代方法中
        def animate(self, frame=None):
            """重写动画方法，添加性能监控"""
            start_time = time.time()

            # 调用原有的动画方法
            result = super().animate(frame)

            # 监控性能
            evaluation_time = time.time() - start_time
            current_generation = getattr(self, 'generation', 0)

            if hasattr(self, 'pareto_solutions') and self.pareto_solutions:
                best_fitness = np.min(self.pareto_solutions['objectives'])
                self.monitor_performance(current_generation, float(best_fitness), evaluation_time)

            # 检查早停条件
            if self.should_stop_early():
                print(f"Early stopping at generation {current_generation}")
                return None

            return result

        def run(self, *args, **kwargs):
            """重写run方法，添加完整的性能监控"""
            import time

            start_time = time.time()

            # 预估性能改进
            if self.enable_parallel_evaluation and hasattr(self, 'pop_size'):
                estimated_speedup = self.parallel_evaluator.estimate_speedup(
                    self.pop_size,
                    avg_eval_time=0.001  # 假设平均1ms评估时间
                )
                if getattr(self, 'verbose', False):
                    print(f"预估并行加速比: {estimated_speedup:.2f}x")

            # 运行优化
            result = super().run(*args, **kwargs)

            # 添加性能报告
            total_time = time.time() - start_time
            performance_report = self.get_performance_report()

            if 'experiment' in result:
                result['experiment']['performance'] = performance_report
                result['experiment']['total_time'] = total_time
            else:
                result['performance'] = performance_report
                result['total_time'] = total_time

            # 输出并行统计
            if self.enable_parallel_evaluation:
                parallel_stats = self.get_parallel_stats()
                if parallel_stats and getattr(self, 'verbose', False):
                    print(f"并行评估统计:")
                    print(f"  总评估次数: {parallel_stats['total_evaluations']}")
                    print(f"  总评估时间: {parallel_stats['total_time']:.2f}s")
                    print(f"  平均评估时间: {parallel_stats['avg_evaluation_time']*1000:.2f}ms")
                    if parallel_stats['error_count'] > 0:
                        print(f"  错误次数: {parallel_stats['error_count']}")

            return result

    return EnhancedSolver


# 便捷函数
def create_parallel_solver(
    solver_class,
    problem,
    enable_parallel=True,
    parallel_backend="process",
    max_workers=None,
    **solver_kwargs
):
    """创建并行求解器的便捷函数"""

    # 动态创建增强的求解器类
    EnhancedSolver = integrate_parallel_evaluation(solver_class)

    # 创建实例
    solver = EnhancedSolver(problem, **solver_kwargs)

    # 启用并行评估
    if enable_parallel:
        solver.enable_parallel(
            backend=parallel_backend,
            max_workers=max_workers,
            auto_configure=True
        )

    return solver