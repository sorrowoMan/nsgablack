# START_HERE

这个 Case 用一个具体任务展示统一视图：模型结构是候选，系数细化是子优化，数据训练是 ML 语义评价。

运行完整 Project：

```powershell
python examples/cases/symbolic_kernel_digits_outer_search/run_project.py --group default
```

请从 Project 输出检查三项：父子 lineage 是否连续、各层资源是否来自 L0 grant、最终 SolverResult 是否保留训练指标和子 Case 证据。

协议说明见：

- `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`
- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
