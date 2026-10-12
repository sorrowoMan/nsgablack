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

对每种可加资源（例如线程、内存）分别计算峰值：同时活跃的需求求和；串行阶段取峰值，不能把不同资源维度相加。设备 token、服务许可等离散资源还须满足各自的授权约束。

如果外层 case 在评估阶段触发内层 case：

```text
peak[d] = outer_active_requirement[d] + sum(active_child[i].requirement[d])
homogeneous_bound[d] = outer_active_requirement[d] + N * max(child_requirement[d])
```

其中 N 是同时活跃的子调用上限。只有外层每 worker 同时占用一个线程、共 N 个 worker 且所有子调用线程需求相同时，线程维度才简化为 `N + N * inner_threads`。父任务等待期间是否仍占用资源必须明确，不能默认释放。异构子任务按实际需求求和；未知动态需求须声明上界或接受运行时 admission 检查。

上述公式用于容量估算。实际授权由 BlackBase Project L0 的 `ResourceGrantPool` 在父 `ResourceContext` 范围内逐请求检查、发放和释放，Case 不得自行扩大 grant。

## 5. 内层 case 识别

外层通过 Project 注入的 `CaseRuntimeContext.invoke()` 调用已注册的内层标准 Case，传递请求、输入和 Artifact/Snapshot 引用。调用路径统一取得子请求并申请父授权内的 grant；直接调用内层 builder 不能替代这一编排入口。

内层 Case 在 project stage 或 case config 中声明 `resource_request`。`build_solver(..., resource_context=...)` 消费已授予的上下文，不拥有全局资源分配权。

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
