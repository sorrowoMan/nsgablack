"""
偏置系统 v2.0 使用示例
演示算法偏置和业务偏置的分离与组合
"""

import numpy as np
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from bias_v2 import (
    UniversalBiasManager, OptimizationContext,
    DiversityBias, ConvergenceBias, ConstraintBias, PreferenceBias
)
from bias_library import (
    BiasFactory, BiasComposer,
    quick_engineering_bias, quick_ml_bias, quick_financial_bias,
    create_bias_manager_from_template
)


# ==================== 测试问题定义 ====================

class EngineeringDesignProblem(BlackBoxProblem):
    """工程设计问题：优化悬臂梁设计"""

    def __init__(self):
        super().__init__(
            name="悬臂梁设计",
            dimension=3,
            bounds={'x0': (0.01, 0.1), 'x1': (0.01, 0.1), 'x2': (0.1, 1.0)}  # 宽度, 高度, 长度
        )

    def evaluate(self, x):
        # 简化的悬臂梁优化问题
        width, height, length = x

        # 目标1：最小化重量
        weight = width * height * length * 7850  # 钢材密度

        # 目标2：最小化材料成本
        cost = weight * 5.0  # 假设每公斤5元

        # 多目标：返回多个目标值
        return np.array([weight, cost])


class MLHyperparameterProblem(BlackBoxProblem):
    """机器学习超参数优化问题"""

    def __init__(self):
        super().__init__(
            name="神经网络超参数优化",
            dimension=4,
            bounds={
                'learning_rate': (0.0001, 0.1),
                'batch_size': (16, 256),
                'hidden_units': (32, 512),
                'dropout': (0.0, 0.5)
            }
        )

    def evaluate(self, x):
        lr, batch_size, hidden_units, dropout = x

        # 模拟神经网络训练结果
        # 学习率影响
        if 0.001 <= lr <= 0.01:
            lr_score = -0.8  # 好（负号表示低loss）
        elif 0.01 < lr <= 0.1:
            lr_score = -0.5
        else:
            lr_score = 0.5   # 差

        # 批次大小影响
        if 32 <= batch_size <= 128:
            batch_score = -0.6
        else:
            batch_score = -0.3

        # 隐藏单元影响
        hidden_score = -np.log(hidden_units / 100.0 + 1)

        # dropout影响
        if 0.1 <= dropout <= 0.3:
            dropout_score = -0.4
        else:
            dropout_score = 0.2

        # 添加一些随机性
        noise = np.random.normal(0, 0.05)

        return lr_score + batch_score + hidden_score + dropout_score + noise


class PortfolioOptimizationProblem(BlackBoxProblem):
    """投资组合优化问题"""

    def __init__(self, n_assets=5):
        super().__init__(
            name="投资组合优化",
            dimension=n_assets,
            bounds={f'asset_{i}': (0.0, 1.0) for i in range(n_assets)}
        )
        self.expected_returns = np.array([0.08, 0.12, 0.15, 0.10, 0.20])
        self.risks = np.array([0.10, 0.15, 0.25, 0.12, 0.30])

    def evaluate(self, x):
        # 确保权重和为1（归一化）
        weights = x / np.sum(x)

        # 计算期望收益
        expected_return = np.dot(weights, self.expected_returns)

        # 计算风险（简化版）
        risk = np.sqrt(np.sum((weights * self.risks) ** 2))

        # 多目标：最小化风险，最大化收益（用负收益）
        return np.array([risk, -expected_return])


# ==================== 偏置配置函数 ====================

def create_engineering_bias_config():
    """创建工程设计偏置配置"""
    config = {
        'algorithmic': {
            'biases': [
                {
                    'type': 'diversity',
                    'parameters': {
                        'weight': 0.15,
                        'metric': 'euclidean'
                    }
                },
                {
                    'type': 'convergence',
                    'parameters': {
                        'weight': 0.1,
                        'early_gen': 10,
                        'late_gen': 50
                    }
                }
            ]
        },
        'domain': {
            'biases': [
                {
                    'type': 'constraint',
                    'parameters': {
                        'weight': 2.0,
                        'hard_constraints': [],
                        'soft_constraints': [],
                        'preferred_constraints': []
                    }
                }
            ]
        }
    }

    # 添加约束函数
    def stress_constraint(x):
        """应力约束"""
        width, height, length = x
        max_stress = 6 * 1000 * length / (width * height ** 2)  # 简化应力计算
        return max(0, max_stress - 200)  # 不超过200MPa

    def displacement_constraint(x):
        """位移约束"""
        width, height, length = x
        max_displacement = 4 * 1000 * length ** 3 / (3 * 2.1e11 * width * height ** 3 / 12)
        return max(0, max_displacement - 0.01)  # 不超过10mm

    config['domain']['biases'][0]['parameters']['hard_constraints'] = [stress_constraint, displacement_constraint]
    config['domain']['biases'][0]['parameters']['soft_constraints'] = [lambda x: x[0] * x[1] * x[2] - 0.1]  # 体积约束

    return config


def create_ml_bias_config():
    """创建机器学习偏置配置"""
    config = {
        'algorithmic': {
            'biases': [
                {
                    'type': 'precision',
                    'parameters': {
                        'weight': 0.2,
                        'precision_radius': 0.05
                    }
                }
            ]
        },
        'domain': {
            'biases': [
                {
                    'type': 'preference',
                    'parameters': {
                        'preferences': [
                            {'metric': 'training_time', 'direction': 'minimize', 'weight': 1.0},
                            {'metric': 'model_complexity', 'direction': 'minimize', 'weight': 0.5}
                        ]
                    }
                }
            ]
        }
    }

    return config


# ==================== 偏置增强的求解器 ====================

class BiasEnhancedSolver(BlackBoxSolverNSGAII):
    """偏置增强的NSGA-II求解器"""

    def __init__(self, problem, bias_manager=None):
        super().__init__(problem)
        self.bias_manager = bias_manager or UniversalBiasManager()
        self.evaluation_history = []

    def evaluate_with_bias(self, population):
        """使用偏置评估种群"""
        objectives = []
        violations = []

        for i, individual in enumerate(population):
            # 基础评估
            base_objective = self.problem.evaluate(individual)

            # 创建上下文
            context = OptimizationContext(
                generation=getattr(self, 'current_generation', 0),
                individual=individual,
                population=population
            )

            # 添加元数据
            context.metrics = {
                'training_time': self.estimate_training_time(individual),
                'model_complexity': self.estimate_model_complexity(individual)
            }

            # 计算偏置
            bias_value = self.bias_manager.compute_total_bias(individual, context)

            # 组合目标函数和偏置
            if isinstance(base_objective, np.ndarray):
                biased_objective = base_objective + bias_value
            else:
                biased_objective = base_objective + bias_value

            objectives.append(biased_objective)

            # 约束评估
            if hasattr(self.problem, 'evaluate_constraints'):
                violations.append(self.problem.evaluate_constraints(individual))
            else:
                violations.append(np.array([]))

            # 记录历史
            self.evaluation_history.append({
                'individual': individual.copy(),
                'base_objective': base_objective.copy() if isinstance(base_objective, np.ndarray) else base_objective,
                'bias': bias_value,
                'final_objective': biased_objective.copy() if isinstance(biased_objective, np.ndarray) else biased_objective
            })

        return np.array(objectives), np.array(violations)

    def estimate_training_time(self, x):
        """估算训练时间"""
        # 简化的训练时间估算
        lr, batch_size, hidden_units, dropout = x
        return hidden_units * 100 / batch_size * 0.01  # 假设的单位时间

    def estimate_model_complexity(self, x):
        """估算模型复杂度"""
        lr, batch_size, hidden_units, dropout = x
        return hidden_units * 100  # 参数数量

    def run(self):
        """重写run方法，使用偏置评估"""
        self.current_generation = 0
        self.initialize_population()

        for self.current_generation in range(self.max_generations):
            # 进化操作
            offspring = self.evolve()

            # 使用偏置评估
            obj_offspring, vio_offspring = self.evaluate_with_bias(offspring)
            obj_current, vio_current = self.evaluate_with_bias(self.population)

            # 环境选择
            self.population = self.environmental_selection(
                self.population, offspring,
                obj_current, obj_offspring,
                vio_current, vio_offspring
            )

            # 调整偏置权重
            state = {
                'is_stuck': self.check_stagnation(),
                'is_violating_constraints': self.check_constraint_violations()
            }
            self.bias_manager.adjust_weights(state)

            if self.enable_progress_log and self.current_generation % 10 == 0:
                print(f"Generation {self.current_generation}: Population size: {len(self.population)}")

        return self.format_results()

    def check_stagnation(self):
        """检查是否停滞"""
        if len(self.evaluation_history) < 20:
            return False

        recent = self.evaluation_history[-20:]
        improvements = [abs(h['final_objective'] - recent[0]['final_objective']) for h in recent]

        # 如果改进很小，认为停滞
        return np.mean(improvements) < 1e-6

    def check_constraint_violations(self):
        """检查是否有约束违反"""
        if not self.evaluation_history:
            return False

        recent = self.evaluation_history[-10:]
        violation_count = sum(1 for h in recent if h.get('constraint_violation', 0) > 0)

        return violation_count > 5  # 最近10次中有5次违反


# ==================== 示例函数 ====================

def example_1_basic_bias_usage():
    """示例1：基础偏置使用"""
    print("="*60)
    print("示例1：基础偏置使用")
    print("="*60)

    # 创建问题
    problem = EngineeringDesignProblem()

    # 创建偏置管理器
    bias_manager = UniversalBiasManager()

    # 添加算法偏置
    bias_manager.algorithmic_manager.add_bias(DiversityBias(weight=0.2))
    bias_manager.algorithmic_manager.add_bias(ConvergenceBias(weight=0.1))

    # 添加业务偏置
    constraint_bias = ConstraintBias(weight=2.0)
    constraint_bias.add_hard_constraint(lambda x: max(0, x[0] * x[1] * x[2] - 0.1))
    bias_manager.domain_manager.add_bias(constraint_bias)

    # 创建求解器
    solver = BiasEnhancedSolver(problem, bias_manager)
    solver.pop_size = 30
    solver.max_generations = 50
    solver.enable_progress_log = True

    print(f"\n问题: {problem.name}")
    print(f"偏置配置:")
    print(f"  - 算法偏置: 多样性 + 收敛性")
    print(f"  - 业务偏置: 约束处理")
    print(f"\n开始优化...")

    # 运行优化
    start_time = time.time()
    result = solver.run()
    end_time = time.time()

    print(f"\n优化完成！耗时: {end_time - start_time:.2f}秒")
    print(f"找到 {len(result['pareto_solutions']['objectives'])} 个Pareto解")

    # 显示最优解
    if len(result['pareto_solutions']['objectives']) > 0:
        best_idx = np.argmin(result['pareto_solutions']['objectives'][:, 0])  # 最小重量
        best_solution = result['pareto_solutions']['individuals'][best_idx]
        best_objectives = result['pareto_solutions']['objectives'][best_idx]

        print(f"\n最优解:")
        print(f"  宽度: {best_solution[0]:.4f}")
        print(f"  高度: {best_solution[1]:.4f}")
        print(f"  长度: {best_solution[2]:.4f}")
        print(f"  重量: {best_objectives[0]:.4f}")
        print(f"  成本: {best_objectives[1]:.2f}")


def example_2_template_usage():
    """示例2：使用偏置模板"""
    print("\n" + "="*60)
    print("示例2：使用偏置模板")
    print("="*60)

    # 创建机器学习问题
    problem = MLHyperparameterProblem()

    # 使用机器学习模板创建偏置管理器
    bias_manager = create_bias_manager_from_template(
        'machine_learning',
        customizations={
            'algorithmic': {
                'parameters': {
                    'precision_radius': 0.03  # 自定义精度半径
                }
            },
            'domain': {
                'parameters': {
                    'weight': 1.5  # 增加业务偏置权重
                }
            }
        }
    )

    # 创建求解器
    solver = BiasEnhancedSolver(problem, bias_manager)
    solver.pop_size = 40
    solver.max_generations = 30
    solver.enable_progress_log = True

    print(f"\n问题: {problem.name}")
    print(f"使用模板: machine_learning")
    print(f"\n开始优化...")

    # 运行优化
    start_time = time.time()
    result = solver.run()
    end_time = time.time()

    print(f"\n优化完成！耗时: {end_time - start_time:.2f}秒")
    print(f"找到 {len(result['pareto_solutions']['objectives'])} 个解")

    # 显示一些解
    print(f"\n前3个解的超参数配置:")
    for i in range(min(3, len(result['pareto_solutions']['objectives']))):
        solution = result['pareto_solutions']['individuals'][i]
        obj = result['pareto_solutions']['objectives'][i]
        print(f"\n解 {i+1}:")
        print(f"  学习率: {solution[0]:.6f}")
        print(f"  批次大小: {int(solution[1])}")
        print(f"  隐藏单元: {int(solution[2])}")
        print(f"  Dropout: {solution[3]:.3f}")
        print(f"  Loss: {obj:.4f}")


def example_3_bias_composer():
    """示例3：使用偏置组合器"""
    print("\n" + "="*60)
    print("示例3：使用偏置组合器")
    print("="*60)

    # 创建投资组合问题
    problem = PortfolioOptimizationProblem(n_assets=5)

    # 创建偏置组合器
    composer = BiasComposer()

    # 添加算法偏置
    composer.add_algorithmic_bias_from_config('diversity_promotion', weight=0.15)
    composer.add_algorithmic_bias_from_config('fast_convergence', early_gen=5, late_gen=25)

    # 添加业务偏置
    finance_bias = composer.add_domain_bias_from_config('financial_optimization', weight=1.5)

    # 添加约束
    def budget_constraint(x):
        return max(0, np.sum(x) - 1.0)

    def risk_constraint(x):
        portfolio_risk = np.sqrt(np.sum((x * np.array([0.10, 0.15, 0.25, 0.12, 0.30])) ** 2))
        return max(0, portfolio_risk - 0.2)

    # 使用 BiasFactory 创建的偏置需要手动添加约束
    # 这里简化处理，实际应用中需要更完整的实现

    print(f"\n问题: {problem.name}")
    print(f"偏置组合:")
    print(f"  - 算法偏置: 多样性促进 + 快速收敛")
    print(f"  - 业务偏置: 金融优化")

    # 运行基础优化（这里简化处理）
    print(f"\n运行投资组合优化...")
    print(f"投资组合的约束和目标:")
    print(f"  - 预算约束: 权重和 <= 1.0")
    print(f"  - 风险约束: 组合风险 <= 0.2")
    print(f"  - 目标: 最小化风险，最大化收益")


def example_4_quick_bias_functions():
    """示例4：快速偏置函数"""
    print("\n" + "="*60)
    print("示例4：快速偏置函数")
    print("="*60)

    # 展示不同领域的快速偏置创建

    print("\n1. 工程设计偏置:")
    eng_bias = quick_engineering_bias(
        safety_constraints=[lambda x: max(0, x[0] * x[1] * x[2] - 0.05)],
        reliability_weight=3.0
    )
    print(f"   - 安全约束: 体积限制")
    print(f"   - 可靠性权重: 3.0")
    print(f"   - 算法偏置: 多样性 + 收敛性")

    print("\n2. 机器学习偏置:")
    ml_bias = quick_ml_bias(
        accuracy_weight=6.0,
        time_limit=1800,  # 30分钟
        memory_limit=4.0   # 4GB
    )
    print(f"   - 准确率权重: 6.0")
    print(f"   - 时间限制: 1800秒")
    print(f"   - 内存限制: 4GB")
    print(f"   - 算法偏置: 精度搜索")

    print("\n3. 金融优化偏置:")
    finance_bias = quick_financial_bias(
        max_risk=0.18,
        max_sector_exposure=0.25,
        target_return=0.15
    )
    print(f"   - 最大风险: 18%")
    print(f"   - 最大行业敞口: 25%")
    print(f"   - 目标收益: 15%")
    print(f"   - 算法偏置: 快速收敛")


def example_5_bias_library():
    """示例5：偏置库使用"""
    print("\n" + "="*60)
    print("示例5：偏置库使用")
    print("="*60)

    # 列出可用的偏置
    alg_biases = BiasFactory.list_available_algorithmic_biases()
    domain_biases = BiasFactory.list_available_domain_biases()

    print(f"\n可用的算法偏置 ({len(alg_biases)} 个):")
    for name, info in alg_biases.items():
        print(f"  - {name}: {info['description']}")

    print(f"\n可用的业务偏置 ({len(domain_biases)} 个):")
    for name, info in domain_biases.items():
        print(f"  - {name}: {info['description']}")

    # 动态创建偏置
    print(f"\n动态创建偏置示例:")

    # 创建探索性偏置
    exploration_bias = BiasFactory.create_algorithmic_bias(
        'balanced_exploration',
        weight=0.2,
        stagnation_threshold=15
    )
    print(f"  - 创建探索性偏置: {exploration_bias.name}")

    # 创建供应链偏置
    supply_bias = BiasFactory.create_domain_bias(
        'supply_chain',
        weight=1.2
    )
    print(f"  - 创建供应链偏置: {supply_bias.name}")

    # 显示偏置库统计
    print(f"\n偏置库统计:")
    print(f"  - 算法偏置总数: {len(alg_biases)}")
    print(f"  - 业务偏置总数: {len(domain_biases)}")
    print(f"  - 总偏置类型: {len(alg_biases) + len(domain_biases)}")


# ==================== 主函数 ====================

def main():
    """主函数"""
    print("偏置系统 v2.0 使用示例")
    print("演示算法偏置和业务偏置的分离与组合")
    print("="*60)

    # 运行示例
    try:
        example_1_basic_bias_usage()
        example_2_template_usage()
        example_3_bias_composer()
        example_4_quick_bias_functions()
        example_5_bias_library()

        print("\n" + "="*60)
        print("所有示例运行完成！")
        print("="*60)

        print("\n偏置系统 v2.0 的优势:")
        print("1. 算法偏置与业务偏置分离，提高复用性")
        print("2. 丰富的偏置库，支持多种应用场景")
        print("3. 模板系统，快速创建常见配置")
        print("4. 偏置组合器，灵活组合多种偏置")
        print("5. 动态权重调整，适应优化过程")
        print("6. 配置保存和加载，支持实验复现")

    except Exception as e:
        print(f"\n运行示例时出错: {e}")
        import traceback
        traceback.print_exc()
if __name__ == "__main__":
    main()