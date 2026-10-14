# Unit 接口增量索引

## 2026-10-14 Adapter 解池接入与参数核对

以下是主干 Adapter 的实际接口增量；`default` 与 `framework-core` 两个口径相同，不新增 example/doc 统计。类和配置由 `nsgablack.adapters` 导出。

### 池输入、投影与结果

- `GaussianSearchAdapter`、`MASAdapter`、`GradientDescentAdapter`、`TrustRegionDFOAdapter`、`TrustRegionMODFOAdapter`、`TrustRegionNonSmoothAdapter`、`TrustRegionSubspaceAdapter` 声明 `pool_input_modes=("initialize",)`、`supports_pool_restart=True`、`supports_objective_projection=True`。通过 `PoolTaskSpec(mode="refine")` 做有界精修；`refine` 由任务包装器重启子 Adapter 并逐个交付种子，不是额外的叶 Adapter 输入模式。
- `GradientOptimizerAdapter` 支持普通池 `initialize/refine`，但 `supports_objective_projection=False`：只变换目标值的视图不能同时重解释 inline gradient 或 Provider 的 `gradient_ref`，装配必须拒绝这种投影。
- `default_pool_input_count()` 描述初始化消费量，不规定母池容量。Gaussian 在 `initialization="population"` 时返回 `population_size`，在 `"center"` 时返回 1；MAS、有限差分、Provider 梯度和四种信赖域均返回 1。精修任务默认每实例一个起点。
- `restart_search(control, context)` 清除任务的工作状态和比较基准；由既有步骤事务协调。Provider 的旧 optimizer slots 在提交时退休，回滚恢复原引用，释放失败保留精确 StateRef 清理债务。
- `get_solution_pool_roots(control)` 声明仍需保留的精确候选版本；`get_pool_refinement_results(control)` 返回最终选择的已评估 `SolutionRef`。结果不按 token 查找最新版本，也不把未评估后继当作结果。输入和结果的候选 metadata、父 token、源引用跟随正式池协议；一次任务的投影固定，换投影必须重启。

### 算法配置与消费时序

- `GaussianSearchConfig`：`population_size=16`、`mutation_scale=0.25`、`random_seed=42`、`exploit_best=True`、`initialization="population"`（或 `"center"`）、`include_center_candidate=True`、`objective_aggregation="sum"`（或 `"first"`）。center 模式先送评基准，population 模式先送评初始化批次；之后才围绕已评估选择生成邻居。投影任务采用所属方向的可行性比较规则。
- `MASConfig`：`batch_size=16`、`exploration_ratio=0.4`、`random_seed=None`、`enable_surrogate=True`、`surrogate_model_type="rf"`、`surrogate_min_train_samples=20`、`surrogate_max_train_samples=5000`、`surrogate_retrain_every_call=True`。先评估种子，随后探索或使用代理模型；训练 X/Y 与精确样本 refs 同步裁剪、保留和恢复。当前搜索中心可移动，任务结果仍交付已评估的最佳选择。
- `GradientDescentConfig` 的字段为 `learning_rate=0.15`、`epsilon=1e-3`、`max_directions=10`、`lr_growth=1.05`、`lr_decay=0.7`、`min_lr=1e-5`、`objective_aggregation="sum"`、`repair_policy="coordinate"`（或 `"reject"`）。执行分成基准评估、正负探针评估、梯度试探点评估；只有试探点自身反馈才能替换中心。部分接纳只使用完整正负探针对，已评估探针也可成为任务结果。这里不使用其它梯度组件的参数名。
- `GradientOptimizerConfig` 支持 `optimizer="sgd"|"adam"|"adamw"`，以及 `learning_rate`、`min_learning_rate`、`weight_decay`、`max_gradient_norm`、`beta1`、`beta2`、`epsilon`、`objective_aggregation`、`skip_infeasible`。`state_gateway` 和 `prefer_provider_transition` 是 Adapter 构造参数；`GradientOptimizerConfig.from_method("gradient.adam", ...)` 等方法映射保持有效。由反馈算出的 next 参数尚未评估，结果接口只交付已评估选择；无新 transition 的跳过或拒绝步骤不得释放仍在使用的 Provider slots。
- 四种信赖域均先评估起点、再提出区域内邻居；基准提交不扩大半径。共有 `batch_size`、`initial_radius/min_radius/max_radius`、`radius_expand/radius_shrink`、`success_tolerance`、`include_center`、`random_seed`。`TrustRegionNonSmoothConfig.score_mode` 为 `"l1"|"linf"`；外部投影直接使用任务标量，不再套绝对值聚合。
- `TrustRegionMODFOConfig` 另有 `weight_method="dirichlet"|"uniform"|"fixed"`、`fixed_weights=None`。普通搜索保留方向重采样，并将已保存的中心/最佳目标向量在同一新权重下重新评分；原生池任务内冻结权重，外部投影覆盖原生标量化。权重必须有限、非负、和大于零且与目标维度一致。
- `TrustRegionSubspaceConfig` 另有 `subspace_dim=8`、`basis_method="random"`（另支持 `pca/svd/sparse_pca/cluster`）、`min_samples=32`、`sample_limit=256`、`resample_every=10`。`sample_limit` 至少覆盖 `min_samples`；参考样本只来自本任务已接纳的有界精确 refs，不隐式读取其他 Adapter 的 population。样本不足时采用随机基底，重启清空样本窗口；边界裁剪沿同一子空间方向缩短步长。

### A* / MOA* 的显式新根边界

`AStarConfig.pool_start_policy` 和 `MOAStarConfig.pool_start_policy` 默认为 `None`，只有显式设为 `"new_root"` 才声明 `initialize` 池输入，且一次恰好一个种子。种子经正常 repair、评估、接纳后建立新根；不会导入其它搜索的 g/h、父路径或 Pareto 标签，也不能覆盖正在运行的搜索树。

两者仍不声明通用 `refine/restart` 或目标投影支持。A* 的 `get_pool_refinement_results` 交付按原有目标聚合与约束惩罚选择的 `best_evaluated`，不等于最短目标路径；MOA* 交付按自身路径成本 g 判断的非支配标签，不把路径成本写回原始 Problem 目标。保留接口保护活跃节点/标签、待展开父引用和相应最佳/目标结果的精确候选版本；缺少可证明的引用时不猜测。

### 索引维护口径

本页是人工维护的接口增量索引。全文导出入口 `catalog.api_index.export_default_api_index_docs()` 从 MySQL API 索引读取，输出到 `COMPONENT_API_INDEX_FULL_CN.md` 与 `COMPONENT_API_INDEX_FRAMEWORK_CORE_CN.md`，不会生成本页；`tools/generate_api_docs.py` 则生成 `docs/api` 下的 Sphinx 文档。更新本页不代表数据库全量索引已重建；全量导出需先确保对应 MySQL API 索引数据已同步。

## 既有接口增量（2026-10-13 及以前）


2026-10-13 取解默认：tool.pool_task_spec 增加可省略 select、count/distribution/on_insufficient/shuffle；initialize 默认每群独立抽样，refine 默认每实例一个起点，整批需 count="all"。adapter.nsga2/nsga3 通过 default_pool_input_count 声明初始化默认量；池容量仍独立。上述主干项在 default 同样可发现。

2026-10-13 子池角色任务：`adapter.pool_task` → PoolTaskAdapter，`tool.pool_task_spec` → PoolTaskSpec，均由 nsgablack.adapters 导出，在 default 同样可发现。RoleSpec/StrategySpec 可声明 pool_task；SolutionPool 增加 create_subpool/subpool_refs/add_to_subpool/drop_subpool/read_raw_feedback。正式规则见 [解池契约第 10 节](../architecture/SOLUTION_POOL_CN.md)。example.pool_refinement 仅在 default 可发现。

2026-10-13 解池（`framework-core`）：`adapter.pool_search` → PoolSearchAdapter；`tool.solution_pool / tool.solution_ref / tool.solution_stamp / tool.pool_retention_policy` → nsgablack.core。五项在 default 同样可发现。Solver 自带池并登记 candidates owner；时间、输入游标、保留年龄和 manifest 参与既有事务，闲置回收显式启用，见 [解池契约](../architecture/SOLUTION_POOL_CN.md)。doc/example 仅在 default 出现，不属于主干统计。

2026-10-12 成员维护（`framework-core`）：`tool.population_change` → `nsgablack.units:PopulationChange`。PopulationUnit 的 initialize_population/apply_selection/replace_evaluated_rows/clear_population 共享成员维护钩子，member_fields 声明行字段；Adapter 保留选择与接受策略。本项也在 default 可发现；见 [Unit 成员维护](../architecture/UNIT_MEMBER_OPERATIONS_CN.md)。

2026-10-09 接纳边界修复（`framework-core`）：UnitRepair.project_admission 在 Adapter disposition 之后执行，draft 已整理为接纳坐标；JointRepairPolicy 的 advance 使用整组规划与决策事务。`repr.unit_trajectory`、`repr.unit_poll`、`repr.unit_parameters`、`repr.unit_region` 对应 Unit schema v2，新增候选反馈依赖版本，旧 v1 不自动恢复。上述主干项在 default 同样可发现；见 [共同修复契约](../architecture/JOINT_REPAIR_CN.md) 与 [Unit 特征维护](../architecture/UNIT_FEATURES_CN.md)。

2026-10-09 双侧修复（`framework-core`）：`tool.problem_repair`、`tool.unit_repair`、`tool.joint_repair_policy` → nsgablack.representation；均为主干 API，default 也可发现。UnitRepair 可扩展 project_admission 处理部分接纳，策略新增 on_rejection（默认 stop），见 [共同修复契约](../architecture/JOINT_REPAIR_CN.md)。

2026-10-09 共享管线装配（`framework-core`）：`repr.pipeline` 新增 `mutation_operators` 注册；Adapter 的 `set_mutation_operator(name)` 选择实际消费的算子。该条目在 default 同样可发现；详见 [算子 Unit 输入](../architecture/UNIT_OPERATOR_INPUTS_CN.md)。

2026-10-09 算子依赖增量（`framework-core`）：`tool.unit_input_spec` → `nsgablack.units:UnitInputSpec`，`tool.unit_inputs` → `nsgablack.units:UnitInputs`。两项也在 default 可发现；详见 [算子 Unit 输入](../architecture/UNIT_OPERATOR_INPUTS_CN.md)。

2026-10-09 派生特征增量（`framework-core`）：`tool.unit_feature` → `nsgablack.units:UnitFeature`，`tool.feature_unit` → `nsgablack.units:FeatureUnit`。两项也在 default 可发现，全部指向主干；详见 [Unit 特征维护](../architecture/UNIT_FEATURES_CN.md)。

2026-10-09 Unit 偏好增量（`framework-core`）：`tool.unit_view`、`tool.preference_query`、`bias.population_diversity`、`bias.unit_preference`。四项均指向 nsgablack 主干，使用方法见 [Unit 偏好契约](../architecture/UNIT_PREFERENCE_CONTRACT_CN.md)。

日期：2026-10-08。口径：`framework-core`。本页列出 Unit 和运行契约相关公开接口，不是全框架数量统计。

## 运行契约增量（2026-10-08）

2026-10-09 新增（同为 `framework-core` 口径）：`tool.strategy_task` → `nsgablack.adapters:StrategyTask`；`tool.strategy_origin` → `nsgablack.adapters:StrategyOrigin`。均为主干接口，见多策略调用作用域契约。

本节同样采用本页标注的口径；以下 8 个 tool 条目在 default 与 framework-core 均可发现，全部指向主干模块。用途与迁移见 [运行契约](../architecture/RUNTIME_CONTRACTS_CN.md)。

- `tool.runtime_participant` → `blackbase.runtime:RuntimeParticipant`：通用步骤事务参与者；局部快照、恢复、子参与者与提交后清理。
- `tool.representation_capabilities` → `blackbase.representation:RepresentationCapabilities`：候选管线显式操作能力声明。
- `tool.participation_contract` → `blackbase.participation:ParticipationContract`：Plugin 与 Controller 的建议、决定和否决域。
- `tool.preference_delta` → `blackbase.preferences:PreferenceDelta`：保留原始反馈的偏好增量值。
- `tool.population_authority` → `nsgablack.core.state.population_authority:PopulationAuthority`：运行内 population、身份、分区与发布游标所有者。
- `tool.run_session` → `nsgablack.core.state.run:RunSession`：运行身份、进度、预算、恢复队列与结果所有者。
- `tool.finalization_hooks` → `blackbase.runtime:FinalizationHooks`：结果准备和事务发布的显式注册入口。
- `tool.semantic_extension` → `nsgablack.core.semantic_extension:SolverSemanticExtension`：提交前语义准备与提交后投影扩展。


## 构建与恢复

- `nsgablack.units.UnitSchema`：结构名、版本、必要字段和投影种类。
- `UnitBuildRequest / StructureBuildRequest`：候选或复合结构请求。
- `UnitBinding`：构建绑定、校验和独立 codec。
- `UnitBinding.require / describe_requirement`：显式 schema 兼容、构建操作与工厂方法对齐；codec 身份仍精确匹配。
- builder 的 `compatible_schemas / supported_operations` 与 Adapter 的 `unit_build_operations / unit_builder_methods`：装配能力声明。
- `AlgorithmAdapter.get_unit_alignment`：主结构及附加槽位的需求与能力审计。
- `AlgorithmAdapter.get_unit_contracts / validate_unit_bindings`：组合审计及兼容性验证。
- `UnitBackedAdapter / UnitField`：复合 Unit 权威字段与状态恢复模板。
- `CandidateProposerAdapter`：简单 Case 策略的候选构建基础。
- `RepresentationPipelineKernelBuild.bind_units`：正式算法管线绑定入口。

## Catalog 条目

- `repr.unit_candidate` → `nsgablack.representation:CandidateUnitBuilder`（representation）。
- `repr.unit_search_node` → `nsgablack.representation:SearchNodeBuilder`（representation）。
- `repr.unit_pareto_label` → `nsgablack.representation:ParetoLabelBuilder`（representation）。
- `repr.unit_trajectory` → `nsgablack.representation:TrajectoryUnitBuilder`（representation）。
- `repr.unit_poll` → `nsgablack.representation:PollUnitBuilder`（representation）。
- `repr.unit_parameters` → `nsgablack.representation:ParameterUnitBuilder`（representation）。
- `repr.unit_population` → `nsgablack.representation:PopulationUnitBuilder`（representation）。
- `repr.unit_reference_population` → `nsgablack.representation:ReferencePopulationBuilder`（representation）。
- `repr.unit_differential_population` → `nsgablack.representation:DifferentialPopulationBuilder`（representation）。
- `repr.unit_decomposition` → `nsgablack.representation:DecompositionUnitBuilder`（representation）。
- `repr.unit_region` → `nsgablack.representation:RegionUnitBuilder`（representation）。
- `repr.unit_model_search` → `nsgablack.representation:ModelSearchUnitBuilder`（representation）。
- `repr.unit_archive` → `nsgablack.representation:ArchiveUnitBuilder`（representation）。
- `repr.unit_neighborhood` → `nsgablack.representation:NeighborhoodUnitBuilder`（representation）。

共 14 个结构构建器；不包含 example/doc 导向条目。

行为与迁移边界见 [算法 Unit 中文说明](../guides/ALGORITHM_UNITS_CN.md)。

## 2026-10-09 可用性与所有权修订

本页口径不变。ContextKeyRegistry/context_key_scope/register_context_keys 属于 blackbase.context；优化键由 nsgablack.context_keys 发布，ML 键由 mlblack.context_keys 发布。UnitBinding.dump/restore 统一验证并脱离显式 codec payload；ParetoArchive 提供 token 对齐的 PopulationSnapshot 与恢复状态。

Catalog 的配方均标注 recipe-status：guidance/template/signature-checked/unverified。静态 import_ok/params_ok 为 null（未检查），签名通过不等于已执行。五个完整 Adapter 配方位于 examples/cases/catalog_recipes，作为 default 口径示例使用；它们不会成为 framework-core 的组件条目。

标准 Case 公共装配实现移到 nsgablack.project.case_support，通用图导出移到 blackbase.project.graph_export；Case 只保留本地工厂绑定和显式导出。目录形状与 build_solver/run_solver 入口不变。
