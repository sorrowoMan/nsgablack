# 同步 BO：观测不等于成员

本 Case 使用 `f(x)=(x-0.25)^2`，定义域 `[0,1]`。公共实现位于
`nsgablack.adapters.bayesian_optimization`；本目录只做标准装配。

`build_solver.py` 将真实 Problem、ClipRepair、BO Adapter、可选软 Bias、
CheckpointResumePlugin 和只读报告插件装起来，Project 发放资源授权。

## 实际算法

1. 显式初始点为 `0,1`，真实目标为 `0.0625,0.5625`。
2. 固定 GP 使用零均值、RBF 核、方差 1、长度尺度 0.25、jitter `1e-8`。
3. 网格 `0.25,0.5,0.75` 上最小化 `LCB=mu-2*sigma`，同值按网格顺序选。
4. 首个采集点必须是 `0.5`，原目标为 `0.0625`。默认总共运行 4 个提交步骤、5 次真实求值。

报告 `report.json` / `summary.json` 保存本次实际观测与最后一次网格 posterior/LCB；
同一 payload 在正式 `case_finalization` 事务发布为 `summary` Artifact，Project 保存其权威收据。
本地文件只在成功 finalized 后写出。模型拟合和采集搜索不调用 Problem，也不增加真实评估计数。

## 改装位置

- `adapter/__init__.py`：替换 posterior 模型、采集函数或采集优化器。
- `problem/__init__.py`：真实目标及硬约束。
- `pipeline/main.py`：问题修复。
- `bias/__init__.py`：可选软选择视图；配置 `bias_weight=10` 时模型仍只学习 raw 目标。
- `config.py`：本 Case 的步数、输出路径和检查点频率，不是全局注册表。

模型组件须声明 `component_state_mode="rebuild"`，提供 `describe/spawn/fit/posterior`；
`spawn()` 返回相同解释的新数值缓存。采集函数和优化器首轮只接受显式声明
`component_state_mode="stateless"` 的实现，不能把随机游标或计数状态藏在未恢复组件里。
这些声明是 Python 契约，不是任意副作用的沙箱。

## 完整观测与恢复

完整 Evaluation Event 先于硬接纳产生。BO 从正式 Journal 枚举并经 `inspect_event` 检查，
以 `(run_id,event_id,原行号)` 幂等消费；硬接纳只允许一行进入 update 时，另外已真实评估的行仍可训练。
候选用正式 Adapter 实例路径标记归属，同名两个实例不会混合训练史。
问题修复可以改变候选值和领域 metadata，但必须保留 `bo_owner` / `bo_seed_index` 的算法绑定；
修改或删除这些保留字段会在真实求值之前明确拒绝。

Unit 的每个 Event 只保存一份可传输训练证据值：原 Snapshot payload、原作用域身份和内容摘要；
观测行引用 Event/行号。正式 checkpoint 带走这些值，独立 Python 进程可重建模型。
恢复校验原 `snapshot_content_digest`、Event codec、身份和训练数据对齐，
不会向新 Journal 伪造旧事件，不会把旧 store scope 改成新 scope。
保存时尚未消费的有效 Event 只读携带为 pending dataset，`get_state()` 不拟合、不推进消费状态。

首轮只支持没有任何 EvaluationProvider、没有决定 evaluation 的 Plugin 的 Problem 求值路径。
`individual_fallback` 只是路由标签，不能独自证明真值；注册了仅单点评估的近似 Provider 也会提前拒绝。
尚未提供按行精确/近似收据后的 Provider BO 接入。

暂时不可读的 Event 不推进消费标记，后续重试。原 Snapshot 已归档且仅余 archive binding 的
未消费事件尚无自动读取支持；不会把缺失内容编造成观测。当前严格策略会拒绝同运行中无法验证的损坏 Event，
即使尚无法确定其属于哪个兄弟；有已验证来源的其他兄弟行则正常忽略。

## 验收范围

`tests/test_bayesian_semantics.py` 覆盖独立 GP 数值公式、Bias/raw 分离、修后版本、
部分接纳、预算裁剪、失败后学习 durable Event、精确成员引用、同名实例隔离和真实跨进程 checkpoint。
q-batch 联合采集、真实异步 pending、随机超参数训练、完整约束 BO、Provider 接入和归档历史读取不在首轮范围。

本例是同步 BO 的实际组件验收，不宣称收敛性或优于其他 BO 库。
