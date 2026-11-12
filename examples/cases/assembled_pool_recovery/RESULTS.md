# SA → 双种群 → SA 恢复 → 返回竞争：实际结果

Project run：`20261019T063031Z-21a4eb4516`。

- 状态：`succeeded`；逻辑提交 `8` 步，实际求值 `29` 次。
- 执行阶段：`['preparing', 'preparing', 'preparing', 'search', 'search', 'recovery', 'recovery', 'return']`。
- 每步求值：`[1, 3, 3, 6, 4, 1, 3, 8]`。
- 最终选择目标：`[0.0]`。
- 最终候选：`[0.052069082548712065, 0.10537616237103889]`。
- 两个独立种群：`{'population_a': 3, 'population_b': 3}`。

本例故意从真实目标的平坦最优区域附近开始，以很小预算复现停滞触发。目标等于零不表示 SA 跳出了局部最优，也不构成算法效果比较。

## 已执行的核对

- 正式结果与轨迹运行身份一致。
- 完整执行 preparing/search/recovery/return。
- 等待阶段不创建种群 Unit。
- 按 raw metric 停滞后唤醒 SA。
- SA 重新加热并先评估起点。
- 两个私有种群保持各自容量。
- 两群初始化提案身份不重叠。
- 正式求值数与提交轨迹一致。
- L0 授权生效。

## 原始文件

- [汇总](results/summary.json)
- [每次提交及精确成员引用/来源](results/trace.json)
- [紧凑 CSV 轨迹](results/trace.csv)
- [正式 Project 返回值](results/project_result.json)

轨迹文件是观察报告，不冒充权威 Snapshot 或 Artifact 收据；完整运行存储位于本地 `.blackbase/`。
