# START_HERE

## 1) 这个 case 验证什么

`l0_distributed_worker` 验证 nsgablack 的 L0 worker/runtime path。

- nsgablack 通过 worker-capable runtime boundary 调度 tiny black-box evaluations。
- case 检查 task claim、result return 和 worker lifecycle behavior。
- 当前 runtime path 不使用 mlblack。

更多指标、结构和能力信号见 `README.md`。

## 2) 验证 assembly

```powershell
python -m nsgablack project doctor --path . --build
python run_solver.py --check
```

## 3) 运行

```powershell
python run_solver.py
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| synthetic objective | 很小的标量目标，用于聚焦 worker behavior。 |
| claimed tasks | Worker dequeue/claim 信号。 |
| completed results | Worker result-return 信号。 |
| heartbeat | Worker liveness 信号。 |

## 5) 预期信号

有效运行应该显示 tasks 被 claim 并 completed，且没有 duplicate processing；优化质量不是这个 case 的目的。
