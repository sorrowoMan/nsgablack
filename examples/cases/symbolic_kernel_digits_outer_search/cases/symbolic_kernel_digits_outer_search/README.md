# symbolic_kernel_digits_outer_search

这是一个已可运行的三层跨框架图像学习示例：

1. `symbolic_kernel_digits_outer_search` 用 nsgablack 搜索符号卷积核结构。
2. `symbolic_kernel_digits_refinement` 用子 Solver 细化固定结构下的核系数。
3. `symbolic_kernel_digits_training` 用 mlblack Trainer 在 sklearn digits 数据上构造卷积特征并拟合分类器。

三层通过正式 `CaseRunRequest/CaseRunResult` 协议递归调用；Project L0 统一派生资源、预算、取消与 lineage，不再依赖旧 demo surface 或目录级私有胶水。

## 运行

```powershell
python examples/cases/symbolic_kernel_digits_outer_search/run_project.py --check
python examples/cases/symbolic_kernel_digits_outer_search/run_project.py --group default
```

默认参数是轻量可执行配置。外层仍交付多目标结果：分类错误率、泛化差距、特征复杂度和 kernel prior penalty；内层 Trainer 返回正式训练结果及可审计指标。

## 边界

- nsgablack 只拥有搜索与 Pareto 语义。
- mlblack 只拥有数据视图、特征/模型语义、训练评估与 Artifact。
- 子 Case 只消费父级 grant，不自行分配全局 GPU、线程或 worker。
- 子失败保留结构化 `CaseFailure`，不会压成无来源的分数。
