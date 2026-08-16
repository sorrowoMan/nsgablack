# Case 编排与资源契约（规范）

本规范定义“多 case 编排”的最小契约与资源计算规则，避免架构侵入与资源超载。solver 和 trainer 是同一抽象层级的 Case；编排属于 Project / Case / L0 substrate。

## 1. 适用范围

- 多 solver / 多 trainer / 混合 case 编排（并行/串行）
- 与嵌套 case 并存
- Project runner 只做调度、资源授权与结果汇总，不做策略

## 2. 角色语义

### Case 编排

- 目的：管理多套标准 case 并行或串行运行
- 行为：调度、资源校验、结果汇总
- 不做：策略逻辑、评估接管

### 嵌套评估

- 目的：外层 case 评估调用内层 case
- 语义：评估实现方式（problem-side inner call / L4 provider）
- 不绕过标准 `build_solver()` 入口

## 3. 资源声明

Project L0 读取资源声明，不干预 case 内部实现。

```python
ResourceRequest(threads=4, device_tokens=(), services=(), backend="local")
```

Project 提供资源上限：

```python
ResourceOffer(
    threads=8,
    device_tokens=("logical-gpu-a",),
    services=("copt-license",),
    backend="local",
)
```

硬约束规则：

- 超预算直接报错
- 不静默降级
- 不让 case 私下抢全局资源

## 4. 资源计算规则

并行 stage 的资源需求求和，串行 stage 不叠加。

如果外层 case 在评估阶段触发内层 case：

```text
total = outer_parallel_workers + outer_parallel_workers * inner_requirement
```

这是上界估算；实际实现应由 Project L0 根据 `ResourceContext` 和 lease store 发放 grant。

## 5. 内层 case 识别

推荐方式：

1. 外层 `Problem.evaluate()` 显式调用 `cases.<inner>.build_solver`
2. `problem.inner_runtime_evaluator`
3. `problem.build_inner_solver(...)` 兼容入口

建议内层 case 在 project stage 或 case config 中声明 `resource_request`，以便精确计算。

## 6. 默认行为

- 单 case：由 `run_project.py` 发放 ResourceContext 后运行
- 多 case：由 Project runner 按 stage/group 调度
- Project runner 只做调度、资源授权、结果汇总

## 7. 设计原则

- 编排属于 substrate
- nsgablack 提供优化搜索语义
- mlblack 提供机器学习语义
- case 不拥有全局 lease
- adapter/plugin 只表达局部 intent
