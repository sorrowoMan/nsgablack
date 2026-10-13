# pool_search

- 语义类型：`solver`
- 语义框架：`nsgablack`
- 规范装配入口：`build_solver.py`
- 独立运行入口：`run_solver.py`

使用 PlateauProblem、共享问题 Pipeline 和 PoolSearchAdapter；组合 SA producer 与两个独立 NSGA-II/III Unit。默认准备 8 个候选，两边分别取 6 个和 2 个，算法容量分别为 4 和 3；停滞后重启 SA，返回候选参与两边环境选择。7 步展示一个周期，详细运行说明见 [Project README](../../README.md)。

Project L0 授权 threads=1、无 GPU；Case 仅消费传入 ResourceContext。无额外 Bias/Plugin/Provider。`build_solver()` 不要求统一大小，`config` 可设置 `max_steps / pool_idle_steps / pool_retained_publications`；默认保留活引用、回收闲置 2 个提交步骤的解，保留最近 2 次池发布。算法参数和取解配额在 `adapter/pool_example.py` 分别声明，component_overrides 仍走正式组件替换入口；替换 Adapter 必须显式声明全部池活引用才能启用回收。
