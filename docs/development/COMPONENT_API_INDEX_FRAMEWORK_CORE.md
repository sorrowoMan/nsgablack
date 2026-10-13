# Unit 接口增量索引

2026-10-13 解池（`framework-core`）：`adapter.pool_search` → PoolSearchAdapter；`tool.solution_pool / tool.solution_ref / tool.solution_stamp` → nsgablack.core。四项在 default 同样可发现。Solver 自带池并登记 candidates owner；按运行时点选择不可原位改写版本，输入游标和 manifest 参与既有事务，见 [解池契约](../architecture/SOLUTION_POOL_CN.md)。doc/example 仅在 default 出现，不属于主干统计。

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
