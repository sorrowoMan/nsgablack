# 02. 每个组件怎么配置

本章按同一种格式解释每个组件：

```text
落点 -> 最小代码 -> 配置字段 -> Builder -> 挂载 API -> 禁止事项 -> 验收方式
```

`nsgablack` 项目脚手架不要把参数散落在 `run_solver.py` 或 example 脚本里。推荐统一语言：

```text
Spec 保存参数
Registry 保存可选项
Builder 把 Spec 变成对象
build_solver 选择 key 并挂载
```

## 0. 配置链路总览

每个正式组件都建议保持同一条链路：

```text
<component>/config.py
  -> Spec(key, params)
  -> Registry(registry=(Spec(...), ...))
  -> register_<component>_builder(key, builder)
  -> build_<component>(registry, key)
  -> build_solver(... key ...)
  -> solver.set_* / solver.add_plugin
```

对应到不同组件：

| 组件 | Spec/Registry | Builder | 挂载 API |
| --- | --- | --- | --- |
| Problem | `ProblemSpec` / `ProblemRegistry` | `build_problem(...)` | `create_evolution_solver(problem)` |
| Pipeline | `PipelineSpec` / `PipelineRegistry` | `build_pipeline(...)` | `solver.set_representation_pipeline(pipeline)` |
| Adapter | `AdapterSpec` / `AdapterRegistry` | `compose_search(...)` | `solver.set_adapter(adapter)` |
| Bias | `BiasSpec` / `BiasRegistry` | `build_bias(...)` | `create_evolution_solver(..., bias_module=bias)` |
| Plugin | `PluginSpec` / `PluginRegistry` | `build_plugins(...)` | `solver.add_plugin(plugin)` |
| Store | `StorageConfig` | `_apply_storage_config(...)` | `solver.set_context_store(...)` / `solver.set_snapshot_store(...)` |

如果一个参数不知道该放哪里，先问它控制什么：

| 参数控制 | 放哪里 |
| --- | --- |
| objective/constraint | problem spec |
| bounds/decode/repair | pipeline spec |
| batch size/search 策略 | adapter spec |
| soft prior/domain seed | bias spec |
| report/checkpoint/trace | plugin spec |
| worker/device/store | runtime/storage config |

## 1. Problem：目标、约束和评估语义

落点：

```text
problem/<name>_problem.py
problem/config.py
```

Problem 负责回答三个问题：

| 问题 | 对应内容 |
| --- | --- |
| 候选解是什么维度？ | `dimension`、`bounds` |
| 优化什么？ | `evaluate(x)` 返回 objectives |
| 什么不可行？ | `evaluate_constraints(x)` 返回 violations |

最小 problem：

```python
from __future__ import annotations

import numpy as np


class ExampleProblem:
    name = "example"
    dimension = 2
    objectives = ("f1", "f2")

    def __init__(self) -> None:
        self.bounds = {"x0": [-5.0, 5.0], "x1": [-5.0, 5.0]}

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        f1 = float(np.sum(x ** 2))
        f2 = float(np.sum((x - 1.0) ** 2))
        return np.asarray([f1, f2], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)
```

配置字段建议：

```python
@dataclass(frozen=True)
class ProblemSpec:
    key: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProblemRegistry:
    registry: tuple[ProblemSpec, ...] = ()
```

Builder 模式：

```python
ProblemBuilder = Callable[[dict[str, object]], object]
_PROBLEM_BUILDERS: dict[str, ProblemBuilder] = {}


def register_problem_builder(key: str, builder: ProblemBuilder) -> None:
    _PROBLEM_BUILDERS[str(key).strip().lower()] = builder


def build_problem(registry: ProblemRegistry, key: str) -> object:
    lookup = str(key).strip().lower()
    for spec in registry.registry:
        if spec.key == lookup:
            return _PROBLEM_BUILDERS[lookup](dict(spec.params))
    raise ValueError(f"Problem key not registered: {key}")
```

挂载 API：

```python
problem = build_problem(cfg.problems, problem_key)
solver = create_evolution_solver(problem, bias_module=bias)
```

禁止事项：

```python
# 错误：problem 里改 adapter 策略
self.adapter = VNSAdapter(...)

# 错误：problem 里写 report 副作用
Path("report.csv").write_text(...)

# 错误：evaluate 返回不稳定 shape
return np.array([f1]) if easy else np.array([f1, f2])
```

验收方式：

- `evaluate(x)` 对任意合法 `x` 返回固定长度 objective。
- `evaluate_constraints(x)` 返回固定长度 violation。
- `bounds` 与 representation 输出维度一致。
- 异常输入要么被 `repair` 修复，要么明确抛错。

逐步改造建议：

1. 先写纯函数形式的 `evaluate(x)`，不要接插件、不要读文件。
2. 再补 `evaluate_constraints(x)`，即使没有约束也返回 `np.zeros(0)`。
3. 再把业务参数放进 `ProblemSpec.params`。
4. 最后才考虑 evaluation provider、缓存或嵌套 inner runtime。

problem 的最小自测片段可以放进项目测试或 notebook：

```python
problem = build_problem(cfg.problems, "offloading")
x = np.asarray([0.5, 0.8], dtype=float)
obj = problem.evaluate(x)
vio = problem.evaluate_constraints(x)
assert obj.shape == (2,)
assert vio.ndim == 1
```

## 2. RepresentationPipeline：候选解流转

落点：

```text
pipeline/<name>_pipeline.py
pipeline/config.py
```

Representation 负责候选从“搜索变量”到“可评估变量”的流转：

| 子组件 | 作用 | 典型实现 |
| --- | --- | --- |
| initializer | 生成初始候选 | `UniformInitializer` |
| mutator | 产生扰动 | `GaussianMutation` |
| repair | 兜底修复 | `ClipRepair` |
| encoder/decode | 内部表示和业务表示转换 | typed object encoder |

最小 pipeline：

```python
from nsgablack.representation import ClipRepair, GaussianMutation, RepresentationPipeline, UniformInitializer


def build_pipeline(low: float = -5.0, high: float = 5.0, sigma: float = 0.25) -> RepresentationPipeline:
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        mutator=GaussianMutation(sigma=sigma, low=low, high=high),
        repair=ClipRepair(low=low, high=high),
        encoder=None,
    )
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "Minimal numeric representation pipeline."
    return pipeline
```

挂载 API：

```python
pipeline = build_pipeline(cfg.pipelines, pipeline_key)
solver.set_representation_pipeline(pipeline)
```

什么时候需要 typed representation object：

| 场景 | 建议 |
| --- | --- |
| genome 只是连续向量 | 普通 numeric pipeline |
| genome 包含类别、shape、开关、层级结构 | typed representation object |
| genome 要控制内层组件参数 | decode 成 `component_overrides` 或 inner task spec |
| genome 要表达符号结构 | 单独 representation object，不要塞进 adapter |

错误写法：

```python
# 错误：repair 里实现业务策略搜索
if network_is_bad:
    x[:] = force_safe_policy()

# 错误：adapter 里硬编码 decode 规则
candidate[0] means kernel_shape, candidate[1] means pooling
```

正确写法：

```python
# repair 只兜底 shape/bounds
x = np.clip(x, low, high)

# decode 规则由 representation 明确表达
component_overrides = decode_typed_genome(x)
```

验收方式：

- initializer/mutator/repair 输出 shape 稳定。
- repair 不改变目标函数语义。
- encode/decode 可序列化、可记录。
- `run_inspector` 能看到 pipeline 挂载状态。

pipeline 与 problem 的对齐检查：

| 检查项 | 例子 |
| --- | --- |
| 维度一致 | problem.dimension=2，initializer 输出 shape=(2,) |
| bounds 一致 | problem bounds 是 `[0,1]`，repair 不应输出 1.3 |
| decode 可追踪 | typed genome decode 后能写入 report |
| repair 不偷业务 | repair 只修 shape/bounds，不做策略选择 |

如果 pipeline 输出的是 typed object，不建议让 problem 猜字段含义。推荐让 representation 明确暴露 decode：

```python
decoded = pipeline.decode(candidate)
objectives = problem.evaluate(decoded)
```

或者在 problem 内部只接收一个明确 task：

```python
task = decode_outer_candidate(x)
result = inner_evaluator.evaluate(task)
```

## 3. Adapter：搜索策略

落点：

```text
adapter/<name>_adapter.py
adapter/config.py
```

Adapter 只做两件事：

```python
class MyAdapter(AlgorithmAdapter):
    def propose(self, solver, context):
        return candidates

    def update(self, solver, candidates, objectives, violations, context):
        self._state = updated_state
```

推荐可选 API：

```python
def get_state(self) -> dict:
    return {"population": self._population, "rng_state": self._rng_state}


def set_state(self, state: dict) -> None:
    self._population = state.get("population")


def get_population(self):
    return self._population


def set_population(self, population) -> None:
    self._population = population


def get_runtime_context_projection(self) -> dict:
    return {"adapter_name": self.name, "population_size": len(self._population)}
```

注册：

```python
register_adapter_builder("vns", lambda p: VNSAdapter(**p))
register_adapter_builder("my_adapter", lambda p: MyAdapter(**p))
```

挂载 API：

```python
adapter = compose_search(cfg.adapters, primary_key="vns", mode="single")
solver.set_adapter(adapter)
```

边界：

| 不应该在 Adapter 里做 | 应该放到哪里 |
| --- | --- |
| 写 checkpoint | Plugin / SnapshotStore |
| 写 CSV report | Plugin / reporting |
| 读大数据训练模型 | Problem inner evaluator 或 mlblack flow |
| 写业务硬约束 | Problem constraint 或 Representation repair |
| 修改 context 大对象 | SnapshotStore + context ref |

验收方式：

- `propose()` 只产候选，不评估候选。
- `update()` 只消费 objectives/violations，不重新计算 objective。
- checkpoint 恢复后 adapter state 一致。
- 多策略编排时 adapter 不依赖全局变量。

adapter 参数的推荐拆法：

| 参数 | 放法 |
| --- | --- |
| `batch_size` | `AdapterSpec.params` |
| `mutation_sigma` | adapter 参数或 pipeline mutator 参数，不能两边重复控制 |
| `trust_region_radius` | adapter 参数 |
| `max_generations` | solver/controller 预算参数，不是 adapter 私有参数 |
| `random_seed` | run config 或 adapter params，但要进入 report |

最小 smoke 逻辑：

```python
adapter = compose_search(cfg.adapters, primary_key="vns", mode="single")
solver.set_adapter(adapter)
candidates = adapter.propose(solver, {"generation": 0})
assert len(candidates) > 0
```

多策略时要确认每个子 adapter 都能收到自己候选的反馈。不要让多个 child adapter 共享同一个内部 population，除非这是显式设计。

## 4. Bias：软引导

落点：

```text
bias/domain/<name>_bias.py
bias/domain/config.py
```

Bias 适合表达“建议”，不适合表达“必须”：

| 适合放 Bias | 不适合放 Bias |
| --- | --- |
| domain seed | 硬约束 |
| 初始候选偏好 | objective |
| candidate prior | 评估短路 |
| surrogate hint | checkpoint |

正确语义：

```python
bias = build_bias(cfg.biases, bias_key, component_overrides=component_overrides)
solver = create_evolution_solver(problem, bias_module=bias)
```

风险说明：

- 如果 bias 会让搜索倾向某些区域，report 中要记录启用状态。
- 如果启用 `ignore_constraint_violation_when_bias` 这类配置，必须写明它可能牺牲可行性排序。
- 业务硬规则应放 constraint，而不是 bias。

## 5. Plugin：运行能力

落点：

```text
plugins/<name>_plugin.py
plugins/config.py
```

生命周期：

```text
on_solver_init
on_population_init
on_generation_start
on_step
on_generation_end
on_solver_finish
```

评估短路入口：

```text
evaluate_individual
evaluate_population
```

典型 plugin 类型：

| 类型 | 用途 |
| --- | --- |
| trace plugin | 记录每代摘要 |
| checkpoint plugin | 保存/恢复 adapter 和 solver state |
| evaluation plugin | 接管单点或批量评估 |
| backend plugin | 接入并行、远端执行、缓存 |
| report plugin | 写 summary、CSV、JSON |
| guard plugin | 超时、预算、严格模式 |

最小生命周期插件：

```python
from nsgablack.plugins import Plugin


class ExampleProjectPlugin(Plugin):
    context_provides = ("example_project_plugin_last_generation",)

    def __init__(self, interval: int = 5) -> None:
        super().__init__(name="example_project_plugin")
        self.interval = int(interval)

    def on_generation_end(self, generation: int) -> None:
        if self.solver is None:
            return
        if generation % self.interval == 0:
            self.solver.context_store.set("example_project_plugin_last_generation", int(generation))
```

短路评估插件要保证 shape：

```python
def evaluate_population(self, solver, population, context):
    objectives = []
    violations = []
    for x in population:
        objectives.append(my_eval(x))
        violations.append(my_constraints(x))
    return np.asarray(objectives, dtype=float), np.asarray(violations, dtype=float)
```

错误写法：

```python
# 错误：批量评估返回少一行
return objectives[:-1], violations

# 错误：把完整 history 长期塞 context
context["history"] = huge_history
```

正确写法：

```python
snapshot_key = solver.write_population_snapshot(population, objectives, violations)
context["population_ref"] = snapshot_key
```

plugin 配置建议：

| 参数 | 示例 | 说明 |
| --- | --- | --- |
| `enabled` | `true/false` | 是否启用 |
| `strict` | `true/false` | 外部资源失败是否中断 |
| `interval` | `5` | 每几代触发 |
| `output_dir` | `runs/<run_id>` | 输出位置 |
| `report_key` | `trace_summary` | 写入报告的稳定 key |

plugin 生命周期中不要假设所有字段都存在。推荐读取 context 时使用默认值，并把必要依赖写进 contract：

```python
context_requires = ("generation",)
context_provides = ("trace_summary_ref",)
context_mutates = ()
context_cache = ()
```

## 6. Evaluation Runtime：评估来源

落点：

```text
evaluation/config.py
evaluation/<provider>.py
```

Evaluation runtime 适合处理：

- 本地 problem evaluate。
- 外部服务评估。
- 缓存评估。
- 嵌套 inner solver/flow 评估。
- 批量评估加速。

边界：

- objective/constraint 语义仍要可追溯。
- provider 可以加速或替换评估路径，但不能让返回 shape 不稳定。
- 如果接远端服务，失败模式必须明确：soft-error 还是 strict fail。

## 7. Runtime：L0 资源与运行后端

落点：

```text
runtime/config.py
runtime/graph.py
```

Runtime 负责 L0 资源和运行过程，不负责业务语义：

| 应放这里 | 不应放这里 |
| --- | --- |
| 并行 backend | objective 公式 |
| worker 数 | adapter 策略 |
| device pool | trainer 参数细节 |
| remote executor | report 逻辑 |
| queue/result/state backend | problem 约束 |
| artifact/data transport | 搜索策略 |

在跨框架 case 中，`nsgablack` 只负责外层资源授权和调度上下文，不能硬编码 `mlblack` 内部 trainer 的 GPU 细节。

L0 配置建议分三层：

| 层 | 说明 |
| --- | --- |
| `ResourceOffer` | 当前 runtime 有什么，例如 threads、device_tokens |
| `ResourceRequest` | 某个 solver/evaluation 想要什么 |
| `ResourceLease` / `ResourceContext` | 实际授权结果，传给 inner runtime |

本机多进程 GPU 互斥用 `SQLiteLeaseStore`；单进程/thread 调试用 `InMemoryLeaseStore`。消息队列不是必需，只作为事件通知或审计扩展。

标准脚手架的默认挂载应保持简单：

```python
apply_runtime_profile(solver, cfg.runtime, "local_cpu")
```

只有当静态执行图或实际运行报告说明某个局部确实需要特殊资源时，再增加 profile：

| profile | 典型用途 |
| --- | --- |
| `local_cpu` | 默认本地 CPU，先保证流程可运行 |
| `threaded_cpu` | 单机 CPU 批量评估 |
| `process_cpu` | CPU-heavy 或隔离性更强的评估 |
| `local_gpu` | 需要明确 GPU token/lease 的 inner evaluation |
| `redis_worker` | 后续分布式 worker queue |
| `ray` / `k8s` | 后续接成熟调度系统 |

`runtime/graph.py` 用来输出静态计划图。它不是优化算法的一部分，而是帮助你在不运行或刚跑 smoke 后看清：

- 哪些 stage 会产生 task。
- 哪些 stage 需要 worker/lease。
- 哪些 stage 会写 artifact。
- 哪些 nested inner flow 必须继承外层 `ResourceContext`。

## 8. Context / Snapshot：状态协议

规则：

```text
轻量状态 -> ContextStore
大对象 -> SnapshotStore
context 只保存 *_ref
```

禁止长期写入 context：

```text
population
objectives
violations
history
trace
large artifact
```

标准 API：

```python
solver.set_context_store(store)
solver.set_snapshot_store(store)
snapshot_key = solver.write_population_snapshot(population, objectives, violations)
payload = solver.read_snapshot(snapshot_key)
```

读取优先级：

```text
snapshot -> adapter 内部状态 -> solver lightweight mirror
```

写回优先级：

```text
adapter.set_population* -> solver.write_population_snapshot -> context *_ref
```

## 9. Catalog：组件可发现性

项目本地 catalog：

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search vns --path . --global
```

框架主干 catalog：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

口径规则：

| profile | 用途 |
| --- | --- |
| `framework-core` | 判断主干能力，不含 example/doc |
| `default` | 查教学示例、模板和完整文档索引 |

新增正式组件时，至少要回答：

- 组件 key 是什么？
- 属于 adapter/problem/pipeline/plugin/bias 哪一类？
- 输入输出 contract 是什么？
- 什么时候应该用？
- 和已有组件有什么差别？

## 10. 最小验收矩阵

| 改动类型 | 至少验证 |
| --- | --- |
| Problem | 单点评估、约束 shape、doctor build |
| Pipeline | init/mutate/repair shape、bounds、doctor build |
| Adapter | propose/update、checkpoint state、单代 smoke |
| Plugin | 生命周期、短路 shape、soft/strict 失败模式 |
| Evaluation provider | 单点/批量一致性、异常路径 |
| Catalog | `default` 与 `framework-core` 口径 |
| 跨框架 case | ResourceContext、inner report、outer objective |
