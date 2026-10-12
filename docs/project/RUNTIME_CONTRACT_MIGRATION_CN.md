# 显式运行契约迁移

本次工作区开发版本为 BlackBase 0.3.26、NSGABlack 0.4.1、MLBlack 0.4.24，未在本任务发布到包仓库。请配套更新三仓；旧版 BlackBase 不提供新增协议。Snapshot/RunProgress wire schema 保持原版本；偏好记录通过 Feedback.info 传输。自定义组件的能力发现和发布注册方式有不兼容变化，升级前须完成下列迁移。

1. 自定义管线声明 `representation_capabilities = RepresentationCapabilities(frozenset({...}))`，只列实际支持的操作。内置 RepresentationPipeline 从装配槽位声明能力，ML bridge 无须 initializer/decoder 自指属性。
2. 发布前严格校验 Plugin 声明 `participation = ParticipationContract(vetoes=("finalization",))`；提供评估结果声明 `decides=("evaluation",)`。NSGABlack 评估接管仍优先通过 EvaluationProvider；角色声明不解除既有路由限制。
3. 自定义结果通过 `FinalizationHooks(prepare_result=..., prepare=..., freeze=..., abort=...)` 注册。同名可选方法不再自动注册；直接发布旧路由须显式注册 publish，不能与事务型钩子混用。
4. 共享 step 提交后的投影迁入 SolverSemanticExtension。异常必须保留 committed=True，不能回滚已经发布的快照。
5. 新状态经 register_state_participant 加入事务。snapshot_step_state 必须只读地返回 Mapping[str, Any]；事务和 Doctor 均校验外层结构。参与者只捕获已脱离活对象的本地状态并声明独立子参与者，不复制 __dict__。登记 authority 的非事务所有者必须显式传 rollback_exempt_reason；RunSession 已声明豁免，不得把它加入步骤事务。
6. 通过 run_session.submit_restore 恢复。Solver 旧字段仍访问同一所有者，供既有接口过渡；新扩展使用公开协议。
7. 原始评估读取 raw_objectives/raw_violations；原 objectives/violations 为选择视图。Case 必须披露忽略违规的选择策略，不得将它当作可行性证明。
8. 生命周期、context、checkpoint 和停止条件通过 SolverSemanticExtension 注册；不要再复制 LearningSolver 的旧覆盖方法。清理回调通过 cleanup_components 声明，适配部分 setup；异常聚合读取 BlackBase collect_failure_evidence(exc)["solver_teardown"]，不再依赖 ML 私有异常属性。
9. A* heuristic、候选初始化、RNG 分叉、快照与 checkpoint 采集的非预期异常现在会中止操作。需要降级的组件应在自己的语义边界显式定义合法降级结果并记录失败；不能依赖框架偷偷生成随机候选、将启发值设为零或漏存状态。
10. 自定义 checkpoint 组件必须返回可脱离的状态。deepcopy 失败现在传播错误，不能把 Provider/session 等活对象原样写入 checkpoint。Catalog 注册 GPU 指标键 metrics.gpu_backend / metrics.gpu_calls / metrics.gpu_fallbacks 使用 BlackBase 的统一键注册表。
11. MonteCarlo Provider 返回带统计量的 OptimizationFeedbackBatch / Feedback，共享评估入口把每个候选的 metrics 交给 Bias，只施加一次偏好。直接调用 evaluate_population_runtime 获得原始数值统计，不再在该方法中施加 Bias；保留完整信息应使用 evaluate_feedback_population 或 Solver 的正式评估入口。

迁移后执行受影响 Case 的 Doctor --build，并验证单点、批量、Provider 接管、Snapshot 和恢复路径。检查口径见 [Doctor 中文说明](DOCTOR_CN.md)。

多策略组合（2026-10-09）：子 Adapter 改用 `StrategyTask.from_context(context)` 读取任务；局部旧键仍由任务派生，但全局不再提供最后一个子任务的 role/strategy_id/region/seeds。`unit_tasks` 的键变为实例路径，值为轻量摘要；完整种子只在局部 task 中读取。候选来源使用 `StrategyOrigin.from_candidate(CandidateBatch.semantic_states[i])`，不要用全局 strategy_id 判断所有候选的来源。task.budget 始终表示原请求，接纳数读取 BatchDisposition。Router checkpoint 使用 v3，旧 v2 缺少正式任务身份，需用旧版本导出领域状态并显式重建装配，禁止仅改 schema 字符串。恢复时仍要求相同实例拓扑。
