# 固定基准协议（small / medium / large）

本文件定义框架的长期基准证据协议：

- 不是追求某一次“跑得快”。
- 是追求版本之间可比较、可复现、可追踪。

## 1. 运行命令

```powershell
python benchmarks/fixed_baseline_runner.py --repeats 3 --seed 20260217
```

输出目录默认：`runs/evidence/baseline`。

## 2. 固定场景

- `small`: dimension=8, pop_size=40, generations=20
- `medium`: dimension=24, pop_size=80, generations=30
- `large`: dimension=60, pop_size=140, generations=40

## 3. 输出产物

- `baseline_raw_*.csv`: 每次运行的原始记录
- `baseline_summary_*.csv`: 每个场景聚合统计
- `baseline_summary_*.json`: 聚合报告（带 schema）

关键指标：
- `wall_s_median`
- `best_score_median`
- `eval_count_median`

## 4. 证据使用方式

建议每次发布前至少保留一份 summary：

- 在 PR/变更说明中对比上一份 summary
- 如果性能或质量波动 > 20%，必须解释原因
- 若为预期变化（如更严格契约检查），需写明 trade-off

## 5. 注意事项

- 固定 seed 才能比较趋势。
- 机器不同会影响绝对时间，优先看同机趋势。
- 大改动后可额外跑一次 `--repeats 5` 观察稳定性。
