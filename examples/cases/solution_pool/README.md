# 解池驱动的准备、双种群与停滞恢复

标准 Project → Case → Scaffold 示例。Project 负责 L0，Case 使用正式 ComposableSolver/PoolSearchAdapter，不自行运行第二套循环。

Project 现在按顺序运行两个独立 Case：本文下面介绍 `pool_search`；新增 [pool_refinement](cases/pool_refinement/README.md) 演示 20 起点、两类四实例 VNS 子池精修及 NSGA-II 返回竞争，默认 25 步。两者独立创建运行池，不共享另一 Case 的 Unit。

组件：PlateauProblem；UniformInitializer/GaussianMutation/ClipRepair；SA producer；NSGA-II 和 NSGA-III 两个独立种群；Solver 自带 SolutionPool。未装额外 Bias、Plugin 或 Evaluation Provider。

默认 SA 准备 8 个接纳候选：NSGA-II 取 6 个、选择保留 4 个；NSGA-III 取 2 个，后续搜索扩充到自身容量 3。在平坦目标区间触发停滞，SA 重启并搜索两个提交步骤，返回候选分别参与种群选择。7 个逻辑步骤覆盖一个完整周期。平坦问题用于稳定演示编排，不能据此声称算法获得性能优势或跳出了局部最优。

```powershell
python examples/cases/solution_pool/cases/pool_search/run_solver.py --check
python examples/cases/solution_pool/run_project.py
python -m nsgablack project doctor --path examples/cases/solution_pool --strict --build --format json
```

`build_solver()` 无需指定全局 `population_size`。可选 Case 配置为 `max_steps / pool_idle_steps / pool_retained_publications`；默认显式启用闲置 2 个提交步骤、保留最近 2 次池发布的回收策略。当前成员与未消费输入继续受保护，无人使用的行压缩退出索引，失去历史保护后才释放底层存储。长期需要重读的旧发布必须显式 pin，或保存携带完整值的正式 checkpoint。

组件装配位于 `adapter/pool_example.py`：各算法独立配置 `population_size`，`PoolSearchSpec.initial_count` 独立配置取解配额。修改本地工厂或通过 `component_overrides={"adapter": ...}` 替换组合即可；替换 Adapter 后要启用回收，必须声明 get_solution_pool_roots，不能假定未知历史也已受保护。200→100×2 与异构容量的行为测试见 `tests/test_pool_search_adapter.py`，回收与恢复见 `tests/test_solution_pool_retention.py`。

运行规则见 [解池契约](../../../docs/architecture/SOLUTION_POOL_CN.md)。原始反馈重新评估，输入与 Unit 独立，时间、游标和阶段随正式 checkpoint 恢复。
