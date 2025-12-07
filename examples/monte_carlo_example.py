"""蒙特卡洛优化示例

展示三种典型用法：
1. 基础MC+GA：处理随机需求的库存优化
2. 鲁棒优化：最小化期望+方差
3. 代理+MC+GA：三层嵌套架构
"""
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solvers.monte_carlo import (
    StochasticProblem, DistributionSpec,
    MonteCarloOptimizer, SurrogateMonteCarloOptimizer,
    optimize_with_monte_carlo, optimize_with_surrogate_mc
)
from solvers.nsga2 import BlackBoxSolverNSGAII


# ============ 示例1: 随机库存优化 ============
class StochasticInventoryProblem(StochasticProblem):
    """随机需求下的库存优化

    决策变量：x = [订货量, 安全库存]
    随机变量：需求 ~ Normal(100, 20)
    目标：最小化 期望总成本 = 订货成本 + 持有成本 + 缺货成本
    """

    def __init__(self):
        super().__init__(
            name="随机库存优化",
            dimension=2,
            bounds={'x0': [50, 200], 'x1': [0, 50]}  # 订货量, 安全库存
        )
        self.order_cost = 10  # 单位订货成本
        self.holding_cost = 2  # 单位持有成本
        self.shortage_cost = 50  # 单位缺货成本

    def get_random_distributions(self):
        return {
            'demand': DistributionSpec('normal', {'mean': 100, 'std': 20})
        }

    def evaluate_stochastic(self, x, random_params):
        order_qty, safety_stock = x
        demand = random_params['demand']

        # 总库存 = 订货量 + 安全库存
        total_inventory = order_qty + safety_stock

        # 成本计算
        order_cost = self.order_cost * order_qty
        holding_cost = self.holding_cost * max(0, total_inventory - demand)
        shortage_cost = self.shortage_cost * max(0, demand - total_inventory)

        total_cost = order_cost + holding_cost + shortage_cost
        return total_cost


# ============ 示例2: 随机投资组合优化 ============
class StochasticPortfolioProblem(StochasticProblem):
    """随机收益率下的投资组合优化

    决策变量：x = [资产1权重, 资产2权重, ..., 资产n权重]
    随机变量：各资产收益率
    目标：最小化 -期望收益 (即最大化收益)
    约束：权重和为1
    """

    def __init__(self, n_assets=3):
        super().__init__(
            name="随机投资组合",
            dimension=n_assets,
            bounds={f'x{i}': [0, 1] for i in range(n_assets)}
        )
        self.n_assets = n_assets
        # 资产期望收益率
        self.expected_returns = np.array([0.08, 0.12, 0.15])
        # 收益率标准差
        self.return_stds = np.array([0.05, 0.10, 0.15])

    def get_random_distributions(self):
        return {
            f'return_{i}': DistributionSpec('normal', {
                'mean': self.expected_returns[i],
                'std': self.return_stds[i]
            })
            for i in range(self.n_assets)
        }

    def evaluate_stochastic(self, x, random_params):
        # 归一化权重
        weights = x / (np.sum(x) + 1e-10)

        # 计算组合收益
        returns = np.array([random_params[f'return_{i}'] for i in range(self.n_assets)])
        portfolio_return = np.dot(weights, returns)

        # 最小化负收益（即最大化收益）
        return -portfolio_return

    def evaluate_constraints(self, x):
        # 约束：权重和接近1
        return np.array([abs(np.sum(x) - 1.0) - 0.01])


# ============ 示例3: 带噪声的工程设计 ============
class NoisyEngineeringProblem(StochasticProblem):
    """带制造误差的工程设计优化

    决策变量：x = [长度, 宽度, 高度]
    随机变量：制造误差 ~ Normal(0, 0.05)
    目标：最小化重量，同时满足强度约束
    """

    def __init__(self):
        super().__init__(
            name="带噪声工程设计",
            dimension=3,
            bounds={'x0': [1, 5], 'x1': [1, 5], 'x2': [1, 5]}
        )

    def get_random_distributions(self):
        return {
            'error_0': DistributionSpec('normal', {'mean': 0, 'std': 0.05}),
            'error_1': DistributionSpec('normal', {'mean': 0, 'std': 0.05}),
            'error_2': DistributionSpec('normal', {'mean': 0, 'std': 0.05})
        }

    def evaluate_stochastic(self, x, random_params):
        # 实际尺寸 = 设计尺寸 + 制造误差
        actual = x + np.array([random_params[f'error_{i}'] for i in range(3)])
        actual = np.maximum(actual, 0.1)  # 避免负值

        # 重量 = 体积 * 密度
        weight = np.prod(actual) * 7.8

        return weight

    def evaluate_constraints(self, x):
        # 强度约束：最小尺寸 >= 1.5
        return np.array([1.5 - np.min(x)])


# ============ 运行示例 ============
def example_1_basic_mc_ga():
    """示例1: 基础MC+GA嵌套"""
    print("\n" + "="*60)
    print("示例1: 随机库存优化 (MC + GA)")
    print("="*60)

    problem = StochasticInventoryProblem()

    # 定义内层优化器工厂
    def optimizer_factory(prob):
        solver = BlackBoxSolverNSGAII(prob)
        solver.enable_progress_log = False
        return solver

    # 运行MC优化
    result = optimize_with_monte_carlo(
        stochastic_problem=problem,
        inner_optimizer_factory=optimizer_factory,
        mc_samples=50,  # MC采样数
        mode='expectation',  # 最小化期望
        pop_size=40,
        max_generations=30
    )

    print(f"\n最优解: {result['best_x']}")
    print(f"期望成本: {result['best_f']:.2f}")
    if result['statistics']:
        stats = result['statistics']
        print(f"标准差: {stats['std']:.2f}")
        print(f"95%分位数: {stats['q75']:.2f}")


def example_2_robust_optimization():
    """示例2: 鲁棒优化 (最小化期望+方差)"""
    print("\n" + "="*60)
    print("示例2: 鲁棒投资组合优化 (期望 + λ*标准差)")
    print("="*60)

    problem = StochasticPortfolioProblem(n_assets=3)

    def optimizer_factory(prob):
        solver = BlackBoxSolverNSGAII(prob)
        solver.enable_progress_log = False
        return solver

    # 鲁棒优化：最小化 E[f] + 0.5*Std[f]
    optimizer = MonteCarloOptimizer(
        stochastic_problem=problem,
        inner_optimizer_factory=optimizer_factory,
        mc_samples=50,
        mode='robust',
        robust_lambda=0.5  # 方差权重
    )

    result = optimizer.optimize(pop_size=40, max_generations=30)

    print(f"\n最优权重: {result['best_x']}")
    print(f"归一化权重: {result['best_x'] / np.sum(result['best_x'])}")
    print(f"鲁棒目标值: {result['best_f']:.4f}")
    if result['statistics']:
        stats = result['statistics']
        print(f"期望收益: {-stats['mean']:.4f}")
        print(f"收益标准差: {stats['std']:.4f}")


def example_3_surrogate_mc_ga():
    """示例3: 代理+MC+GA三层架构"""
    print("\n" + "="*60)
    print("示例3: 带噪声工程设计 (Surrogate + MC + GA)")
    print("="*60)

    problem = NoisyEngineeringProblem()

    def optimizer_factory(prob):
        solver = BlackBoxSolverNSGAII(prob)
        solver.enable_progress_log = False
        return solver

    # 代理+MC优化
    result = optimize_with_surrogate_mc(
        stochastic_problem=problem,
        inner_optimizer_factory=optimizer_factory,
        mc_samples=30,  # 每次MC评估的样本数
        surrogate_type='gp',  # 高斯过程代理
        initial_samples=15,  # 初始训练样本
        max_iterations=5,  # 迭代次数
        pop_size=30,
        max_generations=20
    )

    print(f"\n最优设计: {result['best_x']}")
    print(f"期望重量: {result['best_f']:.2f}")
    print(f"真实MC评估次数: {len(result['y_train'])}")
    if result['statistics']:
        stats = result['statistics']
        print(f"重量标准差: {stats['std']:.2f}")
        print(f"最坏情况: {stats['max']:.2f}")


def run_all_examples():
    """运行所有示例"""
    example_1_basic_mc_ga()
    example_2_robust_optimization()
    example_3_surrogate_mc_ga()

    print("\n" + "="*60)
    print("所有示例运行完成！")
    print("="*60)


if __name__ == "__main__":
    run_all_examples()
