# 09. 定义自己的 Adapter

若只是增加种群成员字段，优先继承 Unit，继续使用已有 Adapter 的搜索决策。标准模板 `pipeline/population_example.py` 提供 AgePopulationUnit/AgePopulationBuilder；在 build_solver 中显式绑定即可。完整代码和成员操作见 [Unit 成员维护](../architecture/UNIT_MEMBER_OPERATIONS_CN.md)。无需重写 NSGA-II 的选择、Solver 生命周期或事务。

Adapter 决定提出哪些候选、如何使用反馈；算法管线负责构建 Unit。本例独立高斯采样，记录最小目标，用来说明接口，不承诺收敛性质。

保存到 Case 的 `adapter/my_adapter.py`。`CandidateProposerAdapter` 继承正式 AlgorithmAdapter，提供候选 Unit、稳定 ID、事务快照和 RNG 恢复；子类显式保存自己的策略状态。

```python
import numpy as np
from nsgablack.adapters import CandidateProposerAdapter


class MyAdapter(CandidateProposerAdapter):
    def __init__(self, population_size=8, sigma=0.5, seed=42):
        super().__init__(name="my_adapter")
        self.population_size = int(population_size)
        self.sigma = float(sigma)
        self.rng = np.random.default_rng(seed)
        self.best_score = None

    def propose(self, control, context):
        rows = self.rng.normal(0, self.sigma,
                              (self.population_size, control.problem.dimension))
        return self.build_candidate_units(rows, context)

    def update(self, control, candidates, feedback, context):
        if len(candidates):
            score = float(np.min(feedback.objectives[:, 0]))
            self.best_score = score if self.best_score is None else min(self.best_score, score)

    def get_state(self):
        return {**super().get_state(), "best_score": self.best_score,
                "population_size": self.population_size, "sigma": self.sigma}

    def set_state(self, state):
        super().set_state(state)
        self.best_score = state["best_score"]
        self.population_size = int(state["population_size"])
        self.sigma = float(state["sigma"])
```

完整 `build_solver.py` 入口如下，保留 Project 的资源授权和组件覆盖：

```python
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline import build_pipeline
from .problem import build_problem
from .adapter.my_adapter import MyAdapter


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(
        problem=build_problem(),
        pipeline=build_pipeline(resource_context=resource_context,
                                component_overrides=component_overrides),
        resource_context=resource_context,
    )
    solver.set_adapter(MyAdapter())
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

在 Project 根执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。使用 `python -m nsgablack project doctor --path . --strict --build --format json` 检查声明和装配。

有内部种群选择的 L2 策略须实现 population mode、CandidateBatch/token 对齐及完整恢复契约，不能照抄本例的 L1 声明。策略组合复用 Composite/Router/Chain；嵌套调用及并行资源分配属于 Project。

## 在多策略组合中读取任务

由 StrategyRouterAdapter 调用的子 Adapter，只需读取一份任务：

```python
from nsgablack.adapters import StrategyTask, StrategyOrigin

# 在子 Adapter.propose/update/repair/disposition 的 context 中：
task = StrategyTask.from_context(context)
owner = task.owner_path     # 实例路径，同一种算法的多个实例也不同
count = task.budget        # 原提案预算；接纳数由 BatchDisposition 给出
region = task.region_id
seeds = task.seeds         # 调用局部数据，不从全局观测回读

# 在结果或 Snapshot 的 CandidateBatch 中查询候选来源：
route = StrategyOrigin.from_candidate(batch.semantic_states[index])
leaf = route[-1]           # 最内层提案者；route 从外到内排列
```

`role/strategy_id/phase/region_id` 等局部键仍由任务生成，便于已有组件消费；全局 `strategy_id` 不能表示所有候选来源。观测使用 `unit_tasks` 的轻量摘要和 `strategy_instances` 的各实例切片。来源和 token 随候选筛选及快照往返，不按数值相等反查。
