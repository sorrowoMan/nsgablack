# 综合装配 Project：本次实际结果

Project run：`20261021T063514Z-682447b246`；group：`default`。

正式 manifest：`C:\Users\hp\Desktop\nsgablack\examples\cases\assembly_workbench\.blackbase\runs\20261021T063514Z-682447b246\manifest.json`。

## hybrid_search

- `14` 次逻辑提交，`36` 次本层求值。
- 最终候选：`[0.6419841826745183, 0.5580158173254817]`；选择目标：`[0.09386592699417522]`。
- 实际装配：`case_class=ComposableSolver, problem=RecipeProblem, pipeline=RecipePipeline, adapter=SearchPlanAdapter`。
- Plugins：`['checkpoint_resume', 'workbench_trace']`；Providers：`[]`。
- L0 grant：`{'threads': 1, 'workers': 1, 'gpus': 0, 'backend': 'local'}`，binding.current=`true`。
- namespace：`assembly_workbench.searches.hybrid_search`。
- 权威发布：`['checkpoint_final', 'summary']`，另有 `14` 份求值证据归档。

## directions

- `15` 次逻辑提交，`24` 次本层求值。
- 最终候选：`[-0.5203461795988562]`；选择目标：`[2.3114525058208377, 0.2300677874254127]`。
- 实际装配：`case_class=ComposableSolver, problem=DirectionProblem, pipeline=RepresentationPipeline, adapter=SearchPlanAdapter`。
- Plugins：`['pareto_archive', 'direction_trace']`；Providers：`[]`。
- L0 grant：`{'threads': 1, 'workers': 1, 'gpus': 0, 'backend': 'local'}`，binding.current=`true`。
- namespace：`assembly_workbench.searches.directions`。
- 权威发布：`['summary']`，另有 `15` 份求值证据归档。

## outer_nested

- `2` 次逻辑提交，`4` 次本层求值。
- 最终候选：`[0.0923037107020466]`；选择目标：`[0.06292599875046834]`。
- 实际装配：`case_class=NestedCase, problem=NestedResponseProblem, pipeline=RepresentationPipeline, adapter=NSGA2Adapter`。
- Plugins：`['nested_trace']`；Providers：`[]`。
- L0 grant：`{'threads': 2, 'workers': 2, 'gpus': 0, 'backend': 'local'}`，binding.current=`true`。
- namespace：`assembly_workbench.nested.outer_nested`。
- 权威发布：`['nested_report', 'summary']`，另有 `2` 份求值证据归档。

## Project 交接

- 两个上游 Case 生命周期重叠 `23.010375` 秒。
- outer_nested 在两个上游发布完成后启动，输入绑定与生产者权威发布一致。
- 生命周期重叠不是 CPU 利用率或性能加速比测量。

## 如何读这些结果

hybrid_search 的 raw 与 selection 不同：Bias 改软评分，原始约束接纳单独判断。
directions 不加 Bias，保留多目标原始反馈，投影只用于任务比较。
outer_nested 的本层求值次数是外层候选数；内层求解的开销与收据在 nested 报告中单独列出。
各 Case 的目标含义不同，不用一个 best 分数对它们排优劣。

- [结构化汇总](results/summary.json)
- [完整正式返回值](results/project_result.json)
- [主 Case 提交轨迹](results/hybrid_search/trace.json)
- [方向与投影轨迹](results/directions/trace.json)
- [装配教程](README.md)

trace 是观察报告；跨 Case 使用 ArtifactBinding，不能把 JSON 文件名当权威引用。
