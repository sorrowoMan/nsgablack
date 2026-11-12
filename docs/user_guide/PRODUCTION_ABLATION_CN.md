# 生产排程：把初始化、搜索和精修的贡献分开

## 要回答的问题

已有排程能运行、满足硬约束且能够恢复，并不等于继续搜索有效。本实验只回答：在同一模型、同一批初始解和相同实际求值预算下，继续构造新排程、MOEA/D 搜索、MOEA/D 加 VNS 哪一种取得更好的原始多目标结果。

这是原生产排程 Project 的实验组，不包含外层到料提前决策。BOM 和供应表仍由原 Case 读取，不更改第 0 天库存，也不新增业务约束。

## 三个对照

- `constructive`：每批调用原质量管线的初始化器，独立构造新排程。初始化器本身包含库存感知和均衡操作，因此不是均匀随机矩阵基线。
- `moead`：使用与组合组相同的 MOEA/D 配置和领域变化管线，持续搜索。
- `directional`：MOEA/D 发布方向视图，VNS 按冻结方向进行精修，最终候选返回 MOEA/D 重评并竞争。

三组共享同一种子生成的首批 48 个候选。报告必须同时核对数值摘要和首批原始目标；任一不一致就拒绝宣布对照成立。各组独立的候选身份不会被强行改成相同 token。

## 运行

在仓库根目录使用安装了 pymoo 0.6.2 的 Python。当前工作区已有 `.benchmark-venv`：

```powershell
.benchmark-venv/Scripts/python.exe examples/cases/production_scheduling/run_ablation.py --profile pilot --seeds 42 --plan
.benchmark-venv/Scripts/python.exe examples/cases/production_scheduling/run_ablation.py --profile pilot --seeds 42 --run-id my_ablation_pilot
.benchmark-venv/Scripts/python.exe examples/cases/production_scheduling/run_ablation.py --profile formal --seeds 42 --run-id my_ablation_formal
```

`pilot` 每组 240 次求值，用于验证交接和测量运行成本。`formal` 每组 1,104 次求值，组合组恰好容纳一轮原配方：12×48 次探索、8×(1+4×16) 次精修、8 次返回评估。两种 profile 的搜索编排不同，不能直接拼成一条收敛曲线。

三组顺序运行，均通过正式 Project/Case/L0 授予单 CPU、无 GPU，每组阶段时限 900 秒。预算是实际求值数，不是代数。达到时限但未完成预算的结果不能作为等预算成功对照。运行 ID 必须唯一；当前入口不会自动续跑或重试失败实验。

## 怎样读结果

`results/ablation/<run-id>/run.json` 保存代码、数据摘要、命令、环境和各组结果。只有三组正式发布的观察 Artifact 都通过读取验证，才生成 `comparison.json`。

- `output_gain_after_initial`：相对首批 48 解的最大产量增量。
- `hv_gain_after_initial`：相对同一初始前沿的原始四目标覆盖改善。
- `empirical_igd`：到本次所有组共同观测到的非支配前沿的距离；不是到真实最优前沿的距离。
- `best_daily_cv_at_90pct_common_output`：产量达到同种子共同最好产量 90% 的可行解中，最好的每日产量变异系数。90% 只是明确的报告筛选政策，不是新增约束。
- `unique_numeric_candidates`：帮助识别重复提案，不按数值合并身份，也不退还重复求值预算。
- `case_elapsed_seconds`、`observer_seconds`、`packing_seconds`：整体 Case 耗时与观察插件局部耗时。后两项不能当作全部框架开销；相减也不是裸算法耗时。

HV/IGD 直接调用 pymoo，所有组使用同一归一化尺度和参考点。真实排程没有已知最优前沿，本次观测并集只能作为经验参考；不同报告若尺度或参考集不同，HV/IGD 数值不能直接横比。

这里测量的是所有已提交批次中实际评估过的可行解形成的机会前沿，不是 Adapter 最终保留下来的种群。若搜索发现好解却没有保留，后续应另查环境选择和交付策略，不能用机会前沿掩盖这个问题。

## 验收边界

### 可选的无变化重试

质量管线支持 `--mutation-attempts 1..8`，默认 1 保持原随机调用序列。设为 4 时，一次完整的领域变化若没有改变输入排程，最多再尝试到总计 4 次；首次得到不同排程即停止，不在算子内部调用 evaluate 或 repair。有限重试仍可能返回原解，不保证跨候选去重，也不改变候选身份及预算记账。

算子保存显式 RNG，非默认尝试数纳入 checkpoint 身份，禁止把不同搜索政策的状态直接互相恢复。初始化器不使用这个参数，三组共同初始解仍须验证。

标准消融入口用环境变量将参数传给 Project 中的所有实验组，并记录在 `run.json` 的实际 argv 中：

```powershell
$env:NSGABLACK_PRODUCTION_MUTATION_ATTEMPTS = '4'
try {
    .benchmark-venv/Scripts/python.exe examples/cases/production_scheduling/run_ablation.py --profile pilot --seeds 42 --run-id my_retry4
} finally {
    Remove-Item Env:NSGABLACK_PRODUCTION_MUTATION_ATTEMPTS
}
```

新旧实验各自归一化的 HV 不能直接相减；比较变体须重新建立共同尺度。该选项改变提案分布，不是无语义影响的性能优化。

2026-11-12 的 `ablation_retry4_20261112` 与先前默认 pilot 比较，均为种子 42、240 次求值。首批 48 解及原始反馈一致；独立构造组全部 240 解数值与原始目标逐项一致。重读正式 Artifact 后，以六组共同尺度和共同经验前沿生成 `results/ablation/ablation_retry4_20261112/variant_comparison.json`：

- MOEA/D 不同数值候选从 166 增至 236，但 HV 从 0.510707 降至 0.491170；Case 耗时从 22.56 秒增至 29.24 秒。
- 组合组不同数值候选从 150 增至 190，HV 从 0.482199 增至 0.486753；Case 耗时从 40.44 秒变为 31.24 秒。
- 最高产量均为 76,404，全部硬可行。独立构造组内容完全相同，但耗时从 77.66 秒变为 62.12 秒，说明单次耗时存在环境波动，不据此宣称组合性能提速。

结论：有限重试减少了重复提案，但没有普遍改善搜索效果，保持默认 1。不能用“不同候选更多”替代目标质量验收，也不因这一次实验改全框架行为。后续需要研究邻域覆盖与方向需求的匹配；本次未验证多种子或大预算下的重试收益。

新增重试的输入不可变、可行性、RNG 重放、不同参数恢复拒绝及有限退出测试，与原有方向交接/回滚/checkpoint 测试共 25 项通过。Project 严格 build Doctor 通过；取消/全局预算代码没有改动，本次没有重跑取消故障注入。

观察插件只读取已提交事件里的 raw feedback，不重新调用 Problem，不用 Bias 分数替换原始目标。正式 finalization 发布观察 Artifact，读取时验证发布收据，并对账事件、求值数和预算。未计入观察的失败求值会使对账失败，不会悄悄省略。

这项质量对照不替代取消、预算竞争、事务回滚及 checkpoint 恢复测试；相关工程验收见 `PRODUCTION_CHECKPOINT_AND_LARGE_RUN_CN.md`。单个种子只能说明这一轮现象；结论稳定性需要重复种子。运行期间源码发生变化则拒绝合并结果。

## 2026-11-12 实际验收

运行 `ablation_pilot_20261112` 和 `ablation_formal_20261112` 均完成三组、种子 42。旧的 `ablation_pilot_20261102` 只有一组完成，且 SolutionPool 源码摘要不同，未混入本次比较。

正式组每组 1,104 次求值，初始 48 解的数值摘要和原始反馈一致，全部观察候选硬可行，均以 `evaluation_budget_exhausted` 结束。结果如下（耗时为 Case 耗时，不含全部启动成本）：

- 独立构造：最高产量 77,113，较初始增加 709；HV 增量 0.131655，经验 IGD 0.007663；312.66 秒。
- MOEA/D：最高产量 76,404，较初始增加 0；HV 增量 0.080212，经验 IGD 0.052737；63.56 秒。
- MOEA/D＋VNS：最高产量 76,404，较初始增加 0；HV 增量 0.061973，经验 IGD 0.056842；89.18 秒。

因此本轮不能宣称组合更有效：独立构造在等求值预算下表现最好，但计算成本明显更高；MOEA/D 更快，且确实改善多目标覆盖。组合组没有超过纯 MOEA/D。等墙钟预算和跨种子稳定性还没有验证。

三组不同数值候选分别为 1,104、712、630。重复中包含精修基准和返回竞争的必要重评，不能一律免评估或合并身份。下一项应验证领域变化算子的无变化提案与搜索覆盖，而不是继续盲目扩大原配方代数。

观察插件自身累计耗时分别为 2.54、2.16、2.38 秒，打包约 0.02 秒；这些数字仅描述本次新增观察插件，不能代替全框架性能归因。

收据和共同尺度见 Project 的 `results/ablation/ablation_formal_20261112/comparison.json`。`exports/plan_production_src-SUPPLY.csv` 等文件保留各组正式导出。运行完成后补强了缺组、重复组、预算不一致、初始约束不一致和无可行初值的报告拒绝检查；对已发布 Artifact 重读后，结果与原报告逐项一致。20 项针对性测试通过（含方向交接、回滚和 checkpoint 恢复），Project Doctor 严格 build 检查为 0 error、0 warning、10 info；其 Catalog registry 检查因 Case 无 TOML 而跳过，不代表 Catalog 全覆盖。
