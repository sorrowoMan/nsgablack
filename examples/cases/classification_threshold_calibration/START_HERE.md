# START_HERE

## 1) 这个 case 验证什么

`classification_threshold_calibration` 验证 hybrid nsgablack + mlblack operating-point search pattern。

- nsgablack 搜索 outer decision variables：threshold 和 temperature。
- mlblack 负责 classification feedback：log-loss、F1、precision、recall 和 accuracy。

完整指标、结构、mlblack component list 和效果对比见 `README.md`。

## 2) 验证 assembly

```powershell
python run_solver.py --check
```

## 3) 运行 capability smoke test

```powershell
python run_solver.py --quickstart
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| `valid_log_loss` | 来自 mlblack classification evaluation 的 validation log-loss。 |
| `f1_loss` | `1 - valid_f1`，越低越好。 |
| `intervention_rate` | Validation samples 中被预测为 positive 的比例。 |

## 5) 预期信号

有效运行应该打印：

- `valid_log_loss`
- `f1_loss`
- `intervention_rate`
- `best_recipe`
- `valid_f1`、`precision`、`recall`

预期对比是 default F1 约 `0.62`，search-selected F1 约 `0.83`，同时暴露 intervention-rate tradeoff。
