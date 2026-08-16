# 并行评估指南

并行评估属于共享 L0 substrate 的执行能力，不属于某个 Solver、Adapter 或示例脚本的私有能力。

当前推荐口径：

- Project 声明可用 CPU/thread/GPU/worker/service backend。
- Case 声明评估需求。
- `run_project.py` 发放 `ResourceContext`。
- Case 内的 solver/plugin/wiring 只消费生效 grant，并在报告中写出实际 backend 与 fallback。

## 1. Project 声明资源

```python
L0 = {
    "backend": "local",
    "resource_pool": {
        "threads": 16,
        "device_tokens": ("logical-gpu-a",),
    },
    "policy": {
        "failure_policy": "soft",
    },
}

resource_requests = {
    "main_case": {"threads": 4},
}
```

不要在 Case 代码里硬编码 `cuda:0`、全局线程池或本机 worker 名称。

## 2. Case 消费 grant

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = make_solver(config)

    runtime = build_runtime_from_context(resource_context)
    attach_parallel_evaluation(
        solver,
        backend=runtime.evaluation_backend,
        max_workers=runtime.max_workers,
        audit=runtime.audit_payload(),
    )

    return solver
```

Case 可以选择 thread/process/Ray/remote backend，但选择依据必须来自 `resource_context` 和本地 runtime profile。若 fallback 到串行评估，必须写入 run summary 或 module report。

## 3. 单 Case 调试

独立调试时可以直接使用本地 evaluator：

```python
from nsgablack.utils.parallel import ParallelEvaluator

with ParallelEvaluator(backend="process", max_workers=4) as evaluator:
    objectives, violations = evaluator.evaluate_population(population, problem)
```

这只是调试路径。正式运行仍应从 Project L0 grant 进入。

## 4. 推荐实践

- 评估函数保持可序列化、无副作用。
- 大 payload 走 Snapshot 或 Artifact ref，不塞进 Context。
- 并行失败策略由 Project 给默认值，Case 可以局部降级但必须审计。
- 嵌套 Case 不能扩大 parent grant，只能使用 parent 派生的 child grant。
- `framework-core` 架构审计时使用 `python -m nsgablack catalog ... --profile framework-core`。

## 5. 相关入口

- `COMPUTE_FLOW_GUIDE_CN.md`
- `../standard_scaffold_tutorial/06_l0_parallel_resource_patterns.md`
- `../architecture/L0_RESOURCE_ORCHESTRATION.md`
- `../architecture/L0_TASK_RESOURCE_BACKEND_ARCHITECTURE.md`

