# production_scheduling

这是一个遵循统一 **Project -> Case -> Standard Scaffold** 结构的 nsgablack 示例 Project。

2026-11-02 的原数据、装配、导出、取消、预算、恢复与供应嵌套验收见
[完整使用链验收](../../../docs/user_guide/PRODUCTION_PROJECT_ACCEPTANCE_CN.md)。
该报告保留失败尝试，并区分运行层通过与工作区尚待完善的操作体验。

预算原因显示、简易保存/续算与大预算实测见
[checkpoint 与大预算运行](../../../docs/user_guide/PRODUCTION_CHECKPOINT_AND_LARGE_RUN_CN.md)。
完整 `directional` 组现在自动每 10 个提交步骤保存签名 checkpoint；
`run_quality_benchmark.py --groups directional --seeds 42 --run-id NEW --resume PATH`
可在新 Project run 中继续原状态，不重置累计求值。

## 运行

~~~powershell
python examples/cases/production_scheduling/run_project.py --check
python examples/cases/production_scheduling/run_project.py
~~~

默认 Project 配置是可执行的 smoke profile；更大的研究规模应通过 Case 配置或显式组件覆盖启用。

## 完整数据质量实验

先查看计划，再按需要运行正式质量组：

~~~powershell
python examples/cases/production_scheduling/run_quality_benchmark.py --plan
python examples/cases/production_scheduling/run_quality_benchmark.py --groups pilot --seeds 42 --run-id my_pilot
python examples/cases/production_scheduling/run_quality_benchmark.py --groups greedy directional phased aco --seeds 42 43 44 --run-id my_quality_run
~~~

这些组使用同一份真实 BOM 和供应表，保留 22 机种、156 个实际物料 ID、31 天。
物料 ID 最大为 157，因此配置必须使用 `--materials 157` 个槽位；156 个槽位会漏掉 ID 157。
`main/default` 仍是小规模检查；
质量实验必须显式选择。所有求解均通过现有 `run_project.py`、标准 Case 与 Project L0，
每次单 CPU、无 GPU；完整质量组各有 2,500 次求值上限和 900 秒阶段时限，失败保留且不自动重跑。

`directional` 使用具名计划完成 MOEA/D 搜索、方向子池精修及原种群返回竞争。其候选管线采用可行整数解固定点修复，
领域算子负责移量、增产和机种替换；`phased` 保留旧配置作为对照。比较尺度只属于 Adapter，原 Problem 不变。
Greedy/ACO 仍按原单目标策略搜索，但汇总时对所有导出整数排程统一重评原始四目标。

`results/quality/<run-id>/` 保存源文件/数据摘要、正式运行收据、每组日志与导出、`comparison.json`、
`comparison.csv` 及 `recommendations/`。后者分别提供 `production.csv`、`stability.csv` 和 `balanced.csv`，
不默认认为产量最高就是用户最满意。折中推荐采用本次可行候选共同归一化参考上的等权 minimax regret，
参考和分数均写入报告；它是明确的显示政策，不是 Problem 新约束。

整数 CSV、summary 和 audit 针对同一实际交付数值。导出与审计在严格 finalization prepare 期间执行，
失败会阻止成功发布。历史旧版浮点 audit 不能直接当作整数 CSV 的精确指标。

## 调整方向精修时，预算怎么理解

若要判断收益来自初始化、MOEA/D 还是 VNS，使用专门的等预算三组对照，见
[生产排程消融说明](../../../docs/user_guide/PRODUCTION_ABLATION_CN.md)。该实验核对首批 48 个初始解，
使用 pymoo 计算原始四目标的 HV/经验 IGD，并独立记录观察成本，不以运行成功代替效果提升。

完整质量组装配的是同一个 MOEA/D 实例：先搜索 12 步，随机选择它创建的 8 个方向视图，
VNS 对每个方向做 5 步，再把本请求的最终候选交回 MOEA/D 竞争。这里的 5 步包含起点评估，
后续 4 步才是邻域提案。整个过程重复 2 轮；控制切换本身不制造逻辑步骤。

本轮前两组完整方向实验均实际完成 **106 个提交步骤、2,208 次求值**。种群为 48 个方向，
VNS 每批 16 个候选，返回候选也要重新送评；因此一次逻辑步骤不等于一次求值。
正式质量配置提供 256 代全局上限、2,500 次求值上限和 900 秒时限，计划完成后提前结束。
它们分别约束逻辑步、实际求值和墙钟时间，不能互相替代。拒绝尝试会消耗求值与时间，
但不会增加已提交代数。

`--refine-directions 0` 表示选择该 MOEA/D 实例全部方向。若仍是 48 个方向、每方向 5 步、
2 轮，名义计划就约为 506 步；求值需求也会超过原 2,500 次预算。调整方向数、局部步数或
轮数时，应一起检查全局预算。直接用 Case 入口运行方向精修也要显式设置 `--generations`；
上面的 `run_quality_benchmark.py` 命令已提供完整配置。

工作区先导使用较小的同构计划：1 轮、4 步探索、4 个方向、每方向 3 步，名义为 17 步。
网页可设 32 步、180 秒先看完整交接；完整研究使用正式 Project 入口，保留网页快捷试跑边界。

需要改搜索顺序时查看 `cases/production_scheduling/adapter/directional.py`；需要改初始化或领域
变化时查看 `pipeline/neighborhood_search.py`。后者把构造策略、变化和问题可行性修复分开，
可行整数解经过 repair 保持原值。方向比较尺度通过 Adapter 配置，原始四目标仍由 Problem 统一求值。

## 编排边界

搜索 Adapter 的 propose 返回待修复提案，问题 repair 统一在控制面预算裁剪后执行；本地搜索使用独立候选副本，CandidateProposerAdapter 在 repair 后重建对应 Unit。

- **run_project.py**：Project 级统一入口。
- **project_config.py**：阶段、Case 顺序、L0 资源请求和组件覆盖。
- **cases/**：可独立装配、检查并由 Project 调用的标准 Case。
- Project L0 负责资源授权；Case 只消费生效后的 **ResourceContext**。

## Cases

- `production_scheduling`

每个 Case 的算法语义、Problem、Pipeline、Adapter 和 Plugin 组合请查看对应 Case 目录。
