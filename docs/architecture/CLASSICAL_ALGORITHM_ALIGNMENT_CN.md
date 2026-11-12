# 经典算法实现补齐与独立核对

## 原因与本轮实际修改

旧 NSGA-III 只实现了“非支配排序后按参考点分散”的骨架：截断前沿局部 min-max、到参考点的欧氏距离，以及从零开始的 niche 计数。它没有完整表达 NSGA-III 的环境选择。这是算法实现缺项，不是 Unit、Pool、事务或组件化导致的限制。

按照 [Deb–Jain 算法定义](https://www.egr.msu.edu/~kdeb/papers/k2012009.pdf)，本轮替换为：

- 在可行群体上维护跨代理想点、极端点与截距归一化；奇异超平面、零跨度均有明确回退。
- 计算到参考方向直线的垂距，关联对象包括已完整保留的前沿与最后待截断前沿。
- niche 数从已保留成员计入；最小占用 niche 随机打破平局，空 niche 优先取垂距最近者，已占用 niche 随机取候选。
- 默认父代选择为约束违反量优先、可行解之间随机配对；用户显式 parent_selector 仍可覆盖。
- 没有直接绑定 initializer 的管线初值同样先经过正常 repair/evaluate/admission，再建立已评估成员。不能在未评分的初始群体上进行 CV 配对。

核心实现只依赖 NumPy，不调用 pymoo。数值退化时的历史 worst-point 截断与小跨度回退明确采用 pymoo 的稳定化策略；这是有说明的数值政策，不宣称所有细节都与原论文唯一一致。

## 状态归属与恢复

`ReferencePopulationUnit.normalization` 保存 ideal/worst/extremes/nadir；没有新增 Solver 权威或 context 大对象。Unit codec、步骤事务和 checkpoint 一起保存它。fresh setup 丢弃旧 Unit，恢复使用 codec，不调用 builder。

ReferencePopulationUnit 正式 schema 升至 v2。旧 v1 checkpoint 缺少归一化历史，明确拒绝混用，不能静默从当前种群重新猜历史。其他 Unit schema 未因此升级。

## 独立核对，而不是两份相同代码互证

`tests/test_classical_algorithm_conformance.py` 包含：

- NSGA-III：随机、常数、共线、目标量纲相差六个数量级、含约束五类场景，三个 seed，每类连续三次更新，对比 pymoo ReferenceDirectionSurvival 的实际选中行与四项历史归一化状态。
- 单独反例保证距离测量指向参考直线，而非参考点坐标。
- NSGA-II：独立 RankAndCrowding 给出排序/拥挤距离截断条件；对无限拥挤距离的边界平局按合法选择集合验收，不错误要求随机平局挑同一行。
- MOEA/D：独立 Tchebicheff 分解器核对标量与替换判定；15 个候选、20 个方向逐项核对。

NSGA-III 的透明性裸参考现在直接由 pymoo 负责生存选择与归一化，数值提案仍用公开声明的相同变化规则。此参考不调用 NSGABlack Adapter、Unit、Solver 或 Pool。它比继续手写同一算法副本更独立，但仍不等同于“默认算子与参数也全部采用 pymoo 的完整算法”。

## NSGA-II 与 MOEA/D 的配置边界

NSGA-II 默认的算术交叉与 Gaussian 变化是装配选择，不是“排序算法缺少一半”。不能将其未经说明称为经典 SBX/Polynomial 默认配方，也不能与另一份不同算子的算法只按同名比较。

MOEA/D 本身已有方向、邻域、理想点、Tchebycheff/weighted-sum 与替换机制。批次送评、nr 限制和 DE/pipeline 变化均须在实验中声明；批量先统一更新理想点与逐子问题即时更新是不同的执行变体，不能混为一份完全相同的参考路径。本轮没有为了凑一致性重写这些既有语义。

## 验收与效果声明

正式运行继续用 `examples/cases/algorithm_transparency/run_project.py --group full` 与 `--group quality`，保留实际评估预算、种群、初值、候选身份、事务与恢复。算法变更后重新生成结果，历史简化实现的报告保留作历史，不修改旧报告来伪装当时已验证新算法。

这些检查能够验证所覆盖的数学步骤和运行轨迹；“达到文献水平”还需要匹配问题维数、算子、方向数、终止预算和充分多的随机重复。结果相同、小型 DTLZ 指标改善或单个种子优胜，都不能替代这项证据。

## 本轮独立整算法实验

新增正式组 `--group classical`，用种群 20、实际评估 400、seed 11/29，对照 pymoo 的 NSGA2、NSGA3 与 ParallelMOEAD。不是只调用其指标或把本仓库的 Adapter 当成参考。

NSGA-II/III 两侧共同使用算术交叉概率 0.9、Gaussian sigma=0.08、clip、禁用去重；NSGA-II 使用 rank/crowding 配对，NSGA-III 使用 CV/random。MOEA/D 明确选择完整并行批、Tchebycheff、邻域 5、delta=1、不限制替换数、DE rand/1/bin（F=.5、CR=.9）。pymoo 侧只用独立提案算子绑定当前方向作为 DE target，理想点和替换由 pymoo 自己执行。所有参考算法也接入父 Case 的控制回调。

两侧初值、种群、方向、变化公式和实际评估预算对齐；独立库的 RNG 消耗顺序、父代抽样方式及合法平局顺序仍有差异。因此比较效果分布，不再要求独立整算法的轨迹逐项相等，也不把 HV/IGD 非零差值自动判成错误。

本轮 IGD（越小越好），依次为框架 / 独立 pymoo：

- NSGA-II / ZDT1：seed11 为 0.33968 / 0.33982，seed29 为 0.26056 / 0.44168。
- NSGA-III / DTLZ2：seed11 为 0.18873 / 0.20241，seed29 为 0.19706 / 0.20901。
- MOEA/D / ZDT1：seed11 为 1.12249 / 1.33402，seed29 为 1.13747 / 0.81187。

这证明独立基线已接通，并提供了可复现结果；不证明统计优胜或文献最佳水平。两个 seed 的 MOEA/D 优劣相反，不能只挑有利 seed。与旧简化 NSGA-III 的 750-eval 对照中，ZDT1 变差、DTLZ2 有改善也有退步：实现定义正确与某小预算下效果最好是两个问题，旧的轨迹一致结论也不能冒充新实现的质量证明。

运行方式：

```powershell
python examples/cases/algorithm_transparency/run_project.py --group classical
python -m pytest tests/test_classical_algorithm_conformance.py tests/test_classical_quality_reference.py
```

机器可读结果位于 `results/test_runs/classical_algorithms_20261102/independent_quality.json`；数学/恢复回归日志为 `results/test_runs/classical_algorithms_verified.log`，最后新增的多目标和独立整算法入口检查为 `results/test_runs/classical_algorithms_last.log`。历史失败和重跑日志保留，不混入成功结果。
