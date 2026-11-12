# 完整批次 CMA-ES

公共实现为 `nsgablack.adapters.cmaes`，Case 仅装配 Problem、identity 问题管线、三个 CMA 组件、UnitBinding、检查点和结果发布。

默认二维目标 `(x0-0.2)^2+(x1+0.1)^2`，每批真实评估四点，内部选两个重组父代。分布均值没有被评估时不作为候选结果交付。结果为实际评估的最佳候选。

`config.fixture="scalar"` 使用文档的一维解析夹具；`"matrix"` 使用二维固定首批；默认使用真实 RNG。固定夹具仅替代首批标准正态输入，之后仍使用明确保存状态的采样器。

首轮只实现正权重、单目标、无约束 full-covariance CMA-ES。实际改变数值或语义 metadata 的 repair 在求值前拒绝；预算裁剪和硬接纳缺行明确报错，不缩小 lambda。真实评估成本和 durable Event 保留。跨步骤攒齐 cohort 暂不支持。

首版未声明 `pool_input_modes`，不支持把它作为 PoolTask 的 initialize/refine/compete 消费者。所有运行提案、送评版本和已接纳引用仍经统一 SolutionPool；分布均值由显式配置给定，不暗中把普通池成员当作分布或精修任务。

正式运行入口为 `run_solver.py`，Project 中名为 `cmaes_distribution`。`summary.json` 为本地可读报告，正式 Case 还以 finalization transaction 发布 `summary` 收据。checkpoint 每次提交保存，恢复不重跑 Unit builder 或已完成求值。
