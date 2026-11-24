# 算法抽象透明性 benchmark 契约

## 1. 检验的命题

同一候选、同一算法决策、同一评估预算，经身份、Pool、Unit、事务与证据控制面运行后，应得到相同数学结果；附加成本应能单独测量。算法质量、实现正确性、基础设施成本和恢复分别验收，不能相互替代。

正式入口见 `examples/cases/algorithm_transparency/README.md`。Project/Case 管授权、外层编排和 Artifact，独立数值参考放在 benchmarks。不得改生产模型、降低 repair 标准或关闭事务来赢 benchmark。

## 2. 独立参考

裸路径以数组、标量、队列/标签/档案实现算法循环，不调用 Adapter.propose/update/get_state/set_state，不创建 Solver、Unit 或 Pool。否则同一代码的两层包装不能证明透明性。

数学原语复用必须披露：人口组共享无状态非支配排序/拥挤距离；排序自身的数学正确性需要另证。CMA 更新、GP/LCB、图搜索、档案替换和轨迹更新由参考内核独立计算。

同名算法也可能不同。NSGA-III 已补齐累计理想点、ASF 极端点与截距归一化、参考线垂距、已保留成员的生态位占用和随机平局，默认配对按 CV/随机规则；其参考生存选择改用独立 pymoo 实现，不再维护一份相同的简化内核。归一化归 ReferencePopulationUnit/v2 所有。SPEA2、DE、MOEA/D 的具体选择/聚合/变化参数仍记录在 metadata。数学组件对照与完整运行透明性分别验收；文献水平还须匹配算子和更大的多种子质量实验，不能用小样本通过代替。详见 CLASSICAL_ALGORITHM_ALIGNMENT_CN.md。

## 3. 输入与真实预算

初始化显式固定数值，搜索流镜像正式 RNG 分叉。相同 seed 不充分：初始化绑定也可能消耗随机数。逐次比较实际 Problem 输入/输出，才能发现多消耗随机数、漏评或重复评估。

算法各有适合自己的种群/批/步数定义。有限差分的探针与下降点都计入；代理训练不是昂贵 Problem 调用。两路径采用相同 clip/repair，不能以删 repair 冒充控制面优化。

同时核对真实 Problem 调用和 Solver.evaluation_count，不只相信事件行数或计划代数。人口组种子评估也计入，N 个体、G 次提交共 N×G 次调用。拒绝/取消/等待不产生幽灵提交。

## 4. 语义与质量

逐提交核对候选/种群、反馈、方向/理想点、温度/半径、均值/协方差、标签/档案等真正算法状态；只比最终最优值不够。数值容差固定 rtol=atol=1e-10，不忽略缺字段、不同长度或 None。

HV/IGD 只调用 [pymoo 官方指标](https://www.pymoo.org/misc/indicators.html)。固定版本官方 Problem.pareto_front 生成参考文件，manifest 提供来源、参数和摘要。测量器拒绝篡改、维数不符和非有限反馈，两路径共用固定参考点和参考集，不重写前沿方程或指标。

只测最终可行非支配成员，不用所有历史评估点替代最终输出。单目标、图标签、BO、CMA 和档案 fixture 保留自身状态/效果指标，不人为把一切改成多目标任务。

## 5. 附加成本

记录完整 run 墙钟/CPU、Problem 耗时、装配、RSS 和平台 I/O。人口组分 bootstrap/正常迭代，按提交顺序配对；没有裸分步时序的其他 fixture 明确 unsupported，不从总时间倒推。

measured 只意味着测量完成。是否可接受取决于真实目标耗时和吞吐预算，不能随意规定全算法统一倍数，也不能因 HV 相等忽略百倍耗时。小 trace 诊断包含记录成本与冷启动影响，需重复隔离运行验证稳定性。并行组测隔离与汇合，不混算单线程开销。

默认配对保留身份、Pool、事务、证据，使用默认内存运行后端；SQLite 预算与文件证据的故障测试分开。一个内存数字不证明全部持久化后端零成本。

内部 Solver 的公开 checkpoint_case_runtime 委托同一父 CaseRuntime.checkpoint，复用父级控制 owner、心跳与缓存；完整 run、checkpoint 前缀和恢复后运行均接入。内部 Solver 不另绑定完整 CaseRuntime，不发布独立子 Solver Artifact；其证据保留在本地存储，最终聚合报告通过外层 Case 正式发布。报告明确此测量边界，第三次真实 Problem 调用取消的回归要求剩余批次不再求值。

## 6. 恢复与故障

完整 run 对照 committed-prefix checkpoint → fresh Solver → resume，核对后缀逐次提交、最终状态、求值序列和累计计数；不是把同一字典保存再读回。

故障使用真实 L0、SQLite 预算/证据和文件 Snapshot，在第二次真实 update 后注入 RuntimeError 或 CancellationRequested。算法、权威、公开池应回滚；已发生评估/事件/预算不能撤销。重开持久组件，按 durable evidence 对账，恢复过程不得调用 Problem 或重做接纳决策。

损失预算后的继续搜索不强求等于无故障轨迹，BO 也可能合法保留真实观测。强求相同会错误鼓励擦掉证据。双故障矩阵不等于 journal 每个写点或全部 Provider 异常均被穷尽。

## 7. 组合与覆盖登记

Adapter 串行、多提案、角色、任务和嵌套计划的预期由独立 activation schedule 生成，不调用框架 ExecutionCursor。启用真实精英保留、PoolTask 提交输出和 PoolSearch 停滞恢复，不以全关配置冒充组合。

Project 并行验证两个 Case 的不同进程、各自授权和 Artifact；跨 Case 走正式 invoke，内外身份分开。它们不能用 Composite 合并提案替代。

跨 Case 对照由外层独立裸参考与内层实际 Solver.run 组成：外层请求 bare_inner 的 matrix 模式，子 Case 接受独立授权、完成真实求解并提交报告，再核对框架最终状态、逐提交状态与真实 Problem 调用。bare_inner 的独立裸阶段不替代该内层求解机器验收。

新具体 Adapter 必须进入公开 inventory 并有 PairSpec。抽象、配置和别名不计算法；没有实际报告只能 registered，新出口自动 uncovered。报告须分别保留语义、质量、成本、恢复与故障状态，不用单个绿勾隐藏缺项。

## 8. 未覆盖范围

小型 fixture 为表达、对照和恢复提供证据，不是全部问题域的性能排名。以下需独立实验：

- 所有变化/替换变体，高维、强约束、噪声和大预算多种子收敛。
- 任意部分硬准入、Bias/硬可行性、联合 ProblemRepair/UnitRepair 的全部算法组合。已有专项测试承担部分边界，不能冒称各算法裸参考。
- ML 语义候选、活 StateRef/session 清理、跨后端恢复和真正跨机器分发。
- MOEA/D 投影视图到多种精修、递归子池、动态 Router 条件的全组合。
- 多种数据库/硬盘后端吞吐，以及昂贵 Problem 下的额外成本占比。

扩展应添加可解释 fixture 与公平裸参考，不能扩大 passed 的定义掩盖未测范围。
