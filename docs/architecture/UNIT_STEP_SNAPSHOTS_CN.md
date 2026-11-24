# Unit 步骤快照与持久状态

2026-11-02。本轮先处理成员变更通知，再处理内建结构 Unit 的步骤捕获。

## 成员变更通知

PopulationChange 需要一份脱离输入的只读候选、反馈、token、metadata 和 provenance，
并不消费摘要。它现在调用 `_detached_readonly`，保留原闭合 codec、解码及不可写数组/容器，
省去 JSON 摘要计算。没有放开锁、会话或任意第三方对象，也没有修改特征缓存的 `_snapshot/_signature`。

## 两种不同的保存目的

`UnitBinding.dump/restore` 仍定义持久格式。get_state、checkpoint、跨进程恢复和显式 codec
验证继续走这一条，输出可按原格式传输；没有更改 UnitSchema 或要求用户迁移旧 checkpoint。

`UnitBinding.snapshot_step/restore_step` 定义同一执行内的回滚值。内建 StructureUnitBuilder
在持久 dump/restore 均保持原函数与代码时，用带 `step_schema=nsgablack.unit_step/native-v1`
的信封保存声明的 dataclass 字段。捕获时复制原生数值数组，递归脱离允许的数据容器；
恢复时再次复制，并直接构造 Unit 和验证绑定、schema、unit_id，不调用 builder.build。
这样重复恢复同一基线不会受上次恢复后原位修改的影响。

此处没有共享可写 Unit 数组，没有 deepcopy(Unit.__dict__)，不保存特征缓存、锁、executor 或 Provider。
对象数组、含 dtype metadata 的数组、活对象、循环或过深的容器会被拒绝；
dtype metadata 也可能藏有锁或会话，不能随数组 dtype 按引用带进基线。原生步骤信封不是一种新的持久编码。

## 适用范围与兼容

UnitBackedAdapter 已经实现局部 `_snapshot_algorithm_step_state/_restore_algorithm_step_state`
的路径改用新接口，MOEA/D 是本轮正常迭代中的实际消费者。
未实现局部协议的 Adapter 保留原有回滚路径；独立实现状态协议的 VNS 等不会自动被重写。
本轮没有缩小组合 Adapter 的参与者集合，没有改成员替换次序，也没有修改池索引事务。

覆盖了持久 dump/restore 的 builder 自动回退原 codec；实例替换和函数代码修改同样保守回退。
自定义 dataclass 扩展字段在默认结构 codec 下可以直接参与原生步骤捕获，无须另写字段清单。
已有旧步骤信封不带 step_schema，restore_step 会交给原 restore；绑定或格式不匹配直接报错。

## 取消、预算与恢复

控制面 RuntimeTransaction、AdapterStepTransaction、取消检查、BudgetAccount、Journal 和
AuthorityStore 围栏没有改动。原生数组快照只改变 Unit 的捕获表示，不是第二份提交权威。
正常更新后注入错误或 CancellationRequested 的测试继续核对成员/来源/RNG/Authority 回滚，
真实消费保留，后续可以重试。持久 checkpoint 的恢复继续验证原 codec，不读取运行内数组信封。

正确性与性能分别验收。正常迭代探针保留原排程模型和装配，运行八步，实际消费 56 次算法评估
与一次审计；通过逐步 MOEA/D/VNS 变化调用确认进入正常搜索。失败的测量与未知消费记录保留，
不能用失败运行的超时作为加速分母，不能用一次 profile 配对外推长期吞吐。

验收数据见仓库 `results/test_runs/unit_runtime_snapshot_20261102/verification.json`。
