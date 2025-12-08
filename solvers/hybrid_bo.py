"""
贝叶斯混合优化器 - Hybrid Bayesian Optimizers

将贝叶斯优化与其他优化策略结合，发挥各自优势。

主要功能：
- BO + NSGA-II 混合
- 自适应策略切换
- 并行评估支持
- 多阶段优化
"""

import numpy as np
from typing import Callable, List, Dict, Any, Optional, Tuple
from .bayesian_optimizer import BayesianOptimizer
from ..core.base import BlackBoxProblem
from ..core.solver import BlackBoxSolverNSGAII
import time


class HybridBO_NSGA:
    """
    贝叶斯-NSGA-II 混合求解器

    结合贝叶斯优化的全局探索能力和NSGA-II的群体搜索优势。
    """

    def __init__(self,
                 problem: BlackBoxProblem,
                 bo_ratio: float = 0.3,
                 crossover_ratio: float = 0.7,
                 adapt_strategy: bool = True):
        """
        初始化混合求解器

        Parameters:
        -----------
        problem : BlackBoxProblem
            优化问题
        bo_ratio : float
            贝叶斯优化阶段的比例 (0-1)
        crossover_ratio : float
            BO到NSGA的交叉比例
        adapt_strategy : bool
            是否自适应调整策略
        """
        self.problem = problem
        self.bo_ratio = bo_ratio
        self.crossover_ratio = crossover_ratio
        self.adapt_strategy = adapt_strategy

        # 初始化优化器
        self.bo_optimizer = BayesianOptimizer(
            acquisition='ei',
            kernel='matern'
        )

        self.nsga_solver = BlackBoxSolverNSGAII(problem)

        # 策略控制
        self.current_strategy = 'bo'
        self.strategy_switch_gen = 0

        # 性能监控
        self.performance_history = []
        self.best_history = []

    def run(self,
            total_budget: int = 300,
            verbose: bool = True) -> Dict[str, Any]:
        """
        运行混合优化

        Parameters:
        -----------
        total_budget : int
            总评估预算
        verbose : bool
            是否显示详细信息

        Returns:
        --------
        Dict : 优化结果
        """
        start_time = time.time()

        # 计算各阶段预算
        bo_budget = int(total_budget * self.bo_ratio)
        nsga_budget = total_budget - bo_budget

        # 阶段1：贝叶斯优化探索
        if verbose:
            print(f"\n阶段1: 贝叶斯优化 (预算: {bo_budget})")
            print("=" * 50)

        bo_result = self._run_bo_phase(bo_budget, verbose)

        # 阶段2：NSGA-II精化
        if verbose:
            print(f"\n阶段2: NSGA-II精化 (预算: {nsga_budget})")
            print("=" * 50)

        nsga_result = self._run_nsga_phase(nsga_budget, bo_result, verbose)

        # 合并结果
        final_result = self._merge_results(bo_result, nsga_result)

        # 计算运行时间
        total_time = time.time() - start_time

        final_result['total_time'] = total_time
        final_result['bo_result'] = bo_result
        final_result['nsga_result'] = nsga_result

        if verbose:
            print(f"\n混合优化完成!")
            print(f"总用时: {total_time:.2f}秒")
            print(f"最优值: {final_result['best_y']:.6f}")

        return final_result

    def _run_bo_phase(self, budget: int, verbose: bool) -> Dict[str, Any]:
        """运行贝叶斯优化阶段"""
        # 设置边界
        bounds = []
        for i in range(self.problem.dimension):
            bounds.append(self.problem.bounds[i])

        # 运行贝叶斯优化
        result = self.bo_optimizer.optimize(
            objective_func=self.problem.evaluate,
            bounds=bounds,
            budget=budget,
            callback=self._bo_callback if verbose else None
        )

        # 记录性能
        self.performance_history.extend(result['history']['y'])
        self.best_history.extend([result['best_y']] * len(result['history']['y']))

        return result

    def _run_nsga_phase(self,
                        budget: int,
                        bo_result: Dict,
                        verbose: bool) -> Dict[str, Any]:
        """运行NSGA-II阶段"""
        # 配置NSGA-II
        self.nsga_solver.pop_size = min(50, budget // 5)
        self.nsga_solver.max_generations = budget // self.nsga_solver.pop_size
        self.nsga_solver.enable_progress_log = verbose

        # 使用BO结果作为初始种群
        if 'best_x' in bo_result and bo_result['best_x'] is not None:
            # 将BO的最优解作为种子
            self._seed_nsga_with_bo_results(bo_result)

        # 运行NSGA-II
        result = self.nsga_solver.run()

        # 记录性能（NSGA-II的日志已包含在回调中）
        if 'pareto_solutions' in result:
            for obj in result['pareto_solutions']['objectives']:
                self.performance_history.append(obj[0])
                self.best_history.append(min(self.best_history + [obj[0]]))

        return result

    def _seed_nsga_with_bo_results(self, bo_result: Dict):
        """用BO结果初始化NSGA-II种群"""
        if hasattr(self.nsga_solver, 'population'):
            # 将BO的最优解加入到初始种群
            bo_best = bo_result['best_x']
            if len(self.nsga_solver.population) > 0:
                # 替换部分个体
                n_replace = min(len(self.nsga_solver.population) // 4, 10)
                for i in range(n_replace):
                    # 在最优解周围生成点
                    x_new = bo_best + np.random.normal(0, 0.1, len(bo_best))
                    # 确保在边界内
                    for j in range(len(x_new)):
                        low, high = self.problem.bounds[j]
                        x_new[j] = np.clip(x_new[j], low, high)
                    self.nsga_solver.population[i] = x_new

    def _merge_results(self,
                       bo_result: Dict,
                       nsga_result: Dict) -> Dict[str, Any]:
        """合并两个阶段的结果"""
        # 从BO和NSGA中找出最优解
        bo_best_y = bo_result.get('best_y', float('inf'))
        nsga_best_y = float('inf')

        if 'pareto_solutions' in nsga_result:
            nsga_objectives = nsga_result['pareto_solutions']['objectives']
            nsga_best_y = min([obj[0] for obj in nsga_objectives])

        # 选择更好的结果
        if bo_best_y < nsga_best_y:
            best_result = bo_result
            best_source = 'Bayesian Optimization'
        else:
            best_result = nsga_result
            best_source = 'NSGA-II'

        return {
            'best_x': best_result.get('best_x', None),
            'best_y': min(bo_best_y, nsga_best_y),
            'best_source': best_source,
            'performance_history': self.performance_history,
            'best_history': self.best_history
        }

    def _bo_callback(self, iteration, x, y, best_y):
        """BO阶段的回调函数"""
        if iteration % 10 == 0:
            print(f"  迭代 {iteration}: 当前={y:.6f}, 最优={best_y:.6f}")


class AdaptiveBOOptimizer:
    """
    自适应贝叶斯优化器

    根据优化进展自动调整策略。
    """

    def __init__(self,
                 problem: BlackBoxProblem,
                 initial_strategy: str = 'ei',
                 adaptation_frequency: int = 20):
        """
        初始化自适应优化器

        Parameters:
        -----------
        problem : BlackBoxProblem
            优化问题
        initial_strategy : str
            初始策略
        adaptation_frequency : int
            策略调整频率
        """
        self.problem = problem
        self.initial_strategy = initial_strategy
        self.adaptation_frequency = adaptation_frequency

        # 策略池
        self.strategies = ['ei', 'ucb', 'pi', 'kg']
        self.current_strategy = initial_strategy

        # 性能追踪
        self.strategy_performance = {s: [] for s in self.strategies}
        self.current_bo = None

    def run(self,
            budget: int = 200,
            verbose: bool = True) -> Dict[str, Any]:
        """运行自适应贝叶斯优化"""
        results = []
        current_budget = 0
        generation = 0

        while current_budget < budget:
            # 计算本阶段预算
            stage_budget = min(self.adaptation_frequency, budget - current_budget)

            # 运行当前策略
            if verbose:
                print(f"\n使用策略: {self.current_strategy} (预算: {stage_budget})")

            stage_result = self._run_strategy(stage_budget, verbose)
            results.append(stage_result)

            # 更新性能记录
            self._update_strategy_performance(self.current_strategy, stage_result)

            # 自适应调整策略
            if current_budget + stage_budget < budget:
                self.current_strategy = self._select_next_strategy()

            current_budget += stage_budget
            generation += 1

        # 合并结果
        return self._merge_adaptive_results(results)

    def _run_strategy(self, budget: int, verbose: bool) -> Dict:
        """运行指定策略"""
        bo = BayesianOptimizer(acquisition=self.current_strategy)
        self.current_bo = bo

        bounds = [self.problem.bounds[i] for i in range(self.problem.dimension)]

        result = bo.optimize(
            objective_func=self.problem.evaluate,
            bounds=bounds,
            budget=budget
        )

        return result

    def _update_strategy_performance(self, strategy: str, result: Dict):
        """更新策略性能记录"""
        if 'best_y' in result:
            improvement = result['best_y']
            self.strategy_performance[strategy].append(improvement)

    def _select_next_strategy(self) -> str:
        """选择下一个策略"""
        # 简单的性能比较策略
        strategy_scores = {}

        for strategy in self.strategies:
            if self.strategy_performance[strategy]:
                # 使用最近的性能
                recent_performance = self.strategy_performance[strategy][-5:]
                avg_performance = np.mean(recent_performance)
                strategy_scores[strategy] = avg_performance
            else:
                strategy_scores[strategy] = float('inf')

        # 选择性能最好的策略
        best_strategy = min(strategy_scores, key=strategy_scores.get)

        # 避免一直使用同一策略
        if best_strategy == self.current_strategy and len(strategy_scores) > 1:
            strategy_scores.pop(best_strategy)
            best_strategy = min(strategy_scores, key=strategy_scores.get)

        return best_strategy

    def _merge_adaptive_results(self, results: List[Dict]) -> Dict:
        """合并自适应优化结果"""
        best_y = float('inf')
        best_x = None
        all_history = []

        for result in results:
            if 'best_y' in result and result['best_y'] < best_y:
                best_y = result['best_y']
                best_x = result.get('best_x')

            if 'history' in result and 'y' in result['history']:
                all_history.extend(result['history']['y'])

        return {
            'best_x': best_x,
            'best_y': best_y,
            'strategy_history': [r.get('acquisition', 'unknown') for r in results],
            'performance_history': all_history
        }


class BatchBayesianOptimizer:
    """
    批量贝叶斯优化器

    支持并行评估的贝叶斯优化。
    """

    def __init__(self,
                 batch_size: int = 5,
                 acquisition_method: str = 'kb'):
        """
        初始化批量优化器

        Parameters:
        -----------
        batch_size : int
            批量大小
        acquisition_method : str
            批量获取函数方法
        """
        self.batch_size = batch_size
        self.acquisition_method = acquisition_method
        self.bo = BayesianOptimizer()

    def optimize(self,
                 objective_func: Callable,
                 bounds: List[Tuple[float, float]],
                 budget: int = 100,
                 parallel_func: Optional[Callable] = None) -> Dict[str, Any]:
        """
        运行批量优化

        Parameters:
        -----------
        objective_func : Callable
            单个目标函数
        bounds : List[Tuple[float, float]]
            变量边界
        budget : int
            总评估预算
        parallel_func : Callable
            并行评估函数

        Returns:
        --------
        Dict : 优化结果
        """
        self.bo.reset()
        evaluations = 0

        while evaluations < budget:
            # 确定本批大小
            current_batch = min(self.batch_size, budget - evaluations)

            # 建议批量点
            batch_points = self.bo.batch_suggest(bounds, current_batch)

            # 评估批量点
            if parallel_func is not None:
                # 并行评估
                batch_values = parallel_func(batch_points)
            else:
                # 串行评估
                batch_values = []
                for point in batch_points:
                    value = objective_func(point)
                    batch_values.append(value)

            # 观察结果
            for point, value in zip(batch_points, batch_values):
                self.bo.observe(point, value)
                evaluations += 1

        return {
            'best_x': self.bo.x_best,
            'best_y': self.bo.y_best,
            'n_evaluations': evaluations
        }


# 便捷函数
def hybrid_optimize(problem: BlackBoxProblem,
                    total_budget: int = 300,
                    bo_ratio: float = 0.3) -> Dict[str, Any]:
    """便捷的混合优化函数"""
    hybrid = HybridBO_NSGA(problem, bo_ratio=bo_ratio)
    return hybrid.run(total_budget=total_budget)


def adaptive_bayesian_optimize(problem: BlackBoxProblem,
                              budget: int = 200) -> Dict[str, Any]:
    """便捷的自适应贝叶斯优化函数"""
    adaptive = AdaptiveBOOptimizer(problem)
    return adaptive.run(budget=budget)


def batch_bayesian_optimize(problem: BlackBoxProblem,
                            batch_size: int = 5,
                            budget: int = 100) -> Dict[str, Any]:
    """便捷的批量贝叶斯优化函数"""
    bounds = [problem.bounds[i] for i in range(problem.dimension)]
    optimizer = BatchBayesianOptimizer(batch_size=batch_size)
    return optimizer.optimize(problem.evaluate, bounds, budget=budget)


# 导出接口
__all__ = [
    'HybridBO_NSGA',
    'AdaptiveBOOptimizer',
    'BatchBayesianOptimizer',
    'hybrid_optimize',
    'adaptive_bayesian_optimize',
    'batch_bayesian_optimize'
]