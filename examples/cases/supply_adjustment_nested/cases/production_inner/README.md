# 正式内层生产排程 Case

父 Case 用 `CaseRuntime.invoke()` 调用本 Case；`component_overrides.task` 携带版本化的供应事件、外层 token、原始数据路径和 SHA、实际场景摘要，以及内层种子和求值预算。矩阵在本次子 Case 内从已核对的原始文件重建，不通过闭包传递活 Solver。

`build_solver.py` 仅连接职责模块。`runtime/task_contract.py` 复用父 Problem 的供应变换；旧生产 Case 的 canonical builder 通过显式 `scenario` 装配原五目标、单机上限 3000 和 phased MOEA/D + VNS 配方。Day0 是今天，逐物料固定。

原生产算子使用进程全局随机流，因此必须启用正式子 Case 进程隔离。隔离发生在 builder 之前；在子进程内保留原 `random.seed`、`np.random.seed`，同时 seed Solver 私有流。不得把直接同进程调用 helper 说成父随机流隔离。

子请求应明确声明 `budget_request={"evaluations": 内层额度, "audit_evaluations": 1}`。原始五目标复核额外执行一次并计入独立审计预算，不混入算法求值数。缺少正式 incumbent、候选身份不匹配、硬约束违反或资源绑定失效均拒绝发布。

结果保留 canonical SolverResult 与原 Pareto 引用，并由 CaseExecutor 封存 `production_summary` JSON Artifact：实际排程、原五目标、约束、外层与内层 token、场景与源摘要、运行身份及真实计算计数。该 Artifact 只有正式 Case 成功结算后才具有权威交付语义。

## 跨机输入 v2

本地旧入口保留 `production_task/v1`。外部 Worker 明确拒绝其中的协调端绝对路径，
使用 `production_task/v2`：`source.bom/supply` 分别包含正式 `binding`、原字节 `sha256` 和解析用 `suffix`。
Task 中不再允许 `production_case_dir`；目标只使用预部署的默认生产 Case，或由可信进程环境
`NSGABLACK_PRODUCTION_CASE_DIR` 指定位置。任务的 `code_manifest` 包含按相对路径排序的 Python 文件摘要，
运行前和发布前都核对，不能让一个供应提案指示 Worker 导入任意目录里的代码。

v2 facade 在 builder／Doctor 观察时不读取工件、不创建 Solver 或 Unit。
真正 run 时先核对 Task 内 Binding 与正式 Case 请求声明完全相同，再通过共享 Artifact reader
读取已验证的源字节，临时物化为原扩展名交给原 loader；数组建立后立即删除临时文件。
原模型、五目标、逐事件供应变化和 Day0 库存语义保持不变。

Project 的 `production_sources` 标准 Case 先发布原始文件；`portable` 组依次运行发布和供应 Case。
外层用 `--portable-inputs` 声明数据交付，在 `CaseInnerRuntimeEvaluator` 上绑定
`artifact_bindings={"bom": "bom", "supply": "supply"}`。
内层交付 `production_summary/v2`，外层交付 `joint_summary/v2`，读取器同时保留 v1。
