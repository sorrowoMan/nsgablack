# 偏置系统架构指南

## 🎯 概述

偏置系统是NSGABlack优化库的核心特色，提供了一种模块化、可组合的方式来增强优化算法的性能。该系统实现了**业务偏置**与**算法偏置**的分离，支持自适应调整、元学习优化和多算法融合。

### 🌟 核心特性

- **双架构设计**: 业务偏置（全局固定）与算法偏置（动态调整）
- **智能自适应**: 基于优化状态自动调整偏置权重
- **元学习能力**: 从历史经验学习最优偏置组合
- **算法无关性**: 偏置可注入任何优化算法
- **效果评估**: 完整的偏置效果分析和评估框架
- **模块化组合**: 支持多偏置同时使用和灵活组合

## 🏗️ 系统架构

### 1. 双层偏置架构

```
偏置系统
├── 业务偏置 (Domain Bias)
│   ├── 全局固定权重
│   ├── 业务规则约束
│   └── 领域知识注入
└── 算法偏置 (Algorithmic Bias)
    ├── 自适应权重调整
    ├── 多样性维护
    ├── 收敛加速
    ├── 模拟退火思想
    └── 元学习优化
```

### 2. 核心组件

#### 2.1 基础偏置类型

```python
# 业务偏置 - 表示固定的业务规则
class DomainBias:
    def __init__(self, weight=0.2):
        self.weight = weight  # 固定权重，不变

    def compute_bias(self, individual, constraint_violation):
        # 基于约束违反的惩罚
        return self.weight * constraint_violation

# 算法偏置 - 可动态调整
class AlgorithmicBias:
    def __init__(self, name, initial_weight=0.1, adaptive=True):
        self.name = name
        self.weight = initial_weight  # 可调整权重
        self.adaptive = adaptive

    def compute_bias(self, individual, context):
        # 基于算法状态的动态偏置
        pass
```

#### 2.2 自适应管理器

```python
class AdaptiveAlgorithmicManager:
    def __init__(self):
        self.biases = {}
        self.performance_history = []
        self.stuck_threshold = 10

    def update_state(self, context, population, fitness_values):
        # 检测优化状态（停滞、收敛、多样等）
        # 动态调整偏置权重
        pass
```

#### 2.3 元学习选择器

```python
class MetaLearningBiasSelector:
    def __init__(self):
        self.historical_data = []
        self.feature_extractor = ProblemFeatureExtractor()

    def recommend_biases(self, problem_features):
        # 基于问题特征推荐最优偏置组合
        pass
```

## 📦 偏置模块详解

### 1. 业务偏置模块

#### 1.1 固定约束偏置
```python
# 工程设计问题中的业务偏置
class EngineeringDomainBias(DomainBias):
    def compute_bias(self, individual, constraint_violation):
        """
        对违反约束的解施加固定惩罚
        - 权重不随优化过程改变
        - 代表业务规则的强制性
        """
        if constraint_violation > 0:
            return self.weight * constraint_violation * 10
        return 0.0
```

**应用场景**:
- 工程设计约束（强度、刚度要求）
- 生产调度约束（资源限制、时间窗口）
- 路径规划约束（交通规则、地理限制）

### 2. 算法偏置模块

#### 2.1 模拟退火偏置
```python
class SimulatedAnnealingBias:
    """将模拟退火思想转换为可注入偏置"""

    def __init__(self, initial_weight=0.15, initial_temp=100.0, cooling_rate=0.995):
        self.weight = initial_weight
        self.temperature = initial_temp
        self.cooling_rate = cooling_rate

    def compute_bias(self, x, context):
        current_energy = context.get('current_energy', 0)
        previous_energy = context.get('previous_energy', 0)
        delta_energy = current_energy - previous_energy

        # Metropolis准则转换为偏置
        if delta_energy <= 0:
            return -self.weight * abs(delta_energy) * 0.1  # 奖励改进
        else:
            acceptance_prob = np.exp(-delta_energy / self.temperature)
            return self.weight * acceptance_prob * delta_energy * 0.1
```

**优势**:
- 可注入任何算法（GA、PSO、DE等）
- 保持算法原有逻辑不变
- 算法无关的温度调度
- 与其他偏置组合使用

#### 2.2 多样性维护偏置
```python
class DiversityBias:
    def compute_bias(self, individual, population):
        # 计算与种群其他个体的距离
        distances = [self._distance(individual, other) for other in population]
        min_distance = min(distances)

        # 鼓励多样性
        return self.weight * min_distance
```

#### 2.3 收敛加速偏置
```python
class ConvergenceBias:
    def compute_bias(self, individual, context):
        if self.is_converging(context):
            # 加强搜索方向
            return self.weight * self.directional_bias(individual, context)
        return 0.0
```

### 3. 自适应机制

#### 3.1 状态检测
```python
class OptimizationStateDetector:
    def detect_stagnation(self, fitness_history, window=10):
        """检测优化停滞"""
        if len(fitness_history) < window:
            return False
        recent = fitness_history[-window:]
        improvement = (recent[0] - recent[-1]) / recent[0]
        return improvement < 0.001

    def detect_diversity_loss(self, population):
        """检测多样性丢失"""
        distances = []
        for i, ind1 in enumerate(population):
            for j, ind2 in enumerate(population[i+1:], i+1):
                distances.append(self._distance(ind1, ind2))
        return np.mean(distances) < 0.1 * self.problem_dimension
```

#### 3.2 权重调整策略
```python
def adaptive_weight_adjustment(self, optimization_state):
    """基于优化状态调整权重"""
    if optimization_state.stuck:
        # 增强探索性偏置
        self.increase_weight("diversity", factor=1.2)
        self.increase_weight("simulated_annealing", factor=1.1)
    elif optimization_state.converging:
        # 增强开发性偏置
        self.increase_weight("convergence", factor=1.15)
    else:
        # 平衡调整
        self.balance_weights()
```

### 4. 元学习系统

#### 4.1 问题特征提取
```python
class ProblemFeatureExtractor:
    def extract_features(self, problem, sample_solutions=100):
        """提取问题特征用于偏置推荐"""
        features = {
            'dimension': problem.dimension,
            'constraint_count': problem.constraint_count,
            'multimodality': self.estimate_multimodality(problem, sample_solutions),
            'separability': self.estimate_separability(problem, sample_solutions),
            'epistasis': self.estimate_epistasis(problem),
            'ruggedness': self.estimate_ruggedness(problem),
            'constraint_severity': self.estimate_constraint_severity(problem),
            'objective_scale': self.estimate_objective_scale(problem)
        }
        return features
```

#### 4.2 偏置推荐引擎
```python
class BiasRecommendationEngine:
    def __init__(self):
        self.rule_base = {
            'high_multimodality': {
                'diversity': {'weight': 0.2, 'reason': '需要多峰搜索能力'},
                'simulated_annealing': {'weight': 0.15, 'reason': '避免局部最优'}
            },
            'high_constraint': {
                'domain_bias': {'weight': 0.3, 'reason': '强约束处理'},
                'repair_bias': {'weight': 0.1, 'reason': '约束修复'}
            },
            'low_separability': {
                'crossover_bias': {'weight': 0.15, 'reason': '变量交互强'},
                'correlation_bias': {'weight': 0.1, 'reason': '利用变量相关性'}
            }
        }

    def recommend(self, problem_features):
        """基于问题特征推荐偏置配置"""
        recommendations = {}

        for rule_name, rule in self.rule_base.items():
            if self.condition_matches(rule_name, problem_features):
                for bias_name, config in rule.items():
                    if bias_name not in recommendations:
                        recommendations[bias_name] = config
                    else:
                        # 合并推荐
                        recommendations[bias_name]['weight'] = max(
                            recommendations[bias_name]['weight'],
                            config['weight']
                        )

        return recommendations
```

## 🔧 使用指南

### 1. 基础使用

```python
from bias import DomainBias, AlgorithmicBias, AdaptiveBiasManager

# 1. 创建业务偏置（固定权重）
domain_bias = DomainBias(weight=0.2)

# 2. 创建算法偏置（自适应）
diversity_bias = AlgorithmicBias("Diversity", 0.1, adaptive=True)
sa_bias = AlgorithmicBias("SimulatedAnnealing", 0.15, adaptive=True)

# 3. 创建自适应管理器
manager = AdaptiveBiasManager()
manager.add_bias(diversity_bias)
manager.add_bias(sa_bias)

# 4. 在算法中使用
for individual in population:
    # 业务偏置（固定）
    domain_bias_value = domain_bias.compute_bias(individual, constraint_violation)

    # 算法偏置（自适应）
    context = {'generation': gen, 'population': population}
    algorithmic_bias_value = manager.compute_total_bias(individual, context)

    # 总适应度
    fitness = objective_value + domain_bias_value + algorithmic_bias_value
```

### 2. 元学习辅助使用

```python
from meta_learning_bias_selector import MetaLearningBiasSelector

# 1. 创建元学习选择器
selector = MetaLearningBiasSelector()

# 2. 分析问题特征
problem_features = selector.analyze_problem(problem)

# 3. 获取偏置推荐
recommendations = selector.recommend_biases(problem_features)

# 4. 应用推荐配置
for bias_name, config in recommendations.items():
    bias = AlgorithmicBias(bias_name, config['weight'])
    manager.add_bias(bias)
    print(f"添加 {bias_name}: {config['reason']}")
```

### 3. SA偏置集成示例

```python
# 将模拟退火思想注入遗传算法
class SAEnhancedGA:
    def __init__(self, use_sa_bias=True):
        self.domain_bias = DomainBias()
        self.adaptive_manager = AdaptiveBiasManager()

        if use_sa_bias:
            self.sa_bias = SimulatedAnnealingBias()
            sa_algo_bias = AlgorithmicBias("SA", self.sa_bias.weight)
            self.adaptive_manager.add_bias(sa_algo_bias)

    def evaluate_individual(self, individual, context):
        obj_value = self.problem.evaluate(individual)

        # 业务偏置
        domain_bias = self.domain_bias.compute_bias(individual,
                                                   self.get_constraint_violation(individual))

        # SA偏置
        sa_bias = self.sa_bias.compute_bias(individual, context) if self.sa_bias else 0

        # 其他算法偏置
        algo_bias = self.adaptive_manager.compute_total_bias(individual, context)

        return obj_value + domain_bias + sa_bias + algo_bias
```

## 📊 效果评估系统

### 1. 偏置效果分析器

```python
from bias_effectiveness_analytics import BiasEffectivenessAnalyzer

# 创建分析器
analyzer = BiasEffectivenessAnalyzer()

# 收集优化数据
optimization_data = {
    'problem_name': 'EngineeringDesign',
    'algorithm': 'GA',
    'biases_used': ['domain', 'diversity', 'simulated_annealing'],
    'fitness_history': fitness_history,
    'constraint_history': constraint_history,
    'solution_quality': final_fitness,
    'convergence_generation': convergence_gen
}

# 分析效果
results = analyzer.analyze_bias_effectiveness(optimization_data)

print(f"收敛改进: {results.convergence_improvement:.2%}")
print(f"解质量提升: {results.solution_quality_boost:.2%}")
print(f"多样性分数: {results.diversity_score:.3f}")
print(f"计算开销: {results.computational_overhead:.2%}")
```

### 2. 统计显著性检验

```python
# 多次运行对比
with_biases_results = []
without_biases_results = []

for run in range(30):
    # 使用偏置的优化
    result_with = self.optimize_with_biases()
    with_biases_results.append(result_with)

    # 不使用偏置的优化
    result_without = self.optimize_without_biases()
    without_biases_results.append(result_without)

# 统计检验
significance = analyzer.statistical_test(with_biases_results, without_biases_results)
print(f"统计显著性: p = {significance.p_value:.4f}")
print(f"效果可靠: {'是' if significance.significant else '否'}")
```

## 🎯 应用场景

### 1. 复杂工程设计

```python
# 飞机机翼设计问题
class WingDesignBias(DomainBias):
    def compute_bias(self, individual, constraint_violation):
        # 气动约束（固定）
        aerodynamics_penalty = self.weight * max(0, constraint_violation['aerodynamics'])

        # 结构约束（固定）
        structure_penalty = self.weight * max(0, constraint_violation['structure'])

        # 制造约束（固定）
        manufacturing_penalty = self.weight * max(0, constraint_violation['manufacturing'])

        return aerodynamics_penalty + structure_penalty + manufacturing_penalty

# 配合算法偏置使用
wing_design_biases = [
    WingDesignBias(weight=0.3),  # 强业务约束
    SimulatedAnnealingBias(initial_weight=0.2),  # 避免局部最优
    DiversityBias(weight=0.15)  # 多样性探索
]
```

### 2. 生产调度优化

```python
# 车间调度问题
class SchedulingBias(DomainBias):
    def compute_bias(self, individual, violations):
        # 时间窗口约束
        time_window_penalty = 0

        # 设备约束
        machine_constraint_penalty = 0

        # 工序顺序约束
        sequence_penalty = 0

        return self.weight * (time_window_penalty +
                            machine_constraint_penalty +
                            sequence_penalty)

# 实时调度偏置
class RealTimeSchedulingBias(AlgorithmicBias):
    def compute_bias(self, individual, context):
        # 紧急订单优先
        if self.has_urgent_order(context):
            return self.weight * self.urgent_order_bias(individual, context)

        # 交货期偏置
        return self.weight * self.delivery_bias(individual, context)
```

### 3. 路径规划

```python
# TSP问题偏置
class TSPBias(DomainBias):
    def compute_bias(self, tour, constraint_violation):
        # 违反访问约束惩罚
        missing_cities = constraint_violation['missing_cities']
        duplicate_visits = constraint_violation['duplicate_visits']

        return self.weight * (missing_cities * 100 + duplicate_visits * 50)

# 路径优化偏置
class TourOptimizationBias(AlgorithmicBias):
    def compute_bias(self, tour, context):
        # 2-opt邻域偏置
        return self.weight * self.two_opt_bias(tour)

    def two_opt_bias(self, tour):
        # 计算潜在的2-opt改进
        best_improvement = 0
        for i in range(len(tour)):
            for j in range(i + 2, len(tour)):
                improvement = self.calculate_2opt_improvement(tour, i, j)
                best_improvement = max(best_improvement, improvement)
        return best_improvement
```

## 🚀 高级功能

### 1. 多目标优化偏置

```python
class MultiObjectiveBias(AlgorithmicBias):
    def __init__(self, objectives, preference_weights):
        self.objectives = objectives
        self.preference_weights = preference_weights

    def compute_bias(self, individual, context):
        # Pareto排序偏置
        pareto_rank = self.get_pareto_rank(individual, context['population'])
        pareto_bias = 1.0 / pareto_rank

        # 拥挤距离偏置
        crowding_distance = self.calculate_crowding_distance(individual, context['population'])
        diversity_bias = crowding_distance

        # 偏好引导偏置
        preference_bias = self.calculate_preference_bias(individual)

        return self.weight * (pareto_bias + diversity_bias + preference_bias)
```

### 2. 动态约束偏置

```python
class DynamicConstraintBias(DomainBias):
    def __init__(self, initial_weight=0.1):
        super().__init__(initial_weight)
        self.constraint_evolution = {}

    def update_constraint_importance(self, constraint_name, importance):
        """动态更新约束重要性"""
        self.constraint_evolution[constraint_name] = importance

    def compute_bias(self, individual, constraint_violation):
        total_penalty = 0
        for constraint_name, violation in constraint_violation.items():
            # 获取动态权重
            dynamic_weight = self.constraint_evolution.get(constraint_name, self.weight)
            total_penalty += dynamic_weight * violation

        return total_penalty
```

### 3. 学习型偏置

```python
class LearningBias(AlgorithmicBias):
    def __init__(self, learning_rate=0.1):
        super().__init__("Learning", 0.1)
        self.learning_rate = learning_rate
        self.pattern_memory = {}

    def learn_from_success(self, successful_solutions):
        """从成功解中学习模式"""
        for solution in successful_solutions:
            pattern = self.extract_pattern(solution)
            if pattern in self.pattern_memory:
                self.pattern_memory[pattern] += self.learning_rate
            else:
                self.pattern_memory[pattern] = self.learning_rate

    def compute_bias(self, individual, context):
        pattern = self.extract_pattern(individual)
        learned_value = self.pattern_memory.get(pattern, 0)
        return self.weight * learned_value
```

## 📈 性能优化建议

### 1. 偏置权重调优

```python
# 网格搜索最优权重
def optimize_bias_weights(problem, bias_types, weight_ranges):
    best_config = None
    best_fitness = float('inf')

    for weights in itertools.product(*weight_ranges):
        # 创建配置
        config = dict(zip(bias_types, weights))

        # 评估配置
        avg_fitness = evaluate_configuration(problem, config)

        if avg_fitness < best_fitness:
            best_fitness = avg_fitness
            best_config = config

    return best_config

# 使用示例
bias_types = ['domain', 'diversity', 'simulated_annealing']
weight_ranges = [
    np.linspace(0.1, 0.5, 5),   # domain bias
    np.linspace(0.05, 0.2, 4),  # diversity bias
    np.linspace(0.1, 0.3, 5)    # SA bias
]

optimal_weights = optimize_bias_weights(problem, bias_types, weight_ranges)
```

### 2. 计算效率优化

```python
# 并行偏置计算
from concurrent.futures import ThreadPoolExecutor

class ParallelBiasManager:
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.biases = {}

    def compute_total_bias_parallel(self, individual, context):
        """并行计算所有偏置"""
        futures = []
        for bias_name, bias in self.biases.items():
            future = self.executor.submit(bias.compute_bias, individual, context)
            futures.append((bias_name, future))

        total_bias = 0
        for bias_name, future in futures:
            try:
                bias_value = future.result(timeout=1.0)
                total_bias += bias_value
            except Exception as e:
                print(f"偏置 {bias_name} 计算失败: {e}")

        return total_bias
```

### 3. 内存优化

```python
# 轻量级偏置实现
class LightweightBias:
    def __init__(self, name, weight, bias_func):
        self.name = name
        self.weight = weight
        self.bias_func = bias_func

    def compute_bias(self, individual, context):
        return self.weight * self.bias_func(individual, context)

# 偏置池管理
class BiasPool:
    def __init__(self, max_size=100):
        self.bias_pool = {}
        self.max_size = max_size

    def get_bias(self, bias_name):
        """获取偏置，如果不存在则创建"""
        if bias_name not in self.bias_pool:
            if len(self.bias_pool) >= self.max_size:
                # 移除最少使用的偏置
                least_used = min(self.bias_pool.items(), key=lambda x: x[1].usage_count)
                del self.bias_pool[least_used[0]]

            self.bias_pool[bias_name] = self.create_bias(bias_name)

        bias = self.bias_pool[bias_name]
        bias.usage_count += 1
        return bias
```

## 🔬 实验案例

### 案例1: 模拟退火偏置评估

```python
# 实验设计
experiment = {
    'problems': [
        'Sphere',          # 单峰
        'Rastrigin',       # 多峰
        'Rosenbrock',      # 狭窄谷
        'Griewank',        # 多峰且可分离
        'Ackley'           # 多峰且不可分离
    ],
    'algorithms': ['GA', 'PSO', 'DE'],
    'bias_configs': [
        {'no_sa': {}},
        {'sa_low': {'weight': 0.05, 'temp': 50.0}},
        {'sa_medium': {'weight': 0.15, 'temp': 100.0}},
        {'sa_high': {'weight': 0.25, 'temp': 200.0}}
    ]
}

# 结果分析
results = run_comprehensive_experiment(experiment)
analyze_results(results)
```

### 案例2: 多偏置组合效果

```python
# 偏置组合测试
bias_combinations = [
    ['domain'],                                    # 仅业务偏置
    ['domain', 'diversity'],                       # 业务+多样性
    ['domain', 'simulated_annealing'],             # 业务+SA
    ['domain', 'diversity', 'simulated_annealing'], # 全部
    ['adaptive_all']                               # 自适应调整
]

performance_comparison = {}
for combo in bias_combinations:
    results = run_with_bias_combination(problem, combo)
    performance_comparison[str(combo)] = {
        'best_fitness': results.best_fitness,
        'convergence_speed': results.convergence_generation,
        'constraint_satisfaction': results.constraint_violation_rate,
        'diversity_score': results.final_diversity
    }
```

## 📋 最佳实践

### 1. 偏置选择原则

```python
def select_biases_guideline(problem_characteristics):
    """偏置选择指导原则"""
    recommendations = []

    # 高维问题
    if problem_characteristics['dimension'] > 100:
        recommendations.extend([
            ('diversity', 0.2, '高维需要多样性维护'),
            'correlation_bias'  # 利用变量相关性
        ])

    # 强约束问题
    if problem_characteristics['constraint_ratio'] > 0.3:
        recommendations.extend([
            ('domain_bias', 0.3, '强约束处理'),
            'repair_bias'      # 约束修复
        ])

    # 多峰问题
    if problem_characteristics['multimodality'] > 0.7:
        recommendations.extend([
            'simulated_annealing',  # 避免局部最优
            'exploration_bias'      # 加强探索
        ])

    return recommendations
```

### 2. 参数调优策略

```python
# 自适应参数调优
class AdaptiveBiasTuner:
    def __init__(self):
        self.tuning_history = []
        self.performance_metrics = []

    def tune_biases(self, optimization_state):
        """基于优化状态调优偏置参数"""
        if optimization_state.is_stuck():
            # 增强探索能力
            self.adjust_bias('diversity', factor=1.2)
            self.adjust_bias('simulated_annealing', factor=1.1)

        elif optimization_state.is_converging():
            # 加强局部搜索
            self.adjust_bias('convergence', factor=1.15)
            self.adjust_bias('exploitation', factor=1.1)

        # 记录调整历史
        self.tuning_history.append({
            'generation': optimization_state.generation,
            'adjustments': self.get_current_adjustments()
        })
```

### 3. 调试和诊断

```python
# 偏置诊断工具
class BiasDiagnostics:
    def __init__(self):
        self.bias_contributions = {}
        self.performance_timeline = []

    def diagnose_bias_effectiveness(self):
        """诊断偏置效果"""
        diagnostics = {
            'dominant_bias': self.find_dominant_bias(),
            'useless_bias': self.find_useless_bias(),
            'conflicting_biases': self.find_conflicts(),
            'recommendations': self.generate_recommendations()
        }
        return diagnostics

    def visualize_bias_impact(self):
        """可视化偏置影响"""
        plt.figure(figsize=(15, 10))

        # 偏置贡献度随时间变化
        plt.subplot(2, 2, 1)
        self.plot_bias_contributions()

        # 性能指标变化
        plt.subplot(2, 2, 2)
        self.plot_performance_metrics()

        # 偏置相关性分析
        plt.subplot(2, 2, 3)
        self.plot_bias_correlations()

        # 权重演化历史
        plt.subplot(2, 2, 4)
        self.plot_weight_evolution()

        plt.tight_layout()
        plt.show()
```

## 🎉 总结

偏置系统为NSGABlack优化库提供了强大的扩展能力：

1. **模块化设计**: 每个偏置都是独立模块，可灵活组合
2. **智能自适应**: 系统能根据优化状态自动调整
3. **元学习优化**: 从历史经验学习最优配置
4. **算法无关性**: 可增强任何优化算法
5. **效果可评估**: 完整的分析和诊断工具

通过合理使用偏置系统，可以显著提升优化算法在各种复杂问题上的性能，实现算法与领域知识的完美融合。

---

*最后更新: 2025年12月*