# 三种算法的语义验收：同步 BO、CMA-ES 与 MAP-Elites

日期：2026-10-22。

状态：**首版已实现并完成针对性验证。** 本文保留最初的验收判据，并在第 12 节记录实际实现、执行结果和边界；设计中的后续扩展不因首版通过而自动算作已支持。

本文接续 [Adapter 行为边界](ADAPTER_OPERATION_BOUNDARIES_CN.md)、[解池契约](SOLUTION_POOL_CN.md) 与 [运行契约](RUNTIME_CONTRACTS_CN.md)，不另建控制循环、证据日志、资源调度器或通用算法基类。

## 1. 要验证的主张

框架能否承接一种算法，要检查其事实、关系、状态和决策条件能否保持原义。

- 同步 BO：候选、真实观测、模型预测、采集价值分别是什么；模型是否能学习未进入成员集合的真实观测。
- CMA-ES：同一分布产生的整批样本如何共同更新分布；裁剪后是否偷偷更改算法。
- MAP-Elites：描述符如何确定格子；谁拥有每个格子的冠军；不同生成器如何共享档案而不争抢权威。

三项均须经过正常装配、问题修复、预算裁剪、评估接纳、失败回滚和正式 checkpoint 恢复。显式拒绝不支持的组合可以是正确行为，但必须同时有正常运行的正例，不能靠一律拒绝宣称支持。

通过这些案例也不构成对所有算法的表达完备性证明，更不构成收敛性或性能优势证明。

## 2. 先分清四种集合

本文始终区分：

1. 提案集合：本轮希望评估的候选。
2. 已评估集合：真实产生了合法反馈的候选及各次观测。
3. 硬接纳集合：允许进入 `Adapter.update` 的候选。
4. 算法最终成员：Adapter 决策后留下的种群、轨迹或档案引用。

它们可以相同，也可以不同。例如 CMA-ES 评估四个样本、选两个参与均值重组，通常是四个都先进入 update，再在算法内部排名；不能用硬接纳策略提前只交付两个，假装已经完成相同算法。

BO 的训练观测也不能直接取当前成员；MAP-Elites 的新观测可以合法进入 update，却因同格质量较差而不成为冠军。

## 3. 复用的现有正式接口

以下是实际存在的源码接口，不是本文提出的新 API：

- `AlgorithmAdapter.propose/update/on_proposal_repair/on_proposal_disposition`：候选与原始索引对账，见 [Adapter](../../adapters/algorithm_adapter.py)。
- `ProposalRepair`：同时给出 before/after、稳定提案 token 和原提案坐标，见 [修复证据](../../adapters/proposal_repair.py)。
- `OptimizationFeedbackBatch.raw_objectives/raw_violations`：未施加选择偏好的原始反馈，见 [反馈](../../core/evaluation_feedback.py)。**raw 不自动证明其来自精确求值**，近似 Provider 的结果仍须核对来源语义。
- `SolutionPool` 与 `SolutionRef`：候选版本、精确引用、普通集合、提交可见性及保留声明，见 [解池](../../core/state/solution_pool.py)。
- `UnitBinding.build/dump/restore`：算法结构及显式 codec；恢复不调用随机 builder，见 [Unit 契约](../../units/contracts.py)。
- `UnitBackedAdapter`：Unit 按需创建、结构 codec 与步骤快照，见 [实现](../../adapters/unit_backed.py)。
- `evaluation_evidence_journal.list_records`、`Solver.inspect_event`、`Solver.read_evaluation_event_snapshot`：枚举、检查、读取完整评估事件，见 [Solver](../../core/blank_solver.py) 和 [优化证据语义](../../core/evidence_semantics.py)。

`UnitBackedAdapter` 会保存 Unit，不代表自动保存任意 Adapter 属性。其默认 `_get_algorithm_state()` 返回空映射；RNG、模型参数、生成器进度等非 Unit 状态必须由所属者明确导出。不可用 `deepcopy(__dict__)` 补洞。

下文的 BO Unit、CMA 分布 Unit、格子档案 Unit 是职责名称。实际公开类为 `BayesianOptimizationUnit`、`CMAUnit`、`MapElitesUnit`；实际构造器与装配代码见第 12 节，不能把职责名称直接当作 import 名。

## 4. 三个 Case 的装配边界

采用一个标准 Project，包含三个可独立运行的 Case：

```text
examples/cases/algorithm_semantics/
  project_config.py
  run_project.py
  README.md
  cases/
    synchronous_bo/
    cmaes_distribution/
    map_elites_archive/
```

每个 Case 继续使用正式 `build_solver.py`、Problem/Pipeline/Adapter/UnitBinding/Plugin 配置与运行入口。算法实现若进入公共产品面，应落入 `nsgablack` 对应模块，不能全部藏在示例里。

模型、采集函数、采样器、描述符和档案竞争规则可以是普通组件；不要求它们各有一套 Solver/Case。只有确实复用完整内层算法或 ML 生命周期时，才采用正式嵌套 Case。

Project 与运行基础设施归 BlackBase；算法决策归 nsgablack。首轮 BO 使用小型数值模型，不因为出现“拟合”一词就强制引入 ML Trainer；以后接入 mlblack 时只走正式 Provider/Case/Artifact 边界。

初始化、变化、选择、修复仍是行为分类。三个算法保留各自控制顺序，不强制套相同四步循环。

## 5. 同步 BO：先把观测与决策分开

### 5.1 最小正常算例

真实目标为 `f(x)=(x-0.25)^2`，在 `[0,1]` 上最小化。

- 初始真实评估：`x=[0,1]`，`y=[0.0625,0.5625]`。
- 模型：固定超参数的零均值 GP，RBF 核，核方差 1，长度尺度 0.25。
- 数值稳定项明确固定，例如 `1e-8`；首轮不优化超参数，不做隐含归一化。
- 采集规则：最小化 `LCB(x)=mu(x)-2*sigma(x)`。
- 采集搜索范围：显式网格 `[0.25,0.5,0.75]`，同值按网格顺序选择。

模型与采集函数使用冻结的本轮观测版本。下一候选应为 `0.5`；真实结果为 `0.0625`。这个预期由固定 GP 的矩阵公式核对，实施时须独立记录三个网格点的 posterior 和 LCB，不能只断言“算法返回了一个点”。

完成三次真实求值后，模型输入必须为：

```text
X = [0, 1, 0.5]
Y = [0.0625, 0.5625, 0.0625]
```

采集函数评估、模型拟合或网格搜索调用次数，都不增加 Problem 的真实求值计数。

### 5.2 组件与权威

- Pool 保存候选及版本引用。
- 原有 Evaluation Event 保存实际观测证据，不再私建一份事件日志。
- BO Unit 保存训练观测身份、有序训练引用、已消费身份、模型解释与模型版本。
- 模型组件产生 posterior；采集组件消费所声明的模型能力；网格组件搜索采集函数。
- BO Adapter 在下一次提案前显式同步观测，随后拟合并提出候选。

`mu`、`sigma`、LCB 与真实 `f(x)` 各自保留含义。采集函数分数不写回原 Problem 的 raw objective。

可用额外 Bias 把选择视图改成 `f(x)+10*x` 进行反证：模型的 Y 仍必须是上面的 raw 值。

### 5.3 完整观测的消费规则

现有控制面先保存完整评估 Event，再按接纳索引裁剪，最后只把接纳子集交给 update。因此，仅在 update 中积累模型数据，不能通过本项验收。

允许消费的最早时点是 Event 已 durable、身份/内容检查通过，并且求值来源满足该模型的数据策略。首轮在下一次 propose 的同步点读取，避免干预当前 Event 的发布顺序。

成员处置和训练资格独立：

- 拒绝进入种群，不自动取消其合法真实观测的训练资格。
- 缺少持久成员提交而归档为 abandoned，也不自动说明已完成观测无效。
- Event Snapshot 损坏、身份不匹配、真实/预测来源不能区分时，不得伪造可信观测。
- 实施时必须明确训练资格策略；不把所有 abandoned 或所有 raw 值一概收入。

观测身份使用 `(run_id, event_id, 原批次行号)`，同时保留候选 token/版本及 Event Snapshot identity。

现有 Journal 的枚举不是追加日志 offset。不能用“最后时间戳”“最后 UUID”或“已经读过多少条”作高水位；首轮采用已消费身份集合和有序训练引用实现幂等。暂时不可读的事件保留待处理，不能永久跳过。

训练数据和消费身份须一起更新或一起回滚。拟合失败不能只推进消费标记。

### 5.4 修复验收 BO-R

独立注入提案 `x=-0.1`，问题管线修为 `0`：

- Problem 只收到 `0`。
- 观测为 `(0,0.0625)`，不得记录成 `(-0.1,0.0625)`。
- 同一提案的 token 保持；观测绑定修复后的最终版本。
- 即使初始已经评估过 `0`，这次真实求值仍有独立观测身份。
- 修复失败时不调用 Problem，不产生模型训练行。

### 5.5 部分接纳验收 BO-A

从初始两个观测出发，故障注入批次 `[0.25,0.75]`，真实反馈为 `[0,0.25]`，硬接纳策略只接纳第二行。

预期：成员 update 只见 `0.75`，模型同步后却具有四行观测：

```text
X = [0, 1, 0.25, 0.75]
Y = [0.0625, 0.5625, 0, 0.25]
真实求值总数 = 4
```

这项使用显式测试策略隔离硬接纳与学习语义，不把它描述成已经实现了完整约束 BO。

### 5.6 失败与恢复验收 BO-F / BO-C

在 `0.5` 已真实评估且 Event durable 后，使 update 抛错：

- 本步骤成员、决策状态、模型版本和已消费身份恢复基线；generation 不推进。
- 已发生的第三次 Problem 调用与 durable Event 保留。
- 显式继续运行后，下一次观测同步加入 `(0.5,0.0625)` 一次。
- 再扫描不重复加入；读取证据不重跑 Problem、Acceptance 或 Adapter.update。
- Event durable 前失败，不凭“可能已经计算过”自行制造观测。

正式 checkpoint 保存有序观测引用、消费身份、模型配置与已拟合参数、解释版本及 RNG 必要状态。

首轮允许从固定参数和同一观测重建数值缓存；恢复后 posterior、LCB 与下一提案在声明容差内相同。若引入超参数优化或随机训练，须保存额外参数/优化器状态或正式模型 Artifact，不能用“数据和 seed 一样”代替恢复保证。

外部重启要确保训练证据闭包随 checkpoint 可读。仅在当前进程持有 Journal/Snapshot、换进程就丢失的恢复不算通过。归档或回收后的证据读取路径未验收前，须明确限制保留范围，不能静默漏样本。

重复带噪观测作为后续扩展：同一 `x=0.25` 两次测得 `-0.1,+0.1`，须保留两次身份；显式聚合时同时保存样本数、规则和噪声解释。

## 6. CMA-ES：样本批次与分布更新要成套

### 6.1 最小正常算例

二维目标最小化：`f(x)=(x[0]-0.2)^2+(x[1]+0.1)^2`。

初始 `m=[0,0]`、`sigma=0.5`、`C=I`，每轮 `lambda=4`、重组 `mu=2`。固定采样夹具提供标准化样本：

```text
z0 = [-1, 0]  -> x0 = [-0.5,  0.0] -> f0 = 0.50
z1 = [ 0, 1]  -> x1 = [ 0.0,  0.5] -> f1 = 0.40
z2 = [ 1, 0]  -> x2 = [ 0.5,  0.0] -> f2 = 0.10
z3 = [ 0,-1]  -> x3 = [ 0.0, -0.5] -> f3 = 0.20
```

四个样本均进入 update，排序应为 `[2,3,1,0]`。正重组权重按明确配置的 CMA-ES 公式生成，若采用 `log(mu+0.5)-log(i)` 归一化，则：

```text
w1 = log(2.5) / (log(2.5) + log(1.25))
w2 = 1 - w1
m_next = [0.5*w1, -0.5*w2]
```

验收不止检查均值：必须按声明版本的完整 CMA-ES 公式独立核对演化路径、协方差和步长更新，并检查 C 对称正定。固定样本夹具验证更新公式；另用真实 RNG 验证继续运行和恢复。

再用一个可手算的标量夹具核对具体数值：`f(x)=(x-1)^2`，`m=0,sigma=C=1`，两个路径为零；`lambda=4,mu=2`，正权重均为 `1/2`，`mu_eff=2`，`cc=cs=1/2,c1=cmu=1/4,ds=1`。固定 `z=[-1,0,1,2]`，稳定排序的重组父代为 `[1,0]`。首轮预期为：

```text
m_next = 1/2
ps_next = pc_next = sqrt(6)/4
h_sigma = 1
C_next = 23/32
sigma_next = exp(0.5 * ((sqrt(6)/4)/sqrt(2/pi) - 1))
```

此处显式参数用于公式验收，不宣称是默认推荐配置。二维夹具还须验证非对角协方差；仅通过一维不能证明矩阵更新正确。新均值是分布参数，未真实评估时不能作为“已评估最好解”交付。

### 6.2 组件与权威

- Pool 保存采样出的候选，不承担协方差自适应。
- CMA Unit 保存均值、协方差、步长、演化路径、轮次及本轮采样关系。
- 采样器消费冻结分布；排名组件消费本轮合法反馈；分布更新器消费同一批次及同一分布版本。
- Adapter 决定何时开启批次、何时资料齐全并更新。

样本关系至少包含：本地 cohort 身份、源分布版本、提案 token、实际送评版本、采样偏移与原始行号。cohort 是算法本地批次，不另建全局执行器。

CMA Unit 的全局分布状态不能当作每个候选共有的附加字段；`PopulationUnit.member_fields` 也不自动承担分布学习。

### 6.3 修复验收 CMA-R

首轮明确选择严格策略：**结构发生实际候选或语义 metadata 改变时，整批拒绝并报出不支持的修复。** 数值和语义均未变化的 repair 正常放行。

- changed repair 在送评前由 `on_proposal_repair` 拒绝。
- Problem 调用数为 0；分布、pending 和 RNG 恢复尝试前状态。
- 不允许候选修成 x'，仍按旧采样偏移更新分布。

以后若增加修复后重算策略，必须作为明确边界处理变体：使用实际送评点重新解释偏移，并验收 repair 改变采样分布后的更新含义。不能把这项扩展描述成首轮已支持。

### 6.4 部分接纳验收 CMA-A

两条独立反例：

1. 预算只准评估四个中的三个。
2. 四个均完成真实评估，但硬接纳策略只允许其中两个进入 update。

首轮均采用完整 cohort 策略：拒绝残缺分布更新，报告具体缺失的原提案索引。

- 均值、C、sigma、路径和算法轮次不更新。
- 已经发生的真实求值与 Event 保留，不能因为拒绝更新而清零。
- 不能把 lambda 从 4 静默改为 3 或 2，不能把硬接纳当成 CMA 内部的 mu 重组选择。
- 默认结束当前错误路径；是否重试由已有显式运行策略决定，不隐含无限重试。

如果可以在采样前获知不足额度，可提前停止。即使如此，仍需故障注入验证“已经发生截断”的处置，避免只测配置正常的情况。

跨步骤累积一个完整 cohort 是另一种可行设计，但首轮不实现、不宣称支持；它需要单独论证零接纳、暂存与逻辑提交语义。

### 6.5 失败与恢复验收 CMA-F / CMA-C

在更新已经计算、权威提交尚未成功时注入失败：

- 分布所有状态一起回滚，不留下“均值新、协方差旧”。
- 私有候选、池视图与新 Authority 均不对外发布。
- 已真实完成的四次求值保留。

保存正式 checkpoint 后，和不中断运行比较下一批样本、排名及下一轮所有分布状态。除 Unit 数据外，必须核对 RNG、采样器/组件状态及参数解释；不得重新随机构建 Unit。

复用 BO 的完整观测消费者不是 CMA 首轮的必要条件。CMA 按其已声明完整批次规则决定分布更新，不自动把历史失败批次混入新一代。

## 7. MAP-Elites：格子冠军是算法事实

### 7.1 最小正常算例

候选 `x=(x0,x1)`，范围 `[0,1]^2`。质量采用最小化成本：

`f(x)=(x0-0.2)^2+(x1-0.8)^2`。

行为描述符为 `(x0,x1)`，每维按 0.5 划为两格：`[0,0.5)` 和 `[0.5,1]`。越界描述符显式拒绝；上边界 1 属于第二格。

依次真实评估：

```text
A = [0.1,0.1], cost=0.50, cell=(0,0)
B = [0.4,0.4], cost=0.20, cell=(0,0)
C = [0.6,0.4], cost=0.32, cell=(1,0)
D = [0.6,0.8], cost=0.16, cell=(1,1)
E = [0.8,0.2], cost=0.72, cell=(1,0)
```

最终档案必须为 `(0,0)->B`、`(1,0)->C`、`(1,1)->D`，`(0,1)` 为空。A 被替换，E 未成为冠军，但不应因此删除其他消费者持有的 A/E 或真实观测证据。

同质量按明确的稳定先到规则保留旧冠军；批内先到使用原提案顺序。浮点比较容差与 tie 规则要固定，不借字典遍历或随机 UUID 决定。

### 7.2 组件与权威

- 描述符组件：候选/合法反馈到行为坐标，声明其依赖与版本。
- 格子映射组件：行为坐标到稳定 cell key，拥有边界规则。
- 档案 Unit：唯一维护 cell -> champion 精确引用及相关质量/描述符证据。
- 生成器：从档案或允许的工作池选父代，生成提案。
- Adapter：决定调用生成器、消费评估和更新档案。

普通 Pool 子集合可以展示冠军引用；它不成为第二份可写档案权威。不能让一个组件写字典冠军，另一个组件独立维护不一致的“冠军池”。

当前 `ArchiveUnit` 只有 entries；需要明确的格子结构和维护语义才能完成本例。不能仅换个名字便声称已实现 MAP-Elites。

### 7.3 修复验收 MAP-R

独立提案 `[0.49,0.6]`，本场景 repair 将第一维舍入到一位小数，得到 `[0.5,0.6]`。

- Problem 和描述符使用最终 `[0.5,0.6]`，cost 为 0.13。
- 最终 cell 为 `(1,1)`，不能保留修复前的 `(0,1)`。
- 描述符若由实际求值产生，必须在合法反馈到达后再计算；候选依赖缓存也须失效。
- 若领域无法重算描述符，送评前明确拒绝，不将旧描述符绑定到新候选。

### 7.4 部分接纳验收 MAP-A

独立新档案同时真实评估 A/B/C/D/E，但硬接纳仅允许原行号 `[1,2,4]`：

- update 只处理 B/C/E，档案为 `(0,0)->B`、`(1,0)->C`。
- D 即使质量好，也不得绕过硬接纳进入冠军集合。
- E 与 C 在同一格竞争后落败，说明“硬接纳”仍不同于“档案留存”。
- 五个真实评估仍在完整 Event 中，原行号与反馈不能因压缩而错配。

MAP-Elites 此时可以合法更新两个格子，不需要伪造与 CMA 相同的整代屏障。若将来生成器本身是 CMA emitter，该生成器的整批反馈要求仍须独立满足。

### 7.5 失败与恢复验收 MAP-F / MAP-C

在同一尝试更新两个格子后、最终发布前注入失败：档案字典、引用保留声明、冠军集合视图和 Authority 全部保持旧状态；真实求值保留。

正式 checkpoint 保存 cell 划分/描述符/质量规则的身份版本、冠军有序引用、必要反馈及生成器 RNG。恢复后继续同一候选流，最终冠军必须与不中断运行一致。

配置了不同格子边界或描述符版本时恢复应明确拒绝，不能把旧 cell key 套在新解释上。保留引用的闭包必须可读，候选被 GC 后不得悄悄丢一个冠军。

## 8. 三者共同的恢复与组合验收

除每例专有断言外，还需以下共同反例：

- 冷构造与 Doctor 读取不创建 Unit；运行首次需要时创建一次。
- checkpoint 中未创建的 Unit 恢复后仍未创建；已创建 Unit 走 codec，不调用 builder。
- 一次失败尝试恢复算法、绑定组件、RNG 与 Pool，物理尝试数及已消耗预算不回滚。
- 同算法两个实例使用独立 owner path；模型、cohort 和档案状态不共享可写对象。
- Router 中 partial disposition 沿原子提案范围路由，孩子不拿全局行号索引自己的局部状态。
- Case 级恢复使用正式恢复信封；不能仅手动 set_state 后比较某几个数组。
- 检查 Pool manifest 与 Authority 指向同一提交结果；失败和零接纳不泄漏新成员。

第一阶段先做三个独立 Case，再选一次 Router 组合验证身份与处置路由。跨 Case 仍通过正式 Artifact/Snapshot 交接，不默认共享一个可写母池。

## 9. 从初始缺口到本次实现

初始静态阅读发现以下缺口；本次已在独立公共模块补齐并完成首版验证：

- BO：完整事件的幂等消费者及证据保留闭包；训练来源筛选；可恢复模型；采集函数与提案接缝。
- CMA-ES：完整分布 Unit、配套采样/更新组件、完整 cohort 的处置约束。
- MAP-Elites：描述符/格子规则、唯一冠军权威、精确引用与档案视图的事务发布。

已有 MAS 可以参考代理重建机制，但其 update 内训练仅见硬接纳子集；不能直接作为 BO-A 已通过的证据。旧 BayesianGuidanceBias 中的占位 GP、CMAESBias 的距离软评分、ParticleSwarmBias 的引导分数，也不能替代完整算法。

另有独立待修问题：MultiFidelity Provider 混合低/高保真结果却统一声明 equivalent；低保真只是近似时必须纠正。本次未修改这一 Provider。BO 首版明确拒绝已注册的求值 Provider 或启用的评估决定 Plugin，不让它们混入本轮真实训练集。

## 10. 最小实施顺序与退出条件

1. 接通 BO 的正式观测消费者，先完成 BO 正常/R/A/F/C；不同时扩展 q-batch 或真实异步。
2. 完成 CMA 的分布与完整 cohort，默认严格拒绝 changed repair 和残缺更新，记录实际求值保留。
3. 完成 MAP-Elites 的格子档案与普通可替换生成器，验证逐点竞争及精确引用。
4. 形成一个三 Case Project；每个 Case 记录正式装配、有效 ResourceContext、结果和恢复证据。
5. 补一次 Router 局部索引/双实例组合验收，再核对受影响 Catalog/Doctor 声明与实际装配。

每项报告必须分别标明：已实现、已运行通过、明确拒绝、尚未实现。不能用 pytest 用例数量或“最优值变好”代替上述断言，也不以小算例宣称优于成熟算法库。

通过后的结论可以限定为：这三种语义不同的搜索过程，能够复用同一候选、修复、证据、事务和恢复基础，并由实际组件保留各自算法语义。

## 11. 阅读来源

- 框架：本文第 3 节对应当前源码；[运行契约](RUNTIME_CONTRACTS_CN.md)；[联合修复](JOINT_REPAIR_CN.md)。
- 贝叶斯采集函数与模型输入语义：[BoTorch 官方接口](https://botorch.readthedocs.io/en/stable/acquisition.html)。本文固定 GP/LCB/网格是自定验收配置，不是 BoTorch 的运行结果。
- CMA-ES 状态和更新参考：[作者教程](https://arxiv.org/abs/1604.00772)。本文固定二维样本是自定公式核对夹具。
- MAP-Elites 的行为描述与档案语义：[原论文](https://arxiv.org/abs/1504.04909)。本文四格、最小成本与 tie 规则是显式自定配置。

## 12. 2026-10-22 实际执行记录

### 12.1 实现落点

- [同步 BO](../../adapters/bayesian_optimization/)：固定 RBF GP、LCB、网格搜索、完整 Event 消费与可传输训练证据闭包；对应 [Unit](../../units/bayesian.py) 和 [builder](../../representation/bayesian_builder.py)。
- [CMA-ES](../../adapters/cmaes/)：正权重完整协方差采样、排名及分布更新；对应 [Unit](../../units/cmaes.py) 和 [builder](../../representation/cmaes_builder.py)。
- [MAP-Elites](../../adapters/map_elites/)：描述符、格子、冠军竞争、有限/高斯生成器；对应 [Unit](../../units/map_elites.py) 和 [builder](../../representation/map_elites_builder.py)。
- [标准 Project 与实际装配](../../examples/cases/algorithm_semantics/README.md)。

三个 Adapter/组件、Unit 和 builder 均有包级公开导出；新 Adapter 包加入发行包清单。Case 使用标准脚手架，不复制控制面实现。

### 12.2 测试与真实运行

最终集合：`125 passed in 33.31s`，包括 56 项新增验收与 69 项原有回归。

- `test_bayesian_semantics.py`：17 项。
- `test_cmaes_semantics.py`：16 项。
- `test_map_elites_semantics.py`：20 项。
- `test_algorithm_semantics_project.py`：3 项，覆盖构建检查、串行与并行实际运行，以及 sealed summary 收据。
- 原有 proposal repair、Adapter step transaction、checkpoint resume：69 项。

正式 Project run 为 `20261022T013854Z-e7140f2a1b`：BO 四次逻辑提交/五次真实求值；CMA-ES 三次逻辑提交/十二次真实求值；MAP-Elites 一次逻辑提交/五次真实求值。详细数值和证据见 [实际结果](../../examples/cases/algorithm_semantics/RESULTS_CN.md)。

两个 Catalog profile 的严格 Doctor 均为 0 error、0 warning、21 info；33 项 coverage completed、0 skipped，包含三个 Case 的真实构建和本地注册检查。

### 12.3 验收过程中真正发现并关闭的问题

- BO 的 `individual_fallback` 并不能认证真值：逐点路径仍可能选择近似 Provider。首版采用保守拒绝策略并加入反例，而不是凭标签收训练数据。
- BO 以 Adapter 实例所有权路径区分来源，两个同名实例不会因 Unit ID 相同而误用对方观测。
- 第一次求值后失败、Unit 回滚为 None 时，checkpoint 仍只读保留已 durable 的待消费证据；恢复不会残留失败 GP 缓存。
- 修复不得改变 BO 的算法归属/初始化消费标记；普通领域 metadata 仍可变化。
- CMA 的有状态组件不能跨 Adapter 共享，冷装配不创建临时 Unit，完整分布和 RNG 有正式恢复保证。
- MAP 不从空提案推断结束；档案 raw 缓存与精确 Pool 版本交叉校验，内置纯描述符/格子/质量解释也核对一致。
- Root Project 汇总一度将 ArtifactBinding 与 PublicationReceipt 直接比较；已改为核对 binding.publication 和准确 ref，随后串并行测试及报告脚本均通过。

### 12.4 保留的限制

同步 BO 暂不支持联合 q-batch、真实异步、随机模型训练、已归档历史自动读取或跨算法观测共享；模型/采集组件能力按首版范围声明。CMA 不支持 changed repair、残缺 cohort 跨步骤累积或未声明的 PoolTask 输入模式。MAP 的 emit-only 接口不代表已接通自适应 CMA emitter 的批次反馈。专用组件的运行时检查也不等同于 Doctor 已覆盖全部自定义行为。

本次验证支持“这三种具体语义能复用同一基础设施”的结论，不支持算法普遍表达完备性或性能优势结论。
