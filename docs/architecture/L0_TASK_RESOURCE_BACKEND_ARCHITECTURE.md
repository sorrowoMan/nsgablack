# L0 Task / Resource / Backend Architecture

本文定义 `nsgablack` 的 L0 主线架构。L0 不是某一个并行后端，也不是优化算法本身；L0 是任务、资源、worker、数据流、状态和结果的运行时编排平面。

## 1. 核心边界

```text
Solver / Adapter / Problem / Plugin
  describe what should happen

L0 Orchestration
  decides where it happens, with which resources, through which data path
```

也就是：

```text
Task: 要做什么
Resource: 需要/可用什么
Worker: 谁能做
ExecutorBackend: 怎么执行
QueueBackend: 怎么排队和传消息
StateBackend: 状态放哪里
ArtifactBackend: 大产物放哪里
DataTransport: 数据怎么流动
Result: 做完后返回什么
```

## 2. Resource 不是 Worker

资源是可以被占用或消耗的东西：

- CPU threads
- RAM
- GPU / VRAM
- disk IO
- network IO
- API quota
- time budget

worker 是持有或声明资源的执行单元：

```text
WorkerDescriptor(
  worker_id="server-a-worker-1",
  executor_backend="redis",
  resource_backend="local",
  capabilities=["nested_eval", "numpy"],
  offer={
    threads=8,
    device_tokens=["cuda:0"],
    metadata={
      "memory_mb": 16384,
      "gpu_memory_mb_by_device": {"cuda:0": 24576}
    }
  }
)
```

CPU/GPU/RAM 本身不是 worker。它们是 worker 的资源属性。

GPU 没有从 L0 中消失。新的 L0 表达方式是把 GPU 从零散的 `metadata` 里提升成可检查的资源要求：

```python
ResourceRequirement(
    threads=4,
    gpus=1,
    device_tokens=("cuda:0",),
    gpu_memory_mb=8192,
    capabilities=("torch_train", "cuda"),
)
```

## 3. Backend 分类

不要把所有后端都叫 backend。L0 至少要分这些类：

| 后端类别 | 职责 | 例子 |
| --- | --- | --- |
| `ComputeBackend` | 真正执行计算 | thread, process, Ray, Dask, CUDA, torch-ddp, k8s job |
| `QueueBackend` | 任务排队和小消息传输 | Redis list/stream, RabbitMQ, Kafka, NATS |
| `StateBackend` | 状态、lease、task status | memory, SQLite, Redis, PostgreSQL, etcd |
| `ArtifactBackend` | 大产物保存 | filesystem, S3, MinIO, network disk |
| `DataTransportBackend` | 数据如何传输 | inline JSON, artifact_ref, shared_memory, mmap, Arrow, DLPack, NCCL, MPI |
| `WorkerRegistryBackend` | worker 注册和心跳 | memory, Redis, PostgreSQL, k8s API |
| `MetricsTraceBackend` | 指标、trace、审计 | jsonl, SQLite, PostgreSQL, Prometheus, OpenTelemetry |

Redis 可以是 queue backend、message transport backend、state backend，但不是计算后端。真正计算的是 Redis 后面的 worker。

Catalog backend 必须和运行过程 backend 分离：

- Catalog backend 负责发现、索引、profile、组件能力矩阵和文档入口。
- L0 runtime backend 负责任务排队、worker 心跳、lease、task state、result、artifact 和数据传输。
- 二者可以都使用 Redis/SQLite/PostgreSQL，但 keyspace、schema、生命周期和故障语义必须分开。

## 4. TaskEnvelope

任务是要执行的一件工作。典型任务：

- `evaluate_candidate`
- `evaluate_population_chunk`
- `run_inner_solver`
- `run_simulation`
- `train_model`
- `predict_batch`
- `export_report`
- `checkpoint`
- `archive_update`

L0 标准任务包：

```python
TaskEnvelope(
    task_id="candidate_0007",
    task_type="nested_candidate_eval",
    payload={"candidate": [...]},
    requirement=ResourceRequirement(
        threads=2,
        memory_mb=1024,
        capabilities=("nested_eval",),
        timeout_seconds=300,
    ),
    executor_backend="redis",
    input_refs=(DataRef(uri="runs/input.parquet", kind="dataset"),),
    namespace="supply_adjustment.outer",
)
```

任务可以携带小 payload，但大数据必须传 `DataRef`。

## 5. DataRef / DataFlow

小数据可以 inline：

```json
{"candidate": [0.1, 0.2, 0.3]}
```

大数据要传引用：

```python
DataRef(
    uri="runs/case/input.parquet",
    kind="dataset",
    backend="filesystem",
)
```

推荐规则：

| 数据类型 | 推荐传输 |
| --- | --- |
| 小候选向量 | inline JSON |
| xlsx/csv/parquet | filesystem / S3 / MinIO ref |
| checkpoint/model | artifact ref |
| 大 numpy array | mmap / shared_memory / artifact ref |
| GPU tensor | DLPack / framework-native transport |
| 高频梯度同步 | NCCL / MPI / torch-ddp / JAX distributed |

数据库不适合高频共享内存或梯度同步。数据库适合状态、索引、审计和结果摘要。

## 6. ResourceRequirement / ResourceLease

任务声明需求：

```python
ResourceRequirement(
    threads=4,
    memory_mb=2048,
    gpus=1,
    capabilities=("torch_train",),
    timeout_seconds=600,
)
```

L0 匹配 worker 后发放 lease：

```text
ResourceRequirement
  -> WorkerDescriptor match
  -> ResourceAllocator
  -> ResourceLease
  -> ResourceContext
```

已有 `ResourceLease` / `ResourceAllocator` 仍是授权事实来源。新的 `core.resources` 只是把 task/worker/result 协议补齐。

## 7. WorkerDescriptor

worker 是执行单元，不是硬件本身。

```python
WorkerDescriptor(
    worker_id="local-thread-1",
    executor_backend="thread",
    resource_backend="local",
    capabilities=("nested_eval", "numpy"),
    offer={"threads": 4, "memory_mb": 2048},
    max_inflight=1,
)
```

多个服务器时，每台服务器可以启动一个或多个 worker：

```text
server-a
  worker-a1: cpu threads=8, memory=16GB
  worker-a2: gpu cuda:0, cpu threads=4, memory=8GB

server-b
  worker-b1: cpu threads=16, memory=32GB
```

L0 不直接调度“服务器”，而是调度 worker。服务器是 worker 的 host 属性。

## 8. ResultEnvelope

结果不应该只有 objectives。

```python
TaskResult(
    task_id="candidate_0007",
    status="ok",
    objectives=(-72333.7, 100.0, 117.0),
    violations=(0.0,),
    worker_id="worker-a1",
    lease_id="outer_eval_xxx",
    metrics={"runtime_seconds": 12.4},
    artifact_refs=(DataRef(uri="runs/out.xlsx", kind="report"),),
)
```

这样才能审计：

- 哪个 worker 跑的
- 用了哪个 lease
- 跑了多久
- 产物在哪里
- 是否超时/失败/重试

## 9. Scheduler 最小流程

```text
TaskEnvelope
  -> ResourceScheduler selects WorkerDescriptor
  -> ResourceAllocator acquires ResourceLease
  -> ExecutorBackend dispatches task
  -> Worker executes
  -> TaskResult returns
  -> ArtifactStore stores large outputs
  -> StateStore records status/audit
  -> ResourceScheduler releases lease
```

当前第一版实现：

- `core.resources.DataRef`
- `core.resources.ResourceRequirement`
- `core.resources.WorkerDescriptor`
- `core.resources.TaskEnvelope`
- `core.resources.TaskResult`
- `core.resources.TaskQueueBackend`
- `core.resources.TaskResultBackend`
- `core.resources.TaskStateBackend`
- `core.resources.ArtifactBackend`
- `core.resources.DataTransportBackend`
- `core.resources.WorkerRegistryBackend`
- `core.resources.InMemoryWorkerRegistry`
- `core.resources.InMemoryResourceScheduler`
- `core.resources.InMemoryL0RuntimeBackend`
- `core.resources.RedisL0RuntimeBackend`
- `core.resources.FilesystemArtifactBackend`
- `core.resources.InlineDataTransportBackend`
- `core.resources.ArtifactDataTransportBackend`

第一版 scheduler 是单进程实现，用来稳定协议。Redis 已经迁入 L0 runtime backend，负责 queue/result/state/worker heartbeat；Ray/K8s 后续应该实现同一套 task/worker/result/backend 协议，而不是复制业务逻辑。

## 10. nested 优化和 nested 计算资源

这两件事不同。

```text
nested optimization:
  outer solver -> inner solver

nested compute resources:
  parent task gets a lease
  child task / inner solver can only use part of that lease
```

例如：

```text
outer candidate evaluation
  lease: cpu_threads=4, memory=2GB
  inner production solver
    max threads <= 4
    memory <= 2GB
```

更复杂时，inner solver 可以继续提交 child tasks 给 L0，但必须携带 `parent_task_id`、`parent_lease_id` 和继承后的 `ResourceRequirement`。

## 11. nsgablack / mlblack 关系

`nsgablack` owns L0 orchestration plane：

- task scheduling
- worker registry
- resource lease
- queue/message backend
- state/artifact backend
- runtime audit

`mlblack` consumes L0 context：

- trainer / backend 接收 `ResourceContext`
- torch/tf/jax/sklearn 在授权 device/thread 内运行
- model/checkpoint/metrics 作为 artifact/result 返回

`mlblack` 不应该复制一套完整 L0。standalone 时可以使用 lightweight local context；嵌套到 `nsgablack` 时必须消费 parent L0 注入的 `ResourceContext`。

## 12. 禁区

- 不要让 solver 直接写死 `cuda:0`。
- 不要让 inner trainer 自己无限开线程。
- 不要把 Redis 当计算资源。
- 不要用数据库解决高频共享内存或连续梯度同步。
- 不要把大矩阵塞进 Redis task payload。
- 不要用 queue ack 代替 lease release。
- 不要在 case 文件里私搭一套资源调度。

## 13. 下一步

已完成：

- `NestedParallelEvaluator` 内部生成并消费 `TaskEnvelope` / `TaskResult`。
- `RedisNestedDistributedEvaluator` 通过 `RedisL0RuntimeBackend` 提交 `TaskEnvelope`，收集 `TaskResult`。
- Redis worker runner 直接接收 `TaskEnvelope`，case runner 返回 `TaskResult`。
- 旧的 nested Redis task/result wrapper 已移除，不再维护第二套协议。
- Redis queue/result/state/heartbeat 已从 nested 私有实现迁到 `core.resources` L0 backend。
- GPU/VRAM 已进入 `ResourceRequirement` 和 `WorkerDescriptor.offer` 的显式检查路径。

后续继续：

1. 把 supply_adjustment_nested 的 outer/inner worker 参数改成 `ResourceRequirement`。
2. 在 runtime summary 中输出 worker、lease、resource_context 和 artifact refs。
3. 让 queue/result backend 支持任务重试、失败分类和 result artifact refs。
4. 增加 Redis worker registry 的 list/scan 查询和过期 worker 清理。
5. 增加 Ray/K8s backend adapter，但继续消费同一套 L0 协议。
