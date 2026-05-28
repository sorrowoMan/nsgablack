# START_HERE

## 1) 这个 case 验证什么

`learnable_conv_component_search` 验证 nsgablack 对 mlblack learnable convolution component 的 outer structure search。

- nsgablack 搜索 kernel structure、stride、padding、pooling、output mode 和 symbolic basis terms。
- mlblack 通过 `learnable_conv_component_demo` 评估/细化选中 component。
- Objectives 平衡 test RMSE、generalization gap、feature complexity 和 kernel recovery。

结构、指标和预期信号见 `README.md`。

## 2) 运行

```powershell
python -m examples.cases.learnable_conv_component_search.run_solver --pop-size 4 --offspring-size 4 --generations 1
```

## 3) 关键指标

| 目标 | 含义 |
|---|---|
| `test_rmse` | Held-out prediction error。 |
| `generalization_gap` | Overfit/generalization signal。 |
| `feature_complexity` | 选中 component 的结构成本。 |
| `kernel_recovery_penalty` | 是否恢复目标 kernel structure。 |

## 4) 预期信号

有效运行应该改善 test error 和 kernel recovery，同时控制 component complexity。
