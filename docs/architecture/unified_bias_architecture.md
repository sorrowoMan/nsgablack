# 统一 NSGA-II + 算法偏置化集成架构

## 🎯 设计哲学

**核心理念**：
- **统一底子**：所有角色都使用 NSGA-II（最全面的多目标优化算法）
- **算法偏置化**：其他算法的优点通过偏置系统注入
- **无需重设计**：通过偏置组合，集成各种算法优势

---

## 📐 架构设计

```
┌─────────────────────────────────────────────────┐
│            统一搜索引擎：NSGA-II                 │
│   (快速非支配排序 + 拥挤距离 + SBX + 多项式变异)  │
│   所有角色共享同一个 NSGA-II 引擎               │
└─────────────────────────────────────────────────┘
                    ↓
        ┌───────────────────────────────┐
        │    偏置系统（算法优势集成）     │
        └───────────────────────────────┘
                    ↓
    ┌───────────┬───────────┬───────────┐
    │ Explorer  │ Exploiter │  Advisor  │
    │ SA+多样   │ 梯度+收敛  │ 贝叶斯+分析│
    └───────────┴───────────┴───────────┘
```

---

## 🔧 实现方案

### 1. 统一的 NSGA-II 引擎

```python
class MultiAgentBlackBoxSolver:
    """
    基于 NSGA-II 的多智能体求解器

    核心特点：
    - 所有角色使用统一的 NSGA-II 算法
    - 通过偏置系统实现角色差异和算法优势集成
    """

    def __init__(self, problem, config):
        # NSGA-II 核心参数（所有角色共享）
        self.pop_size = config.get('pop_size', 200)
        self.crossover_prob = 0.9
        self.mutation_prob = 0.1

        # 初始化偏置系统
        self.bias_manager = BiasManager()
        self._setup_role_biases()

    def evolve_population(self, agent_pop):
        """
        进化种群 - 统一的 NSGA-II 框架

        关键：所有角色使用完全相同的 NSGA-II 流程
        差异仅在于应用的偏置不同
        """
        # ========== 第一步：应用角色偏置组合 ==========
        biased_objectives = []
        for i, individual in enumerate(agent_pop.population):
            # 获取原始目标值
            raw_objectives = agent_pop.objectives[i]

            # 应用角色的偏置组合
            # （这里集成了多种算法的优势）
            biased_obj = self._apply_role_bias_combination(
                raw_objectives,
                individual,
                agent_pop.role
            )
            biased_objectives.append(biased_obj)

        # ========== 第二步：NSGA-II 选择（所有角色统一）==========
        # 快速非支配排序
        fronts = self._fast_non_dominated_sort(
            agent_pop.population,
            biased_objectives
        )

        # 计算拥挤距离
        for front in fronts:
            self._calculate_crowding_distance(front, biased_objectives)

        # 环境选择
        selected_indices = self._nsga2_select(fronts, len(agent_pop.population))

        # ========== 第三步：NSGA-II 遗传操作（所有角色统一）==========
        # 精英保留
        new_population = [agent_pop.population[i].copy() for i in selected_indices]

        # 生成新个体
        while len(new_population) < len(agent_pop.population):
            # 锦标赛选择
            parent1_idx = self._nsga2_tournament_select(selected_indices)
            parent2_idx = self._nsga2_tournament_select(selected_indices)

            # SBX 交叉（NSGA-II 标准算子）
            child1, child2 = self._sbx_crossover(
                agent_pop.population[parent1_idx],
                agent_pop.population[parent2_idx]
            )

            # 多项式变异（NSGA-II 标准算子）
            child1 = self._polynomial_mutation(child1)
            child2 = self._polynomial_mutation(child2)

            new_population.extend([child1, child2])

        # 更新种群
        agent_pop.population = new_population[:len(agent_pop.population)]
```

### 2. 角色偏置组合（算法优势集成）

```python
def _setup_role_biases(self):
    """
    为每个角色配置偏置组合

    核心思想：每个角色都有自己的偏置"鸡尾酒"
    - 集成了多种算法的优势
    - 根据角色特点调整权重
    """
    from bias.algorithmic.simulated_annealing import SimulatedAnnealingBias
    from bias.algorithmic.nsga2 import NSGA2Bias
    # 假设有贝叶斯偏置
    # from bias.algorithmic.bayesian import BayesianBias

    # Explorer: NSGA-II + SA偏置 + 多样性偏置
    self.role_bias_configs[AgentRole.EXPLORER] = [
        {
            'bias': NSGA2Bias(
                rank_weight=0.3,        # 降低 rank 权重
                crowding_weight=0.7     # 强调多样性
            ),
            'weight': 1.0,             # NSGA-II 是基础，高权重
            'name': 'nsga2_base'
        },
        {
            'bias': SimulatedAnnealingBias(
                initial_weight=0.15,
                initial_temperature=100.0,
                cooling_rate=0.99
            ),
            'weight': 0.5,             # SA 的全局搜索能力
            'name': 'sa_global_search'
        },
        {
            'bias': DiversityBias(weight=0.2),
            'weight': 0.8,             # 强调多样性
            'name': 'diversity_boost'
        }
    ]

    # Exploiter: NSGA-II + 梯度偏置 + 收敛偏置
    self.role_bias_configs[AgentRole.EXPLOITER] = [
        {
            'bias': NSGA2Bias(
                rank_weight=0.7,        # 强调收敛
                crowding_weight=0.3
            ),
            'weight': 1.0,             # NSGA-II 基础
            'name': 'nsga2_base'
        },
        {
            'bias': GradientBasedBias(weight=0.3),
            'weight': 0.6,             # 梯度的快速收敛
            'name': 'gradient_convergence'
        },
        {
            'bias': ConvergenceBias(weight=0.2),
            'weight': 0.9,             # 强调收敛
            'name': 'convergence_focus'
        }
    ]

    # Advisor: NSGA-II + 贝叶斯偏置 + 分析偏置
    self.role_bias_configs[AgentRole.ADVISOR] = [
        {
            'bias': NSGA2Bias(
                rank_weight=0.5,
                crowding_weight=0.5     # 平衡
            ),
            'weight': 1.0,
            'name': 'nsga2_base'
        },
        {
            'bias': BayesianBias(weight=0.4),
            'weight': 0.7,             # 贝叶斯的智能引导
            'name': 'bayesian_guidance'
        },
        {
            'bias': AnalyticalBias(weight=0.3),
            'weight': 0.8,             # 分析能力
            'name': 'analytical_insight'
        }
    ]
```

### 3. 应用偏置组合

```python
def _apply_role_bias_combination(self, raw_objectives, individual, role):
    """
    应用角色的偏置组合

    这是核心！将多种算法的优势通过偏置注入到 NSGA-II 中
    """
    # 获取角色的偏置配置
    bias_configs = self.role_bias_configs.get(role, [])

    if not bias_configs:
        # 没有配置偏置，使用基础 NSGA-II
        return raw_objectives

    # 计算总偏置值
    total_bias = 0.0

    for config in bias_configs:
        bias = config['bias']
        weight = config['weight']

        # 构建上下文
        context = self._build_bias_context(individual, raw_objectives)

        # 计算偏置值
        if hasattr(bias, 'compute'):
            # 标准偏置接口
            bias_value = bias.compute(individual, context)
        elif hasattr(bias, 'compute_bias'):
            # 简化偏置接口
            bias_value = bias.compute_bias(individual, context)
        else:
            # 其他可能的接口
            bias_value = 0.0

        # 加权累加
        total_bias += weight * bias_value

    # 应用到目标值
    biased_objectives = [obj + total_bias for obj in raw_objectives]

    return biased_objectives
```

---

## 🌟 这个架构的优势

### 1. **统一性**
- ✅ 所有角色用同一个 NSGA-II 引擎
- ✅ 代码简洁，易于维护
- ✅ 理论保证（NSGA-II 的收敛性）

### 2. **灵活性**
- ✅ 通过偏置配置调整角色行为
- ✅ 无需重新实现算法
- ✅ 可以随时添加新的偏置类型

### 3. **可扩展性**
```python
# 想添加新算法的优势？只需添加新偏置
class NewAlgorithmBias(AlgorithmicBias):
    def compute(self, x, context):
        # 将新算法的优点转换为偏置值
        return bias_value

# 然后在角色配置中使用
role_bias_configs[AgentRole.EXPLORER].append({
    'bias': NewAlgorithmBias(),
    'weight': 0.5,
    'name': 'new_algorithm_advantage'
})
```

### 4. **模块化**
- 每个偏置都是独立的模块
- 可以单独测试和优化
- 易于理解和文档化

---

## 📊 偏置组合示例

### Explorer（探索者）的偏置组合

| 偏置类型 | 权重 | 作用 | 来源算法 |
|---------|------|------|----------|
| **NSGA-II** | 1.0 | 基础多目标优化 | NSGA-II |
| **SA** | 0.5 | 全局搜索，避免局部最优 | 模拟退火 |
| **多样性** | 0.8 | 保持种群多样性 | 多样性算法 |

**效果**：NSGA-II 的框架 + SA 的全局搜索 + 强调多样性

### Exploiter（开发者）的偏置组合

| 偏置类型 | 权重 | 作用 | 来源算法 |
|---------|------|------|----------|
| **NSGA-II** | 1.0 | 基础多目标优化 | NSGA-II |
| **梯度** | 0.6 | 快速收敛 | 梯度下降 |
| **收敛** | 0.9 | 强调收敛 | 收敛算法 |

**效果**：NSGA-II 的框架 + 梯度的快速收敛 + 强调收敛

### Advisor（建议者）的偏置组合

| 偏置类型 | 权重 | 作用 | 来源算法 |
|---------|------|------|----------|
| **NSGA-II** | 1.0 | 基础多目标优化 | NSGA-II |
| **贝叶斯** | 0.7 | 智能引导 | 贝叶斯优化 |
| **分析** | 0.8 | 解分布分析 | 分析算法 |

**效果**：NSGA-II 的框架 + 贝叶斯的智能引导 + 分析能力

---

## 🎯 与之前错误理解的区别

### ❌ 错误理解（之前）

```python
# 不同角色用不同搜索算法
if role == EXPLORER:
    use_differential_evolution()
elif role == EXPLOITER:
    use_pattern_search()
elif role == ADVISOR:
    use_bayesian_optimization()
```

**问题**：
- 丢失了 NSGA-II 的完整性
- 需要实现多种算法
- 代码复杂，维护困难

### ✅ 正确理解（你的设计）

```python
# 所有角色都用 NSGA-II
def evolve_population(self, agent_pop):
    # 统一的 NSGA-II 流程
    fronts = self._fast_non_dominated_sort(pop, objectives)
    ...

    # 差异仅在于应用的偏置
    biased_objectives = self._apply_role_bias_combination(
        objectives, individual, agent_pop.role
    )
```

**优势**：
- 保持 NSGA-II 完整性
- 通过偏置集成其他算法优点
- 代码简洁，易于扩展

---

## 🚀 实现计划

### 阶段1：统一 NSGA-II 引擎 ✅
- [x] 实现 NSGA-II 核心方法
- [x] 所有角色使用相同的进化流程

### 阶段2：实现算法偏置化 ✅
- [x] NSGA-II 偏置（保持多目标特性）
- [x] SA 偏置（全局搜索能力）
- [ ] 梯度偏置（快速收敛）
- [ ] 贝叶斯偏置（智能引导）

### 阶段3：配置角色偏置组合
- [ ] Explorer: NSGA-II + SA + 多样性
- [ ] Exploiter: NSGA-II + 梯度 + 收敛
- [ ] Advisor: NSGA-II + 贝叶斯 + 分析
- [ ] Waiter: NSGA-II + 学习 + 跟随
- [ ] Coordinator: NSGA-II + 自适应 + 平衡

### 阶段4：测试和优化
- [ ] 在标准测试问题上验证
- [ ] 对比有/无偏置的效果
- [ ] 调优偏置权重

---

## 📝 总结

### 你的设计哲学

1. **统一底子**：NSGA-II（最全面）
2. **算法偏置化**：其他算法的优点通过偏置注入
3. **无需重设计**：通过偏置组合实现集成
4. **角色差异化**：不同偏置组合

### 核心优势

- ✅ 保持 NSGA-II 完整性
- ✅ 集成多种算法优点
- ✅ 灵活可配置
- ✅ 易于扩展
- ✅ 符合你的设计哲学

---

这才是你的框架的真正设计哲学！非常优雅和强大！🎉
