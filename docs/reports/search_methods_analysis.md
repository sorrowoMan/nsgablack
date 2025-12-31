# 多智能体搜索方法分析报告

## 📊 当前实现的搜索方法

### 1. Explorer（探索者）- 全局搜索

#### 当前实现：
```python
# 父母选择
parent1, parent2 = self._select_parents_random(agent_pop)
# → 随机均匀选择，不考虑适应度

# 交叉策略：均匀交叉
mask = np.random.rand(len(parent1)) < 0.5
child = np.where(mask, parent1, parent2)
# → 每个维度随机从父或母继承

# 变异策略：高斯变异（大步长）
mutation_rate = 0.3
mutation_strength = 0.8 * 0.5 = 0.4
mutation = np.random.randn(len(individual)) * 0.4
# → 标准正态分布 * 0.4
```

**特点**：
- ✅ 优点：简单、随机性好、覆盖面广
- ❌ 缺点：**盲目搜索**，没有利用问题结构，效率低

**适用场景**：
- 解空间完全未知
- 多峰问题需要广泛探索
- 作为初始化阶段的快速扫描

---

### 2. Exploiter（开发者）- 局部搜索

#### 当前实现：
```python
# 父母选择：适应度比例选择
fitness = fitness - fitness.min() + 1e-8
probabilities = fitness / fitness.sum()
idx1, idx2 = np.random.choice(2, p=probabilities)
# → 适应度高的被选中的概率大

# 交叉策略：算术交叉
alpha = np.random.rand()
child = alpha * parent1 + (1 - alpha) * parent2
# → 父母的加权平均

# 变异策略：高斯变异（小步长）
mutation_rate = 0.1
mutation_strength = 0.2 * 0.5 = 0.1
mutation = np.random.randn(len(individual)) * 0.1
# → 标准正态分布 * 0.1
```

**特点**：
- ✅ 优点：利用优良解信息，收敛快
- ❌ 缺点：**容易陷入局部最优**，多样性丧失

**适用场景**：
- 已知大致区域，需要精细优化
- 单峰或弱多峰问题
- 优化后期快速收敛

---

## 🔍 问题分析

### 当前方法的核心问题：

#### 1. **没有利用问题结构信息**
```
当前：所有问题用同样的搜索策略
问题：不同问题有不同特性（凸性、可分性、多峰性等）
```

#### 2. **搜索策略相对简单**
```
当前：基本的遗传算子（随机选择+均匀交叉+高斯变异）
缺失：
  - 没有基于梯度的搜索
  - 没有基于模式的搜索
  - 没有局部优化算子
  - 没有问题特定的启发式
```

#### 3. **探索与开发的平衡机制粗糙**
```
当前：通过调整变异率、交叉率等参数
问题：参数固定或简单动态调整，不够智能
```

---

## 💡 改进建议

### 方案 1：增强的搜索策略库

为不同角色配置多种搜索策略：

```python
class SearchStrategy(Enum):
    """搜索策略类型"""
    # 基础策略
    RANDOM = "random"                    # 随机搜索
    GENETIC = "genetic"                  # 遗传算法
    DIFFERENTIAL_EVOLUTION = "de"       # 差分进化

    # 基于梯度/模式
    GRADIENT_BASED = "gradient"          # 基于梯度
    PATTERN_BASED = "pattern"            # 基于模式
    SURROGATE_ASSISTED = "surrogate"    # 代理模型辅助

    # 局部搜索
    LOCAL_SEARCH = "local"              # 局部搜索
    SIMULATED_ANNEALING = "sa"          # 模拟退火
    HILL_CLIMBING = "hill_climb"        # 爬山算法

    # 混合策略
    MEMETIC = "memetic"                 # 文化基因算法
    HYBRID = "hybrid"                   # 混合策略
```

### 方案 2：为角色配置专门的搜索方法

```python
EXPLORER_SEARCH_STRATEGIES = {
    'differential_evolution': {
        'description': '差分进化：利用种群差异信息',
        'F': 0.8,  # 差分权重
        'CR': 0.9,  # 交叉概率
        'variant': 'DE/rand/1/bin'  # 变体
    },
    'random_sampling': {
        'description': '随机采样：拉丁超立方采样',
        'method': 'lhs',
        'samples': 100
    },
    'pattern_search': {
        'description': '模式搜索：探索不同方向',
        'pattern_size': 5,
        'step_size': 0.1
    }
}

EXPLOITER_SEARCH_STRATEGIES = {
    'gradient_descent': {
        'description': '梯度下降：快速收敛',
        'learning_rate': 0.01,
        'momentum': 0.9
    },
    'local_search': {
        'description': '局部搜索：Hooke-Jeeves模式搜索',
        'step_size': 0.05,
        'tolerance': 1e-6
    },
    'quasi_newton': {
        'description': '拟牛顿法：BFGS',
        'method': 'BFGS',
        'max_iter': 100
    }
}
```

### 方案 3：实现具体的搜索方法

让我为你实现几个关键的搜索方法...

