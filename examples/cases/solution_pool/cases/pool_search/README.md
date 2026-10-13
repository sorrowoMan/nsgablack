# pool_search

- 语义类型：`solver`
- 语义框架：`nsgablack`
- 规范装配入口：`build_solver.py`
- 独立运行入口：`run_solver.py`

使用 PlateauProblem、共享问题 Pipeline 和 PoolSearchAdapter；组合 SA producer 与两个独立 NSGA-II/III Unit。默认准备 8 个候选，两边各取 4 个；停滞后重启 SA，返回候选参与两边环境选择。7 步展示一个周期，详细运行说明见 [Project README](../../README.md)。

Project L0 授权 threads=1、无 GPU；Case 仅消费传入 ResourceContext。无额外 Bias/Plugin/Provider。`build_solver(config={"population_size": 100})` 可扩大分配，component_overrides 仍走正式组件替换入口。
