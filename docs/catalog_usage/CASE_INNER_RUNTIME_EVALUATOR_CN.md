# 完整内层 Case 的 Catalog 用法

## tool.case_inner_runtime_evaluator

`CaseInnerRuntimeEvaluator` 将外层候选交给一个完整标准 Case，再把它的正式结果投影为外层反馈。这里直接使用现有供应调整 Project，不另建求解循环或复制脚手架。本卡是源码与装配说明；本轮未执行生产算例，不构成运行收据。

### 输入与前提

- 保留完整 `examples/cases/supply_adjustment_nested/` Project。`project_config.py` 声明阶段、L0、共享预算和 Artifact 权威，`run_project.py` 是正式运行入口。
- 外层 Case 位于 `cases/supply_adjustment_nested/`，内层 Case 位于 `cases/production_inner/`，两边都保留标准目录与 canonical `build_solver.py`。可直接核对外层 [装配入口](../../examples/cases/supply_adjustment_nested/cases/supply_adjustment_nested/build_solver.py)、[运行入口](../../examples/cases/supply_adjustment_nested/cases/supply_adjustment_nested/run_solver.py) 与内层 [装配入口](../../examples/cases/supply_adjustment_nested/cases/production_inner/build_solver.py)。内层必须由父请求提供版本化 `task`，不能在缺少 task 时直接运行来证明嵌套可用。
- 安装当前 nsgablack、blackbase 与 NumPy，并准备原生产 Case 的 BOM、SUPPLY 文件和生产代码。缺少输入时加载器明确失败；不能用随机数据、供应总量或代理评分代替生产排程。
- 默认沿既有生产数据加载配置运行。需要换数据时，在 Project 对应阶段的 `component_overrides["supply_adjustment_nested"]["argv"]` 显式加入外层实际支持的 `--bom`、`--supply` 参数，保留阶段原有参数和预算；不要把 Case 参数直接当成 Project CLI 参数。

### 接入步骤

1. 外层 `build_solver.py` 转交 `solver/assembly.py`，以同一个正式 ResourceContext 装配 Problem、Pipeline、NSGA-II 与联合结果交付。问题管线先修复供应候选。
2. `solver/assembly.py` 调用 `evaluation/production_case.py` 的 `build_production_evaluator(problem, *, data, timeout_seconds, max_workers=1, portable_inputs=False)`，并把返回对象绑定到 `problem.inner_runtime_evaluator`。Catalog 同时展示该真实 factory 的完整源码片段；其中 `problem` 和 `data` 来自外层装配，不是未定义的全局依赖。
3. Factory 指定 `case_name="production_inner"`。`ProductionCaseProjection.task_for` 把本候选 token、修复后的供应方案、源摘要和内层预算组成正式任务；`project` 验证子 Case 的 `production_summary` 发布收据、候选身份、排程可行性和已结算预算，再形成外层三目标。
4. Project runtime 为每个子调用发放独立身份、派生资源授权、预算和取消契约。`max_workers` 请求同批并发，不能自行创建全局授权；本例默认本机配置不能因此宣称跨机并发已生效。
5. 先从仓库根目录检查完整 Project，再在输入齐全时运行已有 baseline 组：

```powershell
python examples/cases/supply_adjustment_nested/run_project.py --check --build-check
python examples/cases/supply_adjustment_nested/run_project.py --group baseline
```

检查命令只证明它实际检查的声明或装配；第二条才执行真实内层求解，有生产数据和计算成本要求。本卡与 Catalog 索引构建不会自动执行这两条命令。

### 依赖与边界

- `production_inner` 使用原生产 Case 的 canonical builder，执行原 phased MOEA/D + VNS；Evaluator 不重造算法，不把内层结果的分数冒充外层候选身份。
- 默认本机路径不要求 Redis 或外部 Worker。需要可搬运输入时使用原 Project 的 `portable` 组及正式 ArtifactBinding；需要外部派发时另配置 Project `L0.nested_execution`，不能把协调端绝对路径或 Pool/Unit 活对象直接交给远端。
- Artifact 输入名映射、每子请求资源与预算、超时和终止策略均由该 factory 显式声明。子 Case 失败、摘要不匹配或预算结算异常须传播；不能降级成成功评分。

### 预期结果

- 外层原始目标是 `[-真实排程总产量, 移动事件数, 总提前天数]`，来自验证后的生产排程，不是供应量近似。
- 子 Case 发布 `production_summary`；外层 `JointSupplyCase` 从精确 accepted 版本交付 `joint_summary`，保留 SolutionRef、candidate token、源摘要、子 Case 身份、Artifact 收据与预算结算。不按相同数值或行号猜对应关系。
- 本卡没有新增执行收据；Catalog 应显示源检查状态。实际运行与跨机验收须另核对应命令、发布摘要、真实计数和来源身份。

目录、输入和既有运行配置见 [Project 说明](../../examples/cases/supply_adjustment_nested/README.md) 与 [内层 Case](../../examples/cases/supply_adjustment_nested/cases/production_inner/README.md)；批次并发与授权边界见 [状态成本与嵌套执行](../architecture/STATE_COST_AND_NESTED_EXECUTION_CN.md)。
