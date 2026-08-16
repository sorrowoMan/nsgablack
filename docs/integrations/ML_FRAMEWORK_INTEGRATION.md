# ML / Surrogate Integration

本页说明 `nsgablack` 如何与 ML 能力集成。当前口径是统一框架栈：

- `nsgablack` 是优化搜索语义层。
- `mlblack` 是机器学习语义层。
- Project / Case / Scaffold / L0 / ResourceContext / Artifact ref 属于共享 substrate。
- 编排与资源授权不属于任一语义层的私有能力。

因此，ML 集成不应写成“nsgablack 私有插件里直接训练模型”的路线。正式路线是：ML trainer、surrogate evaluator、artifact builder 都暴露为标准 Case surface，外层通过 payload、artifact ref、component_overrides 和 ResourceContext 调用。

## 1. 推荐形态

### 外层优化调用内层 ML Case

适用场景：

- 外层搜索模型结构、特征组合、训练超参或 surrogate 选择。
- 内层训练/评估由 `mlblack` Trainer Case 完成。
- 外层只关心稳定 result payload，不读取 trainer 私有对象。

标准流：

```text
Project L0 grant
  -> outer optimization Case
      -> Problem.evaluate(candidate)
          -> decode component_overrides
          -> call inner ML Case build_solver/build_trainer alias
          -> receive metrics/artifact refs/result
      -> project objective / constraint projection
```

### ML 作为评估代理

适用场景：

- expensive simulator / true evaluator 太慢。
- ML surrogate 可以短路一部分评估。

要求：

- surrogate 的训练数据、模型 artifact、校准结果写入 Artifact 或 Snapshot。
- 短路评估必须返回与真实评估相同 shape 的 objective / violation payload。
- nsgablack Plugin 可以负责缓存、审计、短路 hook，但不要拥有 trainer 业务逻辑。

## 2. 与第三方 ML 工具集成

PyTorch、TensorFlow、sklearn、statsmodels、Optuna、Ray Tune 等工具应作为 ML Case 内部的 provider/backend 使用：

- provider/backend 选择写在 inner Case config 或 component_overrides 中。
- Project L0 发放 CPU/GPU/thread/device token。
- inner Case 根据 ResourceContext 选择实际执行 backend，并输出 audit。
- outer Case 不硬编码 `cuda:0`、trainer 类路径或 provider 私有参数。

## 3. nsgablack 插件仍然适合做什么

插件适合做横切能力：

- evaluation cache
- decision trace
- benchmark / module report
- artifact ref 记录
- timeout / budget gate
- surrogate short-circuit audit

插件不适合做：

- 直接实现完整 trainer。
- 私下分配 GPU 或 worker。
- 解析内层 trainer 私有对象。
- 承担跨 Case 编排。

## 4. 参考入口

- `../standard_scaffold_tutorial/05_cross_framework_coordination.md`
- `../standard_scaffold_tutorial/07_nested_orchestration_standard.md`
- `../standard_scaffold_tutorial/06_l0_parallel_resource_patterns.md`
- `../user_guide/SURROGATE_CAPABILITY_PATTERN.md`
- `../architecture/L0_RESOURCE_ORCHESTRATION.md`

