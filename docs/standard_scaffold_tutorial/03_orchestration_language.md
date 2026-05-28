# 03. 复杂编排怎么写

`nsgablack` 的复杂编排不是把所有逻辑塞进一个 adapter，而是把不同职责放到不同层：

| 编排类型 | 应放位置 | 解决什么问题 |
| --- | --- | --- |
| 单 solver 内多策略 | Adapter orchestration | 多种搜索策略协同 |
| warmup/exploit 阶段切换 | Serial strategy | 搜索流程随时间推进 |
| 事件驱动切换 | Event strategy | 根据运行信号启用策略 |
| 嵌套评估 | Problem/Evaluation bridge + Plugin | 外层候选触发内层 solver/flow |
| 多 solver 调度 | Solver orchestration | 多个 solver fanout 与结果聚合 |
| 内层组件参数优化 | Representation decode + component_overrides | 外层 genome 控制内层组件 |

## 0. 术语与组件引用

本章默认读者已经知道标准脚手架里的几个核心组件。复杂编排的关键不是“多写几个 if/else”，而是把每种变化放回正确组件层：搜索策略放 `Adapter`，候选表示放 `RepresentationPipeline`，目标约束放 `Problem`，运行能力放 `Plugin`，资源授权放 `L0 Resource`。

| 术语 / 组件 | 在本章中的含义 | 详解入口 |
| --- | --- | --- |
| Solver | 控制平面，负责生命周期、评估入口、插件调度和状态访问 | [组件导读索引](../guides/README.md) |
| Adapter | 搜索策略平面，负责 `propose/update`，可以被 `group/multi/serial/event` 编排 | [DECOUPLING_ADAPTER](../guides/DECOUPLING_ADAPTER.md) |
| RepresentationPipeline / pipeline | 候选解表示管线，负责 `init/mutate/repair/encode/decode` 和 typed genome | [DECOUPLING_REPRESENTATION](../guides/DECOUPLING_REPRESENTATION.md) |
| Problem | 目标与约束平面，负责把候选映射为 objectives / violations | [DECOUPLING_PROBLEM](../guides/DECOUPLING_PROBLEM.md) |
| Plugin / event signal | 生命周期能力层，适合写 checkpoint、trace、event signal、report、短路评估 | [DECOUPLING_CAPABILITIES](../guides/DECOUPLING_CAPABILITIES.md) |
| Bias | 软引导层，适合注入 seed、domain prior、候选偏好，不替代硬约束 | [DECOUPLING_BIAS](../guides/DECOUPLING_BIAS.md) |
| Context / Snapshot | 轻量运行信号与大对象引用层，event 策略通常读 context，population/artifact 进 snapshot | [04. 验证、Catalog 与演进](04_validation_catalog_and_evolution.md) |
| L0 Resource / ResourceContext | 并行与资源授权层，负责 CPU/thread/GPU/device token/lease/heartbeat | [06. L0 并行与资源模式](06_l0_parallel_resource_patterns.md) |
| Inner Bridge | 嵌套评估桥，把外层候选转换为内层 solver/flow 任务，再把结果投影回外层目标约束 | [组件导读索引](../guides/README.md) |

同名词提醒：本章里的 `pipeline` 指 `nsgablack` 的候选解表示管线，不是 `mlblack` 的数据/特征处理 pipeline。跨框架时应以 `05_cross_framework_coordination.md` 的术语表为准。

## 1. 单策略 baseline

适用场景：

- 第一次验证 problem/pipeline 是否正确。
- 建立 baseline。
- 先排除复杂编排带来的噪声。

```python
search_adapter = group(cfg.adapters, "baseline", ["vns"])
solver.set_adapter(search_adapter)
```

验收重点：

- `propose` 能生成候选。
- `evaluate_population` 能返回目标和约束。
- `update` 能接收反馈。
- 单代或少量代数可以稳定运行。

## 2. explore/exploit 多策略

适用场景：同一个问题中需要“广泛探索”和“局部开发”同时存在。

```python
explore = group(cfg.adapters, "explore", ["vns"])
exploit = group(cfg.adapters, "exploit", ["example_adapter"])
search = multi(cfg.adapters, "explore_exploit", [explore, exploit])
solver.set_adapter(search)
```

语义：

- `group(...)` 把若干 adapter 包成一个策略组。
- `multi(...)` 生成 `StrategyRouterAdapter`。
- 多策略共同提出候选。
- solver 统一评估候选。
- adapter router 统一分发反馈。

不要这样写：

```python
# 错误：在 problem.evaluate 里随机切换搜索策略
if random.random() < 0.5:
    use_vns()
else:
    use_de()
```

搜索策略属于 adapter，不属于 problem。

### 2.1 一个 group 内多个 adapter

`group(...)` 不是“目录分组”，而是一个可运行的 adapter 组合单元。组内每个 adapter 都有自己的 `propose/update` 状态，solver 只看到一个统一的 search adapter。

最小可运行例子：

```python
# 默认脚手架通常已经注册 vns 和 example_adapter。
search = group(
    cfg.adapters,
    "baseline_plus_random",
    ["vns", "example_adapter"],
)
solver.set_adapter(search)
```

如果项目已经在 `adapter/config.py` 里注册了更多 adapter，可以把同一类策略放进同一个 group：

```python
population_explore = group(
    cfg.adapters,
    "population_explore",
    ["nsga2", "de", "sa"],
)

local_refine = group(
    cfg.adapters,
    "local_refine",
    ["vns", "trust_region_dfo"],
)
```

组内语义：

- 每个 child adapter 负责提出一部分候选。
- solver 统一走 representation、repair、evaluation。
- controller 根据候选来源，把目标和约束反馈回对应 adapter。
- group 内 adapter 共享同一个 problem、representation、resource context 和 solver 生命周期。

适合放在同一个 group 的情况：

| 情况 | 例子 |
| --- | --- |
| 目标和约束完全相同 | 都在优化同一个 Pareto problem |
| representation 相同 | 都提出同一种 genome |
| 资源上下文相同 | 都由同一个 solver 控制评估预算 |
| 策略互补 | 一个偏全局，一个偏局部，一个偏扰动 |

不适合放进同一个 group 的情况：

| 情况 | 应该怎么做 |
| --- | --- |
| problem 不同 | 用多 solver orchestration |
| representation 不同且难以统一 | 用不同 solver 或不同 phase |
| 资源预算完全不同 | 用 solver orchestration + L0 resource allocator |
| inner runtime 不同且报告口径不同 | 做成不同 regime，再聚合结果 |

### 2.2 多个 group 并行协同

一个 group 已经可以包含多个 adapter；多个 group 还可以再通过 `multi(...)` 组合成更大的 portfolio。这个结构适合表达“策略组”之间的并行协作。

```python
global_group = group(
    cfg.adapters,
    "global_group",
    ["nsga2", "de"],
)

local_group = group(
    cfg.adapters,
    "local_group",
    ["vns", "trust_region_dfo"],
)

robust_group = group(
    cfg.adapters,
    "robust_group",
    ["sa", "moead"],
)

search = multi(
    cfg.adapters,
    "global_local_robust_portfolio",
    [global_group, local_group, robust_group],
)
solver.set_adapter(search)
```

这类结构的语义是：

```text
single solver
  -> portfolio router
      -> global_group router
          -> nsga2
          -> de
      -> local_group router
          -> vns
          -> trust_region_dfo
      -> robust_group router
          -> sa
          -> moead
  -> one evaluation pipeline
  -> feedback routed back to original child adapter
```

这种写法可以表达很多复杂搜索形态：

| 结构 | 写法 | 语义 |
| --- | --- | --- |
| 单 adapter | `group(..., ["vns"])` | 退化为普通单策略 |
| 单 group 多 adapter | `group(..., ["vns", "de"])` | 同一阶段多策略协同 |
| 多 group 并行 | `multi(..., [group_a, group_b])` | 多个策略组共同提出候选 |
| group 内全局 + 局部 | `group(..., ["nsga2", "vns"])` | 同一阶段混合探索和开发 |
| group 内模型 + 搜索 | `group(..., ["mas", "trust_region_dfo"])` | surrogate/search 协作 |

注意：嵌套 group 会让 trace 层级变深。如果你需要非常清晰的报告字段，建议把每个 group 的构造封装成具名函数，例如 `build_global_group(cfg)`、`build_local_group(cfg)`，并在 report 中记录 group 名称和 adapter 名称。

## 3. warmup -> exploit 串行阶段

适用场景：先探索，再利用已有解进行局部细化。

```python
explore = group(cfg.adapters, "explore", ["vns"])
exploit = group(cfg.adapters, "exploit", ["example_adapter"])

search = serial(
    cfg.adapters,
    "warmup_then_exploit",
    [
        phase("warmup", explore, steps=20),
        phase("exploit", exploit, steps=-1),
    ],
)
solver.set_adapter(search)
```

如果需要按运行信号推进阶段：

```python
search = serial(
    cfg.adapters,
    "signal_driven_flow",
    [
        phase("warmup", explore, advance_when=gt(ctx("generation"), 10)),
        phase("exploit", exploit, advance_when=exists(ctx("best_x"))),
    ],
)
```

条件语言：

| 函数 | 作用 |
| --- | --- |
| `ctx("a.b")` | 从 context 读路径 |
| `exists(ref)` | 判断不为空 |
| `truthy(ref)` | 判断真值 |
| `gt/ge/lt/le/eq/ne` | 比较 |
| `all_of/any_of/not_` | 组合条件 |
| `custom(fn)` | 自定义只读条件 |

原则：

- 条件只读 context。
- 阶段推进放在 orchestration layer。
- adapter 内不要私下判断业务阶段。

### 3.1 多 adapter group 之间串行

`serial(...)` 的每个 phase 接收的是一个 adapter object。这个 adapter object 可以是单 adapter，也可以是一个 `group(...)` 返回的多策略 controller。因此，常见正式写法是“阶段之间串行，阶段内部多策略协同”。

```python
bootstrap_group = group(
    cfg.adapters,
    "bootstrap_group",
    ["nsga2", "de"],
)

refine_group = group(
    cfg.adapters,
    "refine_group",
    ["vns", "trust_region_dfo"],
)

robust_group = group(
    cfg.adapters,
    "robust_group",
    ["sa", "moead"],
)

search = serial(
    cfg.adapters,
    "bootstrap_refine_robust",
    [
        phase("bootstrap", bootstrap_group, steps=30),
        phase("refine", refine_group, steps=50),
        phase("robust_check", robust_group, steps=-1),
    ],
)
solver.set_adapter(search)
```

运行语义：

```text
generation 0..29:
  active phase = bootstrap
  active adapter = bootstrap_group(nsga2 + de)

generation 30..79:
  active phase = refine
  active adapter = refine_group(vns + trust_region_dfo)

generation 80..end:
  active phase = robust_check
  active adapter = robust_group(sa + moead)
```

这种结构适合：

- 先用 population/global search 找到粗略 Pareto 区域。
- 再用 local/trust-region 做局部细化。
- 最后用 robust/stress search 检查约束边界和极端场景。

不建议把阶段切换写进 adapter 内部。adapter 应该只管“怎么提出候选、怎么吸收反馈”，阶段推进属于 orchestration layer。

### 3.2 串行 group + 条件推进

固定 `steps` 适合预算明确的实验。如果希望更像生产运行，可以用 context 条件推进阶段。

```python
explore_group = group(
    cfg.adapters,
    "explore_group",
    ["nsga2", "de"],
)

exploit_group = group(
    cfg.adapters,
    "exploit_group",
    ["vns", "trust_region_dfo"],
)

risk_group = group(
    cfg.adapters,
    "risk_group",
    ["sa", "moead"],
)

search = serial(
    cfg.adapters,
    "signal_driven_group_flow",
    [
        phase(
            "explore",
            explore_group,
            advance_when=any_of(
                ge(ctx("generation"), 30),
                exists(ctx("best_x")),
            ),
        ),
        phase(
            "exploit",
            exploit_group,
            advance_when=all_of(
                ge(ctx("generation"), 80),
                truthy(ctx("signal.local_stagnation")),
            ),
        ),
        phase(
            "risk_check",
            risk_group,
            steps=-1,
        ),
    ],
)
solver.set_adapter(search)
```

一个更贴近约束优化的例子：

```python
search = serial(
    cfg.adapters,
    "constraint_aware_flow",
    [
        phase(
            "global_search",
            global_group,
            advance_when=ge(ctx("evaluation_count"), 1000),
        ),
        phase(
            "feasibility_repair",
            repair_group,
            advance_when=le(ctx("constraint_violation.best"), 1e-6),
        ),
        phase(
            "pareto_polish",
            polish_group,
            steps=-1,
        ),
    ],
)
```

条件推进的边界：

| 可以读取 | 不建议读取 |
| --- | --- |
| `generation`、`evaluation_count` | 大型 population 对象 |
| `best_x`、`best_objective` | 完整 trace/history |
| 插件写入的轻量 signal | 外部服务里的隐式状态 |
| context 中的 snapshot ref | snapshot 大对象本体 |

## 4. 事件驱动策略

适用场景：外部评估信号不稳定，或者需要根据插件写入的事件切换策略。

```python
explore = group(cfg.adapters, "explore", ["vns"])
exploit = group(cfg.adapters, "exploit", ["example_adapter"])
search = event(cfg.adapters, "event_flow", [explore, exploit])
solver.set_adapter(search)
```

这里有两种语义：

| 写法 | 当前实际 API | 语义 |
| --- | --- | --- |
| `event(..., [explore, exploit])` | `EventStrategySpec` | queue-based event adapter：多个策略进入事件队列，按权重 dispatch / completion / refill |
| `event(..., [event_case(...), ...])` | `EventCaseSpec` | signal router：每代读取 context signal，按 `when + priority + cooldown` 选择当前激活的 adapter/group |

最简单的事件策略可以只看一个 signal，但真实复杂系统里通常不是这样。更常见的结构是多个插件各自负责一个观测面，然后把轻量信号写入 context；event strategy 只读这些信号，根据组合条件决定当前激活哪个 adapter 或 adapter group。

```text
resource monitor plugin
  -> context["signal.resource.gpu_pressure"]
  -> context["signal.resource.worker_queue_high"]

convergence detector plugin
  -> context["signal.convergence.frontier_stagnated"]
  -> context["signal.convergence.local_stagnation"]

budget tracker plugin
  -> context["signal.budget.remaining_ratio"]
  -> context["signal.budget.prefer_cheap_eval"]

constraint monitor plugin
  -> context["signal.constraint.violation_high"]
  -> context["signal.constraint.feasible_found"]

event strategy
  -> read signal.*
  -> choose explore / exploit / repair / cheap_eval / risk_check adapter group
```

事件驱动的核心边界：

| 组件 | 负责什么 | 不应该做什么 |
| --- | --- | --- |
| signal plugin | 观察运行状态，把轻量 signal 写入 context | 直接切 adapter |
| event strategy | 读取 signal，选择激活的 adapter/group | 计算大对象、读外部隐式状态 |
| adapter/group | propose/update 候选 | 自己判断全局运行阶段 |
| report/plugin | 记录 signal、event decision、active adapter | 改变搜索语义 |

### 4.1 单信号事件只是最小例子

事件驱动通常配合 plugin 使用。最小例子如下：

```python
from nsgablack.plugins import Plugin


class BudgetSignalPlugin(Plugin):
    context_provides = ("signal.prefer_exploit",)

    def __init__(self, name: str = "budget_signal"):
        super().__init__(name=name)

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return
        context = solver.get_context()
        solver.context_store.set("signal.prefer_exploit", context.get("remaining_budget", 0) < 100)
```

注意：事件写入 context 应保持轻量，复杂 trace 写 snapshot。

这个例子只说明写法，不代表正式复杂系统的推荐形态。正式场景里建议把 signal 命名做成稳定层级：

```text
signal.resource.*
signal.convergence.*
signal.budget.*
signal.constraint.*
signal.quality.*
signal.risk.*
signal.event.*
```

### 4.2 多插件信号矩阵

常见 signal 来源：

| 插件 | 写入 signal | 典型含义 |
| --- | --- | --- |
| resource monitor | `signal.resource.gpu_pressure` | GPU 显存或 lease 紧张 |
| resource monitor | `signal.resource.worker_queue_high` | inner eval 排队过多 |
| convergence detector | `signal.convergence.frontier_stagnated` | Pareto frontier 多代没有改进 |
| convergence detector | `signal.convergence.local_stagnation` | 当前局部搜索收益很低 |
| budget tracker | `signal.budget.remaining_ratio` | 剩余预算比例 |
| budget tracker | `signal.budget.prefer_cheap_eval` | 预算不足，应切便宜评估 |
| constraint monitor | `signal.constraint.violation_high` | 候选大量不可行 |
| constraint monitor | `signal.constraint.feasible_found` | 已找到可行区域 |
| quality monitor | `signal.quality.generalization_gap_high` | surrogate 或 inner model 泛化差 |
| risk monitor | `signal.risk.need_stress_check` | 需要进入鲁棒/压力检查阶段 |

示例插件：

```python
from nsgablack.plugins import Plugin


class ResourceSignalPlugin(Plugin):
    context_provides = (
        "signal.resource.gpu_pressure",
        "signal.resource.worker_queue_high",
    )

    def __init__(self, name: str = "resource_signal"):
        super().__init__(name=name)

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return
        context = solver.get_context()
        active_gpu_leases = int(context.get("resource.active_gpu_leases", 0))
        max_gpu_leases = max(1, int(context.get("resource.max_gpu_leases", 1)))
        queue_depth = int(context.get("resource.worker_queue_depth", 0))

        solver.context_store.update(
            {
                "signal.resource.gpu_pressure": active_gpu_leases >= max_gpu_leases,
                "signal.resource.worker_queue_high": queue_depth >= 8,
            }
        )
```

```python
class ConvergenceSignalPlugin(Plugin):
    context_provides = (
        "signal.convergence.frontier_stagnated",
        "signal.convergence.local_stagnation",
    )

    def __init__(self, name: str = "convergence_signal"):
        super().__init__(name=name)

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return
        context = solver.get_context()
        no_improve_generations = int(context.get("frontier.no_improve_generations", 0))
        local_delta = float(context.get("local.best_delta", 0.0))

        solver.context_store.update(
            {
                "signal.convergence.frontier_stagnated": no_improve_generations >= 15,
                "signal.convergence.local_stagnation": abs(local_delta) <= 1e-6,
            }
        )
```

```python
class BudgetSignalPlugin(Plugin):
    context_provides = (
        "signal.budget.remaining_ratio",
        "signal.budget.prefer_cheap_eval",
    )

    def __init__(self, name: str = "budget_signal"):
        super().__init__(name=name)

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return
        context = solver.get_context()
        budget = max(1, int(context.get("budget.total_evaluations", 1)))
        used = int(context.get("evaluation_count", 0))
        remaining_ratio = max(0.0, float(budget - used) / float(budget))

        solver.context_store.update(
            {
                "signal.budget.remaining_ratio": remaining_ratio,
                "signal.budget.prefer_cheap_eval": remaining_ratio <= 0.15,
            }
        )
```

这些插件不应该直接调用 `solver.set_adapter(...)`。它们只负责产生信号。

### 4.3 组合条件决定 adapter group

正式 event strategy 往往不是二选一，而是在多个策略组之间路由：

```python
explore_group = group(
    cfg.adapters,
    "explore_group",
    ["nsga2", "de"],
)

exploit_group = group(
    cfg.adapters,
    "exploit_group",
    ["vns", "trust_region_dfo"],
)

repair_group = group(
    cfg.adapters,
    "repair_group",
    ["constraint_repair", "vns"],
)

cheap_group = group(
    cfg.adapters,
    "cheap_eval_group",
    ["sa", "random_restart"],
)

risk_group = group(
    cfg.adapters,
    "risk_check_group",
    ["moead", "stress_sampler"],
)
```

事件路由逻辑可以表达成优先级规则：

```python
search = event(
    cfg.adapters,
    "multi_signal_event_flow",
    [
        event_case(
            "repair_when_infeasible",
            repair_group,
            when=truthy(ctx("signal.constraint.violation_high")),
            priority=100,
        ),
        event_case(
            "cheap_when_resource_pressure",
            cheap_group,
            when=any_of(
                truthy(ctx("signal.resource.gpu_pressure")),
                truthy(ctx("signal.budget.prefer_cheap_eval")),
            ),
            priority=80,
        ),
        event_case(
            "exploit_when_frontier_stagnates",
            exploit_group,
            when=all_of(
                truthy(ctx("signal.convergence.frontier_stagnated")),
                truthy(ctx("signal.constraint.feasible_found")),
            ),
            priority=60,
        ),
        event_case(
            "risk_check_when_needed",
            risk_group,
            when=truthy(ctx("signal.risk.need_stress_check")),
            priority=40,
        ),
        event_case(
            "default_explore",
            explore_group,
            when=truthy(True),
            priority=0,
        ),
    ],
)
solver.set_adapter(search)
```

`event_case(...)` 是当前标准脚手架的 signal-router surface。它会生成 `EventCaseSpec`，并由 `AsyncEventDrivenAdapter` 在 propose 阶段读取 context signal、选择最高优先级的可用 case，再把当前 case 的 adapter/group 放入事件队列。普通 `event(..., [adapter, adapter])` 仍保持旧的 queue-based event semantics，不要求 signal。

### 4.4 事件冲突、优先级和冷却时间

多插件信号同时触发时必须有冲突处理。推荐规则：

| 机制 | 作用 |
| --- | --- |
| `priority` | 多个条件同时为真时，选择优先级最高的 case |
| `cooldown_generations` | 避免每代来回切换 adapter |
| `min_active_generations` | 一个策略至少运行若干代再允许切换 |
| default case | 用 `when=truthy(True)` 表达没有其他规则命中时的默认策略 |
| `report_fields` | 把关键 signal 或 context 字段写入 event decision，方便审计 |

示例语义：

```python
event_case(
    "repair_when_infeasible",
    repair_group,
    when=truthy(ctx("signal.constraint.violation_high")),
    priority=100,
    cooldown_generations=5,
    min_active_generations=3,
)
```

如果 `violation_high` 和 `gpu_pressure` 同时触发，repair 优先，因为不可行问题比资源压力更影响搜索方向。如果 `frontier_stagnated` 和 `prefer_cheap_eval` 同时触发，可以先切 cheap group，避免在预算末期启动昂贵 exploit。

### 4.5 signal 不是 trace，context 只放轻量结论

不要这样写：

```python
context["signal.resource.full_gpu_history"] = huge_gpu_trace
context["signal.convergence.full_frontier_history"] = frontier_history
```

应该这样写：

```python
gpu_trace_ref = solver.snapshot_store.write({"kind": "gpu_trace", "rows": rows})
solver.context_store.update(
    {
        "resource.gpu_trace_ref": gpu_trace_ref,
        "signal.resource.gpu_pressure": True,
        "signal.resource.gpu_pressure_reason": "active_leases>=max_leases",
    }
)
```

signal 建议包含：

| 字段 | 示例 |
| --- | --- |
| boolean signal | `signal.resource.gpu_pressure = True` |
| numeric score | `signal.convergence.frontier_delta = 0.00001` |
| reason code | `signal.event.reason = "budget_low+frontier_stagnated"` |
| producer | `signal.event.producer = "BudgetSignalPlugin"` |
| updated generation | `signal.event.updated_generation = 42` |

复杂原始数据放 snapshot，context 只留 ref 和轻量判断。

### 4.6 事件决策 report

event strategy 每次切换都应该写入可审计记录：

```json
{
  "event_decision": {
    "generation": 42,
    "active_case": "cheap_when_resource_pressure",
    "active_adapter_group": "cheap_eval_group",
    "matched_cases": [
      "cheap_when_resource_pressure",
      "exploit_when_frontier_stagnates"
    ],
    "selected_priority": 80,
    "selected_reason": "priority",
    "report_fields": {
      "signal.resource.gpu_pressure": true,
      "signal.budget.prefer_cheap_eval": true,
      "signal.convergence.frontier_stagnated": true
    },
    "cooldown": {
      "active_since": 42,
      "last_exit": {
        "exploit_when_frontier_stagnates": 41
      }
    },
    "blocked_cases": []
  }
}
```

最低验收：

- 能看到每代 active case。
- 能看到触发信号和未触发信号。
- 能看到为什么选这个 adapter group。
- 能看到 cooldown 或 fallback 行为。
- 能看到信号来自哪个 plugin。

## 5. 嵌套评估：outer nsgablack -> inner runtime

标准语义：

```text
outer adapter proposes x
outer representation decodes x
outer problem builds inner task
inner runtime runs solver/flow/provider
inner result projects to objectives/violations
outer adapter receives feedback
```

这里的关键点是：inner runtime 不应该被理解成一个普通 Python 函数。它可以是一个完整的标准脚手架结构，也可以有自己的 problem、representation、adapter group、serial/event orchestration、plugin、bias、snapshot、ResourceContext 和 report。

```text
outer nsgablack solver
  -> outer adapter orchestration
  -> outer representation genome
  -> outer problem/evaluation bridge
      -> inner nsgablack solver scaffold
          -> inner adapter orchestration
          -> inner representation
          -> inner plugins / context / snapshot
          -> inner report
      -> or inner mlblack flow scaffold
          -> numericizer / pipeline / trainer / capability
          -> artifact / metrics / report
  -> project inner payload to outer objectives/violations
```

推荐外层 case 结构：

```text
examples/cases/<case>/
  build_solver.py
  run_solver.py
  problem/
    outer_problem.py
    inner_bridge.py
  pipeline/
    genome.py
  config/
    schema.py
  reporting/
```

如果 inner 也是 nsgablack，推荐在 case 内部显式给 inner 一套标准脚手架，不要把 inner solver 构造堆在 outer problem 文件里：

```text
examples/cases/<case>/
  outer/
    build_solver.py
    problem/
    pipeline/
    plugins/
  inner/
    build_solver.py
    problem/
    pipeline/
    adapters/
    plugins/
    reporting/
  bridge/
    inner_task.py
    inner_evaluator.py
    result_projection.py
```

如果 inner 是 mlblack，也应该通过 mlblack 的 `build_flow()` surface，而不是直接 import trainer。

```text
examples/cases/<case>/
  nsgablack_outer/
    build_solver.py
    problem/
    pipeline/
  mlblack_inner/
    build_flow.py
    data/
    config/
    reporting/
  bridge/
    payload_contract.py
    evaluator.py
```

外层 problem 只负责把候选转成 inner task，并把 inner result 投影成 outer objective：

```python
class OuterProblem:
    def __init__(self, inner_evaluator):
        self.inner_evaluator = inner_evaluator

    def evaluate(self, x):
        task = self.decode_outer_candidate(x)
        result = self.inner_evaluator.evaluate(task)
        return np.asarray([
            result.metrics["test_rmse"],
            result.metrics["generalization_gap"],
            result.cost["runtime_seconds"],
        ], dtype=float)

    def evaluate_constraints(self, x):
        task = self.decode_outer_candidate(x)
        result = self.inner_evaluator.peek_last_or_evaluate(task)
        return np.asarray([
            max(0.0, result.cost["runtime_seconds"] - task.max_runtime),
        ], dtype=float)
```

边界：

| 外层 nsgablack | 内层 runtime |
| --- | --- |
| genome、outer objective、outer constraints | trainer/flow/inner solver |
| outer budget、solver fanout、资源授权 | 实际训练或评估执行 |
| ResourceContext 注入 | ResourceContext 消费 |
| outer report | inner metrics/artifact/report |

### 5.1 inner solver 也是完整 solver

inner solver 可以使用和 outer 一样的编排语言。例如 inner 先用全局策略找可行解，再用局部策略细化：

```python
def build_inner_solver(cfg, *, resource_context=None, component_overrides=None):
    solver = EvolutionSolver(...)
    solver.set_context_store(cfg.context_store)
    solver.set_snapshot_store(cfg.snapshot_store)

    inner_explore = group(
        cfg.adapters,
        "inner_explore",
        ["nsga2", "de"],
    )
    inner_refine = group(
        cfg.adapters,
        "inner_refine",
        ["vns", "trust_region_dfo"],
    )
    inner_repair = group(
        cfg.adapters,
        "inner_repair",
        ["constraint_repair", "sa"],
    )

    search = serial(
        cfg.adapters,
        "inner_global_then_refine",
        [
            phase("inner_global", inner_explore, steps=20),
            phase(
                "inner_repair",
                inner_repair,
                advance_when=le(ctx("constraint_violation.best"), 1e-6),
            ),
            phase("inner_refine", inner_refine, steps=-1),
        ],
    )

    solver.set_adapter(search)
    solver.set_resource_context(resource_context)
    solver.set_component_overrides(component_overrides or {})
    return solver
```

这说明 inner 不是“简化版 solver”。它只是被 outer 当作一次 evaluation 调用，但它内部仍然拥有完整生命周期。

### 5.2 nested solver 的三种深度

| 深度 | 形态 | 适用 |
| --- | --- | --- |
| L0 -> L1 | outer solver 调 inner evaluator | 简单代理评估、mlblack flow |
| L0 -> L1 solver | outer solver 调完整 inner nsgablack solver | 内层本身也是优化问题 |
| L0 -> L1 solver -> L2 flow/provider | outer 搜政策，inner solver 搜排程，L2 flow 训练/评估代理 | 复杂工程仿真、分层优化 |

示例：

```text
outer L0:
  search material blacklist / high-level policy

inner L1:
  solve production schedule under selected blacklist

inner L2:
  train/evaluate surrogate or run expensive simulator
```

每层都要有自己的 run id、namespace、resource scope 和 report，不要混用一个全局 context。

### 5.3 outer task 到 inner scaffold 的 payload

outer 候选不应该直接改 inner 对象，而应解码成稳定 payload：

```python
inner_task = {
    "task_id": "outer_trial_0007_inner_0001",
    "outer_trial_id": "outer_trial_0007",
    "scenario": {
        "material_blacklist": ["A12", "B07"],
        "capacity_policy": "conservative",
    },
    "inner_solver_config": {
        "adapter_profile": "global_then_refine",
        "max_generations": 40,
        "population_size": 64,
    },
    "component_overrides": {
        "representation.supply_shift": {
            "max_moved_events": 200,
        },
        "plugin.inner_budget_guard": {
            "max_runtime_seconds": 120.0,
        },
    },
}
```

inner evaluator 负责调用 inner scaffold：

```python
class InnerSolverEvaluator:
    def __init__(self, inner_builder, allocator):
        self.inner_builder = inner_builder
        self.allocator = allocator

    def evaluate(self, task, *, resource_context=None):
        solver = self.inner_builder(
            task["inner_solver_config"],
            resource_context=resource_context,
            component_overrides=task.get("component_overrides", {}),
        )
        summary = solver.run()
        return self.project_summary(task, summary)
```

### 5.4 inner result 到 outer objective 的投影

inner result 应返回稳定 payload，outer 只消费这个 payload：

```python
{
    "status": "ok",
    "inner_run_id": "inner_outer_trial_0007_0001",
    "inner_kind": "nsgablack_solver",
    "metrics": {
        "best_output": 1280.0,
        "service_level": 0.98,
        "runtime_seconds": 83.4
    },
    "objectives": {
        "inner_best_cost": 0.42,
        "inner_risk": 0.08
    },
    "violations": {
        "capacity_violation": 0.0,
        "runtime_violation": 0.0
    },
    "reports": {
        "inner_summary_path": "runs/outer_0007/inner_0001/summary.json",
        "inner_snapshot_key": "snapshot://inner_0001/frontier"
    },
    "effective": {
        "resource_context": {},
        "adapter_profile": "global_then_refine",
        "component_overrides": {}
    }
}
```

outer projection：

```python
def project_inner_to_outer(inner_result, task):
    if inner_result["status"] != "ok":
        return failed_objectives(), failed_violations()

    objectives = np.asarray([
        -float(inner_result["metrics"]["best_output"]),
        float(inner_result["metrics"]["runtime_seconds"]),
        float(inner_result["objectives"]["inner_risk"]),
    ], dtype=float)

    violations = np.asarray([
        float(inner_result["violations"]["capacity_violation"]),
        float(inner_result["violations"]["runtime_violation"]),
    ], dtype=float)
    return objectives, violations
```

不要让 outer 解析 inner solver 私有 population 对象。需要 population/frontier 时，inner 写 snapshot，outer report 只保存 snapshot ref。

### 5.5 nested report 分层

嵌套 report 不应混成一份大 JSON。推荐三层：

| 报告 | 内容 |
| --- | --- |
| outer report | outer genome、decoded task、outer objectives/violations、inner payload summary |
| inner solver report | inner problem、inner adapter orchestration、inner objectives、inner frontier、inner resource usage |
| artifact/provider report | mlblack artifact、simulator log、cache hit、domain report |

outer report 只保存 inner summary 和 ref：

```json
{
  "outer_trial_id": "outer_trial_0007",
  "decoded_inner_task_ref": "snapshot://outer_0007/task",
  "inner_runs": [
    {
      "inner_run_id": "inner_outer_trial_0007_0001",
      "status": "ok",
      "summary_path": "runs/outer_0007/inner_0001/summary.json",
      "frontier_ref": "snapshot://inner_0001/frontier",
      "resource_context": {
        "namespace": "outer_0007.inner_0001",
        "device": "cuda:0",
        "threads": 2
      }
    }
  ],
  "outer_objectives": [-1280.0, 83.4, 0.08],
  "outer_violations": [0.0, 0.0]
}
```

### 5.6 nested solver 反模式

| 反模式 | 问题 | 改法 |
| --- | --- | --- |
| outer problem 里直接 new inner adapter | inner 不可复用、不可审计 | inner 暴露 `build_inner_solver()` |
| inner solver 直接读 outer 全局变量 | 不可复现 | outer 传 JSON-compatible task payload |
| outer context 塞 inner population | 大对象污染 context | inner 写 snapshot，outer 存 ref |
| inner 私下写死 `cuda:0` | 多 trial 抢 GPU | outer L0 注入 ResourceContext |
| inner report 和 outer report 混成一份 | 分层不清 | outer/inner/artifact 三层 report |
| inner 没有 run id | 无法定位失败 | namespace = `outer_trial.inner_run` |
| outer 直接解析 inner 私有对象 | 版本不稳定 | inner 返回稳定 payload |

## 6. 外层优化内层组件参数

适用场景：outer genome 不是直接代表业务决策，而是代表内层某个组件的参数。例如：

- bias 系数。
- pipeline kernel。
- evaluation threshold。
- feature gate。
- symbolic representation object。

标准流程：

```text
outer typed genome
  -> representation.decode(...)
  -> component_overrides
  -> inner scaffold build/run
  -> inner metrics
  -> outer objectives
```

component override 示例：

```python
component_overrides = {
    "pipeline.learnable_conv1d": {
        "kernel_size": 3,
        "coefficients": [0.2, 0.6, 0.2],
        "padding": "same",
    },
    "bias.domain_prior": {
        "strength": 0.4,
    },
}
```

正确传递方式：

```python
inner_result = inner_evaluator.evaluate(
    task,
    component_overrides=component_overrides,
    resource_context=outer_resource_context,
)
```

错误传递方式：

```python
# 错误：直接改内层全局变量，不可审计
mlblack.pipeline.LEARNABLE_KERNEL = coefficients

# 错误：在 example 文件里写死 cuda:0
inner_trainer.device = "cuda:0"
```

## 7. 多 solver 编排

多 solver 编排不是 adapter。它适合：

- 多个 solver 实例并行跑不同搜索 profile。
- 不同 seed 或不同 representation 分支。
- 结果合并成统一 Pareto/frontier。
- 对多个 solver 做资源授权和运行审计。

它不负责：

- 单个 solver 内的 `propose/update`。
- 单个 problem 的 objective 公式。
- inner trainer 细节。

判断标准：

| 需求 | 用什么 |
| --- | --- |
| 一个 solver 内混合 VNS/DE/SA | `StrategyRouterAdapter` |
| 一个 solver 内 warmup -> exploit | `StrategyChainAdapter` / `serial(...)` |
| 多个 solver 实例同时跑 | solver orchestration |
| outer candidate 触发 mlblack 训练 | Problem/Evaluation bridge |

### 7.1 adapter group 和 solver group 的区别

最容易混淆的是两个“group”：

- `adapter group`：一个 solver 内的多个搜索策略。
- `solver group`：多个 solver 实例之间的运行编排。

二者不是同一层。

| 对比项 | adapter group | solver group |
| --- | --- | --- |
| 运行位置 | 单个 solver 内 | solver manager / outer runner |
| 基本对象 | adapter | solver 实例 |
| 共享内容 | 同一个 problem、representation、evaluation path | 可以各自有 problem/profile/seed/representation |
| 反馈路径 | child adapter 收到自己的候选反馈 | 每个 solver 独立运行后聚合结果 |
| 适合问题 | 多策略协同搜索 | 多配置、多 seed、多表示、多资源 profile 对照 |
| 资源管理 | 通常共享单 solver 的评估预算 | 需要 L0 ResourceAllocator 做 fanout 授权 |

adapter group 示例：

```python
search = group(
    cfg.adapters,
    "one_solver_portfolio",
    ["nsga2", "de", "vns"],
)
solver.set_adapter(search)
```

这表示：

```text
one solver
  one problem
  one representation
  one evaluation path
  multiple adapters inside the solver
```

solver group 示例：

```python
manager = SolverManager(
    regimes=(
        RegimeSpec("nsga2_profile", lambda: build_solver(adapter_profile="nsga2")),
        RegimeSpec("vns_profile", lambda: build_solver(adapter_profile="vns")),
        RegimeSpec("hybrid_profile", lambda: build_solver(adapter_profile="hybrid")),
    ),
    offer=ResourceOffer(
        threads=12,
        backend="local",
        device_tokens=("cuda:0", "cuda:1"),
    ),
    policy=ResourcePolicy(
        mode="strict",
        gpu_sharing="exclusive",
        lease_ttl_seconds=300.0,
        heartbeat_interval_seconds=30.0,
    ),
    mode="parallel",
)

summary = manager.run()
```

这表示：

```text
solver manager
  -> solver A: nsga2 profile
  -> solver B: vns profile
  -> solver C: hybrid profile
  -> collect and compare results
```

solver group 的常见形态：

| 形态 | 示例 |
| --- | --- |
| 不同 adapter profile | `nsga2_profile` vs `vns_profile` vs `hybrid_profile` |
| 不同 seed | `seed_0`、`seed_1`、`seed_2` |
| 不同 representation | continuous genome vs typed genome |
| 不同 bias | no bias vs domain bias vs surrogate bias |
| 不同资源 profile | CPU-only vs GPU inner eval |
| 不同 outer objective | accuracy-first vs cost-first |

### 7.2 多 solver + 多 inner 的嵌套编排

多 solver 编排可以继续嵌套 inner solver 或 inner mlblack flow。这个能力来自标准脚手架的分层设计：outer solver 只看候选、目标、约束和资源授权；inner solver/flow 只在被授权的资源范围内完成自己的求解或训练；二者通过稳定 payload 通信。

典型拓扑：

```text
parent resource allocator
  -> solver_A(profile=explore, seed=1)
      -> candidate_001
          -> inner mlblack flow
          -> metrics/artifact/report
      -> candidate_002
          -> inner nsgablack solver
          -> frontier/summary/report
  -> solver_B(profile=exploit, seed=2)
      -> candidate_001
          -> inner mlblack flow
          -> metrics/artifact/report
      -> candidate_002
          -> inner provider/simulator
          -> metrics/report
  -> merge frontier / report / snapshot
```

这不是一种新的 adapter，也不是在 `problem.evaluate()` 里随手递归调用训练脚本，而是多个标准脚手架实例的组合。

| 层级 | 负责什么 | 对下层传什么 | 从下层拿什么 |
| --- | --- | --- | --- |
| parent orchestration | 多 solver fanout、全局资源池、全局审计、结果合并 | solver profile、seed、parent `ResourceContext` | solver summary、frontier ref、resource audit |
| outer solver | 搜索候选、维护 adapter 状态、写 outer snapshot | decoded candidate、component_overrides、child `ResourceContext` | objectives、violations、inner summary |
| inner nsgablack solver | 在给定 inner problem 上继续做优化 | inner problem config、representation config、adapter profile、resource grant | inner frontier、inner objectives、inner report |
| inner mlblack flow | 在给定数据与组件配置下训练/评估模型 | flow assembly、trainer/pipeline overrides、resource grant | metrics、artifact、flow_report |
| merge layer | 合并 Pareto/frontier、去重、生成总报告 | 多 solver 结果引用 | unified frontier、comparison table、audit report |

因此，复杂嵌套可以长成下面这种结构：

```text
solver group
  -> solver profile A
      -> adapter group
          -> candidate
              -> inner solver scaffold
                  -> inner adapter group
                  -> inner plugins / snapshots
  -> solver profile B
      -> serial adapter group
          -> candidate
              -> inner mlblack flow scaffold
                  -> trainer family / head / capability
```

但每一层都必须只通过正式 surface 通信：

| 交互 | 推荐 surface |
| --- | --- |
| outer genome -> inner config | `RepresentationPipeline.decode(...)` + `component_overrides` |
| outer resource -> inner runtime | JSON-compatible `ResourceContext` |
| inner result -> outer objective | stable `inner_result` payload |
| 大对象传递 | inner snapshot/artifact ref |
| 审计与复现 | run id、namespace、resource audit、effective config |

### 7.3 嵌套资源边界

嵌套编排最容易出错的不是 API，而是资源。框架允许 solver、adapter group、inner solver、inner mlblack flow 自由组合，但资源必须形成树形授权，而不是所有层级都直接抢全局资源。

推荐资源树：

```text
root ResourceAllocator
  -> solver_A grant
      -> eval_001 child lease
          -> inner_flow ResourceContext
      -> eval_002 child lease
          -> inner_solver ResourceContext
  -> solver_B grant
      -> eval_001 child lease
          -> inner_flow ResourceContext
```

基本规则：

- parent allocator 拥有全局 CPU/thread/GPU/device token 资源池。
- 每个 solver 实例获得独立 `ResourceContext`、namespace 和 solver budget。
- outer solver 在评估候选时，只能从自己的授权里派生 child lease。
- inner solver 或 inner mlblack flow 只能消费注入的 `ResourceContext`。
- inner 不能私下写死 `cuda:0`、全局线程池或全局临时目录。
- inner result 必须带回 `resource_context_id`、`lease_id`、`namespace`、`budget_used`、`backend` 等审计字段。

资源边界示例：

| 资源对象 | 所属层级 | 典型字段 | 审计意义 |
| --- | --- | --- | --- |
| root offer | parent orchestration | total threads、device_tokens、backend、policy | 全局可用资源 |
| solver grant | solver group | solver_id、namespace、thread_quota、device_pool、budget | 每个 solver 的授权范围 |
| eval lease | outer evaluation | lease_id、candidate_id、device_token、ttl、heartbeat | 每个候选评估的资源占用 |
| child ResourceContext | inner runtime | inherited namespace、effective device、threads、budget | inner 实际可用资源 |
| resource audit | report layer | acquired_at、released_at、stale_recovered、oom_risk | 复现和排错 |

不要形成网状抢占：

```text
solver_A -> cuda:0
solver_B -> cuda:0
inner_flow -> cuda:0
inner_solver -> cuda:0
```

这种写法在单进程小样例里可能偶尔能跑，但在多进程 backend、benchmark、跨框架 case 或长时间运行中会变成不可复现的 OOM、空闲 GPU 误判和互相踩踏。

正确做法是让资源分配显式进入装配语言：

```python
manager = SolverManager(
    regimes=(...),
    offer=ResourceOffer(
        threads=24,
        device_tokens=("cuda:0", "cuda:1"),
        backend="process",
    ),
    policy=ResourcePolicy(
        mode="strict",
        gpu_sharing="exclusive",
        lease_ttl_seconds=300.0,
        heartbeat_interval_seconds=30.0,
    ),
)

summary = manager.run()
```

然后在 outer evaluation 中只派生 child context：

```python
with allocator.acquire_child(parent_context, request) as lease:
    result = inner_evaluator.evaluate(
        task,
        resource_context=lease.to_resource_context(),
    )
```

这样可以把“能嵌套”与“可审计、可复现、不会抢资源”同时成立。

选择规则：

| 需求 | 推荐层级 |
| --- | --- |
| 同一个 solver 内让多个搜索策略互相补充 | adapter group |
| 先全局搜索，再局部搜索，再鲁棒检查 | serial adapter group |
| 同时比较三种完整 solver 配置 | solver group |
| 每个 solver 都有独立 checkpoint/report | solver group |
| 每个外层候选都触发内层训练 | problem/evaluation bridge |
| 多个 outer eval 同时抢 GPU | solver group + L0 ResourceAllocator |

不要这样写：

```python
# 错误：为了比较两个 solver profile，把两个 problem 塞进同一个 adapter group。
search = group(cfg.adapters, "mixed_problem_group", ["profile_a_adapter", "profile_b_adapter"])
```

如果 profile 的 problem、representation 或 resource policy 已经不同，就应该上升到 solver orchestration，而不是继续塞进 adapter orchestration。

## 8. 编排配置放哪里

推荐：

| 内容 | 落点 |
| --- | --- |
| adapter 参数 | `adapter/config.py` 的 `AdapterSpec.params` |
| 编排模式选择 | `build_solver(..., mode="serial")` 或 project config |
| phase 条件 | `compose_search(...)` |
| outer objective 权重 | `problem/config.py` 或 case config |
| inner resource | ResourceContext / runtime profile |
| report 字段 | reporting/plugin |

不要把这些写进 `run_solver.py`。运行入口只负责解析 CLI 并调用正式装配面。

## 9. 编排验收清单

- 单策略 baseline 能跑。
- group 内多个 adapter 的候选来源可追踪。
- group 间串行切换在 report 中能看到 phase 名称。
- 多策略模式下每个 adapter 都能收到对应反馈。
- 串行阶段切换可在 trace/report 中解释。
- solver group 的每个 solver profile 有独立 run id / checkpoint / summary。
- event signal 只写轻量 context。
- 嵌套评估输出包含 inner run id、resource context、metrics、失败模式。
- component overrides 被写入 report，而不是只存在内存里。
- 如果用了 mlblack，inner report 中能看到生效 trainer、pipeline、capability 和资源上下文。
