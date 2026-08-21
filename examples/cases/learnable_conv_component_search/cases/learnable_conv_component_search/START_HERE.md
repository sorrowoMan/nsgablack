# START_HERE

这个 Case 验证一条完整递归链：外层结构搜索 → 内层系数优化 → ML 模型训练。

推荐直接运行 Project，而不是孤立启动需要父级运行时的子 Case：

```powershell
python examples/cases/learnable_conv_component_search/run_project.py --group default
```

运行时应看到三个不同的 `case_run_id`、逐层递增的 depth、父子 `parent_case_run_id`，以及每层生效后的 `ResourceContext`。最终结果同时保留 Pareto/求解信息、训练指标和子调用 lineage。

详细协议见：

- `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`
- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
