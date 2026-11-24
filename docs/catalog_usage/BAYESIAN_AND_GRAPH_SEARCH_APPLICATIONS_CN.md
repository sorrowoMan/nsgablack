# 贝叶斯与图搜索：从正式 Case 装配到准确读取结果

本书是 Catalog 的分组件用法来源。每章独立列出宿主、文件、运行入口和结果含义。以下新片段已经按当前源码核对，不表示已经执行这些改写后的算法，也不承诺某个预算下必然求得最优解。

## adapter.bayesian_optimization · 让模型、采集函数与真实观测各负其责

**什么时候用**：每次真实求值较贵，希望先用已有观测拟合代理，再从有限允许集合中选择下一次求值的位置。这个实现支持单目标最小化；它不是给任意 Adapter 加上的一个软 Bias。

**先准备什么**：使用已有 Project `examples/cases/algorithm_semantics/` 的 `cases/synchronous_bo/`。保留其 `config.py`、`problem/`、`pipeline/`、`bias/`、`plugins/` 和 `build_solver.py`。Problem 定义一维 `[0,1]` 上的 `(x-0.25)**2`；pipeline 只有 ClipRepair；默认初始点是 0 和 1。依赖当前 blackbase、nsgablack、NumPy，不调用外部模型 API，也不需要 GPU。

**放在哪**：只替换该 Case 的 `adapter/__init__.py`，保留下面完整工厂。现有 builder 已执行 `build_adapter()`，将结果传入 ComposableSolver，同时连接原问题、管线、Bias、checkpoint、BOReport 与 Project 发放的 ResourceContext。不要另建一层 run 循环。

**接入步骤**：模型负责拟合和后验；采集函数把后验转换为值得尝试的程度；采集优化器在声明的网格上取最小值；Adapter 安排这几者并提出候选。第一次提案先送评两个初始点，以后每步从网格提一个点。提案仍经过原 repair、真实 Problem、接纳和提交。

```python
# cases/synchronous_bo/adapter/__init__.py：完整替换
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, FixedRBFPosterior,
    LowerConfidenceBound, GridAcquisitionOptimizer,
)


def build_adapter():
    return BayesianOptimizationAdapter(
        model=FixedRBFPosterior(),
        acquisition=LowerConfidenceBound(beta=2.0),
        optimizer=GridAcquisitionOptimizer(
            grid=((0.25,), (0.5,), (0.75,))),
    )
```

这里 FixedRBFPosterior 是固定超参数的零均值精确 GP，没有暗中做超参数优化；LCB 是 `mean - beta * std`；网格并列时保留给定顺序。Adapter 从归属于自身、经过验证的 Evaluation Event 重建训练观测，使用 raw 目标，不把 Bias 调整后的评分或当前成员数组当训练集。被接纳与“已经真实求值”是不同事实；接纳策略拒绝某行也不会抹掉已经发生的求值证据。

**怎样判断接对**：运行后打开本 Project 的 `results/synchronous_bo/summary.json`。检查本轮 `run_id`、`pool_id`、`evaluations`、`problem_calls`、`observations`、`model_revision`、`last_acquisition` 和 `resource_binding_current`。`observations[*].x/y` 是代理训练数据；`last_acquisition.grid/mean/std/acquisition/selected_index` 是最近一次选点的解释。`raw_best` 取真实观测最小值。默认网格包含 0.25，但这里不预写一次新运行的数值结果。报告由原 BOReport 同时发布正式 summary Artifact；本地 JSON 是方便查看的副本，应按运行身份区别旧结果。

不要用 `get_solution_pool_roots()` 的保留引用数冒充训练样本数，不要把 `algorithm_unit` 在尚未启用时为 None 误判为装配失败。checkpoint 恢复重建模型数值缓存，并核对模型、采集函数、网格和初始点解释；不能在恢复时悄悄换一套配置。

**运行入口**：在 nsgablack 仓库根执行，`synchronous_bo` 是 Project 已存在的独立组，只运行这个 Case。

```bash
python examples/cases/algorithm_semantics/run_project.py --group synchronous_bo
```

### 变体一：业务只允许有限档位，限制采集搜索域

例如设备只允许 0.2、0.4、0.8 三个档位。替换同一个完整工厂；初始点也使用合法档位，Problem 与修复管线保持原含义。

```python
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, BayesianOptimizationConfig,
    FixedRBFPosterior, LowerConfidenceBound, GridAcquisitionOptimizer,
)


def build_adapter():
    return BayesianOptimizationAdapter(
        config=BayesianOptimizationConfig(initial_points=((0.2,), (0.8,))),
        model=FixedRBFPosterior(),
        acquisition=LowerConfidenceBound(beta=2.0),
        optimizer=GridAcquisitionOptimizer(grid=((0.2,), (0.4,), (0.8,))),
    )
```

检查 problem_calls 与最后 grid 都落在三个档位；最优档位并不等于连续问题的 0.25。真实业务 Problem 仍须独立检查合法性，网格限制不能替代安全约束。

### 变体二：替换“值得试”的规则，而非改真实目标

若不愿为不确定位置花预算，可以用保守的 `mean + std`；这是一条新的采集规则。替换该 Case 工厂，原报告仍能解释每个网格值。

```python
import numpy as np
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, FixedRBFPosterior, GridAcquisitionOptimizer,
)


class ConservativeAcquisition:
    component_state_mode = "stateless"

    def describe(self):
        return {"type": "case.conservative_acquisition/v1"}

    def __call__(self, mean, std):
        return np.asarray(mean) + np.asarray(std)


def build_adapter():
    return BayesianOptimizationAdapter(
        model=FixedRBFPosterior(), acquisition=ConservativeAcquisition(),
        optimizer=GridAcquisitionOptimizer(),
    )
```

检查 acquisition 与 mean/std 的公式对应，observations.y 仍来自原 Problem。describe 是稳定恢复解释；本例无状态，有私有训练状态的组件不能仅改这个字符串就声称 stateless。当前 BO 没有声明任意投影子池的通用精修任务支持；不能仅因 VNS 支持就认为 BO 也已接通。

## adapter.astar · 邻接关系、边代价与目标结果要一起定义

**什么时候用**：解是图上的状态，希望沿明确邻接边扩展，并用启发式安排搜索。节点的路径代价 g 不是 Problem 的某一个 raw 目标。

**先准备什么**：使用现有 `examples/cases/catalog_recipes/` 中 `cases/astar/` 的标准脚手架。下面把这个 Case 的三个文件完整替换为一个小网格示例，再在 Project 中明确启用它。状态是两个坐标，取值 0 至 4；每次只向右或向上走一格，目标是 `(4,4)`。不需要随机初始化或变异，默认节点 UnitBinding 已由 AStarAdapter 提供。

**放在哪**：Problem 放 `cases/astar/problem/__init__.py`，管线放 `cases/astar/pipeline/main.py`，同时把 pipeline 包入口改成下方薄导出，装配放 `cases/astar/build_solver.py`。保留两个规范运行入口；下面各段按文件分别保存。

**接入步骤**：Problem 只声明候选和约束语义，raw 目标固定为 0；累计代价完全来自 edge_cost。管线虽有 ClipRepair，neighbors 只产生合法点，所以正常路径不会被裁剪。`pool_start_policy="new_root"` 让起点先按正式求值/接纳流程进入池，再扩展新树。

```python
# cases/astar/problem/__init__.py
import numpy as np
from nsgablack.core import BlackBoxProblem


class GridProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="grid_path", dimension=2,
                         bounds=[(0, 4), (0, 4)], objectives=["feasibility"])

    def evaluate(self, candidate):
        return [0.0]

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return [float(np.maximum(-x, 0).sum()
                      + np.maximum(x - 4, 0).sum()
                      + np.abs(x - np.round(x)).sum())]


def build_problem():
    return GridProblem()
```

```python
# cases/astar/pipeline/main.py
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline(*, resource_context=None, component_overrides=None):
    return RepresentationPipeline(repair=ClipRepair(low=0.0, high=4.0))
```

```python
# cases/astar/pipeline/__init__.py：本例只导出使用的工厂
from .main import build_pipeline

__all__ = ["build_pipeline"]
```

```python
# cases/astar/build_solver.py
import json
from pathlib import Path
import numpy as np
from nsgablack.core import ComposableSolver
from nsgablack.adapters import AStarAdapter
from nsgablack.plugins.base import Plugin
from nsgablack.project import apply_solver_component_overrides
from .problem import build_problem
from .pipeline import build_pipeline


def neighbors(state, context):
    x = np.asarray(state)
    return [x + delta for delta in (np.array([1, 0]), np.array([0, 1]))
            if np.all(x + delta <= 4)]


def heuristic(state, context):
    return float(np.sum(4 - np.asarray(state)))


def goal(state, context):
    return bool(np.array_equal(state, [4, 4]))


def edge_cost(parent, child, context):
    return 1.0


class PathReport(Plugin):
    def __init__(self):
        super().__init__(name="path_report")

    def on_solver_finalized(self, result):
        solver = self.solver
        owner = solver.adapter
        data = {"run_id": solver.run_session.run_id,
                "found": owner.found,
                "solution": None if owner.solution is None else owner.solution.tolist(),
                "best_score": owner.best_score,
                "evaluations": solver.evaluation_count}
        output = Path(__file__).resolve().parent / "results" / "path.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def build_solver(*, config=None, resource_context=None, component_overrides=None):
    owner = AStarAdapter(neighbors=neighbors, goal_test=goal,
        heuristic=heuristic, edge_cost=edge_cost, start_state=np.zeros(2),
        path_cost_mode="edge", objective_weight=0.0,
        pool_start_policy="new_root", repair_policy="reject")
    solver = ComposableSolver(build_problem(), adapter=owner,
        representation_pipeline=build_pipeline(), resource_context=resource_context)
    solver.set_max_steps(40)
    solver.add_plugin(PathReport())
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

以上报告默认要求实际 owner 仍是所装配 AStarAdapter；若 component_overrides 换成复合 Adapter，报告也要改为保留真实叶实例，不能对容器猜字段。报告只在最终提交后写本地观察副本，不发布新的权威最短路径 Artifact。

**怎样判断接对**：打开 `cases/astar/results/path.json`，检查当前 run_id、found、solution 和 evaluations。目标解读 `owner.solution`；`best_state/best_score` 按 Problem 原始目标加违反惩罚选择，本例目标全是 0，所以它们不能代表“走到了目标”或完整路径。也不要用 Solver 的 incumbent 代替图的目标结果。正常 neighbors 不越界，repair 不应改变子节点；默认 reject 会阻止候选被修复后沿用旧边。这个例子的启发式与单位边长度相配，但教程没有执行证明或有限预算下的最优保证。

**运行入口**：catalog_recipes 默认只跑 composite，并不会自动遍历所有 Case。保留其 `L0`，把 Project 的 STAGES/GROUPS 改为下面内容后，从仓库根运行。运行时授权仍由 Project 发放。

```python
# examples/cases/catalog_recipes/project_config.py：替换 STAGES 与 GROUPS
STAGES = [{"name": "astar_demo", "policy": "serial", "cases": ["astar"],
           "case_modes": {"astar": "build"},
           "resource_requests": {"astar": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["astar_demo"]}}
```

```bash
python examples/cases/catalog_recipes/run_project.py
```

### 变体一：用邻接规则绕开障碍，不让 repair 偷换路径

只替换 builder 中的 neighbors；其余文件、目标和报告不变。起终点不在障碍中。

```python
BLOCKED = {(1, 1), (1, 2), (2, 2)}


def neighbors(state, context):
    x = np.asarray(state)
    points = [x + delta for delta in (np.array([1, 0]), np.array([0, 1]))]
    return [p for p in points if np.all(p <= 4) and tuple(p.astype(int)) not in BLOCKED]
```

真实业务还应在 Problem 中声明障碍违反量，避免外部输入绕过邻居生成器；若新增跨越、传送或修复后重接边，必须重新定义 edge_cost/heuristic 与合法边含义，不能简单把 repair_policy 改成 recompute 当作正确性证明。

## adapter.moa_star · 多目标标签保留权衡，展开优先级只决定先看谁

**什么时候用**：一个状态可能有多个互不支配的标签，需要保留权衡，同时按一个标量优先级安排展开。priority_weights 不会把所有标签改成单目标。

**先准备什么**：使用 `examples/cases/catalog_recipes/cases/moa_star/` 的标准脚手架。以下完整替换其三个文件，得到一个容易核对的状态权衡示例：状态 `x∈{0,1,2,3,4}`，两个 raw 目标为 `x²` 与 `(4-x)²`。这里采用 objective 模式，g 表示当前状态的目标，不是累积路径开销。起点 0，目标状态 4；不在找到第一个目标后停下。

**放在哪**：分别放入该 Case 的 problem、pipeline/main.py、pipeline/__init__.py 和 build_solver.py，保留 run_solver.py 与 alias。与 A* 是两个独立 Case，不从 A* 章节隐式导入对象。

**接入步骤**：邻居只在有界整数集合中移动；显式 new_root 先求值起点。每次真实反馈生成标签，同状态的支配规则负责保留标签，scalar priority 只排队。下面报告把全局 Pareto 标签与目标状态分别写出。

```python
# cases/moa_star/problem/__init__.py
import numpy as np
from nsgablack.core import BlackBoxProblem


class TradeoffProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="state_tradeoff", dimension=1,
                         bounds=[(0, 4)], objectives=["left", "right"])

    def evaluate(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [x * x, (4 - x) ** 2]

    def evaluate_constraints(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [max(0, -x, x - 4) + abs(x - round(x))]


def build_problem():
    return TradeoffProblem()
```

```python
# cases/moa_star/pipeline/main.py
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline(*, resource_context=None, component_overrides=None):
    return RepresentationPipeline(repair=ClipRepair(low=0.0, high=4.0))
```

```python
# cases/moa_star/pipeline/__init__.py
from .main import build_pipeline

__all__ = ["build_pipeline"]
```

```python
# cases/moa_star/build_solver.py
import json
from pathlib import Path
import numpy as np
from nsgablack.core import ComposableSolver
from nsgablack.adapters import MOAStarAdapter
from nsgablack.plugins.base import Plugin
from nsgablack.project import apply_solver_component_overrides
from .problem import build_problem
from .pipeline import build_pipeline


def neighbors(state, context):
    x = float(np.asarray(state)[0])
    return [np.array([y]) for y in (x - 1, x + 1) if 0 <= y <= 4]


def goal(state, context):
    return bool(float(np.asarray(state)[0]) == 4.0)


class LabelReport(Plugin):
    def __init__(self):
        super().__init__(name="label_report")

    def on_solver_finalized(self, result):
        solver = self.solver
        owner = solver.adapter
        data = {"run_id": solver.run_session.run_id,
                "found": owner.found,
                "goal_states": [x.tolist() for x in owner.goal_states],
                "pareto_states": [x.tolist() for x in owner.pareto_states],
                "pareto_costs": [x.tolist() for x in owner.pareto_costs],
                "evaluations": solver.evaluation_count}
        output = Path(__file__).resolve().parent / "results" / "labels.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def build_solver(*, config=None, resource_context=None, component_overrides=None):
    owner = MOAStarAdapter(neighbors=neighbors, goal_test=goal,
        start_state=np.array([0.0]), path_cost_mode="objective",
        pool_start_policy="new_root", repair_policy="reject", stop_on_goal=False)
    solver = ComposableSolver(build_problem(), adapter=owner,
        representation_pipeline=build_pipeline(), resource_context=resource_context)
    solver.set_max_steps(20)
    solver.add_plugin(LabelReport())
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

**怎样判断接对**：查看 `cases/moa_star/results/labels.json` 的当前 run_id。pareto_states 与 pareto_costs 按行对齐，本例 objective 模式应能按公式检查每个已记录点的两个成本；不能把某个数组长度预写成这次的新运行结果。goal_states 单独表示命中目标的状态，没有与之自动对齐的公开 goal_costs 字段。全局 Pareto 标签也包括非目标状态，因此不要把 pareto_costs 当“所有终点的路径成本”。Solver incumbent 是另一种最终偏好结果，不替代标签集。这里未演示更换 component_overrides 后的自定义结果观察。

**运行入口**：保留 catalog_recipes/project_config.py 的 L0，仅替换 STAGES/GROUPS 如下，然后从仓库根运行。默认的 composite 组不会自动运行本章。

```python
STAGES = [{"name": "moa_demo", "policy": "serial", "cases": ["moa_star"],
           "case_modes": {"moa_star": "build"},
           "resource_requests": {"moa_star": {"threads": 1, "gpus": 0, "backend": "local"}}}]
GROUPS = {"default": {"stages": ["moa_demo"]}}
```

```bash
python examples/cases/catalog_recipes/run_project.py
```

### 变体一：按业务倾向安排先后，仍保留双目标标签

只替换 builder 中构造 owner 的表达式；Problem、报告、管线与 Project 入口不变。下面额外允许跨两格，使同一轮有多个不同优先级的候选可供展开。

```python
def jump_neighbors(state, context):
    x = float(np.asarray(state)[0])
    return [np.array([y]) for y in (x - 1, x + 1, x + 2) if 0 <= y <= 4]


def build_owner():
    return MOAStarAdapter(neighbors=jump_neighbors, goal_test=goal,
        start_state=np.array([0.0]), path_cost_mode="objective",
        priority_mode="weighted", priority_weights=(0.8, 0.2),
        pool_start_policy="new_root", repair_policy="reject", stop_on_goal=False)
```

在原 build_solver 中用 `owner = build_owner()` 替换原 owner 赋值。权重只控制 open list 的排序；raw 目标仍是两个数，标签之间仍按向量支配。如果改成 edge 模式，需要明确每条边的成本向量、是否再加 Problem 贡献与启发式含义；单纯换开关不等于得到正确的多目标最短路。投影子池标量目标也不能直接冒充路径 g，当前 Adapter 会拒绝此类反馈。
