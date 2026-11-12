# nested_outer

先运行直接裸参考，再通过 CaseRuntime.invoke 将 bare_inner 显式切换为 matrix 模式，按相同算法、seed 和步数运行真实 ComposableSolver。子 Case 必须先通过语义和质量检查，再比较其框架最终状态、逐步状态、实际求值序列和计数。报告同时保存子 Case 身份、继承授权与权威 Artifact 发布回执。bare_inner 在独立阶段仍保留裸参考模式。

规范入口为 `build_solver.py`，它委托 `benchmarks.transparency_case.make_benchmark_case`；`run_solver.py` 保持正式 Case CLI。`config.py` 注册实际共享工厂和 PairSpec 目录，并声明一个 CPU 线程、一个 worker。授权由 Project L0 发放，Case 不创建 allocator 或 lease。

实际 Problem、Pipeline、Adapter 和 Unit 由 `benchmarks.transparency_registry.specs()` 返回的 PairSpec 声明；Case 层不复制这些对象，也不保留已删除的 starter 组件。配置通过正式 `config` / `component_overrides["config"]` 注入。

成功报告经 CaseRuntime 发布名为 `report` 的 Artifact，只有正式 Case 最终提交才产生权威回执。必要语义、质量或恢复检查失败时，报告先保存到本地 `results/<case_run_id>/failed_report.json`，Case 抛错并让 Project 返回非零。

`--check` 和 Doctor `--build` 只构造 `TransparencyCase` 并检查其共享装配与授权；此时还没有选中算法的运行 Unit，因此组件面显示 `None`。这些检查不能代替实际逐 PairSpec 的 run、恢复或并行测试。
