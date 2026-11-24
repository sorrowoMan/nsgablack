# 四个完整 Project：从 GA＋VNS 到方向精修、停滞恢复和真正并发

本文把四种不同的装配放在一起阅读。每个例子都有自己的标准 Project、Case、组件实现、正式运行入口和结果文件。

第一份 [GA＋VNS 全过程详解](assembled_ga_vns/PROJECT_DEEP_DIVE_CN.md) 讲的是一个具体 Project 的完整运行。下面三个新增例子分别覆盖它没有表达的方向投影、池驱动恢复、多 Case 并发。

阅读时请区分三种证据：组件源码说明当前怎样实现；实际运行文件说明这份配置发生过什么；修改建议说明还可以怎样装配。已有一个例子运行成功，不能自动替其他算法的接口、数值性质或所有异常路径作保证。

## 1. 先选你想看的那一种合作

### 1.1 GA → VNS → GA：一个种群怎样让局部搜索精修

- [项目说明](assembled_ga_vns/README.md)。
- [详细源码执行说明](assembled_ga_vns/PROJECT_DEEP_DIVE_CN.md)。
- [项目全部代码](assembled_ga_vns/PROJECT_CODE.md)。
- [真实结果](assembled_ga_vns/RESULTS.md)。

它使用一个 12 人种群，先执行 8 步 NSGA-II，再对这 12 个准确成员逐个执行 VNS，最后由 GA 自己决定如何吸收返回提案。

这一份适合先看 Problem、问题 Pipeline、Unit 成员维护、Bias、Plugin 与 Adapter 怎样分工。它还用 `member_age` 展示扩展字段怎样随成员选择更新。

它没有表达 MOEA/D 的方向含义，也没有同时启动两个独立 Case。

### 1.2 MOEA/D → 粗 VNS → 细 VNS → MOEA/D：任务视图可以继续派生

- [项目说明](assembled_moead_nested/README.md)。
- [项目全部代码](assembled_moead_nested/PROJECT_CODE.md)。
- [真实结果](assembled_moead_nested/RESULTS.md)。

这里的难点不只是“多跑一段局部搜索”。同一个多目标 Problem 在不同方向有不同的比较任务，精修必须以该方向的冻结解释评估起点和新邻域。

粗精修完成后，细精修从粗精修明确选中的结果继续，而不是从聚合集合中随便拿到一个旧起点。

### 1.3 SA → 两个独立种群 → 停滞恢复 → 返回竞争

- [项目说明](assembled_pool_recovery/README.md)。
- [项目全部代码](assembled_pool_recovery/PROJECT_CODE.md)。
- [真实结果](assembled_pool_recovery/RESULTS.md)。

这一份体现“先有存解区域，再让算法从区域中工作”。SA 先产生供后续算法使用的候选，两种种群算法从各自分配的准确引用建立自己的成员。

达到已声明的停滞条件后，恢复轨迹产生新的候选，再交回种群竞争。种群结构没有变成 SA 结构，SA 的温度也不会混进种群成员矩阵。

### 1.4 DE 与 SA 两个 Case 真正并发

- [项目说明](assembled_parallel_cases/README.md)。
- [项目全部代码](assembled_parallel_cases/PROJECT_CODE.md)。
- [真实结果](assembled_parallel_cases/RESULTS.md)。

这是 Project 层并发：两个独立 Solver 各有自己的 Problem、Adapter、运行身份、候选池和授权上下文。

它不是一个 CompositeAdapter 在 Python 循环中依次调用两个 `propose()`，也没有把两个 Case 的池偷偷当成共享母池。

## 2. 四个 Project 共享哪些规则

### 2.1 标准脚手架保持一致

每个 Project 都沿用以下入口关系：

```text
Project
├── project_config.py
├── run_project.py
├── run_and_report.py
└── cases/
    └── 一个或多个独立 Case
        ├── .case
        ├── config.py
        ├── build_solver.py
        ├── run_solver.py
        ├── problem/
        ├── pipeline/
        ├── adapter/
        ├── bias/
        ├── plugins/
        ├── evaluation/
        ├── runtime/
        └── solver/
```

是否真的需要自定义 Bias、Plugin 或 Solver，由例子决定。空包可以保留扩展位置，不能为了让目录看上去丰满就重新实现一遍框架能力。

### 2.2 每个地方仍有自己的所有者

Problem 定义原始评价；问题 Pipeline 处理候选；Adapter 组织搜索；Unit 保存算法结构；SolutionPool 保存准确候选版本；Project 发放资源授权。

算法比较规则可以不同，目录职责不需要随算法名称重排。

### 2.3 同一个单词不应掩盖不同层次

“并行”可能是同一逻辑轮多个算法提出候选，也可能是评估并发，还可能是多个 Case 真正同时执行。这里单独给出了 Project 并发例子，就是为了把第三种行为落实到实际时间区间和授权记录。

“串行”可能只是阶段按顺序启动，也可能是候选通过正式池输入交给另一个算法。只换阶段名字不自动完成候选交接。

“嵌套”可以是同一 Solver 内派生任务视图，也可以是外层 Case 调用完整内层 Case。本次 MOEA/D 的粗细搜索展示前一种，不应被解释成已经运行了多层独立 Solver。

## 3. MOEA/D 嵌套精修：重点看什么

### 3.1 原始目标与方向分数是两层含义

Problem 返回原始目标向量，例如 `F(x)=[f1(x),f2(x)]`。方向任务则根据冻结权重和参考点，形成该次局部搜索使用的标量比较。

```text
Problem 原始反馈：        [f1(x), f2(x)]
方向 i 的比较任务：      scalar_i(F(x), frozen_parameters_i)
```

母池中的原始目标不能被方向标量覆盖。否则同一个候选返回其他方向或其他算法时，已经无法知道它在原始问题上的两个目标分别是多少。

本例的精修使用正式 ObjectiveProjection，而不是另写一个“把 x 的目标强行改成 y 的分数”的桥。

### 3.2 方向数不是精修实例数

MOEA/D 每个方向发布一个视图。一个精修实例可以依次处理多项方向任务；增加视图并不自动增加 CPU/GPU grant，也不意味着为每个方向复制整个 Problem。

`subpools.all(moead_instance)` 选择该具体实例发布的视图。它不是查询所有类型名相同的 MOEA/D 对象。

`count` 再控制每个视图取多少起点。视图数量与起点数量是两层选择。

### 3.3 粗结果怎样成为细任务的输入

粗搜索需要显式声明 output，并由算法的结果接口明确交付最终已评估选择。

细搜索通过 `subpools.all(coarse_instance)` 消费这些最终结果视图。它继承父任务的冻结投影解释，对自己的新反馈应用一次；不是对已经标量化的值再次乘一轮权重。

视图的 parent/ancestors 描述派生来源。它不是一个靠名字斜杠拼出来的普通文件目录。

### 3.4 返回给 MOEA/D 的仍然是候选

细搜索找到候选 y 后，MOEA/D 通过正式 `compete` 输入重新评价和竞争。

“由第 i 个方向触发精修”不承诺“最终只能替换第 i 个槽位”。接收时仍按 MOEA/D 自己当前的方向规则、可行性和替换上限决定。

### 3.5 为什么仍然需要显式阶段屏障

`all()` 选择请求开始时已发布的视图，不负责等待未来将要产生的结果。

所以装配应先确认 MOEA/D 方向就绪，再确认粗任务完成，再启动细任务，最后返回。实际条件与运行轨迹见该 Project 的 README 和结果。

### 3.6 当前选择器的限制也要保留

当前 `SubpoolSelection` 只能直接用于 `refine` 模式。不能把一个种群的 `compete` 输入随便改写成 `subpools.all(refiner)`。

本例返回竞争使用明确的具名输出集合。最终选择视图与集合里的途中接纳提案仍是不同输出，不能在解释中合并。

### 3.7 这份配置的实际运行

原始问题是一维双目标：

```text
f1(x) = (x - 1)^2
f2(x) = (x + 1)^2
-2 <= x <= 2
```

两个原始目标的最优点不同，因此不应给整次运行编造一个唯一的“最佳 x”。加权方向的解析最优点则可以独立推导：

```text
direction_score(x) = w0 * (x - 1)^2 + w1 * (x + 1)^2
x_direction_optimum = (w0 - w1) / (w0 + w1)
```

本例为六个方向分别执行粗、细两层搜索，实际完成 29 次逻辑提交、63 次求值：

```text
bootstrap     2 步， 9 次求值
coarse       12 步，18 次求值
fine         12 步，18 次求值
return        3 步，18 次求值
```

每层每方向只有两步：一次起点基准，一次含两个邻域候选的提案。因此一层是 `6 × (1 + 2) = 18` 次求值。

粗层和细层各产生六个最终结果视图，同时各自聚合十八份接纳提案。细层的最终结果保留冻结的粗层父视图身份；原始反馈仍有两个目标维度。

一个方向上的细搜投影分数约从 `0.00194535` 改善到 `0.000852448`。但另一个方向的最终 x 仍离其解析最优点较远。这是小预算下的实际结果，不能被包装成完整 Pareto 前沿已经收敛。

## 4. SA 与两个种群：重点看什么

### 4.1 “SA 生成种子”不是 initializer 假装运行了退火

实际 producer 是一个有温度、当前点和接受规则的 SA Adapter，它通过正式求值和提交产生候选。

后续种群拿到的是已经登记的准确引用。接收方仍按自己的正式初始化、修复、评估和选择路径建立成员。

### 4.2 配额、成员容量、历史池数量各自配置

PoolSearchSpec 的 `initial_count` 描述分给某个搜索者多少初始引用；该算法自己的 population_size 描述希望保留多少成员。

二者不必在整个框架中被强行统一成同一个 `build_solver(config={"population_size":...})` 参数。

两个种群可以有不同算法和不同容量，仍使用同一套输入版本和提交协议。

### 4.3 为什么选 NSGA-II 和 SPEA2

两者具有正式 `initialize` 和 `compete` 输入能力，能够表达“建立成员，然后接收外来候选参与生存竞争”。它们保留各自的环境选择规则。

这里没有把第二个搜索者直接换成 DE。DE 的 target/trial 配对与任意外来候选竞争不是同一个契约；当前 DE 不声明通用 `compete`。

### 4.4 停滞是明确的运行条件

应读装配里实际声明的 metric、stagnation_steps 与 recovery_steps。

连续若干步在这个 metric 上没有改善，不等于数学上证明所有邻域都不存在更优解。小演示中的恢复触发也不能冒充一般局部最优检测器。

结果报告应让读者看到真实阶段变化，而不是只列一个名为 recovery 的配置字符串。

### 4.5 恢复轨迹和返回竞争分别解决什么

恢复阶段回答“从选中的起点继续搜索，产生哪些新的已评估候选”。返回阶段回答“各个种群按自身规则怎样采用这些候选”。

恢复期间不会把所有种群转换成一个 SA Unit。返回也不要求两个种群保留相同成员。

### 4.6 本例特意使用真实平坦目标

原始问题是：

```text
f(x0, x1) = max(0, x0^2 + x1^2 - 1)
-2 <= x0, x1 <= 2
```

单位圆内部的目标都为 0。初始化范围位于这个最优平坦区域中，小变化也可以继续留在平坦区，所以“最好的 raw metric 没有改善”是一个真实可观察的条件。

它展示恢复机制怎样被触发，但不证明 SA 跳出了次优局部极小，更不证明恢复后目标质量提高。本例起点本来就可以达到目标 0。

### 4.7 这份配置的实际运行

运行按下面的顺序真实完成八次逻辑提交：

```text
preparing, preparing, preparing,
search, search,
recovery, recovery,
return
```

每步求值增量为：

```text
1, 3, 3, 6, 4, 1, 3, 8
```

合计二十九次求值。三个准备步骤产生七份接纳候选，两个种群各分配三个起点，分别建立三人种群。下一步两个种群各提出两个后代。

停滞计数达到配置阈值后，SA 重新加热，并先对所选恢复起点评估一次；下一步产生三个邻域候选。返回时，四份恢复提案分别进入两个种群竞争，因此最后一步是八次求值。

第八步实际执行的是 `return`。提交后控制状态已经为下一轮回到 `search`，随后本例因步骤预算停止。所以 JSON 中 `final_phase="search"` 与实际执行过返回并不矛盾，应该同时看 `executed_phase` 和提交后的 phase。

最终两个种群都保持三名成员，最好原始／选择目标均为 0。这个结果证明固定演示配置中的准备、分配、停滞、恢复和返回路径闭环，不证明恢复带来了目标改进。

## 5. DE 与 SA 跨 Case 并发：重点看什么

### 5.1 这是两个运行身份，不是同一个算法的两个角色

Project 创建两个标准 Case 请求。每个 Case 构建自己的 Solver，并绑定自己的资源授权。

一个 Case 使用 DE 的差分供体、交叉和 target replacement；另一个使用 SA 的当前点、温度与 Metropolis 接受。它们不需要共用 Unit 结构。

### 5.2 Project 决定并发，Adapter 不申请线程

并发声明位于 Project 的 stage 策略和 max_workers 等配置。

每个 Case 的生效 grant、命名空间与资源绑定应从正式返回值读取。`n_units=2`、两个子池或两个 Unit，都不能替代这个过程。

### 5.3 并发证据怎样读

设两个正式 Case 的开始与结束区间分别为：

```text
A = [start_A, end_A]
B = [start_B, end_B]
```

区间交集长度为：

```text
overlap = max(0, min(end_A, end_B) - max(start_A, start_B))
```

正交集说明这次两个 Case 的运行区间重叠。它不能单独证明每个瞬间都在同一时刻执行 Python 数值指令，也不能替代 CPU 利用率或吞吐量测量。

本例不通过人为睡眠伪造并发重叠；实际开始、结束和授权来自正式 Project 结果。

### 5.4 独立并发不会自动融合候选

两个 Case 各自有自己的候选池。这种形式适合独立实验、不同任务并行或后续通过正式 Artifact 依赖衔接。

如果要让一个算法的候选成为另一个的输入，需要额外声明正式交付；把两个 Solver 内存里的 pool_id 直接当成同一个地址空间是不成立的。

### 5.5 这份配置的实际运行

DE Case 求解：

```text
f(x) = (x0 - 1)^2 + (x1 + 2)^2
已知最优点 [1, -2]，最优值 0
```

本次完成 16 次提交、192 次求值，最好候选约 `[1.02691, -2.09629]`，目标 `0.00999604`。

SA Case 求解另一份各向异性二次函数，已知最优点 `[-1.5, 0.75]`，最优值 0。本次完成 40 次提交、40 次求值，最好候选约 `[-1.42258, -0.04914]`，目标 `2.56046477`；该短预算运行没有接近精确最优点，不应写成已经充分收敛。

两个 Case 各自获得 `threads=1`、`workers=1` 的授权，有不同的 lease、namespace 和 Case run ID。保存结果中的正式生命周期区间重叠约 **20.654 秒**。

因为两份问题、预算与算法都不同，这些数值不构成 DE 比 SA 更好的实验结论。这里验证的是标准 Project 的真实并发、独立状态和授权绑定。

## 6. 每个组件的代码在哪里

各 Project 的 `PROJECT_CODE.md` 包含该 Project 全部 Python 源码和必要配置，按真实文件生成，并保留原始文件 SHA256。它是阅读快照；修改程序要编辑真正的源文件。

框架已有算法不会被复制成第二份 Case 实现。对应完整源码包括：

- [NSGA-II](../../adapters/nsga2/adapter.py)。
- [SPEA2](../../adapters/spea2/adapter.py)。
- [MOEA/D](../../adapters/moead/adapter.py)。
- [VNS](../../adapters/vns/adapter.py)。
- [SA](../../adapters/simulated_annealing/adapter.py)。
- [DE](../../adapters/differential_evolution/adapter.py)。
- [StrategyRouterAdapter](../../adapters/multi_strategy/adapter.py)。
- [PoolTaskSpec 与 PoolTaskAdapter](../../adapters/pool_tasks.py)。
- [PoolSearchSpec 与 PoolSearchAdapter](../../adapters/pool_search.py)。
- [SolutionPool](../../core/state/solution_pool.py)。
- [Unit 数据结构](../../units/collections.py)。
- [Adapter 直接行为绑定](../../adapters/operations.py)。
- [ComposableSolver](../../core/composable_solver.py)。
- [正式 Project 入口](../../project/project_runner.py)。

每个 Project 的 README 还指向自己的问题、Pipeline、Adapter 装配和报告组件，方便把源码和运行结果一一对应。

## 7. 怎样重新运行

先确认本机能导入与这些例子匹配的 nsgablack 和 BlackBase 开发版本。当前工作区中的新 API 不应被假定存在于任意旧发布包中。

每次进入对应 Project 目录，先检查正式装配，再运行并生成报告：

```powershell
python run_project.py --check --build-check
python run_and_report.py
```

例如方向精修例子：

```powershell
Set-Location "C:\Users\hp\Desktop\nsgablack\examples\cases\assembled_moead_nested"
python run_project.py --check --build-check
python run_and_report.py
```

仅运行标准 Project 时使用 `python run_project.py`。不要因为额外报告器调用了 execute_project，就把它误认为一个私有求解循环。

单独 Case 的 `run_solver.py --check` 可以用于装配调试；它不自动执行 Project 的 L0 分配和全部跨 Case 调度。

## 8. 结果文件各自证明什么

正式 Project 返回值提供 Case 身份、状态、Solver 输出、资源绑定和 Artifact 引用等信息。

轻量 trace 用于看阶段、Unit、视图或提交计数；它不是另一份权威候选池。

`summary.json` 与 `RESULTS.md` 是本例报告代码从正式结果和观察中整理的派生说明。对解析目标的独立重算应明确标注，不冒充从 durable raw evidence 中提取的值。

Doctor 检查组件结构、声明和受支持的构建／运行表面。`--build` 真正调用 builder，`--catalog-audit` 是否启用要看命令与 coverage；不能把零错误解释成算法数学性质已证明。

本次新增三份 Project 均已执行正式构建检查、真实运行和包含 `--build --catalog-audit --profile framework-core` 的严格 Doctor。保存结果分别为：

- [方向嵌套精修 Doctor](assembled_moead_nested/results/doctor.json)：0 错误、0 警告。
- [池驱动恢复 Doctor](assembled_pool_recovery/results/doctor.json)：0 错误、0 警告；另有 [default 口径对照](assembled_pool_recovery/results/doctor_default.json)。
- [多 Case 并发 Doctor](assembled_parallel_cases/results/doctor.json)：0 错误、0 警告；实际命令和覆盖范围保存在 [validation.json](assembled_parallel_cases/results/validation.json)。

每份 Case 的本地自定义组件也已登记为 Catalog 条目。正式运行结果来自本次实跑，源码快照和组件索引在代码冻结后生成，并与原始字节摘要核对。

这些 Project 没有进行相同问题、相同预算下的多种子性能对照，不能直接用它们的目标数值或墙钟时间排列算法优劣。

## 9. 怎样判断你想表达的新组合应该放哪

如果只是多个算法在同一运行中使用和交换候选，先看 Router、PoolTask、PoolSearch 和各算法明确支持的输入模式。

如果需要多个完整求解器或训练器独立运行，先看 Project/Case。跨 Case 的结果应走正式结果与 Artifact 交付，不依赖另一个 Case 内部 Python 对象。

如果只是换某算法的初始化或变化方式，先看该实际叶 Adapter 的 operation_methods 和直接组件绑定，不必重写整份问题 Pipeline。

如果新增算法结构关系，先定义 Unit 的字段、操作、有效性与 codec；不要因为目录里已有 context 就把一切塞进共享字典。

如果修改的是评估含义，改 Problem 或正式 Provider；如果只是软偏好，保留原始反馈再使用 Bias；如果只是运行观察，使用声明清楚的 Plugin。

这四份 Project 共同展示的是：**同一套标准脚手架能够容纳不同的算法结构、候选交接和执行拓扑，同时保留各算法自己的比较规则。**
