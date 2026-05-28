# 00. 标准脚手架装配 API 速查表

这张表只收录“装配语言”和“标准脚手架入口”，不替代完整 API 文档。判断标准是：使用者在 `build_solver.py`、`adapter/config.py`、`run_solver.py`、case runner 或跨框架 bridge 里会直接用到。

核心原则：

- `Spec` 保存参数。
- `Registry` 保存可选组件。
- `Builder/helper` 把声明变成对象。
- `solver.set_* / add_*` 完成挂载。
- `evaluate_* / run / snapshot / context / report` 完成执行与审计。
- 复杂编排不要绕开这些 surface。

## 1. Solver 控制面 API

| API | 常用位置 | 作用 | 示例 | 注意 |
| --- | --- | --- | --- | --- |
| `build_solver(cfg, ...)` | `build_solver.py` | 项目统一装配入口 | `solver = build_solver(cfg)` | 只装配，不要在这里长期写实验循环 |
| `solver.set_adapter(adapter)` | `build_solver.py` | 挂载单策略或编排后的 search adapter | `solver.set_adapter(search)` | 搜索策略必须先在 adapter 层组好 |
| `solver.set_adapters(adapters)` | 兼容/批量挂载 | 挂载多个 adapter | `solver.set_adapters([...])` | 正式复杂编排优先用 `group/multi/serial/event` |
| `solver.set_representation_pipeline(pipeline)` | `build_solver.py` | 挂候选表示管线 | `solver.set_representation_pipeline(pipeline)` | pipeline 负责 init/mutate/repair/encode/decode |
| `solver.add_plugin(plugin)` | `build_solver.py` | 挂载运行能力 | `solver.add_plugin(ModuleReportPlugin(...))` | plugin 不应改写 adapter 算法语义 |
| `solver.register_controller(controller)` | 控制器装配 | 挂载 budget/stop/switch 等控制器 | `solver.register_controller(stop_ctl)` | controller 是控制平面，不是 adapter |
| `solver.set_context_store(store)` | state backend 装配 | 注入轻量 context 后端 | `solver.set_context_store(store)` | context 只放轻量 key/ref |
| `solver.set_snapshot_store(store)` | state backend 装配 | 注入大对象 snapshot 后端 | `solver.set_snapshot_store(store)` | population/frontier/artifact 走 snapshot |
| `solver.evaluate_individual(x)` | problem/eval 测试、bridge | 单候选评估 | `obj, vio = solver.evaluate_individual(x)` | 会经过 plugin/bias/evaluation chain |
| `solver.evaluate_population(population)` | 批量评估 | 批量候选评估 | `obj, vio = solver.evaluate_population(pop)` | 返回数量必须与 population 对齐 |
| `solver.write_population_snapshot(pop, obj, vio)` | checkpoint/report | 写 population 大对象 | `ok = solver.write_population_snapshot(pop, obj, vio)` | 返回 bool；snapshot ref 由 solver/context 维护 |
| `solver.read_snapshot(snapshot_key)` | 恢复/报告 | 读取 snapshot payload | `payload = solver.read_snapshot(key)` | 优先 snapshot，再 fallback 到 runtime state |
| `solver.get_context()` | plugin/report/debug | 读取当前运行态视图 | `ctx = solver.get_context()` | 不要把返回 dict 当长期状态容器 |

## 2. Adapter / Search 编排 Helper

这些 helper 通常位于项目脚手架的 `adapter/config.py`，生成的都是 adapter 对象，最后统一交给 `solver.set_adapter(...)`。

| API | 返回对象 | 作用 | 示例 | 适用场景 |
| --- | --- | --- | --- | --- |
| `require_adapter(registry, key)` | adapter instance | 从 registry 构造一个具体 adapter | `vns = require_adapter(registry, "vns")` | 明确只要一个策略 |
| `group(registry, name, adapter_keys)` | 单 adapter 或 `StrategyRouterAdapter` | 一个组内多个 adapter 协同 | `group(cfg.adapters, "global", ["nsga2", "de"])` | 同一阶段内全局/局部策略协作 |
| `multi(registry, name, adapters)` | `StrategyRouterAdapter` | 多个 adapter/group 并行协同 | `multi(cfg.adapters, "portfolio", [global_g, local_g])` | 多策略组共同提出候选 |
| `phase(name, adapter, steps=-1, advance_when=None)` | `SerialPhaseSpec` | 声明串行阶段 | `phase("warmup", explore, steps=20)` | warmup/exploit/robust_check |
| `serial(registry, name, phases)` | `StrategyChainAdapter` | 多阶段串行推进 | `serial(cfg.adapters, "flow", [phase_a, phase_b])` | 阶段之间顺序执行，阶段内部可 group |
| `event(registry, name, adapters)` | `AsyncEventDrivenAdapter` | 事件队列或 signal router 编排 | `event(cfg.adapters, "event_flow", [case_a, case_b])` | 事件驱动策略 |
| `event_case(name, adapter, when=..., priority=...)` | `EventCaseSpec` | signal-router case | `event_case("cheap", cheap_g, when=truthy(ctx("signal.budget.low")), priority=80)` | 多插件信号决定激活哪个 group |

## 3. 条件表达式 Helper

这些 helper 用在 `phase(..., advance_when=...)` 和 `event_case(..., when=...)`。

| API | 作用 | 示例 | 说明 |
| --- | --- | --- | --- |
| `ctx(path)` | 从 context 读取字段 | `ctx("signal.resource.gpu_pressure")` | 支持 flat key 和点号路径 |
| `val(value)` | 常量引用 | `val(10)` | 用于比较条件 |
| `truthy(ref)` | 判断 ref 是否为真 | `truthy(ctx("signal.prefer_exploit"))` | 最常用 signal 条件 |
| `exists(ref)` | 判断 ref 是否存在 | `exists(ctx("best_x"))` | 适合阶段推进 |
| `eq/ne/gt/ge/lt/le(left, right)` | 比较条件 | `gt(ctx("generation"), 20)` | 返回 `Cond` |
| `in_/not_in(left, right)` | 成员判断 | `in_(ctx("phase"), val(["exploit"]))` | 注意 `in_` 避免 Python 关键字 |
| `between(value, low, high)` | 区间判断 | `between(ctx("budget.ratio"), 0.1, 0.5)` | 等价于 `ge + le` |
| `all_of(*conds)` | 条件与 | `all_of(a, b)` | 全部为真 |
| `any_of(*conds)` | 条件或 | `any_of(a, b)` | 任一为真 |
| `not_(cond)` | 条件非 | `not_(truthy(ctx("x")))` | 避免覆盖 Python `not` |
| `custom(fn)` | 自定义条件 | `custom(lambda c: c.get("mode") == "x")` | 文档/JSON 场景优先用 DSL 或具名函数 |

## 4. 编排对象与直接类名

如果不走 helper，也可以直接使用底层类。正式项目里推荐 helper，框架扩展/测试可以直接用类。

| 类 | 所属层 | 作用 | 常见构造 |
| --- | --- | --- | --- |
| `AlgorithmAdapter` | Adapter base | 自定义 adapter 基类 | 实现 `propose/update` |
| `StrategySpec` | Adapter orchestration | `StrategyRouterAdapter` 的单策略声明 | `StrategySpec(adapter=a, name="a")` |
| `RoleSpec` | Adapter orchestration | 多 role / 多 unit 策略声明 | `RoleSpec(name="explore", adapter=factory, n_units=4)` |
| `StrategyRouterAdapter` | Adapter orchestration | 多策略/多 role 协同 | `StrategyRouterAdapter(strategies=[...])` |
| `MultiStrategyConfig` | Adapter orchestration | 多策略预算、phase、role rule 配置 | `MultiStrategyConfig(total_batch_size=64)` |
| `MultiStrategyControlRule` | Adapter orchestration | context-driven role/phase 控制 | `MultiStrategyControlRule(when_dsl=..., then=...)` |
| `SerialPhaseSpec` | Adapter orchestration | 串行阶段声明 | `SerialPhaseSpec(name="warmup", adapter=a, steps=20)` |
| `StrategyChainAdapter` | Adapter orchestration | 串行阶段控制器 | `StrategyChainAdapter(phases=[...])` |
| `AsyncEventDrivenAdapter` | Adapter orchestration | event queue + signal router | `AsyncEventDrivenAdapter(strategies=[...])` |
| `EventStrategySpec` | Event queue | 普通事件队列策略参与者 | `EventStrategySpec(adapter=a, name="a")` |
| `EventCaseSpec` | Event router | signal case 规则 | `EventCaseSpec(adapter=a, name="cheap", when=...)` |

## 5. 标准组件配置对象

| 对象 | 常用文件 | 作用 | 典型字段 |
| --- | --- | --- | --- |
| `ProblemSpec` / project problem cfg | `problem/config.py` | 声明目标、约束、数据路径、业务参数 | objectives、constraints、data_path |
| `PipelineSpec` / `PipelineRegistry` | `pipeline/config.py` | 声明 representation pipeline | init/mutate/repair/encode/decode 配置 |
| `AdapterSpec` / `AdapterRegistry` | `adapter/config.py` | 声明可用 adapter 及参数 | key、params、orchestration defaults |
| `BiasSpec` / bias cfg | `bias/config.py` | 声明软引导 | key、params、enabled |
| `PluginSpec` / ops cfg | `plugins/config.py` | 声明可挂载能力 | plugin key、params、priority |
| `StateBackendSpec` | `config/state.py` | 声明 context/snapshot 后端 | memory/sqlite/redis、path、ttl |
| `ResourceOffer` | solver manager / runner | 声明资源池 | threads、device_tokens、backend |
| `ResourceRequest` | evaluation / inner bridge | 声明一次资源请求 | cpu_threads、device_tokens、owner_id |
| `ResourceRequirement` | L0 task / nested eval | 声明任务需要什么资源 | threads、gpus、memory_mb、gpu_memory_mb、capabilities |
| `TaskEnvelope` | L0 runtime | 标准任务包 | task_id、task_type、payload、requirement、input_refs |
| `TaskResult` | L0 runtime | 标准任务结果 | objectives、violations、metrics、artifact_refs、resource_context |
| `WorkerDescriptor` | L0 runtime | 声明 worker 能力和资源 offer | worker_id、executor_backend、capabilities、offer |
| `DataRef` | artifact/data transport | 大数据和产物引用 | uri、kind、backend、media_type、checksum |
| `ResourcePolicy` | solver manager / L0 | 声明资源策略 | mode、gpu_sharing、ttl、heartbeat |

## 6. L0 / 多 Solver / 资源装配 API

| API / 对象 | 作用 | 示例 | 注意 |
| --- | --- | --- | --- |
| `SolverManager` | 多 solver fanout、资源授权、结果合并 | `manager = SolverManager(regimes=(...), offer=offer, policy=policy)` | solver group 不是 adapter group |
| `RegimeSpec` | 一个 solver profile | `RegimeSpec("nsga2", lambda: build_solver(...))` | 每个 regime 应有独立 run id |
| `ResourceOffer` | 全局资源池 | `ResourceOffer(threads=12, device_tokens=("cuda:0",))` | parent allocator 拥有全局资源 |
| `ResourceRequest` | 子任务资源请求 | `ResourceRequest(cpu_threads=2, device_tokens=("cuda:0",))` | inner eval 从 parent grant 派生 |
| `ResourceRequirement` | L0 task 资源需求 | `ResourceRequirement(threads=2, gpus=1, gpu_memory_mb=8192)` | 描述 task 需要什么，不负责启动进程 |
| `TaskEnvelope` | L0 标准任务包 | `TaskEnvelope(task_type="nested_candidate_eval", requirement=req, ...)` | 大数据走 `DataRef` |
| `TaskResult` | L0 标准结果包 | `TaskResult.success(..., artifact_refs=(ref,))` | 必须能审计 worker/lease/context |
| `WorkerDescriptor` | L0 worker 声明 | `WorkerDescriptor(worker_id="w1", offer={"threads": 8})` | CPU/GPU 是 worker 的资源属性 |
| `L0RuntimeBackend` | L0 runtime 组合后端 | `RedisL0RuntimeBackend(...)` | 聚合 queue/result/state/registry/artifact/transport |
| `InMemoryL0RuntimeBackend` | 本地 L0 runtime | 单进程测试/调试 | 不代表多机互斥 |
| `RedisL0RuntimeBackend` | Redis worker runtime | queue/result/state/heartbeat | Redis 是队列/状态，不是计算资源 |
| `FilesystemArtifactBackend` | 文件产物后端 | xlsx/csv/json/report | 大产物不要塞进 task payload |
| `InlineDataTransportBackend` | 小 payload 传输 | JSON-compatible 小对象 | candidate vector 可以 inline |
| `ArtifactDataTransportBackend` | 大 payload 传输 | artifact ref | 大矩阵、数据集、checkpoint |
| `ResourcePolicy` | 冲突策略 | `ResourcePolicy(mode="strict", gpu_sharing="exclusive")` | GPU 建议 lease 化 |
| `ResourceAllocator` / manager allocator | 本地资源授权 | `lease = allocator.acquire(request, owner_id="trial_1")` | 单进程或本地多进程 |
| `SQLiteLeaseStore` | 本机多进程 lease 互斥 | `SQLiteLeaseStore("leases.db")` | 解决多个进程同时认为拿到 GPU |
| `ResourceContext` payload | 跨层授权 payload | `ctx = lease.resource_context(namespace="trial_1")` | 只传 JSON-compatible dict 给 inner |

## 7. Context / Snapshot / Report API

| API | 作用 | 推荐写法 | 反模式 |
| --- | --- | --- | --- |
| `context_store.set(key, value, ttl_seconds=None)` | 写轻量状态 | `solver.context_store.set("signal.x", True)` | 写 population/history 大对象 |
| `context_store.update(values, ttl_seconds=None)` | 批量写轻量状态 | `solver.context_store.update({"signal.a": True})` | 写不可序列化对象 |
| `context_store.snapshot()` | 取 context 视图 | `ctx = solver.context_store.snapshot()` | 当成 snapshot store |
| `snapshot_store.write(payload, metadata=...)` | 写大对象 | `key = solver.snapshot_store.write(payload)` | 大对象直接塞 context |
| `solver.write_population_snapshot(...)` | 标准 population 写入 | `ok = solver.write_population_snapshot(pop, obj, vio)` | 各插件私自写不同格式 |
| `get_runtime_context_projection(...)` | adapter/plugin 暴露轻量运行切片 | `adapter.get_runtime_context_projection(solver)` | 返回大对象 |
| `get_report()` | plugin/adapter 小报告 | `plugin.get_report()` | 报告里放完整 trace |

## 8. Catalog / Doctor / CLI 速查

| 命令 / API | 作用 | 示例 |
| --- | --- | --- |
| `python -m nsgablack project doctor --path . --strict --format problem` | 检查标准脚手架边界 | 提交前最小检查 |
| `python -m nsgablack catalog list --profile framework-core --kind adapter` | 查看主干 adapter | 架构审计用 `framework-core` |
| `python -m nsgablack catalog search nsga2 --profile framework-core --limit 20` | 查组件 | 找 key、import path、mount point |
| `python -m nsgablack catalog show <key> --profile framework-core` | 查看单组件 | 查 contract / companions |

## 9. 常见组合模式索引

| 目标 | 推荐装配 | 详解 |
| --- | --- | --- |
| 单策略 baseline | `group(..., ["vns"])` 或直接 adapter | [03_orchestration_language.md](03_orchestration_language.md) |
| 同阶段多策略 | `group(..., ["nsga2", "de"])` | [03_orchestration_language.md](03_orchestration_language.md) |
| 多 group 并行 | `multi(..., [global_group, local_group])` | [03_orchestration_language.md](03_orchestration_language.md) |
| warmup -> exploit | `serial(..., [phase(...), phase(...)])` | [03_orchestration_language.md](03_orchestration_language.md) |
| 插件信号切策略 | `event(..., [event_case(...), ...])` | [03_orchestration_language.md](03_orchestration_language.md) |
| outer candidate 调 inner flow | Problem/Evaluation bridge + `ResourceContext` | [05_cross_framework_coordination.md](05_cross_framework_coordination.md) |
| 多 solver profile | `SolverManager + RegimeSpec + ResourceOffer` | [03_orchestration_language.md](03_orchestration_language.md) |
| GPU lease / 多进程 | `ResourcePolicy + SQLiteLeaseStore` | [06_l0_parallel_resource_patterns.md](06_l0_parallel_resource_patterns.md) |

## 10. 最小完整装配片段

```python
def build_solver(cfg, *, resource_context=None, component_overrides=None):
    problem = build_problem(cfg.problem)
    pipeline = build_pipeline(cfg.pipeline, component_overrides=component_overrides)

    solver = EvolutionSolver(problem=problem)
    solver.set_representation_pipeline(pipeline)

    explore = group(cfg.adapters, "explore", ["nsga2", "de"])
    exploit = group(cfg.adapters, "exploit", ["vns"])
    search = serial(
        cfg.adapters,
        "search_flow",
        [
            phase("warmup", explore, steps=20),
            phase("exploit", exploit, steps=-1),
        ],
    )
    solver.set_adapter(search)

    solver.set_context_store(build_context_store(cfg.state.context))
    solver.set_snapshot_store(build_snapshot_store(cfg.state.snapshot))

    for plugin in build_plugins(cfg.plugins):
        solver.add_plugin(plugin)

    return solver
```

这段代码的重点不是具体算法，而是装配顺序：先 problem/pipeline，再 solver，再 adapter orchestration，再 state/plugin。所有复杂能力都应该在这个结构上扩展。
