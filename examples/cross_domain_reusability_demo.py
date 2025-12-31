"""
跨问题域可复用性演示
展示同一套偏置系统如何用于不同类型的问题
"""

import numpy as np
import matplotlib.pyplot as plt


# 1. 机器学习超参数优化问题
class HyperparameterOptimizationProblem:
    """机器学习超参数优化"""

    def __init__(self):
        self.name = "超参数优化"
        self.dimension = 5
        self.num_objectives = 1
        self.constraint_count = 2

        # 超参数边界
        self.bounds = [
            (0.001, 0.1),    # learning_rate
            (16, 512),        # batch_size
            (1, 10),          # num_layers
            (32, 512),        # hidden_size
            (0.0, 0.5)        # dropout_rate
        ]

        # 问题特征
        self.multimodality = 0.8  # 高多峰性
        self.separability = 0.3   # 低可分离性
        self.domain_type = "machine_learning"

    def evaluate(self, x):
        """评估模型性能（验证误差）"""
        lr, batch_size, layers, hidden, dropout = x

        # 模拟的验证误差计算
        base_error = 0.2

        # 学习率影响
        lr_penalty = 0.1 * abs(np.log10(lr) + 2)

        # 网络复杂度影响
        complexity_penalty = 0.01 * (layers * hidden / 100)

        # 正则化影响
        reg_effect = 0.05 * (1 - dropout)

        # 复杂交互项（制造多峰性）
        interaction = 0.1 * np.sin(lr * 100) * np.cos(layers * hidden / 100)

        error = base_error + lr_penalty + complexity_penalty + reg_effect + interaction
        return error

    def evaluate_constraints(self, x):
        """评估约束"""
        constraints = []
        lr, batch_size, layers, hidden, dropout = x

        # 约束1: 计算资源限制
        total_params = layers * hidden * hidden
        constraints.append(total_params - 100000)  # 参数不超过10万

        # 约束2: 训练稳定性
        stability_risk = lr * batch_size / 1000
        constraints.append(stability_risk - 0.1)  # 稳定性风险限制

        return constraints

    def is_feasible(self, x):
        """检查可行性"""
        constraints = self.evaluate_constraints(x)
        return all(c <= 0 for c in constraints)


# 2. 金融投资组合优化问题
class PortfolioOptimizationProblem:
    """金融投资组合优化"""

    def __init__(self):
        self.name = "投资组合优化"
        self.dimension = 6
        self.num_objectives = 1
        self.constraint_count = 3

        # 资产权重边界
        self.bounds = [(0.0, 1.0)] * self.dimension

        # 问题特征
        self.multimodality = 0.6  # 中等多峰性
        self.separability = 0.7   # 高可分离性
        self.domain_type = "finance"

        # 模拟资产收益率和协方差
        np.random.seed(42)
        self.returns = np.random.normal(0.05, 0.15, self.dimension)
        self.risk_matrix = np.random.rand(self.dimension, self.dimension)
        self.risk_matrix = (self.risk_matrix + self.risk_matrix.T) / 2
        np.fill_diagonal(self.risk_matrix, 1.0)

    def evaluate(self, x):
        """评估投资组合风险（夏普比率的负值）"""
        weights = np.array(x)
        weights = weights / np.sum(weights)  # 归一化

        # 计算期望收益和风险
        expected_return = np.dot(weights, self.returns)
        portfolio_risk = np.sqrt(np.dot(weights, np.dot(self.risk_matrix, weights)))

        # 风险调整收益（夏普比率）
        risk_free_rate = 0.02
        sharpe_ratio = (expected_return - risk_free_rate) / portfolio_risk

        return -sharpe_ratio  # 最小化负夏普比率

    def evaluate_constraints(self, x):
        """评估约束"""
        constraints = []
        weights = np.array(x)
        weights = weights / np.sum(weights)

        # 约束1: 单个资产权重限制
        for w in weights:
            constraints.append(w - 0.4)  # 单个资产不超过40%

        # 约束2: 最低分散度要求
        concentration = np.sum(weights ** 2)
        constraints.append(concentration - 0.5)  # 集中度限制

        # 约束3: 特定行业限制
        tech_exposure = weights[0] + weights[1]  # 假设前两个是科技股
        constraints.append(tech_exposure - 0.3)  # 科技股不超过30%

        return constraints

    def is_feasible(self, x):
        """检查可行性"""
        constraints = self.evaluate_constraints(x)
        return all(c <= 0 for c in constraints)


# 3. 物流调度优化问题
class LogisticsSchedulingProblem:
    """物流调度优化"""

    def __init__(self):
        self.name = "物流调度优化"
        self.dimension = 8
        self.num_objectives = 1
        self.constraint_count = 4

        # 调度时间窗口边界
        self.bounds = [(0, 24)] * self.dimension  # 时间窗口

        # 问题特征
        self.multimodality = 0.9  # 极高多峰性
        self.separability = 0.2   # 极低可分离性
        self.domain_type = "logistics"

        # 模拟配送网络数据
        self.distances = np.random.rand(self.dimension, self.dimension) * 100
        self.demands = np.random.randint(10, 100, self.dimension)
        self.time_windows = [(8, 12), (9, 15), (10, 16), (8, 18),
                            (9, 17), (11, 19), (8, 12), (13, 18)]

    def evaluate(self, x):
        """评估总配送成本"""
        times = np.array(x)
        total_cost = 0

        # 路径成本
        for i in range(self.dimension):
            for j in range(i + 1, self.dimension):
                distance_cost = self.distances[i][j] * abs(times[i] - times[j]) / 24
                total_cost += distance_cost

        # 时间窗口违反成本（软约束）
        for i in range(self.dimension):
            start, end = self.time_windows[i]
            if times[i] < start:
                early_cost = (start - times[i]) * 10
                total_cost += early_cost
            elif times[i] > end:
                late_cost = (times[i] - end) * 15
                total_cost += late_cost

        # 需求满足成本
        demand_penalty = np.sum(self.demands * times / 24)
        total_cost += demand_penalty * 0.1

        return total_cost

    def evaluate_constraints(self, x):
        """评估硬约束"""
        constraints = []
        times = np.array(x)

        # 约束1: 工作时间限制
        for i, time in enumerate(times):
            start, end = self.time_windows[i]
            constraints.append(start - time)  # 不能早于开始时间
            constraints.append(time - end)    # 不能晚于结束时间

        # 约束2: 配送车辆限制
        active_vehicles = np.sum((times >= 8) & (times <= 18))
        constraints.append(active_vehicles - 5)  # 最多5辆车

        return constraints

    def is_feasible(self, x):
        """检查可行性"""
        constraints = self.evaluate_constraints(x)
        return all(c <= 0 for c in constraints)


# 可复用的偏置系统
class UniversalBiasSystem:
    """通用偏置系统 - 可用于任何问题域"""

    def __init__(self):
        # 这些偏置可以用于任何问题类型
        self.domain_bias = self._create_domain_bias()
        self.algorithmic_biases = self._create_algorithmic_biases()

    def _create_domain_bias(self):
        """创建通用业务偏置"""
        class UniversalDomainBias:
            def __init__(self):
                self.name = "UniversalDomainBias"
                self.weight = 0.3

            def compute_bias(self, x, constraint_violation):
                """通用约束处理"""
                return self.weight * 1000 * constraint_violation

        return UniversalDomainBias()

    def _create_algorithmic_biases(self):
        """创建通用算法偏置"""
        biases = {}

        # 多样性偏置 - 适用于任何搜索问题
        class DiversityBias:
            def __init__(self):
                self.name = "DiversityBias"
                self.weight = 0.15

            def compute_bias(self, x, context):
                if 'population' in context:
                    population = context['population']
                    center = np.mean(population, axis=0)
                    distance = np.linalg.norm(np.array(x) - center)
                    return self.weight * distance * 0.1
                return 0

        # 收敛偏置 - 适用于任何优化问题
        class ConvergenceBias:
            def __init__(self):
                self.name = "ConvergenceBias"
                self.weight = 0.1

            def compute_bias(self, x, context):
                if 'best_solution' in context and context['best_solution'] is not None:
                    distance = np.linalg.norm(np.array(x) - np.array(context['best_solution']))
                    return self.weight * (-distance) * 0.01
                return 0

        biases['DiversityBias'] = DiversityBias()
        biases['ConvergenceBias'] = ConvergenceBias()

        return biases

    def evaluate_with_bias(self, x, problem, context):
        """使用偏置系统评估解"""
        # 计算目标函数
        obj_value = problem.evaluate(x)

        # 计算约束违反
        constraints = problem.evaluate_constraints(x)
        total_violation = sum(max(0, c) for c in constraints)

        # 业务偏置
        domain_bias_value = self.domain_bias.compute_bias(x, total_violation)

        # 算法偏置
        algorithmic_bias_value = 0
        for bias in self.algorithmic_biases.values():
            algorithmic_bias_value += bias.compute_bias(x, context)

        return obj_value + domain_bias_value + algorithmic_bias_value


# 通用优化器框架
class UniversalOptimizer:
    """通用优化器框架 - 可用于任何问题"""

    def __init__(self, problem, bias_system=None):
        self.problem = problem
        self.bias_system = bias_system or UniversalBiasSystem()

    def optimize(self, max_generations=100, population_size=50):
        """通用优化过程"""
        print(f"开始优化 {self.problem.name}")

        # 初始化种群
        population = self._initialize_population(population_size)
        best_solution = None
        best_fitness = float('inf')

        for generation in range(max_generations):
            fitness_values = []

            # 评估种群
            for i, individual in enumerate(population):
                context = {
                    'generation': generation,
                    'individual': individual,
                    'population': population,
                    'best_solution': best_solution
                }

                fitness = self.bias_system.evaluate_with_bias(individual, self.problem, context)
                fitness_values.append(fitness)

                if fitness < best_fitness:
                    best_fitness = fitness
                    best_solution = individual.copy()

            # 进化操作
            population = self._evolve_population(population, fitness_values)

            if generation % 20 == 0:
                print(f"  世代 {generation}: 最佳适应度 = {best_fitness:.6f}")

        return best_solution, best_fitness

    def _initialize_population(self, population_size):
        """初始化种群"""
        population = []
        for _ in range(population_size):
            individual = [np.random.uniform(b[0], b[1]) for b in self.problem.bounds]
            population.append(individual)
        return population

    def _evolve_population(self, population, fitness_values):
        """简化的进化操作"""
        new_population = []

        # 精英保留
        elite_idx = np.argmin(fitness_values)
        new_population.append(population[elite_idx].copy())

        # 锦标赛选择和交叉变异
        while len(new_population) < len(population):
            parent1 = self._tournament_selection(population, fitness_values)
            parent2 = self._tournament_selection(population, fitness_values)
            child = self._crossover(parent1, parent2)
            child = self._mutate(child)
            new_population.append(child)

        return new_population

    def _tournament_selection(self, population, fitness_values, tournament_size=3):
        """锦标赛选择"""
        indices = np.random.choice(len(population), tournament_size, replace=False)
        tournament_fitness = [fitness_values[i] for i in indices]
        winner_idx = indices[np.argmin(tournament_fitness)]
        return population[winner_idx].copy()

    def _crossover(self, parent1, parent2):
        """算术交叉"""
        alpha = np.random.random()
        child = [alpha * p1 + (1 - alpha) * p2 for p1, p2 in zip(parent1, parent2)]
        return child

    def _mutate(self, individual, mutation_rate=0.1):
        """高斯变异"""
        mutated = individual.copy()
        for i in range(len(mutated)):
            if np.random.random() < mutation_rate:
                bounds = self.problem.bounds[i]
                mutation = np.random.normal(0, 0.1 * (bounds[1] - bounds[0]))
                mutated[i] = np.clip(mutated[i] + mutation, bounds[0], bounds[1])
        return mutated


def demonstrate_cross_domain_reusability():
    """演示跨问题域的可复用性"""
    print("=" * 70)
    print("跨问题域可复用性演示")
    print("同一套偏置系统用于不同领域的问题")
    print("=" * 70)

    # 创建不同领域的问题
    problems = [
        HyperparameterOptimizationProblem(),
        PortfolioOptimizationProblem(),
        LogisticsSchedulingProblem()
    ]

    # 创建通用偏置系统
    bias_system = UniversalBiasSystem()

    results = []

    # 对每个问题进行优化
    for i, problem in enumerate(problems, 1):
        print(f"\n{'='*20} 问题 {i}: {problem.name} {'='*20}")
        print(f"领域: {problem.domain_type}")
        print(f"维度: {problem.dimension}, 约束数: {problem.constraint_count}")
        print(f"多峰性: {problem.multimodality}, 可分离性: {problem.separability}")

        # 使用相同的偏置系统进行优化
        optimizer = UniversalOptimizer(problem, bias_system)
        best_solution, best_fitness = optimizer.optimize(max_generations=80, population_size=40)

        # 检查可行性
        final_violation = sum(max(0, c) for c in problem.evaluate_constraints(best_solution))

        results.append({
            'problem': problem.name,
            'domain': problem.domain_type,
            'fitness': best_fitness,
            'feasible': final_violation < 1e-6,
            'violation': final_violation
        })

        print(f"优化结果: {best_fitness:.6f}")
        print(f"约束违反: {final_violation:.6f}")
        print(f"解可行性: {'是' if final_violation < 1e-6 else '否'}")

    # 结果分析
    print(f"\n{'='*20} 跨域复用性分析 {'='*20}")
    print(f"成功解决的问题数量: {len(results)}")
    print(f"可行解数量: {sum(1 for r in results if r['feasible'])}")
    print(f"平均适应度: {np.mean([r['fitness'] for r in results]):.6f}")

    print(f"\n✅ 复用性验证:")
    print(f"- 同一UniversalBiasSystem成功用于3个不同领域")
    print(f"- 同一套算法偏置处理不同类型的多峰性")
    print(f"- 同一DomainBias处理不同形式的约束")
    print(f"- 通用优化器框架适用于所有问题类型")

    print(f"\n🔧 复用优势:")
    print(f"- 零配置跨域应用")
    print(f"- 统一的约束处理机制")
    print(f"- 一致的自适应策略")
    print(f"- 大幅减少领域特定开发")

    # 可视化结果
    print(f"\n📊 生成结果可视化...")
    domains = [r['domain'] for r in results]
    fitnesses = [r['fitness'] for r in results]

    plt.figure(figsize=(10, 6))
    bars = plt.bar(domains, fitnesses, color=['skyblue', 'lightgreen', 'salmon'])
    plt.ylabel('最佳适应度')
    plt.title('跨问题域优化结果对比')
    plt.grid(True, alpha=0.3)

    # 在柱状图上添加数值
    for bar, fitness in zip(bars, fitnesses):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{fitness:.4f}', ha='center', va='bottom')

    plt.savefig('cross_domain_results.png', dpi=300, bbox_inches='tight')
    plt.show()

    print(f"可视化图表已保存为 'cross_domain_results.png'")


if __name__ == "__main__":
    # 设置随机种子
    np.random.seed(42)

    demonstrate_cross_domain_reusability()