# STABLE_API_SURFACE（稳定入口清单）

本文件把“对外可依赖的稳定入口”收敛成一页，配合：
- `docs/project/API_STABILITY_POLICY.md`
- `docs/CORE_STABILITY.md`
- `catalog/registry.py`

## 1) 最推荐入口（Discoverability）

- CLI：`python -m nsgablack catalog search <query>`
- API：
  - `from nsgablack.catalog import get_catalog`
  - `get_catalog().search(...) / list(...) / get(key)`

## 2) 权威装配（Wiring Helpers）

原则：用户优先依赖 `utils/wiring` 下的 `attach_*` 入口，因为它代表“官方推荐的组合方式”。

- `plugin.benchmark_harness` -> `nsgablack.utils.wiring:attach_benchmark_harness`
- `plugin.module_report` -> `nsgablack.utils.wiring:attach_module_report`
- `utils/wiring/ray_parallel.py` -> `nsgablack.utils.wiring:attach_ray_parallel`（可选依赖）

## 3) 能力层（Plugins）

原则：插件应当是“可插拔、可审计、尽量不改控制流”。

- `plugin.benchmark_harness` -> `nsgablack.utils.plugins:BenchmarkHarnessPlugin`
- `plugin.module_report` -> `nsgablack.utils.plugins:ModuleReportPlugin`
- `plugin.profiler` -> `nsgablack.utils.plugins:ProfilerPlugin`
- `plugin.pareto_archive` -> `nsgablack.utils.plugins:ParetoArchivePlugin`

## 4) 策略层（Adapters）

原则：策略/控制器优先走 adapter；core solver 尽量保持生命周期稳定。

- `adapter.vns` -> `nsgablack.adapters:VNSAdapter`
- `adapter.sa` -> `nsgablack.adapters:SimulatedAnnealingAdapter`
- `adapter.moead` -> `nsgablack.adapters:MOEADAdapter`
- `adapter.multi_strategy` -> `nsgablack.adapters:StrategyRouterAdapter`

## 5) 工程工具（Tools）

- `tool.parallel_evaluator` -> `nsgablack.utils.parallel:ParallelEvaluator`
- `tool.context_keys` -> `nsgablack.core.state:context_keys`
- `tool.context_schema` -> `nsgablack.core.state:MinimalEvaluationContext`

## 6) 明确不承诺稳定的范围

- 历史 `deprecated/legacy/` 内容（目录已从仓库清理；如需追溯请查看 git 历史）
- solver 内部字段/私有方法（除非 wiring/plugin 明确依赖并写入稳定文档）

