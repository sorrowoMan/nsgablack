# learnable_conv_component_search

`learnable_conv_component_search` 保留的是一个跨框架 outer-search 设计壳，用来表达：

- `nsgablack` 负责 outer structure search
- 内层评价本应通过正式 `mlblack` Case surface 完成
- Project 层统一负责编排和 `ResourceContext` grant

它现在属于迁移保留材料，不应再被当作“当前可直接运行的权威跨框架案例”。

## 当前定位

这个 Case 想表达的语义仍然成立：

- outer decision vector 负责卷积结构选择
- inner task 负责系数拟合和性能评价
- outer/inner 之间通过标准 Case surface、artifact/result payload 和 `component_overrides` 通信

但当前仓库里并没有随仓提供的内层 `learnable_conv_component_demo` 标准 Case，所以这里不能再继续用旧的私有目录组织去暗示“已经完整接好”。

## 现在应该怎样理解它

- `build_solver.py` 仍然是这个 outer Case 的标准组装入口
- `run_solver.py` 是本地 Case 运行入口
- Project 层如果要真正跑通它，必须先恢复内层 `mlblack` 标准 Case
- Project L0 负责声明资源并下发 `ResourceContext`
- outer Case 只能消费 grant，不能自己私配全局资源

## 目录口径

请把这个目录视为“标准 Case 外壳 + 迁移保留实现”，而不是旧式 `case_scaffold` 教学样板。

现在真正应该关注的是这些标准落点：

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 Case 组装入口 |
| `run_solver.py` | Case 本地 CLI / 调试入口 |
| `problem/` | outer problem、objective、constraint、inner-task contract |
| `pipeline/` | outer genome 的表示与流转 |
| `adapter/` | outer search strategy |
| `bias/` | outer soft guidance |
| `plugins/` | 运行时 bridge、审计、追踪、超时控制 |
| `evaluation/` | outer evaluation surface |
| `runtime/` | Case 级 requirement / audit |

## 迁移建议

如果要把这个案例重新扶正，正确路径是：

1. 在 `mlblack/examples/cases/*` 中补回内层标准 Case。
2. 让 Project 层把 outer Case 和 inner Case 一起装进正式 Project。
3. outer `evaluate()` 或 stage runner 只通过标准 Case surface 调用 inner Case。
4. 资源统一走 Project L0 grant，不在 case 默认值里写死设备、线程或 backend。

## 结论

保留它是合理的，因为它表达了一个重要架构方向；但它现在是“迁移中的 compatibility material”，不是新架构的最终示范面。
