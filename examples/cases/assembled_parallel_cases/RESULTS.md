# 两个独立 Case 的实际并发结果

Project run：`20261019T062843Z-aa700e9860`。

- Stage：`parallel`，`max_workers=2`。
- 实际观察到的 Case 生命周期重叠：`20.654013` 秒。
- 重叠区间：`2026-10-19T06:28:46.093+00:00` → `2026-10-19T06:29:06.747+00:00`。
- 整体入口耗时：`27.185419` 秒。

重叠使用正式 CaseRunResult 的 started_at/finished_at 计算，包含构建、运行、清理和发布；
它证明两个 Case 生命周期并发，不证明某一瞬间两个目标函数都占用 CPU，也不是加速比测试。

## de_bowl · DifferentialEvolutionAdapter

- 最终候选：`[1.0269052606207416, -2.0962919978836867]`。
- 目标：`0.0099960419055`；已知最优值 `0`，最优点 `[1.0, -2.0]`。
- `16` 次逻辑提交、`192` 次求值。
- 开始：`2026-10-19T06:28:46.093+00:00`；结束：`2026-10-19T06:29:06.747+00:00`。
- Case 生命周期耗时 `20.654551` 秒；Solver 报告耗时 `16.427336` 秒。
- L0 授权：threads=`1`、workers=`1`。
- namespace：`assembled_parallel_cases.independent_searches.de_bowl`。
- lease：`lease-de_bowl-independent_searches-6eff2b0af749`。

## sa_valley · SimulatedAnnealingAdapter

- 最终候选：`[-1.422580916364861, -0.0491356359036378]`。
- 目标：`2.5604647728`；已知最优值 `0`，最优点 `[-1.5, 0.75]`。
- `40` 次逻辑提交、`40` 次求值。
- 开始：`2026-10-19T06:28:46.093+00:00`；结束：`2026-10-19T06:29:09.829+00:00`。
- Case 生命周期耗时 `23.736003` 秒；Solver 报告耗时 `17.402314` 秒。
- L0 授权：threads=`1`、workers=`1`。
- namespace：`assembled_parallel_cases.independent_searches.sa_valley`。
- lease：`lease-sa_valley-independent_searches-64f2a7e6cb27`。

## 对账

- 两个独立 Case 均通过正式 Project 执行。
- 两段 Case 生命周期发生真实重叠。
- 每个 Case 的 threads=1、workers=1 且 binding.current=true。
- Case 运行身份、资源 lease 与 namespace 彼此独立。
- 求值次数与各算法声明预算一致。
- 最终候选、原始函数解析核对和问题边界一致。

解析重算仅用于报告核对；没有 Bias，所以本例选择目标与原始目标一致。
DE 与 SA 使用不同问题、不同 Solver、不同解池，没有交换候选，也没有共享 Unit。
该结果不能用于比较 DE 与 SA 优劣：问题、步数、批量数都不同。

完整正式返回值：[project_result.json](results/project_result.json)；简明汇总：[summary.json](results/summary.json)。
