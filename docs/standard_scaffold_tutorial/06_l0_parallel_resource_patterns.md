# 06. L0 资源层与并行编排

L0 不是“开几个线程”的小参数，而是整个框架能否稳定跑并行、GPU、嵌套评估和多进程的基础层。它回答的问题是：

```text
这一次 solver / trial / inner evaluation
到底被授权使用哪些 CPU thread、GPU device、backend 和存储后端？
```

当前标准语言可以更精确地拆成三类：

```text
CPU / GPU / RAM:
  被申请和消耗的资源

Ray / K8s / local thread / process:
  执行任务的 ComputeBackend / ExecutorBackend

nsgablack L0:
  描述 task 需要什么资源、谁能跑、结果和产物如何审计
```

因此不要把 CPU/GPU 和 Ray/K8s 混成一类。CPU/GPU 是资源，Ray/K8s 是执行平台；L0 用统一协议把任务交给本地、Redis worker、未来 Ray/K8s 或云服务。

## 0. 项目侧入口：runtime/

标准脚手架的 L0 入口统一放在：

```text
runtime/
  config.py   # RuntimeProfile / backend / resource / store / transport
  graph.py    # 静态执行图：不运行也能看全局结构
  exporters.py  # 导出 json / mermaid / html
```

这里不再叫 `acceleration/`。原因是 L0 不只是“加速”，还包含：

| 维度 | 例子 | 说明 |
| --- | --- | --- |
| compute/executor | local/thread/process/Ray/K8s/cloud batch | 谁执行 task |
| resource | CPU thread/GPU/RAM/device token | task 被授权使用什么 |
| queue/result/state | memory/Redis/SQLite/service | task 怎么排队、回收结果、记录状态 |
| artifact | filesystem/S3/MinIO/object store | xlsx/json/checkpoint/model 放哪里 |
| transport | inline/artifact ref/object ref | 大数据如何跨 worker 传递 |
| lease | memory/SQLite/Redis/service lease | 谁真实持有 GPU/CPU 资源 |

默认 profile 应该是 `local_cpu`，也就是：

```python
apply_runtime_profile(solver, cfg.runtime, "local_cpu")
```

这个默认值不要求用户一开始理解所有后端。项目可以先完整编排 problem、pipeline、adapter、plugin、evaluation，让代码在本地 CPU 串行或轻量路径跑通。

推荐工作流：

```text
1. 先编排业务结构
   problem -> pipeline -> adapter/solver group -> plugin/evaluation

2. 不急着分配特殊资源
   默认 local_cpu，可以先跑 smoke

3. 生成静态执行图
   runtime/graph.py 输出一棵 folder-like plan tree
   runtime/exporters.py 输出 json/mmd/html

4. 根据图反推资源瓶颈
   哪些节点是 population evaluation
   哪些节点是 nested inner solver
   哪些节点会写大 artifact
   哪些节点需要 GPU lease

5. 只对特殊局部覆盖 runtime
   例如 threaded_cpu / process_cpu / local_gpu / Redis worker / Ray adapter

6. 运行后追加 runtime graph
   记录实际耗时、worker、lease、artifact_refs、fallback
```

这就是“先全局编排，再局部调资源”。如果什么都不写，项目仍然能跑；只有当某个局部确实需要更强资源语义时，才在 `runtime/config.py` 增加 profile 或 override。

静态图建议长这样：

```text
run
  modeling
    problem
    pipeline
      initializer
      mutator
      repair
      encoder
  search
    adapter / serial / multi / solver_group
  runtime
    profile=local_cpu
    task_requirement
    queue/result/state/artifact/transport/lease
  plugins
    observability
    checkpoint
    report
```

嵌套或多 solver 时不是把图拍扁，而是展开子树：

```text
outer_solver
  outer_population_evaluation
    candidate_task_0001
      inner_solver
        inner_pipeline
        inner_evaluation
        inner_runtime_context
    candidate_task_0002
      inner_solver
```

这样你不运行也知道大概哪里会有计算、数据传输和 artifact 输出；运行后再把真实耗时和资源占用补到同一棵树上。

## 1. L0 最小运行协议

标准脚手架里，L0 的最小对象是：

| 对象 | 回答的问题 | 标准位置 |
| --- | --- | --- |
| `TaskEnvelope` | 要执行什么任务 | outer evaluation / worker queue |
| `ResourceRequirement` | 这个任务需要什么资源 | solver config / task envelope |
| `WorkerDescriptor` | 哪个 worker 能跑 | local registry / Redis worker registry |
| `ResourceLease` | 实际授权了什么资源 | scheduler / allocator |
| `ResourceContext` | 传给 inner solver / trainer 的授权上下文 | eval context / report |
| `TaskResult` | 跑完结果是什么 | result backend / evaluator |
| `DataRef` | 大数据和产物在哪里 | artifact backend / report |

最小流程：

```text
TaskEnvelope
  -> WorkerDescriptor capability match
  -> ResourceRequirement becomes ResourceRequest
  -> ResourceAllocator acquires ResourceLease
  -> worker runs task
  -> TaskResult returns objectives/violations/artifact_refs
  -> ResourceLease release
```

这套协议和具体后端无关。本地 thread、Redis worker、未来 Ray/K8s 都应该消费同一套 `TaskEnvelope / TaskResult / ResourceRequirement`。

## 2. 后端分类

标准脚手架里不要只写一个模糊的 `backend` 字段。至少区分：

| 后端类别 | 职责 | 当前可用/状态 |
| --- | --- | --- |
| `ComputeBackend` / `ExecutorBackend` | 真正执行任务 | local thread/process；Ray/K8s 作为后续 adapter |
| `TaskQueueBackend` | 任务排队 | memory、Redis |
| `TaskResultBackend` | task result 存取 | memory、Redis |
| `TaskStateBackend` | task status | memory、Redis |
| `WorkerRegistryBackend` | worker 注册和 heartbeat | memory、Redis heartbeat |
| `ArtifactBackend` | xlsx/json/model/checkpoint 等产物 | memory、filesystem |
| `DataTransportBackend` | 数据怎么流动 | inline JSON、artifact ref |
| `LeaseStore` | 资源互斥真相 | memory、SQLite；Redis/service lease 后续扩展 |
| `ContextStore/SnapshotStore` | solver 运行态和大对象 snapshot | memory、Redis、file |

Redis 不是计算资源。Redis 在当前 L0 中适合做 queue/result/state/heartbeat；真正计算的是 Redis 后面的 worker。

Catalog backend 也不属于这张运行表。Catalog 负责组件发现、profile、能力矩阵和文档入口；L0 runtime backend 负责任务执行过程。二者可以都用 Redis/SQLite/PostgreSQL，但 schema、keyspace、生命周期必须分开。

## 3. 并行有几种层级

不同“并行”不在同一层：

| 并行层级 | 发生在哪里 | 典型对象 | L0 关注点 |
| --- | --- | --- | --- |
| adapter group 并行 | 单 solver 内多个 adapter 同时 propose | `group(...)` / `multi(...)` | 候选来源追踪，不直接代表 GPU 并行 |
| population evaluation 并行 | 单 solver 对一批候选并行评估 | evaluation runtime / backend plugin | worker 数、batch、CPU 线程 |
| solver group 并行 | 多个 solver profile 同时跑 | `SolverManager` / `RegimeSpec` | 每个 solver 的资源请求和隔离 |
| outer-inner 嵌套并行 | 多个 outer candidate 同时触发 inner flow | outer evaluator / process pool | 每个 inner 的 GPU lease |
| mlblack portfolio 并行 | inner flow 内多个 model candidate | mlblack portfolio / execution | 消费外层 `ResourceContext`，不抢外层 GPU |
| 分布式并行 | 多机、Ray、服务化 worker | future Redis/Ray backend | 分布式 lease store、heartbeat、队列 |

最常见误区：adapter group 不是 GPU 并行。adapter group 只是多个策略共同提出候选；候选是否并行评估，取决于 evaluation backend 和资源授权。

## 4. 单 solver 内的 adapter group

```python
search = multi(
    cfg.adapters,
    "portfolio",
    [
        group(cfg.adapters, "global", ["nsga2", "de"]),
        group(cfg.adapters, "local", ["vns", "trust_region_dfo"]),
    ],
)
solver.set_adapter(search)
```

这个结构的 L0 语义：

```text
one solver
  one problem
  one representation pipeline
  one evaluation path
  one L0 evaluation backend
```

它不会自动给 `nsga2` 一张 GPU、给 `vns` 另一张 GPU。GPU 或 CPU worker 是 evaluation/runtime 层决定的，不是 adapter group 决定的。

适合：

- 多策略共同提出候选。
- 同一 problem、同一 representation。
- 同一批评估预算。

不适合：

- 每个策略需要独立 GPU。
- 每个策略使用不同 problem。
- 每个策略需要独立 checkpoint/report。

这些情况应上升到 solver group。

## 5. 单 solver 的 population evaluation 并行

单 solver 里真正消耗资源的是评估阶段：

```text
adapter.propose(...)
  -> candidates
  -> representation repair/decode
  -> evaluate_population(candidates)
```

如果 `evaluate_population` 走 thread/process/backend plugin，就要控制：

| 参数 | 说明 |
| --- | --- |
| `batch_size` | 每代产生多少候选 |
| `max_workers` | 同时评估多少候选 |
| `threads_per_eval` | 每个候选评估可用线程 |
| `device_tokens` | 是否需要 GPU |
| `fail_fast` | 子任务失败是否中断整批 |

CPU-only 情况下可以比较宽松：

```python
offer = ResourceOffer(
    threads=16,
    backend="local",
    device_tokens=(),
)
policy = ResourcePolicy(
    mode="auto",
    cpu_oversubscribe=False,
)
```

GPU 情况下必须显式：

```python
offer = ResourceOffer(
    threads=16,
    backend="local",
    device_tokens=("cuda:0", "cuda:1"),
)
policy = ResourcePolicy(
    mode="strict",
    gpu_sharing="exclusive",
)
```

如果 8 个 worker 都可能调用 `cuda:0`，必须通过 lease 控制；不能只靠 trainer 自己写 `device="cuda:0"`。

### 5.1 用 ResourceRequirement 描述一个 task

在新的 L0 语言里，单个 task 不直接写 `workers=8`。`workers` 是并发池大小；单个 task 应写它自己需要什么：

```python
outer_task_requirement = ResourceRequirement(
    threads=1,
    gpus=0,
    memory_mb=512,
    capabilities=("nested_eval",),
    metadata={
        "layer": "L1",
        "role": "outer_candidate_task",
        "outer_parallel_workers": 4,
    },
)
```

如果 task 需要 GPU：

```python
train_requirement = ResourceRequirement(
    threads=4,
    gpus=1,
    device_tokens=("cuda:0",),
    gpu_memory_mb=8192,
    capabilities=("torch_train", "cuda"),
)
```

注意：

| 字段 | 语义 |
| --- | --- |
| `threads` | 单个 task 需要几个 CPU thread |
| `gpus` | 单个 task 需要几张 GPU |
| `device_tokens` | 指定或继承的具体设备，例如 `cuda:0` |
| `memory_mb` | task 需要的 RAM |
| `gpu_memory_mb` | task 需要的单卡显存要求 |
| `capabilities` | worker 必须声明的能力 |
| `metadata` | 并发池、layer、role、case 等审计信息 |

`outer_parallel_workers=4` 表示同时跑 4 个 outer candidate；不等于每个 candidate 吃 4 个 thread。这个区别很重要。

### 5.2 TaskEnvelope / TaskResult 最小形态

```python
task = TaskEnvelope(
    task_id="candidate_0007",
    task_type="nested_candidate_eval",
    payload={"candidate": [0.0, 2.0, 1.0], "index": 7, "run_id": "run_001"},
    requirement=outer_task_requirement,
    executor_backend="thread",
    namespace="supply_adjustment.run_001",
)
```

worker 完成后返回：

```python
result = TaskResult.success(
    task_id=task.task_id,
    objectives=(-78000.0, 22.0, 108.0),
    violations=(0.0,),
    worker_id="local-thread-1",
    lease_id="nested_candidate_eval_xxx",
    resource_context=resource_context,
    artifact_refs=(DataRef(uri="runs/out.xlsx", kind="report"),),
)
```

`objectives/violations` 是优化语义，`worker_id/lease_id/resource_context/artifact_refs` 是运行审计语义。两者都必须保留。

## 6. 多 solver group 并行

多个 solver profile 并行时，资源冲突概率更高：

```python
manager = SolverManager(
    regimes=(
        RegimeSpec("global_nsga2", lambda: build_solver(adapter_profile="nsga2")),
        RegimeSpec("local_vns", lambda: build_solver(adapter_profile="vns")),
        RegimeSpec("hybrid", lambda: build_solver(adapter_profile="hybrid")),
    ),
    offer=ResourceOffer(
        threads=16,
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

适合多 solver group 的情况：

| 情况 | 原因 |
| --- | --- |
| 比较多个 adapter profile | 每个 solver 有独立运行状态 |
| 不同 seed | checkpoint/report 不混 |
| 不同 representation | 维度、decode、repair 不同 |
| 不同 bias | 可以清楚比较 bias 收益 |
| 不同资源 profile | CPU/GPU 分开审计 |

不建议把这些硬塞进 adapter group，因为 adapter group 共享同一个 problem、pipeline 和 solver state。

## 7. outer-inner 嵌套评估的 GPU lease

最需要 L0 的场景是外层同时跑多个 inner evaluation：

```text
outer candidates:
  x0 -> inner mlblack flow -> cuda:0
  x1 -> inner mlblack flow -> cuda:1
  x2 -> wait / fail / queue
```

标准写法：

```python
allocator = ResourceAllocator(
    offer=ResourceOffer(
        threads=16,
        backend="local",
        device_tokens=("cuda:0", "cuda:1"),
    ),
    policy=ResourcePolicy(
        mode="strict",
        gpu_sharing="exclusive",
        lease_ttl_seconds=300.0,
        heartbeat_interval_seconds=30.0,
    ),
    lease_store=SQLiteLeaseStore("runs/resource_l0.sqlite3"),
)

lease = allocator.acquire(
    ResourceRequest(threads=2, backend="local", gpus=1),
    owner_id="trial_0007",
    scope="outer_eval",
)

try:
    resource_context = lease.resource_context(
        compute_backend="torch",
        device="auto",
        execution_backend="thread",
        namespace="nsgablack.trial_0007",
    )
    inner_result = inner_runner.evaluate(
        task,
        component_overrides=component_overrides,
        resource_context=resource_context,
    )
finally:
    allocator.release(lease)
```

长任务应在 worker wrapper 中周期性 heartbeat：

```python
allocator.heartbeat(lease)
```

不要把 heartbeat 写进 trainer。trainer 只消费 `ResourceContext`。

### 7.1 supply_adjustment_nested 的标准写法

`supply_adjustment_nested` 现在是这个 L0 形态的参考 case：

```text
outer solver:
  population fanout / candidate task queue
  outer_task_requirement = ResourceRequirement(...)

inner production solver:
  build_inner_task()
  inner_resource_requirement = ResourceRequirement(...)

worker:
  claims TaskEnvelope
  acquires ResourceLease
  injects ResourceContext into inner runtime
  returns TaskResult

export plugin:
  writes adjusted_supply xlsx
  writes move_log csv
  writes audit json
  writes l0_runtime_summary json
```

CLI 层不要只传散落参数，应该收口成两个 requirement：

```python
outer_task_requirement = ResourceRequirement(
    threads=1,
    capabilities=("nested_eval",),
    metadata={"outer_parallel_workers": outer_workers},
)

inner_resource_requirement = ResourceRequirement(
    threads=inner_workers,
    capabilities=("production_inner", "nested_eval"),
    metadata={"inner_parallel_workers": inner_workers},
)
```

当前 case 已支持这些 CLI 资源字段：

| 字段 | 作用 |
| --- | --- |
| `--outer-task-threads` | 单个 outer candidate task 的线程需求 |
| `--outer-memory-mb` | 单个 outer task RAM 需求 |
| `--outer-gpus` | 单个 outer task GPU 数 |
| `--outer-device-token` | 单个 outer task 指定设备，可重复传 |
| `--outer-gpu-memory-mb` | 单个 outer task 单卡显存需求 |
| `--inner-parallel-workers` | inner solver 可用 worker/threads |
| `--inner-memory-mb` | inner solver RAM 需求 |
| `--inner-gpus` | inner solver GPU 数 |
| `--inner-device-token` | inner solver 指定设备，可重复传 |
| `--inner-gpu-memory-mb` | inner solver 单卡显存需求 |

运行结束会输出：

```text
l0_runtime_summary_<run_id>.json
```

这个 summary 至少应该能看到：

| 字段 | 说明 |
| --- | --- |
| `outer.task_requirement` | outer task 的生效 `ResourceRequirement` |
| `inner.resource_requirement` | inner solver 的生效 `ResourceRequirement` |
| `effective_runtime.workers` | 实际 worker id |
| `effective_runtime.leases` | task 对应 lease |
| `effective_runtime.resource_contexts` | 注入 inner 的上下文 |
| `artifact_refs` | xlsx/csv/audit/report 的 `DataRef` |

如果一个 case 没有这些字段，就不能声称它已经标准接入 L0。

### 7.2 inner solver 也是资源消费者

如果 inner runtime 是一个完整 `nsgablack` solver，它和 `mlblack` flow 一样是资源消费者。区别只在于 inner solver 内部还会继续调度自己的 adapter group、population evaluation、plugin 和 snapshot。

```text
outer solver L0:
  owns outer population fanout
  owns outer trial priority
  owns GPU/CPU lease truth
  injects ResourceContext into inner runtime

inner solver L0:
  owns inner evaluation backend inside the grant
  owns inner adapter/phase execution details
  consumes parent ResourceContext
  must not acquire devices outside parent grant
```

这意味着 inner solver 不是不能并行，而是只能在 parent grant 内并行。例如 outer 给了：

```json
{
  "scope": "outer_eval",
  "namespace": "outer.trial_0007",
  "device_tokens": ["cuda:0"],
  "threads": 4,
  "max_workers": 2
}
```

inner solver 可以把这 4 个线程分给自己的 evaluation backend，但不能再私下开 16 个 worker，也不能改用 `cuda:1`。

### 7.3 nested ResourceContext 继承规则

推荐继承优先级：

```text
parent ResourceLease
  -> parent ResourceContext
  -> child ResourceRequest clamp
  -> child effective ResourceContext
  -> inner solver / flow / trainer consumes it
```

示例：

```python
parent_lease = allocator.acquire(
    ResourceRequest(threads=4, backend="local", gpus=1),
    owner_id="outer_trial_0007",
    scope="outer_eval",
)

parent_ctx = parent_lease.resource_context(
    namespace="outer.trial_0007",
    compute_backend="torch",
    device="auto",
    execution_backend="process",
)

inner_request = ResourceRequest(
    threads=2,
    backend="local",
    gpus=1,
)

child_ctx = clamp_child_request_to_parent(
    parent_context=parent_ctx,
    child_request=inner_request,
    namespace="outer.trial_0007.inner_0001",
)

inner_solver = build_inner_solver(
    inner_cfg,
    resource_context=child_ctx,
)
summary = inner_solver.run()
```

`clamp_child_request_to_parent(...)` 可以是项目工具函数，也可以后续收口到框架 L0。核心规则是：child 不能拿到 parent 没有授权的资源。

### 7.4 多层嵌套 namespace

多层嵌套时必须用稳定 namespace，否则 report 和 lease 很快不可读。

推荐格式：

```text
<outer_run_id>.trial_<outer_candidate_id>
<outer_run_id>.trial_<outer_candidate_id>.inner_<inner_run_id>
<outer_run_id>.trial_<outer_candidate_id>.inner_<inner_run_id>.flow_<flow_id>
```

示例：

```json
{
  "outer": {
    "namespace": "supply_l0.trial_0007"
  },
  "inner_solver": {
    "namespace": "supply_l0.trial_0007.inner_l1_0001"
  },
  "inner_flow": {
    "namespace": "supply_l0.trial_0007.inner_l1_0001.flow_eval_0003"
  }
}
```

namespace 应写入：

| 位置 | 字段 |
| --- | --- |
| lease | `lease.namespace` |
| context | `resource_context.namespace` |
| report | `runtime.namespace` |
| snapshot | `snapshot.metadata.namespace` |
| event trace | `event.namespace` |

### 7.5 inner 并行预算不能超过 outer grant

常见错误是 outer 同时跑 8 个候选，每个 inner 又开 8 个 worker，最后实际变成 64 个任务抢同一台机器。

正确做法：

```text
machine offer:
  threads = 32
  gpus = ["cuda:0", "cuda:1"]

outer:
  max_outer_workers = 4
  each outer eval grant = 1 GPU + 4 threads

inner:
  max_inner_workers <= 4
  threads_per_inner_eval <= 1 or 2
  device_tokens subset of parent grant
```

建议公式：

```text
outer_workers * threads_per_outer_eval <= total_threads
inner_workers_per_outer * threads_per_inner_eval <= threads_per_outer_eval
active_gpu_inner_jobs <= leased_gpu_tokens * max_jobs_per_gpu
```

如果 inner solver 内部还有 `mlblack portfolio`，portfolio 也必须在 inner grant 内运行：

```text
outer trial grant:
  cuda:0, threads=4

inner solver:
  evaluation backend max_workers=2

inner mlblack portfolio:
  serial or max_workers=2
  device must be cuda:0
```

不要让 inner portfolio 自己重新 round_robin 到 `cuda:1`，除非 parent grant 也包含 `cuda:1`。

### 7.6 lease 和 heartbeat 放在哪一层

推荐：

| 层 | 是否 acquire lease | 是否 heartbeat | 说明 |
| --- | --- | --- | --- |
| outer solver manager | 是 | 是 | 管 outer fanout 和真实 GPU token |
| outer evaluation worker | 通常持有 parent lease | 是 | 长 inner eval 期间续租 |
| inner solver | 不重新抢 parent 外资源 | 可报告使用状态 | 消费 child ResourceContext |
| inner trainer/flow | 否 | 否 | 只消费 device/thread |

如果 inner solver 运行时间很长，可以让 outer worker wrapper 负责 heartbeat：

```python
lease = allocator.acquire(request, owner_id=trial_id, scope="outer_eval")
try:
    with heartbeat_loop(allocator, lease, interval_seconds=30.0):
        result = inner_evaluator.evaluate(
            task,
            resource_context=lease.resource_context(namespace=namespace),
        )
finally:
    allocator.release(lease)
```

不要把 heartbeat 写进 inner trainer 或业务 problem。资源生命周期属于 L0 runner/worker，不属于业务模型。

### 7.7 nested resource report

嵌套运行至少记录三份资源信息：

| 报告层 | 必须记录 |
| --- | --- |
| outer report | parent request、parent lease、outer worker id、outer namespace |
| inner solver report | child effective context、inner workers、inner active backend |
| artifact/flow report | trainer/device/backend、fallback、runtime seconds |

示例：

```json
{
  "resource_tree": {
    "outer": {
      "request": {"threads": 4, "gpus": 1},
      "lease": {"device_tokens": ["cuda:0"], "ttl_seconds": 300},
      "namespace": "outer.trial_0007"
    },
    "inner_solver": {
      "effective_context": {
        "threads": 2,
        "device_tokens": ["cuda:0"],
        "namespace": "outer.trial_0007.inner_0001"
      },
      "max_workers": 2
    },
    "inner_flow": {
      "backend": "torch",
      "device": "cuda:0",
      "fallback": false
    }
  }
}
```

如果 report 中只看到 `gpus=1`，但看不到具体 `device_tokens` 和 namespace，就无法审计是否抢卡。

### 7.8 nested L0 反模式

| 反模式 | 后果 | 改法 |
| --- | --- | --- |
| inner solver 自己重新探测全部 GPU | 破坏 parent 调度 | 只消费 parent ResourceContext |
| parent 给 2 线程，inner 开 16 worker | CPU oversubscribe | child request clamp |
| outer 和 inner 共用一个 namespace | report/lease 混乱 | namespace 分层 |
| inner trainer 负责 heartbeat | 资源生命周期污染业务层 | outer worker wrapper heartbeat |
| inner portfolio round_robin 到未授权 GPU | 抢卡/OOM | device_tokens 必须是 parent 子集 |
| 多进程 nested 用 memory lease store | 每个进程都以为拿到 GPU | 用 SQLiteLeaseStore |

## 8. backend / store 怎么选

| 场景 | 推荐 |
| --- | --- |
| 单进程、本地调试、无 GPU | `InMemoryL0RuntimeBackend` + `InMemoryLeaseStore` |
| 单进程 thread backend + GPU | `InMemoryLeaseStore` 可以用，但仍建议显式 lease |
| 多进程 process backend + GPU | `SQLiteLeaseStore` |
| 多个 Python 进程共享本机 GPU | `SQLiteLeaseStore` |
| Redis worker 队列 | `RedisL0RuntimeBackend` |
| Ray / 多机 / 容器集群 | 后续 `RayBackendAdapter` / `K8sBackendAdapter` + distributed lease backend |
| 大产物 xlsx/json/model | `FilesystemArtifactBackend` 或后续 S3/MinIO backend |
| 小 task payload | `InlineDataTransportBackend` |
| 大矩阵/数据集/checkpoint | `ArtifactDataTransportBackend` / mmap / object store |
| 只需要事件通知 | `InMemoryMessageQueue` / `SQLiteMessageQueue` |
| solver 运行状态大对象 | `ContextStore` / `SnapshotStore` |

关键边界：

| 后端 | 真正负责什么 |
| --- | --- |
| `TaskQueueBackend` | task 排队 |
| `TaskResultBackend` | task result 存取 |
| `TaskStateBackend` | task status |
| `WorkerRegistryBackend` | worker 注册和 heartbeat |
| `ArtifactBackend` | 大产物保存 |
| `DataTransportBackend` | task 输入输出数据传输 |
| `LeaseStore` | 资源互斥真相 |
| `MessageQueue` | 事件通知，不释放资源 |
| `ContextStore` | 轻量运行状态 |
| `SnapshotStore` | 大对象和 artifact 引用 |
| Redis context/snapshot | 分布式状态存储，不等于 GPU 锁 |

当前主干已经有 `SQLiteLeaseStore`，可解决本机多进程 GPU 抢占。`RedisL0RuntimeBackend` 已经可以做 task queue/result/state/heartbeat，但 Redis distributed lease store 仍作为扩展点保留；不要在文档或项目里假装 Redis GPU lease 已经完整可用。

## 9. GPU 策略

默认用 exclusive：

```python
ResourcePolicy(mode="strict", gpu_sharing="exclusive")
```

这表示同一张 GPU 同时只能给一个 active lease。适合：

- torch 训练。
- 显存占用不可预测。
- inner evaluation 时间较长。

共享 GPU 必须显式：

```python
ResourcePolicy(
    mode="strict",
    gpu_sharing="shared",
    max_jobs_per_gpu=2,
    gpu_memory_fraction=0.45,
)
```

共享 GPU 只适合：

- 每个任务显存可控。
- batch 很小。
- trainer 能尊重 memory fraction。
- report 记录了共享策略。

不要默认 shared。OOM 风险通常比闲置 GPU 更难排查。

## 10. strict / warn / auto / queue

| mode | 语义 | 适用 |
| --- | --- | --- |
| `strict` | 超预算直接失败 | 默认推荐 |
| `warn` | 记录警告，尽量继续 | 调试、兼容旧项目 |
| `auto` | CPU 线程可 clamp | CPU-only smoke |
| `queue` | 语义上表示等待资源 | 后续可接调度队列 |

当前本机实现里，`queue` 不应被理解为完整调度系统。要真正排队，需要 worker scheduler 或 message queue/Redis/Ray 后端配合。没有队列 worker 时，建议用 `strict`，失败后由上层决定重试或降级。

## 11. Redis 应该放在哪

Redis 有几种完全不同的用途：

| 用途 | 是否当前主干已完整内置 | 说明 |
| --- | --- | --- |
| runtime context/snapshot | 取决于对应 store 实现 | 存运行状态和大对象引用 |
| L0 task queue/result/state/heartbeat | 已有 `RedisL0RuntimeBackend` | 分发 `TaskEnvelope`，收集 `TaskResult` |
| message queue / stream | 扩展点 | 事件通知、worker 唤醒，可后续从 list 升级 stream |
| distributed lease store | 扩展点 | 多机 GPU/worker 资源互斥 |

Redis lease store 的语义应是：

```text
acquire:
  atomic check active lease keys
  write lease key with TTL
  write device-token index

heartbeat:
  extend lease TTL
  refresh last_heartbeat_at

release:
  delete / mark released
  remove device-token index

active_leases:
  scan active lease keys
```

Redis message queue 的语义应是：

```text
publish resource.lease.acquired
publish resource.lease.released
publish resource.lease.expired
publish resource.lease.conflict
```

两者不能混。ack 消息不等于 release lease。

Redis worker 的最小边界：

```text
solver process:
  RedisL0RuntimeBackend.submit_many(TaskEnvelope...)

worker process:
  RedisL0RuntimeBackend.claim()
  acquire local / distributed lease
  run task
  RedisL0RuntimeBackend.complete(TaskResult)

solver process:
  RedisL0RuntimeBackend.get_result(run_id, task_id)
```

如果以后接 Ray/K8s，仍然保持这个边界，只是 worker 启动和任务执行从“自己写 worker loop”变成 Ray task 或 K8s Job。

## 12. Ray / K8s / 云服务属于哪一层

Ray/K8s/云服务属于 L0 的 backend adapter，不属于 L0 protocol 核心。

```text
L0 Protocol:
  TaskEnvelope / TaskResult / ResourceRequirement / DataRef

L0 Runtime:
  submit / claim / complete / heartbeat / state / artifact

Backend Adapter:
  local thread
  Redis worker
  Ray task/actor
  Kubernetes Job/Pod
  cloud batch job
```

Ray backend 应该做：

```text
TaskEnvelope -> ray.remote task/actor
TaskResult <- ray result
DataRef -> object store / filesystem / S3
ResourceRequirement -> Ray resource options
```

K8s backend 应该做：

```text
TaskEnvelope -> Job/Pod spec
ResourceRequirement -> cpu/memory/gpu limits
TaskResult <- result backend / artifact backend
WorkerDescriptor <- node/pod capability projection
```

L0 不应该重写 Ray/K8s 的容错、扩缩容和部署生态。L0 只负责把 `nsgablack/mlblack` 的任务语义、资源要求和审计结果稳定映射过去。

## 13. 不同组装下怎么配

| 组装形态 | 推荐资源策略 |
| --- | --- |
| 单 solver + 单 adapter + CPU | `ResourceOffer(threads=N)`，无 GPU lease |
| 单 solver + adapter group + CPU | 控制 evaluation worker，不给 adapter 单独分资源 |
| 单 solver + GPU inner eval | acquire lease per inner eval |
| serial group | 同一时刻只有一个 phase active，共享同一 L0 |
| multi group | group 只影响候选来源，不直接分 GPU |
| solver group parallel | 每个 solver 声明 request，由 manager 统一检查 |
| nested nsgablack -> mlblack | nsgablack acquire lease，注入 `ResourceContext` |
| mlblack portfolio inside inner | mlblack 在外层 grant 内消费资源，不再抢外层 GPU |
| process backend | 用 `SQLiteLeaseStore` |
| Ray / 多机 | 需要 Redis/service lease backend |

## 14. 报告字段

资源相关 report 至少记录：

| 字段 | 说明 |
| --- | --- |
| `resource_offer` | 本次运行可用资源 |
| `resource_requirement` | task/inner/worker 级资源需求 |
| `resource_request` | 转给 allocator 的资源请求 |
| `resource_policy` | strict/shared/ttl 等策略 |
| `resource_lease` | 实际授权 |
| `resource_context` | 注入 inner 的上下文 |
| `task_envelope` | task 输入、类型、namespace、requirement |
| `task_result` | objectives、violations、metrics、worker、lease |
| `worker_id` / `worker_descriptor` | 谁跑的、声明了什么能力 |
| `artifact_refs` | xlsx/json/checkpoint/model 等产物引用 |
| `lease_store` | in-memory/sqlite/redis |
| `active_lease_count` | 调试并发 |
| `heartbeat` | 是否启用、最近时间 |
| `stale_pruned` | 是否清理 stale lease |
| `fallback` | 是否从 GPU fallback 到 CPU |

如果 report 中看不到生效资源，就不要相信“它用了 GPU”。

## 15. 常见反模式

| 反模式 | 后果 | 改法 |
| --- | --- | --- |
| example 里写死 `cuda:0` | 多进程抢卡、不可审计 | 用 `ResourceContext` |
| 只写 `gpus=1` 不落具体 token | 不知道用哪张 GPU | 用 `device_tokens` |
| 把 `outer_parallel_workers` 当成单 task threads | 并发池和 task 需求混乱 | `outer_parallel_workers` 放 metadata，task `threads` 单独声明 |
| 把 xlsx/csv/checkpoint 放进 task payload | Redis/queue 变慢且不可控 | 用 `DataRef` / `ArtifactBackend` |
| 把 Redis 当计算后端 | 误以为 Redis 会跑任务 | Redis 只排队，worker/Ray/K8s 才计算 |
| catalog backend 和 runtime backend 共用语义 | 发现索引和运行状态混乱 | catalog 与 L0 runtime schema 分离 |
| adapter group 当成 GPU 分组 | 资源层级混乱 | evaluation/solver group 管资源 |
| 多进程用 `InMemoryLeaseStore` | 每个进程各自以为拿到 GPU | 用 `SQLiteLeaseStore` |
| message ack 当 release | stale lease 仍存在 | 调 `release()` 或 TTL 过期 |
| heartbeat 写进 trainer | 业务和资源生命周期混在一起 | runner/worker 管 heartbeat |
| Redis context store 当 lease store | 状态存储不等于资源互斥 | 单独实现 Redis lease store |

## 16. 验收清单

- 单进程 CPU smoke 能跑。
- `TaskEnvelope` 里能看到生效 `ResourceRequirement`。
- `TaskResult` 里能看到 `worker_id`、`lease_id`、`resource_context`。
- 大产物通过 `artifact_refs` 暴露，不进入 task payload。
- GPU 任务能看到具体 `device_tokens`。
- 多进程 GPU 使用 `SQLiteLeaseStore`。
- stale lease 能通过 TTL/heartbeat 清理。
- nested inner report 能看到外层 `ResourceContext`。
- `l0_runtime_summary` 能看到 outer/inner requirement、worker、lease、artifact refs。
- catalog backend 与 L0 runtime backend 没有混用 schema/keyspace。
- adapter group 和 solver group 的资源语义没有混淆。
- report 中能看到 request/offer/policy/lease/context。
