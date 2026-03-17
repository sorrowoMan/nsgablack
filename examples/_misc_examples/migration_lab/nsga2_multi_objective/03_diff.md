# Traditional NSGA-II -> Framework Mapping / 传统 NSGA-II 到框架映射

This file maps baseline implementation (`00_baseline.py`) to framework implementation (`02_framework_final.py`).
本文件用于对照 `00_baseline.py` 与 `02_framework_final.py` 的职责迁移关系。

## Mapping Table / 映射表

| Baseline responsibility / 基线职责 | Baseline location / 基线位置 | Framework replacement / 框架替换 | Why this helps / 作用说明 |
|---|---|---|---|
| Objective pair / 双目标定义 | `evaluate_individual` | `BiObjectiveShiftedSphere.evaluate` | Keep objective semantics in Problem layer. / 目标语义回到 Problem 层。 |
| Non-dominated sort / 非支配排序 | `fast_non_dominated_sort` | `NSGA2Adapter.update` internal ranking | Process detail moves into adapter. / 过程细节下沉到 adapter。 |
| Crowding distance / 拥挤距离 | `crowding_distance` | `NSGA2Adapter` internal selection | Selection policy stays encapsulated. / 选择策略被封装。 |
| Tournament + crossover + mutation / 锦标赛+交叉+变异 | baseline loop | `NSGA2Adapter.propose` + pipeline mutator | Process and operator concerns are decoupled. / 流程与算子解耦。 |
| Environmental selection / 生存选择 | `environmental_selection` | `NSGA2Adapter.update` | Survivor logic becomes reusable. / 生存选择逻辑可复用。 |
| Runtime loop / 运行主循环 | `run_baseline` | `ComposableSolver.run` | Unified lifecycle and plugin/context hooks. / 生命周期与钩子统一。 |
| Seed / 随机种子 | local RNG only | `solver.set_random_seed` | Framework-level reproducibility entry. / 框架级可复现入口。 |

## Minimal Migration Checklist / 最小迁移清单

1. Move objective definitions to a `BlackBoxProblem` subclass. / 将目标定义迁移到 `BlackBoxProblem` 子类。
2. Move operator components to `RepresentationPipeline`. / 将算子组件迁移到 `RepresentationPipeline`。
3. Replace manual NSGA-II loop with `NSGA2Adapter`. / 用 `NSGA2Adapter` 替代手写 NSGA-II 循环。
4. Assemble with `ComposableSolver(problem, adapter, pipeline)`. / 用 `ComposableSolver(problem, adapter, pipeline)` 装配。
5. Run via `set_max_steps` + `run()` and inspect Pareto front. / 用 `set_max_steps` + `run()` 执行并查看 Pareto 前沿。

## Notes / 备注

- This workshop focuses on process migration first. / 本练习先关注流程迁移，不先叠加 bias/plugin。
- Next step: add one domain bias and one runtime plugin while keeping adapter unchanged. / 下一步是在不改 adapter 的前提下增加一个业务 bias 和一个 runtime plugin。
