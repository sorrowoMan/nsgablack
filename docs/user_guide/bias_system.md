# 偏置系统 v2.0 使用指南

## 概述

偏置系统 v2.0 是对原有偏置模块的重大升级，实现了**算法偏置**和**业务偏置**的分离，提供了更强大、更灵活、更可复用的优化引导机制。

## 核心创新

### 1. **双重架构设计**

```
传统偏置：
evaluate(x) = f(x) + bias(x)

新架构：
evaluate(x) = f(x) + algorithmic_bias(x) + domain_bias(x)
```

- **算法偏置 (Algorithmic Bias)**：关注优化算法本身的效率和性能
- **业务偏置 (Domain Bias)**：关注实际业务问题的约束、偏好和目标

### 2. **高度可复用**

算法偏置可以在不同问题间复用，业务偏置针对特定领域定制，两者灵活组合。

### 3. **信号驱动偏置（需要能力层信号）**

有一类算法偏置并不“自产”关键评估信号，而是消费能力层（插件/外部评估器）注入到 `context.metrics` 的统计量（例如 `mc_std`、代理模型不确定性等）。

- 这类偏置必须与信号提供方配套（推荐通过 suite 的权威组合入口完成装配）
- 详见：`docs/user_guide/signal_driven_bias.md`

## 快速开始

### 基础使用

```python
from nsgablack.bias import UniversalBiasManager, OptimizationContext
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII

# 创建问题
problem = YourProblem()

# 创建偏置管理器
bias_manager = UniversalBiasManager()

# 添加算法偏置
bias_manager.algorithmic_manager.add_bias(DiversityBias(weight=0.2))
bias_manager.algorithmic_manager.add_bias(ConvergenceBias(weight=0.1))

# 添加业务偏置
constraint_bias = ConstraintBias(weight=2.0)
constraint_bias.add_hard_constraint(your_constraint_function)
bias_manager.domain_manager.add_bias(constraint_bias)

# 使用偏置的求解器
solver = YourBiasEnhancedSolver(problem, bias_manager)
result = solver.run()
```

### 使用模板

```python
from nsgablack.bias.library import create_bias_manager_from_template

# 使用机器学习模板
bias_manager = create_bias_manager_from_template('machine_learning')

# 自定义参数
bias_manager = create_bias_manager_from_template(
    'financial_optimization',
    customizations={
        'algorithmic': {'parameters': {'precision_radius': 0.03}},
        'domain': {'parameters': {'weight': 1.5}}
    }
)
```

### 快速函数

```python
from nsgablack.bias.library import quick_engineering_bias, quick_ml_bias

# 快速创建工程设计偏置
eng_bias = quick_engineering_bias(
    safety_constraints=[your_safety_function],
    reliability_weight=3.0
)

# 快速创建机器学习偏置
ml_bias = quick_ml_bias(
    accuracy_weight=5.0,
    time_limit=3600,
    memory_limit=8.0
)
```

## 算法偏置详解

### 1. **多样性偏置 (DiversityBias)**

促进种群多样性，避免早熟收敛。

```python
diversity_bias = DiversityBias(
    weight=0.2,           # 偏置权重
    metric='euclidean'    # 距离度量
)
```

**适用场景**：
- 多模态优化问题
- 需要探索多个解的问题
- 避免陷入局部最优

### 2. **收敛性偏置 (ConvergenceBias)**

根据迭代阶段调整收敛倾向。

```python
convergence_bias = ConvergenceBias(
    weight=0.1,        # 偏置权重
    early_gen=10,       # 早期不偏置
    late_gen=50        # 后期加强偏置
)
```

**适用场景**：
- 时间敏感的优化问题
- 需要快速收敛的问题
- 后期精度要求高的问题

### 3. **探索性偏置 (ExplorationBias)**

检测停滞并增加探索倾向。

```python
exploration_bias = ExplorationBias(
    weight=0.1,                # 偏置权重
    stagnation_threshold=20    # 停滞阈值
)
```

**适用场景**：
- 复杂的优化地形
- 容易早熟收敛的问题
- 需要全局搜索的问题

### 4. **精度偏置 (PrecisionBias)**

在好解周围进行精细搜索。

```python
precision_bias = PrecisionBias(
    weight=0.1,             # 偏置权重
    precision_radius=0.05   # 精度搜索半径
)

# 添加已知的好解
precision_bias.add_good_solution(np.array([1.0, 2.0, 3.0]))
```

**适用场景**：
- 需要高精度解的问题
- 已知一些好解的问题
- 局部精化阶段

## 业务偏置详解

### 1. **约束偏置 (ConstraintBias)**

处理各种类型的约束。

```python
constraint_bias = ConstraintBias(weight=2.0)

# 硬约束：违反则严重惩罚
constraint_bias.add_hard_constraint(lambda x: max(0, stress_limit - calculate_stress(x)))

# 软约束：违反则适度惩罚
constraint_bias.add_soft_constraint(lambda x: max(0, cost_limit - calculate_cost(x)))

# 偏好约束：满足则奖励
constraint_bias.add_preferred_constraint(lambda x: calculate_manufacturability(x))
```

**约束类型**：
- **硬约束**：必须满足，违反时大惩罚
- **软约束**：尽量满足，违反时适度惩罚
- **偏好约束**：满足时给予奖励

### 2. **偏好偏置 (PreferenceBias)**

体现业务偏好和目标。

```python
preference_bias = PreferenceBias(weight=0.5)

# 设置偏好
preference_bias.set_preference('reliability', 'maximize', weight=2.0)
preference_bias.set_preference('cost', 'minimize', weight=1.5)
preference_bias.set_preference('manufacturing_time', 'minimize', weight=1.0)
```

**偏好类型**：
- **最小化**：值越小越好
- **最大化**：值越大越好

### 3. **目标偏置 (ObjectiveBias)**

引导向理想目标方向。

```python
objective_bias = ObjectiveBias(weight=1.0)

# 设置目标值和方向
objective_bias.set_target('performance', target_value=0.95, direction='maximize')
objective_bias.set_target('error_rate', target_value=0.01, direction='minimize')
```

## 偏置库

### 算法偏置库

```python
from nsgablack.bias.library import BiasFactory, ALGORITHMIC_BIAS_LIBRARY

# 列出可用的算法偏置
for name, info in ALGORITHMIC_BIAS_LIBRARY.items():
    print(f"{name}: {info['description']}")
    print(f"  适用场景: {info['use_case']}")
    print(f"  默认参数: {info['default_params']}")
```

可用的算法偏置：
- `diversity_promotion` - 促进多样性
- `fast_convergence` - 快速收敛
- `precision_search` - 精度搜索
- `balanced_exploration` - 平衡探索
- `late_precision` - 后期精度

### 业务偏置库

```python
from nsgablack.bias.library import DOMAIN_BIAS_LIBRARY

# 列出可用的业务偏置
for name, info in DOMAIN_BIAS_LIBRARY.items():
    print(f"{name}: {info['description']}")
    print(f"  约束: {info['constraints']}")
    print(f"  偏好: {info['preferences']}")
```

可用的业务偏置：
- `engineering_design` - 工程设计
- `financial_optimization` - 金融优化
- `supply_chain` - 供应链优化
- `machine_learning` - 机器学习
- `scheduling` - 调度优化
- `portfolio_optimization` - 投资组合优化

## 偏置组合

### 偏置组合器

```python
from nsgablack.bias.library import BiasComposer

composer = BiasComposer()

# 添加算法偏置
composer.add_algorithmic_bias_from_config('diversity_promotion', weight=0.15)
composer.add_algorithmic_bias_from_config('fast_convergence', early_gen=5)

# 添加业务偏置
composer.add_domain_bias_from_config('financial_optimization', weight=1.5)

# 组合计算
bias = composer.compose(x, context, alg_weight=0.3, domain_weight=0.7)
```

### 动态权重调整

```python
# 根据优化状态调整权重
bias_manager.set_bias_weights(algorithmic_weight=0.5, domain_weight=0.5)

# 自动调整
optimization_state = {
    'is_stuck': True,      # 陷入局部最优
    'is_violating_constraints': False  # 没有违反约束
}
bias_manager.adjust_weights(optimization_state)
```

## 偏置模板系统

### 内置模板

```python
from nsgablack.bias.library import (
    BASIC_ENGINEERING_TEMPLATE,
    FINANCIAL_OPTIMIZATION_TEMPLATE,
    MACHINE_LEARNING_TEMPLATE
)
```

### 创建自定义模板

```python
CUSTOM_TEMPLATE = {
    'algorithmic': {
        'type': 'diversity_convergence_mix',
        'parameters': {
            'diversity_weight': 0.2,
            'convergence_weight': 0.1
        }
    },
    'domain': {
        'type': 'your_domain_type',
        'parameters': {
            # 你的参数
        }
    }
}
```

## 实际应用案例

### 案例1：机械零件优化

```python
from nsgablack.bias.library import quick_engineering_bias

# 创建偏置
bias_manager = quick_engineering_bias(
    safety_constraints=[
        lambda x: max(0, 200 - calculate_stress(x)),      # 应力约束
        lambda x: max(0, 10 - calculate_displacement(x))   # 位移约束
    ],
    manufacturing_constraints=[
        lambda x: max(0, min_feature_size - x[0]),         # 最小特征尺寸
        lambda x: max(0, tolerance - calculate_tolerance(x))  # 制造公差
    ],
    reliability_weight=3.0
)

# 使用偏置的求解器
solver = BiasEnhancedSolver(problem, bias_manager)
```

### 案例2：神经网络架构搜索

```python
from nsgablack.bias.library import quick_ml_bias

# 创建偏置
bias_manager = quick_ml_bias(
    accuracy_weight=5.0,    # 高权重准确率
    time_limit=1800,        # 30分钟时间限制
    memory_limit=4.0        # 4GB内存限制
)

# 添加自定义约束
def flops_constraint(x):
    lr, batch_size, hidden_units, dropout = x
    flops = hidden_units * hidden_units * 100  # 简化FLOP计算
    return max(0, flops - 1e9)  # 不超过10亿FLOPS

bias_manager.domain_manager.get_bias('ml_hyperparameter').add_hard_constraint(flops_constraint)
```

### 案例3：投资组合优化

```python
from nsgablack.bias.library import BiasFactory

# 创建金融偏置
finance_bias = BiasFactory.create_domain_bias('portfolio_optimization')

# 添加自定义风险模型
def custom_risk_model(x):
    weights = x / np.sum(x)  # 归一化
    # VaR计算
    var_95 = calculate_var_95(weights, returns_history)
    return var_95

finance_bias.add_hard_constraint(lambda x: max(0, custom_risk_model(x) - 0.05))

# 设置收益率目标
finance_bias.set_target('expected_return', 0.15, 'maximize')
```

## 性能优化建议

### 1. **偏置权重调整**

```python
# 早期：增加算法偏置
bias_manager.set_bias_weights(algorithmic_weight=0.6, domain_weight=0.4)

# 中期：平衡
bias_manager.set_bias_weights(algorithmic_weight=0.5, domain_weight=0.5)

# 后期：增加业务偏置
bias_manager.set_bias_weights(algorithmic_weight=0.3, domain_weight=0.7)
```

### 2. **偏置开关管理**

```python
# 动态启用/禁用偏置
bias_manager.algorithmic_manager.get_bias('diversity').disable()
bias_manager.domain_manager.get_bias('constraint').enable()

# 批量操作
bias_manager.algorithmic_manager.enable_all()
bias_manager.algorithmic_manager.disable_all()
```

### 3. **偏置权重微调**

```python
# 精细调整权重
diversity_bias = bias_manager.get_algorithmic_bias('diversity')
diversity_bias.set_weight(0.15)  # 调整多样性权重
```

## 配置管理

### 保存配置

```python
bias_manager.save_config('my_bias_config.json')
```

### 加载配置

```python
bias_manager.load_config('my_bias_config.json')
```

### 配置文件格式

```json
{
  "bias_weights": {
    "algorithmic": 0.3,
    "domain": 0.7
  },
  "algorithmic_biases": {
    "diversity": {
      "type": "DiversityBias",
      "weight": 0.15,
      "enabled": true
    }
  },
  "domain_biases": {
    "constraint": {
      "type": "ConstraintBias",
      "weight": 1.0,
      "enabled": true
    }
  }
}
```

## 与旧版本的兼容性

### 自动兼容

```python
# 旧版本的代码仍然可以工作
from nsgablack.bias import BiasModule

bias_module = BiasModule()
# constraint_func 需返回 {"penalty": value}
from nsgablack.bias.domain import CallableBias

bias_module.add(CallableBias(name="constraint", func=constraint_func, weight=1.0, mode="penalty"))
```

### 迁移指南

```python
# 旧版本
bias_module = BiasModule()
bias_module.add(CallableBias(name="constraint_strict", func=constraint_func, weight=2.0, mode="penalty"))
bias_module.add(CallableBias(name="reward", func=reward_func, weight=0.05, mode="reward"))

# 新版本
bias_manager = UniversalBiasManager()
constraint_bias = ConstraintBias(weight=2.0)
constraint_bias.add_hard_constraint(constraint_func)
bias_manager.domain_manager.add_bias(constraint_bias)
```

## 高级用法

### 1. **自适应偏置**

```python
class AdaptiveBiasManager(UniversalBiasManager):
    """自适应偏置管理器"""

    def adapt_to_problem_complexity(self, problem):
        if problem.dimension > 20:
            # 高维问题：增加多样性
            diversity_bias = self.get_algorithmic_bias('diversity')
            if diversity_bias:
                diversity_bias.set_weight(0.3)

        if hasattr(problem, 'evaluate_constraints'):
            # 有约束的问题：增加约束偏置权重
            self.set_bias_weights(algorithmic_weight=0.2, domain_weight=0.8)
```

### 2. **多阶段偏置**

```python
class MultiStageBias:
    """多阶段偏置策略"""

    def __init__(self):
        self.stages = {
            'exploration': {'alg_weight': 0.7, 'domain_weight': 0.3},
            'exploitation': {'alg_weight': 0.3, 'domain_weight': 0.7},
            'refinement': {'alg_weight': 0.1, 'domain_weight': 0.9}
        }

    def get_stage_config(self, generation, total_generations):
        if generation < total_generations * 0.3:
            return self.stages['exploration']
        elif generation < total_generations * 0.7:
            return self.stages['exploitation']
        else:
            return self.stages['refinement']
```

### 3. **偏置效果分析**

```python
def analyze_bias_effectiveness(bias_manager, evaluation_history):
    """分析偏置效果"""

    # 计算偏置贡献
    bias_contributions = []
    for record in evaluation_history:
        context = OptimizationContext(
            generation=record['generation'],
            individual=record['individual'],
            population=record['population']
        )

        alg_bias = bias_manager.algorithmic_manager.compute_algorithmic_bias(
            record['individual'], context
        )
        domain_bias = bias_manager.domain_manager.compute_domain_bias(
            record['individual'], context
        )

        bias_contributions.append({
            'generation': record['generation'],
            'algorithmic_bias': alg_bias,
            'domain_bias': domain_bias,
            'total_bias': alg_bias + domain_bias
        })

    return bias_contributions
```

## 常见问题

### Q1: 如何选择合适的偏置？

**A**:
- **算法偏置**：根据优化问题的特性选择
  - 简单问题：`diversity` + `convergence`
  - 复杂问题：添加 `exploration`
  - 精度要求高：添加 `precision`

- **业务偏置**：根据应用领域选择
  - 工程设计：`engineering_design`
  - 机器学习：`machine_learning`
  - 金融优化：`financial_optimization`

### Q2: 偏置权重如何设置？

**A**:
- **算法偏置权重**：通常 0.1-0.3
- **业务偏置权重**：通常 0.7-2.0（业务更重要）
- 根据约束严格性调整：约束越严格，业务偏置权重越大

### Q3: 如何调试偏置效果？

**A**:
```python
# 1. 关闭所有偏置，运行基准测试
bias_manager.algorithmic_manager.disable_all()
bias_manager.domain_manager.disable_all()
baseline_result = solver.run()

# 2. 逐一启用偏置，观察效果
for bias_name in ['diversity', 'constraint', 'preference']:
    bias_manager.get_bias(bias_name).enable()
    result = solver.run()
    print(f"{bias_name}: 改进 = {result['best_f'] - baseline_result['best_f']}")
    bias_manager.get_bias(bias_name).disable()
```

## 总结

偏置系统 v2.0 提供了：

1. **更清晰的结构**：算法偏置和业务偏置分离
2. **更高的复用性**：偏置可以在不同问题间复用
3. **更灵活的组合**：支持任意偏置的组合
4. **更强的扩展性**：易于添加新的偏置类型
5. **更好的可维护性**：模块化设计，易于调试和优化

这个系统让优化不再只是"盲目搜索"，而是"智能引导"，大大提高了优化效率和实用性！
