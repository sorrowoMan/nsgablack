# MAP-Elites 档案 Case

使用真实 `MapElitesAdapter`，装配 `IdentityDescriptor`、二维 `GridCells`、`MinimizeObjective` 与有限 `SequenceEmitter`。五个候选真实送评，最终三个格子保留 B/C/D，A 被同格更好者替换，E 未成为冠军。

运行入口是本目录 `run_solver.py`，Project 入口是上层 `run_project.py --group map_elites_archive`。在正式 CaseRuntime 中，summary 经既有 case_finalization 事务发布为权威 Artifact；`summary.json` 另作本地观察文件，不冒充 Artifact 交付收据。

档案 Unit 是唯一可写冠军权威。Pool 的 `map_elites/archive` 是该权威的准确引用视图，与 Unit、Authority 在原步骤事务一同发布。描述符使用实际送评后候选；部分接纳只更新接纳行，不把未评估或未接纳行伪装成冠军。

此版本 emitter 接口只声明候选生成，支持有限序列与从档案抽样的高斯变化；未声明依赖整批反馈进行分布自适应的 CMA emitter。替换 emitter 时空返回只表示等待，须显式 `exhausted=True` 才正常结束。专用组件有显式状态 codec 与运行期所有权检查；当前 Doctor 的四类行为绑定检查不自动覆盖这些专用方法。
