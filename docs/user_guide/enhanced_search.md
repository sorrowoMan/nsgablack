# 多策略协同（StrategyRouterAdapter）

本页讲清楚一件事：当你不想把“探索/开发/局部搜索/启发式”硬塞进一个算法里时，框架推荐你把它们拆成多个 Adapter，让一个控制器负责“协同与信息共享”。

对应组件：

- 控制器：`adapters/multi_strategy/adapter.py` (`StrategyRouterAdapter`)
- 装配方式：在 `build_solver.py` 直接 `solver.set_adapter(...)`
- 共享事实（可选）：`plugin.pareto_archive`（按需 `solver.add_plugin(...)`）

## 1) 什么时候需要“多策略协同”

典型信号：

- 你已经有一个能跑的主流程，但不同阶段需要不同搜索强度（先探索、后开发）
- 单一算子/单一策略在某些约束模式下很吃亏（需要启发式修复/邻域搜索补强）
- 你想做消融：开关某个策略，看它到底贡献了什么（而不是改一坨大算法）

## 2) 最小示例：两个角色（explorer / exploiter）

```python
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import (
    MultiStrategyConfig,
    StrategyRouterAdapter,
    RoleSpec,
    VNSAdapter,
    SimulatedAnnealingAdapter,
)

solver = ComposableSolver(problem=problem, adapter=VNSAdapter())  # 先随便给一个，后面会被 controller 接管

roles = [
    RoleSpec(
        name="explorer",
        adapter_factory=lambda: SimulatedAnnealingAdapter(),
        n_units=2,
        weight=1.0,
    ),
    RoleSpec(
        name="exploiter",
        adapter_factory=lambda: VNSAdapter(),
        n_units=2,
        weight=1.0,
    ),
]

cfg = MultiStrategyConfig(
    total_batch_size=64,                   # 每代总共提案多少候选（所有角色合计）
    objective_aggregation="sum",           # 多目标排序用什么聚合方式（工程口径）
    adapt_weights=True,                   # 是否根据效果动态调权重
    stagnation_window=10,                 # “停滞”窗口（用于触发调整）
    phase_schedule=(("explore", 30), ("exploit", -1)),  # 前30代探索，其后开发
    phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},
)

solver.set_adapter(StrategyRouterAdapter(roles=roles, config=cfg))
solver.max_steps = 80
solver.run()
```

你得到的好处是：

- 每个策略的实现保持独立（可复用、可替换、可测）
- 控制器能统一调度候选预算、阶段、权重与共享状态
- 你可以直接做消融：删掉一个 RoleSpec 就能比较效果

## 3) 推荐用法：用 Wiring 做权威装配

当你不想手动记“要不要挂 ParetoArchive”等细节时，直接用 Wiring：

```python
from nsgablack.adapters import StrategyRouterAdapter
from nsgablack.plugins import ParetoArchivePlugin

solver.set_adapter(StrategyRouterAdapter(roles=roles, config=cfg))
solver.add_plugin(ParetoArchivePlugin())  # optional
```

## 4) 和并行评估怎么配合

多策略协同解决的是“搜索机制与信息流”，并行评估解决的是“真实评估太慢”。

两者可以叠加：

- 多策略：用 `ComposableSolver + StrategyRouterAdapter`
- 并行：用 `with_parallel_evaluation(ComposableSolver)` 或在 wiring 中装配并行能力

并行评估的详细用法见：`docs/user_guide/parallel_evaluation.md`

