# 07. 后续逐文件深挖任务包

状态：工作清单  
用途：把“两个框架全部对齐”拆成可持续推进的逐文件任务包。  
说明：当前 `01-06` 是主干机制级对齐；本文件列出下一轮应该逐文件展开的顺序。

## A. nsgablack 控制平面深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| A1 SolverBase 生命周期 | `core/blank_solver.py`, `core/solver_helpers/run_helpers.py` | run/setup/step/finish、插件调度、RNG、storage config、strict/soft-error | `08_nsgablack_solverbase_deep_dive.zh-CN.md` |
| A2 评估链 | `core/solver_helpers/evaluation_helpers.py`, `core/evaluation_runtime.py`, `utils/evaluation/shape_validation.py` | 单点/批量评估、插件短路、bias 介入、shape contract、EvaluationMediator | `09_nsgablack_evaluation_chain.zh-CN.md` |
| A3 Snapshot/Context | `core/state/*`, `utils/context/*`, `core/solver_helpers/snapshot_helpers.py` | context key、snapshot ref、大对象治理、state event、schema | `10_nsgablack_state_plane.zh-CN.md` |
| A4 控制器 | `core/control_plane.py`, `core/runtime_governance.py`, `core/acceleration.py` | budget/stop/switch、convergence、adaptive governor、acceleration facade | `11_nsgablack_runtime_governance.zh-CN.md` |
| A5 嵌套求解 | `core/nested_solver.py`, `plugins/solver_backends/backend_contract.py` | InnerSolveRequest/Result、TaskInnerRuntimeEvaluator、backend bridge、fallback/timeout | `12_nsgablack_nested_runtime.zh-CN.md` |

## B. nsgablack 算法与候选深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| B1 Adapter 总契约 | `adapters/algorithm_adapter.py` | ask-tell、contract、state、population write-back、CompositeAdapter | `13_nsgablack_adapter_contract.zh-CN.md` |
| B2 Pareto EA | `adapters/nsga2`, `adapters/nsga3`, `adapters/spea2`, `adapters/moead` | non-dominated sorting、reference point、decomposition、archive、selection | `14_nsgablack_pareto_adapters.zh-CN.md` |
| B3 单轨迹/局部搜索 | `adapters/simulated_annealing`, `adapters/vns`, `adapters/pattern_search`, `adapters/trust_region_*` | neighborhood、temperature、trust region、DFO、local refinement | `15_nsgablack_local_search_adapters.zh-CN.md` |
| B4 离散/图搜索 | `adapters/astar`, `adapters/moa_star`, `adapters/mas` | heuristic graph search、multi-agent search、discrete state expansion | `16_nsgablack_discrete_search_adapters.zh-CN.md` |
| B5 Representation | `representation/*` | binary/integer/permutation/graph/matrix、repair、encode/decode、parallel repair | `17_nsgablack_representation_deep_dive.zh-CN.md` |
| B6 Bias | `bias/core`, `bias/domain`, `bias/algorithmic`, `bias/surrogate` | domain prior、algorithmic heuristic、surrogate guidance、dynamic penalty | `18_nsgablack_bias_deep_dive.zh-CN.md` |

## C. nsgablack 能力层与产品面深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| C1 PluginManager | `plugins/base.py` | priority、dispatch、profile、report、snapshot-first read | `19_nsgablack_plugin_manager.zh-CN.md` |
| C2 Runtime plugins | `plugins/runtime/*` | Pareto archive、elite retention、diversity init、dynamic switch | `20_nsgablack_runtime_plugins.zh-CN.md` |
| C3 Evaluation plugins | `plugins/evaluation/*` | surrogate、multi-fidelity、Monte Carlo、numerical solvers、GPU template | `21_nsgablack_evaluation_plugins.zh-CN.md` |
| C4 Solver backends | `plugins/solver_backends/*` | COPT templates、ngspice、mlblack backend、contract bridge | `22_nsgablack_solver_backends.zh-CN.md` |
| C5 Catalog | `catalog/*` | profile/filter、registry、DB store、relations、dashboard | `23_nsgablack_catalog_deep_dive.zh-CN.md` |
| C6 Doctor/Scaffold | `project/*`, `project/doctor_core/*` | project scaffold、rules、runtime surface、adapter purity、snapshot policy | `24_nsgablack_project_doctor.zh-CN.md` |

## D. mlblack 数据到训练流深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| D1 Schema | `schema/*` | FeatureSpec、TargetSpec、DatasetSchema、parser、view builder、execution schema | `25_mlblack_schema_deep_dive.zh-CN.md` |
| D2 Numericizer | `numericizer/*` | ModalityEncoder、NumericizationPlan、TargetCodec、unknown policy | `26_mlblack_numericizer_deep_dive.zh-CN.md` |
| D3 Pipeline | `pipeline/*` | identity/zscore、feature space builder、learnable conv、component override | `27_mlblack_pipeline_deep_dive.zh-CN.md` |
| D4 Assembly | `config/assembly.py`, `config/defaults.py`, `config/registry.py` | FlowAssemblySpec、TrainerAssemblySpec、ExecutionSpec、ResourceContext、registry | `28_mlblack_assembly_deep_dive.zh-CN.md` |
| D5 Workflow | `core/orchestration/workflow.py`, `workflow/orchestrator.py`, `workflow/hook_bus.py` | run_train_flow、semantic flow、portfolio flow、stage orchestration、lifecycle report | `29_mlblack_workflow_deep_dive.zh-CN.md` |

## E. mlblack trainer/artifact 深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| E1 Base trainer | `core/common/base_trainer.py`, `training/*` | fit_task、capabilities、resource request、TrainingInit、FitResult、Lineage | `30_mlblack_trainer_contract.zh-CN.md` |
| E2 Linear/Tree families | `core/linear`, `core/tree`, `core/tree_boosting`, `core/trainers/*tree*`, `xgboost_trainer.py` | family/preset/head、tree ensembles、boosting、artifact | `31_mlblack_tabular_families.zh-CN.md` |
| E3 Neural family | `core/neural`, `core/models`, `core/trainers/torch_trainer.py`, `sklearn_mlp_trainer.py` | MLP、torch model、device、optimizer、trainer state | `32_mlblack_neural_family.zh-CN.md` |
| E4 Artifacts | `core/artifacts/*` | predict/uncertainty/validity、save/load、metadata、signature | `33_mlblack_artifact_deep_dive.zh-CN.md` |
| E5 Plugins | `plugins/*`, `core/orchestration/capabilities.py` | checkpoint、resource audit、report writer、reproducibility | `34_mlblack_plugins_capabilities.zh-CN.md` |

## F. mlblack 符号与机制深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| F1 Symbolic DSL | `core/symbolic/symbolic_dsl.py`, `symbolic_gradient.py`, `gradient_parser.py` | expression DSL、symbolic gradient、gradient signal | `35_mlblack_symbolic_dsl_gradient.zh-CN.md` |
| F2 Structure search | `structure_optimizer.py`, `symbolic_structure_search.py`, `search_mechanism_contract.py` | program search、structure optimizer、outer-search boundary | `36_mlblack_symbolic_structure_search.zh-CN.md` |
| F3 Orthogonal basis | `orthogonal_basis_search.py`, `basis_consensus.py`, `artifact_schema.py` | basis discovery、consensus、locked core、equivalence class | `37_mlblack_orthogonal_basis_consensus.zh-CN.md` |
| F4 Feature space | `core/symbolic/feature_space/*` | candidate pool、grammar、primitive registry、regime router、CV/fold report | `38_mlblack_symbolic_feature_space.zh-CN.md` |
| F5 Mechanisms | `core/mechanisms/*`, `core/orthogonal_source/*` | mechanism protocols、family binding、orthogonal source governance | `39_mlblack_mechanisms_orthogonal_source.zh-CN.md` |
| F6 Benchmarks/proxy | `core/symbolic/benchmark/*`, `my_project/known_relation_symbolic/*` | benchmark contract、bundle、outer proxy、truth recovery | `40_mlblack_symbolic_benchmark_proxy.zh-CN.md` |

## G. 跨框架案例深挖

| 任务包 | 文件/目录 | 要对齐的细节机制 | 产出建议 |
| --- | --- | --- | --- |
| G1 Symbolic consensus scaffold | `nsgablack/examples/cases/mlblack_symbolic_consensus_scaffold/*`, `mlblack/my_project/known_relation_symbolic/*` | outer problem、backend、proxy、basis consensus、run surface | `41_cross_symbolic_consensus_case.zh-CN.md` |
| G2 Learnable conv search | `nsgablack/my_project/learnable_conv_component_search/*`, `mlblack/my_project/learnable_conv_component_demo/*` | component override、NAS-lite、inner refinement | `42_cross_learnable_conv_case.zh-CN.md` |
| G3 Phi bundle image search | `nsgablack/my_project/phi_bundle_image_search/*`, `mlblack/my_project/orthogonal_source_image_classification/*` | representation program search、orthogonal source、image proxy | `43_cross_phi_bundle_image_case.zh-CN.md` |
| G4 ETF lane search | `nsgablack/my_project/etf_lane_outer_search/*`, `mlblack/my_project/etf_quant_interval_proxy/*` | walk-forward proxy、strategy lane config、interval metrics | `44_cross_etf_lane_case.zh-CN.md` |
| G5 Run surface contract | `docs/project/RUN_SURFACE_CONTRACT.md`, `RUN_ARTIFACT_SURFACE_PROTOCOL.md`, both experiment/catalog modules | surface/assembly/run/artifact、signature、dashboard | `45_cross_run_surface_contract.zh-CN.md` |

## 建议推进顺序

1. 先做 A1-A3：控制平面、评估链、状态面，这是 nsgablack 主干可信度。
2. 再做 D1-D5：schema 到 workflow，这是 mlblack 主干可信度。
3. 再做 F1-F4：符号学习细节，这是你的差异化核心。
4. 最后做 G1-G5：跨框架案例，这是对外展示和实证入口。

## 每份深挖文档建议模板

```md
# 模块名

## 覆盖文件

## 1. 代码结构

## 2. 关键类/函数逐项对齐

| 代码对象 | 社区概念 | 框架职责 | 差异点 | 可验证证据 |
| --- | --- | --- | --- | --- |

## 3. 调用链

## 4. 和其他模块的边界

## 5. 对外表达

## 6. 后续 benchmark / ablation
```

