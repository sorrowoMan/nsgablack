# START_HERE

## 1) 这个 case 验证什么

`residual_boosting` 验证 hybrid nsgablack + mlblack residual-training pattern。

- nsgablack 搜索 outer recipe：base L2、residual L2、residual weight、residual feature mode。
- mlblack 负责 inner ML semantics：serial stages、residual target construction、regression evaluation 和 additive prediction integration。

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
| `valid_mse` | Integrated base + residual model 的 validation MSE。 |
| `recipe_complexity` | Residual feature/weight 使用的 complexity proxy。 |

## 5) 预期信号

有效运行应该找到 enriched residual recipe，并打印：

- `best_valid_mse`
- `recipe_complexity`
- `best_recipe`
- `mlblack_serial_stages=['base_linear', 'residual_linear']`

预期对比是 base-only MSE 约 `4.19`，enriched residual MSE 约 `0.006`，说明 mlblack residual semantics 确实在起作用。
