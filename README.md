# nsgablack

<div align="center">

**基于偏置系统的多智能体 NSGA-II 多目标优化生态框架**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

把算法策略与业务约束解耦 · 编码与算子模块化 · 智能策略可插拔复用

</div>

---

## 📖 目录

- [✨ 核心特性](#-核心特性)
- [🎯 适用问题](#-适用问题)
- [🚀 快速上手](#-快速上手)
- [💡 核心创新](#-核心创新)
- [🏗️ 系统架构](#️-系统架构)
- [🔧 模块详解](#-模块详解)
- [📋 使用指南](#-使用指南)
- [📚 示例索引](#-示例索引)
- [🧪 验证测试](#-验证测试)
- [📁 项目结构](#-项目结构)
- [🔮 发展方向](#-发展方向)
- [🤝 贡献](##-贡献)
- [📄 许可证](#-许可证)

---

## ✨ 核心特性

本项目定位为"可复用的优化工程框架"，具有五大核心能力：

**解耦性** - 算法与业务规则分离，约束逻辑不再耦合进求解器

**复用性** - 编码、修复、初始化、变异等模块可跨问题复用

**扩展性** - 策略通过偏置系统扩展，不必重写算法核心

**可控性** - 通过智能体角色与偏置调参实现搜索风格可控

**可验证** - 提供一键验证脚本与丰富示例，降低工程风险

---

## 🎯 适用问题

- **复杂约束优化** - 多峰、多目标、多约束的组合优化问题
- **混合变量类型** - 连续、整数、排列、矩阵、图结构等混合变量
- **昂贵评估场景** - 需要代理模型或并行评估的优化任务
- **快速迁移需求** - 新业务场景下减少重复编码成本的项目

---

## 🚀 快速上手

### 环境要求

- Python 3.8+
- NumPy, SciPy, matplotlib
- (可选) scikit-learn, GPyOpt

### 安装依赖

```bash
pip install -r requirements.txt
```

### 五分钟入门

```python
from core.solver import BlackBoxSolverNSGAII
from core.problems import ZDT1BlackBox

# 定义问题
problem = ZDT1BlackBox(dimension=10)

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 50

# 运行优化
result = solver.run()
print(f"找到 {len(result['pareto_solutions'])} 个 Pareto 最优解")
```

### 添加约束偏置

```python
from bias.bias import BiasModule

# 定义约束函数（返回惩罚和约束违规度）
def constraint_penalty(x, constraints, context):
    violation = max(0.0, x[0] + x[1] - 1.0)
    return {"penalty": violation, "constraint": violation}

# 创建并挂载偏置
bias = BiasModule()
bias.add_penalty(constraint_penalty, weight=10.0, name="sum_limit")
solver.bias_module = bias
solver.enable_bias = True
```

---

## 💡 核心创新

### 1️⃣ 偏置化思想

将"算法策略"和"业务约束"抽象为统一接口的偏置模块：

| 偏置类型 | 作用 | 示例 |
|---------|------|------|
| 算法偏置 | 控制搜索方向、多样性、收敛性 | PSO、CMA-ES、Levy Flight |
| 领域偏置 | 表达约束、偏好、规则、可行域 | 业务规则、行业知识、约束条件 |

偏置可以返回约束违规度，直接参与排序与选择。

### 2️⃣ 约束外置

传统做法将约束硬编码进问题类，本框架允许偏置独立返回约束违规度：

- ✅ 约束可插拔，问题类无需改动
- ✅ 支持硬约束与软约束的动态权重调整
- ✅ 业务团队只需实现规则偏置，无需理解求解器

### 3️⃣ 表征流水线模块化

将编码、修复、初始化、变异解耦为独立模块：

```python
# 快速切换表征方式
encoding = PermutationEncoding()
repair = PermutationRepair()
init = RandomInit()
mutate = SwapMutate()

pipeline = RepresentationPipeline(encoding, repair, init, mutate)
```

### 4️⃣ 算法偏置化扩展

将强算法抽象为偏置层，挂接到 NSGA-II 通用底座：

```
NSGA-II (通用底座)
    ↓
算法偏置层 (PSO / CMA-ES / Tabu / Levy)
    ↓
领域偏置层 (约束 / 偏好 / 规则)
```

既保留通用性，又增强可扩展性。

### 5️⃣ 多智能体角色差异化

在同一代中并行运行多个差异化角色：

| 角色 | 职责 | 行为特征 |
|-----|------|---------|
| Explorer | 大范围探索 | 高变异、低选择压力 |
| Exploiter | 局部开发 | 低变异、强局部搜索 |
| Waiter | 趋势观察 | 延迟加入、跟随趋势 |
| Advisor | 策略建议 | 贝叶斯/ML 建议区域 |
| Coordinator | 动态调节 | 根据统计调整角色比例 |

---

## 🏗️ 系统架构

### 整体流程

```
问题定义目标函数
    ↓
表征模块（编码/修复/初始化/变异）
    ↓
偏置系统（策略 + 约束）
    ↓
求解器（NSGA-II + 多智能体协作）
    ↓
代理模型与并行评估
    ↓
实验跟踪与可视化
```

### 核心评价机制

1. **初始化种群** → 表征管线规则化初始化
2. **计算目标值** → 原始多目标评估
3. **应用偏置** → 计算惩罚/奖励并汇总约束违规度
4. **排序选择** → 基于目标值与约束违规度
5. **生成新一代** → 交叉、变异、修复
6. **智能体协作** → 信息交流、策略更新

### 为什么选择 NSGA-II？

- ✅ 结构清晰、稳定可靠，工程实践验证充分
- ✅ 天然适合多智能体协作与偏置系统集成
- ✅ 可解释的排序与拥挤距离机制，便于调试
- ✅ 通过偏置化引入强策略，保留通用性

---

## 🔧 模块详解

### 1. 偏置系统 (`bias/`)

提供统一接口，支持惩罚与奖励、约束返回：

**偏置返回值规范：**
```python
# 方式1：返回单个数值
return penalty_value

# 方式2：返回二元组
return (value, constraint_violation)

# 方式3：返回字典
return {"penalty": ..., "reward": ..., "constraint": ...}
```

**偏置分类：**
- **算法偏置** - 搜索策略、多样性维护、局部强化
- **领域偏置** - 约束、偏好、业务规则、行业知识

### 2. 表征与编码体系 (`utils/representation/`)

**支持的表征类型：**
- 连续向量编码
- 整数编码
- 排列编码（TSP 等）
- 矩阵编码
- 图结构编码

**表征流水线四大模块：**
```python
编码 → 修复 → 初始化 → 变异/交叉
```

### 3. 多智能体系统 (`solvers/multi_agent.py`, `multi_agent/`)

- 角色可配置比例，动态调整
- 角色共享最优解、趋势、可行域信息
- Advisor 基于贝叶斯/ML 生成建议
- Coordinator 通过统计调整角色比例

### 4. 求解器生态 (`solvers/`)

- NSGA-II（核心）
- MOEA/D
- 变邻域搜索（VNS）
- 贝叶斯优化
- 代理模型辅助

### 5. 代理模型与并行评估 (`utils/parallel_evaluator.py`)

- 代理模型加速评估
- 并行评估后端
- 多智能体并行评估支持

### 6. 工具与实验支持 (`utils/`)

- 实验跟踪与结果导出
- 可视化分析与趋势监控
- 一键验证脚本

---

## 📋 使用指南

### 快速迁移七步法

**步骤1** - 明确变量类型（连续/整数/排列/矩阵/图）

**步骤2** - 组合表征流水线
```python
pipeline = RepresentationPipeline(
    encoding=PermutationEncoding(),
    repair=PermutationRepair(),
    init=RandomInit(),
    mutate=SwapMutate()
)
```

**步骤3** - 定义目标函数
```python
class MyProblem(BlackBoxProblem):
    def evaluate(self, x):
        return [objective_1(x), objective_2(x)]
```

**步骤4** - 编写偏置（约束与规则）
```python
bias = BiasModule()
bias.add_penalty(constraint_func, weight=10.0)
```

**步骤5** - 选择求解器与智能体配置
```python
solver = BlackBoxSolverNSGAII(problem)
solver.multi_agent_config = {"explorer": 0.3, "exploiter": 0.5}
```

**步骤6** - 配置权重与比例
```python
solver.bias_weights = {"bias1": 1.0, "bias2": 2.0}
```

**步骤7** - 运行并验证
```python
result = solver.run()
# 使用验证脚本检查结果
```

### 算法偏置类型

| 偏置类型 | 功能描述 |
|---------|---------|
| Simulated Annealing | 退火型接受机制，提升跳出局部最优能力 |
| Differential Evolution | 强调差分方向与步长控制 |
| Pattern Search | 局部模式搜索，强化可行邻域探索 |
| Gradient Descent | 引导局部下降方向 |
| PSO | 引入速度与群体引导机制 |
| CMA-ES | 协方差自适应搜索策略 |
| Tabu Search | 记录禁忌，避免短期回访 |
| Levy Flight | �跳跃探索，提升全局探索能力 |

### 编码/修复/初始化/变异模式速查

**编码模式：**
- 连续向量、整数、排列（TSP）、矩阵、图结构

**修复模式：**
- 范围裁剪、边界投影、约束投影、排列合法化、矩阵结构修复

**初始化模式：**
- 随机初始化、规则初始化、采样初始化、偏置引导初始化

**变异模式：**
- 连续扰动、整数扰动、排列变异（交换/逆序/插入）、矩阵局部扰动

---

## 📚 示例索引

| 示例文件 | 说明 |
|---------|------|
| `algorithmic_biases_demo.py` | 算法偏置快速演示 |
| `algorithmic_biases_full_demo.py` | 算法偏置组合演示 |
| `bayesian_optimization_example.py` | 贝叶斯偏置示例 |
| `validation_smoke_suite.py` | 一键验证核心模块 |
| `tsp_representation_pipeline_demo.py` | TSP 表征管线示例 |
| `representation_comprehensive_demo.py` | 表征体系综合示例 |
| `bias_system_real_example.py` | 偏置系统业务化示例 |

---

## 🧪 验证测试

运行一键验证脚本，检查所有核心模块：

```bash
python examples/validation_smoke_suite.py
```

验证内容：
- ✅ 偏置系统功能
- ✅ 表征管线各模块
- ✅ 多智能体协作
- ✅ 求解器基本运行
- ✅ 结果输出与可视化

**常见输出信息：**
- Pareto 解集与目标值
- 评估次数与时间开销
- 历史最优记录与收敛轨迹
- 约束违规度统计与可行率

---

## 📁 项目结构

```
nsgablack/
├── core/                   # 核心模块
│   ├── base.py            # 基础类定义
│   ├── solver.py          # 主求解器
│   └── problems.py        # 内置测试问题
├── solvers/               # 求解器实现
│   ├── nsga2.py          # NSGA-II
│   ├── moead.py          # MOEA/D
│   ├── bayesian_optimizer.py  # 贝叶斯优化
│   ├── multi_agent.py    # 多智能体系统
│   └── vns.py            # 变邻域搜索
├── bias/                  # 偏置系统
│   ├── algorithmic/      # 算法偏置（PSO、CMA-ES等）
│   ├── domain/           # 领域偏置（约束、规则）
│   └── bias.py           # 偏置核心模块
├── utils/                 # 工具模块
│   ├── representation/   # 表征管线
│   ├── parallel_evaluator.py  # 并行评估
│   └── visualization.py  # 可视化工具
├── multi_agent/           # 多智能体
│   ├── roles/            # 角色定义
│   └── strategies/       # 协作策略
├── surrogate/             # 代理模型
├── examples/              # 示例代码
├── docs/                  # 文档
└── requirements.txt       # 依赖清单
```

---

## 🔮 发展方向

- [ ] 新的偏置库扩展与行业约束模板
- [ ] 更丰富的表征管线与修复算子
- [ ] 多智能体协作策略与动态调参研究
- [ ] 代理模型的性能评估与集成策略优化
- [ ] 更多经典算法的偏置化实现
- [ ] 分布式计算支持与GPU加速

---

## 🤝 贡献指南

欢迎贡献！以下是几种贡献方式：

1. **新增偏置** - 实现新的算法偏置或领域偏置
2. **扩展表征** - 添加新的编码方式、修复算子或变异策略
3. **优化求解器** - 改进现有求解器或添加新算法
4. **丰富示例** - 提供更多实际应用场景的示例代码
5. **完善文档** - 补充文档、注释或使用指南
6. **报告问题** - 提交 Bug 或功能建议

---

## 📄 许可证

MIT License

---

## 📮 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 Issue
- 发起 Pull Request
- 项目讨论区

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给个 Star！⭐**

</div>
