# 同一个 Case 的自然循环：两轮 GA → VNS → GA

2026-10-21：这是已接通并实跑的可选模式，使用同一个标准 `hybrid_search` Case。
默认 `phases` 模式和原 elite 模式继续使用各自配置；本次运行文件放在 `results/plan/`。
需要包含 `blackbase.orchestration` 的 BlackBase 0.3.27 开发版本与对应 NSGABlack 源码。

## 用户装配的主体

`adapter/composition.py` 的 plan 分支直接写：

```python
repeat(times=settings.rounds, body=serial(
    stage("ga", steps=settings.ga_steps, label="ga"),
    stage("vns", label="vns"),
    stage("ga", label="return"),
))
```

其中只有一个 GA 实例和一个 VNS 实例。两个 `ga` 位置引用同一个算法所有者，
不会多装一套种群、重建已有 Unit，或在离开本轮 GA 时 teardown 它。
新一轮重置的是本次阶段额度；GA 继续保留原种群和 RNG。

`ga` 阶段有明确的更新额度。`vns` 与 `return` 则等待各自有限池任务实际完成，
没有再按全局 step 推算持续时间。`multi` 也可作为上述结构的子块；
本例实际数据流是串行交接，因此没有为单条精修支路添加无用途的并行包装。

## 每轮处理哪些解

Project 的 `plan` 分组配置种群 6、GA 2 步、精英 2、每项 VNS 2 步、邻域批量 1，重复 2 轮。
普通 GA 选择函数仍先进行 NSGA-II 的约束支配／拥挤度选择，再从最终成员创建或替换 `ga_elite`。

VNS 的 `PoolTaskSpec` 用已有 `select_elite_refs` 读取这个准确公共集合，
冻结当前轮的两个 SolutionRef。两步包括起点重新求值与一次邻域求值。
VNS 分别对两个种子显式重启搜索；这是任务换起点，不是重新 setup 整个 Case。

计划激活身份包含结构位置与轮次，故第二轮精修建立新请求，不会把同名 `vns` 阶段误作已经完成的上一轮任务。
恢复原激活时仍使用原请求与已冻结起点，不重新抽样。

## 交还最终选择，而不是历史提案

GA 的池任务只在 `phases=("return",)` 生效。其它阶段该包装器透传给已有 GA 搜索。
返回来源是一个普通命名函数：

```python
def select_current_refinement_results(control, context):
    del context
    return control.adapter.get_pool_task_results(control, "vns")
```

它只读取本轮已完成、已提交的 VNS 最终结果视图。每轮恰好交还两个最终选择，
由 GA 正常重新 repair、求值和竞争；不会直接覆盖 GA 成员，更不会把精修后的 y 分数写给原 x。

VNS 显式配置 `output="refined"`，用于保留累计接纳历史；最终视图独立发布，设置 `output=None` 也能交还本轮最终选择。
`ga_vns/refined` 在第一轮有 4 个接纳提案，第二轮累计有 8 个；它不是本轮两个最终选择的别名。
第二轮 return 不会重新消费第一轮历史。

## 执行与计数

在本目录执行正式 Project 入口：

```powershell
python run_project.py --group plan --check --build-check
python run_plan_and_report.py
python run_plan_and_report.py --report-only
```

`run_plan_and_report.py` 调用已有 `execute_project`，只额外核对同次正式结果与观察记录。
它没有独立调度算法、手写求解循环或分配资源。Project L0 的实际授权是 1 thread／1 worker／CPU。

真实运行 `20261021T052200Z-b7791e60bf` 的结果为：

- 每轮 2 次 GA 更新、4 次 VNS 更新、1 次返回竞争，合计 14 次逻辑提交。
- 求值为 2 ×（GA 12 + VNS 4 + 返回 2）= 36 次。
- 另一次空尝试只报告计划正常完成；没有第 15 次逻辑提交或额外求值。
- 从源引用选择、读取任务最终结果和游标控制转移都不制造求值。
- 两轮请求身份不同，冻结的精英均等于对应轮 GA 已提交的精英；来源 raw feedback 保持不变。

求解逻辑步上限保留一个额外许可，使完整计划有机会报告正常结束；
这个许可不会使空提案成为 `committed`。详细观察含本轮实际任务 phase 与提交后的游标，
不能用游标已经指向的“下一阶段”反推刚完成的一步。

运行记录：`results/plan/project_result.json`、`trace.json`、`trace.csv`、`summary.json`。
这些观察文件不代替 Authority Snapshot、Evaluation Event 或带权威收据的 Artifact。

## 验证范围

`tests/test_search_plan_project.py` 从这个正式 Project 复制测试工程，验证：

- Project build-check 与真实 L0 执行、两轮准确候选交接、14 次提交与 36 次求值。
- GA 在两轮 GA／return 中始终持有同一个 Unit；返回批次均为 2 个最终选择。
- 第 5 次提交与第 10 次提交的正式 checkpoint 分别从两轮精修中途恢复。
  恢复只执行剩余求值，后续候选数值轨迹与连续运行一致，已有 GA 初始化器禁止再次运行。
- 原 `tests/test_assembled_ga_vns_elite.py` 继续验证默认 population 和 elite 模式。

两个模块同组验证为 6 项通过。恢复第 5 次提交只补跑 21 次求值，
恢复第 10 次提交只补跑 5 次求值；历史引用和已保存观察仍保留，后续新提案正常派生身份。

```powershell
python -m pytest tests/test_search_plan_project.py tests/test_assembled_ga_vns_elite.py -q -o addopts=
```

严格 Doctor 包含 `--build --catalog-audit --profile framework-core`。
整项目检查为 0 error／0 warning／10 info，记录在 `results/plan/doctor.json`；
另复制 Project 并让默认 builder 明确采用相同 plan 小配置，再做实际 plan 装配检查，
同样为 0 error／0 warning／10 info，19 个覆盖项 completed、0 skipped，
记录在 `results/plan/doctor_plan.json`。这避免把默认 Router 的检查冒充 SearchPlanAdapter 已构建验证。

本例验证有限循环、局部任务完成、同一所有者续跑与候选交还。
它不把 Case 内 `multi` 当成进程并行，也不宣称任意无评估 Pool 编辑均已可作为独立阶段执行。
