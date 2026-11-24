# 成员维护、步骤事务与子池发布验收

日期：2026-11-24。范围为当前本地 BlackBase、nsgablack 与相关 mlblack 集成测试；没有部署或修改远端服务。

## 1. 原生算法真正复用什么

正式成员的选择、重排和槽位替换继续由 PopulationUnit 的成员操作维护，扩展字段由 member_fields / on_members_changed 定义。
NSGA-II、DE、MOEA/D 的新增验收共用同一份来源标签与出生值维护规则，运行原生 propose/update，核对精确候选引用，并保存、恢复签名文件 checkpoint。
测试同时补出了语义初值与默认数值变化的 metadata 交接缺口：数值计算不应擦除候选的模型解释或来源标签。

待评估提案不属于正式成员：DE 的目标索引/比较基线、MOEA/D 的待处理方向、有限差分的探针字段，按 BatchDisposition 的原始提案坐标投影。
这些 Adapter 现在复用 project_pending_proposals；字段先全部验收，再安装投影值。算法仍负责声明哪些字段属于提案、如何比较及替换成员。
这没有把所有 UnitField 直写都判为错误，也没有要求方向权重、邻域、温度等状态服从行成员操作。

## 2. 一次捕获与不同提交职责

ComposableSolver/EvolutionSolver 联合解析 Solver 与 Adapter 的参与者图，按对象身份捕获一次；AdapterStepTransaction 从原 RuntimeTransaction 转交已捕获范围，不重新保存同一子图。
提交清理或异常回滚只由所属范围执行；共享范围的捕获、回滚、清理次数有专门断言。
临时评估投影的阶段基线集中登记；零接纳先恢复该投影，再调用 repair/disposition 钩子，异常使用完整参与者回滚。

Snapshot 暂存、Pool 的发布 lease、不可撤销求值 journal 仍各自负责值发布、围栏与证据。
它们没有被删成一个通用状态机；本轮统一的是参与者捕获与投影拒绝路径，不能声称持久提交协议已全部合并。
失败前真实发生的求值和预算消耗不回滚。

## 3. 子池来源与草稿可见性

普通 create_subpool 接受显式 created_by 路径；无 Adapter 所属关系的外部集合允许 None。
原生选择、池维护及完整 change 输出创建集合时记录真实 Adapter 实例路径，更新既有集合不篡改创建者。
默认 subpools.all/random 仍选择算法结果或投影视图；选择普通精英集合要显式 kind="candidate_collection"，避免把所有输出集合隐含变成精修任务。

步骤外 initial/accepted 默认公开；mutation/proposal/repair 等草稿仍立即保存，但默认不进入公共选择。
步骤外可显式 publish=True；活跃 attempt 禁止绕过提交强制公开。私有状态经过 checkpoint 恢复仍保持私有。
真实 GA 维护集合、VNS 按创建者选普通集合及文件恢复均有验收。

## 4. 验证入口和证据范围

新增测试：

- tests/test_step_state_unification.py：共享捕获范围、转交校验、零接纳钩子观察。
- tests/test_proposal_state_projection.py：全字段预检、DE/MOEA/D 非前缀接纳映射。
- tests/test_pool_creation_publication.py：私有草稿、创建者、显式集合选择、GA→VNS、文件恢复。
- tests/test_native_member_fields.py：原生 NSGA-II/DE/MOEA/D 共用字段规则及文件恢复。

完整选定回归的执行输出：results/state_unification_regression_final.txt。
本轮该集合为 503 passed、37 warnings，耗时 519.75 秒；警告包括未装配 Pareto 档案、VNS 算子上下文声明等配置提示。
另有成员字段、提案投影及方向视图的 82 项针对性回归通过，输出为 results/state_unification_semantic_final.txt；它与主集合有重叠，不相加当作独立覆盖数量。
MOEA/D 语义读取收尾改为按目标槽位检查，避免对每个后代全表扫描；该最终调整的 21 项针对性重跑全部通过，输出为 results/state_unification_last_refinement.txt。
algorithm_units Project 的 strict/build Doctor 输出：results/state_unification_doctor.json。
该 Doctor 本轮返回 0 errors、0 warnings、16 infos；两个 Case 缺少 Catalog TOML，注册检查以 registry-skip 明确跳过，不代表 Catalog 注册验收。
这些日志是当前工作区运行产物；版本后续变化需要重新执行，不能由测试文件存在推定通过。

没有执行全仓所有测试、全算法数学正确性对照或性能 benchmark；本验收不宣称性能改善幅度或所有算法内部更新均已迁移。
