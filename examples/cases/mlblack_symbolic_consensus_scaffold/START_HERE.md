# START_HERE

## 1) 这个 case 验证什么

`mlblack_symbolic_consensus_scaffold` 验证 nsgablack 对多次 mlblack symbolic-learning runs 的编排。

- nsgablack 搜索 consensus 和 budget knobs。
- mlblack 执行 symbolic orthogonal-basis runs、consensus 和 locked-core refinement。
- Bridge-back metrics 将 truth recovery、RMSE 和 core-basis stability 暴露给 outer solver。

Contract path、结构、指标和预期信号见 `README.md`。

## 2) 运行

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\build_solver.py `
  --benchmark-key ohm_like `
  --outer-adapter complex `
  --generations 3 `
  --pop-size 6 `
  --vanilla-runs 3 `
  --locked-runs 2
```

## 3) 关键指标

| 指标 | 含义 |
|---|---|
| truth-recovery summary | 符号结构恢复信号。 |
| RMSE summary | 内层 mlblack error signal。 |
| core-basis summary | Consensus basis terms 的稳定性。 |
| timeout/budget metrics | 选中 recipe 的 runtime control signal。 |

## 4) 预期信号

有效运行应该在不超过 outer runtime budget 的前提下，改善 symbolic consensus stability 或 RMSE。
