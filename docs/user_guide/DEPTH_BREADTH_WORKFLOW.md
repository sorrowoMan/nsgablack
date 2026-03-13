# Depth × Breadth Workflow / 深度 × 广度工作流

这份说明聚焦一个核心：NSGABlack 如何同时打通“深度嵌套”和“广度协同”。

## 1) 深度（Depth）：层级嵌套
- L1：外层优化（问题主目标、主约束）。
- L2：内层评估流程（可有自己的求解逻辑）。
- L3：更内层数值求解（隐式方程/残差求根）。

实现路径：
- `InnerSolverPlugin`：L1 在 `evaluate_individual` 调 L2/L3。
- `ContractBridgePlugin`：把内层结果桥接回外层 context。
- `TimeoutBudgetPlugin`：限制内层调用预算，避免失控。
- `NewtonSolverPlugin/BroydenSolverPlugin`：作为 L3 求解工具。

## 2) 广度（Breadth）：多策略协同
- 同层并行角色（explorer / exploiter）。
- 同层多 Adapter 协作（multi-strategy）。
- 同层多 Bias 组合（业务偏好 + 算法偏好）。
- 同层插件组合（缓存/容错/报告/审计）。

实现路径：
- `MultiStrategyControllerAdapter` + role adapters
- BiasModule 组合
- Plugin wiring helpers/capability plugins

## 3) 一条闭环工作流
1. 脚手架：`project init`
2. 组件开发：problem/pipeline/bias/adapter/plugin
3. 注册：Catalog entry（可由 UI Add Entry）
4. 装配：`build_solver()`
5. 运行：solver run
6. 审计：Run Inspector + doctor strict
7. 迭代：按契约和指标回改组件

## 4) 示例
- 三层嵌套示例：`examples/nested_three_layer_demo.py`
  - L1 调 L2，L2 调 L3，bridge 直写回 L1。

## 5) 设计边界
- `plugins/evaluation`：评估工具（包括数值求解）。
- `plugins/solver_backends`：跨层编排与桥接。
- Adapter 一等公民：搜索流程逻辑在 Adapter，不把 process-like 算法塞进 bias。
