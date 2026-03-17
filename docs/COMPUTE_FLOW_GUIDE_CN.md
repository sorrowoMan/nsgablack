# 计算流使用说明（L0 执行能力）

本页说明如何在框架中使用 L0 计算后端（同步/异步、CPU/GPU）以及推荐的使用方式。

## 1. L0 的定位

- L0 只负责“执行与调度”，不负责业务语义。
- 业务语义（约束/快照/计数/偏置）仍由上层完成。
- CPU/GPU 都通过“后端”实现，上层调用方式一致。

## 2. 同步与异步的区别

- 同步：`run` / `map`，调用即阻塞，返回 `ExecutionResult`。
- 异步：`submit` / `map_async`，调用立即返回 `AsyncHandle`，由调用方决定何时等待。

## 3. 结果协议（统一）

所有 L0 调用返回或最终解析成 `ExecutionResult`：

- `ok`: 是否成功  
- `data`: 计算结果  
- `error`: 错误信息（失败时）  
- `backend`: 实际后端名称  
- `latency_ms`: 执行耗时  
- `trace_id`: 可观测链路标识  
- `metrics`: 额外指标  

## 4. 失败语义

通过 `hints.failure_policy` 控制：

- `strict`：失败直接抛异常  
- `soft`：失败返回 `ExecutionResult(ok=False, error=...)`  

## 5. 注册后端（示例：CPU 线程池）

```python
from nsgablack.core import ThreadPoolBackend

solver.register_acceleration_backend(
    scope="evaluation",
    backend="thread",
    factory=lambda: ThreadPoolBackend(max_workers=8),
)
```

## 6. 手动调用（同步）

```python
result = solver.accel_map(
    scope="evaluation",
    task="map",
    items=population,
    call=lambda x: solver.problem.evaluate(x),
    backend="thread",
    hints={"failure_policy": "strict"},
)
objectives = result.data
```

## 7. 手动调用（异步）

```python
handle = solver.accel_map_async(
    scope="evaluation",
    task="map",
    items=population,
    call=lambda x: solver.problem.evaluate(x),
    backend="thread",
)
result = handle.result(timeout=5.0)
```

## 8. GPU 后端（说明）

GPU 后端不会自动加速任意函数。  
你的 callable 必须自行实现 GPU 逻辑（例如 torch/cupy）。

注册方式：

```python
from nsgablack.core import GpuBackend

solver.register_acceleration_backend(
    scope="evaluation",
    backend="gpu",
    factory=lambda: GpuBackend(preferred_backend="auto", device="cuda:0"),
)
```

调用方式（批量 GPU 评估）：

```python
result = solver.accel_run(
    scope="evaluation",
    task="run",
    payload={
        "callable": solver.problem.evaluate_gpu_batch,
        "args": (population,),
        "kwargs": {"backend": "torch", "device": "cuda:0"},
    },
    backend="gpu",
)
objectives = result.data
```

## 9. 统一 helper（可选）

如果你不想每次判断是否有后端，可用：

```python
from nsgablack.core import maybe_accel_map

result = maybe_accel_map(
    solver=solver,
    scope="evaluation",
    task="map",
    items=population,
    call=lambda x: solver.problem.evaluate(x),
    backend=None,  # None 表示走本地
)
```

## 10. 推荐实践

- 只在“批量+向量化”的计算上优先使用 GPU  
- 阶段内可并行，阶段间仍保持顺序  
- 评估/快照/计数语义仍由上层控制  
