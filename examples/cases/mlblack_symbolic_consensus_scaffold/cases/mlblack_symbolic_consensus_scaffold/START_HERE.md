# 从这里开始

先执行只装配检查：

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\run_project.py --check
```

再执行一个小规模真实闭环：

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\cases\mlblack_symbolic_consensus_scaffold\run_solver.py `
  --outer-adapter vns --generations 1 --pop-size 4 --batch-size 4 `
  --n-total 32 --consensus-cycles 1 `
  --unlocked-runs-per-cycle 1 --locked-runs-per-cycle 1 `
  --inner-fit-steps 1 --task-fit-steps 1 --no-logs
```

成功时应看到：

- `[resource-context]`：Project 发放并由内层继承的资源；
- `[case] status=ok`：外层 Solver 完成；
- `best_inner`：truth recovery、family recovery 和 RMSE；
- `summary=...`：mlblack 正式 symbolic surface 生成的审计摘要。

完整边界和参数说明见同目录 `README.md`。
