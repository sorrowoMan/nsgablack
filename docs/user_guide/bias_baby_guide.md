# 偏置系统宝宝级教程

本教程按“偏置类型”来讲，告诉你**怎么写**、**怎么接**、**什么时候用**。  
一句话记住：**偏置就是给优化过程一个额外的“倾向”**。

---

## 先选类型（最快决策）

| 你想做什么 | 选哪类偏置 | 写在哪里 | 谁会用 |
| --- | --- | --- | --- |
| 直接改目标值（奖励/惩罚） | 函数式偏置 `BiasModule` | 任意脚本/模块 | `EvolutionSolver` |
| 需要上下文/更复杂逻辑 | 类偏置 `AlgorithmicBias/DomainBias` | `bias/algorithmic` 或 `bias/domain` | 偏置管理器或自定义流程 |
| 让算法“变成偏置” | 算法偏置（本质还是类偏置或函数偏置） | 同上 | 同上 |
| 减少真实评估次数（代理评估） | L4 评估提供器 `SurrogateEvaluationProviderPlugin(...).build_provider()` | `evaluation_mediator` | `ComposableSolver` / `SolverBase` |

---

## A. 函数式偏置（最简单，最稳）

**适合**：你只想给目标值加个惩罚/奖励。  
**接口**：传入函数即可，函数可以写成 `f(x)`、`f(x, constraints)` 或 `f(x, constraints, context)`。

### 第一步：写偏置函数

```python
import numpy as np

def constraint_penalty(x, constraints, context):
    # 违规越多，惩罚越大
    g = np.maximum(0.0, np.asarray(constraints)).sum()
    return {"penalty": g, "constraint": g}

def business_reward(x, constraints, context):
    # 奖励越大越好
    return {"reward": float(np.mean(x))}
```

### 第二步：组装 BiasModule

```python
from nsgablack.bias import BiasModule

bias = BiasModule()
from nsgablack.bias.domain import CallableBias

bias.add(CallableBias(name="constraint", func=constraint_penalty, weight=1.0, mode="penalty"))
bias.add(CallableBias(name="business", func=business_reward, weight=0.05, mode="reward"))
```

### 第三步：挂到 NSGA 求解器

```python
solver.enable_bias = True
solver.bias_module = bias
```

### 返回值规则（非常重要）

函数返回可以是：
- **数值**：直接当作 penalty/reward
- **字典**：支持 `penalty` / `reward` / `value`  
  还可以加 `constraint` 或 `constraints`，会被累计进约束列表

---

## B. 类偏置（算法偏置 / 业务偏置）

**适合**：你需要“更复杂逻辑/上下文”。  
**接口**：继承 `AlgorithmicBias` 或 `DomainBias`，实现 `compute()`。

### 示例 1：算法偏置（更偏搜索策略）

```python
from nsgablack.bias.core.base import AlgorithmicBias, OptimizationContext
import numpy as np

class DiversityBias(AlgorithmicBias):
    def compute(self, x, context: OptimizationContext) -> float:
        pop = np.asarray(context.population) if context.population else None
        if pop is None or len(pop) == 0:
            return 0.0
        d = np.mean(np.linalg.norm(pop - x, axis=1))
        return -d  # 负号=奖励多样性
```

注意：`context.population` 由 SnapshotStore 通过 `population_ref/snapshot_key` 解析填充。  
如果你在自定义流程中手动构造 context，需要提供快照引用或直接传入 population。

### 示例 2：业务偏置（更偏业务规则）

```python
from nsgablack.bias.core.base import DomainBias, OptimizationContext

class SupplyRuleBias(DomainBias):
    def compute(self, x, context: OptimizationContext) -> float:
        # 业务规则：总量不能超过1000
        violation = max(0.0, float(x.sum()) - 1000.0)
        return violation
```

### 这种偏置怎么用？

你可以用偏置管理器在自定义流程里计算：

```python
from nsgablack.bias.core.manager import AlgorithmicBiasManager

manager = AlgorithmicBiasManager()
manager.add_algorithmic_bias(DiversityBias("diversity", weight=0.2))
# manager.compute_total_bias(x, context)
```

如果你只想快速接到 NSGA-II，**建议仍然用 A 类函数偏置**（最省事）。

---

## C. “算法偏置化”怎么理解

意思是：**把一个算法的结果当作“偏置值”**。  
比如你用局部搜索/启发式给一个解打分，然后把分数当作奖励或惩罚。

两种写法都可以：
- 写成函数偏置（A类）
- 写成算法偏置类（B类）

**一句话**：算法产出一个“分数”，你把分数变成 penalty/reward 就行。

---

## D. 代理评估（L4 Provider）

**适合**：`evaluate(x)` 很贵（仿真/调度/训练），你想“少做真实评估”，把更多候选交给代理模型排序/筛选。

框架当前推荐的落地方式是：通过 L4 `EvaluationProvider` 接入代理评估，保持 solver 主流程不变。

### 最小示例（ComposableSolver）

```python
import numpy as np
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.utils.plugins import SurrogateEvaluationProviderPlugin, SurrogateEvaluationConfig

class MyProblem(BlackBoxProblem):
    def __init__(self, dim=10):
        super().__init__(name="my_problem", dimension=dim, bounds={f"x{i}": (-5.0, 5.0) for i in range(dim)})
    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))

class RandomBatch(AlgorithmAdapter):
    def __init__(self, n=64):
        super().__init__(name="random_batch")
        self.n = int(n)
    def propose(self, solver, context):
        lows = np.array([solver.var_bounds[f\"x{i}\"][0] for i in range(solver.dimension)], dtype=float)
        highs = np.array([solver.var_bounds[f\"x{i}\"][1] for i in range(solver.dimension)], dtype=float)
        return [np.random.uniform(lows, highs, size=solver.dimension) for _ in range(self.n)]

solver = ComposableSolver(problem=MyProblem(dim=16), adapter=RandomBatch(n=64))
solver.max_steps = 20

cfg = SurrogateEvaluationConfig(
    min_train_samples=40,   # 数据不足时全真评估并积累训练数据
    min_true_evals=8,       # 每代至少做多少次真实评估（保底）
    topk_exploit=8,         # 额外：挑预测最优的 top-k 做真评估（防偏）
    topk_explore=8,         # 额外：挑不确定性最高的 top-k 做真评估（主动学习）
)
solver.register_evaluation_provider(
    SurrogateEvaluationProviderPlugin(config=cfg, model_type=\"rf\").build_provider()
)
solver.run()
```

### 说明（避免误解）

- 代理评估是 L4 能力，不是 core solver 的默认行为；你可以随时开关它做消融对比。
- `bias/surrogate` 下的控制类（`SurrogateControlBias`）目前主要作为预留扩展点；如果你需要“分阶段动态调预算”，建议先在插件/adapter 层显式实现，再沉淀成稳定契约。

---

## 文件与命名建议（按你的规范）

| 偏置类型 | 建议放哪 | 备注 |
| --- | --- | --- |
| 函数偏置 | 任意脚本/模块 | 可直接挂 `BiasModule` |
| 算法偏置 | `bias/algorithmic/xxx.py` | 做复杂搜索策略 |
| 业务偏置 | `bias/domain/xxx.py` | 做规则/约束 |
| 代理偏置 | `bias/surrogate/xxx.py` | 控制代理流程 |

**习惯**：每写一个偏置类，旁边放一个同名 `*.md` 说明用途和参数。

---

## 一句话总结

- **想快**：用函数偏置（A类）。  
- **想复杂**：用类偏置（B类）。  
- **想控制代理流程**：用代理偏置（D类）。  
  
需要我给你写模板文件和目录脚手架的话，告诉我偏置类型即可。
