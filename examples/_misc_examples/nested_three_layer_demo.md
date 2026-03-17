# Three-Layer Nested Demo / 三层嵌套示例

示例文件：`examples/nested_three_layer_demo.py`

## 目标
演示以下链路：
- L1 调 L2
- L2 再调 L3
- `ContractBridgePlugin` 将 L3 字段直接写回 L1 context

## 运行
```powershell
python examples/nested_three_layer_demo.py
```

## 关键模块
- `problem.inner_runtime_evaluator`：在外层评估阶段触发内层流程。
- `ContractBridgePlugin`：把 `l3_root/l3_residual/...` 映射到 L1。
- `TimeoutBudgetPlugin`：限制内层调用预算。
- `NewtonSolverProviderPlugin`（示例中以内联数值求解函数体现同类能力）：处理 L3 残差方程。

## 预期输出
- `best_objective`
- `L1 bridged fields`
- `bridge_records`

这说明“外层只消费评估结果，但能拿到内层关键信号”，实现深度打通。
