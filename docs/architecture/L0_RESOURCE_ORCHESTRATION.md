# L0 Resource Orchestration

本文说明 `nsgablack` / `mlblack` 中 L0 资源层的职责边界、对象协议和 GPU lease 机制。L0 不是算法层，也不是业务目标层；它只回答一个问题：一次求解或一次内层评估到底被允许使用哪些计算资源。

## 1. 为什么需要 L0

CPU thread 和 GPU 的资源语义不同。CPU 线程通常可以自动估算，也允许一定程度的超卖；GPU 则更接近稀缺设备，尤其是 CUDA 设备和显存。如果外层 `nsgablack` 同时启动 10 个 inner evaluation，而每个 inner 都私下使用 `cuda:0`，轻则互相抢占导致性能不稳定，重则 OOM 或 CUDA context 冲突。

因此，L0 的设计不应该是简单的 `if cuda:0 used then warn`，而应该是：

```text
ResourceRequest
  -> ResourceAllocator
  -> ResourceLease
  -> JSON-compatible ResourceContext
  -> inner trainer / pipeline / provider
  -> ResourceAudit / report
```

报警只是 `strict / warn / shared / queue` 等策略的一种结果，不是 L0 本体。

## 2. 两个框架的边界

| 框架 | L0 职责 |
| --- | --- |
| `mlblack` | 单次训练/评估内部资源上下文，负责消费 `ResourceContext`，并在 trainer/pipeline/provider 中按授权使用 CPU/GPU |
| `nsgablack` | 外层多候选、多 inner evaluation 的资源调度，负责发放 `ResourceLease` 并把 JSON `ResourceContext` 注入 inner |

`mlblack` 必须能 standalone 使用 L0，不依赖 `nsgablack`。当二者嵌套时，`nsgablack` 是 parent allocator，`mlblack` 只消费被注入的授权上下文。

```text
standalone mlblack:
  mlblack LocalResourceAllocator
  -> ResourceLease
  -> ResourceContext

nested nsgablack -> mlblack:
  nsgablack ResourceAllocator
  -> ResourceLease
  -> JSON ResourceContext
  -> mlblack build_flow(..., resource_context=...)
```

## 3. 标准对象

| 对象 | 作用 |
| --- | --- |
| `ResourceOffer` | 当前 runtime 能提供的资源，例如 threads、device_tokens |
| `ResourceRequest` | 某个 solver/evaluation 申请的资源，例如 threads=2、gpus=1 |
| `ResourcePolicy` | 资源策略，例如 `exclusive/shared`、`strict/warn` |
| `ResourceAllocator` | 根据 offer、request、policy 发放 lease |
| `ResourceLease` | 实际授权结果，含 `lease_id`、`owner_id`、device、threads |
| `ResourceContext` | 传给 inner 框架的 JSON-compatible 执行上下文 |
| `LeaseStore` | 保存 active leases，决定是否能跨进程互斥 |

`gpus: int` 仍然保留为兼容字段，但正式调度应优先看 `device_tokens` 和 `lease`。

## 4. CPU 与 GPU 策略

| 资源 | 默认建议 | 原因 |
| --- | --- | --- |
| CPU threads | `auto` 或 clamp | CPU 可以共享，轻度超卖通常可接受 |
| GPU device | `exclusive` | 单卡训练默认不应被多个 inner 抢占 |
| GPU memory | shared 时显式声明 | 显存是主要 OOM 来源 |
| Process/Ray | 必须使用共享 lease store | 进程内 dict 无法跨进程互斥 |

推荐默认：

```python
ResourcePolicy(mode="strict", gpu_sharing="exclusive")
```

如果确实要共享 GPU：

```python
ResourcePolicy(
    mode="strict",
    gpu_sharing="shared",
    max_jobs_per_gpu=2,
    gpu_memory_fraction=0.45,
)
```

## 5. Lease Store

### InMemoryLeaseStore

`InMemoryLeaseStore` 是默认后端，只适用于单 Python 进程。

适用：

- serial backend
- thread backend
- 单进程本地调试

不适用：

- process pool
- Ray
- 多个 Python 进程同时跑 outer evaluation

### SQLiteLeaseStore

`SQLiteLeaseStore` 用 SQLite 的 `BEGIN IMMEDIATE` 做本机跨进程互斥，适合 process backend 或多个本地 Python 进程共享 GPU。

```python
from nsgablack.core import (
    ResourceAllocator,
    ResourceOffer,
    ResourcePolicy,
    ResourceRequest,
    SQLiteLeaseStore,
)

allocator = ResourceAllocator(
    offer=ResourceOffer(
        threads=8,
        backend="local",
        device_tokens=("cuda:0", "cuda:1"),
    ),
    policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
    lease_store=SQLiteLeaseStore("runs/resource_leases.sqlite3"),
)

lease = allocator.acquire(
    ResourceRequest(threads=2, backend="local", gpus=1),
    owner_id="trial_0007",
    scope="outer_eval",
)

resource_context = lease.resource_context(
    compute_backend="torch",
    device="auto",
    execution_backend="thread",
    namespace="nsgablack.trial_0007",
)
```

这个 `resource_context` 是普通 dict，可以直接传给 `mlblack build_flow()` 或 case runner。

```python
flow = build_flow(cfg, resource_context=resource_context)
result = flow.fit(data)
```

完成后必须释放：

```python
allocator.release(lease)
```

### RedisLeaseStore

Redis 更适合 Ray/分布式多机，但当前主干优先提供 `SQLiteLeaseStore`，因为它无额外服务依赖，足够解决本机多进程 GPU 抢占。后续如果引入 Redis，语义应保持一致：

```text
acquire(lease) -> atomic conflict check + write
release(lease_id) -> mark inactive / delete key
active_leases() -> audit/debug
```

## 6. TTL / Heartbeat

仅有 `release()` 不能覆盖异常退出场景。如果某个 Python 进程在拿到 GPU lease 后崩溃，进程没有机会调用 `allocator.release(lease)`，SQLite 中就会留下 `released_at IS NULL` 的 stale lease。TTL/heartbeat 的作用是给 lease 增加“活性证明”：

```text
ResourcePolicy(lease_ttl_seconds=300, heartbeat_interval_seconds=30)
  -> ResourceLease(ttl_seconds=300, last_heartbeat_at=...)
  -> heartbeat(lease_id) refreshes last_heartbeat_at
  -> active_leases()/acquire()/prune_expired() expires stale lease
```

默认情况下 TTL 是关闭的，即 `lease_ttl_seconds=None`，这样不会改变旧任务语义。需要处理异常退出时，应显式打开：

```python
allocator = ResourceAllocator(
    offer=ResourceOffer(threads=8, backend="local", device_tokens=("cuda:0",)),
    policy=ResourcePolicy(
        mode="strict",
        gpu_sharing="exclusive",
        lease_ttl_seconds=300.0,
        heartbeat_interval_seconds=30.0,
    ),
    lease_store=SQLiteLeaseStore("runs/resource_l0.sqlite3"),
)

lease = allocator.acquire(ResourceRequest(threads=2, gpus=1), owner_id="trial_0007")

# 长任务应周期性调用，通常由 runner / worker wrapper 做，而不是 trainer 私下做。
allocator.heartbeat(lease)
```

`active_leases()`、`acquire()` 和 `prune_expired()` 都会先清理过期 lease。过期判断只看 `last_heartbeat_at + ttl_seconds`，不依赖消息队列。因此，即使事件队列不可用，lease store 仍然能释放 stale GPU 授权。

事件口径：

| 事件 | 触发时机 |
| --- | --- |
| `resource.lease.heartbeat` | 心跳刷新成功 |
| `resource.lease.expired` | stale lease 被 TTL 清理 |
| `resource.lease.released` | 正常 release |

实践建议：

- `lease_ttl_seconds` 应明显大于一次正常 heartbeat 间隔，例如 heartbeat=30s、ttl=300s。
- heartbeat 应由外层 evaluation wrapper、process worker 或 runner 控制，不应散落进业务 trainer。
- 如果任务可能长时间阻塞在 CUDA kernel 或数据加载阶段，TTL 不要设得过短。
- TTL 解决异常退出后的 stale lease，不解决显存碎片、CUDA runtime 泄漏或驱动级残留进程；这些仍需要运行时清理。

## 7. MessageQueue / Event Backend

消息队列可以接入，但它不是 lease 的真相来源。正确分层是：

| 层 | 职责 | 是否决定资源互斥 |
| --- | --- | --- |
| `LeaseStore` | 原子检查 active leases，并写入/释放 lease | 是 |
| `MessageQueue` | 发布 acquire/release/conflict 等资源事件 | 否 |
| `ContextStore` / `SnapshotStore` | 保存运行上下文、审计引用、报告材料 | 否 |

因此，`SQLiteMessageQueue` 解决的是“多个进程或后端如何感知资源事件”，不是“如何锁住 GPU”。GPU 是否可用仍然由 `SQLiteLeaseStore` 的事务检查决定。队列事件被 ack 掉，也不会释放 lease；释放必须调用 `allocator.release(lease)` 或 `lease_store.release(lease_id)`。

当前提供两个轻量后端：

- `InMemoryMessageQueue`：单进程内事件通知，适合 thread/serial 调试。
- `SQLiteMessageQueue`：本机多进程事件通知，可与 `SQLiteLeaseStore` 共用同一个 SQLite 文件。

示例：

```python
from nsgablack.core import SQLiteLeaseStore, SQLiteMessageQueue

queue = SQLiteMessageQueue("runs/resource_l0.sqlite3")
lease_store = SQLiteLeaseStore(
    "runs/resource_l0.sqlite3",
    message_queue=queue,
)

allocator = ResourceAllocator(
    offer=ResourceOffer(threads=8, backend="local", device_tokens=("cuda:0",)),
    policy=ResourcePolicy(mode="strict", gpu_sharing="exclusive"),
    lease_store=lease_store,
)

lease = allocator.acquire(ResourceRequest(threads=2, gpus=1), owner_id="trial_0007")
events = queue.peek(limit=10)
allocator.release(lease)
```

默认情况下，事件发布是 soft-fail：队列写入失败不应破坏已经完成的 lease 事务。如果某个生产环境要求“审计事件必须写入成功”，可以在 lease store 上打开 `queue_strict=True`，让事件后端失败直接暴露出来。

后续如果引入 Redis 或消息队列系统，应保持同样边界：Redis/SQLite 作为 `LeaseStore` 时负责互斥；Kafka/RabbitMQ/Redis Stream 作为 `MessageQueue` 时只负责事件广播、worker 唤醒、heartbeat 观测或异步审计。它们可以接入 context/snapshot 体系，但不能替代 active lease 表。

## 8. 跨框架注入格式

`nsgablack` 发放的 `ResourceLease` 会生成 JSON-compatible `ResourceContext`：

```json
{
  "scope": "outer_eval",
  "execution_backend": "thread",
  "compute_backend": "torch",
  "device": "cuda:0",
  "threads": 2,
  "nested": true,
  "namespace": "nsgablack.trial_0007",
  "grant": {
    "phase": "outer_eval",
    "threads": 2,
    "backend": "thread",
    "label": "outer_eval_xxx",
    "request_label": "trial_0007",
    "device_tokens": ["cuda:0"],
    "metadata": {
      "parent_scope": "nsgablack_outer"
    }
  },
  "lease": {
    "lease_id": "outer_eval_xxx",
    "owner_id": "trial_0007",
    "device_tokens": ["cuda:0"],
    "policy": {
      "mode": "strict",
      "gpu_sharing": "exclusive",
      "lease_ttl_seconds": 300.0,
      "heartbeat_interval_seconds": 30.0
    },
    "ttl_seconds": 300.0,
    "heartbeat_interval_seconds": 30.0,
    "last_heartbeat_at": 1710000000.0
  }
}
```

`mlblack` 收到后应只使用 `ResourceContext` 中的 device/thread。如果 inner trainer 请求 `cuda:1`，但 parent grant 是 `cuda:0`，`mlblack` 应 clamp 到 `cuda:0` 或在 strict 模式下失败。

## 9. 设计禁区

- 不要在 example 里直接写死 `cuda:0`。
- 不要让每个 inner eval 自己猜 GPU。
- 不要把资源调度塞进 trainer。
- 不要把 process/Ray 资源互斥建立在进程内 dict 上。
- 不要把 `gpus: 1` 当作完整资源授权；它只是抽象请求，必须落到具体 `device_tokens`。
- 不要用 message queue ack 代替 `release()` 或 TTL 过期。
- 不要把 heartbeat 写进业务模型内部；它应该属于 runner/worker 的资源生命周期。

## 10. 当前实现状态

已实现：

- `nsgablack.core.solver_manager.ResourceRequest`
- `ResourceOffer`
- `ResourcePolicy`
- `ResourceLease`
- `ResourceAllocator`
- `InMemoryLeaseStore`
- `SQLiteLeaseStore`
- `InMemoryMessageQueue`
- `SQLiteMessageQueue`
- `ResourceAllocator.heartbeat(...)`
- `ResourceAllocator.prune_expired(...)`
- `ResourceLease.resource_context(...)`

已接入：

- `learnable_conv_component_search`
- `symbolic_kernel_digits_outer_search`

仍需后续完善：

- Redis/Ray 分布式 lease store
- Redis Stream / Kafka / RabbitMQ 等分布式 message queue 后端
- 资源感知调度目标，例如 maximize throughput、minimize OOM risk、minimize idle GPU time
- Run Inspector 中展示 active leases / resource audit
