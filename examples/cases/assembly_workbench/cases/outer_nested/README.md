# 外层条件优化

外层决策为 x，内层独立搜索 y，目标为 `inner_loss + 0.05*x**2`。
每个候选通过 `CaseRuntimeContext.invoke(CaseRunRequest(...))` 调用完整 inner_response，
条件仅放在 `inputs.inner_task_payload`，父级资源、预算、取消与身份由底座派生。
默认两个 GA 提交、每次两候选；每个内层两次求值，规模用于检查协议而非算法效果比较。

从 Project 根执行 `python cases/outer_nested/run_solver.py --check` 或直接运行该文件。
实际独立运行委托 Project 的 nested 分组，仍有正式 L0 与 Artifact authority。
无上游输入时报告明确标记 `baseline_source=builtin`，不声称读取过上游产物。
完整 Project 接收 hybrid_summary、directions_summary 两个权威输入，供比较报告使用，不共享 Pool。

默认输出 `results/outer_nested/`，可通过 `component_overrides.output_dir` 改变。
每次内层输出分开保存在 `inner_calls/call_*/`。
summary 和 nested_report 由 Case 最终发布事务生成；本地 JSON 是便于查看的副本，权威性以 Case 发布收据为准。

Solver 已完成自己的 teardown 与最终结果准备后，Case 的 export_case_result 再暂存两份教学 Artifact。
共享 CaseExecutor 在结果序列化和清理成功后封印这组产物；这两层发布职责不同，不把本地文件当发布收据。

验证：

```powershell
python -m pytest tests/test_assembly_workbench_nested.py -q -o addopts=
python -m nsgablack project doctor --path examples/cases/assembly_workbench/cases/outer_nested --strict --build --catalog-audit --profile framework-core --format json
```

2026-10-21：五项实际运行测试通过，包含两个 Case 的 --check 与默认 CLI；本 Case Doctor 为零错误、零警告。
测试检查真实响应、父子身份、独立 Pool、每次子预算结算 2 次、权威收据和运行身份。
