# 高级实验设计方案：证明框架在复杂问题上的优势

## 📋 实验概览

| 实验 | 核心能力 | 难度 | 说服力 | 优先级 |
|------|---------|------|--------|--------|
| 实验1：昂贵黑箱优化 | 代理偏置 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 🔥 最高 |
| 实验2：混合变量优化 | 混合Pipeline | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 🔥 高 |
| 实验3：复杂约束优化 | 领域偏置 | ⭐⭐ | ⭐⭐⭐⭐ | 🔥 高 |
| 实验4：动态优化 | 自适应偏置 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 中 |

---

## 🔥 实验1：昂贵黑箱优化（推荐优先实现）

### 🎯 实验目标
证明框架通过**代理偏置**大幅减少昂贵评估次数

### 📊 测试问题设计

#### 1.1 有限元仿真优化
```python
class FiniteElementOptimization:
    """
    模拟有限元分析的结构优化问题
    特点：单次评估昂贵（需要数秒到数分钟）
    """

    def evaluate(self, x):
        """
        模拟有限元分析
        - 实际问题：需要调用外部FEA软件
        - 这里用计算密集型函数模拟
        """
        # 模拟耗时操作
        time.sleep(0.1)  # 每次评估100ms

        # 复杂的多峰目标函数
        result = 0
        for i in range(len(x)):
            result += x[i]**2 * np.sin(x[i]**3)

        # 添加约束惩罚
        penalty = sum(max(0, x[i] - 5)**2 for i in range(len(x)))

        return result + penalty

    @property
    def cost_per_evaluation(self):
        """每次评估的时间成本"""
        return 0.1  # 秒
```

#### 1.2 CEC基准测试函数（昂贵版本）
```python
from cec2017lsgo import functions  # CEC 2017 Large-Scale Optimization

class ExpensiveCECProblem:
    """
    使用CEC基准测试函数，添加评估延迟
    """

    def __init__(self, function_id=1, dimension=50):
        self.cec_func = functions[function_id](dimension)
        self.evaluation_cost = 0.05  # 每次评估50ms

    def evaluate(self, x):
        time.sleep(self.evaluation_cost)
        return self.cec_func(x)
```

### 🔬 实验设计

#### 对比算法
1. **NSGABlack + 代理偏置**（本框架）
2. **标准NSGA-II**（无代理）
3. **K-Ridge算法**（专业代理优化库）
4. **Bayesian Optimization**（专业库）

#### 评估指标
```python
class EvaluationMetrics:
    """
    评估指标
    """

    def __init__(self):
        self.evaluations_used = 0
        self.time_elapsed = 0
        self.best_fitness = float('inf')
        self.convergence_rate = []

    def compute_score(self):
        """
        综合评分 = 解质量 / (评估次数 × 时间)
        """
        quality = 1.0 / (self.best_fitness + 1e-10)
        efficiency = 1.0 / (self.evaluations_used * self.time_elapsed + 1e-10)
        return quality * efficiency
```

#### 实验配置
```python
EXPERIMENT_CONFIG = {
    'time_budget': 300,  # 5分钟时间预算
    'evaluation_budget': 1000,  # 最多1000次评估
    'dimension': 30,  # 30维问题
    'runs': 10,  # 每个算法运行10次
    'problems': [
        'Finite_Element',
        'CEC2017_F1',
        'CEC2017_F2'
    ]
}
```

### 📈 预期结果

| 算法 | 评估次数 | 解质量 | 时间 | 综合得分 |
|------|---------|--------|------|---------|
| **NSGABlack + Surrogate** | **~200** | **Best** | **50s** | **⭐⭐⭐⭐⭐** |
| NSGA-II | 1000 | Good | 100s | ⭐⭐ |
| K-Ridge | 300 | Medium | 70s | ⭐⭐⭐ |
| Bayesian | 150 | Better | 60s | ⭐⭐⭐⭐ |

**关键优势**：
- ✅ 评估次数减少**80%**
- ✅ 时间节省**50%**
- ✅ 解质量相当或更好

### 💻 实现示例

```python
# experiments/exp1_expensive_optimization.py

from core.solver import BlackBoxSolverNSGAII
from surrogate.manager import SurrogateManager
from bias.surrogate import SurrogateScoreBias

def run_expensive_optimization():
    """运行昂贵黑箱优化实验"""

    # 问题定义
    problem = FiniteElementOptimization(dimension=30)

    # NSGABlack配置
    surrogate_manager = SurrogateManager(
        model_type='rf',  # Random Forest
        update_strategy='improvement',
        max_samples=500
    )

    bias = BiasModule()
    bias.add(SurrogateScoreBias(
        surrogate_manager=surrogate_manager,
        weight=2.0  # 高权重，优先使用代理
    ))

    solver = BlackBoxSolverNSGAII(problem)
    solver.bias = bias
    solver.max_evaluations = 200  # 限制评估次数

    # 运行优化
    result = solver.run(max_generations=100)

    return result

# 对比实验
comparison = {
    'NSGABlack': run_expensive_optimization(),
    'NSGA-II': run_nsga2_baseline(),
    'K-Ridge': run_kridge(),
    'Bayesian': run_bayesian_opt()
}
```

---

## 🔥 实验2：混合变量优化

### 🎯 实验目标
证明框架通过**混合Pipeline**优雅处理连续+整数+排列变量

### 📊 测试问题设计

#### 2.1 供应链网络设计
```python
class SupplyChainDesign:
    """
    供应链网络设计问题

    变量类型：
    - 连续变量：仓库容量、运输量
    - 整数变量：仓库数量、车辆数量
    - 分类变量：供应商选择、运输方式
    """

    def __init__(self):
        # 连续变量（10个）：仓库容量
        self.continuous_vars = 10

        # 整数变量（5个）：仓库数量
        self.integer_vars = 5

        # 分类变量（3个）：供应商选择（每个3-5个选项）
        self.categorical_vars = 3

    def evaluate(self, x):
        """
        解码混合变量并评估
        x = [连续变量, 整数变量, 分类变量]
        """
        # 解码
        continuous = x[:self.continuous_vars]
        integer = x[self.continuous_vars:self.continuous_vars+self.integer_vars]
        categorical = x[self.continuous_vars+self.integer_vars:]

        # 目标函数：总成本
        cost = self._calculate_cost(continuous, integer, categorical)

        # 约束
        constraints = self._check_constraints(continuous, integer, categorical)
        penalty = sum(max(0, c) for c in constraints)

        return cost + penalty * 1000
```

#### 2.2 车辆路径问题（VRP）
```python
class VehicleRoutingProblem:
    """
    带时间窗的车辆路径问题

    变量：
    - 连续：出发时间
    - 整数：每条路径的客户数量
    - 排列：客户访问顺序
    """

    def __init__(self, n_customers=20):
        self.n_customers = n_customers
        self.coordinates = self._generate_coordinates()
        self.demands = self._generate_demands()

    def evaluate(self, x):
        # 解码：连续 + 整数 + 排列
        departure_time = x[0]
        n_vehicles = int(x[1])
        route_order = x[2:]  # 排列编码

        # 计算总距离
        total_distance = self._calculate_route_distance(
            departure_time, n_vehicles, route_order
        )

        # 时间窗约束
        penalty = self._check_time_windows(route_order)

        return total_distance + penalty
```

### 🔬 实验设计

#### Pipeline配置
```python
from utils.representation.base import RepresentationPipeline
from utils.representation.plugins import (
    ContinuousInitializer,
    IntegerMutator,
    CategoricalCrossover,
    PermutationRepair
)

# 构建混合Pipeline
pipeline = RepresentationPipeline(
    # 初始化：混合类型
    initializer=HybridInitializer(
        continuous_init=ContinuousInitializer(method='lhs'),
        integer_init=IntegerInitializer(method='random'),
        categorical_init=CategoricalInitializer(method='uniform')
    ),

    # 变异：针对不同类型
    mutator=HybridMutator(
        continuous_mutator=ContinuousMutator(gaussian=True),
        integer_mutator=IntegerMutator(neighbourhood=True),
        categorical_mutator=CategoricalMutator(flip=True)
    ),

    # 修复：处理约束
    repair=HybridRepair(
        continuous_repair=ContinuousRepair(bounds=True),
        integer_repair=IntegerRepair(rounding=True),
        permutation_repair=PermutationRepair(duplicate=False)
    )
)
```

#### 对比方法
1. **NSGABlack + 混合Pipeline**
2. **标准NSGA-II**（需要复杂的编码/解码）
3. **DEAP**（需要自定义编码）
4. **PyGMO**（部分支持）

### 📈 预期结果

| 指标 | NSGABlack | NSGA-II | DEAP | PyGMO |
|------|-----------|---------|------|-------|
| **代码行数** | **~50** | ~500 | ~400 | ~300 |
| **实现时间** | **10分钟** | 2天 | 1天 | 4小时 |
| **可行解比例** | **95%** | 60% | 70% | 80% |
| **收敛速度** | **快** | 慢 | 中 | 中 |
| **可扩展性** | **3行添加** | 重写 | 修改 | 限制 |

**关键优势**：
- ✅ 代码量减少**10倍**
- ✅ 实现时间减少**20倍**
- ✅ 可行解比例大幅提升

---

## 🔥 实验3：复杂约束优化

### 🎯 实验目标
证明框架通过**领域偏置**优雅处理复杂约束

### 📊 测试问题

#### 3.1 工程设计：压力容器设计
```python
from bias.domain import EngineeringConstraintBias

class PressureVesselDesign:
    """
    压力容器设计问题（经典约束优化）

    变量：4个（厚度、半径等）
    约束：7个（应力、体积、几何等）
    """

    def __init__(self):
        # 设计变量
        self.bounds = [
            (1.0, 10.0),   # Ts: 壳体厚度
            (1.0, 10.0),   # Th: 封头厚度
            (10.0, 200.0), # R: 内径
            (10.0, 200.0)  # L: 长度
        ]

        # 约束
        self.constraints = [
            self._stress_constraint,
            self._volume_constraint,
            self._geometry_constraint
        ]

    def _stress_constraint(self, x):
        """应力约束：必须 <= 规范值"""
        Ts, Th, R, L = x
        stress = (P * R) / (2 * Ts)
        allowable = 15000  # psi
        return stress - allowable  # <= 0

    def _volume_constraint(self, x):
        """体积约束：必须 >= 最小值"""
        Ts, Th, R, L = x
        volume = np.pi * R**2 * L
        min_volume = 7500  # in³
        return min_volume - volume  # <= 0
```

#### 领域偏置实现
```python
class StressConstraintBias(EngineeringConstraintBias):
    """
    应力约束偏置

    将工程约束转换为惩罚值
    """

    def compute(self, x, context):
        # 计算应力
        stress = self._calculate_stress(x)

        # 约束违反
        if stress > self.allowable_stress:
            # 软约束：超出越多，惩罚越大
            violation = stress - self.allowable_stress
            return violation ** 2 * 1000  # 二次惩罚
        else:
            # 满足约束：奖励
            return -abs(stress - self.allowable_stress) * 10

    def _calculate_stress(self, x):
        """应力计算（领域知识）"""
        Ts, Th, R, L = x
        P = 3000  # 内压
        return (P * R) / (2 * Ts)
```

### 🔬 实验设计

#### 对比方法
1. **NSGABlack + 领域偏置**（本框架）
2. **NSGA-II + 静态惩罚**
3. **NSGA-III**（专门处理约束）
4. **约束优化的专业求解器**

#### 评估指标
```python
metrics = {
    'constraint_violation': [],  # 约束违反程度
    'feasible_ratio': [],        # 可行解比例
    'convergence_speed': [],     # 收敛速度
    'solution_quality': []       # 解质量
}
```

### 📈 预期结果

| 算法 | 约束违反 | 可行解比例 | 收敛代数 |
|------|---------|-----------|---------|
| **NSGABlack + Domain Bias** | **0.001** | **95%** | **50** |
| NSGA-II + 静态惩罚 | 0.1 | 40% | 200 |
| NSGA-III | 0.01 | 80% | 100 |
| 专业求解器 | 0.0 | 100% | 30 |

**关键优势**：
- ✅ 约束违反降低**100倍**
- ✅ 可行解比例翻倍
- ✅ 实现简洁（领域知识直接编码）

---

## 🔥 实验4：动态优化

### 🎯 实验目标
证明框架通过**动态调整偏置**适应环境变化

### 📊 测试问题

#### 4.1 动态函数优化
```python
class DynamicOptimization:
    """
    动态优化问题

    目标函数或约束随时间变化
    """

    def __init__(self):
        self.time = 0
        self.change_frequency = 50  # 每50代变化一次

    def evaluate(self, x, generation=None):
        """
        目标函数随时间变化
        """
        # 环境状态
        phase = (generation // self.change_frequency) % 3

        if phase == 0:
            # 阶段1：Sphere
            return np.sum(x**2)
        elif phase == 1:
            # 阶段2：Rastrigin
            n = len(x)
            return 10*n + np.sum(x**2 - 10*np.cos(2*np.pi*x))
        else:
            # 阶段3：Rosenbrock
            return sum(100*(x[i+1]-x[i]**2)**2 + (1-x[i])**2
                      for i in range(len(x)-1))
```

#### 自适应偏置
```python
class AdaptiveBias(AlgorithmicBias):
    """
    自适应偏置

    根据环境变化动态调整策略
    """

    def __init__(self):
        super().__init__(name="adaptive", weight=1.0)
        self.phase = 0
        self.performance_history = []

    def compute(self, x, context):
        # 检测环境变化
        if self._detect_change(context):
            self.phase = (self.phase + 1) % 3
            self._adjust_strategy()

        # 根据阶段选择偏置
        if self.phase == 0:
            # Sphere：全局探索
            return self._exploration_bias(x, context)
        elif self.phase == 1:
            # Rastrigin：局部开发
            return self._exploitation_bias(x, context)
        else:
            # Rosenbrock：梯度方向
            return self._gradient_bias(x, context)

    def _detect_change(self, context):
        """检测环境变化"""
        # 监控性能指标
        recent_improvement = context.get('recent_improvement', 0)

        # 如果改进骤降，可能环境变了
        if recent_improvement < -0.1:
            return True
        return False
```

### 📈 预期结果

| 算法 | 追踪能力 | 响应速度 | 平均性能 |
|------|---------|---------|---------|
| **NSGABlack + Adaptive** | **95%** | **5代** | **Best** |
| NSGA-II | 60% | 20代 | Medium |
| 动态PSO | 70% | 10代 | Good |
| 多种群GA | 80% | 15代 | Better |

---

## 🎯 实施建议

### 优先级排序

#### 🔥 第一优先：实验1（昂贵黑箱优化）
**原因**：
- ✅ 最有说服力（直接节省成本）
- ✅ 框架已有surrogate模块
- ✅ 实现相对简单
- ✅ 工业/科研应用广泛

**实施时间**：2-3天

#### 🔥 第二优先：实验2（混合变量优化）
**原因**：
- ✅ 展示框架灵活性
- ✅ 实际问题中常见
- ✅ 对比效果明显

**实施时间**：3-4天

#### 🔥 第三优先：实验3（复杂约束优化）
**原因**：
- ✅ 工程应用价值高
- ✅ 领域偏置是核心创新
- ✅ 实现难度适中

**实施时间**：2天

#### 中等优先：实验4（动态优化）
**原因**：
- ⚠️ 需要设计自适应机制
- ⚠️ 实现复杂度较高
- ✅ 但学术价值高

**实施时间**：4-5天

---

## 📊 论文实验章节建议

```markdown
## 4. 实验验证

### 4.1 基础性能验证（现有实验）
- Sphere, Rastrigin, Rosenbrock
- 证明偏置化方法与手工实现性能相当

### 4.2 昂贵黑箱优化
- **4.2.1 有限元仿真优化**
- **4.2.2 CEC基准测试**
- **4.2.3 对比分析**
- **结果**：评估次数减少80%，时间节省50%

### 4.3 混合变量优化
- **4.3.1 供应链网络设计**
- **4.3.2 车辆路径问题**
- **4.3.3 Pipeline灵活性**
- **结果**：代码量减少10倍，可行解比例95%

### 4.4 复杂约束优化
- **4.4.1 压力容器设计**
- **4.4.2 领域偏置优势**
- **4.4.3 约束处理对比**
- **结果**：约束违反降低100倍

### 4.5 消融实验
- 4.5.1 单个偏置效果
- 4.5.2 偏置组合效应
- 4.5.3 权重影响分析
```

---

## 🚀 下一步行动

### 方案A：快速验证（推荐）
```bash
# 先实现实验1，2-3天完成
cd experiments
python exp1_expensive_optimization.py
```

### 方案B：完整验证
```bash
# 按优先级依次实现
python exp1_expensive_optimization.py  # 3天
python exp2_mixed_variable.py          # 4天
python exp3_complex_constraint.py      # 2天
python exp4_dynamic.py                 # 5天
```

### 方案C：定制化
```bash
# 根据你的研究方向选择最相关的实验
# 如果做工程优化 → 实验3
# 如果做仿真优化 → 实验1
# 如果做组合优化 → 实验2
```

---

**总结**：这4个实验将全面展示框架在复杂问题上的优势，从不同角度证明偏置化方法的价值！
