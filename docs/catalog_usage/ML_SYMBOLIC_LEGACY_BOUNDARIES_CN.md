# 旧符号嵌套路径：可阅读的能力与尚未闭合的正式装配

本页是迁移/边界说明，目录应明确显示“迁移说明”，不把记录计作可直接照跑的完整算法用法。只依据当前源码；没有运行旧算法、实例化数据库或更改核心实现。替代指南已经给出真正的标准Project/Case工厂，而不是建议放开unsafe pickle或私改资源授权。

## mlblack.nsgablack_symbolic.orthogonal_basis_outer · 旧两阶段内层调用未完成标准Case交接

**什么时候用：** 理解历史设计如何以函数池index做外层结构候选、内层拟合参数，再把Stage1基作为Stage2输入。此说明对应OrthogonalBasisOuterProblem、BasisConditionedSymbolicTaskProblem和SymbolicOrthogonalNestedSuite，不表示三者已能作为新统一框架的完整装配捷径。

**先准备什么：** 源码在mlblack/integrations/nsgablack_symbolic的orthogonal_problem.py、task_symbolic_problem.py、builders.py；旧正式外壳位于examples/cases/symbolic_orthogonal_nested。理解FunctionPool index、表达式参数向量、基变换后的输入列是三种不同数据。不存在把A的标量目标随便写回B的原目标这条自动路径。

**放在哪：** 原设计意图是nsgablack外层Problem短路到内层mlblack；按当前AGENTS，内层仍须以独立标准Case、Artifact/result和父派生ResourceContext交付，不能在一个Problem里私开另一套训练装配。

**接入步骤：** 目前不建议直接照旧evaluate_detailed路径装新项目，原因可以精确对到代码：

1. OrthogonalBasisOuterProblem.evaluate_detailed直接构造SymbolicBasisSetRepresentation、OrthogonalBasisEvaluationProblem、Adapter及build_learning_solver，再调用trainer.fit。它没有把这段内层工作交给一个独立标准Case入口。
2. BasisConditionedSymbolicTaskProblem亦直接构造内层表示/Problem/Adapter并fit，分类/区间等分支的Artifact安全交付不能从“fit有返回”推断成立。新固定符号/typed Artifact指南已显式补Problem-owned JSON载荷，旧默认类没有这个hook。
3. 旧示例build_stage1_solver/build_stage2_solver给最终外层Solver传resource_context，但调用build_stage1_problem/build_stage2_problem时未传这个参数。problem/factories.py遂使用cfg.resource_context；配置资源意图不等于本次Project有效grant，不能把这种回退视为完整L0继承验收。
4. SymbolicOrthogonalNestedSuite是Problem bundle，as_spec只是SymbolicOrthogonalNestedPlan描述；它不执行Project、不分配L0，也不自动完成两个Case的Artifact传递。不要把“有plan对象”当作已经跑完两个阶段。
5. 这些旧Problem还持有evaluation_cache/best_record/记录列表和可选PathMemory等状态；仅用可发现性/普通get_state的存在不能证明它们已经参加共享步骤事务、恢复和发布围栏。不能给未来任务默认复用这些隐藏权威。

**怎样判断接对：** 真正闭环应能从外层Evaluation Event追到独立内层Case收据、有效资源grant和确切模型/基Artifact引用；拒绝或恢复不能偷偷再fit。当前本页没有这些执行证据，因此不提供“已接通”结论，也不把source_checked改成executed。

**运行入口：** 此处没有经本轮验收的旧一键嵌套运行命令。可先用 [固定符号/基集合Case](ML_SYMBOLIC_FIXED_APPLICATIONS_CN.md)、[函数池实际消费](ML_SYMBOLIC_FUNCTION_POOL_APPLICATIONS_CN.md) 分别验证表达式与参数语义；需要跨Case时走当前正式Project/Case协议。不能只把旧cfg.resource_context改成更大数字或许可unsafe pickle来绕过边界。

### 可用替代：先把两个阶段拆成独立正式Case

固定结构的基质量评估已由SymbolicBasisSetRepresentation+OrthogonalBasisEvaluationProblem的完整Case表达；后续点/区间/概率参数任务也已有独立正式Case。它们目前是可参考的语义和装配落点，不声称本页已经实现自动Stage1→Stage2桥。下一步核心工作是内层Case工厂注入、数据/基引用精确交付、父授权及事务恢复组合验证，而不是再增一层命名别名。

## mlblack.example.traffic_symbolic_regression · 示例名字与实际算法含义不同

**什么时候用：** 查找traffic_congestion Project中已有的CI数值回归入口。目录key叫symbolic_regression，但当前实现是带截距的**线性系数SGD**，不是搜索符号树、函数池或自定义运算结构。

**先准备什么：** mlblack/examples/cases/traffic_congestion/data/ci_interval_opt_table_no_flow_speed_occ_lag.csv必须真实存在并匹配数值列契约。pipeline/main.py按列排除date、ci、Unnamed:0及test_fold_前缀，目标是ci；不是凭“traffic”名字推断任意排程或图输入。

**放在哪：** Case在examples/cases/traffic_congestion/cases/symbolic_regression，现有build_solver.py里还直接定义CIDirectRegressionProblem；新正式结构应把问题定义放problem/，不能照此把全部实现继续堆builder。

**接入步骤：** 当前源码的真实顺序是CSV→随机train_valid_split→仅训练均值/标准差缩放→CIDirectRepresentation的系数向量→CIDirectRegressionProblem用加截距矩阵算MSE/梯度→gradient.sgd。表示构造时只设置n_features，未显式声明正式dimension；不能把它当已经验收的新ML布局准备范例。

**怎样判断接对：** 它的evaluate只返回训练MSE与梯度，虽准备了验证数组，却没有计算验证指标；读取结果不能编造valid.mse。原Project的symbolic组只启动此Case，default还启动另外五个诊断Case。原始数据按当前随机划分也不是严格的时间外推验证。构造/命名/历史JSON均不能证明符号结构恢复或新接口兼容。

**运行入口：** 保留原入口作为源码参考，但本轮没有运行这个CSV任务。若需求是普通线性CI回归，采用 [完整表格回归Case](ML_TABULAR_APPLICATIONS_CN.md) 的显式dimension/表示/验证/Artifact链，再接真实列；若需求是符号函数，采用 [固定符号Case](ML_SYMBOLIC_FIXED_APPLICATIONS_CN.md) 或 [函数池Case](ML_SYMBOLIC_FUNCTION_POOL_APPLICATIONS_CN.md)。本页不推荐将旧名称解释成已完成的符号回归算法。

### 可用替代：按要解决的任务选择入口

保留线性模型时只替换数据工厂并显式声明训练/验证的业务划分；要找非线性结构时先明确FunctionPool/表达式语法和外层选择规则。两者的参数、预算和结果含义不同，不因同一个目录名而可以直接交换旧checkpoint。
