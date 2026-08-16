# Production Scheduling 解题思路

这份 walkthrough 只保留当前架构下的说明，不再讲旧 single-file demo 路线。

## 边界

`production_scheduling` 是标准 `nsgablack` Case：

- `problem/` 定义生产目标、约束和数据契约。
- `pipeline/` 负责 schedule 初始化、变异、repair、smoothing 和候选流转。
- `adapter/` 负责 greedy、ACO、local/random、multi-agent 等搜索策略。
- `bias/` 负责软偏好和先验信号。
- `plugins/` 负责 progress、export、audit、report 等副作用。
- `build_solver.py` 是 canonical assembly entry。
- `run_solver.py` 是薄 CLI/debug entry。

如果这个 Case 和其他 Case 组合，Project-level 编排和资源 grant 应放在外层 Project。

## 为什么要分层

生产排程难点在于 feasibility 和 tradeoff 高度耦合：

- 机器可用性和产能限制
- 物料消耗和库存流约束
- output、utilization、stability、switching 之间的权衡

框架分层让这些关注点可审计：

| 关注点 | 正确层 |
| --- | --- |
| objectives / violations | `problem/` |
| 可行 schedule shape / repair | `pipeline/` |
| 搜索策略 | `adapter/` |
| 软偏好信号 | `bias/` |
| export、sidecar、profile、report | `plugins/` |

## 当前入口

```powershell
python examples\cases\production_scheduling\run_project.py --check
```

更大的 scenario run 和 baseline 对比见：

- `examples/cases/production_scheduling/README.md`
- `examples/cases/production_scheduling/SCENARIO_MATRIX.md`

## Legacy 说明

`working_integrated_optimizer.py` 可以作为 compatibility wrapper 保留，但新文档和新机制应该使用标准 Case surface。
