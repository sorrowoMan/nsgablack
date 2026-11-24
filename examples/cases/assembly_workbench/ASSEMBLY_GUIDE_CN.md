# 综合 Project 装配详解

本文对应同目录真实代码。先读 [README](README.md) 运行，再对着
[源码读本](SOURCE_CODE_CN.md) 看具体组件。源码读本保存本 Project 的本地组件和装配代码；
共同的框架实现按真实路径索引，不复制整套 Solver、存储或执行器。

## 1. 先把三个“组合”分开

### 1.1 Case 内算法组合

`hybrid_search` 中，GA 与 VNS 在同一 Solver 控制面下运行。
它们共享 Problem、问题 Pipeline、Bias、接纳、预算与 SolutionPool；各自持有 Unit。
这里交接的是候选的精确池引用，不是把 GA 的 PopulationUnit 当成 VNS 的节点结构。

`SearchPlanAdapter` 只决定哪个算法实例现在工作。
`serial`、`multi`、`repeat` 不创建另一个 Solver，不分配 Project lease，也不自己结算求值证据。

### 1.2 Project 组合

`hybrid_search` 和 `directions` 是独立 Case，Problem 含义不同、解池不同、运行身份不同。
它们可并发执行；Project 配置输入 Artifact 与资源。
这里不使用 `Pool.concat` 把两个问题的候选拼起来，也不用某个 Adapter 兼职分配全局资源。

### 1.3 真正的内层 Case

`outer_nested.problem.evaluate(x)` 发出完整 Case 请求，条件为 x。
`inner_response` 在自己的 Problem 下搜索 y，返回自己的求解结果和发布收据。
外层用内层结果计算 x 的目标值，外层候选仍然是 x。

因此“GA 的一个精英交给 VNS，再交回 GA”与“每次评分运行另一个独立优化问题”有不同接口。
本 Project 两种都给出真实实现，避免把“嵌套”一词用在所有组合上。

## 2. 主问题：两种原料怎么配

候选 `x=[a,b]` 是两个原料的投料量。

原始成本定义为：

```text
cost(a,b) = (a-0.85)^2 + 1.6*(b-0.65)^2 + 0.03*(a+b)
0 <= a <= 1
0 <= b <= 1
a+b <= 1.2
```

代码在 `cases/hybrid_search/problem/recipe.py`。
`evaluate` 只返回原始成本；`evaluate_constraints` 返回各条约束违反表达式。
容量属于硬约束，不通过 Bias 惩罚系数去“近似替代”。

另一个偏好是配比不要过分失衡。`BalancedMixBias` 计算 `(a-b)^2`，权重默认 `0.15`。

```text
raw_cost = Problem 的成本
selection_cost = raw_cost + 0.15*(a-b)^2
```

这不是第二个 Problem，也不改变原始约束。
调优算法用的选择评分与对外解释的真实成本在 trace 中分别保存。
directions Case 则不装这个 Bias，它的双目标 Pareto 含义单独成立。

## 3. build_solver 是装配清单

主入口 `cases/hybrid_search/build_solver.py` 只做六类工作：

1. 合并本地配置与标准 component_overrides，生成 HybridConfig。
2. 创建 Problem、问题 Pipeline、Adapter 组合和 BiasModule。
3. 创建 ComposableSolver，并传入 Project 已授权的 resource_context。
4. 设置随机种子、逻辑步骤上限、raw 可行性接纳与求值预算。
5. 按 evaluation_mode 注册可选 Provider，附加检查点与观察／发布校验 Plugin。
6. 应用剩余的正式组件覆盖，返回已装配对象。

算法公式不写在入口里，阶段推进不写在 Plugin 里，Project 并发不写在 Problem 里。
你只改“怎么变异”，应该主要改 adapter/operations.py 和对应绑定；
不应重写 run_solver.py、求值证据、SnapshotStore 或资源授权。

这也是判断入口是否太重的直接标准：它应让你一眼看出实际启用了什么，而不是藏起所有细节。

## 4. 第一个解怎样出现

### 4.1 Pipeline 提供初始值

主 Case 使用 `UniformInitializer(-0.2, 1.2)`。
范围故意稍大，让例子实际触发边界修复。
GA 首次需要成员时，沿 Solver 的初始化入口调用问题 Pipeline。
初始化值登记到运行内 SolutionPool，后续提案修复、求值和接纳使用正式身份协议。

### 4.2 repair 处理问题合法性

`RecipeRepair` 先将坐标裁到 `[0,1]`，如果总量超过 1.2，再按比例缩小。
它不求值、不决定成员生死、不访问 PopulationUnit 的年龄字段。
`validate` 是只读检查，供需要严格共同验收的调用使用。

初始化中的 repair 与送评前提案 repair 是不同入口。
因此本例修复调用次数可以多于 Problem 求值次数；不要仅凭这个计数断言同一提案被错误地重复送评。
trace 将初始化记录、修复计数、实际求值分别展示。

### 4.3 Unit 不是候选编码

GA 需要算法工作结构时才通过 UnitBinding 构建 RecipePopulation。
空 Unit 容器可能先被 ensure；“存在空 Unit”不意味着已经有已评估成员。
完整成员在求值、硬接纳和 GA 的成员选择后才成为 X/F/V/token 对齐的结构。

构建 Unit 不会把 `[a,b]` 编成另一种候选值，VNS 也不会解码 GA 的 Unit。
两个 Adapter 取的是池里的候选，按自己的规则建立或更新结构。

### 4.4 为什么没有另加一个种子 Plugin

本例已经通过 GA 的正规初始化位置消费 Pipeline。
再叠一个准备／恢复／返回控制器，会使同一条示例链多出一套阶段所有者。
Pipeline 负责如何产生合法候选，Adapter 决定何时需要它；Plugin 不接管搜索策略。

若要复现“单解算法先准备一百个种子，再启动多个种群”，应使用已有 PoolSearchAdapter 的专门装配，
见 [解池示例](../solution_pool/README.md)。它与本例的最小 GA bootstrap 是不同使用场景。

## 5. GA 的变化怎样写成普通函数

`crossover_then_mutate(request, *, rng, sigma)` 接收本次正式变化请求。
函数取得两个父候选，生成两个加权交叉结果，再分别加入高斯扰动。
返回 ChangeBatchResult，其中每个 ChangeResult 对应一个独立后代。

```text
parents = 两个父候选
crossed_1 = alpha*parent_1 + (1-alpha)*parent_2
crossed_2 = (1-alpha)*parent_1 + alpha*parent_2
child_i = crossed_i + noise_i
```

它没有直接写 Unit，也没有直接把未评估数组塞进精英池。
控制面为新提案建立身份，repair 保留本提案 token，求值和接纳后才允许发布。

`request.max_outputs` 限制本次还允许返回多少后代。函数按此裁剪，
一次共享计算可以交回多个孩子，但不能超配额或给同一个身份重复结算。

要改成“先变异、再交叉”，只改这个函数里两个操作的顺序。
要把父代改为来自两个已声明池，使用请求的池来源能力并显式装配 parent_selector／change_sources；
不要从共享 context 里偷拿其他算法的候选矩阵。

注意本例使用完整 change，所以不会再隐含追加旧默认交叉或变异。
共享 Pipeline 的 mutator 仍被 VNS 消费；不能因为两个地方都叫变化，就把它们重复执行。

## 6. 生存选择、精英池和 Unit 更新如何接在一起

普通选择函数 `choose_members_and_elite` 的输入是本次调用的 Pool。
它携带待选候选、精确引用、当前选择反馈和合法位置。

本例是单目标，明确按“是否可行、违反量、选择成本”排序。
主结果取 population_size 个成员；随后从这些最终成员中选 elite_count 个。

```python
members = pool.chosen(member_rule, rng=rng)
elite = Pool(parent=members, name="elite")
elite.inject(members.chosen(elite_rule, rng=rng), replace=True)
return members
```

上面只展示本例实际代码的结构；具体 rule 及 partial 绑定见 operations.py。
调用期 `Pool(parent=...)` 是同一作用域的空草稿，inject 声明待提交成员计划。
它不在函数执行到这一行时另开事务，也不立刻让其他算法读到尚未提交的精英。

同一次成员提交包含：GA 选中的主成员、年龄联动更新、精英普通集合的精确替换。
当这次步骤失败，它们按原事务一起恢复；已发生的求值成本不会被抹掉。

这里 `chosen` 决定本次从谁里面选出谁；`inject` 声明把这些引用放入哪个普通集合。
不需要为这个简单的精英思想再增加一个“精英算法 Plugin”。

## 7. 多一个成员字段需要改多少

`RecipePopulation` 继承 PopulationUnit，只增加 member_age：

- 在 member_fields 声明它是按行对齐的成员字段。
- 在 on_members_changed 读取本次变更的 previous_member_indices。
- 老成员按选择轮次增龄，新成员年龄为零。
- validate 检查非负整数。

Adapter 只提交“保留哪些成员或替换哪些槽位”，不用知道年龄怎么维护。
RecipePopulationBuilder 沿用标准纯数据 codec，并显式声明兼容 PopulationUnit 的结构契约。

如果以后增加的是路径代价、方向关联或历史动量，就不能一律按年龄规则拷贝。
同样的成员变化接口负责把真实来源交给字段拥有者；维护规则仍由该 Unit 定义。
“Adapter 不知道字段”不等于“这个字段永远不需要更新”。

## 8. GA → VNS → GA 到底传了什么

每轮局部计划是：

```python
serial(
    stage("ga", steps=2, label="ga"),
    stage("vns", label="vns"),
    stage("ga", label="return"),
)
```

GA 搜索位置每次实际收到接纳反馈才计一次更新。
VNS 位置没有固定 stage.steps，它等当前 PoolTask 的全部起点完成。
默认两个精英、每个起点两次更新，所以 VNS 共四次更新：每个起点基准一次、邻域一次。

`select_elite` 从已经发布的精英普通集合读精确 SolutionRef。
请求启动时冻结本轮输入；暂停、异常重试、检查点恢复不重新抽精英。
VNS 从候选建立自己的当前点与邻域结构，不共享 GA 的成员年龄或写排名。

`select_refined` 读本轮 get_pool_task_results，不把累计 refined 接纳历史当成最终精选。
GA 的 return 位置使用同一个实例，以 mode="compete" 重新求值并运行自己的生存选择。

因此：

- VNS 找到 y，交回的是 y 及其真实引用；不会把 x 的 raw 评分改成 y 的评分。
- y 进入 GA 竞争，不保证一定留下。
- GA 淘汰某个成员，只解除自己的成员关系；其他 Unit、结果视图和历史仍可能持有它。
- 主 Case 保留 refined 历史以便教学观察；directions 用 output=None 演示只交还最终结果。

外层 repeat 只重开位置，不重跑 setup，不重新初始化已有 GA Unit。
等待、控制切换与零接纳都不增加逻辑代。

## 9. Bias、硬接纳和 Provider 分别在哪里

### 9.1 Bias 是软评分

BalancedMixBias 只读候选，返回均衡惩罚。
它既不生成候选、不做禁用，也不直接修改生存成员。
raw_objectives 与 selection_objectives 可在同一成员行对应查看。

### 9.2 可行性接纳读取 raw

FeasibleEvaluationAcceptance 从原始违反量选择允许进入 Adapter.update 的行。
它不读“为了选择而软化过”的违反量。
本例默认问题修复已经把候选投到可行域，所以正常运行中该门主要承担独立验证。
不能把“安装了这条策略”写成“本次一定发生过部分拒绝”。

### 9.3 Provider 替换求值实现

`evaluation_mode="problem"` 用 Problem.evaluate。
`evaluation_mode="provider"` 注册 RecipeProvider：单点／批量都使用同一个配方公式的等价数值实现，
返回原始目标与原始违反量，然后继续进入相同 Bias 和接纳。

Provider 的 can_handle 表示派发前的能力承诺。
它被选中后，不依靠返回 None 自动尝试下一个实现，也不能将错误数值当作成功而期待仲裁器发现。
这里通过两条实际运行路径及公式核对确认等价，不仅看 semantic_mode 的字符串声明。

Provider 不重新定义 GA/VNS 的选择目标；MOEA/D 的投影也不应被这个后端覆写进 raw。

## 10. Plugin 与发布为什么没有塞进 Adapter

主 Case 的检查点 Plugin 按已提交步骤保存，最后检查点在正式 finalization 中发布。
WorkbenchTrace 记录轻量观测，并声明 finalization veto；它在结果公开之前检查权威状态和池引用的一致性。

摘要 Artifact 也进入同一个正式发布事务。
本地 trace 文件在 finalized 后导出，只方便阅读；它不拥有搜索状态，也不能充当下游权威输入。

RecipeRepair 的修复本身是确定性的；它附带的计数只是示例观察数据。
组件提供 get_state/set_state 只有在实际所属 checkpoint surface 接入它时才会生效，
不能仅凭写了两个方法就宣称它已经可恢复。以本例具体 Pipeline codec 和恢复测试为准。

继续搜索的状态包括：Solver 进度、池引用／输入游标、Plan 位置、各 Adapter Unit、绑定组件、RNG、Bias 与有状态 Plugin。
日志、锁、executor 和活 Provider/session 不通过深拷贝对象图保存。

Project 的 `--resume-from` 恢复的是 Project manifest 与已完成 Case；
CheckpointResumePlugin 恢复的是某次 Solver 的算法状态。
当前标准 Case CLI 只有 `--check`，不要凭空给它加上文档里并不存在的 `--resume` 参数。

公开 Python API 的接法如下。resource_context 由宿主授权，output_dir 是原本保存检查点的本地目录；
算法装配保持与保存时一致，先请求恢复，再让正式 run_case 执行统一恢复生命周期：

```python
from blackbase.project import build_case, load_case_builder, run_case


def continue_with_grant(project_root, resource_context, output_dir, checkpoint_path):
    solver = build_case(
        load_case_builder(project_root, "hybrid_search"),
        resource_context=resource_context,
        component_overrides={"config": {"output_dir": str(output_dir)}},
    )
    if not solver.get_plugin("checkpoint_resume").resume(str(checkpoint_path)):
        raise RuntimeError("检查点恢复请求未被接受")
    run_case(solver)
    return solver
```

对应的真实文件恢复测试在 `tests/test_assembly_workbench_hybrid.py`。
从第 8 次提交保存的文件继续，只执行剩余 12 次 Problem 求值，最终累计仍为 36，
最终成员、目标和年龄与连续运行一致。它使用公开 resume，不只在测试中搬运内部 payload。

## 11. MOEA/D 的方向子池怎样变成可装配输入

directions 的原始 Problem 是：

```text
F(x) = [(x-1)^2, (x+1)^2],   -2 <= x <= 2
```

MOEA/D 按方向创建投影视图。每份视图有：

- 原始候选的精确引用。
- created_by：实际 Adapter 实例所有权路径。
- slot：本方向的槽位解释。
- projection：冻结的分解类型、权重与参考点。
- view_id/revision、parent/ancestors：视图身份、修订与派生来源。

默认 Tchebycheff 比较使用 `max_j(weight_j * abs(F_j-reference_j))`。
VNS 起点与邻域沿同一个冻结投影比较；第二层 Pattern Search 继承该解释。
原始反馈仍是两个目标，不会被这个标量替代。

默认串行装配：

```python
coarse_input = subpools.all(moead)
fine_input = subpools.all(coarse)
```

选择器返回装配期的输入计划，到请求开始时才定位该实例已经发布的视图。
`all` 选择的是这个实例的视图集合；不是一个“自动选择最新这一轮”的隐藏过滤器。
本例串行只做一轮，避免在没声明历史视图生命周期时把重复轮次混进来。

`direction_sample=2` 改为 `subpools.random(2, moead)`：抽两个方向视图，每个再取一个起点。
如果两个算法同时对同一候选有成员关系，不会因此改变候选本身身份；各自的比较状态仍独立。

## 12. 换精修算法时，哪些代码真的不用改

本例 coarse 是 VNS，fine 是 Pattern Search。
可以保留 Problem、共享问题修复、PoolTask 的来源与完成语义、最终结果 getter、返回 MOEA/D 的竞争入口和 Project/L0。

需要明确改变的是实际 Adapter 实例、它支持的算子绑定、邻域参数、批次预算与预期求值数量。
VNS 的 mutator/change 入口不等于 Pattern Search 的坐标轮询；后者保留自己的几何结构。

所以“装配一致”指交接协议与职责一致，不承诺所有算法都接受相同的变异函数。
若替换的是 MOEA/D 本身，还要重新检查是否有方向视图生产能力及返回 compete 能力。

`refinement_layout="parallel"` 则让两个精修器从 MOEA/D 的方向分别启动：

```python
serial(stage("moead", steps=2, label="search"), multi(stage("coarse"), stage("fine")), stage("moead", label="return"))
```

它们发布各自的结果视图，汇合后交回两个结果集合的精确引用。
这里没有中间的“fine 继承 coarse”关系，parent/ancestors 与默认串行模式不同。
配合随机抽样时，两份请求独立抽样；不能假设抽中的方向必然相同。
默认 all 才覆盖相同的全部方向集合。

## 13. Pareto、投影分数和单一 best 不能混为一谈

directions 启用 ParetoArchivePlugin，且没有 Bias。
最终 MOEA/D 成员和池原始反馈都按双目标解释；局部精修器的标量只用于它所绑定任务。

多目标 Case 可能同时有一种 incumbent 政策给出的 best，与一组 Pareto 非支配解。
阅读报告时先看 objectives 的维度和 metadata，不把单个 best 当成整条前沿。

主配方 Case 有非零 Bias。若将来在那里也挂 ParetoArchivePlugin，
必须检查插件消费的是 selection 还是 raw，不能直接把带偏好档案称为原问题的 raw Pareto 前沿。
这个工作台通过两个清晰的 Case 分别展示这些语义。

## 14. 真正内外层 Case 的一轮调用

外层候选 x 的条件问题：内层搜索 y，使 `(y-x)^2` 尽量小。
本例为了可核对，内层从 `y=x+0.5` 开始，一次变化将其与 target 的差减半。
默认两次内层求值／提交（基准一次、变化一次）后返回 `y=x+0.25`，内层损失为 `0.0625`。

外层目标为：

```text
outer_score(x) = inner_loss(x) + 0.05*x^2
```

外层 Problem 构造 CaseRunRequest，指定 inner_response、子资源需求、预算与
`inputs={"inner_task_payload": {...}}`，再调用正式 `case_runtime.invoke(request)`。
Inner 的 set_case_inputs 在运行前应用 target，Problem 不通过读取外层共享变量偷取条件。

返回的 CaseRunResult 包含独立 Case 身份、结果、资源、预算与发布证明。
外层先确认成功，再从正式 SolverResult 提取 y 和损失；记录这次调用以供报告。

这是“内层求解结果定义外层评分”，所以给 x 的评分包含 inner_loss 是正确的。
它与同一 Problem 内“局部算法找到了 y，因此把 x 的 raw 目标改成 y 的目标”不同。
如果要替换外层候选，应返回 y 的真实候选身份并走明确的候选交接；本例没有偷偷做这件事。

## 15. 母池、子视图和跨 Case 交接的边界

主 Case：GA、VNS、精英集合和最终结果都在一个 SolutionPool 中。
directions：MOEA/D、两个精修器和多级投影视图也共享自己 Case 的一个 SolutionPool。
outer 与每次 inner 调用：各有独立池。

不能把 inner 的 SolutionRef 直接塞进 outer 的 Pool。它们的 pool_id 和问题解释不同。
跨 Case 要传递正式 payload、Snapshot/Artifact 引用与返回结果；若需导入候选，要按接收问题显式绑定与重新评估。
本例用不同 pool_id、父子 identity 与 child_grant 的实际记录展示这个边界。

删除一个普通精英池或解除某 Unit 的成员关系，也不等于删除候选值。
保留和回收由原引用根与 PoolRetentionPolicy 决定。
本例保留教学轨迹，没有把“视图不复制候选”写成“总存储不会增长”。

## 16. Project 为什么先并行再串行

第一阶段 `searches` 声明 policy="parallel"，max_workers=2。
hybrid_search 和 directions 每个得到一线程、一 worker 的 grant。
L0 总 offer 为四线程、四 worker，使用 SQLite lease 和共享预算。

第二阶段 `nested` 给 outer_nested 两线程、两 worker 的授权，
输入为两上游的权威 summary。内层请求一线程、一 worker，实际权限由父派生，不能自行扩大。

这并不表示外层始终占满两个线程，也不是并行加速比测试。
实际报告用 Case 生命周期时间判断有没有重叠，并核对 outer 的启动晚于两个上游发布完成。

`dag` 分组把三者放进同一个 DAG Stage，仍用同样的 ArtifactBinding 声明依赖。
你不用写“轮询两个文件是否出现”，也不用把 Project Stage 改塞进 Adapter。

两份上游 summary 在这里作为权威比较报告输入。
因为两个上游问题不同，本例不把它们的 best 分数比较成排行榜，也不伪装成 outer 的暖启动候选。

## 17. 正式结果、Artifact 与报告文件

`trace.json` 回答“实际发生了什么”，便于人读，但单靠路径没有发布权威。
`summary` Artifact 是正式交易结果，由运行时发布并产生 receipt。
`ArtifactBinding` 将内容引用与发布身份绑定，Project 下游读取前验证它。

本 Project 已把“写出本地 summary 文件”和“发布可供依赖的 summary”分成两件事。
主 Case 与 directions 在 Solver 的 finalization prepare 中暂存摘要；
两个 nested Case 的包装则在 Solver 生命周期结束后，通过 Case exporter 暂存 summary／nested_report。
最终都由共享 CaseExecutor 封印 Case 产物与发布收据；不另造一个结果存储或例子专用消息总线。

`run_and_report.py` 仅执行正式 Project、读取返回值、验证运行身份并整理报告。
它不在报告阶段重新调用 Problem 冒充求解证据，也不修改候选成员或补跑算法。

默认完整运行的 top-level CaseRunResult 是三份，inner 的多次调用在 outer 的 nested_report 和正式 manifest 血缘中。
四个 Case 定义不等于 Project 顶层列表里必须有四个并列任务。

## 18. 做一个改动时具体编辑哪里

### 18.1 只改问题

改 problem/recipe.py 的成本或约束。
如果可行域变化，更新对应 RecipeRepair／validate；Provider 模式也必须保持同样含义。
不要只改 evaluate 却让等价 Provider 继续计算旧公式。

### 18.2 只改 GA 变化

改 crossover_then_mutate 的操作顺序或计算。
仍返回独立 ChangeResult，尊重 max_outputs、RNG 与来源声明。
主成员选择、池精英、Plugin 和 Project 无需跟着重写。

### 18.3 精英从前两个改成另一种规则

改 operations.py 中 elite 的 chosen 规则。
若基于多目标 Pareto，显式定义比较规则，不默认目标求和。
精英仍来自已选的 members，inject 的事务语义不变。

### 18.4 VNS 想参考另一个池

改 PoolTaskSpec.select，或在普通变化请求中声明额外 donor 来源。
池必须存在、已经发布且可读。字符串名称、创建者选择计划和候选数量是三个不同维度。

### 18.5 只把 fine 换成 SA 或另一种局部算法

先查该实例是否声明支持普通／投影 refine、restart 与最终结果交付。
满足时替换实例并设置自己的参数，保留相同任务和返回形状。
如果算法只支持普通 refine，就不能因为它也接收数组而喂一个方向投影。

### 18.6 将两个精修器改并行

用 refinement_layout="parallel"，同时改变 fine 的来源为 MOEA/D，而不是仍从未完成的 coarse 读结果。
只改 serial 为 multi、忘了调整数据依赖，是很常见的装配错误。

### 18.7 多一个独立搜索 Case

复制脚手架职责与薄入口，写本 Case 的问题和装配。
在 Project 加入 Stage／DAG，并声明资源与 Artifact 输入。
不要复制框架的 Store、图导出器、执行器或整个 case_support 实现。

本地参数也要看具体 Case 的配置契约：hybrid_search／directions 的输出目录是 `config.output_dir`；
两个 nested Case 使用顶层 `component_overrides.output_dir`。
这不是通用字段自动透传，不能把一份覆盖字典不加检查地用于所有 Case。
当前示例保留并明确展示这个装配差异；若要产品化统一输出策略，应在正式 Case 配置协议中收口。

### 18.8 增加真正内层问题

新增独立标准 Case，用 inner_task_payload 表达条件，声明子资源与预算。
把结果留在实际的内层候选上；由外层 Problem 明确解释结果怎样组成自己的评分。

## 19. 哪些内容刻意留到对应专题

本工作台覆盖的是主要装配职责和组合路径，不是每个后端都能通用的“全部开关样板”。

- A*/MOA*：路径、父节点、g/h、标签支配与 repair 重算有专门不变量，见 algorithm_units 示例。
- 梯度／Provider 状态：梯度变换与目标投影不是同一件事；活 StateRef 不能按候选数组复制，见对应 Adapter 契约。
- 严格 JointRepair：ProblemRepair 与 UnitRepair 需要共同验证和 admission 投影；本例只用共享问题修复。
- Unit 级多样性偏好：需要显式参考 Unit 和候选范围，不应把候选级 BalancedMixBias 改名后冒充实现。
- 闲置回收：需要明确消费者保留与结果视图释放；可对照 assembled_pool_recovery，不默认删教学证据。
- 数据库／GPU／远程执行：需要真实后端和授权，不能在 README 声称接通但实际全走本地数值函数。
- ML：Trainer/Provider/DataView/模型 Artifact 属于 mlblack，跨框架示例应继续走两边正式 Case。

这些专题保留同样的 Project／Case 落点和输入输出边界，但不能只用一种通用变化函数代替全部专用协议。

## 20. 运行后应该逐条核对

打开主 trace，确认初始观察没有为了日志创建 Unit，随后出现已评估成员；
年龄数量等于真实成员数；raw 与 selection 的差对应 Bias；repair 确实处理过候选。

确认每轮 VNS 输入对应本轮精英，返回的是本轮最终选择，而不是累计接纳历史。
改变 Provider 模式后，候选与 raw 目标仍一致，实际求值入口发生变化。

打开方向 trace，确认原始目标始终两列，投影只进入任务比较；
serial 的 fine 有 coarse 父视图，parallel 的 fine 直接来自 MOEA/D；结果引用都已提交。

打开 nested_report，确认 outer 与各 inner pool_id 不同；子身份有正确父级，
授权不超过父级，子 summary 有正式发布收据；上游两个输入绑定与生产者发布一致。

最后查看 Doctor coverage 与定向行为测试。Doctor 检查声明和支持的运行面，
不会仅因它通过就证明算法收敛、Provider 数学正确或任意 Python 副作用已经安全。

实际命令、通过数与本轮结果在项目结果记录中追加。

## 21. 增大规模之前先看四种数量

`population_size` 是 GA Unit 的成员容量；`elite_count` 是每轮给 VNS 的起点数；
`local_steps` 是每个起点的更新数；SolutionPool 的历史记录量是随提案和保留规则产生的结果。
它们没有被一个所谓 pool_size 参数绑在一起。

默认主 Case 每轮：2 次 GA 更新 + 2 个起点各 2 次 VNS 更新 + 1 次返回竞争，共 7 次提交。
两轮共 14 次；求值为每轮 `2*6 + 2*2 + 2 = 18`，两轮共 36 次。
起点基准包含在 VNS 的两次更新内，不额外猜成一次隐藏求值。

想配置一百轮时，在 Project 对该 Case 的 component_overrides.config 修改 rounds。
还要核对两级预算：主 Case 的 evaluation_budget，以及 Project L0 的共享 evaluations。
只增大轮数却保留默认预算，框架会正常提前停下；不能据此判断 repeat 少运行了。

directions 的局部算法批次大小不同。Pattern Search 一维轮询可提出两个候选，
所以“更新次数相同”不代表“求值开销相同”。并行变体在一次根提交中可更新两个孩子，
也不能把根提交数乘以两个就当成全局代数。

## 22. 这个例子也暴露了装配成本

核心变化与选择函数很短，仍有三处需要用户明确接线：

1. **状态 codec 的实际拥有者。** 带计数的修复器仅提供 get_state/set_state，并不表示普通 Pipeline 自动保存它；
   本例 RecipePipeline 明确串接初始化器、mutator RNG 与修复观察状态，并验证恢复后的候选轨迹一致。
2. **报告与权威发布。** 一个 Plugin 写出 JSON 不等于下游可依赖；本例显式在正式发布 seam 暂存 summary，
   下游实际验证 ArtifactBinding。这个区别应在正式脚手架里看得见。
3. **带条件的 Case 边界。** 内层需要接 inputs，外层需要接 runtime／Artifact，
   因此两个 Case 有小型边界包装；它们不另写搜索循环或资源分配器。

再加上各 Case 输出目录配置目前不完全一致，这些都是本 Project 可以继续讨论的具体装配摩擦，
不会用“基础设施用户不用关心”把它们隐去。
反过来，正常改变交叉、变异、精英规则、精修算法或 Project 依赖，不要求用户修改核心 Solver 和 Store。

## 23. 本次实际验证记录

执行日期：2026-10-21。保存的完整默认运行：`20261021T063514Z-682447b246`。
完整正式结果、各 Case 观察、子调用报告与摘要均保存在本 Project 的 results/ 和 .blackbase/。

- hybrid_search：14 次逻辑提交、36 次求值；6 个成员、2 个精英，两轮返回；修复观察共 42 次，其中 11 次改变候选。
- directions 默认串行：15 次提交、24 次求值，三方向、VNS→Pattern Search→原 MOEA/D。
- directions 抽两方向：11 次提交、18 次求值；并行精修默认三方向：9 次提交、27 次求值。
- outer_nested：2 次提交、4 次外层求值，触发 4 次独立 inner_response，每次 2 次求值。
- outer 与四个 inner 实例合计五个不同 pool_id，内层 default loss 均可按 0.0625 核对。
- 默认上游 Case 生命周期实际重叠，outer 的启动及权威输入晚于两个上游完成。
- Provider 模式同样 14/36，Problem 实际调用计数为 0；求值预算不因 Provider 而少记。
- 默认与 DAG 两种 Project 依赖、公开检查点文件恢复、预算 11 的部分批次终止均有实际行为测试。

完整测试命令：

```powershell
python -m pytest tests/test_assembly_workbench_hybrid.py tests/test_assembly_workbench_directions.py tests/test_assembly_workbench_nested.py tests/test_assembly_workbench_project.py -q
```

执行记录：首次整组 32 项中 31 项通过；唯一失败是测试把正式不可变元组 provider_names 与列表比较。
修正测试的容器类型假设后，对应 Provider Project 场景单独重跑 1 项通过。
随后新增公开检查点文件恢复场景，单独执行 1 项通过。
当前四模块共 33 个独立场景均有通过记录；未把多次重跑重复计数，也未执行全仓库测试或性能 benchmark。

严格 Doctor 对 default 和 framework-core 两种口径均为：
0 error、0 warning、25 info，40 个覆盖项 completed、0 skipped。
原始记录分别为 `results/doctor_default.json` 和 `results/doctor.json`。

源码读本包含 92 个本地源码／声明文件和框架实现索引，文档中的本地链接已检查存在。
它由以下只读生成命令同步；不构建或执行 Solver：

```powershell
python examples/cases/assembly_workbench/write_source_book.py
```

这些结果验证列出的装配和交接，不把简单问题上的固定预算运行当作性能优越性或任意自定义组件正确性的证明。
