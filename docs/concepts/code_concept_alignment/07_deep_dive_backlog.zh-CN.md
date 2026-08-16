# 07. 后续逐文件深挖任务包

本清单用于把两套框架继续对齐到共享 Project / Case / Scaffold / L0 substrate。所有新增文档都必须遵守当前口径：编排属于 substrate，nsgablack 提供优化搜索语义，mlblack 提供机器学习语义。

## A. nsgablack 控制面

| 任务 | 覆盖路径 | 产出建议 |
| --- | --- | --- |
| Solver lifecycle | `core/blank_solver.py`, `core/solver_helpers/run_helpers.py` | `08_nsgablack_solverbase_deep_dive.zh-CN.md` |
| Evaluation chain | `core/solver_helpers/evaluation_helpers.py`, `core/evaluation_runtime.py` | `09_nsgablack_evaluation_chain.zh-CN.md` |
| State plane | `core/state/*`, `utils/context/*` | `10_nsgablack_state_plane.zh-CN.md` |
| Runtime governance | `core/control_plane.py`, `core/runtime_governance.py` | `11_nsgablack_runtime_governance.zh-CN.md` |
| Nested case runtime | `core/nested_solver.py`, `plugins/solver_backends/*` | `12_nsgablack_nested_runtime.zh-CN.md` |

## B. nsgablack 算法与候选层

| 任务 | 覆盖路径 | 产出建议 |
| --- | --- | --- |
| Adapter contract | `adapters/algorithm_adapter.py` | `13_nsgablack_adapter_contract.zh-CN.md` |
| Pareto adapters | `adapters/nsga2`, `adapters/nsga3`, `adapters/spea2`, `adapters/moead` | `14_nsgablack_pareto_adapters.zh-CN.md` |
| Local search adapters | `adapters/simulated_annealing`, `adapters/vns`, `adapters/trust_region_*` | `15_nsgablack_local_search_adapters.zh-CN.md` |
| Discrete search adapters | `adapters/astar`, `adapters/moa_star`, `adapters/mas` | `16_nsgablack_discrete_search_adapters.zh-CN.md` |
| Candidate representation | `representation/*` | `17_nsgablack_representation_deep_dive.zh-CN.md` |
| Bias system | `bias/core`, `bias/domain`, `bias/algorithmic`, `bias/surrogate` | `18_nsgablack_bias_deep_dive.zh-CN.md` |

## C. nsgablack 能力层与项目面

| 任务 | 覆盖路径 | 产出建议 |
| --- | --- | --- |
| Plugin manager | `plugins/base.py` | `19_nsgablack_plugin_manager.zh-CN.md` |
| Runtime plugins | `plugins/runtime/*` | `20_nsgablack_runtime_plugins.zh-CN.md` |
| Evaluation plugins | `plugins/evaluation/*` | `21_nsgablack_evaluation_plugins.zh-CN.md` |
| Solver backends | `plugins/solver_backends/*` | `22_nsgablack_solver_backends.zh-CN.md` |
| Catalog | `catalog/*` | `23_nsgablack_catalog_deep_dive.zh-CN.md` |
| Doctor / Scaffold | `project/*`, `project/doctor_core/*` | `24_nsgablack_project_doctor.zh-CN.md` |

## D. mlblack 语义层

| 任务 | 覆盖路径 | 产出建议 |
| --- | --- | --- |
| Schema | `schema/*` | `25_mlblack_schema_deep_dive.zh-CN.md` |
| Numericizer | `numericizer/*` | `26_mlblack_numericizer_deep_dive.zh-CN.md` |
| Pipeline | `pipeline/*` | `27_mlblack_pipeline_deep_dive.zh-CN.md` |
| Assembly | `config/assembly.py`, `config/defaults.py`, `config/registry.py` | `28_mlblack_assembly_deep_dive.zh-CN.md` |
| Trainer contract | `core/common/base_trainer.py`, `training/*` | `29_mlblack_trainer_contract.zh-CN.md` |
| Artifacts | `core/artifacts/*` | `30_mlblack_artifact_deep_dive.zh-CN.md` |
| Plugins / capabilities | `plugins/*`, `core/orchestration/capabilities.py` | `31_mlblack_plugins_capabilities.zh-CN.md` |

## E. 符号与机制层

| 任务 | 覆盖路径 | 产出建议 |
| --- | --- | --- |
| Symbolic DSL | `core/symbolic/symbolic_dsl.py`, `symbolic_gradient.py` | `32_mlblack_symbolic_dsl_gradient.zh-CN.md` |
| Structure search component | `structure_optimizer.py`, `symbolic_structure_search.py` | `33_mlblack_symbolic_structure_search.zh-CN.md` |
| Orthogonal basis | `orthogonal_basis_search.py`, `basis_consensus.py` | `34_mlblack_orthogonal_basis_consensus.zh-CN.md` |
| Feature space | `core/symbolic/feature_space/*` | `35_mlblack_symbolic_feature_space.zh-CN.md` |
| Mechanisms and sources | `core/mechanisms/*`, `core/orthogonal_source/*` | `36_mlblack_mechanisms_orthogonal_source.zh-CN.md` |

## F. 跨框架案例

| 任务 | 目标 |
| --- | --- |
| Symbolic consensus case | 两边各自用标准 Case surface，Project 注入资源上下文 |
| Learnable component search | 外层搜索组件配置，内层返回 artifact 与指标 |
| Image source search | 表征来源选择作为候选，ML 评估作为内层 Case |
| Finance lane search | 策略 lane 作为候选，滚动评估作为内层 Case |
| Run surface contract | 统一 assembly signature、resource audit、artifact refs |

## 文档模板

```md
# 模块名

## 覆盖文件

## 1. 代码结构

## 2. 关键对象对齐

| 代码对象 | 社区概念 | 框架职责 | 可验证证据 |
| --- | --- | --- | --- |

## 3. 调用链

## 4. 与 substrate 的边界

## 5. 对外表达

## 6. 后续 benchmark / ablation
```
