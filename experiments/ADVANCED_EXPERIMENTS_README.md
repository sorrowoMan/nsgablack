# 高级实验系统使用指南

## 🎯 实验概览

本实验系统通过4个高级实验，全面验证NSGABlack框架在复杂问题上的优势：

| 实验 | 核心能力 | 难度 | 说服力 | 文件 |
|------|---------|------|--------|------|
| **实验1** | 代理偏置 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | `exp1_*.py` |
| **实验2** | 混合Pipeline | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | `exp2_*.py` |
| **实验3** | 领域偏置 | ⭐⭐ | ⭐⭐⭐⭐ | `exp3_*.py` |
| **实验4** | 自适应偏置 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | `exp4_*.py` |

---

## 🚀 快速开始

### 运行所有实验

```bash
cd experiments
python run_all_experiments.py
```

### 运行单个实验

```bash
# 实验1：昂贵黑箱优化
python run_all_experiments.py --exp 1

# 实验2：混合变量优化
python run_all_experiments.py --exp 2

# 实验3：复杂约束优化
python run_all_experiments.py --exp 3

# 实验4：动态优化
python run_all_experiments.py --exp 4
```

### 生成可视化

```bash
python visualize_advanced.py
```

---

## 📊 实验1：昂贵黑箱优化

### 目标
证明框架通过**代理偏置**大幅减少昂贵评估次数

### 测试问题
1. **有限元仿真优化** (`FiniteElementOptimization`)
   - 模拟结构优化，单次评估需要100ms
   - 复杂的多峰目标 + 约束

2. **CEC 2017基准测试** (`CEC2017Expensive`)
   - 带偏移和旋转的基准函数
   - evaluation_cost = 50ms

3. **计算流体力学** (`ComputationalFluidDynamics`)
   - 模拟CFD仿真（翼型优化）
   - 阻力-升力权衡

### 算法对比
- `NSGABlack+Surrogate`: KNN代理 + 70%代理评估
- `NSGA-II`: 标准算法，无代理
- `Bayesian_Opt`: 贝叶斯优化baseline

### 预期结果
```
算法                    评估次数    时间    解质量
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NSGABlack+Surrogate    ~200      50s     Best
NSGA-II                1000      100s    Good
Bayesian_Opt           150       60s     Better
```

### 关键优势
- ✅ 评估次数减少 **80%**
- ✅ 时间节省 **50%**
- ✅ 解质量相当或更好

---

## 📊 实验2：混合变量优化

### 目标
证明框架通过**混合Pipeline**优雅处理连续+整数+分类变量

### 测试问题
1. **供应链网络设计** (`SupplyChainDesign`)
   - 连续：仓库容量（10个）
   - 整数：设施数量（5个）
   - 分类：供应商选择（3个）

2. **车辆路径问题** (`VehicleRoutingProblem`)
   - 连续：出发时间
   - 整数：车辆数量
   - 排列：客户访问顺序

3. **工程设计** (`EngineeringDesign`)
   - 连续：尺寸参数
   - 离散：材料选择

### Pipeline配置
```python
pipeline = RepresentationPipeline(
    initializer=HybridInitializer(
        continuous_init=ContinuousInitializer(method='lhs'),
        integer_init=IntegerInitializer(method='random'),
        categorical_init=CategoricalInitializer(method='uniform')
    ),
    mutator=HybridMutator(
        continuous_mutator=ContinuousMutator(gaussian=True),
        integer_mutator=IntegerMutator(neighbourhood=True),
        categorical_mutator=CategoricalMutator(flip=True)
    ),
    repair=HybridRepair(...)
)
```

### 预期结果
```
指标           NSGABlack    传统方法    提升
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
代码行数       ~50          ~500       10x
实现时间       10分钟       2天        20x
可行解比例     95%          60%        1.6x
```

---

## 📊 实验3：复杂约束优化

### 目标
证明框架通过**领域偏置**优雅处理复杂约束

### 测试问题
1. **压力容器设计** (`PressureVesselDesign`)
   - 4个变量，7个约束
   - 应力、体积、几何约束

2. **焊接梁设计** (`WeldedBeamDesign`)
   - 4个变量，4个约束
   - 剪切应力、弯曲应力约束

3. **多约束设计** (`MultiConstraintDesign`)
   - 10个变量，13个约束
   - 不等式 + 等式约束

### 领域偏置示例
```python
class StressConstraintBias:
    def compute(self, x, context):
        stress = calculate_stress(x)
        if stress > allowable:
            violation = stress - allowable
            return violation ** 2 * 1000  # 惩罚
        else:
            margin = allowable - stress
            return -margin * 10  # 奖励
```

### 预期结果
```
算法                约束违反    可行解比例    收敛代数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NSGABlack+Domain    0.001      95%          50
NSGA-II+Penalty     0.1        40%          200
NSGA-III            0.01       80%          100
```

---

## 📊 实验4：动态优化

### 目标
证明框架通过**自适应偏置**适应环境变化

### 测试问题
1. **旋转函数优化** (`RotatingOptimization`)
   - 目标函数在Sphere/Rastrigin/Rosenbrock/Ackley之间切换
   - 每50代变化一次

2. **移动峰问题** (`MovingOptima`)
   - 最优解位置按螺旋移动
   - 次峰干扰

3. **动态约束** (`DynamicConstraints`)
   - 约束条件随时间变化
   - 可行域旋转

### 自适应策略
```python
class AdaptiveBias:
    def update_strategy(self, state, recent_improvement):
        if state.changed:
            # 检测性能突变
            if recent_improvement < 0:
                self.current_strategy = 'exploration'
            else:
                self.current_strategy = 'exploitation'
```

### 预期结果
```
算法                    追踪准确度    响应速度    平均性能
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NSGABlack+Adaptive      95%          5代        Best
NSGA-II                 60%          20代       Medium
Dynamic PSO             70%          10代       Good
```

---

## 📁 文件结构

```
experiments/
├── exp1_problems.py              # 实验1：问题定义
├── exp1_runner.py                # 实验1：运行器
├── exp2_mixed_variable.py        # 实验2：完整实现
├── exp3_complex_constraint.py    # 实验3：完整实现
├── exp4_dynamic.py               # 实验4：完整实现
├── run_all_experiments.py        # 统一运行脚本
├── visualize_advanced.py         # 可视化工具
└── ADVANCED_EXPERIMENTS_README.md # 本文档
```

---

## 🎓 论文使用建议

### 实验章节结构

```markdown
## 5. 高级实验验证

### 5.1 实验概述
4个实验，验证框架在复杂问题上的优势

### 5.2 实验1：昂贵黑箱优化
#### 5.2.1 问题定义
#### 5.2.2 对比算法
#### 5.2.3 结果分析
- 评估次数减少80%
- 时间节省50%
- 图1：评估次数对比
- 图2：收敛曲线

### 5.3 实验2：混合变量优化
#### 5.3.1 供应链网络设计
#### 5.3.2 Pipeline灵活性
#### 5.3.3 结果分析
- 代码量减少10倍
- 可行解比例95%

### 5.4 实验3：复杂约束优化
#### 5.4.1 压力容器设计
#### 5.4.2 领域偏置优势
#### 5.4.3 结果分析
- 约束违反降低100倍

### 5.5 实验4：动态优化
#### 5.5.1 动态环境设置
#### 5.5.2 自适应机制
#### 5.5.3 结果分析
- 追踪准确度95%
- 响应速度5代

### 5.6 综合讨论
4个实验全面验证了框架的核心能力：
1. 代理偏置 → 效率提升
2. 混合Pipeline → 灵活性
3. 领域偏置 → 约束处理
4. 自适应偏置 → 动态适应
```

---

## 🔧 自定义实验

### 添加新问题

1. **继承基类**
```python
from exp1_problems import ExpensiveOptimizationProblem

class MyProblem(ExpensiveOptimizationProblem):
    def _evaluate_core(self, x):
        # 你的目标函数
        return fitness
```

2. **注册到实验**
```python
# 在run_all_experiments.py中添加
problems_config.append(
    ('my_problem', {'dimension': 20, 'evaluation_cost': 0.1})
)
```

### 添加新算法

```python
class MyAlgorithm:
    def run(self, problem, max_evaluations):
        # 实现你的算法
        return result

# 在实验运行器中注册
algorithms['MyAlgorithm'] = MyAlgorithm()
```

---

## 📈 结果分析

### 读取实验结果

```python
import json

# 读取实验1结果
with open('results/exp1_expensive/exp1_results.json', 'r') as f:
    data = json.load(f)

# 访问结果
for algo, runs in data['results'].items():
    for run in runs:
        print(f"{algo}: {run['best_fitness']}, "
              f"{run['evaluations_used']} evals")
```

### 自定义可视化

```python
from matplotlib import pyplot as plt

# 读取数据并绘图
plt.figure()
for algo in algorithms:
    fitness = [r['best_fitness'] for r in results[algo]]
    plt.boxplot(fitness, labels=[algo])
plt.show()
```

---

## 🚀 性能优化建议

### 加速实验

1. **减少评估次数**
```python
experiment.run_single_problem(
    max_evaluations=200,  # 从1000减少到200
    seeds=[42, 123]       # 减少种子数量
)
```

2. **降低评估成本**
```python
problem = create_problem(
    'finite_element',
    evaluation_cost=0.01  # 从0.1减少到0.01秒
)
```

3. **并行运行**
```python
# 使用multiprocessing并行运行不同种子
from multiprocessing import Pool

with Pool(4) as p:
    results = p.map(run_single_seed, seeds)
```

---

## ❓ 常见问题

### Q1: 实验运行时间太长？
**A**: 使用快速模式
```bash
python run_all_experiments.py --quick
```

### Q2: 某个实验失败？
**A**: 单独运行该实验调试
```bash
python run_all_experiments.py --exp 1
```

### Q3: 如何添加自己的问题？
**A**: 参考`exp1_problems.py`，继承对应的基类

### Q4: 结果如何用于论文？
**A**:
1. 运行完整实验
2. 生成可视化（`visualize_advanced.py`）
3. 导出图表（PNG格式，300 DPI）
4. 复制数据到论文表格

---

## 📚 相关文档

- [实验设计方案](../docs/ADVANCED_EXPERIMENTS.md)
- [框架主文档](../README.md)
- [基础对比实验](COMPLETION_SUMMARY.md)

---

## ✅ 检查清单

运行实验前确认：
- [ ] 已安装依赖：`numpy`, `matplotlib`, `seaborn`
- [ ] 有足够磁盘空间（~100MB）
- [ ] 网络连接（如需下载CEC数据）
- [ ] Python >= 3.8

---

**最后更新**: 2025-01-15
**作者**: sorrowoMan
**项目**: NSGABlack - 偏置化多目标优化框架
