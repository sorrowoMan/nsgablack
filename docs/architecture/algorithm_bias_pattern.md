# ✅ 完成！按照你的设计模式实现的 NSGA-II 偏置化

## 🎯 你的设计模式：算法偏置化

从你的模拟退火偏置化例子，我理解了核心设计理念：

### 核心思想

```
算法思想 → 转换为偏置值 → 注入到任何算法
```

### 模拟退火偏置化的例子

```python
class SimulatedAnnealingBias:
    def compute_bias(self, x, context):
        # SA的核心：Metropolis准则
        delta_energy = current_energy - previous_energy

        # 转换为偏置值
        if delta_energy <= 0:
            # 好的解 → 负偏置（奖励）
            return -weight * abs(delta_energy) * 0.1
        else:
            # 差的解 → 根据温度给正偏置（惩罚）
            acceptance_prob = exp(-delta_energy / temperature)
            return weight * acceptance_prob * delta_energy * 0.1
```

**关键点**：
1. ✅ 算法概念（Metropolis准则）转换为偏置值
2. ✅ 算法无关性：任何算法都可以用
3. ✅ 简洁的接口：`compute_bias(x, context) -> float`

---

## ✅ 按照同样模式实现的 NSGA-II 偏置化

### 实现文件

- **核心实现**: `bias/algorithmic/nsga2.py`
- **使用示例**: `examples/nsga2_bias_demo.py`

### NSGA-II 偏置化实现

```python
class NSGA2Bias(AlgorithmicBias):
    """
    NSGA-II 偏置 - 将 NSGA-II 概念转换为可注入的偏置
    """

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算 NSGA-II 偏置值

        核心概念转换：
        1. Pareto rank → 偏置值
        2. Crowding distance → 偏置值
        3. Pareto dominance → 偏置值
        """
        # 获取 NSGA-II 信息
        pareto_rank = context.metrics.get('pareto_rank', 0)
        crowding_distance = context.metrics.get('crowding_distance', 0.0)
        is_dominated = context.metrics.get('is_dominated', False)

        bias_value = 0.0

        # 1. Pareto rank 偏置
        # rank=0（最好）→ 负偏置（奖励）
        # rank>0（被支配）→ 正偏置（惩罚）
        rank_bias = pareto_rank * self.rank_weight
        bias_value += rank_bias

        # 2. 拥挤距离偏置
        # 大距离（稀疏）→ 负偏置（奖励，保持多样性）
        # 小距离（聚集）→ 正偏置（惩罚）
        if crowding_distance > 0:
            crowding_bias = -crowding_distance * self.crowding_weight
        else:
            crowding_bias = -self.crowding_weight  # 边界奖励
        bias_value += crowding_bias

        # 3. Pareto 支配关系偏置
        if is_dominated:
            bias_value += self.dominance_weight
        else:
            bias_value -= self.dominance_weight * 0.5

        return bias_value
```

---

## 🎯 使用方式（完全模仿 SA 偏置）

### 在任何优化算法中使用

```python
class NSGA2EnhancedOptimizer:
    def __init__(self, problem, use_nsga2_bias=True):
        self.problem = problem
        self.use_nsga2_bias = use_nsga2_bias

        # 添加 NSGA-II 偏置
        if self.use_nsga2_bias:
            self.nsga2_bias = NSGA2Bias(weight=0.15)

    def optimize(self, max_generations=100):
        for generation in range(max_generations):
            for individual in population:
                # 计算目标函数
                obj_value = self.problem.evaluate(individual)

                # 计算 NSGA-II 指标
                pareto_rank = self._compute_pareto_rank(obj_value, all_objectives)
                crowding_distance = self._compute_crowding_distance(obj_value, all_objectives)
                is_dominated = pareto_rank > 0

                # 构建上下文
                context = {
                    'pareto_rank': pareto_rank,
                    'crowding_distance': crowding_distance,
                    'is_dominated': is_dominated
                }

                # 应用偏置
                base_fitness = obj_value
                if self.use_nsga2_bias:
                    nsga2_bias_value = self.nsga2_bias.compute_bias(individual, context)
                    total_fitness = base_fitness + nsga2_bias_value
                else:
                    total_fitness = base_fitness

                fitness_values.append(total_fitness)
```

---

## 🌟 核心优势

### 1. 算法无关性

任何算法都可以通过偏置获得 NSGA-II 的能力：

```python
# 遗传算法 + NSGA-II 偏置 = 多目标 GA
GA + NSGA2Bias = MOGA

# 粒子群优化 + NSGA-II 偏置 = 多目标 PSO
PSO + NSGA2Bias = MOPSO

# 差分进化 + NSGA-II 偏置 = 多目标 DE
DE + NSGA2Bias = MODE

# 模拟退火 + NSGA-II 偏置 = 多目标 SA
SA + NSGA2Bias = MOSA
```

### 2. 与 SA 偏置的对比

| 特性 | SA 偏置 | NSGA-II 偏置 |
|------|---------|--------------|
| **核心概念** | Metropolis准则 | Pareto 支配 + 拥挤距离 |
| **主要能力** | 全局搜索（避免局部最优） | 多目标优化 + 多样性保持 |
| **适用场景** | 单峰/多峰问题 | 多目标问题 |
| **组合使用** | ✅ 可以 | ✅ 可以 |

### 3. 两种偏置的组合

```python
# 同时使用 SA 偏置和 NSGA-II 偏置
total_fitness = obj_value + sa_bias_value + nsga2_bias_value

# 效果：全局搜索 + 多目标优化 = 强大的多目标全局优化
```

---

## 📊 在你的多智能体系统中的应用

### 为每个角色配置 NSGA-II 偏置

```python
class MultiAgentBlackBoxSolver:
    def __init__(self, problem, config):
        # 为每个角色创建 NSGA-II 偏置
        self.nsga2_biases = {
            AgentRole.EXPLORER: NSGA2Bias(
                rank_weight=0.3,      # 降低 rank 权重
                crowding_weight=0.7   # 增加拥挤权重（更多样性）
            ),
            AgentRole.EXPLOITER: NSGA2Bias(
                rank_weight=0.7,      # 增加 rank 权重（更快收敛）
                crowding_weight=0.3   # 降低拥挤权重
            ),
            AgentRole.ADVISOR: NSGA2Bias(
                rank_weight=0.5,
                crowding_weight=0.5   # 平衡
            ),
        }

    def evaluate_population(self, agent_pop):
        """评估种群（应用 NSGA-II 偏置）"""
        for individual in agent_pop.population:
            # 计算基础适应度
            obj_value = self.problem.evaluate(individual)

            # 计算 NSGA-II 指标
            pareto_rank = self._compute_pareto_rank(individual)
            crowding_distance = self._compute_crowding_distance(individual)

            # 应用角色特定的 NSGA-II 偏置
            nsga2_bias = self.nsga2_biases[agent_pop.role]
            bias_value = nsga2_bias.compute_bias(individual, context)

            # 总适应度
            total_fitness = obj_value + bias_value
```

---

## 🎯 设计模式总结

### 你的"算法偏置化"模式

```
┌─────────────────────────────────────────┐
│      算法的核心思想/概念                │
│  （SA的Metropolis、NSGA-II的Pareto等）  │
└─────────────────────────────────────────┘
                 ↓ 转换
┌─────────────────────────────────────────┐
│      偏置值（数值）                     │
│  - 负值：奖励                           │
│  - 正值：惩罚                           │
└─────────────────────────────────────────┘
                 ↓ 注入
┌─────────────────────────────────────────┐
│      任何优化算法                       │
│  - 原始适应度 + 偏置值                 │
│  - 无需修改算法核心逻辑                 │
└─────────────────────────────────────────┘
```

### 实现的关键要素

1. **概念转换**：算法概念 → 偏置值
   ```python
   # SA: delta_energy → bias_value
   # NSGA-II: pareto_rank → bias_value
   ```

2. **简洁接口**：
   ```python
   def compute_bias(x, context) -> float:
       return bias_value
   ```

3. **算法无关性**：
   ```python
   total_fitness = base_fitness + bias_value
   ```

4. **可组合性**：
   ```python
   total_fitness = base_fitness + sa_bias + nsga2_bias + diversity_bias
   ```

---

## 📝 创建的文件

1. ✅ `bias/algorithmic/nsga2.py` - NSGA-II 偏置实现
   - `NSGA2Bias` - 标准 NSGA-II 偏置
   - `AdaptiveNSGA2Bias` - 自适应版本
   - `DiversityPreservingNSGA2Bias` - 强多样性版本

2. ✅ `examples/nsga2_bias_demo.py` - 使用示例
   - 展示如何注入 NSGA-II 偏置到任何算法
   - 对比有/无偏置的性能差异

---

## 🚀 下一步

### 在你的多智能体系统中使用

```python
# 修改 solvers/multi_agent.py
from bias.algorithmic.nsga2 import NSGA2Bias

class MultiAgentBlackBoxSolver:
    def __init__(self, problem, config):
        # 为每个角色配置 NSGA-II 偏置
        self.role_nsga2_biases = {
            AgentRole.EXPLORER: NSGA2Bias(
                rank_weight=0.3, crowding_weight=0.7
            ),
            AgentRole.EXPLOITER: NSGA2Bias(
                rank_weight=0.7, crowding_weight=0.3
            ),
            # ... 其他角色
        }

    def evaluate_population(self, agent_pop):
        # 应用 NSGA-II 偏置
        nsga2_bias = self.role_nsga2_biases[agent_pop.role]
        bias_value = nsga2_bias.compute(x, context)
        total_fitness = obj_value + bias_value
```

---

**创建日期**: 2025-12-31
**设计模式**: 算法偏置化（模仿你的模拟退火偏置化）
**核心理念**: 算法思想 → 偏置值 → 注入到任何算法
