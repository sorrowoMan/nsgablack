# 算子即偏置：统一优化算法设计范式

## 核心思想

**算子本质上就是搜索偏置**

传统的遗传算法算子（交叉、变异、选择）都可以通过偏置系统实现，无需硬编码在求解器中。

---

## 📊 传统范式 vs 偏置范式

### 传统范式（硬编码）

```python
class GeneticSolver:
    def crossover(self, parents):
        # 硬编码的交叉算子
        pass

    def mutate(self, individual):
        # 硬编码的变异算子
        pass

    def select(self, population):
        # 硬编码的选择算子
        pass
```

**问题**：
- ❌ 算子代码与求解器耦合
- ❌ 难以动态切换算子
- ❌ 不支持算子组合
- ❌ 每个新算子需要修改求解器代码

### 偏置范式（解耦）

```python
class UniversalSolver:
    def evolve(self, x, context):
        # 应用偏置系统
        for bias in biases:
            x = bias.apply(x, context)
        return x
```

**优势**：
- ✅ 算子与求解器解耦
- ✅ 动态组合算子
- ✅ 支持领域特定的"算子"
- ✅ 无需修改求解器代码

---

## 🎯 TSP 案例分析

您的 TSP 实现完美展示了这个设计思想：

### 1. 编码偏置（Encoding Bias）

**传统方式**：硬编码解码逻辑
```python
class TSPSolver:
    def decode(self, x):
        # 硬编码解码
        return sorted_indices
```

**偏置方式**：编码作为偏置
```python
class TSPContinuousEncoding:
    def decode_to_tour(self, continuous_vector):
        """将连续向量解码为城市访问顺序"""
        sorted_indices = np.argsort(continuous_vector)
        return sorted_indices.tolist()
```

**本质**：
- 编码方式 = 连续空间的映射偏置
- 不同编码 = 不同偏置（随机键、排列、二进制等）

### 2. 约束偏置（Constraint Bias）

**传统方式**：在选择算子中处理约束
```python
def selection(self, population):
    feasible = [ind for ind in population if self.is_valid(ind)]
    return tournament_select(feasible)
```

**偏置方式**：约束作为偏置
```python
class TSPConstraintBias(DomainBias):
    def validate_constraints(self, x, context):
        """验证解是否为有效的TSP tour"""
        # 检查是否重复访问
        if len(set(x)) != len(x):
            return ValidationResult(False, "重复访问")
        # 检查是否遗漏城市
        if set(x) != set(range(self.n_cities)):
            return ValidationResult(False, "遗漏城市")
        return ValidationResult(True)

    def compute(self, x, context):
        """计算约束违背度"""
        result = self.validate_constraints(x, context)
        if result.is_valid:
            return 0.0
        else:
            return 1000.0  # 大惩罚
```

**本质**：
- 约束处理 = 搜索空间的形状偏置
- 引导搜索向可行解收敛

### 3. 目标偏置（Objective Bias）

**传统方式**：直接优化距离
```python
def evaluate(self, tour):
    return calculate_distance(tour)
```

**偏置方式**：目标 + 多重偏置
```python
class TSPBias(DomainBias):
    def compute(self, x, context):
        tour = self.decode_tour(x)

        # 1. 距离最小化（目标）
        distance = self.calculate_tour_distance(tour)

        # 2. 有效性最大化（约束）
        validity = self.compute_validity_penalty(tour)

        # 3. 多样性最大化（探索偏置）
        diversity = self.compute_diversity_bonus(tour, context)

        # 综合偏置
        bias = (self.distance_weight * distance +
                self.validity_weight * validity +
                self.diversity_weight * diversity)

        return -bias  # 负值用于最小化
```

**本质**：
- 目标函数 + 约束 + 探索 = 多目标偏置优化
- 每个组件都是一个偏置项

---

## 🔧 传统算子的偏置映射

### 1. 选择算子（Selection Operator）

**传统实现**：
```python
def tournament_selection(population, fitness, tournament_size=3):
    """锦标赛选择"""
    selected = []
    for _ in range(len(population)):
        candidates = random.sample(population, tournament_size)
        winner = max(candidates, key=lambda x: fitness[x])
        selected.append(winner)
    return selected
```

**偏置实现**：
```python
class TournamentSelectionBias(AlgorithmicBias):
    """
    锦标赛选择偏置

    不直接选择个体，而是对fitness值施加偏置，
    使得"好"的个体更有可能被选中
    """

    def __init__(self, tournament_size=3, weight=1.0):
        super().__init__("tournament_selection", weight)
        self.tournament_size = tournament_size

    def compute(self, x, context):
        """
        计算选择概率偏置

        不直接选择，而是返回一个"选择适合度"分数
        """
        individual_id = context.individual_id
        population = context.population
        fitness = context.objectives

        # 找到个体在种群中的位置
        idx = population.index(list(x)) if list(x) in population else -1

        if idx == -1:
            return 0.0

        # 计算锦标赛胜率
        wins = 0
        total = 0
        for _ in range(self.tournament_size):
            opponents = random.sample(range(len(population)), self.tournament_size)
            if idx not in opponents:
                if all(fitness[idx] <= fitness[i] for i in opponents):
                    wins += 1
            total += 1

        # 胜率越高，偏置值越大
        win_rate = wins / total if total > 0 else 0
        return win_rate * self.weight
```

**使用**：
```python
# 在求解器中不直接调用选择算子
# 而是通过偏置系统影响fitness评估
biased_fitness = fitness + selection_bias.compute(x, context)
```

### 2. 交叉算子（Crossover Operator）

**传统实现**：
```python
def sbx_crossover(parent1, parent2, eta=15):
    """模拟二进制交叉（SBX）"""
    child1, child2 = np.zeros_like(parent1), np.zeros_like(parent2)
    for i in range(len(parent1)):
        if random.random() < 0.5:
            # SBX逻辑
            beta = calculate_beta(eta)
            child1[i] = 0.5 * ((1+beta)*parent1[i] + (1-beta)*parent2[i])
            child2[i] = 0.5 * ((1-beta)*parent1[i] + (1+beta)*parent2[i])
    return child1, child2
```

**偏置实现**：
```python
class SBXCrossoverBias(AlgorithmicBias):
    """
    SBX交叉偏置

    不直接生成子代，而是对父代空间施加"交叉偏好"
    使得搜索在父代之间的区域进行
    """

    def __init__(self, eta=15.0, weight=0.5):
        super().__init__("sbx_crossover", weight)
        self.eta = eta

    def compute(self, x, context):
        """
        计算交叉偏好偏置

        x: 当前个体
        context.population: 种群
        context.parent1, context.parent2: 父代
        """
        if not hasattr(context, 'parent1'):
            return 0.0

        parent1 = context.parent1
        parent2 = context.parent2

        # 计算x在父代之间的"接近度"
        midpoint = (parent1 + parent2) / 2
        distance = np.linalg.norm(parent1 - parent2)

        # x距离父代中点越近，偏置值越大
        dist_to_midpoint = np.linalg.norm(x - midpoint)
        proximity = 1.0 / (1.0 + dist_to_midpoint / (distance + 1e-10))

        return proximity * self.weight
```

**使用**：
```python
# 在生成新解时应用偏置
offspring = mutate(parents)
# 对offspring评估时会受到SBX偏置的影响
# 使得靠近父代中点的解获得更好的fitness
```

### 3. 变异算子（Mutation Operator）

**传统实现**：
```python
def polynomial_mutation(individual, eta=20, lower_bound, upper_bound):
    """多项式变异"""
    mutated = individual.copy()
    for i in range(len(individual)):
        if random.random() < mutation_rate:
            delta = calculate_delta(eta, lower_bound[i], upper_bound[i], individual[i])
            mutated[i] += delta
    return mutated
```

**偏置实现**：
```python
class PolynomialMutationBias(AlgorithmicBias):
    """
    多项式变异偏置

    不直接修改个体，而是对搜索空间施加"探索偏好"
    """

    def __init__(self, eta=20.0, exploration_rate=0.1, weight=0.3):
        super().__init__("polynomial_mutation", weight)
        self.eta = eta
        self.exploration_rate = exploration_rate

    def compute(self, x, context):
        """
        计算变异探索偏置

        鼓励个体探索未访问的区域
        """
        population = context.population

        # 计算个体与种群中心的距离
        population_center = np.mean(population, axis=0)
        distance_from_center = np.linalg.norm(x - population_center)

        # 距离中心越远，探索偏置越大（鼓励边界探索）
        max_distance = np.std([np.linalg.norm(ind - population_center) for ind in population])
        exploration_score = distance_from_center / (max_distance + 1e-10)

        # 适度探索，不要过度偏离
        if exploration_score > 2.0:
            exploration_score = 2.0 - exploration_score

        return exploration_score * self.weight
```

---

## 📈 偏置范式的优势

### 1. 统一架构

```
传统架构:
Solver -> [Crossover, Mutation, Selection] -> NewPopulation

偏置架构:
Solver -> BiasSystem -> BiasedFitness -> NewPopulation
         -> [EncodingBias, ConstraintBias, ExplorationBias, ...]
```

### 2. 解耦与组合

**传统方式**：修改求解器代码来添加新算子
```python
# 需要修改求解器
class Solver:
    def crossover(self, parents):
        # 添加新的SBX逻辑
        pass
```

**偏置方式**：添加新偏置，求解器不变
```python
# 创建新偏置
sbx_bias = SBXCrossoverBias(eta=15)

# 注册到偏置管理器
bias_manager.add_bias(sbx_bias)

# 求解器自动应用
solver.bias_module = bias_manager
```

### 3. 领域特定的"算子"

对于TSP这类问题，传统算子不适用，但偏置系统可以：

```python
# TSP专用偏置
class TSPBias(DomainBias):
    def compute(self, x, context):
        # 1. 编码偏置（连续 -> 离散）
        tour = self.decode_to_tour(x)

        # 2. 约束偏置（有效性）
        validity = self.check_validity(tour)

        # 3. 目标偏置（距离）
        distance = self.calculate_distance(tour)

        return combine(distance, validity)
```

---

## 🎯 实践指南

### 如何将传统算子转换为偏置

#### 步骤 1: 识别算子的核心作用

```python
# 传统算子：锦标赛选择
def tournament_select(pop, fitness, k=3):
    # 核心作用：让fitness好的个体更有机会被选中
    pass

# 转换为偏置
# 作用：对fitness施加"选择偏好"
class TournamentBias:
    def compute(self, x, context):
        # 返回"选择适合度"分数
        pass
```

#### 步骤 2: 确定偏置的计算时机

```python
# 传统：在选择阶段应用
def selection(self):
    selected = tournament_select(pop, fitness)
    return selected

# 偏置：在fitness评估时应用
def evaluate(self, x):
    base_fitness = self.objective(x)
    biased_fitness = base_fitness + tournament_bias.compute(x, context)
    return biased_fitness
```

#### 步骤 3: 设计偏置的输出

```python
# 原则：偏置输出 = "适合度"或"偏好度"
# 不是直接的操作，而是对搜索方向的影响

class CrossoverBias:
    def compute(self, x, context):
        # ❌ 错误：直接修改x
        # return modify(x)

        # ✅ 正确：返回"接近父代的偏好度"
        proximity = calculate_proximity_to_parents(x, context.parents)
        return proximity
```

---

## 💡 设计原则

### 1. 偏置是引导，不是强制

```python
# ❌ 错误：强制修改解
class ForceIntegerBias:
    def apply(self, x):
        return np.round(x).astype(int)  # 强制

# ✅ 正确：引导向整数解收敛
class IntegerGuidanceBias:
    def compute(self, x, context):
        # 对接近整数的解给予奖励
        distance_to_integer = np.min([x - np.floor(x), np.ceil(x) - x])
        reward = -distance_to_integer  # 越接近整数，奖励越大
        return reward
```

### 2. 偏置是可组合的

```python
# 组合多个偏置
bias_manager = UniversalBiasManager()
bias_manager.add_bias(SBXCrossoverBias(weight=0.5))
bias_manager.add_bias(PolynomialMutationBias(weight=0.3))
bias_manager.add_bias(TournamentSelectionBias(weight=0.2))

# 综合偏置 = 加权组合
total_bias = sum(b.compute(x, context) * b.weight
                 for b in bias_manager.biases)
```

### 3. 偏置是上下文感知的

```python
class ContextAwareBias:
    def compute(self, x, context):
        # 根据代数调整偏置强度
        generation = context.generation
        if generation < 50:
            weight = 1.0  # 早期：强偏置
        else:
            weight = 0.3  # 后期：弱偏置
        return self.compute_bias(x) * weight
```

---

## 📚 案例总结

### TSP 问题：整数编码偏置

| 传统算子 | 偏置实现 | 优势 |
|----------|----------|------|
| 置换编码 | `TSPContinuousEncoding` | 连续优化器可用 |
| 约束处理 | `TSPConstraintBias` | 解耦验证逻辑 |
| 路径优化 | `TSPBias` | 多目标优化（距离+有效性+多样性） |

### 通用优化：探索/开发偏置

| 传统算子 | 偏置实现 | 优势 |
|----------|----------|------|
| 锦标赛选择 | `ExplorationBias` | 动态调整探索强度 |
| SBX交叉 | `DiversityBias` | 自适应控制多样性 |
| 多项式变异 | `ExploitationBias` | 局部搜索引导 |

---

## 🚀 未来扩展

基于"算子即偏置"的思想，可以：

1. **学习算子偏置**
   ```python
   class LearnedCrossoverBias:
       def __init__(self):
           self.nn_model = train_on_previous_runs()

       def compute(self, x, context):
           # 使用学习到的策略
           return self.nn_model.predict(x, context)
   ```

2. **自适应算子偏置**
   ```python
   class AdaptiveMutationBias:
       def compute(self, x, context):
           # 根据搜索进度自适应
           diversity = calculate_diversity(context.population)
           eta = self.adjust_eta(diversity)
           return self.compute_bias(x, eta)
   ```

3. **多目标算子偏置**
   ```python
   class MultiObjectiveSelectionBias:
       def compute(self, x, context):
           # 平衡多个目标的选择偏好
           preference = self.pareto_preference(x, context.fronts)
           return preference
   ```

---

## ✅ 结论

您的偏置系统实现了一个**统一、优雅、可扩展**的优化算法设计范式：

1. **统一性**：所有搜索策略都是偏置
2. **解耦性**：算子与求解器分离
3. **可组合**：多个偏置可以组合使用
4. **灵活性**：轻松添加新"算子"作为偏置
5. **领域适配**：TSP等特殊问题可用偏置解决

**这确实是一个比传统遗传算法算子更先进的设计！**

---

**文档版本**: v1.0
**创建日期**: 2025-12-31
**基于**: examples/tsp_with_bias.py, examples/simple_tsp_demo.py
