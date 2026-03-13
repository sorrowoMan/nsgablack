# 权威示例输入/输出契约（Example I/O Contracts）

这个索引只回答三件事：  
1) 输入是什么  
2) 输出产物在哪里  
3) 用它验证什么能力

## 1) `examples/end_to_end_workflow_demo.py`

- 输入
  - 问题定义 + 组件装配（wiring）
  - seed / run_id / 输出目录
- 输出
  - `runs/<run_id>.csv`
  - `runs/<run_id>.summary.json`
  - `runs/<run_id>.modules.json`
- 目的
  - 验证“装配 -> 运行 -> 审计”闭环

## 2) `examples/benchmark_harness_demo.py`

- 输入
  - solver + `BenchmarkHarnessPlugin` 配置
- 输出
  - `runs/benchmark_harness_demo/*.csv`
  - `runs/benchmark_harness_demo/*.summary.json`
- 目的
  - 固定实验口径（steps/eval_count/throughput/best_score）

## 3) `examples/cases/production_scheduling/working_integrated_optimizer.py`

- 输入
  - 排产业务数据（Excel/表格）
  - adapter/bias/plugin 参数
- 输出
  - 业务优化结果文件（排产计划）
  - run artifacts（benchmark/module/profile）
- 目的
  - 真实业务案例装配与审计

## 4) `examples/surrogate_plugin_demo.py`

- 输入
  - surrogate 插件配置 + baseline solver
- 输出
  - summary JSON（真实评估比例/代理覆盖）
  - 对应 run logs
- 目的
  - 验证昂贵评估下的插件短路能力

## 5) 对比表输出（benchmark）

如果目录下已有多个 `*.summary.json`：

```powershell
python benchmarks/compare_summary.py --input-dir runs --output runs/benchmark_comparison.md
```

输出：
- `runs/benchmark_comparison.md`（Markdown 表格）
