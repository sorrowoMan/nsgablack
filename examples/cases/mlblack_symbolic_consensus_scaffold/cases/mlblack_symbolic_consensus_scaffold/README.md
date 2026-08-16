# mlblack symbolic bridge Case

这个 Case 演示统一框架栈中的正确分工：

- Project/blackbase L0 发放 `ResourceContext`；
- nsgablack 外层 Solver 搜索符号学习方案；
- mlblack 通过 `mlblack.integrations.nsgablack_symbolic` 完成基函数拟合和任务拟合；
- backend/provider 只做两边正式契约的转换，不再导入已退役的 `config.py`、`training.py` 或 `workflow.py`。

## 正式入口

- `build_solver.py`：只组装并返回一个外层 Solver；
- `run_solver.py`：解析 CLI、执行和打印结果；
- `run_project.py`：由 Project L0 发放资源后启动 Case；
- `plugins/domain_backends/mlblack_symbolic_consensus_backend.py`：跨框架 provider surface。

`--check` 只装配，不启动优化，也不会创建运行日志。正常运行会先打印脱敏的 `[resource-context]`，便于核对实际 grant。

## 快速验证

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\run_project.py --check

python examples\cases\mlblack_symbolic_consensus_scaffold\cases\mlblack_symbolic_consensus_scaffold\run_solver.py `
  --outer-adapter vns `
  --generations 1 `
  --pop-size 4 `
  --batch-size 4 `
  --n-total 32 `
  --consensus-cycles 1 `
  --unlocked-runs-per-cycle 1 `
  --locked-runs-per-cycle 1 `
  --inner-fit-steps 1 `
  --task-fit-steps 1 `
  --no-logs
```

## 资源与预算

内层 mlblack Trainer 继承外层 `ResourceContext`，并把 namespace 派生为 `<outer>.mlblack_inner`。以下参数控制单个 backend 调用的工程成本：

- `--inner-fit-steps` / `--inner-fit-population`：正交基拟合；
- `--task-fit-steps` / `--task-fit-population`：基条件任务拟合；
- `--inner-time-budget-ms`：单次内层调用超时；
- `--max-inner-calls`：外层运行可发起的内层调用上限。

输出中的 `summary.json`、`comparison.json` 和 `core_selection.json` 是可审计结果；大对象不写入 Solver context。
