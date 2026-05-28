# START_HERE

## 1) 这个 case 验证什么

`ransac` 验证 robust subset selection 可以作为 black-box optimization。

- nsgablack 在 samples 上搜索 inlier mask。
- NumPy least squares 拟合选中的 inlier subset。
- 当前 runtime path 不使用 mlblack。

指标、结构、mlblack 状态和能力信号见 `README.md`。

## 2) 验证 assembly

```powershell
python run_solver.py --check
```

## 3) 运行

```powershell
python run_solver.py
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| inlier RSS | Selected inliers 上的 least-squares residual sum of squares。 |

## 5) 预期信号

有效运行应该在 outliers 存在时找到低 residual cost 的 inlier subset，而且不需要 specialized RANSAC Adapter。
