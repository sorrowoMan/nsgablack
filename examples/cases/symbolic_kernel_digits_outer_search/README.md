# Symbolic Kernel Image Outer Search（符号核图像外层搜索）

`symbolic_kernel_digits_outer_search` 验证 nsgablack 对 mlblack 图像分类 inner case 的 symbolic image-kernel structure 外层搜索能力。

## 这个 case 验证什么

- nsgablack 搜索 symbolic image-kernel structure。
- mlblack 在图像分类数据集上评估解码后的 kernel object。
- Objective 是 strict accuracy-first，gap、complexity 和 prior penalties 作为次级项。
- case 支持轻量 `digits` 运行，也支持更大的 Fashion-MNIST 图像分类运行。

## 是否使用 mlblack

使用。Inner evaluation surface 是 mlblack 图像分类 case：

- `examples.cases.symbolic_kernel_digits_classification`

## nsgablack 侧能力

- Outer symbolic kernel genome。
- 搜索 kernel/object structure choices。
- 使用 strict-primary scalar objective，同时记录 secondary raw/weighted terms。

## mlblack 侧能力

- `digits` 和 `fashion_mnist` 图像分类数据集加载。
- `symbolic_kernel_object` pipeline object。
- `ridge` 和 `mlp_torch` 等 trainers。
- 将 classification metrics 返回给 outer objective。

## 目标和指标（Objectives / Metrics）

| 指标 | 含义 |
|---|---|
| `strict_primary_loss` | nsgablack 主目标；accuracy-first scalar，并带次级惩罚。 |
| `classification_error` | 原始图像分类错误率。 |
| `generalization_gap` | Train/test gap penalty。 |
| `feature_complexity` | Symbolic kernel features 的结构复杂度。 |
| `kernel_prior_penalty` | 违反 preferred kernel priors 的惩罚。 |
| weighted accuracy/gap/complexity/prior terms | 构造 strict primary loss 的分项。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `run_solver.py` | CLI entry。 |
| `build_solver.py` | 被 CLI 使用时的标准 assembly entry。 |
| `case_scaffold/problem/outer_problem.py` | 解码 kernel structure，并调用 mlblack inner case。 |
| `case_scaffold/pipeline/` | Outer kernel genome 的 representation pipeline。 |
| `case_scaffold/config/` | CLI/config surface。 |
| `case_scaffold/orchestration/` | Solver assembly 和 strategy selection。 |

## 运行

Digits：

```powershell
python -m examples.cases.symbolic_kernel_digits_outer_search.run_solver --inner-dataset-key digits --inner-trainer-key mlp_torch --inner-backend torch --inner-device cuda:0
```

Fashion-MNIST：

```powershell
python -m examples.cases.symbolic_kernel_digits_outer_search.run_solver --inner-dataset-key fashion_mnist --inner-trainer-key mlp_torch --inner-backend torch --inner-device cuda:0 --inner-max-rows 4000 --inner-mlp-epochs 10
```

## 预期信号（Expected signal）

有效运行应该主要通过降低 `classification_error` 来降低 strict primary loss，而不是靠降低 complexity 或 prior penalties 来掩盖 accuracy regression。
