# 纯框架主干 API 索引（逐类逐方法，含用途/用法）

> 来源：白名单目录 AST 扫描，仅包含框架主干。
> 白名单：`core/adapters/plugins/representation/bias/utils/catalog/project/nsgablack`

- 扫描文件数：`266`
- 组件（模块+类）数：`389`
- 方法/函数条目总数：`1264`

## 覆盖统计（按顶层目录）

| 顶层目录 | 条目数 |
|---|---:|
| `adapters` | 141 |
| `bias` | 280 |
| `catalog` | 30 |
| `core` | 175 |
| `nsgablack` | 36 |
| `plugins` | 178 |
| `project` | 43 |
| `representation` | 76 |
| `utils` | 305 |

## A. 扁平检索总表（模块 / 类 / 方法 / 用途 / 用法）

| 模块 | 类 | 方法 | 用途 | 用法 |
|---|---|---|---|---|
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `coerce_candidates` | 将输入规范化为 `candidates` 预期格式 | 在接口边界调用以保证 shape/type 一致 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `create_local_rng` | 创建 `local_rng` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `resolve_config` | 解析并确定 `config` 最终结果 | 在多来源配置合并时调用 `obj.resolve_config(...)` |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `set_population` | 写入当前种群快照 | 用于 runtime 插件回写或恢复后对齐 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/algorithm_adapter.py` | `AlgorithmAdapter` | `validate_population_snapshot` | 校验 `population_snapshot` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/algorithm_adapter.py` | `CompositeAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/astar/adapter.py` | `AStarAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/astar/adapter.py` | `AStarAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/astar/adapter.py` | `AStarAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/astar/adapter.py` | `AStarAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/astar/adapter.py` | `AStarAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/async_event_driven/adapter.py` | `AsyncEventDrivenAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `get_population` | 读取当前种群快照 | 给插件/可视化读取运行态 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `set_population` | 写入当前种群快照 | 用于 runtime 插件回写或恢复后对齐 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/differential_evolution/adapter.py` | `DifferentialEvolutionAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/gradient_descent/adapter.py` | `GradientDescentAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/mas/adapter.py` | `MASAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/mas/adapter.py` | `MASAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/mas/adapter.py` | `MASAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/mas/adapter.py` | `MASAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/moa_star/adapter.py` | `MOAStarAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/moa_star/adapter.py` | `MOAStarAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/moa_star/adapter.py` | `MOAStarAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/moa_star/adapter.py` | `MOAStarAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/moa_star/adapter.py` | `MOAStarAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `get_population` | 读取当前种群快照 | 给插件/可视化读取运行态 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `rec` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.rec(...)`，并结合所属类职责使用 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `set_population` | 写入当前种群快照 | 用于 runtime 插件回写或恢复后对齐 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/moead/adapter.py` | `MOEADAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/multi_strategy/adapter.py` | `StrategyRouterAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `get_population` | 读取当前种群快照 | 给插件/可视化读取运行态 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `set_population` | 写入当前种群快照 | 用于 runtime 插件回写或恢复后对齐 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/nsga2/adapter.py` | `NSGA2Adapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/nsga3/adapter.py` | `NSGA3Adapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/pattern_search/adapter.py` | `PatternSearchAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/role_adapters/adapter.py` | `RoleAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/role_adapters/adapter.py` | `RoleRouterAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/serial_strategy/adapter.py` | `StrategyChainAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/serial_strategy/adapter.py` | `StrategyChainAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/serial_strategy/adapter.py` | `StrategyChainAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/serial_strategy/adapter.py` | `StrategyChainAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/serial_strategy/adapter.py` | `StrategyChainAdapter` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `adapters/serial_strategy/adapter.py` | `StrategyChainAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/simulated_annealing/adapter.py` | `SimulatedAnnealingAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/single_trajectory_adaptive/adapter.py` | `SingleTrajectoryAdaptiveAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/trust_region_base/adapter.py` | `TrustRegionBaseAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/trust_region_base/adapter.py` | `TrustRegionBaseAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/trust_region_base/adapter.py` | `TrustRegionBaseAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/trust_region_base/adapter.py` | `TrustRegionBaseAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/trust_region_base/adapter.py` | `TrustRegionBaseAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `get_runtime_context_projection` | 输出可观测运行态切片 | 供插件/UI 获取关键运行指标 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `get_runtime_context_projection_sources` | 读取 `runtime_context_projection_sources` 相关运行态或配置值 | 通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `get_state` | 导出可恢复状态快照 | 用于 checkpoint、断点续跑与调试可视化 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `set_state` | 恢复内部状态 | 在 resume 或迁移运行态时调用 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `adapters/vns/adapter.py` | `VNSAdapter` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `bias/algorithmic/cma_es.py` | `AdaptiveCMAESBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/cma_es.py` | `CMAESBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/convergence.py` | `AdaptiveConvergenceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/convergence.py` | `ConvergenceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/convergence.py` | `LateStageConvergenceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/convergence.py` | `MultiStageConvergenceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/convergence.py` | `PrecisionBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/diversity.py` | `AdaptiveDiversityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/diversity.py` | `CrowdingDistanceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/diversity.py` | `DiversityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/diversity.py` | `DiversityBias` | `get_average_diversity` | 读取 `average_diversity` 相关运行态或配置值 | 通过 `obj.get_average_diversity(...)` 在日志、诊断或编排阶段查询 |
| `bias/algorithmic/diversity.py` | `NicheDiversityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/diversity.py` | `NicheDiversityBias` | `update_niches` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_niches(...)`，并结合所属类职责使用 |
| `bias/algorithmic/diversity.py` | `SharingFunctionBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/levy_flight.py` | `LevyFlightBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/pso.py` | `AdaptivePSOBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/pso.py` | `ParticleSwarmBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/signal_driven/robustness.py` | `RobustnessBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/signal_driven/uncertainty_exploration.py` | `UncertaintyExplorationBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/tabu_search.py` | `TabuSearchBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/algorithmic/template_algorithmic_bias.py` | `ExampleAlgorithmicBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/analytics.py` | `BiasAnalytics` | `generate_report` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.generate_report(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `(module)` | `create_bias_module` | 创建 `bias_module` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/bias_module.py` | `(module)` | `from_universal_manager` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.from_universal_manager(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `(module)` | `improvement_reward` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.improvement_reward(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `(module)` | `proximity_reward` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.proximity_reward(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `add` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `algorithmic_manager` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.algorithmic_manager(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `clear` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `clear_cache` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear_cache(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `compute_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_bias(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `compute_bias_batch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_bias_batch(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `compute_bias_vector` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_bias_vector(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `disable_all` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.disable_all(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `domain_manager` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.domain_manager(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `enable_all` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.enable_all(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `from_universal_manager` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.from_universal_manager(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `get_bias` | 读取 `bias` 相关运行态或配置值 | 通过 `obj.get_bias(...)` 在日志、诊断或编排阶段查询 |
| `bias/bias_module.py` | `BiasModule` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `bias/bias_module.py` | `BiasModule` | `list_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_biases(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `remove_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.remove_bias(...)`，并结合所属类职责使用 |
| `bias/bias_module.py` | `BiasModule` | `set_cache_backend` | 设置 `cache_backend` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_cache_backend(...)` |
| `bias/bias_module.py` | `BiasModule` | `set_cache_context_keys` | 设置 `cache_context_keys` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_cache_context_keys(...)` |
| `bias/bias_module.py` | `BiasModule` | `set_cache_include_generation` | 设置 `cache_include_generation` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_cache_include_generation(...)` |
| `bias/bias_module.py` | `BiasModule` | `set_context_store` | 注入 context 存储实现 | 运行前配置状态存储后端 |
| `bias/bias_module.py` | `BiasModule` | `set_snapshot_store` | 注入 snapshot 存储实现 | 运行前配置大对象快照后端 |
| `bias/bias_module.py` | `BiasModule` | `to_universal_manager` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.to_universal_manager(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `(module)` | `create_bias` | 创建 `bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/core/base.py` | `AlgorithmicBias` | `is_adaptive` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_adaptive(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `AlgorithmicBias` | `reset_to_initial_weight` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset_to_initial_weight(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasBase` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasBase` | `compute_with_tracking` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_with_tracking(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasBase` | `disable` | 禁用功能开关 | 运行中灰度关闭能力 |
| `bias/core/base.py` | `BiasBase` | `enable` | 启用功能开关 | 运行中灰度打开能力 |
| `bias/core/base.py` | `BiasBase` | `finalize_generation` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.finalize_generation(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasBase` | `get_average_bias` | 读取 `average_bias` 相关运行态或配置值 | 通过 `obj.get_average_bias(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasBase` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `bias/core/base.py` | `BiasBase` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasBase` | `get_statistics` | 读取 `statistics` 相关运行态或配置值 | 通过 `obj.get_statistics(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasBase` | `get_weight` | 读取 `weight` 相关运行态或配置值 | 通过 `obj.get_weight(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasBase` | `register_param_change_callback` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_param_change_callback(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasBase` | `reset_statistics` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset_statistics(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasBase` | `set_weight` | 设置 `weight` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_weight(...)` |
| `bias/core/base.py` | `BiasInterface` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasInterface` | `disable` | 禁用功能开关 | 运行中灰度关闭能力 |
| `bias/core/base.py` | `BiasInterface` | `enable` | 启用功能开关 | 运行中灰度打开能力 |
| `bias/core/base.py` | `BiasInterface` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasInterface` | `get_weight` | 读取 `weight` 相关运行态或配置值 | 通过 `obj.get_weight(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasInterface` | `set_weight` | 设置 `weight` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_weight(...)` |
| `bias/core/base.py` | `BiasManager` | `add_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_bias(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasManager` | `compute_total_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `BiasManager` | `get_bias` | 读取 `bias` 相关运行态或配置值 | 通过 `obj.get_bias(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/base.py` | `BiasManager` | `remove_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.remove_bias(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `DomainBias` | `is_mandatory` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_mandatory(...)`，并结合所属类职责使用 |
| `bias/core/base.py` | `OptimizationContext` | `set_constraint_violation` | 设置 `constraint_violation` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_constraint_violation(...)` |
| `bias/core/base.py` | `OptimizationContext` | `set_convergence_status` | 设置 `convergence_status` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_convergence_status(...)` |
| `bias/core/base.py` | `OptimizationContext` | `set_stuck_status` | 设置 `stuck_status` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_stuck_status(...)` |
| `bias/core/manager.py` | `AlgorithmicBiasManager` | `adapt_weights` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.adapt_weights(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `AlgorithmicBiasManager` | `add_algorithmic_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_algorithmic_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `AlgorithmicBiasManager` | `adjust_convergence_weights` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.adjust_convergence_weights(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `AlgorithmicBiasManager` | `adjust_exploration_weights` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.adjust_exploration_weights(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `AlgorithmicBiasManager` | `compute_total_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `AlgorithmicBiasManager` | `reset_adaptive_weights` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset_adaptive_weights(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `BiasManagerMixin` | `add_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `BiasManagerMixin` | `disable_all` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.disable_all(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `BiasManagerMixin` | `enable_all` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.enable_all(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `BiasManagerMixin` | `get_bias` | 读取 `bias` 相关运行态或配置值 | 通过 `obj.get_bias(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/manager.py` | `BiasManagerMixin` | `get_bias_statistics` | 读取 `bias_statistics` 相关运行态或配置值 | 通过 `obj.get_bias_statistics(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/manager.py` | `BiasManagerMixin` | `get_enabled_biases` | 读取 `enabled_biases` 相关运行态或配置值 | 通过 `obj.get_enabled_biases(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/manager.py` | `BiasManagerMixin` | `list_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_biases(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `BiasManagerMixin` | `remove_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.remove_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `DomainBiasManager` | `add_domain_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_domain_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `DomainBiasManager` | `compute_constraint_violation_rate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_constraint_violation_rate(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `DomainBiasManager` | `compute_total_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `DomainBiasManager` | `ensure_mandatory_enabled` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.ensure_mandatory_enabled(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `DomainBiasManager` | `get_mandatory_biases` | 读取 `mandatory_biases` 相关运行态或配置值 | 通过 `obj.get_mandatory_biases(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/manager.py` | `UniversalBiasManager` | `add_algorithmic_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_algorithmic_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `UniversalBiasManager` | `add_domain_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_domain_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `UniversalBiasManager` | `compute_total_algorithmic_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_total_algorithmic_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `UniversalBiasManager` | `compute_total_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `UniversalBiasManager` | `get_comprehensive_statistics` | 读取 `comprehensive_statistics` 相关运行态或配置值 | 通过 `obj.get_comprehensive_statistics(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/manager.py` | `UniversalBiasManager` | `load_configuration` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_configuration(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `UniversalBiasManager` | `reset_all_statistics` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset_all_statistics(...)`，并结合所属类职责使用 |
| `bias/core/manager.py` | `UniversalBiasManager` | `save_configuration` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.save_configuration(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `(module)` | `decorator` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decorator(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `(module)` | `get_bias_registry` | 读取 `bias_registry` 相关运行态或配置值 | 通过 `obj.get_bias_registry(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/registry.py` | `(module)` | `register_algorithmic_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_algorithmic_bias(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `(module)` | `register_bias_factory` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_bias_factory(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `(module)` | `register_domain_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_domain_bias(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `create_algorithmic_bias` | 创建 `algorithmic_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/core/registry.py` | `BiasRegistry` | `create_bias_from_factory` | 创建 `bias_from_factory` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/core/registry.py` | `BiasRegistry` | `create_domain_bias` | 创建 `domain_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/core/registry.py` | `BiasRegistry` | `get_bias_documentation` | 读取 `bias_documentation` 相关运行态或配置值 | 通过 `obj.get_bias_documentation(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/registry.py` | `BiasRegistry` | `get_bias_info` | 读取 `bias_info` 相关运行态或配置值 | 通过 `obj.get_bias_info(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/registry.py` | `BiasRegistry` | `get_biases_in_category` | 读取 `biases_in_category` 相关运行态或配置值 | 通过 `obj.get_biases_in_category(...)` 在日志、诊断或编排阶段查询 |
| `bias/core/registry.py` | `BiasRegistry` | `list_algorithmic_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_algorithmic_biases(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `list_bias_factories` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_bias_factories(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `list_categories` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_categories(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `list_domain_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_domain_biases(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `register_algorithmic_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_algorithmic_bias(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `register_bias_factory` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_bias_factory(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `register_domain_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_domain_bias(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `search_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search_biases(...)`，并结合所属类职责使用 |
| `bias/core/registry.py` | `BiasRegistry` | `validate_bias_registration` | 校验 `bias_registration` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/domain/callable_bias.py` | `CallableBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `ConstraintBias` | `add_constraint` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_constraint(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `ConstraintBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `ConstraintBias` | `get_violation_statistics` | 读取 `violation_statistics` 相关运行态或配置值 | 通过 `obj.get_violation_statistics(...)` 在日志、诊断或编排阶段查询 |
| `bias/domain/constraint.py` | `FeasibilityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `PreferenceBias` | `add_preference_function` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_preference_function(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `PreferenceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `RuleBasedBias` | `add_rule` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_rule(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `RuleBasedBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/constraint.py` | `RuleBasedBias` | `get_rule_statistics` | 读取 `rule_statistics` 相关运行态或配置值 | 通过 `obj.get_rule_statistics(...)` 在日志、诊断或编排阶段查询 |
| `bias/domain/dynamic_penalty.py` | `DynamicPenaltyBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/engineering.py` | `EngineeringDesignBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/engineering.py` | `ManufacturingBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/engineering.py` | `SafetyBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/risk_bias.py` | `RiskBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/scheduling.py` | `ResourceConstraintBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/scheduling.py` | `SchedulingBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/scheduling.py` | `TimeWindowBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/structure_prior.py` | `StructurePriorBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/domain/template_domain_bias.py` | `ExampleDomainBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/library.py` | `(module)` | `create_bias_manager_from_template` | 创建 `bias_manager_from_template` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/library.py` | `(module)` | `quick_engineering_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.quick_engineering_bias(...)`，并结合所属类职责使用 |
| `bias/library.py` | `(module)` | `quick_financial_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.quick_financial_bias(...)`，并结合所属类职责使用 |
| `bias/library.py` | `(module)` | `quick_ml_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.quick_ml_bias(...)`，并结合所属类职责使用 |
| `bias/library.py` | `BiasComposer` | `add_algorithmic_bias_from_config` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_algorithmic_bias_from_config(...)`，并结合所属类职责使用 |
| `bias/library.py` | `BiasComposer` | `add_domain_bias_from_config` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_domain_bias_from_config(...)`，并结合所属类职责使用 |
| `bias/library.py` | `BiasComposer` | `build` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.build(...)`，并结合所属类职责使用 |
| `bias/library.py` | `BiasFactory` | `create_algorithmic_bias` | 创建 `algorithmic_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/library.py` | `BiasFactory` | `create_domain_bias` | 创建 `domain_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/library.py` | `BiasFactory` | `list_available_algorithmic_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_available_algorithmic_biases(...)`，并结合所属类职责使用 |
| `bias/library.py` | `BiasFactory` | `list_available_domain_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_available_domain_biases(...)`，并结合所属类职责使用 |
| `bias/library.py` | `_GenericAlgorithmicBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/library.py` | `_GenericDomainBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/managers/adaptive_manager.py` | `AdaptiveAlgorithmicManager` | `add_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_bias(...)`，并结合所属类职责使用 |
| `bias/managers/adaptive_manager.py` | `AdaptiveAlgorithmicManager` | `get_adaptation_history` | 读取 `adaptation_history` 相关运行态或配置值 | 通过 `obj.get_adaptation_history(...)` 在日志、诊断或编排阶段查询 |
| `bias/managers/adaptive_manager.py` | `AdaptiveAlgorithmicManager` | `update_state` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_state(...)`，并结合所属类职责使用 |
| `bias/managers/analytics.py` | `BiasEffectivenessAnalyzer` | `evaluate_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_bias(...)`，并结合所属类职责使用 |
| `bias/managers/analytics.py` | `BiasEffectivenessAnalyzer` | `export_metrics_to_csv` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.export_metrics_to_csv(...)`，并结合所属类职责使用 |
| `bias/managers/analytics.py` | `BiasEffectivenessAnalyzer` | `plot_bias_comparison` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.plot_bias_comparison(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `MetaLearningBiasSelector` | `add_historical_data` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_historical_data(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `MetaLearningBiasSelector` | `export_database` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.export_database(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `MetaLearningBiasSelector` | `import_database` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_database(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `MetaLearningBiasSelector` | `load_models` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_models(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `MetaLearningBiasSelector` | `recommend_biases` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.recommend_biases(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `MetaLearningBiasSelector` | `train_models` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.train_models(...)`，并结合所属类职责使用 |
| `bias/managers/meta_learning_selector.py` | `ProblemFeatureExtractor` | `extract_features` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.extract_features(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `(module)` | `create_bayesian_convergence_bias` | 创建 `bayesian_convergence_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/bayesian_biases.py` | `(module)` | `create_bayesian_exploration_bias` | 创建 `bayesian_exploration_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/bayesian_biases.py` | `(module)` | `create_bayesian_guidance_bias` | 创建 `bayesian_guidance_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/bayesian_biases.py` | `(module)` | `create_bayesian_suite` | 创建 `bayesian_suite` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/bayesian_biases.py` | `BayesianConvergenceBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `BayesianExplorationBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `BayesianExplorationBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `BayesianGuidanceBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `BayesianGuidanceBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `SimpleBayesianOptimizer` | `observe` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.observe(...)`，并结合所属类职责使用 |
| `bias/specialized/bayesian_biases.py` | `SimpleBayesianOptimizer` | `reset` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset(...)`，并结合所属类职责使用 |
| `bias/specialized/engineering.py` | `(module)` | `create_engineering_bias_suite` | 创建 `engineering_bias_suite` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/engineering.py` | `(module)` | `create_engineering_constraint_bias` | 创建 `engineering_constraint_bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/engineering.py` | `EngineeringConstraintBias` | `add_engineering_constraint` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_engineering_constraint(...)`，并结合所属类职责使用 |
| `bias/specialized/engineering.py` | `EngineeringConstraintBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/engineering.py` | `EngineeringConstraintBias` | `get_constraint_status` | 读取 `constraint_status` 相关运行态或配置值 | 通过 `obj.get_constraint_status(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/engineering.py` | `EngineeringPrecisionBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/engineering.py` | `EngineeringRobustnessBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `AbstractGraphProblem` | `decode_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `AbstractGraphProblem` | `evaluate_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `AbstractGraphProblem` | `get_encoding` | 读取 `encoding` 相关运行态或配置值 | 通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `AbstractGraphProblem` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `AbstractGraphProblem` | `validate_solution` | 校验 `solution` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/abstract.py` | `BinaryEdgesGraphProblem` | `decode_edges` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_edges(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `BinaryEdgesGraphProblem` | `decode_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `BinaryEdgesGraphProblem` | `get_encoding` | 读取 `encoding` 相关运行态或配置值 | 通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `CompositeGraphProblem` | `add_subproblem` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_subproblem(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `CompositeGraphProblem` | `decode_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `CompositeGraphProblem` | `evaluate_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `CompositeGraphProblem` | `get_encoding` | 读取 `encoding` 相关运行态或配置值 | 通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `CompositeGraphProblem` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `CompositeGraphProblem` | `validate_solution` | 校验 `solution` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/abstract.py` | `GraphColoringProblem` | `evaluate_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `GraphColoringProblem` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `GraphColoringProblem` | `validate_solution` | 校验 `solution` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/abstract.py` | `GraphProblemFactory` | `create_graph_coloring` | 创建 `graph_coloring` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/graph/abstract.py` | `GraphProblemFactory` | `create_hamiltonian_path` | 创建 `hamiltonian_path` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/graph/abstract.py` | `GraphProblemFactory` | `create_spanning_tree` | 创建 `spanning_tree` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/graph/abstract.py` | `GraphProblemFactory` | `create_tsp` | 创建 `tsp` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/graph/abstract.py` | `GraphProblemFactory` | `get_available_problems` | 读取 `available_problems` 相关运行态或配置值 | 通过 `obj.get_available_problems(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `HamiltonianPathProblem` | `evaluate_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `HamiltonianPathProblem` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `HamiltonianPathProblem` | `validate_solution` | 校验 `solution` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/abstract.py` | `PartitionGraphProblem` | `decode_partition` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_partition(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `PartitionGraphProblem` | `decode_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `PartitionGraphProblem` | `get_encoding` | 读取 `encoding` 相关运行态或配置值 | 通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `PermutationGraphProblem` | `decode_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `PermutationGraphProblem` | `get_encoding` | 读取 `encoding` 相关运行态或配置值 | 通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `PermutationGraphProblem` | `validate_permutation_constraints` | 校验 `permutation_constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/abstract.py` | `SpanningTreeProblem` | `evaluate_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `SpanningTreeProblem` | `find` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.find(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `SpanningTreeProblem` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `SpanningTreeProblem` | `union` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.union(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `SpanningTreeProblem` | `validate_solution` | 校验 `solution` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/abstract.py` | `TSPProblem` | `evaluate_solution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/abstract.py` | `TSPProblem` | `get_name` | 读取 `name` 相关运行态或配置值 | 通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/abstract.py` | `TSPProblem` | `validate_solution` | 校验 `solution` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/base.py` | `CommunityDetectionBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `ConnectivityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `DegreeDistributionBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `GraphBias` | `encode_solution_to_graph` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.encode_solution_to_graph(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `GraphBiasFactory` | `create_bias` | 创建 `bias` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/graph/base.py` | `GraphBiasFactory` | `get_available_biases` | 读取 `available_biases` 相关运行态或配置值 | 通过 `obj.get_available_biases(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/base.py` | `GraphColoringBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `GraphColoringBias` | `encode_solution_to_graph` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.encode_solution_to_graph(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `GraphUtils` | `compute_graph_properties` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_graph_properties(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `GraphUtils` | `extract_subgraph` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.extract_subgraph(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `MaxFlowBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `ShortestPathBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/base.py` | `SparsityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/constraints.py` | `CompositeGraphConstraintBias` | `add_constraint` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_constraint(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/constraints.py` | `CompositeGraphConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `GraphColoringConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `GraphConstraintBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/constraints.py` | `GraphConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `GraphConstraintFactory` | `create_constraint` | 创建 `constraint` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/graph/constraints.py` | `GraphConstraintFactory` | `get_available_constraints` | 读取 `available_constraints` 相关运行态或配置值 | 通过 `obj.get_available_constraints(...)` 在日志、诊断或编排阶段查询 |
| `bias/specialized/graph/constraints.py` | `HamiltonianPathConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `MatchingConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `PathConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `TSPConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/graph/constraints.py` | `TreeConstraintBias` | `find` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.find(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/constraints.py` | `TreeConstraintBias` | `union` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.union(...)`，并结合所属类职责使用 |
| `bias/specialized/graph/constraints.py` | `TreeConstraintBias` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `bias/specialized/local_search.py` | `(module)` | `create_derivative_free_suite` | 创建 `derivative_free_suite` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/local_search.py` | `(module)` | `create_gradient_descent_suite` | 创建 `gradient_descent_suite` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/local_search.py` | `(module)` | `create_hybrid_local_suite` | 创建 `hybrid_local_suite` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/local_search.py` | `(module)` | `create_newton_suite` | 创建 `newton_suite` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/specialized/local_search.py` | `GradientDescentBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/local_search.py` | `LineSearchBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/local_search.py` | `NelderMeadBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/local_search.py` | `NewtonMethodBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/local_search.py` | `QuasiNewtonBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/local_search.py` | `TrustRegionBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/specialized/production/scheduling.py` | `ProductionConstraintBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/production/scheduling.py` | `ProductionContinuityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/production/scheduling.py` | `ProductionDiversityBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/production/scheduling.py` | `ProductionSchedulingBias` | `compute` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute(...)`，并结合所属类职责使用 |
| `bias/specialized/production/scheduling.py` | `ProductionSchedulingBiasManager` | `compute_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_bias(...)`，并结合所属类职责使用 |
| `bias/surrogate/base.py` | `SurrogateBiasContext` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `bias/surrogate/base.py` | `SurrogateBiasContext` | `progress` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.progress(...)`，并结合所属类职责使用 |
| `bias/surrogate/base.py` | `SurrogateControlBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/surrogate/base.py` | `SurrogateControlBias` | `should_apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.should_apply(...)`，并结合所属类职责使用 |
| `bias/surrogate/phase_schedule.py` | `PhaseScheduleBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/surrogate/template_surrogate_bias.py` | `ExampleSurrogateBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/surrogate/uncertainty_budget.py` | `UncertaintyBudgetBias` | `apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply(...)`，并结合所属类职责使用 |
| `bias/surrogate/uncertainty_budget.py` | `UncertaintyBudgetBias` | `should_apply` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.should_apply(...)`，并结合所属类职责使用 |
| `bias/utils/helpers.py` | `(module)` | `create_universal_bias_manager` | 创建 `universal_bias_manager` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `bias/utils/helpers.py` | `(module)` | `get_bias_system_info` | 读取 `bias_system_info` 相关运行态或配置值 | 通过 `obj.get_bias_system_info(...)` 在日志、诊断或编排阶段查询 |
| `bias/utils/helpers.py` | `(module)` | `quick_bias_setup` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.quick_bias_setup(...)`，并结合所属类职责使用 |
| `catalog/__init__.py` | `(module)` | `get_entry` | 读取 `entry` 相关运行态或配置值 | 通过 `obj.get_entry(...)` 在日志、诊断或编排阶段查询 |
| `catalog/__init__.py` | `(module)` | `list_catalog` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_catalog(...)`，并结合所属类职责使用 |
| `catalog/__init__.py` | `(module)` | `reload_catalog` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reload_catalog(...)`，并结合所属类职责使用 |
| `catalog/__init__.py` | `(module)` | `search_catalog` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search_catalog(...)`，并结合所属类职责使用 |
| `catalog/markers.py` | `(module)` | `component` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.component(...)`，并结合所属类职责使用 |
| `catalog/quick_add.py` | `(module)` | `build_entry_payload` | 构建 `entry_payload` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `catalog/quick_add.py` | `(module)` | `main` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.main(...)`，并结合所属类职责使用 |
| `catalog/quick_add.py` | `(module)` | `remove_catalog_entry` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.remove_catalog_entry(...)`，并结合所属类职责使用 |
| `catalog/quick_add.py` | `(module)` | `render_entry_block` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.render_entry_block(...)`，并结合所属类职责使用 |
| `catalog/quick_add.py` | `(module)` | `upsert_catalog_entry` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.upsert_catalog_entry(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `(module)` | `get_catalog` | 读取 `catalog` 相关运行态或配置值 | 通过 `obj.get_catalog(...)` 在日志、诊断或编排阶段查询 |
| `catalog/registry.py` | `(module)` | `parse_items` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.parse_items(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `BuiltinTomlProvider` | `load` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `Catalog` | `add_field` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_field(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `Catalog` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `Catalog` | `list` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `Catalog` | `match` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.match(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `Catalog` | `rank` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.rank(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `Catalog` | `search` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `CatalogEntry` | `load` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `CatalogProvider` | `load` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load(...)`，并结合所属类职责使用 |
| `catalog/registry.py` | `EnvTomlProvider` | `load` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load(...)`，并结合所属类职责使用 |
| `catalog/source_sync.py` | `(module)` | `apply_symbol_contract` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply_symbol_contract(...)`，并结合所属类职责使用 |
| `catalog/source_sync.py` | `(module)` | `detect_expansion_scope` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.detect_expansion_scope(...)`，并结合所属类职责使用 |
| `catalog/source_sync.py` | `(module)` | `expand_marked_component_template` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.expand_marked_component_template(...)`，并结合所属类职责使用 |
| `catalog/source_sync.py` | `(module)` | `list_source_symbols` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_source_symbols(...)`，并结合所属类职责使用 |
| `catalog/source_sync.py` | `(module)` | `read_symbol_contract` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read_symbol_contract(...)`，并结合所属类职责使用 |
| `catalog/usage.py` | `(module)` | `build_usage_profile` | 构建 `usage_profile` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `catalog/usage.py` | `(module)` | `enrich_context_contracts` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.enrich_context_contracts(...)`，并结合所属类职责使用 |
| `catalog/usage.py` | `(module)` | `enrich_usage_contracts` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.enrich_usage_contracts(...)`，并结合所属类职责使用 |
| `core/acceleration.py` | `AccelerationBackend` | `run` | 执行完整生命周期主流程 | 直接调用 `instance.run(...)` 作为入口 |
| `core/acceleration.py` | `AccelerationFacade` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `core/acceleration.py` | `AccelerationFacade` | `list_backends` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_backends(...)`，并结合所属类职责使用 |
| `core/acceleration.py` | `AccelerationFacade` | `register` | 注册组件到管理器 | 初始化时挂载插件/子组件 |
| `core/acceleration.py` | `AccelerationRegistry` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `core/acceleration.py` | `AccelerationRegistry` | `global_registry` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.global_registry(...)`，并结合所属类职责使用 |
| `core/acceleration.py` | `AccelerationRegistry` | `list_backends` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_backends(...)`，并结合所属类职责使用 |
| `core/acceleration.py` | `AccelerationRegistry` | `register` | 注册组件到管理器 | 初始化时挂载插件/子组件 |
| `core/acceleration.py` | `NoopAccelerationBackend` | `run` | 执行完整生命周期主流程 | 直接调用 `instance.run(...)` 作为入口 |
| `core/base.py` | `BlackBoxProblem` | `evaluate` | 执行问题评估并产出目标值 | 由评估链路调用，输入单个 candidate |
| `core/base.py` | `BlackBoxProblem` | `evaluate_constraints` | 计算约束违背信息 | 在目标评估后统一汇总 violation |
| `core/base.py` | `BlackBoxProblem` | `get_num_objectives` | 读取 `num_objectives` 相关运行态或配置值 | 通过 `obj.get_num_objectives(...)` 在日志、诊断或编排阶段查询 |
| `core/base.py` | `BlackBoxProblem` | `is_multiobjective` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_multiobjective(...)`，并结合所属类职责使用 |
| `core/base.py` | `BlackBoxProblem` | `is_valid` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_valid(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `add_plugin` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_plugin(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `bias_module` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.bias_module(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `build_context` | 构建 `context` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `core/blank_solver.py` | `SolverBase` | `decode_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decode_candidate(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `enable_bias_module` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.enable_bias_module(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `encode_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.encode_candidate(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `core/blank_solver.py` | `SolverBase` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `core/blank_solver.py` | `SolverBase` | `fork_rng` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.fork_rng(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `get_acceleration_backend` | 读取 `acceleration_backend` 相关运行态或配置值 | 通过 `obj.get_acceleration_backend(...)` 在日志、诊断或编排阶段查询 |
| `core/blank_solver.py` | `SolverBase` | `get_best_snapshot` | 读取 `best_snapshot` 相关运行态或配置值 | 通过 `obj.get_best_snapshot(...)` 在日志、诊断或编排阶段查询 |
| `core/blank_solver.py` | `SolverBase` | `get_context` | 读取 `context` 相关运行态或配置值 | 通过 `obj.get_context(...)` 在日志、诊断或编排阶段查询 |
| `core/blank_solver.py` | `SolverBase` | `get_plugin` | 读取 `plugin` 相关运行态或配置值 | 通过 `obj.get_plugin(...)` 在日志、诊断或编排阶段查询 |
| `core/blank_solver.py` | `SolverBase` | `get_rng_state` | 读取 `rng_state` 相关运行态或配置值 | 通过 `obj.get_rng_state(...)` 在日志、诊断或编排阶段查询 |
| `core/blank_solver.py` | `SolverBase` | `has_bias_support` | 判断是否具备 `bias_support` 能力 | 在装配分支中调用并据此选择能力路径 |
| `core/blank_solver.py` | `SolverBase` | `has_numba_support` | 判断是否具备 `numba_support` 能力 | 在装配分支中调用并据此选择能力路径 |
| `core/blank_solver.py` | `SolverBase` | `increment_evaluation_count` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.increment_evaluation_count(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `init_bias_module` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.init_bias_module(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `init_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.init_candidate(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `initialize_population` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.initialize_population(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `mutate_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.mutate_candidate(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `read_snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read_snapshot(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `register_acceleration_backend` | 注册加速后端 | 并行/硬件加速能力接入 |
| `core/blank_solver.py` | `SolverBase` | `register_controller` | 注册控制器到控制平面 | 接入 stopping/switch/budget 控制逻辑 |
| `core/blank_solver.py` | `SolverBase` | `register_evaluation_provider` | 注册 L4 评估提供器 | 接入 surrogate/multi-fidelity 等路径 |
| `core/blank_solver.py` | `SolverBase` | `remove_plugin` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.remove_plugin(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `repair_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.repair_candidate(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `representation_pipeline` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.representation_pipeline(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `request_plugin_order` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_plugin_order(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `request_stop` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_stop(...)`，并结合所属类职责使用 |
| `core/blank_solver.py` | `SolverBase` | `run` | 执行完整生命周期主流程 | 直接调用 `instance.run(...)` 作为入口 |
| `core/blank_solver.py` | `SolverBase` | `set_adapter` | 设置主适配器 | solver 装配或切换算法时调用 |
| `core/blank_solver.py` | `SolverBase` | `set_best_snapshot` | 设置 `best_snapshot` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_best_snapshot(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_bias_enabled` | 设置 `bias_enabled` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_bias_enabled(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_bias_module` | 设置 `bias_module` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_bias_module(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_context_store` | 注入 context 存储实现 | 运行前配置状态存储后端 |
| `core/blank_solver.py` | `SolverBase` | `set_context_store_backend` | 设置 `context_store_backend` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_context_store_backend(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_generation` | 设置 `generation` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_generation(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_max_steps` | 设置 `max_steps` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_max_steps(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_pareto_snapshot` | 设置 `pareto_snapshot` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_pareto_snapshot(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_phase_controller` | 设置 `phase_controller` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_phase_controller(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_plugin_order` | 设置 `plugin_order` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_plugin_order(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_random_seed` | 设置 `random_seed` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_random_seed(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_representation_pipeline` | 设置 `representation_pipeline` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_representation_pipeline(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_rng_state` | 设置 `rng_state` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_rng_state(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_snapshot_store` | 注入 snapshot 存储实现 | 运行前配置大对象快照后端 |
| `core/blank_solver.py` | `SolverBase` | `set_snapshot_store_backend` | 设置 `snapshot_store_backend` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_snapshot_store_backend(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_solver_hyperparams` | 设置 `solver_hyperparams` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_solver_hyperparams(...)` |
| `core/blank_solver.py` | `SolverBase` | `set_strategy_controller` | 设置 `strategy_controller` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_strategy_controller(...)` |
| `core/blank_solver.py` | `SolverBase` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `core/blank_solver.py` | `SolverBase` | `step` | 执行一个离散迭代步 | 用于调试或外部细粒度驱动 |
| `core/blank_solver.py` | `SolverBase` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `core/blank_solver.py` | `SolverBase` | `validate_control_plane` | 校验 `control_plane` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/blank_solver.py` | `SolverBase` | `validate_plugin_order` | 校验 `plugin_order` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/blank_solver.py` | `SolverBase` | `write_population_snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.write_population_snapshot(...)`，并结合所属类职责使用 |
| `core/composable_solver.py` | `ComposableSolver` | `select_best` | 选择 `best` 候选或策略 | 在决策阶段调用，根据上下文返回最优分支 |
| `core/composable_solver.py` | `ComposableSolver` | `set_adapter` | 设置主适配器 | solver 装配或切换算法时调用 |
| `core/composable_solver.py` | `ComposableSolver` | `set_adapters` | 设置 `adapters` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_adapters(...)` |
| `core/composable_solver.py` | `ComposableSolver` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `core/composable_solver.py` | `ComposableSolver` | `step` | 执行一个离散迭代步 | 用于调试或外部细粒度驱动 |
| `core/composable_solver.py` | `ComposableSolver` | `teardown` | 释放资源并收尾持久化 | 在 `run` 结束后自动调用，可用于 flush/report |
| `core/control_plane.py` | `BaseController` | `propose` | 生成待评估候选解 | 由 solver 在评估前调用，返回候选序列 |
| `core/control_plane.py` | `ControlArbiter` | `resolve` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.resolve(...)`，并结合所属类职责使用 |
| `core/control_plane.py` | `RuntimeController` | `collect` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.collect(...)`，并结合所属类职责使用 |
| `core/control_plane.py` | `RuntimeController` | `list_controllers` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_controllers(...)`，并结合所属类职责使用 |
| `core/control_plane.py` | `RuntimeController` | `register_controller` | 注册控制器到控制平面 | 接入 stopping/switch/budget 控制逻辑 |
| `core/control_plane.py` | `RuntimeController` | `resolve` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.resolve(...)`，并结合所属类职责使用 |
| `core/control_plane.py` | `RuntimeController` | `validate_configuration` | 校验 `configuration` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/evaluation_runtime.py` | `EvaluationMediator` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `core/evaluation_runtime.py` | `EvaluationMediator` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `core/evaluation_runtime.py` | `EvaluationMediator` | `list_providers` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_providers(...)`，并结合所属类职责使用 |
| `core/evaluation_runtime.py` | `EvaluationMediator` | `register_provider` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_provider(...)`，并结合所属类职责使用 |
| `core/evaluation_runtime.py` | `EvaluationProvider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `core/evaluation_runtime.py` | `EvaluationProvider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `core/evaluation_runtime.py` | `EvaluationProvider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `core/evaluation_runtime.py` | `EvaluationProvider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `core/evolution_solver.py` | `EvolutionSolver` | `crossover` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.crossover(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `environmental_selection` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.environmental_selection(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `core/evolution_solver.py` | `EvolutionSolver` | `initialize_population` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.initialize_population(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `core/evolution_solver.py` | `EvolutionSolver` | `non_dominated_sorting` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.non_dominated_sorting(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `record_history` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_history(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `representation_pipeline` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.representation_pipeline(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `run` | 执行完整生命周期主流程 | 直接调用 `instance.run(...)` 作为入口 |
| `core/evolution_solver.py` | `EvolutionSolver` | `selection` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.selection(...)`，并结合所属类职责使用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `set_adapter` | 设置主适配器 | solver 装配或切换算法时调用 |
| `core/evolution_solver.py` | `EvolutionSolver` | `set_context_store` | 注入 context 存储实现 | 运行前配置状态存储后端 |
| `core/evolution_solver.py` | `EvolutionSolver` | `set_context_store_backend` | 设置 `context_store_backend` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_context_store_backend(...)` |
| `core/evolution_solver.py` | `EvolutionSolver` | `set_snapshot_store` | 注入 snapshot 存储实现 | 运行前配置大对象快照后端 |
| `core/evolution_solver.py` | `EvolutionSolver` | `set_snapshot_store_backend` | 设置 `snapshot_store_backend` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_snapshot_store_backend(...)` |
| `core/evolution_solver.py` | `EvolutionSolver` | `set_solver_hyperparams` | 设置 `solver_hyperparams` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_solver_hyperparams(...)` |
| `core/evolution_solver.py` | `EvolutionSolver` | `setup` | 初始化组件运行态并绑定上下文 | 在 `run/setup` 阶段由框架调用，通常不手工频繁触发 |
| `core/evolution_solver.py` | `EvolutionSolver` | `step` | 执行一个离散迭代步 | 用于调试或外部细粒度驱动 |
| `core/evolution_solver.py` | `EvolutionSolver` | `update_pareto_solutions` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_pareto_solutions(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `(module)` | `create_bias_context` | 创建 `bias_context` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `core/interfaces.py` | `(module)` | `has_bias_module` | 判断是否具备 `bias_module` 能力 | 在装配分支中调用并据此选择能力路径 |
| `core/interfaces.py` | `(module)` | `has_numba` | 判断是否具备 `numba` 能力 | 在装配分支中调用并据此选择能力路径 |
| `core/interfaces.py` | `(module)` | `has_representation_module` | 判断是否具备 `representation_module` 能力 | 在装配分支中调用并据此选择能力路径 |
| `core/interfaces.py` | `(module)` | `has_visualization_module` | 判断是否具备 `visualization_module` 能力 | 在装配分支中调用并据此选择能力路径 |
| `core/interfaces.py` | `(module)` | `load_bias_module` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_bias_module(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `(module)` | `load_representation_pipeline` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_representation_pipeline(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `BiasInterface` | `add_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_bias(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `BiasInterface` | `compute_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compute_bias(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `BiasInterface` | `disable` | 禁用功能开关 | 运行中灰度关闭能力 |
| `core/interfaces.py` | `BiasInterface` | `enable` | 启用功能开关 | 运行中灰度打开能力 |
| `core/interfaces.py` | `BiasInterface` | `is_enabled` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_enabled(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `ExperimentResultInterface` | `add_result` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_result(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `ExperimentResultInterface` | `save` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.save(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `ExperimentResultInterface` | `to_dict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.to_dict(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `OptimizationContext` | `get_statistics` | 读取 `statistics` 相关运行态或配置值 | 通过 `obj.get_statistics(...)` 在日志、诊断或编排阶段查询 |
| `core/interfaces.py` | `PluginInterface` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `core/interfaces.py` | `PluginInterface` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `core/interfaces.py` | `PluginInterface` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `core/interfaces.py` | `PluginInterface` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `core/interfaces.py` | `PluginInterface` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `core/interfaces.py` | `PluginInterface` | `on_step` | 步级别钩子 | 需要更细粒度监控时使用 |
| `core/interfaces.py` | `RepresentationInterface` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `core/interfaces.py` | `RepresentationInterface` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `core/interfaces.py` | `RepresentationInterface` | `init` | 初始化候选或批次 | solver 初始化种群时触发 |
| `core/interfaces.py` | `RepresentationInterface` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `core/interfaces.py` | `RepresentationInterface` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `core/interfaces.py` | `RepresentationInterface` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `core/interfaces.py` | `SimpleContext` | `get_statistics` | 读取 `statistics` 相关运行态或配置值 | 通过 `obj.get_statistics(...)` 在日志、诊断或编排阶段查询 |
| `core/interfaces.py` | `VisualizationInterface` | `plot_convergence` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.plot_convergence(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `VisualizationInterface` | `plot_diversity` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.plot_diversity(...)`，并结合所属类职责使用 |
| `core/interfaces.py` | `VisualizationInterface` | `plot_pareto_front` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.plot_pareto_front(...)`，并结合所属类职责使用 |
| `core/nested_solver.py` | `InnerRuntimeEvaluator` | `can_handle` | 判断当前是否可执行 `handle` | 在执行前先调用，返回布尔值决定是否继续 |
| `core/nested_solver.py` | `InnerRuntimeEvaluator` | `evaluate` | 执行问题评估并产出目标值 | 由评估链路调用，输入单个 candidate |
| `core/nested_solver.py` | `TaskInnerRuntimeEvaluator` | `can_handle` | 判断当前是否可执行 `handle` | 在执行前先调用，返回布尔值决定是否继续 |
| `core/nested_solver.py` | `TaskInnerRuntimeEvaluator` | `evaluate` | 执行问题评估并产出目标值 | 由评估链路调用，输入单个 candidate |
| `core/solver_helpers/bias_helpers.py` | `(module)` | `apply_bias_module` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply_bias_module(...)`，并结合所属类职责使用 |
| `core/solver_helpers/candidate_helpers.py` | `(module)` | `sample_random_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.sample_random_candidate(...)`，并结合所属类职责使用 |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `register_component` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_component(...)`，并结合所属类职责使用 |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `resolve_order` | 解析并确定 `order` 最终结果 | 在多来源配置合并时调用 `obj.resolve_order(...)` |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `resolve_order_strict` | 解析并确定 `order_strict` 最终结果 | 在多来源配置合并时调用 `obj.resolve_order_strict(...)` |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `restore_rules` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.restore_rules(...)`，并结合所属类职责使用 |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `set_constraints` | 设置 `constraints` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_constraints(...)` |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `snapshot_rules` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot_rules(...)`，并结合所属类职责使用 |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `unregister_component` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.unregister_component(...)`，并结合所属类职责使用 |
| `core/solver_helpers/component_scheduler.py` | `ComponentDependencyScheduler` | `validate_constraints` | 校验 `constraints` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/solver_helpers/context_helpers.py` | `(module)` | `build_solver_context` | 构建 `solver_context` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `core/solver_helpers/context_helpers.py` | `(module)` | `ensure_snapshot_readable` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.ensure_snapshot_readable(...)`，并结合所属类职责使用 |
| `core/solver_helpers/context_helpers.py` | `(module)` | `get_solver_context_view` | 读取 `solver_context_view` 相关运行态或配置值 | 通过 `obj.get_solver_context_view(...)` 在日志、诊断或编排阶段查询 |
| `core/solver_helpers/control_plane_helpers.py` | `(module)` | `collect_runtime_context_projection` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.collect_runtime_context_projection(...)`，并结合所属类职责使用 |
| `core/solver_helpers/control_plane_helpers.py` | `(module)` | `get_best_snapshot_fields` | 读取 `best_snapshot_fields` 相关运行态或配置值 | 通过 `obj.get_best_snapshot_fields(...)` 在日志、诊断或编排阶段查询 |
| `core/solver_helpers/control_plane_helpers.py` | `(module)` | `increment_evaluation_counter` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.increment_evaluation_counter(...)`，并结合所属类职责使用 |
| `core/solver_helpers/control_plane_helpers.py` | `(module)` | `set_best_snapshot_fields` | 设置 `best_snapshot_fields` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_best_snapshot_fields(...)` |
| `core/solver_helpers/control_plane_helpers.py` | `(module)` | `set_generation_value` | 设置 `generation_value` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_generation_value(...)` |
| `core/solver_helpers/control_plane_helpers.py` | `(module)` | `set_pareto_snapshot_fields` | 设置 `pareto_snapshot_fields` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_pareto_snapshot_fields(...)` |
| `core/solver_helpers/evaluation_helpers.py` | `(module)` | `evaluate_individual_with_plugins_and_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_individual_with_plugins_and_bias(...)`，并结合所属类职责使用 |
| `core/solver_helpers/evaluation_helpers.py` | `(module)` | `evaluate_population_with_plugins_and_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_population_with_plugins_and_bias(...)`，并结合所属类职责使用 |
| `core/solver_helpers/result_helpers.py` | `(module)` | `format_run_result` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.format_run_result(...)`，并结合所属类职责使用 |
| `core/solver_helpers/run_helpers.py` | `(module)` | `apply_runtime_control_slot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply_runtime_control_slot(...)`，并结合所属类职责使用 |
| `core/solver_helpers/run_helpers.py` | `(module)` | `run_solver_loop` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_solver_loop(...)`，并结合所属类职责使用 |
| `core/solver_helpers/snapshot_helpers.py` | `(module)` | `build_snapshot_payload` | 构建 `snapshot_payload` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `core/solver_helpers/snapshot_helpers.py` | `(module)` | `build_snapshot_refs` | 构建 `snapshot_refs` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `core/solver_helpers/snapshot_helpers.py` | `(module)` | `snapshot_meta` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot_meta(...)`，并结合所属类职责使用 |
| `core/solver_helpers/snapshot_helpers.py` | `(module)` | `strip_large_context_fields` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.strip_large_context_fields(...)`，并结合所属类职责使用 |
| `core/solver_helpers/store_helpers.py` | `(module)` | `build_context_store_or_memory` | 构建 `context_store_or_memory` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `core/solver_helpers/store_helpers.py` | `(module)` | `build_snapshot_store_or_memory` | 构建 `snapshot_store_or_memory` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `nsgablack/__init__.py` | `(module)` | `get_available_features` | 读取 `available_features` 相关运行态或配置值 | 通过 `obj.get_available_features(...)` 在日志、诊断或编排阶段查询 |
| `nsgablack/__init__.py` | `(module)` | `get_package_info` | 读取 `package_info` 相关运行态或配置值 | 通过 `obj.get_package_info(...)` 在日志、诊断或编排阶段查询 |
| `nsgablack/__init__.py` | `(module)` | `get_version` | 读取 `version` 相关运行态或配置值 | 通过 `obj.get_version(...)` 在日志、诊断或编排阶段查询 |
| `nsgablack/__main__.py` | `(module)` | `build_parser` | 构建 `parser` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `nsgablack/__main__.py` | `(module)` | `main` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.main(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `astar_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.astar_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `async_event_driven_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.async_event_driven_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `bias_gallery_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.bias_gallery_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `context_keys_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.context_keys_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `context_schema_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.context_schema_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `dynamic_cli_signal_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.dynamic_cli_signal_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `dynamic_multi_strategy_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.dynamic_multi_strategy_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `gpu_ray_mysql_stack_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.gpu_ray_mysql_stack_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `logging_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.logging_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `metrics_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.metrics_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `moa_star_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.moa_star_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `monte_carlo_dp_robust_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.monte_carlo_dp_robust_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `multi_fidelity_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.multi_fidelity_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `nsga2_solver_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.nsga2_solver_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `parallel_evaluator_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.parallel_evaluator_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `parallel_repair_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.parallel_repair_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `plugin_gallery_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.plugin_gallery_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `risk_bias_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.risk_bias_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `role_adapters_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.role_adapters_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `single_trajectory_adaptive_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.single_trajectory_adaptive_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `surrogate_plugin_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.surrogate_plugin_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_assignment_matrix` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_assignment_matrix(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_continuous_constrained` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_continuous_constrained(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_graph_path` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_graph_path(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_knapsack_binary` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_knapsack_binary(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_multiobjective_pareto` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_multiobjective_pareto(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_portfolio_pareto` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_portfolio_pareto(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_production_schedule_simple` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_production_schedule_simple(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `template_tsp_permutation` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.template_tsp_permutation(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `trust_region_dfo_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.trust_region_dfo_demo(...)`，并结合所属类职责使用 |
| `nsgablack/examples_registry.py` | `(module)` | `trust_region_subspace_demo` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.trust_region_subspace_demo(...)`，并结合所属类职责使用 |
| `plugins/base.py` | `Plugin` | `attach` | 附着到 solver 生命周期 | 通过 `add_plugin` 后自动调用 |
| `plugins/base.py` | `Plugin` | `commit_population_snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.commit_population_snapshot(...)`，并结合所属类职责使用 |
| `plugins/base.py` | `Plugin` | `configure` | 注入运行配置 | 初始化或外部配置变更时调用 |
| `plugins/base.py` | `Plugin` | `create_local_rng` | 创建 `local_rng` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/base.py` | `Plugin` | `detach` | 从 solver 生命周期解绑 | 插件卸载或结束时调用 |
| `plugins/base.py` | `Plugin` | `disable` | 禁用功能开关 | 运行中灰度关闭能力 |
| `plugins/base.py` | `Plugin` | `enable` | 启用功能开关 | 运行中灰度打开能力 |
| `plugins/base.py` | `Plugin` | `get_config` | 读取当前配置 | 用于审计/可视化/调试 |
| `plugins/base.py` | `Plugin` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `plugins/base.py` | `Plugin` | `get_population_snapshot` | 读取 `population_snapshot` 相关运行态或配置值 | 通过 `obj.get_population_snapshot(...)` 在日志、诊断或编排阶段查询 |
| `plugins/base.py` | `Plugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/base.py` | `Plugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/base.py` | `Plugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/base.py` | `Plugin` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `plugins/base.py` | `Plugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/base.py` | `Plugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/base.py` | `Plugin` | `on_step` | 步级别钩子 | 需要更细粒度监控时使用 |
| `plugins/base.py` | `PluginManager` | `clear` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear(...)`，并结合所属类职责使用 |
| `plugins/base.py` | `PluginManager` | `disable` | 禁用功能开关 | 运行中灰度关闭能力 |
| `plugins/base.py` | `PluginManager` | `dispatch` | 分发事件到订阅者 | manager/总线在生命周期节点触发 |
| `plugins/base.py` | `PluginManager` | `enable` | 启用功能开关 | 运行中灰度打开能力 |
| `plugins/base.py` | `PluginManager` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `plugins/base.py` | `PluginManager` | `list_plugins` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.list_plugins(...)`，并结合所属类职责使用 |
| `plugins/base.py` | `PluginManager` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/base.py` | `PluginManager` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/base.py` | `PluginManager` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `plugins/base.py` | `PluginManager` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/base.py` | `PluginManager` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/base.py` | `PluginManager` | `on_step` | 步级别钩子 | 需要更细粒度监控时使用 |
| `plugins/base.py` | `PluginManager` | `register` | 注册组件到管理器 | 初始化时挂载插件/子组件 |
| `plugins/base.py` | `PluginManager` | `set_event_hook` | 设置 `event_hook` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_event_hook(...)` |
| `plugins/base.py` | `PluginManager` | `set_execution_order` | 设置 `execution_order` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_execution_order(...)` |
| `plugins/base.py` | `PluginManager` | `trigger` | 触发指定事件 | 显式触发事件链并执行监听回调 |
| `plugins/base.py` | `PluginManager` | `unregister` | 从管理器移除组件 | 动态卸载或收尾阶段调用 |
| `plugins/evaluation/broyden_solver_plugin.py` | `BroydenSolverProviderPlugin` | `solve_backend` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve_backend(...)`，并结合所属类职责使用 |
| `plugins/evaluation/evaluation_model.py` | `EvaluationModelProviderPlugin` | `create_provider` | 创建 `provider` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/evaluation/evaluation_model.py` | `EvaluationModelProviderPlugin` | `evaluate_individual_runtime` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_individual_runtime(...)`，并结合所属类职责使用 |
| `plugins/evaluation/evaluation_model.py` | `EvaluationModelProviderPlugin` | `evaluate_model` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_model(...)`，并结合所属类职责使用 |
| `plugins/evaluation/evaluation_model.py` | `_Provider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/evaluation_model.py` | `_Provider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/evaluation_model.py` | `_Provider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `plugins/evaluation/evaluation_model.py` | `_Provider` | `evaluate_model` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_model(...)`，并结合所属类职责使用 |
| `plugins/evaluation/evaluation_model.py` | `_Provider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `plugins/evaluation/gpu_evaluation_template.py` | `GpuEvaluationTemplateProviderPlugin` | `create_provider` | 创建 `provider` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/evaluation/gpu_evaluation_template.py` | `GpuEvaluationTemplateProviderPlugin` | `evaluate_population_runtime` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用 |
| `plugins/evaluation/gpu_evaluation_template.py` | `_Provider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/gpu_evaluation_template.py` | `_Provider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/gpu_evaluation_template.py` | `_Provider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `plugins/evaluation/gpu_evaluation_template.py` | `_Provider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `plugins/evaluation/monte_carlo_evaluation.py` | `MonteCarloEvaluationProviderPlugin` | `create_provider` | 创建 `provider` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/evaluation/monte_carlo_evaluation.py` | `MonteCarloEvaluationProviderPlugin` | `evaluate_population_runtime` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用 |
| `plugins/evaluation/monte_carlo_evaluation.py` | `_Provider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/monte_carlo_evaluation.py` | `_Provider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/monte_carlo_evaluation.py` | `_Provider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `plugins/evaluation/monte_carlo_evaluation.py` | `_Provider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `plugins/evaluation/multi_fidelity_evaluation.py` | `MultiFidelityEvaluationProviderPlugin` | `create_provider` | 创建 `provider` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/evaluation/multi_fidelity_evaluation.py` | `MultiFidelityEvaluationProviderPlugin` | `evaluate_population_runtime` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用 |
| `plugins/evaluation/multi_fidelity_evaluation.py` | `_Provider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/multi_fidelity_evaluation.py` | `_Provider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/multi_fidelity_evaluation.py` | `_Provider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `plugins/evaluation/multi_fidelity_evaluation.py` | `_Provider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `plugins/evaluation/newton_solver_plugin.py` | `NewtonSolverProviderPlugin` | `solve_backend` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve_backend(...)`，并结合所属类职责使用 |
| `plugins/evaluation/numerical_solver_base.py` | `NumericalSolverProviderPlugin` | `create_provider` | 创建 `provider` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/evaluation/numerical_solver_base.py` | `NumericalSolverProviderPlugin` | `evaluate_individual_runtime` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_individual_runtime(...)`，并结合所属类职责使用 |
| `plugins/evaluation/numerical_solver_base.py` | `NumericalSolverProviderPlugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/evaluation/numerical_solver_base.py` | `NumericalSolverProviderPlugin` | `solve_backend` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve_backend(...)`，并结合所属类职责使用 |
| `plugins/evaluation/numerical_solver_base.py` | `_Provider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/numerical_solver_base.py` | `_Provider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/numerical_solver_base.py` | `_Provider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `plugins/evaluation/numerical_solver_base.py` | `_Provider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `plugins/evaluation/surrogate_evaluation.py` | `SurrogateEvaluationProviderPlugin` | `create_provider` | 创建 `provider` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `plugins/evaluation/surrogate_evaluation.py` | `SurrogateEvaluationProviderPlugin` | `evaluate_population_runtime` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用 |
| `plugins/evaluation/surrogate_evaluation.py` | `_Provider` | `can_handle_individual` | 判断当前是否可执行 `handle_individual` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/surrogate_evaluation.py` | `_Provider` | `can_handle_population` | 判断当前是否可执行 `handle_population` | 在执行前先调用，返回布尔值决定是否继续 |
| `plugins/evaluation/surrogate_evaluation.py` | `_Provider` | `evaluate_individual` | 单点评估入口 | 调试/在线评估场景优先使用 |
| `plugins/evaluation/surrogate_evaluation.py` | `_Provider` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `plugins/ops/benchmark_harness.py` | `BenchmarkHarnessPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/ops/benchmark_harness.py` | `BenchmarkHarnessPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/ops/benchmark_harness.py` | `BenchmarkHarnessPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/ops/decision_trace.py` | `DecisionTracePlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/ops/decision_trace.py` | `DecisionTracePlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/ops/decision_trace.py` | `DecisionTracePlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/ops/decision_trace.py` | `DecisionTracePlugin` | `record_decision` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_decision(...)`，并结合所属类职责使用 |
| `plugins/ops/module_report.py` | `ModuleReportPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/ops/module_report.py` | `ModuleReportPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/ops/otel_tracing.py` | `OpenTelemetryTracingPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/ops/otel_tracing.py` | `OpenTelemetryTracingPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/ops/profiler.py` | `ProfilerPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/ops/profiler.py` | `ProfilerPlugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/ops/profiler.py` | `ProfilerPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/ops/profiler.py` | `ProfilerPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/ops/sensitivity_analysis.py` | `SensitivityAnalysisPlugin` | `run_study` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_study(...)`，并结合所属类职责使用 |
| `plugins/ops/sequence_graph.py` | `SequenceGraphPlugin` | `on_context_build` | 插件生命周期钩子 | 由 PluginManager 在对应事件节点触发 |
| `plugins/ops/sequence_graph.py` | `SequenceGraphPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/ops/sequence_graph.py` | `SequenceGraphPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/ops/sequence_graph.py` | `SequenceGraphPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/ops/sequence_graph.py` | `SequenceGraphPlugin` | `record_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_event(...)`，并结合所属类职责使用 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `is_similar` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_similar(...)`，并结合所属类职责使用 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/runtime/diversity_init.py` | `DiversityInitPlugin` | `should_accept` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.should_accept(...)`，并结合所属类职责使用 |
| `plugins/runtime/dynamic_switch.py` | `DynamicSwitchPlugin` | `hard_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.hard_switch(...)`，并结合所属类职责使用 |
| `plugins/runtime/dynamic_switch.py` | `DynamicSwitchPlugin` | `select_switch_mode` | 选择 `switch_mode` 候选或策略 | 在决策阶段调用，根据上下文返回最优分支 |
| `plugins/runtime/dynamic_switch.py` | `DynamicSwitchPlugin` | `should_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.should_switch(...)`，并结合所属类职责使用 |
| `plugins/runtime/dynamic_switch.py` | `DynamicSwitchPlugin` | `soft_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.soft_switch(...)`，并结合所属类职责使用 |
| `plugins/runtime/elite_retention.py` | `BasicElitePlugin` | `on_context_build` | 插件生命周期钩子 | 由 PluginManager 在对应事件节点触发 |
| `plugins/runtime/elite_retention.py` | `BasicElitePlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/runtime/elite_retention.py` | `BasicElitePlugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/runtime/elite_retention.py` | `BasicElitePlugin` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `plugins/runtime/elite_retention.py` | `BasicElitePlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/runtime/elite_retention.py` | `BasicElitePlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/runtime/elite_retention.py` | `HistoricalElitePlugin` | `on_context_build` | 插件生命周期钩子 | 由 PluginManager 在对应事件节点触发 |
| `plugins/runtime/elite_retention.py` | `HistoricalElitePlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/runtime/elite_retention.py` | `HistoricalElitePlugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/runtime/elite_retention.py` | `HistoricalElitePlugin` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `plugins/runtime/elite_retention.py` | `HistoricalElitePlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/runtime/elite_retention.py` | `HistoricalElitePlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/runtime/pareto_archive.py` | `ParetoArchivePlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/solver_backends/backend_contract.py` | `(module)` | `normalize_backend_output` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_backend_output(...)`，并结合所属类职责使用 |
| `plugins/solver_backends/backend_contract.py` | `BackendSolver` | `solve` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve(...)`，并结合所属类职责使用 |
| `plugins/solver_backends/contract_bridge.py` | `ContractBridgePlugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/solver_backends/contract_bridge.py` | `ContractBridgePlugin` | `on_inner_result` | 插件生命周期钩子 | 由 PluginManager 在对应事件节点触发 |
| `plugins/solver_backends/copt_backend.py` | `CoptBackend` | `solve` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve(...)`，并结合所属类职责使用 |
| `plugins/solver_backends/copt_templates/linear.py` | `(module)` | `solve_linear_template` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve_linear_template(...)`，并结合所属类职责使用 |
| `plugins/solver_backends/copt_templates/qp.py` | `(module)` | `solve_qp_template` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve_qp_template(...)`，并结合所属类职责使用 |
| `plugins/solver_backends/copt_templates/registry.py` | `(module)` | `build_default_templates` | 构建 `default_templates` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `plugins/solver_backends/ngspice_backend.py` | `NgspiceBackend` | `solve` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.solve(...)`，并结合所属类职责使用 |
| `plugins/solver_backends/timeout_budget.py` | `TimeoutBudgetPlugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/solver_backends/timeout_budget.py` | `TimeoutBudgetPlugin` | `on_inner_guard` | 插件生命周期钩子 | 由 PluginManager 在对应事件节点触发 |
| `plugins/solver_backends/timeout_budget.py` | `TimeoutBudgetPlugin` | `on_inner_result` | 插件生命周期钩子 | 由 PluginManager 在对应事件节点触发 |
| `plugins/solver_backends/timeout_budget.py` | `TimeoutBudgetPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/storage/mysql_run_logger.py` | `MySQLRunLoggerPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/system/async_event_hub.py` | `AsyncEventHubPlugin` | `commit` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.commit(...)`，并结合所属类职责使用 |
| `plugins/system/async_event_hub.py` | `AsyncEventHubPlugin` | `get_committed_context` | 读取 `committed_context` 相关运行态或配置值 | 通过 `obj.get_committed_context(...)` 在日志、诊断或编排阶段查询 |
| `plugins/system/async_event_hub.py` | `AsyncEventHubPlugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/system/async_event_hub.py` | `AsyncEventHubPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/system/async_event_hub.py` | `AsyncEventHubPlugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/system/async_event_hub.py` | `AsyncEventHubPlugin` | `record_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_event(...)`，并结合所属类职责使用 |
| `plugins/system/boundary_guard.py` | `BoundaryGuardPlugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/system/boundary_guard.py` | `BoundaryGuardPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin` | `get_report` | 输出组件报告 | 用于 module report / 结果审计 |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin` | `resume` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.resume(...)`，并结合所属类职责使用 |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin` | `save_checkpoint` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.save_checkpoint(...)`，并结合所属类职责使用 |
| `plugins/system/memory_optimize.py` | `MemoryPlugin` | `get_memory_usage` | 读取 `memory_usage` 相关运行态或配置值 | 通过 `obj.get_memory_usage(...)` 在日志、诊断或编排阶段查询 |
| `plugins/system/memory_optimize.py` | `MemoryPlugin` | `on_generation_end` | 每代结束钩子 | 插件记录指标/归档/动态调控 |
| `plugins/system/memory_optimize.py` | `MemoryPlugin` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `plugins/system/memory_optimize.py` | `MemoryPlugin` | `on_population_init` | 初代种群完成后的钩子 | 插件统计或过滤初始化结果 |
| `plugins/system/memory_optimize.py` | `MemoryPlugin` | `on_solver_finish` | 求解结束钩子 | 输出报告、落盘、清理资源 |
| `plugins/system/memory_optimize.py` | `MemoryPlugin` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `project/catalog.py` | `(module)` | `export_project_entries` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.export_project_entries(...)`，并结合所属类职责使用 |
| `project/catalog.py` | `(module)` | `find_project_root` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.find_project_root(...)`，并结合所属类职责使用 |
| `project/catalog.py` | `(module)` | `load_project_catalog` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_project_catalog(...)`，并结合所属类职责使用 |
| `project/catalog.py` | `(module)` | `load_project_entries` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_project_entries(...)`，并结合所属类职责使用 |
| `project/doctor.py` | `(module)` | `format_doctor_report` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.format_doctor_report(...)`，并结合所属类职责使用 |
| `project/doctor.py` | `(module)` | `iter_diagnostics_by_level` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.iter_diagnostics_by_level(...)`，并结合所属类职责使用 |
| `project/doctor.py` | `(module)` | `run_project_doctor` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_project_doctor(...)`，并结合所属类职责使用 |
| `project/doctor_core/model.py` | `(module)` | `add_diagnostic` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_diagnostic(...)`，并结合所属类职责使用 |
| `project/doctor_core/model.py` | `(module)` | `format_doctor_report_text` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.format_doctor_report_text(...)`，并结合所属类职责使用 |
| `project/doctor_core/model.py` | `(module)` | `iter_diagnostics_by_level` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.iter_diagnostics_by_level(...)`，并结合所属类职责使用 |
| `project/doctor_core/model.py` | `DoctorReport` | `error_count` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.error_count(...)`，并结合所属类职责使用 |
| `project/doctor_core/model.py` | `DoctorReport` | `info_count` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.info_count(...)`，并结合所属类职责使用 |
| `project/doctor_core/model.py` | `DoctorReport` | `warn_count` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.warn_count(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/adapter_purity.py` | `(module)` | `check_adapter_layer_purity` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_adapter_layer_purity(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/broad_except.py` | `(module)` | `check_broad_exception_swallow` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_broad_exception_swallow(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/build_solver.py` | `(module)` | `check_build_solver` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_build_solver(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/component_catalog.py` | `(module)` | `check_component_catalog_registration` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_component_catalog_registration(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/component_catalog.py` | `(module)` | `check_process_like_bias_usage` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_process_like_bias_usage(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/component_catalog.py` | `(module)` | `collect_bias_instances` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.collect_bias_instances(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/component_catalog.py` | `(module)` | `collect_solver_components` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.collect_solver_components(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/component_order.py` | `(module)` | `check_component_order_constraints` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_component_order_constraints(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/component_order.py` | `_OrderActionCollector` | `visit_Call` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.visit_Call(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/contract_source.py` | `(module)` | `check_contract_source` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_contract_source(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/examples_suites.py` | `(module)` | `check_examples_suites_solver_control_writes` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_examples_suites_solver_control_writes(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/metrics_provider.py` | `(module)` | `check_metrics_provider_alignment` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_metrics_provider_alignment(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/registry_checks.py` | `(module)` | `check_registry` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_registry(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_governance.py` | `(module)` | `check_no_plugin_evaluation_short_circuit` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_no_plugin_evaluation_short_circuit(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_governance.py` | `(module)` | `check_runtime_governance_runtime_state` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_runtime_governance_runtime_state(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `(module)` | `check_forbidden_solver_mirror_writes` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_forbidden_solver_mirror_writes(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `(module)` | `check_plugin_solver_state_access` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_plugin_solver_state_access(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `(module)` | `check_runtime_bypass_writes` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_runtime_bypass_writes(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `(module)` | `check_runtime_private_calls` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_runtime_private_calls(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `_SolverMirrorWriteVisitor` | `visit_Assign` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.visit_Assign(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `_SolverMirrorWriteVisitor` | `visit_AugAssign` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.visit_AugAssign(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_guards.py` | `_SolverMirrorWriteVisitor` | `visit_Call` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.visit_Call(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/runtime_surface.py` | `(module)` | `check_runtime_private_surface` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_runtime_private_surface(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/scaffold.py` | `(module)` | `check_structure` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_structure(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/scaffold.py` | `(module)` | `looks_like_scaffold_project` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.looks_like_scaffold_project(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/snapshot_context_policy.py` | `(module)` | `check_context_store_policy` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_context_store_policy(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/snapshot_context_policy.py` | `(module)` | `check_large_objects_in_context` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_large_objects_in_context(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/snapshot_context_policy.py` | `(module)` | `check_snapshot_refs` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_snapshot_refs(...)`，并结合所属类职责使用 |
| `project/doctor_core/rules/snapshot_context_policy.py` | `(module)` | `check_snapshot_store_policy` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_snapshot_store_policy(...)`，并结合所属类职责使用 |
| `project/scaffold.py` | `(module)` | `init_project` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.init_project(...)`，并结合所属类职责使用 |
| `representation/base.py` | `ContinuousRepresentation` | `add_constraint` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `ContinuousRepresentation` | `check_constraints` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `ContinuousRepresentation` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/base.py` | `ContinuousRepresentation` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/base.py` | `ContinuousRepresentation` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/base.py` | `CrossoverPlugin` | `crossover` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `EncodingPlugin` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/base.py` | `EncodingPlugin` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/base.py` | `InitPlugin` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/base.py` | `IntegerRepresentation` | `add_constraint` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `IntegerRepresentation` | `check_constraints` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `IntegerRepresentation` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/base.py` | `IntegerRepresentation` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/base.py` | `IntegerRepresentation` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/base.py` | `MixedRepresentation` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/base.py` | `MixedRepresentation` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/base.py` | `MutationPlugin` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/base.py` | `ParallelRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/base.py` | `ParallelRepair` | `repair_batch` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `PermutationRepresentation` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/base.py` | `PermutationRepresentation` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/base.py` | `PermutationRepresentation` | `generate_random` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `RepairPlugin` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/base.py` | `RepresentationPipeline` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/base.py` | `RepresentationPipeline` | `decode_batch` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `RepresentationPipeline` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/base.py` | `RepresentationPipeline` | `encode_batch` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `RepresentationPipeline` | `get_context_contract` | 声明 context 读写契约 | doctor 校验与组件编排时读取 |
| `representation/base.py` | `RepresentationPipeline` | `init` | 初始化候选或批次 | solver 初始化种群时触发 |
| `representation/base.py` | `RepresentationPipeline` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/base.py` | `RepresentationPipeline` | `mutate_batch` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `RepresentationPipeline` | `repair_batch` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/base.py` | `RepresentationPipeline` | `repair_one` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/binary.py` | `BinaryCapacityRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/binary.py` | `BinaryInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/binary.py` | `BinaryRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/binary.py` | `BitFlipMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/constraints.py` | `BoundConstraint` | `check` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/constraints.py` | `BoundConstraint` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/context_mutators.py` | `ContextDispatchMutator` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/context_mutators.py` | `ContextSelectMutator` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/context_mutators.py` | `SerialMutator` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/continuous.py` | `ClipRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/continuous.py` | `ContextGaussianMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/continuous.py` | `GaussianMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/continuous.py` | `PolynomialMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/continuous.py` | `ProjectionRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/continuous.py` | `SBXCrossover` | `crossover` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/continuous.py` | `UniformInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/dynamic.py` | `DynamicRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/graph.py` | `GraphConnectivityRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/graph.py` | `GraphDegreeRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/graph.py` | `GraphEdgeInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/graph.py` | `GraphEdgeMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/integer.py` | `IntegerInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/integer.py` | `IntegerMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/integer.py` | `IntegerRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/matrix.py` | `IntegerMatrixInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/matrix.py` | `IntegerMatrixMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/matrix.py` | `MatrixBlockSumRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/matrix.py` | `MatrixRowColSumRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/matrix.py` | `MatrixSparsityRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/orchestrator.py` | `PipelineOrchestrator` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/orchestrator.py` | `PipelineOrchestrator` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/permutation.py` | `OrderCrossover` | `crossover` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/permutation.py` | `PMXCrossover` | `crossover` | 表示层算子动作 | 由 pipeline/orchestrator 在候选处理阶段调用 |
| `representation/permutation.py` | `PermutationFixRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/permutation.py` | `PermutationInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/permutation.py` | `PermutationInversionMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/permutation.py` | `PermutationRepair` | `repair` | 执行可行性修复 | 评估前最后防线，修正越界或结构违规 |
| `representation/permutation.py` | `PermutationSwapMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/permutation.py` | `RandomKeyInitializer` | `initialize` | 初始化单个候选 | 初始化阶段由 pipeline/initializer 调用 |
| `representation/permutation.py` | `RandomKeyMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `representation/permutation.py` | `RandomKeyPermutationDecoder` | `decode` | 将搜索表示解码为业务表示 | 评估前或结果解释时调用 |
| `representation/permutation.py` | `RandomKeyPermutationDecoder` | `encode` | 将业务表示编码为搜索表示 | 在优化前或导出前调用 |
| `representation/permutation.py` | `TwoOptMutation` | `mutate` | 执行变异操作 | 在生成新候选阶段调用，输入一个解 |
| `utils/analysis/metrics.py` | `(module)` | `hypervolume_2d` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.hypervolume_2d(...)`，并结合所属类职责使用 |
| `utils/analysis/metrics.py` | `(module)` | `igd` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.igd(...)`，并结合所属类职责使用 |
| `utils/analysis/metrics.py` | `(module)` | `pareto_filter` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.pareto_filter(...)`，并结合所属类职责使用 |
| `utils/analysis/metrics.py` | `(module)` | `reference_front_dtlz2` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reference_front_dtlz2(...)`，并结合所属类职责使用 |
| `utils/analysis/metrics.py` | `(module)` | `reference_front_zdt1` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reference_front_zdt1(...)`，并结合所属类职责使用 |
| `utils/analysis/metrics.py` | `(module)` | `reference_front_zdt3` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reference_front_zdt3(...)`，并结合所属类职责使用 |
| `utils/constraints/constraint_utils.py` | `(module)` | `evaluate_constraints_batch_safe` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_constraints_batch_safe(...)`，并结合所属类职责使用 |
| `utils/constraints/constraint_utils.py` | `(module)` | `evaluate_constraints_safe` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.evaluate_constraints_safe(...)`，并结合所属类职责使用 |
| `core/state/context_contracts.py` | `(module)` | `collect_solver_contracts` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.collect_solver_contracts(...)`，并结合所属类职责使用 |
| `core/state/context_contracts.py` | `(module)` | `detect_context_conflicts` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.detect_context_conflicts(...)`，并结合所属类职责使用 |
| `core/state/context_contracts.py` | `(module)` | `get_component_contract` | 读取 `component_contract` 相关运行态或配置值 | 通过 `obj.get_component_contract(...)` 在日志、诊断或编排阶段查询 |
| `core/state/context_contracts.py` | `(module)` | `validate_context_contracts` | 校验 `context_contracts` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/state/context_contracts.py` | `ContextContract` | `merge` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.merge(...)`，并结合所属类职责使用 |
| `core/state/context_contracts.py` | `ContextContract` | `normalized` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalized(...)`，并结合所属类职责使用 |
| `core/state/context_contracts.py` | `ContextContract` | `to_dict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.to_dict(...)`，并结合所属类职责使用 |
| `core/state/context_events.py` | `(module)` | `apply_context_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply_context_event(...)`，并结合所属类职责使用 |
| `core/state/context_events.py` | `(module)` | `record_context_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_context_event(...)`，并结合所属类职责使用 |
| `core/state/context_events.py` | `(module)` | `replay_context` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.replay_context(...)`，并结合所属类职责使用 |
| `core/state/context_events.py` | `ContextEvent` | `to_dict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.to_dict(...)`，并结合所属类职责使用 |
| `core/state/context_field_governance.py` | `(module)` | `context_field_schema_dict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.context_field_schema_dict(...)`，并结合所属类职责使用 |
| `core/state/context_field_governance.py` | `(module)` | `is_canonical_context_key` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_canonical_context_key(...)`，并结合所属类职责使用 |
| `core/state/context_field_governance.py` | `(module)` | `schema_meta` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.schema_meta(...)`，并结合所属类职责使用 |
| `core/state/context_keys.py` | `(module)` | `normalize_context_key` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_context_key(...)`，并结合所属类职责使用 |
| `core/state/context_schema.py` | `(module)` | `build_minimal_context` | 构建 `minimal_context` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `core/state/context_schema.py` | `(module)` | `get_context_lifecycle` | 读取 `context_lifecycle` 相关运行态或配置值 | 通过 `obj.get_context_lifecycle(...)` 在日志、诊断或编排阶段查询 |
| `core/state/context_schema.py` | `(module)` | `is_replayable_context` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_replayable_context(...)`，并结合所属类职责使用 |
| `core/state/context_schema.py` | `(module)` | `strip_context_for_replay` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.strip_context_for_replay(...)`，并结合所属类职责使用 |
| `core/state/context_schema.py` | `(module)` | `validate_context` | 校验 `context` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/state/context_schema.py` | `(module)` | `validate_minimal_context` | 校验 `minimal_context` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `core/state/context_schema.py` | `ContextSchema` | `field_map` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.field_map(...)`，并结合所属类职责使用 |
| `core/state/context_schema.py` | `ContextSchema` | `required_keys` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.required_keys(...)`，并结合所属类职责使用 |
| `core/state/context_schema.py` | `MinimalEvaluationContext` | `to_dict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.to_dict(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `(module)` | `create_context_store` | 创建 `context_store` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `core/state/context_store.py` | `ContextStore` | `clear` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `ContextStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `ContextStore` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `ContextStore` | `set` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.set(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `ContextStore` | `snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `ContextStore` | `update` | 根据评估反馈更新内部状态 | 在目标值/约束值返回后调用 |
| `core/state/context_store.py` | `InMemoryContextStore` | `clear` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `InMemoryContextStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `InMemoryContextStore` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `InMemoryContextStore` | `set` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.set(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `InMemoryContextStore` | `snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `RedisContextStore` | `clear` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `RedisContextStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `RedisContextStore` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `RedisContextStore` | `set` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.set(...)`，并结合所属类职责使用 |
| `core/state/context_store.py` | `RedisContextStore` | `snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `(module)` | `create_snapshot_store` | 创建 `snapshot_store` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `core/state/snapshot_store.py` | `(module)` | `make_snapshot_key` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.make_snapshot_key(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `FileSnapshotStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `FileSnapshotStore` | `read` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `FileSnapshotStore` | `write` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.write(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `InMemorySnapshotStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `InMemorySnapshotStore` | `read` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `InMemorySnapshotStore` | `write` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.write(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `RedisSnapshotStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `RedisSnapshotStore` | `read` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `RedisSnapshotStore` | `write` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.write(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `SnapshotStore` | `delete` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.delete(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `SnapshotStore` | `read` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read(...)`，并结合所属类职责使用 |
| `core/state/snapshot_store.py` | `SnapshotStore` | `write` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.write(...)`，并结合所属类职责使用 |
| `utils/dynamic/cli_provider.py` | `CLISignalProvider` | `read` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read(...)`，并结合所属类职责使用 |
| `utils/dynamic/switch.py` | `DynamicSwitchBase` | `hard_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.hard_switch(...)`，并结合所属类职责使用 |
| `utils/dynamic/switch.py` | `DynamicSwitchBase` | `on_generation_start` | 每代开始钩子 | 插件更新调度参数或预算 |
| `utils/dynamic/switch.py` | `DynamicSwitchBase` | `on_solver_init` | solver 初始化生命周期钩子 | 插件在启动阶段注入逻辑 |
| `utils/dynamic/switch.py` | `DynamicSwitchBase` | `select_switch_mode` | 选择 `switch_mode` 候选或策略 | 在决策阶段调用，根据上下文返回最优分支 |
| `utils/dynamic/switch.py` | `DynamicSwitchBase` | `should_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.should_switch(...)`，并结合所属类职责使用 |
| `utils/dynamic/switch.py` | `DynamicSwitchBase` | `soft_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.soft_switch(...)`，并结合所属类职责使用 |
| `utils/dynamic/switch.py` | `SignalProviderBase` | `close` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.close(...)`，并结合所属类职责使用 |
| `utils/dynamic/switch.py` | `SignalProviderBase` | `read` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.read(...)`，并结合所属类职责使用 |
| `utils/engineering/config_loader.py` | `(module)` | `apply_config` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply_config(...)`，并结合所属类职责使用 |
| `utils/engineering/config_loader.py` | `(module)` | `build_dataclass_config` | 构建 `dataclass_config` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `utils/engineering/config_loader.py` | `(module)` | `load_config` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_config(...)`，并结合所属类职责使用 |
| `utils/engineering/config_loader.py` | `(module)` | `merge_dicts` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.merge_dicts(...)`，并结合所属类职责使用 |
| `utils/engineering/config_loader.py` | `(module)` | `select_section` | 选择 `section` 候选或策略 | 在决策阶段调用，根据上下文返回最优分支 |
| `utils/engineering/error_policy.py` | `(module)` | `report_soft_error` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.report_soft_error(...)`，并结合所属类职责使用 |
| `utils/engineering/experiment.py` | `ExperimentResult` | `save` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.save(...)`，并结合所属类职责使用 |
| `utils/engineering/experiment.py` | `ExperimentResult` | `set_results` | 设置 `results` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_results(...)` |
| `utils/engineering/experiment.py` | `ExperimentTracker` | `log_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.log_run(...)`，并结合所属类职责使用 |
| `utils/engineering/file_io.py` | `(module)` | `atomic_write_json` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.atomic_write_json(...)`，并结合所属类职责使用 |
| `utils/engineering/file_io.py` | `(module)` | `atomic_write_text` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.atomic_write_text(...)`，并结合所属类职责使用 |
| `utils/engineering/logging_config.py` | `(module)` | `configure_logging` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.configure_logging(...)`，并结合所属类职责使用 |
| `utils/engineering/logging_config.py` | `JsonFormatter` | `format` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.format(...)`，并结合所属类职责使用 |
| `utils/engineering/schema_version.py` | `(module)` | `expected_schema_version` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.expected_schema_version(...)`，并结合所属类职责使用 |
| `utils/engineering/schema_version.py` | `(module)` | `require_schema` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.require_schema(...)`，并结合所属类职责使用 |
| `utils/engineering/schema_version.py` | `(module)` | `schema_check` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.schema_check(...)`，并结合所属类职责使用 |
| `utils/engineering/schema_version.py` | `(module)` | `stamp_schema` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.stamp_schema(...)`，并结合所属类职责使用 |
| `utils/evaluation/shape_validation.py` | `(module)` | `validate_individual_evaluation_shape` | 校验 `individual_evaluation_shape` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `utils/evaluation/shape_validation.py` | `(module)` | `validate_plugin_short_circuit_return` | 校验 `plugin_short_circuit_return` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `utils/evaluation/shape_validation.py` | `(module)` | `validate_population_evaluation_shape` | 校验 `population_evaluation_shape` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `utils/extension_contracts.py` | `(module)` | `normalize_bias_output` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_bias_output(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `normalize_candidate` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_candidate(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `normalize_candidates` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_candidates(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `normalize_objectives` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_objectives(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `normalize_violation` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.normalize_violation(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `stack_population` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.stack_population(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `verify_component_contract` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.verify_component_contract(...)`，并结合所属类职责使用 |
| `utils/extension_contracts.py` | `(module)` | `verify_solver_contracts` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.verify_solver_contracts(...)`，并结合所属类职责使用 |
| `utils/parallel/batch.py` | `(module)` | `create_batch_evaluator` | 创建 `batch_evaluator` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `utils/parallel/batch.py` | `BatchEvaluator` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `utils/parallel/batch.py` | `BatchEvaluator` | `get_stats` | 读取 `stats` 相关运行态或配置值 | 通过 `obj.get_stats(...)` 在日志、诊断或编排阶段查询 |
| `utils/parallel/batch.py` | `BatchEvaluator` | `reset_stats` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset_stats(...)`，并结合所属类职责使用 |
| `utils/parallel/evaluator.py` | `(module)` | `create_parallel_evaluator` | 创建 `parallel_evaluator` 实例或资源 | 在初始化阶段调用并返回可复用对象 |
| `utils/parallel/evaluator.py` | `ParallelEvaluator` | `estimate_speedup` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.estimate_speedup(...)`，并结合所属类职责使用 |
| `utils/parallel/evaluator.py` | `ParallelEvaluator` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `utils/parallel/evaluator.py` | `ParallelEvaluator` | `get_stats` | 读取 `stats` 相关运行态或配置值 | 通过 `obj.get_stats(...)` 在日志、诊断或编排阶段查询 |
| `utils/parallel/evaluator.py` | `ParallelEvaluator` | `reset_stats` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reset_stats(...)`，并结合所属类职责使用 |
| `utils/parallel/evaluator.py` | `SmartEvaluatorSelector` | `select_evaluator` | 选择 `evaluator` 候选或策略 | 在决策阶段调用，根据上下文返回最优分支 |
| `utils/parallel/integration.py` | `(module)` | `with_parallel_evaluation` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.with_parallel_evaluation(...)`，并结合所属类职责使用 |
| `utils/parallel/integration.py` | `ParallelizedSolver` | `evaluate_population` | 批量评估入口 | 算法主路径与并行评估常用入口 |
| `utils/parallel/runs.py` | `(module)` | `run_headless_in_parallel` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_headless_in_parallel(...)`，并结合所属类职责使用 |
| `utils/parallel/runs.py` | `(module)` | `run_vns_in_parallel` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_vns_in_parallel(...)`，并结合所属类职责使用 |
| `utils/performance/__init__.py` | `(module)` | `fast_non_dominated_sort_optimized` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.fast_non_dominated_sort_optimized(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_array_concat` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_array_concat(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_array_index` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_array_index(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_array_reshape` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_array_reshape(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_get_2d_element` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_get_2d_element(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_get_element` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_get_element(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_get_row` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_get_row(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `safe_slice_bounds` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_slice_bounds(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `(module)` | `validate_array_bounds` | 校验 `array_bounds` 合法性与一致性 | 在运行前调用，异常时中断并修正配置 |
| `utils/performance/array_utils.py` | `SafeArrayAccess` | `safe_get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_get(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `SafeArrayAccess` | `safe_slice_1d` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_slice_1d(...)`，并结合所属类职责使用 |
| `utils/performance/array_utils.py` | `SafeArrayAccess` | `safe_slice_2d` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_slice_2d(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `(module)` | `count_non_dominated_solutions` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.count_non_dominated_solutions(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `(module)` | `dominates_numba` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.dominates_numba(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `(module)` | `fast_non_dominated_sort_numba` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.fast_non_dominated_sort_numba(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `(module)` | `fast_non_dominated_sort_optimized` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.fast_non_dominated_sort_optimized(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `(module)` | `get_pareto_front_indices` | 读取 `pareto_front_indices` 相关运行态或配置值 | 通过 `obj.get_pareto_front_indices(...)` 在日志、诊断或编排阶段查询 |
| `utils/performance/fast_non_dominated_sort.py` | `(module)` | `is_pareto_optimal` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_pareto_optimal(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `FastNonDominatedSort` | `calculate_crowding_distance` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.calculate_crowding_distance(...)`，并结合所属类职责使用 |
| `utils/performance/fast_non_dominated_sort.py` | `FastNonDominatedSort` | `sort` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.sort(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `(module)` | `decorator` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.decorator(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `(module)` | `get_global_memory_manager` | 读取 `global_memory_manager` 相关运行态或配置值 | 通过 `obj.get_global_memory_manager(...)` 在日志、诊断或编排阶段查询 |
| `utils/performance/memory_manager.py` | `(module)` | `memory_monitoring` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.memory_monitoring(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `(module)` | `monitor_and_optimize_memory` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.monitor_and_optimize_memory(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `(module)` | `wrapper` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.wrapper(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `check_memory_pressure` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_memory_pressure(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `cleanup_memory` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.cleanup_memory(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `get_memory_trend` | 读取 `memory_trend` 相关运行态或配置值 | 通过 `obj.get_memory_trend(...)` 在日志、诊断或编排阶段查询 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `get_memory_usage` | 读取 `memory_usage` 相关运行态或配置值 | 通过 `obj.get_memory_usage(...)` 在日志、诊断或编排阶段查询 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `register_cleanup_strategy` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.register_cleanup_strategy(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `start_monitoring` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.start_monitoring(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `MemoryManager` | `stop_monitoring` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.stop_monitoring(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `OptimizationMemoryOptimizer` | `auto_optimize` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.auto_optimize(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `OptimizationMemoryOptimizer` | `clear_temporary_data` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear_temporary_data(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `OptimizationMemoryOptimizer` | `get_optimization_report` | 读取 `optimization_report` 相关运行态或配置值 | 通过 `obj.get_optimization_report(...)` 在日志、诊断或编排阶段查询 |
| `utils/performance/memory_manager.py` | `OptimizationMemoryOptimizer` | `optimize_history_storage` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.optimize_history_storage(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `OptimizationMemoryOptimizer` | `optimize_population_storage` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.optimize_population_storage(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `SmartArrayCache` | `clear` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `SmartArrayCache` | `get` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.get(...)`，并结合所属类职责使用 |
| `utils/performance/memory_manager.py` | `SmartArrayCache` | `get_stats` | 读取 `stats` 相关运行态或配置值 | 通过 `obj.get_stats(...)` 在日志、诊断或编排阶段查询 |
| `utils/performance/memory_manager.py` | `SmartArrayCache` | `put` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.put(...)`，并结合所属类职责使用 |
| `utils/performance/numba_helpers.py` | `(module)` | `fast_is_dominated` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.fast_is_dominated(...)`，并结合所属类职责使用 |
| `utils/performance/numba_helpers.py` | `(module)` | `njit` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.njit(...)`，并结合所属类职责使用 |
| `utils/performance/numba_helpers.py` | `(module)` | `wrapper` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.wrapper(...)`，并结合所属类职责使用 |
| `utils/runs/headless.py` | `(module)` | `run_headless_single_objective` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_headless_single_objective(...)`，并结合所属类职责使用 |
| `utils/runs/headless.py` | `CallableSingleObjectiveProblem` | `evaluate` | 执行问题评估并产出目标值 | 由评估链路调用，输入单个 candidate |
| `utils/runs/headless.py` | `CallableSingleObjectiveProblem` | `get_num_objectives` | 读取 `num_objectives` 相关运行态或配置值 | 通过 `obj.get_num_objectives(...)` 在日志、诊断或编排阶段查询 |
| `utils/runtime/decision_trace.py` | `(module)` | `append_decision_jsonl` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.append_decision_jsonl(...)`，并结合所属类职责使用 |
| `utils/runtime/decision_trace.py` | `(module)` | `build_decision_event` | 构建 `decision_event` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `utils/runtime/decision_trace.py` | `(module)` | `load_decision_jsonl` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_decision_jsonl(...)`，并结合所属类职责使用 |
| `utils/runtime/decision_trace.py` | `(module)` | `record_decision_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_decision_event(...)`，并结合所属类职责使用 |
| `utils/runtime/decision_trace.py` | `DecisionReplayEngine` | `from_jsonl` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.from_jsonl(...)`，并结合所属类职责使用 |
| `utils/runtime/decision_trace.py` | `DecisionReplayEngine` | `iter` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.iter(...)`，并结合所属类职责使用 |
| `utils/runtime/decision_trace.py` | `DecisionReplayEngine` | `summary` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.summary(...)`，并结合所属类职责使用 |
| `utils/runtime/dependencies.py` | `(module)` | `check_dependency` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_dependency(...)`，并结合所属类职责使用 |
| `utils/runtime/dependencies.py` | `(module)` | `dependency_report` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.dependency_report(...)`，并结合所属类职责使用 |
| `utils/runtime/dependencies.py` | `(module)` | `ensure_dependencies` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.ensure_dependencies(...)`，并结合所属类职责使用 |
| `utils/runtime/dependencies.py` | `(module)` | `summarize_report` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.summarize_report(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `add_to_path` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_to_path(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `check_optional_dependency` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_optional_dependency(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `get_import_status` | 读取 `import_status` 相关运行态或配置值 | 通过 `obj.get_import_status(...)` 在日志、诊断或编排阶段查询 |
| `utils/runtime/imports.py` | `(module)` | `get_package_root` | 读取 `package_root` 相关运行态或配置值 | 通过 `obj.get_package_root(...)` 在日志、诊断或编排阶段查询 |
| `utils/runtime/imports.py` | `(module)` | `import_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_bias(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_core` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_core(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_joblib` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_joblib(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_matplotlib` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_matplotlib(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_numba` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_numba(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_numpy` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_numpy(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_plotly` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_plotly(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_sklearn` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_sklearn(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `import_utils` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.import_utils(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `is_headless` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_headless(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `is_jupyter_notebook` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.is_jupyter_notebook(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `(module)` | `safe_import` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_import(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `ImportManager` | `check_optional_dependency` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.check_optional_dependency(...)`，并结合所属类职责使用 |
| `utils/runtime/imports.py` | `ImportManager` | `get_import_status` | 读取 `import_status` 相关运行态或配置值 | 通过 `obj.get_import_status(...)` 在日志、诊断或编排阶段查询 |
| `utils/runtime/imports.py` | `ImportManager` | `safe_import` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.safe_import(...)`，并结合所属类职责使用 |
| `utils/runtime/repro_bundle.py` | `(module)` | `apply_bundle_to_solver` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.apply_bundle_to_solver(...)`，并结合所属类职责使用 |
| `utils/runtime/repro_bundle.py` | `(module)` | `build_repro_bundle` | 构建 `repro_bundle` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `utils/runtime/repro_bundle.py` | `(module)` | `compare_repro_bundle` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compare_repro_bundle(...)`，并结合所属类职责使用 |
| `utils/runtime/repro_bundle.py` | `(module)` | `load_repro_bundle` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_repro_bundle(...)`，并结合所属类职责使用 |
| `utils/runtime/repro_bundle.py` | `(module)` | `replay_spec` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.replay_spec(...)`，并结合所属类职责使用 |
| `utils/runtime/repro_bundle.py` | `(module)` | `write_repro_bundle` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.write_repro_bundle(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `(module)` | `build_sequence_token` | 构建 `sequence_token` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `utils/runtime/sequence_graph.py` | `(module)` | `record_sequence_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_sequence_event(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceGraphRecorder` | `end_trace_span` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.end_trace_span(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceGraphRecorder` | `finalize_cycle` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.finalize_cycle(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceGraphRecorder` | `record_event` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_event(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceGraphRecorder` | `record_instant_trace` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.record_instant_trace(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceGraphRecorder` | `snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceGraphRecorder` | `start_trace_span` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.start_trace_span(...)`，并结合所属类职责使用 |
| `utils/runtime/sequence_graph.py` | `SequenceRecord` | `to_dict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.to_dict(...)`，并结合所属类职责使用 |
| `utils/surrogate/manager.py` | `SurrogateManager` | `add_model` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_model(...)`，并结合所属类职责使用 |
| `utils/surrogate/manager.py` | `SurrogateManager` | `predict_model` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.predict_model(...)`，并结合所属类职责使用 |
| `utils/surrogate/manager.py` | `SurrogateManager` | `train_model` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.train_model(...)`，并结合所属类职责使用 |
| `utils/surrogate/manager.py` | `SurrogateManager` | `uncertainty` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.uncertainty(...)`，并结合所属类职责使用 |
| `utils/surrogate/strategies.py` | `AdaptiveStrategy` | `update_strategy` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_strategy(...)`，并结合所属类职责使用 |
| `utils/surrogate/strategies.py` | `UncertaintySampling` | `select` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.select(...)`，并结合所属类职责使用 |
| `utils/surrogate/trainer.py` | `SurrogateTrainer` | `predict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.predict(...)`，并结合所属类职责使用 |
| `utils/surrogate/trainer.py` | `SurrogateTrainer` | `predict_uncertainty` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.predict_uncertainty(...)`，并结合所属类职责使用 |
| `utils/surrogate/trainer.py` | `SurrogateTrainer` | `train` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.train(...)`，并结合所属类职责使用 |
| `utils/surrogate/vector_surrogate.py` | `VectorSurrogate` | `fit` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.fit(...)`，并结合所属类职责使用 |
| `utils/surrogate/vector_surrogate.py` | `VectorSurrogate` | `predict` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.predict(...)`，并结合所属类职责使用 |
| `utils/surrogate/vector_surrogate.py` | `VectorSurrogate` | `uncertainty` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.uncertainty(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `(module)` | `launch_empty` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.launch_empty(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `(module)` | `launch_from_builder` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.launch_from_builder(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `(module)` | `launch_from_entry` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.launch_from_entry(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `(module)` | `main` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.main(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `(module)` | `maybe_launch_ui` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.maybe_launch_ui(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `append_history` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.append_history(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `request_context_refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_context_refresh(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `request_decision_refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_decision_refresh(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `request_doctor_refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_doctor_refresh(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `request_repro_refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_repro_refresh(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `request_sequence_refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_sequence_refresh(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `search_catalog_for_component` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search_catalog_for_component(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `search_catalog_for_context_key` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search_catalog_for_context_key(...)`，并结合所属类职责使用 |
| `utils/viz/app.py` | `VisualizerApp` | `show_component_detail` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.show_component_detail(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `clear_all_plots` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.clear_all_plots(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `init_plot_static_elements` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.init_plot_static_elements(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `redraw_static_elements` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.redraw_static_elements(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `setup_ui` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.setup_ui(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `start_animation` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.start_animation(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `stop_animation` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.stop_animation(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `toggle_diversity_init` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.toggle_diversity_init(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `toggle_elite_retention` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.toggle_elite_retention(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `toggle_history` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.toggle_history(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `toggle_plot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.toggle_plot(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `update_elite_prob` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_elite_prob(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `update_fitness_plot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_fitness_plot(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `update_info_text` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_info_text(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `update_plot_dynamic` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_plot_dynamic(...)`，并结合所属类职责使用 |
| `utils/viz/matplotlib.py` | `SolverVisualizationMixin` | `update_population_and_pareto_plot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_population_and_pareto_plot(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `(module)` | `context_role_match` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.context_role_match(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `(module)` | `scope_from_key` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.scope_from_key(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `key_for_bias` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.key_for_bias(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `key_for_plugin` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.key_for_plugin(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `load_catalog` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_catalog(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `on_select` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.on_select(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `open_register_dialog` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.open_register_dialog(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `search` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search(...)`，并结合所属类职责使用 |
| `utils/viz/ui/catalog_view.py` | `CatalogView` | `search_context_key` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.search_context_key(...)`，并结合所属类职责使用 |
| `utils/viz/ui/context_view.py` | `ContextView` | `refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.refresh(...)`，并结合所属类职责使用 |
| `utils/viz/ui/context_view.py` | `ContextView` | `request_refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.request_refresh(...)`，并结合所属类职责使用 |
| `utils/viz/ui/context_view.py` | `ContextView` | `show_replay_keys` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.show_replay_keys(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `add_run_choice` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.add_run_choice(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `compare_runs` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compare_runs(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `index_by_name` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.index_by_name(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `key_fmt` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.key_fmt(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `refresh_contribution` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.refresh_contribution(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `reload_run_choices` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.reload_run_choices(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `sort_items` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.sort_items(...)`，并结合所属类职责使用 |
| `utils/viz/ui/contrib_view.py` | `ContributionView` | `y_for` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.y_for(...)`，并结合所属类职责使用 |
| `utils/viz/ui/decision_view.py` | `DecisionView` | `load_from_history_index` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_from_history_index(...)`，并结合所属类职责使用 |
| `utils/viz/ui/decision_view.py` | `DecisionView` | `load_from_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_from_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/decision_view.py` | `DecisionView` | `load_last_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_last_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/decision_view.py` | `DecisionView` | `refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.refresh(...)`，并结合所属类职责使用 |
| `utils/viz/ui/doctor_view.py` | `(module)` | `build_doctor_visual_hints` | 构建 `doctor_visual_hints` 产物或对象 | 作为工厂方法在装配阶段调用并接入后续流程 |
| `utils/viz/ui/doctor_view.py` | `(module)` | `count_doctor_guard_issues` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.count_doctor_guard_issues(...)`，并结合所属类职责使用 |
| `utils/viz/ui/doctor_view.py` | `DoctorView` | `refresh_state` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.refresh_state(...)`，并结合所属类职责使用 |
| `utils/viz/ui/doctor_view.py` | `DoctorView` | `run_doctor` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_doctor(...)`，并结合所属类职责使用 |
| `utils/viz/ui/doctor_view.py` | `DoctorView` | `use_default_path` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.use_default_path(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `compare_current` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.compare_current(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `export_last` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.export_last(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `load_file` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_file(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `load_from_history_index` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_from_history_index(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `load_from_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_from_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `load_last_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_last_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/repro_view.py` | `ReproView` | `run_by_bundle` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.run_by_bundle(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `get_plugin` | 读取 `plugin` 相关运行态或配置值 | 通过 `obj.get_plugin(...)` 在日志、诊断或编排阶段查询 |
| `utils/viz/ui/run_view.py` | `RunView` | `on_refresh_ui` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.on_refresh_ui(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `on_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.on_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `on_sensitivity` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.on_sensitivity(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `snapshot` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.snapshot(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `sort_items` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.sort_items(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `sync_run_id_plugins` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.sync_run_id_plugins(...)`，并结合所属类职责使用 |
| `utils/viz/ui/run_view.py` | `RunView` | `update_sensitivity_button` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.update_sensitivity_button(...)`，并结合所属类职责使用 |
| `utils/viz/ui/sequence_view.py` | `SequenceView` | `load_from_history_index` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_from_history_index(...)`，并结合所属类职责使用 |
| `utils/viz/ui/sequence_view.py` | `SequenceView` | `load_from_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_from_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/sequence_view.py` | `SequenceView` | `load_last_run` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.load_last_run(...)`，并结合所属类职责使用 |
| `utils/viz/ui/sequence_view.py` | `SequenceView` | `refresh` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.refresh(...)`，并结合所属类职责使用 |
| `utils/wiring/__init__.py` | `(module)` | `set_parallel_thread_bias_isolation` | 设置 `parallel_thread_bias_isolation` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_parallel_thread_bias_isolation(...)` |
| `utils/wiring/__init__.py` | `(module)` | `set_plugin_strict` | 设置 `plugin_strict` 相关运行参数或状态 | 在构建 solver/adapter/plugin 时调用 `obj.set_plugin_strict(...)` |
| `utils/wiring/benchmark_harness.py` | `(module)` | `attach_benchmark_harness` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_benchmark_harness(...)`，并结合所属类职责使用 |
| `utils/wiring/checkpoint_resume.py` | `(module)` | `attach_checkpoint_resume` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_checkpoint_resume(...)`，并结合所属类职责使用 |
| `utils/wiring/default_plugins.py` | `(module)` | `attach_default_observability_plugins` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_default_observability_plugins(...)`，并结合所属类职责使用 |
| `utils/wiring/default_plugins.py` | `(module)` | `attach_observability_profile` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_observability_profile(...)`，并结合所属类职责使用 |
| `utils/wiring/default_plugins.py` | `(module)` | `resolve_observability_preset` | 解析并确定 `observability_preset` 最终结果 | 在多来源配置合并时调用 `obj.resolve_observability_preset(...)` |
| `utils/wiring/dynamic_switch.py` | `(module)` | `attach_dynamic_switch` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_dynamic_switch(...)`，并结合所属类职责使用 |
| `utils/wiring/module_report.py` | `(module)` | `attach_module_report` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_module_report(...)`，并结合所属类职责使用 |
| `utils/wiring/ray_parallel.py` | `(module)` | `attach_ray_parallel` | 组件公开方法（需结合实现细节） | 按签名调用 `obj.attach_ray_parallel(...)`，并结合所属类职责使用 |

## B. 逐类完整展开（每个 class/模块函数集合）

### `adapters/algorithm_adapter.py`

- `AlgorithmAdapter`
  - 方法数：`14`
  - 方法明细：
    - `coerce_candidates`（L152）：用途=将输入规范化为 `candidates` 预期格式；用法=在接口边界调用以保证 shape/type 一致
    - `create_local_rng`（L59）：用途=创建 `local_rng` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `get_context_contract`（L162）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `get_runtime_context_projection`（L205）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L209）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L104）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L85）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `resolve_config`（L32）：用途=解析并确定 `config` 最终结果；用法=在多来源配置合并时调用 `obj.resolve_config(...)`
    - `set_population`（L142）：用途=写入当前种群快照；用法=用于 runtime 插件回写或恢复后对齐
    - `set_state`（L108）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L80）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L100）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L89）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用
    - `validate_population_snapshot`（L113）：用途=校验 `population_snapshot` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `CompositeAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_context_contract`（L282）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `get_state`（L272）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L234）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L275）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L230）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L268）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L245）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/astar/adapter.py`

- `AStarAdapter`
  - 方法数：`5`
  - 方法明细：
    - `get_state`（L309）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L137）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L318）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L123）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L192）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/async_event_driven/adapter.py`

- `AsyncEventDrivenAdapter`
  - 方法数：`8`
  - 方法明细：
    - `get_runtime_context_projection`（L420）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L424）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L429）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L157）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L440）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L131）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L152）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L203）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/differential_evolution/adapter.py`

- `DifferentialEvolutionAdapter`
  - 方法数：`9`
  - 方法明细：
    - `get_population`（L167）：用途=读取当前种群快照；用法=给插件/可视化读取运行态
    - `get_runtime_context_projection`（L176）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L180）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L185）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L87）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_population`（L159）：用途=写入当前种群快照；用法=用于 runtime 插件回写或恢复后对齐
    - `set_state`（L193）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L78）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L111）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/gradient_descent/adapter.py`

- `GradientDescentAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_runtime_context_projection`（L129）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L133）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L138）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L66）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L145）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L58）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L85）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/mas/adapter.py`

- `MASAdapter`
  - 方法数：`4`
  - 方法明细：
    - `get_state`（L138）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L58）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L143）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `update`（L86）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/moa_star/adapter.py`

- `MOAStarAdapter`
  - 方法数：`5`
  - 方法明细：
    - `get_state`（L402）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L156）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L411）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L134）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L206）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/moead/adapter.py`

- `MOEADAdapter`
  - 方法数：`11`
  - 方法明细：
    - `get_population`（L296）：用途=读取当前种群快照；用法=给插件/可视化读取运行态
    - `get_runtime_context_projection`（L250）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L254）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L262）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L163）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `rec`（L517）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.rec(...)`，并结合所属类职责使用
    - `set_population`（L301）：用途=写入当前种群快照；用法=用于 runtime 插件回写或恢复后对齐
    - `set_state`（L276）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L117）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L157）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L190）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/multi_strategy/adapter.py`

- `StrategyRouterAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_context_contract`（L1223）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `get_runtime_context_projection`（L1018）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L1066）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `propose`（L797）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `setup`（L249）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L281）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L933）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/nsga2/adapter.py`

- `NSGA2Adapter`
  - 方法数：`9`
  - 方法明细：
    - `get_population`（L136）：用途=读取当前种群快照；用法=给插件/可视化读取运行态
    - `get_runtime_context_projection`（L145）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L149）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L154）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L74）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_population`（L127）：用途=写入当前种群快照；用法=用于 runtime 插件回写或恢复后对齐
    - `set_state`（L161）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L65）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L92）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/nsga3/adapter.py`

- `NSGA3Adapter`
  - 方法数：`1`
  - 方法明细：
    - `setup`（L51）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发

### `adapters/pattern_search/adapter.py`

- `PatternSearchAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_runtime_context_projection`（L106）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L110）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L115）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L63）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L122）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L56）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L80）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/role_adapters/adapter.py`

- `RoleAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_context_contract`（L231）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `get_state`（L200）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L102）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L213）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L98）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L131）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L114）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

- `RoleRouterAdapter`
  - 方法数：`8`
  - 方法明细：
    - `get_runtime_context_projection`（L367）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L371）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L344）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L289）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L349）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L284）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L340）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L310）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/serial_strategy/adapter.py`

- `StrategyChainAdapter`
  - 方法数：`6`
  - 方法明细：
    - `get_state`（L154）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L100）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L169）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L82）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `teardown`（L90）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `update`（L110）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/simulated_annealing/adapter.py`

- `SimulatedAnnealingAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_runtime_context_projection`（L231）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L235）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L212）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L143）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L220）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L97）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L156）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/single_trajectory_adaptive/adapter.py`

- `SingleTrajectoryAdaptiveAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_runtime_context_projection`（L214）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L226）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L187）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L119）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L199）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L91）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L132）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/trust_region_base/adapter.py`

- `TrustRegionBaseAdapter`
  - 方法数：`5`
  - 方法明细：
    - `get_state`（L104）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L53）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L115）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L47）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L71）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `adapters/vns/adapter.py`

- `VNSAdapter`
  - 方法数：`7`
  - 方法明细：
    - `get_runtime_context_projection`（L204）：用途=输出可观测运行态切片；用法=供插件/UI 获取关键运行指标
    - `get_runtime_context_projection_sources`（L208）：用途=读取 `runtime_context_projection_sources` 相关运行态或配置值；用法=通过 `obj.get_runtime_context_projection_sources(...)` 在日志、诊断或编排阶段查询
    - `get_state`（L225）：用途=导出可恢复状态快照；用法=用于 checkpoint、断点续跑与调试可视化
    - `propose`（L134）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列
    - `set_state`（L232）：用途=恢复内部状态；用法=在 resume 或迁移运行态时调用
    - `setup`（L87）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `update`（L154）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

### `bias/algorithmic/cma_es.py`

- `AdaptiveCMAESBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L104）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `CMAESBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L47）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/convergence.py`

- `AdaptiveConvergenceBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L85）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ConvergenceBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L32）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `LateStageConvergenceBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L201）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `MultiStageConvergenceBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L242）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `PrecisionBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L151）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/diversity.py`

- `AdaptiveDiversityBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L155）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `CrowdingDistanceBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L346）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `DiversityBias`
  - 方法数：`2`
  - 方法明细：
    - `compute`（L52）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `get_average_diversity`（L105）：用途=读取 `average_diversity` 相关运行态或配置值；用法=通过 `obj.get_average_diversity(...)` 在日志、诊断或编排阶段查询

- `NicheDiversityBias`
  - 方法数：`2`
  - 方法明细：
    - `compute`（L263）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `update_niches`（L303）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_niches(...)`，并结合所属类职责使用

- `SharingFunctionBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L420）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/levy_flight.py`

- `LevyFlightBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L39）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/pso.py`

- `AdaptivePSOBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L94）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ParticleSwarmBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L47）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/signal_driven/robustness.py`

- `RobustnessBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L52）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/signal_driven/uncertainty_exploration.py`

- `UncertaintyExplorationBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L40）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/tabu_search.py`

- `TabuSearchBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L44）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/algorithmic/template_algorithmic_bias.py`

- `ExampleAlgorithmicBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L32）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/analytics.py`

- `BiasAnalytics`
  - 方法数：`1`
  - 方法明细：
    - `generate_report`（L39）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.generate_report(...)`，并结合所属类职责使用

### `bias/bias_module.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `create_bias_module`（L745）：用途=创建 `bias_module` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `from_universal_manager`（L749）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.from_universal_manager(...)`，并结合所属类职责使用
    - `improvement_reward`（L741）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.improvement_reward(...)`，并结合所属类职责使用
    - `proximity_reward`（L736）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.proximity_reward(...)`，并结合所属类职责使用

- `BiasModule`
  - 方法数：`21`
  - 方法明细：
    - `add`（L165）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add(...)`，并结合所属类职责使用
    - `algorithmic_manager`（L644）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.algorithmic_manager(...)`，并结合所属类职责使用
    - `clear`（L676）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear(...)`，并结合所属类职责使用
    - `clear_cache`（L698）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear_cache(...)`，并结合所属类职责使用
    - `compute_bias`（L216）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_bias(...)`，并结合所属类职责使用
    - `compute_bias_batch`（L297）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_bias_batch(...)`，并结合所属类职责使用
    - `compute_bias_vector`（L254）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_bias_vector(...)`，并结合所属类职责使用
    - `disable_all`（L597）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.disable_all(...)`，并结合所属类职责使用
    - `domain_manager`（L648）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.domain_manager(...)`，并结合所属类职责使用
    - `enable_all`（L588）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.enable_all(...)`，并结合所属类职责使用
    - `from_universal_manager`（L159）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.from_universal_manager(...)`，并结合所属类职责使用
    - `get_bias`（L606）：用途=读取 `bias` 相关运行态或配置值；用法=通过 `obj.get_bias(...)` 在日志、诊断或编排阶段查询
    - `get_context_contract`（L94）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `list_biases`（L632）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_biases(...)`，并结合所属类职责使用
    - `remove_bias`（L617）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.remove_bias(...)`，并结合所属类职责使用
    - `set_cache_backend`（L149）：用途=设置 `cache_backend` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_cache_backend(...)`
    - `set_cache_context_keys`（L152）：用途=设置 `cache_context_keys` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_cache_context_keys(...)`
    - `set_cache_include_generation`（L155）：用途=设置 `cache_include_generation` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_cache_include_generation(...)`
    - `set_context_store`（L131）：用途=注入 context 存储实现；用法=运行前配置状态存储后端
    - `set_snapshot_store`（L139）：用途=注入 snapshot 存储实现；用法=运行前配置大对象快照后端
    - `to_universal_manager`（L640）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.to_universal_manager(...)`，并结合所属类职责使用

### `bias/core/base.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `create_bias`（L577）：用途=创建 `bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `AlgorithmicBias`
  - 方法数：`2`
  - 方法明细：
    - `is_adaptive`（L458）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_adaptive(...)`，并结合所属类职责使用
    - `reset_to_initial_weight`（L467）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset_to_initial_weight(...)`，并结合所属类职责使用

- `BiasBase`
  - 方法数：`13`
  - 方法明细：
    - `compute`（L159）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `compute_with_tracking`（L175）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_with_tracking(...)`，并结合所属类职责使用
    - `disable`（L303）：用途=禁用功能开关；用法=运行中灰度关闭能力
    - `enable`（L298）：用途=启用功能开关；用法=运行中灰度打开能力
    - `finalize_generation`（L354）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.finalize_generation(...)`，并结合所属类职责使用
    - `get_average_bias`（L337）：用途=读取 `average_bias` 相关运行态或配置值；用法=通过 `obj.get_average_bias(...)` 在日志、诊断或编排阶段查询
    - `get_context_contract`（L218）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `get_name`（L321）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `get_statistics`（L378）：用途=读取 `statistics` 相关运行态或配置值；用法=通过 `obj.get_statistics(...)` 在日志、诊断或编排阶段查询
    - `get_weight`（L318）：用途=读取 `weight` 相关运行态或配置值；用法=通过 `obj.get_weight(...)` 在日志、诊断或编排阶段查询
    - `register_param_change_callback`（L324）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_param_change_callback(...)`，并结合所属类职责使用
    - `reset_statistics`（L346）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset_statistics(...)`，并结合所属类职责使用
    - `set_weight`（L308）：用途=设置 `weight` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_weight(...)`

- `BiasInterface`
  - 方法数：`6`
  - 方法明细：
    - `compute`（L21）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `disable`（L36）：用途=禁用功能开关；用法=运行中灰度关闭能力
    - `enable`（L33）：用途=启用功能开关；用法=运行中灰度打开能力
    - `get_name`（L24）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `get_weight`（L27）：用途=读取 `weight` 相关运行态或配置值；用法=通过 `obj.get_weight(...)` 在日志、诊断或编排阶段查询
    - `set_weight`（L30）：用途=设置 `weight` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_weight(...)`

- `BiasManager`
  - 方法数：`4`
  - 方法明细：
    - `add_bias`（L529）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_bias(...)`，并结合所属类职责使用
    - `compute_total_bias`（L550）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用
    - `get_bias`（L563）：用途=读取 `bias` 相关运行态或配置值；用法=通过 `obj.get_bias(...)` 在日志、诊断或编排阶段查询
    - `remove_bias`（L538）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.remove_bias(...)`，并结合所属类职责使用

- `DomainBias`
  - 方法数：`1`
  - 方法明细：
    - `is_mandatory`（L511）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_mandatory(...)`，并结合所属类职责使用

- `OptimizationContext`
  - 方法数：`3`
  - 方法明细：
    - `set_constraint_violation`（L91）：用途=设置 `constraint_violation` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_constraint_violation(...)`
    - `set_convergence_status`（L82）：用途=设置 `convergence_status` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_convergence_status(...)`
    - `set_stuck_status`（L73）：用途=设置 `stuck_status` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_stuck_status(...)`

### `bias/core/manager.py`

- `AlgorithmicBiasManager`
  - 方法数：`6`
  - 方法明细：
    - `adapt_weights`（L186）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.adapt_weights(...)`，并结合所属类职责使用
    - `add_algorithmic_bias`（L151）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_algorithmic_bias(...)`，并结合所属类职责使用
    - `adjust_convergence_weights`（L229）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.adjust_convergence_weights(...)`，并结合所属类职责使用
    - `adjust_exploration_weights`（L217）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.adjust_exploration_weights(...)`，并结合所属类职责使用
    - `compute_total_bias`（L168）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用
    - `reset_adaptive_weights`（L241）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset_adaptive_weights(...)`，并结合所属类职责使用

- `BiasManagerMixin`
  - 方法数：`8`
  - 方法明细：
    - `add_bias`（L38）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_bias(...)`，并结合所属类职责使用
    - `disable_all`（L98）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.disable_all(...)`，并结合所属类职责使用
    - `enable_all`（L93）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.enable_all(...)`，并结合所属类职责使用
    - `get_bias`（L72）：用途=读取 `bias` 相关运行态或配置值；用法=通过 `obj.get_bias(...)` 在日志、诊断或编排阶段查询
    - `get_bias_statistics`（L112）：用途=读取 `bias_statistics` 相关运行态或配置值；用法=通过 `obj.get_bias_statistics(...)` 在日志、诊断或编排阶段查询
    - `get_enabled_biases`（L103）：用途=读取 `enabled_biases` 相关运行态或配置值；用法=通过 `obj.get_enabled_biases(...)` 在日志、诊断或编排阶段查询
    - `list_biases`（L84）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_biases(...)`，并结合所属类职责使用
    - `remove_bias`（L57）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.remove_bias(...)`，并结合所属类职责使用

- `DomainBiasManager`
  - 方法数：`5`
  - 方法明细：
    - `add_domain_bias`（L267）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_domain_bias(...)`，并结合所属类职责使用
    - `compute_constraint_violation_rate`（L327）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_constraint_violation_rate(...)`，并结合所属类职责使用
    - `compute_total_bias`（L284）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用
    - `ensure_mandatory_enabled`（L322）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.ensure_mandatory_enabled(...)`，并结合所属类职责使用
    - `get_mandatory_biases`（L312）：用途=读取 `mandatory_biases` 相关运行态或配置值；用法=通过 `obj.get_mandatory_biases(...)` 在日志、诊断或编排阶段查询

- `UniversalBiasManager`
  - 方法数：`8`
  - 方法明细：
    - `add_algorithmic_bias`（L363）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_algorithmic_bias(...)`，并结合所属类职责使用
    - `add_domain_bias`（L372）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_domain_bias(...)`，并结合所属类职责使用
    - `compute_total_algorithmic_bias`（L432）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_total_algorithmic_bias(...)`，并结合所属类职责使用
    - `compute_total_bias`（L381）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_total_bias(...)`，并结合所属类职责使用
    - `get_comprehensive_statistics`（L443）：用途=读取 `comprehensive_statistics` 相关运行态或配置值；用法=通过 `obj.get_comprehensive_statistics(...)` 在日志、诊断或编排阶段查询
    - `load_configuration`（L497）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_configuration(...)`，并结合所属类职责使用
    - `reset_all_statistics`（L527）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset_all_statistics(...)`，并结合所属类职责使用
    - `save_configuration`（L463）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.save_configuration(...)`，并结合所属类职责使用

### `bias/core/registry.py`

- `(module)`
  - 方法数：`5`
  - 方法明细：
    - `decorator`（L308）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decorator(...)`，并结合所属类职责使用
    - `get_bias_registry`（L291）：用途=读取 `bias_registry` 相关运行态或配置值；用法=通过 `obj.get_bias_registry(...)` 在日志、诊断或编排阶段查询
    - `register_algorithmic_bias`（L296）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_algorithmic_bias(...)`，并结合所属类职责使用
    - `register_bias_factory`（L332）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_bias_factory(...)`，并结合所属类职责使用
    - `register_domain_bias`（L314）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_domain_bias(...)`，并结合所属类职责使用

- `BiasRegistry`
  - 方法数：`15`
  - 方法明细：
    - `create_algorithmic_bias`（L96）：用途=创建 `algorithmic_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_bias_from_factory`（L138）：用途=创建 `bias_from_factory` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_domain_bias`（L117）：用途=创建 `domain_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `get_bias_documentation`（L209）：用途=读取 `bias_documentation` 相关运行态或配置值；用法=通过 `obj.get_bias_documentation(...)` 在日志、诊断或编排阶段查询
    - `get_bias_info`（L179）：用途=读取 `bias_info` 相关运行态或配置值；用法=通过 `obj.get_bias_info(...)` 在日志、诊断或编排阶段查询
    - `get_biases_in_category`（L175）：用途=读取 `biases_in_category` 相关运行态或配置值；用法=通过 `obj.get_biases_in_category(...)` 在日志、诊断或编排阶段查询
    - `list_algorithmic_biases`（L159）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_algorithmic_biases(...)`，并结合所属类职责使用
    - `list_bias_factories`（L167）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_bias_factories(...)`，并结合所属类职责使用
    - `list_categories`（L171）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_categories(...)`，并结合所属类职责使用
    - `list_domain_biases`（L163）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_domain_biases(...)`，并结合所属类职责使用
    - `register_algorithmic_bias`（L27）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_algorithmic_bias(...)`，并结合所属类职责使用
    - `register_bias_factory`（L75）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_bias_factory(...)`，并结合所属类职责使用
    - `register_domain_bias`（L51）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_domain_bias(...)`，并结合所属类职责使用
    - `search_biases`（L214）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search_biases(...)`，并结合所属类职责使用
    - `validate_bias_registration`（L240）：用途=校验 `bias_registration` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

### `bias/domain/callable_bias.py`

- `CallableBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L57）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/domain/constraint.py`

- `ConstraintBias`
  - 方法数：`3`
  - 方法明细：
    - `add_constraint`（L53）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_constraint(...)`，并结合所属类职责使用
    - `compute`（L79）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `get_violation_statistics`（L115）：用途=读取 `violation_statistics` 相关运行态或配置值；用法=通过 `obj.get_violation_statistics(...)` 在日志、诊断或编排阶段查询

- `FeasibilityBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L179）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `PreferenceBias`
  - 方法数：`2`
  - 方法明细：
    - `add_preference_function`（L244）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_preference_function(...)`，并结合所属类职责使用
    - `compute`（L253）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `RuleBasedBias`
  - 方法数：`3`
  - 方法明细：
    - `add_rule`（L324）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_rule(...)`，并结合所属类职责使用
    - `compute`（L357）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `get_rule_statistics`（L394）：用途=读取 `rule_statistics` 相关运行态或配置值；用法=通过 `obj.get_rule_statistics(...)` 在日志、诊断或编排阶段查询

### `bias/domain/dynamic_penalty.py`

- `DynamicPenaltyBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L121）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/domain/engineering.py`

- `EngineeringDesignBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L41）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ManufacturingBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L90）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `SafetyBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L69）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/domain/risk_bias.py`

- `RiskBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L60）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/domain/scheduling.py`

- `ResourceConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L48）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `SchedulingBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L27）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `TimeWindowBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L69）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/domain/structure_prior.py`

- `StructurePriorBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L54）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/domain/template_domain_bias.py`

- `ExampleDomainBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L33）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/library.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `create_bias_manager_from_template`（L146）：用途=创建 `bias_manager_from_template` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `quick_engineering_bias`（L178）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.quick_engineering_bias(...)`，并结合所属类职责使用
    - `quick_financial_bias`（L186）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.quick_financial_bias(...)`，并结合所属类职责使用
    - `quick_ml_bias`（L182）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.quick_ml_bias(...)`，并结合所属类职责使用

- `BiasComposer`
  - 方法数：`3`
  - 方法明细：
    - `add_algorithmic_bias_from_config`（L132）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_algorithmic_bias_from_config(...)`，并结合所属类职责使用
    - `add_domain_bias_from_config`（L137）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_domain_bias_from_config(...)`，并结合所属类职责使用
    - `build`（L142）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.build(...)`，并结合所属类职责使用

- `BiasFactory`
  - 方法数：`4`
  - 方法明细：
    - `create_algorithmic_bias`（L102）：用途=创建 `algorithmic_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_domain_bias`（L114）：用途=创建 `domain_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `list_available_algorithmic_biases`（L86）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_available_algorithmic_biases(...)`，并结合所属类职责使用
    - `list_available_domain_biases`（L94）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_available_domain_biases(...)`，并结合所属类职责使用

- `_GenericAlgorithmicBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L27）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `_GenericDomainBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L41）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/managers/adaptive_manager.py`

- `AdaptiveAlgorithmicManager`
  - 方法数：`3`
  - 方法明细：
    - `add_bias`（L63）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_bias(...)`，并结合所属类职责使用
    - `get_adaptation_history`（L328）：用途=读取 `adaptation_history` 相关运行态或配置值；用法=通过 `obj.get_adaptation_history(...)` 在日志、诊断或编排阶段查询
    - `update_state`（L70）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_state(...)`，并结合所属类职责使用

### `bias/managers/analytics.py`

- `BiasEffectivenessAnalyzer`
  - 方法数：`3`
  - 方法明细：
    - `evaluate_bias`（L69）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_bias(...)`，并结合所属类职责使用
    - `export_metrics_to_csv`（L286）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.export_metrics_to_csv(...)`，并结合所属类职责使用
    - `plot_bias_comparison`（L202）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.plot_bias_comparison(...)`，并结合所属类职责使用

### `bias/managers/meta_learning_selector.py`

- `MetaLearningBiasSelector`
  - 方法数：`6`
  - 方法明细：
    - `add_historical_data`（L197）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_historical_data(...)`，并结合所属类职责使用
    - `export_database`（L746）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.export_database(...)`，并结合所属类职责使用
    - `import_database`（L793）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_database(...)`，并结合所属类职责使用
    - `load_models`（L723）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_models(...)`，并结合所属类职责使用
    - `recommend_biases`（L267）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.recommend_biases(...)`，并结合所属类职责使用
    - `train_models`（L213）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.train_models(...)`，并结合所属类职责使用

- `ProblemFeatureExtractor`
  - 方法数：`1`
  - 方法明细：
    - `extract_features`（L84）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.extract_features(...)`，并结合所属类职责使用

### `bias/specialized/bayesian_biases.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `create_bayesian_convergence_bias`（L465）：用途=创建 `bayesian_convergence_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_bayesian_exploration_bias`（L460）：用途=创建 `bayesian_exploration_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_bayesian_guidance_bias`（L455）：用途=创建 `bayesian_guidance_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_bayesian_suite`（L470）：用途=创建 `bayesian_suite` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `BayesianConvergenceBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L409）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

- `BayesianExplorationBias`
  - 方法数：`2`
  - 方法明细：
    - `apply`（L340）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用
    - `compute`（L324）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `BayesianGuidanceBias`
  - 方法数：`2`
  - 方法明细：
    - `apply`（L90）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用
    - `compute`（L73）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `SimpleBayesianOptimizer`
  - 方法数：`2`
  - 方法明细：
    - `observe`（L22）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.observe(...)`，并结合所属类职责使用
    - `reset`（L27）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset(...)`，并结合所属类职责使用

### `bias/specialized/engineering.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `create_engineering_bias_suite`（L445）：用途=创建 `engineering_bias_suite` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_engineering_constraint_bias`（L483）：用途=创建 `engineering_constraint_bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `EngineeringConstraintBias`
  - 方法数：`3`
  - 方法明细：
    - `add_engineering_constraint`（L209）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_engineering_constraint(...)`，并结合所属类职责使用
    - `compute`（L242）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `get_constraint_status`（L285）：用途=读取 `constraint_status` 相关运行态或配置值；用法=通过 `obj.get_constraint_status(...)` 在日志、诊断或编排阶段查询

- `EngineeringPrecisionBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L72）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `EngineeringRobustnessBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L350）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/specialized/graph/abstract.py`

- `AbstractGraphProblem`
  - 方法数：`5`
  - 方法明细：
    - `decode_solution`（L105）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用
    - `evaluate_solution`（L110）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用
    - `get_encoding`（L95）：用途=读取 `encoding` 相关运行态或配置值；用法=通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询
    - `get_name`（L90）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `validate_solution`（L100）：用途=校验 `solution` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `BinaryEdgesGraphProblem`
  - 方法数：`3`
  - 方法明细：
    - `decode_edges`（L294）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_edges(...)`，并结合所属类职责使用
    - `decode_solution`（L307）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用
    - `get_encoding`（L291）：用途=读取 `encoding` 相关运行态或配置值；用法=通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询

- `CompositeGraphProblem`
  - 方法数：`6`
  - 方法明细：
    - `add_subproblem`（L595）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_subproblem(...)`，并结合所属类职责使用
    - `decode_solution`（L579）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用
    - `evaluate_solution`（L583）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用
    - `get_encoding`（L562）：用途=读取 `encoding` 相关运行态或配置值；用法=通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询
    - `get_name`（L559）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `validate_solution`（L566）：用途=校验 `solution` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `GraphColoringProblem`
  - 方法数：`3`
  - 方法明细：
    - `evaluate_solution`（L492）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用
    - `get_name`（L457）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `validate_solution`（L460）：用途=校验 `solution` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `GraphProblemFactory`
  - 方法数：`5`
  - 方法明细：
    - `create_graph_coloring`（L521）：用途=创建 `graph_coloring` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_hamiltonian_path`（L526）：用途=创建 `hamiltonian_path` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_spanning_tree`（L516）：用途=创建 `spanning_tree` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_tsp`（L511）：用途=创建 `tsp` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `get_available_problems`（L531）：用途=读取 `available_problems` 相关运行态或配置值；用法=通过 `obj.get_available_problems(...)` 在日志、诊断或编排阶段查询

- `HamiltonianPathProblem`
  - 方法数：`3`
  - 方法明细：
    - `evaluate_solution`（L270）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用
    - `get_name`（L240）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `validate_solution`（L243）：用途=校验 `solution` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `PartitionGraphProblem`
  - 方法数：`3`
  - 方法明细：
    - `decode_partition`（L434）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_partition(...)`，并结合所属类职责使用
    - `decode_solution`（L440）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用
    - `get_encoding`（L431）：用途=读取 `encoding` 相关运行态或配置值；用法=通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询

- `PermutationGraphProblem`
  - 方法数：`3`
  - 方法明细：
    - `decode_solution`（L171）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_solution(...)`，并结合所属类职责使用
    - `get_encoding`（L127）：用途=读取 `encoding` 相关运行态或配置值；用法=通过 `obj.get_encoding(...)` 在日志、诊断或编排阶段查询
    - `validate_permutation_constraints`（L130）：用途=校验 `permutation_constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `SpanningTreeProblem`
  - 方法数：`5`
  - 方法明细：
    - `evaluate_solution`（L408）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用
    - `find`（L389）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.find(...)`，并结合所属类职责使用
    - `get_name`（L327）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `union`（L395）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.union(...)`，并结合所属类职责使用
    - `validate_solution`（L330）：用途=校验 `solution` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `TSPProblem`
  - 方法数：`3`
  - 方法明细：
    - `evaluate_solution`（L212）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_solution(...)`，并结合所属类职责使用
    - `get_name`（L193）：用途=读取 `name` 相关运行态或配置值；用法=通过 `obj.get_name(...)` 在日志、诊断或编排阶段查询
    - `validate_solution`（L196）：用途=校验 `solution` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

### `bias/specialized/graph/base.py`

- `CommunityDetectionBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L454）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ConnectivityBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L189）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `DegreeDistributionBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L256）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `GraphBias`
  - 方法数：`1`
  - 方法明细：
    - `encode_solution_to_graph`（L171）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.encode_solution_to_graph(...)`，并结合所属类职责使用

- `GraphBiasFactory`
  - 方法数：`2`
  - 方法明细：
    - `create_bias`（L494）：用途=创建 `bias` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `get_available_biases`（L513）：用途=读取 `available_biases` 相关运行态或配置值；用法=通过 `obj.get_available_biases(...)` 在日志、诊断或编排阶段查询

- `GraphColoringBias`
  - 方法数：`2`
  - 方法明细：
    - `compute`（L415）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `encode_solution_to_graph`（L433）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.encode_solution_to_graph(...)`，并结合所属类职责使用

- `GraphUtils`
  - 方法数：`2`
  - 方法明细：
    - `compute_graph_properties`（L80）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_graph_properties(...)`，并结合所属类职责使用
    - `extract_subgraph`（L134）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.extract_subgraph(...)`，并结合所属类职责使用

- `MaxFlowBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L374）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ShortestPathBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L328）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `SparsityBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L229）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

### `bias/specialized/graph/constraints.py`

- `CompositeGraphConstraintBias`
  - 方法数：`2`
  - 方法明细：
    - `add_constraint`（L691）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_constraint(...)`，并结合所属类职责使用
    - `validate_constraints`（L682）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `GraphColoringConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `validate_constraints`（L428）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `GraphConstraintBias`
  - 方法数：`2`
  - 方法明细：
    - `compute`（L69）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用
    - `validate_constraints`（L81）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `GraphConstraintFactory`
  - 方法数：`2`
  - 方法明细：
    - `create_constraint`（L633）：用途=创建 `constraint` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `get_available_constraints`（L651）：用途=读取 `available_constraints` 相关运行态或配置值；用法=通过 `obj.get_available_constraints(...)` 在日志、诊断或编排阶段查询

- `HamiltonianPathConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `validate_constraints`（L566）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `MatchingConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `validate_constraints`（L491）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `PathConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `validate_constraints`（L217）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `TSPConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `validate_constraints`（L111）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `TreeConstraintBias`
  - 方法数：`3`
  - 方法明细：
    - `find`（L386）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.find(...)`，并结合所属类职责使用
    - `union`（L392）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.union(...)`，并结合所属类职责使用
    - `validate_constraints`（L304）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

### `bias/specialized/local_search.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `create_derivative_free_suite`（L800）：用途=创建 `derivative_free_suite` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_gradient_descent_suite`（L775）：用途=创建 `gradient_descent_suite` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_hybrid_local_suite`（L791）：用途=创建 `hybrid_local_suite` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `create_newton_suite`（L783）：用途=创建 `newton_suite` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `GradientDescentBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L69）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `LineSearchBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L332）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

- `NelderMeadBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L601）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

- `NewtonMethodBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L199）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

- `QuasiNewtonBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L708）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

- `TrustRegionBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L458）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

### `bias/specialized/production/scheduling.py`

- `ProductionConstraintBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L137）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ProductionContinuityBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L225）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ProductionDiversityBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L203）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ProductionSchedulingBias`
  - 方法数：`1`
  - 方法明细：
    - `compute`（L253）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute(...)`，并结合所属类职责使用

- `ProductionSchedulingBiasManager`
  - 方法数：`1`
  - 方法明细：
    - `compute_bias`（L90）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_bias(...)`，并结合所属类职责使用

### `bias/surrogate/base.py`

- `SurrogateBiasContext`
  - 方法数：`2`
  - 方法明细：
    - `get`（L33）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `progress`（L28）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.progress(...)`，并结合所属类职责使用

- `SurrogateControlBias`
  - 方法数：`2`
  - 方法明细：
    - `apply`（L55）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用
    - `should_apply`（L52）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.should_apply(...)`，并结合所属类职责使用

### `bias/surrogate/phase_schedule.py`

- `PhaseScheduleBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L31）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

### `bias/surrogate/template_surrogate_bias.py`

- `ExampleSurrogateBias`
  - 方法数：`1`
  - 方法明细：
    - `apply`（L20）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用

### `bias/surrogate/uncertainty_budget.py`

- `UncertaintyBudgetBias`
  - 方法数：`2`
  - 方法明细：
    - `apply`（L51）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply(...)`，并结合所属类职责使用
    - `should_apply`（L47）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.should_apply(...)`，并结合所属类职责使用

### `bias/utils/helpers.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `create_universal_bias_manager`（L11）：用途=创建 `universal_bias_manager` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `get_bias_system_info`（L112）：用途=读取 `bias_system_info` 相关运行态或配置值；用法=通过 `obj.get_bias_system_info(...)` 在日志、诊断或编排阶段查询
    - `quick_bias_setup`（L44）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.quick_bias_setup(...)`，并结合所属类职责使用

### `catalog/__init__.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `get_entry`（L39）：用途=读取 `entry` 相关运行态或配置值；用法=通过 `obj.get_entry(...)` 在日志、诊断或编排阶段查询
    - `list_catalog`（L34）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_catalog(...)`，并结合所属类职责使用
    - `reload_catalog`（L44）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reload_catalog(...)`，并结合所属类职责使用
    - `search_catalog`（L29）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search_catalog(...)`，并结合所属类职责使用

### `catalog/markers.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `component`（L6）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.component(...)`，并结合所属类职责使用

### `catalog/quick_add.py`

- `(module)`
  - 方法数：`5`
  - 方法明细：
    - `build_entry_payload`（L22）：用途=构建 `entry_payload` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `main`（L194）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.main(...)`，并结合所属类职责使用
    - `remove_catalog_entry`（L144）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.remove_catalog_entry(...)`，并结合所属类职责使用
    - `render_entry_block`（L88）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.render_entry_block(...)`，并结合所属类职责使用
    - `upsert_catalog_entry`（L111）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.upsert_catalog_entry(...)`，并结合所属类职责使用

### `catalog/registry.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `get_catalog`（L2559）：用途=读取 `catalog` 相关运行态或配置值；用法=通过 `obj.get_catalog(...)` 在日志、诊断或编排阶段查询
    - `parse_items`（L2370）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.parse_items(...)`，并结合所属类职责使用

- `BuiltinTomlProvider`
  - 方法数：`1`
  - 方法明细：
    - `load`（L2521）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load(...)`，并结合所属类职责使用

- `Catalog`
  - 方法数：`6`
  - 方法明细：
    - `add_field`（L212）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_field(...)`，并结合所属类职责使用
    - `get`（L64）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `list`（L70）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list(...)`，并结合所属类职责使用
    - `match`（L106）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.match(...)`，并结合所属类职责使用
    - `rank`（L135）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.rank(...)`，并结合所属类职责使用
    - `search`（L80）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search(...)`，并结合所属类职责使用

- `CatalogEntry`
  - 方法数：`1`
  - 方法明细：
    - `load`（L47）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load(...)`，并结合所属类职责使用

- `CatalogProvider`
  - 方法数：`1`
  - 方法明细：
    - `load`（L2438）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load(...)`，并结合所属类职责使用

- `EnvTomlProvider`
  - 方法数：`1`
  - 方法明细：
    - `load`（L2535）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load(...)`，并结合所属类职责使用

### `catalog/source_sync.py`

- `(module)`
  - 方法数：`5`
  - 方法明细：
    - `apply_symbol_contract`（L405）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply_symbol_contract(...)`，并结合所属类职责使用
    - `detect_expansion_scope`（L93）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.detect_expansion_scope(...)`，并结合所属类职责使用
    - `expand_marked_component_template`（L329）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.expand_marked_component_template(...)`，并结合所属类职责使用
    - `list_source_symbols`（L106）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_source_symbols(...)`，并结合所属类职责使用
    - `read_symbol_contract`（L147）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read_symbol_contract(...)`，并结合所属类职责使用

### `catalog/usage.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `build_usage_profile`（L157）：用途=构建 `usage_profile` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `enrich_context_contracts`（L180）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.enrich_context_contracts(...)`，并结合所属类职责使用
    - `enrich_usage_contracts`（L229）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.enrich_usage_contracts(...)`，并结合所属类职责使用

### `core/acceleration.py`

- `AccelerationBackend`
  - 方法数：`1`
  - 方法明细：
    - `run`（L13）：用途=执行完整生命周期主流程；用法=直接调用 `instance.run(...)` 作为入口

- `AccelerationFacade`
  - 方法数：`3`
  - 方法明细：
    - `get`（L91）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `list_backends`（L94）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_backends(...)`，并结合所属类职责使用
    - `register`（L88）：用途=注册组件到管理器；用法=初始化时挂载插件/子组件

- `AccelerationRegistry`
  - 方法数：`4`
  - 方法明细：
    - `get`（L62）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `global_registry`（L48）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.global_registry(...)`，并结合所属类职责使用
    - `list_backends`（L73）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_backends(...)`，并结合所属类职责使用
    - `register`（L53）：用途=注册组件到管理器；用法=初始化时挂载插件/子组件

- `NoopAccelerationBackend`
  - 方法数：`1`
  - 方法明细：
    - `run`（L20）：用途=执行完整生命周期主流程；用法=直接调用 `instance.run(...)` 作为入口

### `core/base.py`

- `BlackBoxProblem`
  - 方法数：`5`
  - 方法明细：
    - `evaluate`（L42）：用途=执行问题评估并产出目标值；用法=由评估链路调用，输入单个 candidate
    - `evaluate_constraints`（L46）：用途=计算约束违背信息；用法=在目标评估后统一汇总 violation
    - `get_num_objectives`（L100）：用途=读取 `num_objectives` 相关运行态或配置值；用法=通过 `obj.get_num_objectives(...)` 在日志、诊断或编排阶段查询
    - `is_multiobjective`（L105）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_multiobjective(...)`，并结合所属类职责使用
    - `is_valid`（L62）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_valid(...)`，并结合所属类职责使用

### `core/blank_solver.py`

- `SolverBase`
  - 方法数：`55`
  - 方法明细：
    - `add_plugin`（L374）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_plugin(...)`，并结合所属类职责使用
    - `bias_module`（L304）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.bias_module(...)`，并结合所属类职责使用
    - `build_context`（L1109）：用途=构建 `context` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `decode_candidate`（L750）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decode_candidate(...)`，并结合所属类职责使用
    - `enable_bias_module`（L366）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.enable_bias_module(...)`，并结合所属类职责使用
    - `encode_candidate`（L744）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.encode_candidate(...)`，并结合所属类职责使用
    - `evaluate_individual`（L1151）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L1154）：用途=批量评估入口；用法=算法主路径与并行评估常用入口
    - `fork_rng`（L1072）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.fork_rng(...)`，并结合所属类职责使用
    - `get_acceleration_backend`（L661）：用途=读取 `acceleration_backend` 相关运行态或配置值；用法=通过 `obj.get_acceleration_backend(...)` 在日志、诊断或编排阶段查询
    - `get_best_snapshot`（L696）：用途=读取 `best_snapshot` 相关运行态或配置值；用法=通过 `obj.get_best_snapshot(...)` 在日志、诊断或编排阶段查询
    - `get_context`（L1126）：用途=读取 `context` 相关运行态或配置值；用法=通过 `obj.get_context(...)` 在日志、诊断或编排阶段查询
    - `get_plugin`（L503）：用途=读取 `plugin` 相关运行态或配置值；用法=通过 `obj.get_plugin(...)` 在日志、诊断或编排阶段查询
    - `get_rng_state`（L1082）：用途=读取 `rng_state` 相关运行态或配置值；用法=通过 `obj.get_rng_state(...)` 在日志、诊断或编排阶段查询
    - `has_bias_support`（L644）：用途=判断是否具备 `bias_support` 能力；用法=在装配分支中调用并据此选择能力路径
    - `has_numba_support`（L649）：用途=判断是否具备 `numba_support` 能力；用法=在装配分支中调用并据此选择能力路径
    - `increment_evaluation_count`（L670）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.increment_evaluation_count(...)`，并结合所属类职责使用
    - `init_bias_module`（L327）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.init_bias_module(...)`，并结合所属类职责使用
    - `init_candidate`（L719）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.init_candidate(...)`，并结合所属类职责使用
    - `initialize_population`（L773）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.initialize_population(...)`，并结合所属类职责使用
    - `mutate_candidate`（L728）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.mutate_candidate(...)`，并结合所属类职责使用
    - `read_snapshot`（L962）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read_snapshot(...)`，并结合所属类职责使用
    - `register_acceleration_backend`（L658）：用途=注册加速后端；用法=并行/硬件加速能力接入
    - `register_controller`（L652）：用途=注册控制器到控制平面；用法=接入 stopping/switch/budget 控制逻辑
    - `register_evaluation_provider`（L655）：用途=注册 L4 评估提供器；用法=接入 surrogate/multi-fidelity 等路径
    - `remove_plugin`（L494）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.remove_plugin(...)`，并结合所属类职责使用
    - `repair_candidate`（L736）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.repair_candidate(...)`，并结合所属类职责使用
    - `representation_pipeline`（L353）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.representation_pipeline(...)`，并结合所属类职责使用
    - `request_plugin_order`（L551）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_plugin_order(...)`，并结合所属类职责使用
    - `request_stop`（L1183）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_stop(...)`，并结合所属类职责使用
    - `run`（L1195）：用途=执行完整生命周期主流程；用法=直接调用 `instance.run(...)` 作为入口
    - `set_adapter`（L599）：用途=设置主适配器；用法=solver 装配或切换算法时调用
    - `set_best_snapshot`（L678）：用途=设置 `best_snapshot` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_best_snapshot(...)`
    - `set_bias_enabled`（L636）：用途=设置 `bias_enabled` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_bias_enabled(...)`
    - `set_bias_module`（L626）：用途=设置 `bias_module` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_bias_module(...)`
    - `set_context_store`（L245）：用途=注入 context 存储实现；用法=运行前配置状态存储后端
    - `set_context_store_backend`（L251）：用途=设置 `context_store_backend` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_context_store_backend(...)`
    - `set_generation`（L667）：用途=设置 `generation` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_generation(...)`
    - `set_max_steps`（L664）：用途=设置 `max_steps` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_max_steps(...)`
    - `set_pareto_snapshot`（L687）：用途=设置 `pareto_snapshot` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_pareto_snapshot(...)`
    - `set_phase_controller`（L606）：用途=设置 `phase_controller` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_phase_controller(...)`
    - `set_plugin_order`（L506）：用途=设置 `plugin_order` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_plugin_order(...)`
    - `set_random_seed`（L1054）：用途=设置 `random_seed` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_random_seed(...)`
    - `set_representation_pipeline`（L641）：用途=设置 `representation_pipeline` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_representation_pipeline(...)`
    - `set_rng_state`（L1085）：用途=设置 `rng_state` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_rng_state(...)`
    - `set_snapshot_store`（L248）：用途=注入 snapshot 存储实现；用法=运行前配置大对象快照后端
    - `set_snapshot_store_backend`（L268）：用途=设置 `snapshot_store_backend` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_snapshot_store_backend(...)`
    - `set_solver_hyperparams`（L699）：用途=设置 `solver_hyperparams` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_solver_hyperparams(...)`
    - `set_strategy_controller`（L602）：用途=设置 `strategy_controller` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_strategy_controller(...)`
    - `setup`（L1186）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `step`（L1189）：用途=执行一个离散迭代步；用法=用于调试或外部细粒度驱动
    - `teardown`（L1192）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report
    - `validate_control_plane`（L590）：用途=校验 `control_plane` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置
    - `validate_plugin_order`（L584）：用途=校验 `plugin_order` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置
    - `write_population_snapshot`（L792）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.write_population_snapshot(...)`，并结合所属类职责使用

### `core/composable_solver.py`

- `ComposableSolver`
  - 方法数：`6`
  - 方法明细：
    - `select_best`（L136）：用途=选择 `best` 候选或策略；用法=在决策阶段调用，根据上下文返回最优分支
    - `set_adapter`（L76）：用途=设置主适配器；用法=solver 装配或切换算法时调用
    - `set_adapters`（L79）：用途=设置 `adapters` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_adapters(...)`
    - `setup`（L82）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `step`（L90）：用途=执行一个离散迭代步；用法=用于调试或外部细粒度驱动
    - `teardown`（L86）：用途=释放资源并收尾持久化；用法=在 `run` 结束后自动调用，可用于 flush/report

### `core/control_plane.py`

- `BaseController`
  - 方法数：`1`
  - 方法明细：
    - `propose`（L40）：用途=生成待评估候选解；用法=由 solver 在评估前调用，返回候选序列

- `ControlArbiter`
  - 方法数：`1`
  - 方法明细：
    - `resolve`（L50）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.resolve(...)`，并结合所属类职责使用

- `RuntimeController`
  - 方法数：`5`
  - 方法明细：
    - `collect`（L136）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.collect(...)`，并结合所属类职责使用
    - `list_controllers`（L133）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_controllers(...)`，并结合所属类职责使用
    - `register_controller`（L118）：用途=注册控制器到控制平面；用法=接入 stopping/switch/budget 控制逻辑
    - `resolve`（L149）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.resolve(...)`，并结合所属类职责使用
    - `validate_configuration`（L153）：用途=校验 `configuration` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

### `core/evaluation_runtime.py`

- `EvaluationMediator`
  - 方法数：`4`
  - 方法明细：
    - `evaluate_individual`（L64）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L105）：用途=批量评估入口；用法=算法主路径与并行评估常用入口
    - `list_providers`（L61）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_providers(...)`，并结合所属类职责使用
    - `register_provider`（L52）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_provider(...)`，并结合所属类职责使用

- `EvaluationProvider`
  - 方法数：`4`
  - 方法明细：
    - `can_handle_individual`（L15）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L27）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L18）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L30）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `core/evolution_solver.py`

- `EvolutionSolver`
  - 方法数：`19`
  - 方法明细：
    - `crossover`（L490）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.crossover(...)`，并结合所属类职责使用
    - `environmental_selection`（L558）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.environmental_selection(...)`，并结合所属类职责使用
    - `evaluate_population`（L310）：用途=批量评估入口；用法=算法主路径与并行评估常用入口
    - `initialize_population`（L327）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.initialize_population(...)`，并结合所属类职责使用
    - `mutate`（L525）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解
    - `non_dominated_sorting`（L447）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.non_dominated_sorting(...)`，并结合所属类职责使用
    - `record_history`（L625）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_history(...)`，并结合所属类职责使用
    - `representation_pipeline`（L162）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.representation_pipeline(...)`，并结合所属类职责使用
    - `run`（L679）：用途=执行完整生命周期主流程；用法=直接调用 `instance.run(...)` 作为入口
    - `selection`（L469）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.selection(...)`，并结合所属类职责使用
    - `set_adapter`（L179）：用途=设置主适配器；用法=solver 装配或切换算法时调用
    - `set_context_store`（L208）：用途=注入 context 存储实现；用法=运行前配置状态存储后端
    - `set_context_store_backend`（L214）：用途=设置 `context_store_backend` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_context_store_backend(...)`
    - `set_snapshot_store`（L211）：用途=注入 snapshot 存储实现；用法=运行前配置大对象快照后端
    - `set_snapshot_store_backend`（L229）：用途=设置 `snapshot_store_backend` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_snapshot_store_backend(...)`
    - `set_solver_hyperparams`（L183）：用途=设置 `solver_hyperparams` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_solver_hyperparams(...)`
    - `setup`（L345）：用途=初始化组件运行态并绑定上下文；用法=在 `run/setup` 阶段由框架调用，通常不手工频繁触发
    - `step`（L379）：用途=执行一个离散迭代步；用法=用于调试或外部细粒度驱动
    - `update_pareto_solutions`（L599）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_pareto_solutions(...)`，并结合所属类职责使用

### `core/interfaces.py`

- `(module)`
  - 方法数：`7`
  - 方法明细：
    - `create_bias_context`（L194）：用途=创建 `bias_context` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `has_bias_module`（L136）：用途=判断是否具备 `bias_module` 能力；用法=在装配分支中调用并据此选择能力路径
    - `has_numba`（L164）：用途=判断是否具备 `numba` 能力；用法=在装配分支中调用并据此选择能力路径
    - `has_representation_module`（L145）：用途=判断是否具备 `representation_module` 能力；用法=在装配分支中调用并据此选择能力路径
    - `has_visualization_module`（L154）：用途=判断是否具备 `visualization_module` 能力；用法=在装配分支中调用并据此选择能力路径
    - `load_bias_module`（L174）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_bias_module(...)`，并结合所属类职责使用
    - `load_representation_pipeline`（L183）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_representation_pipeline(...)`，并结合所属类职责使用

- `BiasInterface`
  - 方法数：`5`
  - 方法明细：
    - `add_bias`（L35）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_bias(...)`，并结合所属类职责使用
    - `compute_bias`（L31）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compute_bias(...)`，并结合所属类职责使用
    - `disable`（L47）：用途=禁用功能开关；用法=运行中灰度关闭能力
    - `enable`（L43）：用途=启用功能开关；用法=运行中灰度打开能力
    - `is_enabled`（L39）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_enabled(...)`，并结合所属类职责使用

- `ExperimentResultInterface`
  - 方法数：`3`
  - 方法明细：
    - `add_result`（L126）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_result(...)`，并结合所属类职责使用
    - `save`（L129）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.save(...)`，并结合所属类职责使用
    - `to_dict`（L132）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.to_dict(...)`，并结合所属类职责使用

- `OptimizationContext`
  - 方法数：`1`
  - 方法明细：
    - `get_statistics`（L23）：用途=读取 `statistics` 相关运行态或配置值；用法=通过 `obj.get_statistics(...)` 在日志、诊断或编排阶段查询

- `PluginInterface`
  - 方法数：`6`
  - 方法明细：
    - `on_generation_end`（L113）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L110）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L107）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L119）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L104）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `on_step`（L116）：用途=步级别钩子；用法=需要更细粒度监控时使用

- `RepresentationInterface`
  - 方法数：`6`
  - 方法明细：
    - `decode`（L75）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L71）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用
    - `init`（L55）：用途=初始化候选或批次；用法=solver 初始化种群时触发
    - `initialize`（L59）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用
    - `mutate`（L63）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解
    - `repair`（L67）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `SimpleContext`
  - 方法数：`1`
  - 方法明细：
    - `get_statistics`（L211）：用途=读取 `statistics` 相关运行态或配置值；用法=通过 `obj.get_statistics(...)` 在日志、诊断或编排阶段查询

- `VisualizationInterface`
  - 方法数：`3`
  - 方法明细：
    - `plot_convergence`（L92）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.plot_convergence(...)`，并结合所属类职责使用
    - `plot_diversity`（L96）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.plot_diversity(...)`，并结合所属类职责使用
    - `plot_pareto_front`（L83）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.plot_pareto_front(...)`，并结合所属类职责使用

### `core/nested_solver.py`

- `InnerRuntimeEvaluator`
  - 方法数：`2`
  - 方法明细：
    - `can_handle`（L68）：用途=判断当前是否可执行 `handle`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate`（L74）：用途=执行问题评估并产出目标值；用法=由评估链路调用，输入单个 candidate

- `TaskInnerRuntimeEvaluator`
  - 方法数：`2`
  - 方法明细：
    - `can_handle`（L219）：用途=判断当前是否可执行 `handle`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate`（L229）：用途=执行问题评估并产出目标值；用法=由评估链路调用，输入单个 candidate

### `core/solver_helpers/bias_helpers.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `apply_bias_module`（L29）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply_bias_module(...)`，并结合所属类职责使用

### `core/solver_helpers/candidate_helpers.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `sample_random_candidate`（L10）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.sample_random_candidate(...)`，并结合所属类职责使用

### `core/solver_helpers/component_scheduler.py`

- `ComponentDependencyScheduler`
  - 方法数：`8`
  - 方法明细：
    - `register_component`（L45）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_component(...)`，并结合所属类职责使用
    - `resolve_order`（L153）：用途=解析并确定 `order` 最终结果；用法=在多来源配置合并时调用 `obj.resolve_order(...)`
    - `resolve_order_strict`（L156）：用途=解析并确定 `order_strict` 最终结果；用法=在多来源配置合并时调用 `obj.resolve_order_strict(...)`
    - `restore_rules`（L85）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.restore_rules(...)`，并结合所属类职责使用
    - `set_constraints`（L96）：用途=设置 `constraints` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_constraints(...)`
    - `snapshot_rules`（L75）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot_rules(...)`，并结合所属类职责使用
    - `unregister_component`（L64）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.unregister_component(...)`，并结合所属类职责使用
    - `validate_constraints`（L115）：用途=校验 `constraints` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

### `core/solver_helpers/context_helpers.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `build_solver_context`（L35）：用途=构建 `solver_context` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `ensure_snapshot_readable`（L147）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.ensure_snapshot_readable(...)`，并结合所属类职责使用
    - `get_solver_context_view`（L112）：用途=读取 `solver_context_view` 相关运行态或配置值；用法=通过 `obj.get_solver_context_view(...)` 在日志、诊断或编排阶段查询

### `core/solver_helpers/control_plane_helpers.py`

- `(module)`
  - 方法数：`6`
  - 方法明细：
    - `collect_runtime_context_projection`（L164）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.collect_runtime_context_projection(...)`，并结合所属类职责使用
    - `get_best_snapshot_fields`（L113）：用途=读取 `best_snapshot_fields` 相关运行态或配置值；用法=通过 `obj.get_best_snapshot_fields(...)` 在日志、诊断或编排阶段查询
    - `increment_evaluation_counter`（L35）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.increment_evaluation_counter(...)`，并结合所属类职责使用
    - `set_best_snapshot_fields`（L58）：用途=设置 `best_snapshot_fields` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_best_snapshot_fields(...)`
    - `set_generation_value`（L29）：用途=设置 `generation_value` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_generation_value(...)`
    - `set_pareto_snapshot_fields`（L80）：用途=设置 `pareto_snapshot_fields` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_pareto_snapshot_fields(...)`

### `core/solver_helpers/evaluation_helpers.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `evaluate_individual_with_plugins_and_bias`（L24）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_individual_with_plugins_and_bias(...)`，并结合所属类职责使用
    - `evaluate_population_with_plugins_and_bias`（L126）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_population_with_plugins_and_bias(...)`，并结合所属类职责使用

### `core/solver_helpers/result_helpers.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `format_run_result`（L8）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.format_run_result(...)`，并结合所属类职责使用

### `core/solver_helpers/run_helpers.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `apply_runtime_control_slot`（L9）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply_runtime_control_slot(...)`，并结合所属类职责使用
    - `run_solver_loop`（L36）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_solver_loop(...)`，并结合所属类职责使用

### `core/solver_helpers/snapshot_helpers.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `build_snapshot_payload`（L78）：用途=构建 `snapshot_payload` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `build_snapshot_refs`（L127）：用途=构建 `snapshot_refs` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `snapshot_meta`（L48）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot_meta(...)`，并结合所属类职责使用
    - `strip_large_context_fields`（L42）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.strip_large_context_fields(...)`，并结合所属类职责使用

### `core/solver_helpers/store_helpers.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `build_context_store_or_memory`（L11）：用途=构建 `context_store_or_memory` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `build_snapshot_store_or_memory`（L39）：用途=构建 `snapshot_store_or_memory` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程

### `nsgablack/__init__.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `get_available_features`（L124）：用途=读取 `available_features` 相关运行态或配置值；用法=通过 `obj.get_available_features(...)` 在日志、诊断或编排阶段查询
    - `get_package_info`（L119）：用途=读取 `package_info` 相关运行态或配置值；用法=通过 `obj.get_package_info(...)` 在日志、诊断或编排阶段查询
    - `get_version`（L114）：用途=读取 `version` 相关运行态或配置值；用法=通过 `obj.get_version(...)` 在日志、诊断或编排阶段查询

### `nsgablack/__main__.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `build_parser`（L569）：用途=构建 `parser` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `main`（L718）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.main(...)`，并结合所属类职责使用

### `nsgablack/examples_registry.py`

- `(module)`
  - 方法数：`31`
  - 方法明细：
    - `astar_demo`（L87）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.astar_demo(...)`，并结合所属类职责使用
    - `async_event_driven_demo`（L127）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.async_event_driven_demo(...)`，并结合所属类职责使用
    - `bias_gallery_demo`（L75）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.bias_gallery_demo(...)`，并结合所属类职责使用
    - `context_keys_demo`（L107）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.context_keys_demo(...)`，并结合所属类职责使用
    - `context_schema_demo`（L111）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.context_schema_demo(...)`，并结合所属类职责使用
    - `dynamic_cli_signal_demo`（L123）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.dynamic_cli_signal_demo(...)`，并结合所属类职责使用
    - `dynamic_multi_strategy_demo`（L47）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.dynamic_multi_strategy_demo(...)`，并结合所属类职责使用
    - `gpu_ray_mysql_stack_demo`（L135）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.gpu_ray_mysql_stack_demo(...)`，并结合所属类职责使用
    - `logging_demo`（L115）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.logging_demo(...)`，并结合所属类职责使用
    - `metrics_demo`（L119）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.metrics_demo(...)`，并结合所属类职责使用
    - `moa_star_demo`（L91）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.moa_star_demo(...)`，并结合所属类职责使用
    - `monte_carlo_dp_robust_demo`（L59）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.monte_carlo_dp_robust_demo(...)`，并结合所属类职责使用
    - `multi_fidelity_demo`（L67）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.multi_fidelity_demo(...)`，并结合所属类职责使用
    - `nsga2_solver_demo`（L99）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.nsga2_solver_demo(...)`，并结合所属类职责使用
    - `parallel_evaluator_demo`（L103）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.parallel_evaluator_demo(...)`，并结合所属类职责使用
    - `parallel_repair_demo`（L95）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.parallel_repair_demo(...)`，并结合所属类职责使用
    - `plugin_gallery_demo`（L79）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.plugin_gallery_demo(...)`，并结合所属类职责使用
    - `risk_bias_demo`（L71）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.risk_bias_demo(...)`，并结合所属类职责使用
    - `role_adapters_demo`（L83）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.role_adapters_demo(...)`，并结合所属类职责使用
    - `single_trajectory_adaptive_demo`（L131）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.single_trajectory_adaptive_demo(...)`，并结合所属类职责使用
    - `surrogate_plugin_demo`（L63）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.surrogate_plugin_demo(...)`，并结合所属类职责使用
    - `template_assignment_matrix`（L31）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_assignment_matrix(...)`，并结合所属类职责使用
    - `template_continuous_constrained`（L15）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_continuous_constrained(...)`，并结合所属类职责使用
    - `template_graph_path`（L35）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_graph_path(...)`，并结合所属类职责使用
    - `template_knapsack_binary`（L19）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_knapsack_binary(...)`，并结合所属类职责使用
    - `template_multiobjective_pareto`（L27）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_multiobjective_pareto(...)`，并结合所属类职责使用
    - `template_portfolio_pareto`（L43）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_portfolio_pareto(...)`，并结合所属类职责使用
    - `template_production_schedule_simple`（L39）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_production_schedule_simple(...)`，并结合所属类职责使用
    - `template_tsp_permutation`（L23）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.template_tsp_permutation(...)`，并结合所属类职责使用
    - `trust_region_dfo_demo`（L51）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.trust_region_dfo_demo(...)`，并结合所属类职责使用
    - `trust_region_subspace_demo`（L55）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.trust_region_subspace_demo(...)`，并结合所属类职责使用

### `plugins/base.py`

- `Plugin`
  - 方法数：`17`
  - 方法明细：
    - `attach`（L91）：用途=附着到 solver 生命周期；用法=通过 `add_plugin` 后自动调用
    - `commit_population_snapshot`（L272）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.commit_population_snapshot(...)`，并结合所属类职责使用
    - `configure`（L107）：用途=注入运行配置；用法=初始化或外部配置变更时调用
    - `create_local_rng`（L67）：用途=创建 `local_rng` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `detach`（L95）：用途=从 solver 生命周期解绑；用法=插件卸载或结束时调用
    - `disable`（L103）：用途=禁用功能开关；用法=运行中灰度关闭能力
    - `enable`（L99）：用途=启用功能开关；用法=运行中灰度打开能力
    - `get_config`（L111）：用途=读取当前配置；用法=用于审计/可视化/调试
    - `get_context_contract`（L57）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `get_population_snapshot`（L152）：用途=读取 `population_snapshot` 相关运行态或配置值；用法=通过 `obj.get_population_snapshot(...)` 在日志、诊断或编排阶段查询
    - `get_report`（L134）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_generation_end`（L125）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L122）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L119）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L131）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L116）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `on_step`（L128）：用途=步级别钩子；用法=需要更细粒度监控时使用

- `PluginManager`
  - 方法数：`17`
  - 方法明细：
    - `clear`（L720）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear(...)`，并结合所属类职责使用
    - `disable`（L470）：用途=禁用功能开关；用法=运行中灰度关闭能力
    - `dispatch`（L576）：用途=分发事件到订阅者；用法=manager/总线在生命周期节点触发
    - `enable`（L465）：用途=启用功能开关；用法=运行中灰度打开能力
    - `get`（L461）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `list_plugins`（L714）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.list_plugins(...)`，并结合所属类职责使用
    - `on_generation_end`（L705）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L702）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L699）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L711）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L676）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `on_step`（L708）：用途=步级别钩子；用法=需要更细粒度监控时使用
    - `register`（L441）：用途=注册组件到管理器；用法=初始化时挂载插件/子组件
    - `set_event_hook`（L387）：用途=设置 `event_hook` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_event_hook(...)`
    - `set_execution_order`（L475）：用途=设置 `execution_order` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_execution_order(...)`
    - `trigger`（L498）：用途=触发指定事件；用法=显式触发事件链并执行监听回调
    - `unregister`（L452）：用途=从管理器移除组件；用法=动态卸载或收尾阶段调用

### `plugins/evaluation/broyden_solver_plugin.py`

- `BroydenSolverProviderPlugin`
  - 方法数：`1`
  - 方法明细：
    - `solve_backend`（L29）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve_backend(...)`，并结合所属类职责使用

### `plugins/evaluation/evaluation_model.py`

- `EvaluationModelProviderPlugin`
  - 方法数：`3`
  - 方法明细：
    - `create_provider`（L147）：用途=创建 `provider` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `evaluate_individual_runtime`（L98）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_individual_runtime(...)`，并结合所属类职责使用
    - `evaluate_model`（L66）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_model(...)`，并结合所属类职责使用

- `_Provider`
  - 方法数：`5`
  - 方法明细：
    - `can_handle_individual`（L155）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L169）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L161）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_model`（L181）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_model(...)`，并结合所属类职责使用
    - `evaluate_population`（L175）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `plugins/evaluation/gpu_evaluation_template.py`

- `GpuEvaluationTemplateProviderPlugin`
  - 方法数：`2`
  - 方法明细：
    - `create_provider`（L140）：用途=创建 `provider` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `evaluate_population_runtime`（L88）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用

- `_Provider`
  - 方法数：`4`
  - 方法明细：
    - `can_handle_individual`（L147）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L160）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L151）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L165）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `plugins/evaluation/monte_carlo_evaluation.py`

- `MonteCarloEvaluationProviderPlugin`
  - 方法数：`2`
  - 方法明细：
    - `create_provider`（L159）：用途=创建 `provider` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `evaluate_population_runtime`（L62）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用

- `_Provider`
  - 方法数：`4`
  - 方法明细：
    - `can_handle_individual`（L166）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L177）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L171）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L182）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `plugins/evaluation/multi_fidelity_evaluation.py`

- `MultiFidelityEvaluationProviderPlugin`
  - 方法数：`2`
  - 方法明细：
    - `create_provider`（L148）：用途=创建 `provider` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `evaluate_population_runtime`（L48）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用

- `_Provider`
  - 方法数：`4`
  - 方法明细：
    - `can_handle_individual`（L155）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L169）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L163）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L178）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `plugins/evaluation/newton_solver_plugin.py`

- `NewtonSolverProviderPlugin`
  - 方法数：`1`
  - 方法明细：
    - `solve_backend`（L29）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve_backend(...)`，并结合所属类职责使用

### `plugins/evaluation/numerical_solver_base.py`

- `NumericalSolverProviderPlugin`
  - 方法数：`4`
  - 方法明细：
    - `create_provider`（L264）：用途=创建 `provider` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `evaluate_individual_runtime`（L181）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_individual_runtime(...)`，并结合所属类职责使用
    - `get_report`（L261）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `solve_backend`（L83）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve_backend(...)`，并结合所属类职责使用

- `_Provider`
  - 方法数：`4`
  - 方法明细：
    - `can_handle_individual`（L271）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L284）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L276）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L290）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `plugins/evaluation/surrogate_evaluation.py`

- `SurrogateEvaluationProviderPlugin`
  - 方法数：`2`
  - 方法明细：
    - `create_provider`（L186）：用途=创建 `provider` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `evaluate_population_runtime`（L97）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_population_runtime(...)`，并结合所属类职责使用

- `_Provider`
  - 方法数：`4`
  - 方法明细：
    - `can_handle_individual`（L193）：用途=判断当前是否可执行 `handle_individual`；用法=在执行前先调用，返回布尔值决定是否继续
    - `can_handle_population`（L204）：用途=判断当前是否可执行 `handle_population`；用法=在执行前先调用，返回布尔值决定是否继续
    - `evaluate_individual`（L198）：用途=单点评估入口；用法=调试/在线评估场景优先使用
    - `evaluate_population`（L209）：用途=批量评估入口；用法=算法主路径与并行评估常用入口


  - 方法数：`3`
  - 方法明细：
    - `on_context_build`（L77）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L53）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_solver_init`（L46）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑


  - 方法数：`2`
  - 方法明细：
    - `on_context_build`（L65）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L49）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控

### `plugins/ops/benchmark_harness.py`

- `BenchmarkHarnessPlugin`
  - 方法数：`3`
  - 方法明细：
    - `on_generation_end`（L127）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_solver_finish`（L162）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L86）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/ops/decision_trace.py`

- `DecisionTracePlugin`
  - 方法数：`4`
  - 方法明细：
    - `on_generation_end`（L87）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_solver_finish`（L93）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L56）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `record_decision`（L103）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_decision(...)`，并结合所属类职责使用

### `plugins/ops/module_report.py`

- `ModuleReportPlugin`
  - 方法数：`2`
  - 方法明细：
    - `on_solver_finish`（L67）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L61）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/ops/otel_tracing.py`

- `OpenTelemetryTracingPlugin`
  - 方法数：`2`
  - 方法明细：
    - `on_solver_finish`（L100）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L51）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/ops/profiler.py`

- `ProfilerPlugin`
  - 方法数：`4`
  - 方法明细：
    - `on_generation_end`（L77）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L73）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_solver_finish`（L117）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L59）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/ops/sensitivity_analysis.py`

- `SensitivityAnalysisPlugin`
  - 方法数：`1`
  - 方法明细：
    - `run_study`（L105）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_study(...)`，并结合所属类职责使用

### `plugins/ops/sequence_graph.py`

- `SequenceGraphPlugin`
  - 方法数：`5`
  - 方法明细：
    - `on_context_build`（L148）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L126）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_solver_finish`（L137）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L63）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `record_event`（L153）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_event(...)`，并结合所属类职责使用


  - 方法数：`6`
  - 方法明细：
    - `on_context_build`（L63）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L70）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L60）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L56）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L95）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L49）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑


  - 方法数：`4`
  - 方法明细：
    - `get_report`（L237）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_context_build`（L188）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L195）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_solver_init`（L177）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

- `CompanionPhaseScheduler`
  - 方法数：`1`
  - 方法明细：
    - `should_trigger`（L98）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.should_trigger(...)`，并结合所属类职责使用


  - 方法数：`7`
  - 方法明细：
    - `get_convergence_info`（L142）：用途=读取 `convergence_info` 相关运行态或配置值；用法=通过 `obj.get_convergence_info(...)` 在日志、诊断或编排阶段查询
    - `on_context_build`（L70）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L76）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L67）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L56）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L112）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L48）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/runtime/diversity_init.py`

- `DiversityInitPlugin`
  - 方法数：`7`
  - 方法明细：
    - `is_similar`（L70）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_similar(...)`，并结合所属类职责使用
    - `on_generation_end`（L45）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L42）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L37）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L48）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L31）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `should_accept`（L81）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.should_accept(...)`，并结合所属类职责使用

### `plugins/runtime/dynamic_switch.py`

- `DynamicSwitchPlugin`
  - 方法数：`4`
  - 方法明细：
    - `hard_switch`（L63）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.hard_switch(...)`，并结合所属类职责使用
    - `select_switch_mode`（L53）：用途=选择 `switch_mode` 候选或策略；用法=在决策阶段调用，根据上下文返回最优分支
    - `should_switch`（L50）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.should_switch(...)`，并结合所属类职责使用
    - `soft_switch`（L58）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.soft_switch(...)`，并结合所属类职责使用

### `plugins/runtime/elite_retention.py`

- `BasicElitePlugin`
  - 方法数：`6`
  - 方法明细：
    - `on_context_build`（L74）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L80）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L71）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L68）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L92）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L61）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

- `HistoricalElitePlugin`
  - 方法数：`6`
  - 方法明细：
    - `on_context_build`（L186）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_generation_end`（L192）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L183）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L180）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L204）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L174）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/runtime/pareto_archive.py`

- `ParetoArchivePlugin`
  - 方法数：`1`
  - 方法明细：
    - `on_generation_end`（L51）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控

### `plugins/solver_backends/backend_contract.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `normalize_backend_output`（L23）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_backend_output(...)`，并结合所属类职责使用

- `BackendSolver`
  - 方法数：`1`
  - 方法明细：
    - `solve`（L19）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve(...)`，并结合所属类职责使用

### `plugins/solver_backends/contract_bridge.py`

- `ContractBridgePlugin`
  - 方法数：`2`
  - 方法明细：
    - `get_report`（L123）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_inner_result`（L60）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发

### `plugins/solver_backends/copt_backend.py`

- `CoptBackend`
  - 方法数：`1`
  - 方法明细：
    - `solve`（L362）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve(...)`，并结合所属类职责使用

### `plugins/solver_backends/copt_templates/linear.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `solve_linear_template`（L24）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve_linear_template(...)`，并结合所属类职责使用

### `plugins/solver_backends/copt_templates/qp.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `solve_qp_template`（L26）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve_qp_template(...)`，并结合所属类职责使用

### `plugins/solver_backends/copt_templates/registry.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `build_default_templates`（L10）：用途=构建 `default_templates` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程

### `plugins/solver_backends/ngspice_backend.py`

- `NgspiceBackend`
  - 方法数：`1`
  - 方法明细：
    - `solve`（L112）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.solve(...)`，并结合所属类职责使用

### `plugins/solver_backends/timeout_budget.py`

- `TimeoutBudgetPlugin`
  - 方法数：`4`
  - 方法明细：
    - `get_report`（L77）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_inner_guard`（L53）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_inner_result`（L70）：用途=插件生命周期钩子；用法=由 PluginManager 在对应事件节点触发
    - `on_solver_init`（L45）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `plugins/storage/mysql_run_logger.py`

- `MySQLRunLoggerPlugin`
  - 方法数：`1`
  - 方法明细：
    - `on_solver_finish`（L110）：用途=求解结束钩子；用法=输出报告、落盘、清理资源

### `plugins/system/async_event_hub.py`

- `AsyncEventHubPlugin`
  - 方法数：`6`
  - 方法明细：
    - `commit`（L100）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.commit(...)`，并结合所属类职责使用
    - `get_committed_context`（L122）：用途=读取 `committed_context` 相关运行态或配置值；用法=通过 `obj.get_committed_context(...)` 在日志、诊断或编排阶段查询
    - `get_report`（L125）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_generation_end`（L51）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L48）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `record_event`（L55）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_event(...)`，并结合所属类职责使用

### `plugins/system/boundary_guard.py`

- `BoundaryGuardPlugin`
  - 方法数：`2`
  - 方法明细：
    - `get_report`（L73）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_generation_end`（L41）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控

### `plugins/system/checkpoint_resume.py`

- `CheckpointResumePlugin`
  - 方法数：`6`
  - 方法明细：
    - `get_report`（L564）：用途=输出组件报告；用法=用于 module report / 结果审计
    - `on_generation_end`（L88）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_solver_finish`（L99）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L77）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `resume`（L131）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.resume(...)`，并结合所属类职责使用
    - `save_checkpoint`（L109）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.save_checkpoint(...)`，并结合所属类职责使用

### `plugins/system/memory_optimize.py`

- `MemoryPlugin`
  - 方法数：`6`
  - 方法明细：
    - `get_memory_usage`（L97）：用途=读取 `memory_usage` 相关运行态或配置值；用法=通过 `obj.get_memory_usage(...)` 在日志、诊断或编排阶段查询
    - `on_generation_end`（L41）：用途=每代结束钩子；用法=插件记录指标/归档/动态调控
    - `on_generation_start`（L38）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_population_init`（L35）：用途=初代种群完成后的钩子；用法=插件统计或过滤初始化结果
    - `on_solver_finish`（L46）：用途=求解结束钩子；用法=输出报告、落盘、清理资源
    - `on_solver_init`（L31）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑

### `project/catalog.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `export_project_entries`（L153）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.export_project_entries(...)`，并结合所属类职责使用
    - `find_project_root`（L25）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.find_project_root(...)`，并结合所属类职责使用
    - `load_project_catalog`（L141）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_project_catalog(...)`，并结合所属类职责使用
    - `load_project_entries`（L110）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_project_entries(...)`，并结合所属类职责使用

### `project/doctor.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `format_doctor_report`（L487）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.format_doctor_report(...)`，并结合所属类职责使用
    - `iter_diagnostics_by_level`（L491）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.iter_diagnostics_by_level(...)`，并结合所属类职责使用
    - `run_project_doctor`（L439）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_project_doctor(...)`，并结合所属类职责使用

### `project/doctor_core/model.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `add_diagnostic`（L40）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_diagnostic(...)`，并结合所属类职责使用
    - `format_doctor_report_text`（L57）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.format_doctor_report_text(...)`，并结合所属类职责使用
    - `iter_diagnostics_by_level`（L70）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.iter_diagnostics_by_level(...)`，并结合所属类职责使用

- `DoctorReport`
  - 方法数：`3`
  - 方法明细：
    - `error_count`（L28）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.error_count(...)`，并结合所属类职责使用
    - `info_count`（L36）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.info_count(...)`，并结合所属类职责使用
    - `warn_count`（L32）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.warn_count(...)`，并结合所属类职责使用

### `project/doctor_core/rules/adapter_purity.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_adapter_layer_purity`（L12）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_adapter_layer_purity(...)`，并结合所属类职责使用

### `project/doctor_core/rules/broad_except.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_broad_exception_swallow`（L34）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_broad_exception_swallow(...)`，并结合所属类职责使用

### `project/doctor_core/rules/build_solver.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_build_solver`（L22）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_build_solver(...)`，并结合所属类职责使用

### `project/doctor_core/rules/component_catalog.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `check_component_catalog_registration`（L126）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_component_catalog_registration(...)`，并结合所属类职责使用
    - `check_process_like_bias_usage`（L91）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_process_like_bias_usage(...)`，并结合所属类职责使用
    - `collect_bias_instances`（L52）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.collect_bias_instances(...)`，并结合所属类职责使用
    - `collect_solver_components`（L11）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.collect_solver_components(...)`，并结合所属类职责使用

### `project/doctor_core/rules/component_order.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_component_order_constraints`（L428）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_component_order_constraints(...)`，并结合所属类职责使用

- `_OrderActionCollector`
  - 方法数：`1`
  - 方法明细：
    - `visit_Call`（L92）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.visit_Call(...)`，并结合所属类职责使用

### `project/doctor_core/rules/contract_source.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_contract_source`（L657）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_contract_source(...)`，并结合所属类职责使用

### `project/doctor_core/rules/examples_suites.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_examples_suites_solver_control_writes`（L33）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_examples_suites_solver_control_writes(...)`，并结合所属类职责使用

### `project/doctor_core/rules/metrics_provider.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_metrics_provider_alignment`（L60）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_metrics_provider_alignment(...)`，并结合所属类职责使用

### `project/doctor_core/rules/registry_checks.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_registry`（L23）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_registry(...)`，并结合所属类职责使用

### `project/doctor_core/rules/runtime_governance.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `check_no_plugin_evaluation_short_circuit`（L39）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_no_plugin_evaluation_short_circuit(...)`，并结合所属类职责使用
    - `check_runtime_governance_runtime_state`（L77）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_runtime_governance_runtime_state(...)`，并结合所属类职责使用

### `project/doctor_core/rules/runtime_guards.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `check_forbidden_solver_mirror_writes`（L56）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_forbidden_solver_mirror_writes(...)`，并结合所属类职责使用
    - `check_plugin_solver_state_access`（L221）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_plugin_solver_state_access(...)`，并结合所属类职责使用
    - `check_runtime_bypass_writes`（L154）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_runtime_bypass_writes(...)`，并结合所属类职责使用
    - `check_runtime_private_calls`（L115）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_runtime_private_calls(...)`，并结合所属类职责使用

- `_SolverMirrorWriteVisitor`
  - 方法数：`3`
  - 方法明细：
    - `visit_Assign`（L28）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.visit_Assign(...)`，并结合所属类职责使用
    - `visit_AugAssign`（L33）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.visit_AugAssign(...)`，并结合所属类职责使用
    - `visit_Call`（L37）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.visit_Call(...)`，并结合所属类职责使用

### `project/doctor_core/rules/runtime_surface.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `check_runtime_private_surface`（L80）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_runtime_private_surface(...)`，并结合所属类职责使用

### `project/doctor_core/rules/scaffold.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `check_structure`（L15）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_structure(...)`，并结合所属类职责使用
    - `looks_like_scaffold_project`（L11）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.looks_like_scaffold_project(...)`，并结合所属类职责使用

### `project/doctor_core/rules/snapshot_context_policy.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `check_context_store_policy`（L37）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_context_store_policy(...)`，并结合所属类职责使用
    - `check_large_objects_in_context`（L509）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_large_objects_in_context(...)`，并结合所属类职责使用
    - `check_snapshot_refs`（L264）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_snapshot_refs(...)`，并结合所属类职责使用
    - `check_snapshot_store_policy`（L132）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_snapshot_store_policy(...)`，并结合所属类职责使用

### `project/scaffold.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `init_project`（L1425）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.init_project(...)`，并结合所属类职责使用

### `representation/base.py`

- `ContinuousRepresentation`
  - 方法数：`5`
  - 方法明细：
    - `add_constraint`（L452）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `check_constraints`（L455）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `decode`（L464）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L461）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用
    - `repair`（L468）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `CrossoverPlugin`
  - 方法数：`1`
  - 方法明细：
    - `crossover`（L190）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

- `EncodingPlugin`
  - 方法数：`2`
  - 方法明细：
    - `decode`（L19）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L16）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用

- `InitPlugin`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L180）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `IntegerRepresentation`
  - 方法数：`5`
  - 方法明细：
    - `add_constraint`（L489）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `check_constraints`（L492）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `decode`（L503）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L498）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用
    - `repair`（L509）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `MixedRepresentation`
  - 方法数：`2`
  - 方法明细：
    - `decode`（L582）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L574）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用

- `MutationPlugin`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L185）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `ParallelRepair`
  - 方法数：`2`
  - 方法明细：
    - `repair`（L98）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规
    - `repair_batch`（L101）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

- `PermutationRepresentation`
  - 方法数：`3`
  - 方法明细：
    - `decode`（L535）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L529）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用
    - `generate_random`（L541）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

- `RepairPlugin`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L24）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `RepresentationPipeline`
  - 方法数：`10`
  - 方法明细：
    - `decode`（L389）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `decode_batch`（L361）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `encode`（L394）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用
    - `encode_batch`（L352）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `get_context_contract`（L221）：用途=声明 context 读写契约；用法=doctor 校验与组件编排时读取
    - `init`（L281）：用途=初始化候选或批次；用法=solver 初始化种群时触发
    - `mutate`（L315）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解
    - `mutate_batch`（L379）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `repair_batch`（L370）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `repair_one`（L334）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

### `representation/binary.py`

- `BinaryCapacityRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L78）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `BinaryInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L29）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `BinaryRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L61）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `BitFlipMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L45）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

### `representation/constraints.py`

- `BoundConstraint`
  - 方法数：`2`
  - 方法明细：
    - `check`（L31）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用
    - `repair`（L35）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

### `representation/context_mutators.py`

- `ContextDispatchMutator`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L105）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `ContextSelectMutator`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L46）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `SerialMutator`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L75）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

### `representation/continuous.py`

- `ClipRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L237）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `ContextGaussianMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L177）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `GaussianMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L103）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `PolynomialMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L127）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `ProjectionRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L283）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `SBXCrossover`
  - 方法数：`1`
  - 方法明细：
    - `crossover`（L206）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

- `UniformInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L85）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

### `representation/dynamic.py`

- `DynamicRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L32）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

### `representation/graph.py`

- `GraphConnectivityRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L95）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `GraphDegreeRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L151）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `GraphEdgeInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L29）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `GraphEdgeMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L55）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

### `representation/integer.py`

- `IntegerInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L54）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `IntegerMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L110）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `IntegerRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L77）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

### `representation/matrix.py`

- `IntegerMatrixInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L50）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `IntegerMatrixMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L73）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `MatrixBlockSumRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L187）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `MatrixRowColSumRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L90）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `MatrixSparsityRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L151）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

### `representation/orchestrator.py`

- `PipelineOrchestrator`
  - 方法数：`2`
  - 方法明细：
    - `mutate`（L80）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解
    - `repair`（L84）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

### `representation/permutation.py`

- `OrderCrossover`
  - 方法数：`1`
  - 方法明细：
    - `crossover`（L212）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

- `PMXCrossover`
  - 方法数：`1`
  - 方法明细：
    - `crossover`（L231）：用途=表示层算子动作；用法=由 pipeline/orchestrator 在候选处理阶段调用

- `PermutationFixRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L152）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `PermutationInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L77）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `PermutationInversionMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L115）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `PermutationRepair`
  - 方法数：`1`
  - 方法明细：
    - `repair`（L135）：用途=执行可行性修复；用法=评估前最后防线，修正越界或结构违规

- `PermutationSwapMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L95）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `RandomKeyInitializer`
  - 方法数：`1`
  - 方法明细：
    - `initialize`（L43）：用途=初始化单个候选；用法=初始化阶段由 pipeline/initializer 调用

- `RandomKeyMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L61）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

- `RandomKeyPermutationDecoder`
  - 方法数：`2`
  - 方法明细：
    - `decode`（L23）：用途=将搜索表示解码为业务表示；用法=评估前或结果解释时调用
    - `encode`（L26）：用途=将业务表示编码为搜索表示；用法=在优化前或导出前调用

- `TwoOptMutation`
  - 方法数：`1`
  - 方法明细：
    - `mutate`（L180）：用途=执行变异操作；用法=在生成新候选阶段调用，输入一个解

### `utils/analysis/metrics.py`

- `(module)`
  - 方法数：`6`
  - 方法明细：
    - `hypervolume_2d`（L31）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.hypervolume_2d(...)`，并结合所属类职责使用
    - `igd`（L59）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.igd(...)`，并结合所属类职责使用
    - `pareto_filter`（L9）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.pareto_filter(...)`，并结合所属类职责使用
    - `reference_front_dtlz2`（L102）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reference_front_dtlz2(...)`，并结合所属类职责使用
    - `reference_front_zdt1`（L76）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reference_front_zdt1(...)`，并结合所属类职责使用
    - `reference_front_zdt3`（L83）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reference_front_zdt3(...)`，并结合所属类职责使用

### `utils/constraints/constraint_utils.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `evaluate_constraints_batch_safe`（L34）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_constraints_batch_safe(...)`，并结合所属类职责使用
    - `evaluate_constraints_safe`（L14）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.evaluate_constraints_safe(...)`，并结合所属类职责使用

### `core/state/context_contracts.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `collect_solver_contracts`（L198）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.collect_solver_contracts(...)`，并结合所属类职责使用
    - `detect_context_conflicts`（L254）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.detect_context_conflicts(...)`，并结合所属类职责使用
    - `get_component_contract`（L141）：用途=读取 `component_contract` 相关运行态或配置值；用法=通过 `obj.get_component_contract(...)` 在日志、诊断或编排阶段查询
    - `validate_context_contracts`（L241）：用途=校验 `context_contracts` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `ContextContract`
  - 方法数：`3`
  - 方法明细：
    - `merge`（L129）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.merge(...)`，并结合所属类职责使用
    - `normalized`（L110）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalized(...)`，并结合所属类职责使用
    - `to_dict`（L119）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.to_dict(...)`，并结合所属类职责使用

### `core/state/context_events.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `apply_context_event`（L54）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply_context_event(...)`，并结合所属类职责使用
    - `record_context_event`（L30）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_context_event(...)`，并结合所属类职责使用
    - `replay_context`（L83）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.replay_context(...)`，并结合所属类职责使用

- `ContextEvent`
  - 方法数：`1`
  - 方法明细：
    - `to_dict`（L18）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.to_dict(...)`，并结合所属类职责使用

### `core/state/context_field_governance.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `context_field_schema_dict`（L36）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.context_field_schema_dict(...)`，并结合所属类职责使用
    - `is_canonical_context_key`（L26）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_canonical_context_key(...)`，并结合所属类职责使用
    - `schema_meta`（L19）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.schema_meta(...)`，并结合所属类职责使用

### `core/state/context_keys.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `normalize_context_key`（L296）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_context_key(...)`，并结合所属类职责使用

### `core/state/context_schema.py`

- `(module)`
  - 方法数：`6`
  - 方法明细：
    - `build_minimal_context`（L39）：用途=构建 `minimal_context` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `get_context_lifecycle`（L238）：用途=读取 `context_lifecycle` 相关运行态或配置值；用法=通过 `obj.get_context_lifecycle(...)` 在日志、诊断或编排阶段查询
    - `is_replayable_context`（L251）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_replayable_context(...)`，并结合所属类职责使用
    - `strip_context_for_replay`（L264）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.strip_context_for_replay(...)`，并结合所属类职责使用
    - `validate_context`（L202）：用途=校验 `context` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置
    - `validate_minimal_context`（L69）：用途=校验 `minimal_context` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `ContextSchema`
  - 方法数：`2`
  - 方法明细：
    - `field_map`（L119）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.field_map(...)`，并结合所属类职责使用
    - `required_keys`（L116）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.required_keys(...)`，并结合所属类职责使用

- `MinimalEvaluationContext`
  - 方法数：`1`
  - 方法明细：
    - `to_dict`（L25）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.to_dict(...)`，并结合所属类职责使用

### `core/state/context_store.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `create_context_store`（L177）：用途=创建 `context_store` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `ContextStore`
  - 方法数：`6`
  - 方法明细：
    - `clear`（L32）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear(...)`，并结合所属类职责使用
    - `delete`（L28）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `get`（L20）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `set`（L24）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.set(...)`，并结合所属类职责使用
    - `snapshot`（L36）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot(...)`，并结合所属类职责使用
    - `update`（L39）：用途=根据评估反馈更新内部状态；用法=在目标值/约束值返回后调用

- `InMemoryContextStore`
  - 方法数：`5`
  - 方法明细：
    - `clear`（L87）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear(...)`，并结合所属类职责使用
    - `delete`（L82）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `get`（L68）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `set`（L72）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.set(...)`，并结合所属类职责使用
    - `snapshot`（L91）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot(...)`，并结合所属类职责使用

- `RedisContextStore`
  - 方法数：`5`
  - 方法明细：
    - `clear`（L150）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear(...)`，并结合所属类职责使用
    - `delete`（L147）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `get`（L126）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `set`（L135）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.set(...)`，并结合所属类职责使用
    - `snapshot`（L161）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot(...)`，并结合所属类职责使用

### `core/state/snapshot_store.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `create_snapshot_store`（L722）：用途=创建 `snapshot_store` 实例或资源；用法=在初始化阶段调用并返回可复用对象
    - `make_snapshot_key`（L66）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.make_snapshot_key(...)`，并结合所属类职责使用

- `FileSnapshotStore`
  - 方法数：`3`
  - 方法明细：
    - `delete`（L704）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `read`（L656）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read(...)`，并结合所属类职责使用
    - `write`（L546）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.write(...)`，并结合所属类职责使用

- `InMemorySnapshotStore`
  - 方法数：`3`
  - 方法明细：
    - `delete`（L173）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `read`（L169）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read(...)`，并结合所属类职责使用
    - `write`（L134）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.write(...)`，并结合所属类职责使用

- `RedisSnapshotStore`
  - 方法数：`3`
  - 方法明细：
    - `delete`（L474）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `read`（L458）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read(...)`，并结合所属类职责使用
    - `write`（L403）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.write(...)`，并结合所属类职责使用

- `SnapshotStore`
  - 方法数：`3`
  - 方法明细：
    - `delete`（L106）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.delete(...)`，并结合所属类职责使用
    - `read`（L102）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read(...)`，并结合所属类职责使用
    - `write`（L90）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.write(...)`，并结合所属类职责使用

### `utils/dynamic/cli_provider.py`

- `CLISignalProvider`
  - 方法数：`1`
  - 方法明细：
    - `read`（L35）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read(...)`，并结合所属类职责使用

### `utils/dynamic/switch.py`

- `DynamicSwitchBase`
  - 方法数：`6`
  - 方法明细：
    - `hard_switch`（L123）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.hard_switch(...)`，并结合所属类职责使用
    - `on_generation_start`（L90）：用途=每代开始钩子；用法=插件更新调度参数或预算
    - `on_solver_init`（L87）：用途=solver 初始化生命周期钩子；用法=插件在启动阶段注入逻辑
    - `select_switch_mode`（L115）：用途=选择 `switch_mode` 候选或策略；用法=在决策阶段调用，根据上下文返回最优分支
    - `should_switch`（L111）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.should_switch(...)`，并结合所属类职责使用
    - `soft_switch`（L119）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.soft_switch(...)`，并结合所属类职责使用

- `SignalProviderBase`
  - 方法数：`2`
  - 方法明细：
    - `close`（L46）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.close(...)`，并结合所属类职责使用
    - `read`（L42）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.read(...)`，并结合所属类职责使用

### `utils/engineering/config_loader.py`

- `(module)`
  - 方法数：`5`
  - 方法明细：
    - `apply_config`（L76）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply_config(...)`，并结合所属类职责使用
    - `build_dataclass_config`（L101）：用途=构建 `dataclass_config` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `load_config`（L23）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_config(...)`，并结合所属类职责使用
    - `merge_dicts`（L58）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.merge_dicts(...)`，并结合所属类职责使用
    - `select_section`（L69）：用途=选择 `section` 候选或策略；用法=在决策阶段调用，根据上下文返回最优分支

### `utils/engineering/error_policy.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `report_soft_error`（L55）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.report_soft_error(...)`，并结合所属类职责使用

### `utils/engineering/experiment.py`

- `ExperimentResult`
  - 方法数：`2`
  - 方法明细：
    - `save`（L37）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.save(...)`，并结合所属类职责使用
    - `set_results`（L22）：用途=设置 `results` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_results(...)`

- `ExperimentTracker`
  - 方法数：`1`
  - 方法明细：
    - `log_run`（L97）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.log_run(...)`，并结合所属类职责使用

### `utils/engineering/file_io.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `atomic_write_json`（L17）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.atomic_write_json(...)`，并结合所属类职责使用
    - `atomic_write_text`（L9）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.atomic_write_text(...)`，并结合所属类职责使用

### `utils/engineering/logging_config.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `configure_logging`（L37）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.configure_logging(...)`，并结合所属类职责使用

- `JsonFormatter`
  - 方法数：`1`
  - 方法明细：
    - `format`（L15）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.format(...)`，并结合所属类职责使用

### `utils/engineering/schema_version.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `expected_schema_version`（L22）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.expected_schema_version(...)`，并结合所属类职责使用
    - `require_schema`（L47）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.require_schema(...)`，并结合所属类职责使用
    - `schema_check`（L36）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.schema_check(...)`，并结合所属类职责使用
    - `stamp_schema`（L29）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.stamp_schema(...)`，并结合所属类职责使用

### `utils/evaluation/shape_validation.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `validate_individual_evaluation_shape`（L24）：用途=校验 `individual_evaluation_shape` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置
    - `validate_plugin_short_circuit_return`（L274）：用途=校验 `plugin_short_circuit_return` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置
    - `validate_population_evaluation_shape`（L135）：用途=校验 `population_evaluation_shape` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

### `utils/extension_contracts.py`

- `(module)`
  - 方法数：`8`
  - 方法明细：
    - `normalize_bias_output`（L93）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_bias_output(...)`，并结合所属类职责使用
    - `normalize_candidate`（L36）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_candidate(...)`，并结合所属类职责使用
    - `normalize_candidates`（L44）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_candidates(...)`，并结合所属类职责使用
    - `normalize_objectives`（L73）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_objectives(...)`，并结合所属类职责使用
    - `normalize_violation`（L83）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.normalize_violation(...)`，并结合所属类职责使用
    - `stack_population`（L58）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.stack_population(...)`，并结合所属类职责使用
    - `verify_component_contract`（L106）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.verify_component_contract(...)`，并结合所属类职责使用
    - `verify_solver_contracts`（L143）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.verify_solver_contracts(...)`，并结合所属类职责使用

### `utils/parallel/batch.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `create_batch_evaluator`（L337）：用途=创建 `batch_evaluator` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `BatchEvaluator`
  - 方法数：`3`
  - 方法明细：
    - `evaluate_population`（L43）：用途=批量评估入口；用法=算法主路径与并行评估常用入口
    - `get_stats`（L323）：用途=读取 `stats` 相关运行态或配置值；用法=通过 `obj.get_stats(...)` 在日志、诊断或编排阶段查询
    - `reset_stats`（L327）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset_stats(...)`，并结合所属类职责使用

### `utils/parallel/evaluator.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `create_parallel_evaluator`（L571）：用途=创建 `parallel_evaluator` 实例或资源；用法=在初始化阶段调用并返回可复用对象

- `ParallelEvaluator`
  - 方法数：`4`
  - 方法明细：
    - `estimate_speedup`（L551）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.estimate_speedup(...)`，并结合所属类职责使用
    - `evaluate_population`（L262）：用途=批量评估入口；用法=算法主路径与并行评估常用入口
    - `get_stats`（L539）：用途=读取 `stats` 相关运行态或配置值；用法=通过 `obj.get_stats(...)` 在日志、诊断或编排阶段查询
    - `reset_stats`（L542）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reset_stats(...)`，并结合所属类职责使用

- `SmartEvaluatorSelector`
  - 方法数：`1`
  - 方法明细：
    - `select_evaluator`（L579）：用途=选择 `evaluator` 候选或策略；用法=在决策阶段调用，根据上下文返回最优分支

### `utils/parallel/integration.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `with_parallel_evaluation`（L24）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.with_parallel_evaluation(...)`，并结合所属类职责使用

- `ParallelizedSolver`
  - 方法数：`1`
  - 方法明细：
    - `evaluate_population`（L126）：用途=批量评估入口；用法=算法主路径与并行评估常用入口

### `utils/parallel/runs.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `run_headless_in_parallel`（L31）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_headless_in_parallel(...)`，并结合所属类职责使用
    - `run_vns_in_parallel`（L81）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_vns_in_parallel(...)`，并结合所属类职责使用

### `utils/performance/__init__.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `fast_non_dominated_sort_optimized`（L20）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.fast_non_dominated_sort_optimized(...)`，并结合所属类职责使用

### `utils/performance/array_utils.py`

- `(module)`
  - 方法数：`8`
  - 方法明细：
    - `safe_array_concat`（L92）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_array_concat(...)`，并结合所属类职责使用
    - `safe_array_index`（L9）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_array_index(...)`，并结合所属类职责使用
    - `safe_array_reshape`（L118）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_array_reshape(...)`，并结合所属类职责使用
    - `safe_get_2d_element`（L294）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_get_2d_element(...)`，并结合所属类职责使用
    - `safe_get_element`（L282）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_get_element(...)`，并结合所属类职责使用
    - `safe_get_row`（L287）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_get_row(...)`，并结合所属类职责使用
    - `safe_slice_bounds`（L62）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_slice_bounds(...)`，并结合所属类职责使用
    - `validate_array_bounds`（L155）：用途=校验 `array_bounds` 合法性与一致性；用法=在运行前调用，异常时中断并修正配置

- `SafeArrayAccess`
  - 方法数：`3`
  - 方法明细：
    - `safe_get`（L190）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_get(...)`，并结合所属类职责使用
    - `safe_slice_1d`（L229）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_slice_1d(...)`，并结合所属类职责使用
    - `safe_slice_2d`（L253）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_slice_2d(...)`，并结合所属类职责使用

### `utils/performance/fast_non_dominated_sort.py`

- `(module)`
  - 方法数：`6`
  - 方法明细：
    - `count_non_dominated_solutions`（L298）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.count_non_dominated_solutions(...)`，并结合所属类职责使用
    - `dominates_numba`（L199）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.dominates_numba(...)`，并结合所属类职责使用
    - `fast_non_dominated_sort_numba`（L211）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.fast_non_dominated_sort_numba(...)`，并结合所属类职责使用
    - `fast_non_dominated_sort_optimized`（L258）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.fast_non_dominated_sort_optimized(...)`，并结合所属类职责使用
    - `get_pareto_front_indices`（L292）：用途=读取 `pareto_front_indices` 相关运行态或配置值；用法=通过 `obj.get_pareto_front_indices(...)` 在日志、诊断或编排阶段查询
    - `is_pareto_optimal`（L304）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_pareto_optimal(...)`，并结合所属类职责使用

- `FastNonDominatedSort`
  - 方法数：`2`
  - 方法明细：
    - `calculate_crowding_distance`（L144）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.calculate_crowding_distance(...)`，并结合所属类职责使用
    - `sort`（L25）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.sort(...)`，并结合所属类职责使用

### `utils/performance/memory_manager.py`

- `(module)`
  - 方法数：`5`
  - 方法明细：
    - `decorator`（L473）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.decorator(...)`，并结合所属类职责使用
    - `get_global_memory_manager`（L441）：用途=读取 `global_memory_manager` 相关运行态或配置值；用法=通过 `obj.get_global_memory_manager(...)` 在日志、诊断或编排阶段查询
    - `memory_monitoring`（L466）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.memory_monitoring(...)`，并结合所属类职责使用
    - `monitor_and_optimize_memory`（L449）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.monitor_and_optimize_memory(...)`，并结合所属类职责使用
    - `wrapper`（L474）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.wrapper(...)`，并结合所属类职责使用

- `MemoryManager`
  - 方法数：`7`
  - 方法明细：
    - `check_memory_pressure`（L58）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_memory_pressure(...)`，并结合所属类职责使用
    - `cleanup_memory`（L82）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.cleanup_memory(...)`，并结合所属类职责使用
    - `get_memory_trend`（L154）：用途=读取 `memory_trend` 相关运行态或配置值；用法=通过 `obj.get_memory_trend(...)` 在日志、诊断或编排阶段查询
    - `get_memory_usage`（L41）：用途=读取 `memory_usage` 相关运行态或配置值；用法=通过 `obj.get_memory_usage(...)` 在日志、诊断或编排阶段查询
    - `register_cleanup_strategy`（L73）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.register_cleanup_strategy(...)`，并结合所属类职责使用
    - `start_monitoring`（L123）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.start_monitoring(...)`，并结合所属类职责使用
    - `stop_monitoring`（L138）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.stop_monitoring(...)`，并结合所属类职责使用

- `OptimizationMemoryOptimizer`
  - 方法数：`5`
  - 方法明细：
    - `auto_optimize`（L380）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.auto_optimize(...)`，并结合所属类职责使用
    - `clear_temporary_data`（L371）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear_temporary_data(...)`，并结合所属类职责使用
    - `get_optimization_report`（L406）：用途=读取 `optimization_report` 相关运行态或配置值；用法=通过 `obj.get_optimization_report(...)` 在日志、诊断或编排阶段查询
    - `optimize_history_storage`（L312）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.optimize_history_storage(...)`，并结合所属类职责使用
    - `optimize_population_storage`（L339）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.optimize_population_storage(...)`，并结合所属类职责使用

- `SmartArrayCache`
  - 方法数：`4`
  - 方法明细：
    - `clear`（L276）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear(...)`，并结合所属类职责使用
    - `get`（L204）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.get(...)`，并结合所属类职责使用
    - `get_stats`（L284）：用途=读取 `stats` 相关运行态或配置值；用法=通过 `obj.get_stats(...)` 在日志、诊断或编排阶段查询
    - `put`（L221）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.put(...)`，并结合所属类职责使用

### `utils/performance/numba_helpers.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `fast_is_dominated`（L26）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.fast_is_dominated(...)`，并结合所属类职责使用
    - `njit`（L16）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.njit(...)`，并结合所属类职责使用
    - `wrapper`（L19）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.wrapper(...)`，并结合所属类职责使用

### `utils/runs/headless.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `run_headless_single_objective`（L25）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_headless_single_objective(...)`，并结合所属类职责使用

- `CallableSingleObjectiveProblem`
  - 方法数：`2`
  - 方法明细：
    - `evaluate`（L16）：用途=执行问题评估并产出目标值；用法=由评估链路调用，输入单个 candidate
    - `get_num_objectives`（L21）：用途=读取 `num_objectives` 相关运行态或配置值；用法=通过 `obj.get_num_objectives(...)` 在日志、诊断或编排阶段查询

### `utils/runtime/decision_trace.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `append_decision_jsonl`（L64）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.append_decision_jsonl(...)`，并结合所属类职责使用
    - `build_decision_event`（L31）：用途=构建 `decision_event` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `load_decision_jsonl`（L70）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_decision_jsonl(...)`，并结合所属类职责使用
    - `record_decision_event`（L130）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_decision_event(...)`，并结合所属类职责使用

- `DecisionReplayEngine`
  - 方法数：`3`
  - 方法明细：
    - `from_jsonl`（L93）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.from_jsonl(...)`，并结合所属类职责使用
    - `iter`（L96）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.iter(...)`，并结合所属类职责使用
    - `summary`（L113）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.summary(...)`，并结合所属类职责使用

### `utils/runtime/dependencies.py`

- `(module)`
  - 方法数：`4`
  - 方法明细：
    - `check_dependency`（L23）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_dependency(...)`，并结合所属类职责使用
    - `dependency_report`（L45）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.dependency_report(...)`，并结合所属类职责使用
    - `ensure_dependencies`（L55）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.ensure_dependencies(...)`，并结合所属类职责使用
    - `summarize_report`（L80）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.summarize_report(...)`，并结合所属类职责使用

### `utils/runtime/imports.py`

- `(module)`
  - 方法数：`16`
  - 方法明细：
    - `add_to_path`（L275）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_to_path(...)`，并结合所属类职责使用
    - `check_optional_dependency`（L127）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_optional_dependency(...)`，并结合所属类职责使用
    - `get_import_status`（L132）：用途=读取 `import_status` 相关运行态或配置值；用法=通过 `obj.get_import_status(...)` 在日志、诊断或编排阶段查询
    - `get_package_root`（L270）：用途=读取 `package_root` 相关运行态或配置值；用法=通过 `obj.get_package_root(...)` 在日志、诊断或编排阶段查询
    - `import_bias`（L183）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_bias(...)`，并结合所属类职责使用
    - `import_core`（L169）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_core(...)`，并结合所属类职责使用
    - `import_joblib`（L158）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_joblib(...)`，并结合所属类职责使用
    - `import_matplotlib`（L143）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_matplotlib(...)`，并结合所属类职责使用
    - `import_numba`（L153）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_numba(...)`，并结合所属类职责使用
    - `import_numpy`（L138）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_numpy(...)`，并结合所属类职责使用
    - `import_plotly`（L163）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_plotly(...)`，并结合所属类职责使用
    - `import_sklearn`（L148）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_sklearn(...)`，并结合所属类职责使用
    - `import_utils`（L218）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.import_utils(...)`，并结合所属类职责使用
    - `is_headless`（L259）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_headless(...)`，并结合所属类职责使用
    - `is_jupyter_notebook`（L248）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.is_jupyter_notebook(...)`，并结合所属类职责使用
    - `safe_import`（L121）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_import(...)`，并结合所属类职责使用

- `ImportManager`
  - 方法数：`3`
  - 方法明细：
    - `check_optional_dependency`（L72）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.check_optional_dependency(...)`，并结合所属类职责使用
    - `get_import_status`（L90）：用途=读取 `import_status` 相关运行态或配置值；用法=通过 `obj.get_import_status(...)` 在日志、诊断或编排阶段查询
    - `safe_import`（L29）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.safe_import(...)`，并结合所属类职责使用

### `utils/runtime/repro_bundle.py`

- `(module)`
  - 方法数：`6`
  - 方法明细：
    - `apply_bundle_to_solver`（L621）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.apply_bundle_to_solver(...)`，并结合所属类职责使用
    - `build_repro_bundle`（L440）：用途=构建 `repro_bundle` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `compare_repro_bundle`（L513）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compare_repro_bundle(...)`，并结合所属类职责使用
    - `load_repro_bundle`（L505）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_repro_bundle(...)`，并结合所属类职责使用
    - `replay_spec`（L658）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.replay_spec(...)`，并结合所属类职责使用
    - `write_repro_bundle`（L490）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.write_repro_bundle(...)`，并结合所属类职责使用

### `utils/runtime/sequence_graph.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `build_sequence_token`（L23）：用途=构建 `sequence_token` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `record_sequence_event`（L51）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_sequence_event(...)`，并结合所属类职责使用

- `SequenceGraphRecorder`
  - 方法数：`6`
  - 方法明细：
    - `end_trace_span`（L317）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.end_trace_span(...)`，并结合所属类职责使用
    - `finalize_cycle`（L406）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.finalize_cycle(...)`，并结合所属类职责使用
    - `record_event`（L358）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_event(...)`，并结合所属类职责使用
    - `record_instant_trace`（L257）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.record_instant_trace(...)`，并结合所属类职责使用
    - `snapshot`（L441）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot(...)`，并结合所属类职责使用
    - `start_trace_span`（L291）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.start_trace_span(...)`，并结合所属类职责使用

- `SequenceRecord`
  - 方法数：`1`
  - 方法明细：
    - `to_dict`（L82）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.to_dict(...)`，并结合所属类职责使用

### `utils/surrogate/manager.py`

- `SurrogateManager`
  - 方法数：`4`
  - 方法明细：
    - `add_model`（L15）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_model(...)`，并结合所属类职责使用
    - `predict_model`（L25）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.predict_model(...)`，并结合所属类职责使用
    - `train_model`（L20）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.train_model(...)`，并结合所属类职责使用
    - `uncertainty`（L30）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.uncertainty(...)`，并结合所属类职责使用

### `utils/surrogate/strategies.py`

- `AdaptiveStrategy`
  - 方法数：`1`
  - 方法明细：
    - `update_strategy`（L32）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_strategy(...)`，并结合所属类职责使用

- `UncertaintySampling`
  - 方法数：`1`
  - 方法明细：
    - `select`（L12）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.select(...)`，并结合所属类职责使用

### `utils/surrogate/trainer.py`

- `SurrogateTrainer`
  - 方法数：`3`
  - 方法明细：
    - `predict`（L38）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.predict(...)`，并结合所属类职责使用
    - `predict_uncertainty`（L45）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.predict_uncertainty(...)`，并结合所属类职责使用
    - `train`（L31）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.train(...)`，并结合所属类职责使用

### `utils/surrogate/vector_surrogate.py`

- `VectorSurrogate`
  - 方法数：`3`
  - 方法明细：
    - `fit`（L33）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.fit(...)`，并结合所属类职责使用
    - `predict`（L43）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.predict(...)`，并结合所属类职责使用
    - `uncertainty`（L48）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.uncertainty(...)`，并结合所属类职责使用

### `utils/viz/app.py`

- `(module)`
  - 方法数：`5`
  - 方法明细：
    - `launch_empty`（L1621）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.launch_empty(...)`，并结合所属类职责使用
    - `launch_from_builder`（L1604）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.launch_from_builder(...)`，并结合所属类职责使用
    - `launch_from_entry`（L1612）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.launch_from_entry(...)`，并结合所属类职责使用
    - `main`（L1645）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.main(...)`，并结合所属类职责使用
    - `maybe_launch_ui`（L1630）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.maybe_launch_ui(...)`，并结合所属类职责使用

- `VisualizerApp`
  - 方法数：`9`
  - 方法明细：
    - `append_history`（L897）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.append_history(...)`，并结合所属类职责使用
    - `request_context_refresh`（L431）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_context_refresh(...)`，并结合所属类职责使用
    - `request_decision_refresh`（L441）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_decision_refresh(...)`，并结合所属类职责使用
    - `request_doctor_refresh`（L436）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_doctor_refresh(...)`，并结合所属类职责使用
    - `request_repro_refresh`（L455）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_repro_refresh(...)`，并结合所属类职责使用
    - `request_sequence_refresh`（L448）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_sequence_refresh(...)`，并结合所属类职责使用
    - `search_catalog_for_component`（L511）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search_catalog_for_component(...)`，并结合所属类职责使用
    - `search_catalog_for_context_key`（L493）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search_catalog_for_context_key(...)`，并结合所属类职责使用
    - `show_component_detail`（L529）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.show_component_detail(...)`，并结合所属类职责使用

### `utils/viz/matplotlib.py`

- `SolverVisualizationMixin`
  - 方法数：`15`
  - 方法明细：
    - `clear_all_plots`（L176）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.clear_all_plots(...)`，并结合所属类职责使用
    - `init_plot_static_elements`（L195）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.init_plot_static_elements(...)`，并结合所属类职责使用
    - `redraw_static_elements`（L214）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.redraw_static_elements(...)`，并结合所属类职责使用
    - `setup_ui`（L66）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.setup_ui(...)`，并结合所属类职责使用
    - `start_animation`（L346）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.start_animation(...)`，并结合所属类职责使用
    - `stop_animation`（L359）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.stop_animation(...)`，并结合所属类职责使用
    - `toggle_diversity_init`（L140）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.toggle_diversity_init(...)`，并结合所属类职责使用
    - `toggle_elite_retention`（L126）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.toggle_elite_retention(...)`，并结合所属类职责使用
    - `toggle_history`（L152）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.toggle_history(...)`，并结合所属类职责使用
    - `toggle_plot`（L164）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.toggle_plot(...)`，并结合所属类职责使用
    - `update_elite_prob`（L136）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_elite_prob(...)`，并结合所属类职责使用
    - `update_fitness_plot`（L269）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_fitness_plot(...)`，并结合所属类职责使用
    - `update_info_text`（L298）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_info_text(...)`，并结合所属类职责使用
    - `update_plot_dynamic`（L222）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_plot_dynamic(...)`，并结合所属类职责使用
    - `update_population_and_pareto_plot`（L230）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_population_and_pareto_plot(...)`，并结合所属类职责使用

### `utils/viz/ui/catalog_view.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `context_role_match`（L13）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.context_role_match(...)`，并结合所属类职责使用
    - `scope_from_key`（L9）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.scope_from_key(...)`，并结合所属类职责使用

- `CatalogView`
  - 方法数：`7`
  - 方法明细：
    - `key_for_bias`（L1125）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.key_for_bias(...)`，并结合所属类职责使用
    - `key_for_plugin`（L1113）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.key_for_plugin(...)`，并结合所属类职责使用
    - `load_catalog`（L173）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_catalog(...)`，并结合所属类职责使用
    - `on_select`（L1002）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.on_select(...)`，并结合所属类职责使用
    - `open_register_dialog`（L424）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.open_register_dialog(...)`，并结合所属类职责使用
    - `search`（L274）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search(...)`，并结合所属类职责使用
    - `search_context_key`（L977）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.search_context_key(...)`，并结合所属类职责使用

### `utils/viz/ui/context_view.py`

- `ContextView`
  - 方法数：`3`
  - 方法明细：
    - `refresh`（L136）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.refresh(...)`，并结合所属类职责使用
    - `request_refresh`（L133）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.request_refresh(...)`，并结合所属类职责使用
    - `show_replay_keys`（L216）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.show_replay_keys(...)`，并结合所属类职责使用

### `utils/viz/ui/contrib_view.py`

- `ContributionView`
  - 方法数：`8`
  - 方法明细：
    - `add_run_choice`（L117）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.add_run_choice(...)`，并结合所属类职责使用
    - `compare_runs`（L552）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compare_runs(...)`，并结合所属类职责使用
    - `index_by_name`（L392）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.index_by_name(...)`，并结合所属类职责使用
    - `key_fmt`（L389）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.key_fmt(...)`，并结合所属类职责使用
    - `refresh_contribution`（L147）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.refresh_contribution(...)`，并结合所属类职责使用
    - `reload_run_choices`（L129）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.reload_run_choices(...)`，并结合所属类职责使用
    - `sort_items`（L472）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.sort_items(...)`，并结合所属类职责使用
    - `y_for`（L722）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.y_for(...)`，并结合所属类职责使用

### `utils/viz/ui/decision_view.py`

- `DecisionView`
  - 方法数：`4`
  - 方法明细：
    - `load_from_history_index`（L93）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_from_history_index(...)`，并结合所属类职责使用
    - `load_from_run`（L109）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_from_run(...)`，并结合所属类职责使用
    - `load_last_run`（L85）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_last_run(...)`，并结合所属类职责使用
    - `refresh`（L122）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.refresh(...)`，并结合所属类职责使用

### `utils/viz/ui/doctor_view.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `build_doctor_visual_hints`（L211）：用途=构建 `doctor_visual_hints` 产物或对象；用法=作为工厂方法在装配阶段调用并接入后续流程
    - `count_doctor_guard_issues`（L187）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.count_doctor_guard_issues(...)`，并结合所属类职责使用

- `DoctorView`
  - 方法数：`3`
  - 方法明细：
    - `refresh_state`（L339）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.refresh_state(...)`，并结合所属类职责使用
    - `run_doctor`（L436）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_doctor(...)`，并结合所属类职责使用
    - `use_default_path`（L368）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.use_default_path(...)`，并结合所属类职责使用

### `utils/viz/ui/repro_view.py`

- `ReproView`
  - 方法数：`7`
  - 方法明细：
    - `compare_current`（L153）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.compare_current(...)`，并结合所属类职责使用
    - `export_last`（L241）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.export_last(...)`，并结合所属类职责使用
    - `load_file`（L107）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_file(...)`，并结合所属类职责使用
    - `load_from_history_index`（L76）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_from_history_index(...)`，并结合所属类职责使用
    - `load_from_run`（L86）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_from_run(...)`，并结合所属类职责使用
    - `load_last_run`（L68）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_last_run(...)`，并结合所属类职责使用
    - `run_by_bundle`（L205）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.run_by_bundle(...)`，并结合所属类职责使用

### `utils/viz/ui/run_view.py`

- `RunView`
  - 方法数：`8`
  - 方法明细：
    - `get_plugin`（L66）：用途=读取 `plugin` 相关运行态或配置值；用法=通过 `obj.get_plugin(...)` 在日志、诊断或编排阶段查询
    - `on_refresh_ui`（L485）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.on_refresh_ui(...)`，并结合所属类职责使用
    - `on_run`（L323）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.on_run(...)`，并结合所属类职责使用
    - `on_sensitivity`（L498）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.on_sensitivity(...)`，并结合所属类职责使用
    - `snapshot`（L127）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.snapshot(...)`，并结合所属类职责使用
    - `sort_items`（L228）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.sort_items(...)`，并结合所属类职责使用
    - `sync_run_id_plugins`（L77）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.sync_run_id_plugins(...)`，并结合所属类职责使用
    - `update_sensitivity_button`（L60）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.update_sensitivity_button(...)`，并结合所属类职责使用

### `utils/viz/ui/sequence_view.py`

- `SequenceView`
  - 方法数：`4`
  - 方法明细：
    - `load_from_history_index`（L189）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_from_history_index(...)`，并结合所属类职责使用
    - `load_from_run`（L205）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_from_run(...)`，并结合所属类职责使用
    - `load_last_run`（L181）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.load_last_run(...)`，并结合所属类职责使用
    - `refresh`（L228）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.refresh(...)`，并结合所属类职责使用

### `utils/wiring/__init__.py`

- `(module)`
  - 方法数：`2`
  - 方法明细：
    - `set_parallel_thread_bias_isolation`（L27）：用途=设置 `parallel_thread_bias_isolation` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_parallel_thread_bias_isolation(...)`
    - `set_plugin_strict`（L16）：用途=设置 `plugin_strict` 相关运行参数或状态；用法=在构建 solver/adapter/plugin 时调用 `obj.set_plugin_strict(...)`

### `utils/wiring/benchmark_harness.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `attach_benchmark_harness`（L14）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_benchmark_harness(...)`，并结合所属类职责使用

### `utils/wiring/checkpoint_resume.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `attach_checkpoint_resume`（L14）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_checkpoint_resume(...)`，并结合所属类职责使用

### `utils/wiring/default_plugins.py`

- `(module)`
  - 方法数：`3`
  - 方法明细：
    - `attach_default_observability_plugins`（L107）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_default_observability_plugins(...)`，并结合所属类职责使用
    - `attach_observability_profile`（L201）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_observability_profile(...)`，并结合所属类职责使用
    - `resolve_observability_preset`（L88）：用途=解析并确定 `observability_preset` 最终结果；用法=在多来源配置合并时调用 `obj.resolve_observability_preset(...)`

### `utils/wiring/dynamic_switch.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `attach_dynamic_switch`（L13）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_dynamic_switch(...)`，并结合所属类职责使用

### `utils/wiring/module_report.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `attach_module_report`（L14）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_module_report(...)`，并结合所属类职责使用

### `utils/wiring/ray_parallel.py`

- `(module)`
  - 方法数：`1`
  - 方法明细：
    - `attach_ray_parallel`（L14）：用途=组件公开方法（需结合实现细节）；用法=按签名调用 `obj.attach_ray_parallel(...)`，并结合所属类职责使用

