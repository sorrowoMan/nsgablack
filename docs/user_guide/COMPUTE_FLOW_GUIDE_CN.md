# 计算流使用说明：Project L0 与 Case 执行能力

本页说明如何使用 L0 计算能力。L0 是共享 substrate 的一部分，不属于某个语义层的私有能力。

## 1. 定位

- Project L0 声明资源池、服务后端和全局策略。
- Case 声明资源需求，并在运行时接收 `ResourceContext`。
- Solver、Adapter、Trainer、Plugin 只能使用生效后的上下文。
- 业务语义仍由 Problem、Pipeline、Trainer、Head、Artifact 等上层组件表达。

## 2. 同步与异步

L0 执行可以是同步或异步：

- 同步：`run` / `map`，调用者等待 `ExecutionResult`。
- 异步：`submit` / `map_async`，调用者得到 handle 后再等待结果。

不管哪种形式，结果都应归一到可审计 payload：

- `ok`
- `data`
- `error`
- `backend`
- `latency_ms`
- `trace_id`
- `metrics`
- `resource_context`

## 3. Project 声明资源

```python
L0 = {
    "backend": "local",
    "resource_pool": {
        "threads": 16,
        "device_tokens": ("logical-gpu-a", "logical-gpu-b"),
    },
    "policy": {
        "device_sharing": "exclusive",
        "failure_policy": "soft",
    },
}

resource_requests = {
    "outer_search": {"threads": 4},
    "inner_learning": {"threads": 4, "device_tokens": ("logical-gpu-a",)},
}
```

这里的 device token 是 Project 里的逻辑名称。它可以映射到本机 GPU、远程 worker、容器资源或测试替身。Case 不应直接写机器本地设备字符串。

## 4. Case 消费资源

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = make_solver(config)
    runtime = build_runtime_from_context(resource_context)
    attach_execution_backend(solver, runtime)
    attach_resource_audit(solver, runtime)
    return solver
```

Case 可以根据 `resource_context` 决定使用线程池、GPU evaluator 或远程 executor。它必须记录实际选择和 fallback。

## 5. 批量评估

```python
result = solver.accel_map(
    scope="evaluation",
    task="map",
    items=population,
    call=lambda x: solver.problem.evaluate(x),
    backend=runtime.evaluation_backend,
    hints={
        "failure_policy": runtime.failure_policy,
        "resource_context": runtime.as_payload(),
    },
)
objectives = result.data
```

## 6. GPU 后端

GPU 后端不会自动加速任意函数。被调用函数必须自己实现向量化或框架侧逻辑。

推荐写法：

```python
device = runtime.get_device_token()

result = solver.accel_run(
    scope="evaluation",
    task="run",
    payload={
        "callable": solver.problem.evaluate_batch_on_device,
        "args": (population,),
        "kwargs": {"device_token": device},
    },
    backend=runtime.evaluation_backend,
)
```

`device_token` 来自 Project grant，不在 Case 中硬编码。

## 7. 失败策略

Project 可以声明默认失败策略，Case 可以在自身报告中说明是否覆盖：

- `strict`：失败即中止。
- `soft`：返回失败结果并给外层投影成 penalty 或 fallback。

嵌套运行时，inner Case 不能扩大自己的资源范围，只能在 grant 内降级或失败。

## 8. 推荐实践

- 资源池只在 Project 层声明。
- Case 中只写需求、消费和审计。
- 大数据走 Snapshot 或 Artifact ref，不进入 `Context`。
- 外层只看标准结果 payload，不读取内层 backend 细节。
- 每次正式运行都输出 effective `ResourceContext`。
