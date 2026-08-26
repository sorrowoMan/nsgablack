# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project aims to follow SemVer.

## [Unreleased]

### Added
- 正式 `super_topology_orchestration` 跨框架示例：BlackBase Project DAG 自动调度并行
  Solver/MLBlack Trainer 基线与 Artifact 下游，外层复合 Adapter 的每个候选再动态调用
  Trainer Case，Trainer 继续调用内层 Solver Case，并验证三层资源、预算与 lineage。
- BlackBase `EvaluationEvidenceJournal` 接入：以 preparing/pending/deciding/terminal 状态机索引评估证据；恢复时补结算已发布处置，或把无确定决策的 Event 明确归档为 abandoned，绝不隐式重放评估。
- `evaluation_disposition/v1` 证据边：把完整 Evaluation Event、接纳/提案裁决与最终 authority Snapshot 显式关联；拒绝和失败使用独立证据记录。
- Gradient Provider cleanup debt checkpoint：仅保存 host/cluster 可寻址 StateRef，恢复后继续按当前 L0 grant 偿还。
- Controller checkpoint state protocol；`RuntimeController` 按稳定 name/type 恢复 StopController patience 等控制状态。
- Adapter 显式 `snapshot_step_state()/restore_step_state()` 步骤事务协议，以及 `step_transaction_children()/commit_step_state()` 参与者闭包；第三方锁、executor、Provider/session 不再被整个对象图深拷贝。
- `PopulationPartition` 与复合 Adapter 的 `single/delegate/partitioned` 权威 population 协议。
- 可恢复的 `RunProgressState`，统一逻辑步数、累计耗时、deadline 与 ML CompletionPolicy 状态。
- checkpoint v7：显式保存 population authority、语义 partitions、独立的 last-evaluated event、candidate lineage，以及逻辑步/物理 attempt 运行进度。
- checkpoint v9：通过 BlackBase `evaluation_event/v1` 信封保存完整 CandidateBatch、Feedback、provenance、Pareto 语义身份和 run/attempt identity；旧数值事件迁移后显式标记语义不完整。
- `StepOutcome`：区分 committed、idle、rejected、cancelled 与 terminal，空执行不再制造逻辑步骤。
- `EvaluationAcceptancePolicy`：评估后的可行性/质量门禁通过 `BatchDisposition` 原子裁剪 CandidateBatch、Feedback 和 Adapter proposal ranges。
- API stability policy and release process documentation.
- Pipeline repair guardrails: ComposableSolver uses repair_batch when available; NSGA-II evaluates repaired candidates.
- ParallelRepair wrapper for optional parallel repair_batch (thread/process).
- Context field governance guard (`tools/context_field_guard.py`) and CI gate.
- Fixed baseline benchmark runner (`benchmarks/fixed_baseline_runner.py`) and evidence protocol doc.
- Run Inspector Context regression tests (`tests/test_context_view_flow.py`).
- State Governance + RNG 规范 + Bias 统一 apply 规则已收敛到 `docs/project/CORE_STABILITY.md`、`docs/user_guide/CONTEXT_CONTRACTS.md` 和 `docs/user_guide/CONTEXT_FIELD_RULES.md`。
- `docs/concepts/CONTEXT_SCHEMA.md`：修复乱码，重写为可读中文。

### Changed
- Evaluation Evidence terminal 必须携带目标 Snapshot 实读验证回执；恢复时暂时不可读的
  Event/authority 保持 unresolved 并允许后续重试，而不是被不可逆归档。
- committed Evidence 结算会复用 Population Snapshot v2 语义校验器，验证 authority mode、
  单/分区结构、X/F/V 基数以及 CandidateBatch token/provenance；摘要正确但语义非法的
  Snapshot 保持 deciding/retry，不会获得 terminal receipt。
- SnapshotStore/EvidenceJournal 改为未运行、未发布状态下的原子成对切换；Adapter
  post-commit cleanup report 无论成功或失败都写独立 Snapshot 并发布 Context ref。
- 评估、步骤回滚、生命周期清理与 teardown 的次生错误通过 BlackBase 正式 failure
  evidence carrier 进入跨 Case `CaseFailure.details`。
- 周期 checkpoint 的保存频率与 `resume_cursor` 统一取已提交逻辑步
  `RunProgressState.steps_completed`，不再按 Solver 类型猜测 generation 口径。
- Evaluation Evidence 正常结算会重新读取 Event/authority Snapshot，并逐字段验证处置信封；
  SnapshotStore 与 Evidence Journal 改为原子成对替换。
- `AdapterCommitReport` 升级为携带 cleanup evidence 的 v2；Gradient Adapter 只有在 Provider
  回执完整覆盖 requested/released/not-found state ID 时才清除清理债务。
- 运行级 Plugin init/finish/finalized/error 使用精确参与者 receipt；所有终止观察器独立执行，`on_error` 失败不再替换原始运行异常。
- 权威 Population Snapshot 改为步骤内 staging + committed 后新 key 发布；Evaluation Event 使用独立 key，失败、拒绝和零接纳不会覆盖上一份权威快照。
- Adapter semantic commit 与 post-commit cleanup 分离；所有事务参与者都会生成 `AdapterCommitReport`，Provider 清理失败引用保留为可重试队列。
- Plugin attempt/generation 生命周期使用 BlackBase receipt 精确配对；最终结果和 save-on-finish checkpoint 延后到 teardown 成功后的 `on_solver_finalized`。
- 事务型最终发布新增 `on_solver_finalization_prepare` 严格否决阶段；Artifact 原子 commit 后才进入 `on_solver_finalized`，统一普通 Solver 与 ML Solver 的 finalized 语义。
- Adapter 回滚会尝试恢复所有显式参与者并聚合次生错误，Solver 保留原始步骤异常；Provider-backed 梯度步骤按本次尝试的 state ID 定向释放未提交槽位。
- AsyncEventHub 在同一锁域内捕获 attempt identity，并通过原子摘取队列提交；`drop_old` 并发写入不再误删新事件。
- generation/attempt 尾钩子独立执行并聚合次生清理异常，严格模式下也维持已启动生命周期参与者的结束闭包。
- Controller 与 Plugin 共享 `attempt_*` / `generation_*` 生命周期槽；idle/rejected 不再消耗 generation budget。
- Composable/Evolution step 使用回滚事务提交 Adapter、population authority、incumbent、Pareto/history 与 snapshot 引用；评估事件作为已完成事实独立保留。
- 复合 Adapter 把局部 allocation 与全局 acceptance 合成为对子 Adapter 的一次最终 `BatchDisposition`。
- AsyncEventHub 在 attempt 内对 sync/async 都采用事务缓冲，并能提交 attempt 边界外到达的后台事件。
- Evaluation acceptance 使用 full-evaluated event、accepted update batch 与 Adapter authoritative population 三视图事务；零接纳恢复旧权威投影，partial/partitioned snapshot 保留完整评估事件。
- `StepOutcome(status="cancelled")` 固化为终止请求；committed outcome 的停止请求在完成本代生命周期后生效。
- Profiler 与 AsyncEventHub 在 attempt-end 结算，rejected/failed 尝试的耗时、评估量和事件不再混入下一代。
- 恢复生命周期统一为 `prepare -> setup -> Plugin.prepare_restore -> restore -> ordinary init hooks -> initialize-if-fresh -> run`，预加载状态不再被 Adapter `setup()` 清空，普通插件只观察恢复后的状态。
- Population Snapshot 升级为 `nsgablack.population_snapshot/v2`；partitioned authority 不再把最后评估批次伪装成单一 population。
- `max_steps` 只限制已提交逻辑步；`max_step_attempts` 与连续 idle 上限独立承担活性保护。attempt 生命周期钩子始终成对，完成类副作用只监听 `on_generation_committed`。
- `EvolutionSolver` 在没有正式聚合策略时拒绝 partitioned population topology；delegate wrapper 递归解析实际 population owner。
- 标准 Case 自定义 `step()` 默认严格要求 `StepOutcome`，Doctor 会拒绝缺失注解或 bare/None return。
- mutate 创建带 `parent_token` 的新候选 lineage；repair 保持 token 并更新语义状态。
- Project doctor strict mode escalates missing contracts as errors.
- Run Inspector Context panel gains throttled refresh, local cache, and in-UI error visibility.
- State Governance 双轨制：`get_population_snapshot()` (读) + `commit_population_snapshot()` (写)，消除 solver mirror write。
- Doctor `--strict` 新增两条守卫规则：`solver-mirror-write` + `plugin-direct-solver-state-access`。
- MOEA/D 修复：per-candidate mode + batch subproblem projection (M-04/M-05)。
- AdaptiveBias weight_cap 限制 + 多样性采样优化 (M-09/M-10)。
- 并行评估器 executor 生命周期统一 (M-11)。
- UniversalBias / DomainBias bias_history 改为 bounded deque + 真实违反率 (M-15/M-16)。
- UI 热重载改为 hash+invalidate (M-13)。ContextView 缓存改为 weakref (M-14)。
- memory_manager 历史采样恢复时序 (M-12)。
- **BREAKING**: Context no longer carries large arrays (`population/objectives/constraint_violations`). Added SnapshotStore + snapshot refs (`snapshot_key`, `population_ref`, etc), bumped context field schema to v2.

### Deprecated
- (fill in as you cut releases)

### Removed
- (fill in as you cut releases)

### Fixed
- **N-01/N-02 (🔴)**: SurrogateEvaluation double-bias + 训练数据污染。`_true_evaluate()` 不再 apply bias；并行路径传入 `enable_bias=False`。
- **N-03**: 6 个 adapter 补齐 `set_state()` 对称实现（moa_star/sa/mas/astar/trust_region_subspace/trust_region_nonsmooth）。
- **N-04**: MOA\* `_labels` dict 追加 `.pop()` 清理，消除内存泄漏。
- **N-05**: SA/SingleTrajectoryAdaptive/AsyncEventDriven 3 个 adapter 改用实例级 `self._rng`。
- **N-06**: representation 模块 30+ 处全局 `np.random` 替换为实例级 `self._rng`（base/continuous/binary/permutation/matrix/integer/graph）。
- **N-07**: `checkpoint_resume.py` 的 `pickle.load` 添加安全注释 `# SECURITY NOTE` + `# nosec B301`。
- **N-10**: MultiFidelityEvaluation 补计 low-fidelity 调用次数。
- **C-01**: MonteCarlo 插件不再污染全局 `np.random` 种子。
- **C-02**: MySQL run_id 改从 context 读取。
- **C-03**: DE bias 使用正确的 fitness 数据源。
- **C-04**: MetaLearning import 路径修正。
- **C-05**: AdaptiveBias 匹配逻辑一致化。
- **C-06**: Plugin dispatch 不再静默吞异常。
- **C-07**: Adapter `__setattr__` 与 dataclass 兼容。
- **C-08~12**: Context-ification 全套，消除 solver mirror write。
