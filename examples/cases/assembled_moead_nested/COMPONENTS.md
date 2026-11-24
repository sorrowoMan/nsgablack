# 本例组件及其真实源码

本索引按项目源码的显式导入整理，不冒充运行时调用追踪。项目自定义实现完整展开在 [PROJECT_CODE.md](PROJECT_CODE.md)。
行为、输入输出和验证范围见 [README.md](README.md)，正式运行结果见 [RESULTS.md](RESULTS.md)。

## 本项目的实现

- [_bootstrap.py](_bootstrap.py)：`ensure_importable / bootstrap`。
- [cases/direction_refinement/adapter/composition.py](cases/direction_refinement/adapter/composition.py)：`build_adapter`。
- [cases/direction_refinement/build_solver.py](cases/direction_refinement/build_solver.py)：`build_solver`。
- [cases/direction_refinement/config.py](cases/direction_refinement/config.py)：`DemoConfig`。
- [cases/direction_refinement/pipeline/main.py](cases/direction_refinement/pipeline/main.py)：`build_pipeline`。
- [cases/direction_refinement/plugins/trace.py](cases/direction_refinement/plugins/trace.py)：`data_copy / NestedTrace`。
- [cases/direction_refinement/problem/two_targets.py](cases/direction_refinement/problem/two_targets.py)：`TwoTargets / build_problem`。
- [cases/direction_refinement/run_solver.py](cases/direction_refinement/run_solver.py)：`main`。
- [run_and_report.py](run_and_report.py)：`write_json / close / summarize / write_report / main`。

## 复用的框架源码入口

- `blackbase.participation:ParticipationContract` → [真实源文件](../../../../blackbase/src/blackbase/participation.py)。
- `blackbase.project:run_standard_case_cli` → [真实源文件](../../../../blackbase/src/blackbase/project/case_cli.py)。
- `nsgablack.adapters:MOEADAdapter` → [真实源文件](../../../adapters/moead/adapter.py)。
- `nsgablack.adapters:MultiStrategyConfig` → [真实源文件](../../../adapters/multi_strategy/adapter.py)。
- `nsgablack.adapters:PoolTaskSpec` → [真实源文件](../../../adapters/pool_tasks.py)。
- `nsgablack.adapters:RoleSpec` → [真实源文件](../../../adapters/multi_strategy/adapter.py)。
- `nsgablack.adapters:StrategyRouterAdapter` → [真实源文件](../../../adapters/multi_strategy/adapter.py)。
- `nsgablack.adapters:VNSAdapter` → [真实源文件](../../../adapters/vns/adapter.py)。
- `nsgablack.adapters:subpools` → [真实源文件](../../../adapters/subpools.py)。
- `nsgablack.adapters.subpools:adapter_path` → [真实源文件](../../../adapters/subpools.py)。
- `nsgablack.core:BlackBoxProblem` → [真实源文件](../../../core/base.py)。
- `nsgablack.core:ComposableSolver` → [真实源文件](../../../core/composable_solver.py)。
- `nsgablack.plugins:ParetoArchivePlugin` → [真实源文件](../../../plugins/runtime/pareto_archive.py)。
- `nsgablack.plugins.base:Plugin` → [真实源文件](../../../plugins/base.py)。
- `nsgablack.project:apply_solver_component_overrides` → [真实源文件](../../../project/case_components.py)。
- `nsgablack.project.project_runner:execute_project` → [真实源文件](../../../project/project_runner.py)。
- `nsgablack.project.project_runner:main` → [真实源文件](../../../project/project_runner.py)。
- `nsgablack.representation:ClipRepair` → [真实源文件](../../../representation/continuous.py)。
- `nsgablack.representation:ContextGaussianMutation` → [真实源文件](../../../representation/continuous.py)。
- `nsgablack.representation:GaussianMutation` → [真实源文件](../../../representation/continuous.py)。
- `nsgablack.representation:RepresentationPipeline` → [真实源文件](../../../representation/base.py)。
- `nsgablack.representation:UniformInitializer` → [真实源文件](../../../representation/continuous.py)。
- `nsgablack.utils.engineering.file_io:atomic_write_text` → [真实源文件](../../../utils/engineering/file_io.py)。

## 共同底座与状态入口

- [SolutionPool 与准确候选引用](../../../core/state/solution_pool.py)。
- [Unit 与种群成员维护](../../../units/collections.py)。
- [PopulationAuthority](../../../core/state/population_authority.py)。
- [RunSession](../../../core/state/run.py)。
- [正式 Project runner](../../../project/project_runner.py)。
- [BlackBase Project 执行与 Case 结果](../../../../blackbase/src/blackbase/project/execution.py)。

索引只链接真实实现，不将这些底座代码复制到 Case。标准薄别名和空包保留脚手架形状，不意味着每个别名都被本次运行调用。
