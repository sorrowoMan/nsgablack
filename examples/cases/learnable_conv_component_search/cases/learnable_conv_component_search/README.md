# learnable_conv_component_search

这是一个已闭环的三层跨 Case 示例，用来展示“结构搜索、系数细化、模型训练”如何在统一 Project/L0 控制面下组合：

1. `learnable_conv_component_search`：nsgablack 外层 Solver，搜索卷积结构与符号基。
2. `learnable_conv_coefficient_refinement`：nsgablack 子 Solver，在固定结构下细化系数。
3. `learnable_conv_component_training`：mlblack 子 Trainer，拟合并验证实际卷积特征模型。

外层和子层都不是私有函数调用。每次递归都通过 `CaseRunRequest` 发起，继承父级 lineage、deadline/cancellation、预算与 `ChildResourceGrant`，结果通过正式 `CaseRunResult` 返回。

## 运行

从 nsgablack 仓库根目录执行：

```powershell
python examples/cases/learnable_conv_component_search/run_project.py --check
python examples/cases/learnable_conv_component_search/run_project.py --group default
```

默认配置是可执行的轻量演示；扩大 population、generation、训练样本数和 refinement steps 即可形成更完整实验。

## 职责边界

- 外层 Problem 只生成结构任务并消费子 Case 结果，不知道 mlblack Trainer 内部实现。
- 系数细化 Case 负责数值优化语义，不直接拥有模型训练后端。
- mlblack Case 负责数据、卷积特征、拟合、指标和模型 Artifact 语义。
- Project L0 是资源、取消、预算和 Artifact authority 的唯一授权者。

主要目标为 `test_rmse`、`generalization_gap`、`feature_complexity` 与 `kernel_recovery_penalty`。`fit_complexity_score` 仅是前三项的报告聚合值，不参与替代多目标结果。
