# L0 Distributed Worker（L0 分布式 Worker）

`l0_distributed_worker` 验证 nsgablack 的 L0 distributed task execution（分布式任务执行）能力，并刻意避开重领域问题。

## 这个 case 验证什么

- L0 runtime 可以 enqueue outer evaluation tasks，并让 workers 并发 claim。
- Worker registry/heartbeat 和 task-claim lifecycle 通过 scaffold 被验证。
- Objective 故意很小，用来隔离 queue/worker behavior，而不是优化质量。
- 当前不使用 mlblack。

## 是否使用 mlblack

不使用。这是 nsgablack runtime/worker capability check。

## nsgablack 能力体现

- 通过 `build_solver.py` 使用标准 scaffold assembly。
- `runtime/` 下的 L0 runtime 和 worker backend wiring。
- `evaluation/` 下的 evaluation layer separation。
- governance、observability、operations 的 plugin 边界。
- 分布式 evaluation 的 task claim / result flow。

## 指标和目标（Metrics / Objectives）

| 指标 | 含义 |
|---|---|
| synthetic objective | 很小的标量目标，只用于验证 distributed worker path。 |
| claimed tasks | 确认 worker 能 claim queued work，且不重复处理。 |
| completed results | 确认 claimed tasks 能把结果写回 scheduler path。 |
| worker heartbeat | 确认 L0 runtime 能观察 worker liveness。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 主 assembly entry。 |
| `run_solver.py` | CLI smoke entry。 |
| `??????` | Attach/build helpers。 |
| `problem/` | Tiny black-box problem，用于隔离 worker backend。 |
| `pipeline/` | Representation pipeline。 |
| `runtime/` | L0 distributed runtime pieces。 |
| `evaluation/` | Worker execution 的 evaluation boundary。 |
| `plugins/` | Governance、ops、observability plugin surfaces。 |
| `catalog/entries/<kind>.toml` | Case-local catalog entries。 |

## 运行

```powershell
python -m nsgablack project doctor --path . --build
python run_solver.py --check
python run_solver.py
```

## 预期信号（Expected signal）

有效运行应该完成 worker-backed evaluations，能看到 tasks 被 claim 并返回 results；objective quality 不是重点，因为该 case 验证的是 L0 execution semantics。
