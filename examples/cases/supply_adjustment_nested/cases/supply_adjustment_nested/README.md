# 供应调整 Case

本 Case 的正式 Project 用法和预算见[Project 说明](../../README.md)。

装配入口为 `build_solver.py`，实际连接如下：

1. 生产 Case 的公开数据加载器读取原 BOM、SUPPLY，记录 SHA256。
2. Pipeline 创建整数提前天数候选；`SupplyShiftRepair` 在评估前落实逐事件日期和最多移动事件数，Day 0 双向固定。
3. 外层 NSGA-II 提案；`CaseInnerRuntimeEvaluator` 从已绑定 provenance 取候选 token，按修复后的整数向量生成版本化生产任务。
4. 正式 `production_inner` 子 Case 取得父级派生授权、独立预算、取消和隔离终止契约，运行原 phased MOEA/D + VNS。
5. 外层验证封存的 `production_summary`，形成原三目标；反馈携带轻量收据，存入同一精确 SolutionRef 的 Snapshot。
6. `JointSupplyCase` 导出最终结果时只读取 incumbent 对应的唯一 accepted 版本，发布 `joint_summary`，不额外重跑优化，也不猜相同数值的身份。

## 指定候选复核

`component_overrides={"argv": ["--evaluation-only", ...], "candidate": [...合法整数提前天数...]}` 可只评估一个明确候选。未指定 candidate 时使用零调整。

跨阶段复核使用 Project `input_artifacts` 声明 `candidate_plan`，绑定上游 `joint_summary`。仅 evaluation-only 装配支持该输入；运行前验证收据、源文件 SHA、候选维度、今天库存与物料守恒。可以更换内层 seed/预算，保持供应问题一致。全组配方已在 Project config 中给出。

## 边界

候选数、种群容量、内层逻辑步数与原始求值预算分别配置；达到步数不表示用完原始求值预算。实际次数写入子 Case 摘要。VNS 第 6 步只评估起点，至少运行到第 7 步才有邻域变化，不能只凭它在装配图中存在就声称已精修。

`Problem.evaluate` 在缺少正式内层求值路径时明确失败。旧直接 callback、cheap supply-sum proxy、blacklist 研究入口与专用 Redis candidate-worker 不属于这条正式实现路径；其历史运行不能充当本轮结果。
