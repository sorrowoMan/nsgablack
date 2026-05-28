# START_HERE

## 1) 这个 case 验证什么

`symbolic_kernel_digits_outer_search` 验证 nsgablack 对 mlblack image-classification inner case 的 symbolic kernel search。

- nsgablack 搜索 symbolic kernel/object structure。
- mlblack 在 `digits` 或 `fashion_mnist` 上评估解码后的 kernel。
- 主指标是 strict accuracy-first loss，并包含 gap、complexity、prior penalties。

结构、指标和预期信号见 `README.md`。

## 2) 运行 digits

```powershell
python -m examples.cases.symbolic_kernel_digits_outer_search.run_solver --inner-dataset-key digits --inner-trainer-key mlp_torch --inner-backend torch --inner-device cuda:0
```

## 3) 运行 Fashion-MNIST

```powershell
python -m examples.cases.symbolic_kernel_digits_outer_search.run_solver --inner-dataset-key fashion_mnist --inner-trainer-key mlp_torch --inner-backend torch --inner-device cuda:0 --inner-max-rows 4000 --inner-mlp-epochs 10
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| `strict_primary_loss` | Accuracy-first scalar objective。 |
| `classification_error` | 原始分类错误率。 |
| `generalization_gap` | Train/test gap。 |
| `feature_complexity` | Kernel feature complexity。 |
| `kernel_prior_penalty` | Preferred-prior violation penalty。 |

## 5) 预期信号

有效运行应该改善图像分类错误率，同时控制 gap、complexity 和 prior penalties。
