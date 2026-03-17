# 组件命名审计

## 1. 组件-路径清单

| 文件 | 组件名 | 类型 | 层级 |
|---|---|---|---|
| `catalog/registry.py` | `BuiltinTomlProvider` | `Provider` | `plugins` |
| `catalog/registry.py` | `CatalogProvider` | `Provider` | `plugins` |
| `catalog/registry.py` | `EnvTomlProvider` | `Provider` | `plugins` |
| `examples/_misc_examples/blank_solver_plugin_demo.py` | `RandomWalkPlugin` | `Plugin` | `plugins` |
| `examples/_misc_examples/composable_solver_fusion_demo.py` | `LocalStepAdapter` | `Adapter` | `adapters` |
| `examples/_misc_examples/composable_solver_fusion_demo.py` | `RandomProbeAdapter` | `Adapter` | `adapters` |
| `examples/_misc_examples/composable_solver_fusion_demo.py` | `StepLoggerPlugin` | `Plugin` | `plugins` |
| `examples/_misc_examples/decision_trace_demo.py` | `DecisionSignalPlugin` | `Plugin` | `plugins` |
| `examples/_misc_examples/nested_three_layer_demo.py` | `RandomSearchAdapter` | `Adapter` | `adapters` |
| `examples/_misc_examples/ngspice_inner_demo.py` | `FixedAdapter` | `Adapter` | `adapters` |
| `examples/cases/production_scheduling/adapter/search_adapters.py` | `ProductionACOBaselineAdapter` | `Adapter` | `adapters` |
| `examples/cases/production_scheduling/adapter/search_adapters.py` | `ProductionGreedyBaselineAdapter` | `Adapter` | `adapters` |
| `examples/cases/production_scheduling/adapter/search_adapters.py` | `ProductionLocalSearchAdapter` | `Adapter` | `adapters` |
| `examples/cases/production_scheduling/adapter/search_adapters.py` | `ProductionRandomSearchAdapter` | `Adapter` | `adapters` |
| `examples/cases/production_scheduling/plugins/runtime_plugins.py` | `ConsoleProgressPlugin` | `Plugin` | `plugins` |
| `examples/cases/production_scheduling/plugins/runtime_plugins.py` | `ProductionExportPlugin` | `Plugin` | `plugins` |
| `examples/cases/supply_adjustment_nested/plugins/supply_adjustment_export_plugin.py` | `SupplyAdjustmentExportPlugin` | `Plugin` | `plugins` |
| `representation/base.py` | `CrossoverPlugin` | `Plugin` | `plugins` |
| `representation/base.py` | `EncodingPlugin` | `Plugin` | `plugins` |
| `representation/base.py` | `InitPlugin` | `Plugin` | `plugins` |
| `representation/base.py` | `MutationPlugin` | `Plugin` | `plugins` |
| `representation/base.py` | `RepairPlugin` | `Plugin` | `plugins` |
| `utils/dynamic/cli_provider.py` | `CLISignalProvider` | `Provider` | `plugins` |

## 2. ControllerAdapter 命名规则

- 统一使用 `*ControllerAdapter` 后缀。
- 若为组合控制器，可在名称中体现语义（例如 `PhaseControllerAdapter`）。
