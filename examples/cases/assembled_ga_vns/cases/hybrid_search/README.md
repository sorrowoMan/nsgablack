# hybrid_search

唯一装配入口为 build_solver.py。Problem、问题 Pipeline、自定义种群 Unit、软 Bias、观察 Plugin 分目录提供代码；算法行为装配在 adapter/composition.py。

从 Project 根运行 python run_project.py --check --build-check 检查装配，运行 python run_and_report.py 执行并整理报告。Case 本身可用 python cases/hybrid_search/run_solver.py 独立运行，使用标准 Case CLI 的资源绑定路径。

运行细节、组件源码位置和实际数值见 Project 根的 README、COMPONENTS 与 results。

默认 `refinement_source="population"` 维持原先全种群逐成员精修。显式选择 `"elite"` 时，GA的choose同时发布 `ga_elite`，VNS命名回调按准确公共池名冻结精英引用，再把聚合接纳提案返回GA竞争。Project的 `elite` 分组使用同一Case的正式config override，演示24成员中选20个精英、预算128次求值；从Project根运行 `python run_elite_and_report.py`。结果独立保存在 `results/elite/`，详情见根目录 `ELITE_RESULTS.md`；聚合提案不是每项任务最终精选的别名。
