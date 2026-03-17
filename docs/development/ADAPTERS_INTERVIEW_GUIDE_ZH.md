# `nsgablack` Adapter 全量复习文档

> 面向面试复习 / 框架理解 / 二次开发。
>
> 本文基于仓库当前真实源码整理，核心参考文件包括：
>
> - `adapters/algorithm_adapter.py`
> - `adapters/__init__.py`
> - `core/composable_solver.py`
> - `core/evolution_solver.py`
> - `adapters/*/adapter.py`

---

## 1. 先记住：Adapter 在这个框架里到底是什么

在 `nsgablack` 里，**Adapter 不是“一个算法函数”**，而是一个正式的运行组件。

它的职责不是包办一切，而是专门回答两个问题：

1. **`propose()`：下一批候选解从哪里来？**
2. **`update()`：拿到评估结果后，内部算法状态怎么更新？**

这意味着：

- `Solver` 负责生命周期、评估入口、插件、snapshot、context
- `Representation` 负责初始化、变异、修复、编码/解码
- `Adapter` 只负责**搜索策略本体**

这是这个框架和很多“一个大 solver 类全写完”的代码库最大的区别。

---

## 2. Adapter 在框架中的落地链路

核心代码在 `core/composable_solver.py::ComposableSolver.step()`。

一轮标准调用链是：

1. `solver.build_context()` 构造运行时 context
2. `adapter.propose(solver, context)` 产出候选解
3. `solver` 对候选解统一做 `normalize`
4. 若存在 `representation_pipeline`，统一走 `repair`
5. `solver.evaluate_population(population)` 统一评估
6. `solver._update_best(...)` 更新全局 best
7. `adapter.update(solver, candidates, objectives, violations, context)` 更新算法内部状态

也就是说，Adapter **不直接主导评估**，也**不直接主导插件生命周期**。

它主要做的是：

- 读 solver 当前状态 / snapshot / context
- 生成候选
- 吃回评估反馈
- 维护自己的“算法态”

---

## 3. Adapter 通用接口契约

基础类在 `adapters/algorithm_adapter.py::AlgorithmAdapter`。

### 3.1 最小契约

- `propose(self, solver, context) -> Sequence[np.ndarray]`
- `update(self, solver, candidates, objectives, violations, context)`

### 3.2 常见可选能力

- `setup(self, solver)`
- `teardown(self, solver)`
- `get_state()` / `set_state()`：用于 checkpoint / 恢复
- `set_population()` / `get_population()`：允许 runtime 插件或 snapshot 回写群体状态
- `get_runtime_context_projection()`：向外暴露关键运行态
- `get_runtime_context_projection_sources()`：标记这些字段由谁写出

### 3.3 为什么这个接口设计适合工程

因为它把“算法逻辑”和“运行框架”拆开了：

- 算法可以替换
- `Solver` 可以稳定
- 插件和 checkpoint 可以围绕统一接口工作
- 多种算法可以被控制器再组合

---

## 4. 复习时建议先按类别记，而不是按文件名死背

这个仓库里的官方导出 adapter 在 `adapters/__init__.py` 中包括：

- `RoleAdapter`, `RoleRouterAdapter`
- `VNSAdapter`
- `MOEADAdapter`
- `SimulatedAnnealingAdapter`
- `StrategyRouterAdapter`
- `AStarAdapter`
- `MOAStarAdapter`
- `TrustRegionDFOAdapter`
- `TrustRegionMODFOAdapter`
- `TrustRegionSubspaceAdapter`
- `TrustRegionNonSmoothAdapter`
- `MASAdapter`
- `AsyncEventDrivenAdapter`
- `SingleTrajectoryAdaptiveAdapter`
- `DifferentialEvolutionAdapter`
- `GradientDescentAdapter`
- `PatternSearchAdapter`
- `NSGA2Adapter`
- `NSGA3Adapter`
- `SPEA2Adapter`

建议按下面类别记忆：

### 单轨迹搜索

- `VNSAdapter`
- `SimulatedAnnealingAdapter`
- `SingleTrajectoryAdaptiveAdapter`
- `GradientDescentAdapter`
- `PatternSearchAdapter`

### 种群进化 / 群体搜索

- `DifferentialEvolutionAdapter`
- `NSGA2Adapter`
- `NSGA3Adapter`
- `SPEA2Adapter`

### 分解型多目标

- `MOEADAdapter`

### 控制器 / 协作编排

- `RoleAdapter`
- `RoleRouterAdapter`
- `StrategyRouterAdapter`
- `AsyncEventDrivenAdapter`

### 图搜索

- `AStarAdapter`
- `MOAStarAdapter`

### 信赖域 / 局部近似

- `TrustRegionDFOAdapter`
- `TrustRegionMODFOAdapter`
- `TrustRegionSubspaceAdapter`
- `TrustRegionNonSmoothAdapter`

### 模型辅助

- `MASAdapter`

---

## 4.1 每个 Adapter 的形象比喻（面试速记版）

这部分专门给“口述记忆”准备：先记画面，再讲原理。

- `RoleAdapter`：像给运动员发“号码牌”，本体不跑战术，只标身份与职责。
- `RoleRouterAdapter`：像一个排班队长，把不同工种分组上场，再按小组回收战报。
- `VNSAdapter`：像“先在家门口找钥匙，找不到就扩大搜索半径到整条街”。
- `MOEADAdapter`：像“把大项目拆成很多小任务，每个小组盯一个子目标并互相借力”。
- `SimulatedAnnealingAdapter`：像“趁热多试错，越冷越保守”，温度高时敢接受差解。
- `StrategyRouterAdapter`：像“战役总指挥”，按阶段给侦察队和突击队分预算与任务。
- `AStarAdapter`：像“导航软件”，综合“已走路程 + 预计路程”选下一步。
- `MOAStarAdapter`：像“多维导航”，同时看时间/油耗/风险，保留多条互不支配路线。
- `TrustRegionDFOAdapter`：像“在当前位置周边画个小圈试探”，圈内找改进，找不到就缩圈。
- `TrustRegionMODFOAdapter`：像“多目标局部会诊”，先按权重折成一个综合评分再在小圈里优化。
- `TrustRegionSubspaceAdapter`：像“只在关键车道超车”，先降维到子空间再搜索。
- `TrustRegionNonSmoothAdapter`：像“走石子路放慢脚步”，用更稳健的评分应对不光滑目标。
- `MASAdapter`：像“带顾问团做决策”，顾问（模型）给建议，搜索器负责拍板试跑。
- `AsyncEventDrivenAdapter`：像“事件调度中台”，谁触发事件就先处理谁，不按死板流水线。
- `SingleTrajectoryAdaptiveAdapter`：像“一个老手司机边开边调方向盘灵敏度”，根据近期效果自动调步长。
- `DifferentialEvolutionAdapter`：像“看同伴差异学动作”，用人群间差分来生成新解。
- `GradientDescentAdapter`：像“摸坡下山”，试探左右高低后沿最陡下降方向走。
- `PatternSearchAdapter`：像“十字路口四处探路”，哪个方向更好就往哪边多走一步。
- `NSGA2Adapter`：像“选秀分层 + 保持队形”，先按等级（非支配层）再看站位稀疏度（拥挤距离）。
- `NSGA3Adapter`：像“按预设站位点排队”，用参考点把多目标解分布摆匀。
- `SPEA2Adapter`：像“既看个人战绩也看人群密度”，强者得分高，扎堆会被稀释。

补充（非 `adapters/__init__.py` 的主清单，但常被问到）：

- `CompositeAdapter`：像“拼盘套餐”，把多个 adapter 的候选直接合并，不做复杂调度。

---

## 5. 所有 Adapter 的统一复习模板

面试复习时，建议每个 adapter 都按 6 个问题回答：

1. **它解决什么问题？**
2. **它的搜索原理是什么？**
3. **`propose()` 怎么生成候选？**
4. **`update()` 更新了哪些内部状态？**
5. **它在这个框架里依赖哪些能力？**
6. **和经典算法相比，本仓实现做了哪些工程化简化？**

下面就按这个模板展开。

---

# 6. 群体进化类 Adapters

## 6.1 `NSGA2Adapter`

**源码**：`adapters/nsga2/adapter.py`

### 6.1.1 它是什么

`NSGA2Adapter` 是本框架里最标准、最成熟的多目标种群进化 adapter 之一。

它内部自己持有：

- `population`
- `objectives`
- `violations`
- `_rank`
- `_crowding`
- `_runtime_projection`

也就是说，它不是无状态函数，而是一个真正的“算法状态机”。

### 6.1.2 配置结构

配置 dataclass：`NSGA2Config`

关键参数：

- `population_size`
- `offspring_size`
- `crossover_rate`
- `objective_aggregation`

### 6.1.3 算法原理

NSGA-II 的核心思想：

1. 对候选解做**非支配排序**，按 Pareto 层分级
2. 在同一层里用**拥挤距离**保持分布多样性
3. 父代选择常用“rank 优先、crowding 次之”的锦标赛
4. 子代产生后，与父代合并，再做环境选择保留固定规模种群

如果面试官问一句话定义，可以答：

> NSGA-II 是一种经典多目标进化算法，用非支配排序保证收敛，用拥挤距离维持解集分布。

### 6.1.4 `propose()` 在本仓里怎么做

核心流程：

1. `_ensure_population()`：优先尝试从 `snapshot` 或 solver 当前种群恢复内部种群
2. 若没有种群，则调用 `solver.init_candidate(context)` 初始化
3. `_refresh_ranking()`：做 non-dominated sort 和 crowding distance
4. 多次 `_tournament_pick()` 挑父母
5. `_crossover()` 生成子代
6. `solver.mutate_candidate()`
7. `solver.repair_candidate()`
8. 返回 offspring 列表

### 6.1.5 `update()` 做什么

`update()` 会：

1. 把当前评估得到的 candidates / objectives / violations 转成数组
2. 若内部还没有种群，则直接把本轮候选作为初始种群
3. 否则把旧种群和新候选合并
4. 调 `_environmental_select()` 做保留
5. 刷新 `rank/crowding`
6. `_sync_runtime_projection()` 暴露 `best_x` 和 `best_objective`

### 6.1.6 状态能力

它实现了：

- `setup()`
- `get_state()` / `set_state()`
- `set_population()` / `get_population()`
- `get_runtime_context_projection()`

因此它是本仓库中**恢复能力最完整**的一类 adapter。

### 6.1.7 在框架里的落地价值

- 可以和 snapshot / checkpoint 无缝结合
- 可以被 runtime 插件直接写回 population
- 可以被 solver 从运行时 context 中读取 best 信息
- 可以作为 `EvolutionSolver` 的默认 adapter

### 6.1.8 实现上的工程特点

- 不把评估塞进 adapter，评估仍由 solver 统一处理
- 尽量从 snapshot 恢复种群，适合恢复运行
- 支持 pipeline crossover，也支持 fallback 线性混合 crossover

### 6.1.9 和经典 NSGA-II 的差异

- 初始种群 bootstrap 比较工程化，不强调严格“先完整评估一代再开始”
- crossover 实现依赖 pipeline，可替换为业务型 crossover
- objective aggregation 主要服务于 best summary，不等于 NSGA-II 的核心判优

### 6.1.10 面试怎么讲

可以答：

> 在这个框架里，NSGA2Adapter 自己持有群体状态，`propose()` 负责锦标赛选父、交叉、变异、修复，`update()` 负责父子合并和环境选择。它最大的工程价值是支持 snapshot 恢复、runtime projection 和 population 写回，所以不是一个纯算法 demo，而是一个可恢复的多目标搜索组件。

---

## 6.2 `NSGA3Adapter`

**源码**：`adapters/nsga3/adapter.py`

### 6.2.1 它是什么

`NSGA3Adapter` 本质上是在 `NSGA2Adapter` 基础上扩展 many-objective 选择机制。

### 6.2.2 配置结构

配置 dataclass：`NSGA3Config`

典型字段：

- 继承 NSGA-II 类似参数
- `divisions`

### 6.2.3 算法原理

NSGA-III 针对的是**目标维度更高**时，NSGA-II 的 crowding distance 不够好用的问题。

它的核心是：

1. 用参考点 / 参考方向覆盖目标空间
2. 个体和参考方向做关联
3. 在最后一个 front 上按 niche 占用做补选

所以 NSGA-III 的关键词是：

- reference points
- niche preservation
- many-objective optimization

### 6.2.4 `propose()` / `update()`

- `propose()` 基本继承 NSGA-II 的生成逻辑
- `update()` 的差异主要在环境选择，最后一个 front 会用参考点 niching 来决定保留谁

### 6.2.5 状态能力

与 `NSGA2Adapter` 类似，具有较强状态性；同时额外维护参考点集合。

### 6.2.6 工程特色

- 复用 NSGA-II 大量工程壳
- 通过 runtime projection 暴露 `reference_points`
- 恢复时重建 reference points，而不是把所有派生结构都序列化

### 6.2.7 风险 / 简化

当前实现里有配置覆盖的风险：某些本地 config 字段可能在后续赋值中回退成默认值，这属于实现细节问题，不是算法思想问题。

### 6.2.8 面试讲法

> NSGA-III 是 NSGA-II 在 many-objective 场景下的增强版本，关键不是 crowding distance，而是 reference points 和 niche selection。在这个仓库里它复用 NSGA-II 的群体状态管理，只在环境选择上做 many-objective 扩展。

---

## 6.3 `SPEA2Adapter`

**源码**：`adapters/spea2/adapter.py`

### 6.3.1 它是什么

SPEA2 是另一条经典多目标进化路线，强调 strength / density fitness。

### 6.3.2 配置结构

配置 dataclass：`SPEA2Config`

关键参数通常包括：

- `population_size`
- `offspring_size`
- `archive_size`
- `k_neighbors`

### 6.3.3 算法原理

SPEA2 的核心不是 crowding distance，而是：

1. 计算每个个体能支配多少其他个体（strength）
2. 用支配关系累积原始适应度（raw fitness）
3. 加上基于邻域距离的密度项
4. 档案过大时做 truncation 保留稀疏分布

### 6.3.4 `propose()` / `update()`

- `propose()` 基本沿用 NSGA-II 的候选生成壳
- `update()` 在环境选择时使用 SPEA2 fitness 而不是 NSGA-II 的 front + crowding 逻辑

### 6.3.5 状态能力

大量状态管理沿用 `NSGA2Adapter`。

### 6.3.6 工程特点

- 复用统一 snapshot / population 写回机制
- 适合和现有 solver、plugin、representation 无缝配合

### 6.3.7 和经典 SPEA2 的差异

- 当前实现更像“沿用 NSGA-II 外壳 + 替换环境选择”的工程版
- 不强调教科书式独立 archive 流程

---

## 6.4 `DifferentialEvolutionAdapter`

**源码**：`adapters/differential_evolution/adapter.py`

### 6.4.1 它是什么

这是 DE（Differential Evolution）在本框架里的实现，属于经典连续优化群体算法。

### 6.4.2 配置结构

配置 dataclass：`DEConfig`

关键参数：

- `population_size`
- `batch_size`
- `f`
- `cr`
- `strategy`（如 `rand1bin` / `best1bin`）

### 6.4.3 算法原理

DE 的核心非常经典：

1. 对每个 target vector，随机选若干个体
2. 构造差分向量
3. 得到 mutant
4. 做 binomial crossover 生成 trial
5. 用 trial 与 target 做贪婪比较，好的留下

一句话：

> DE 是“利用群体差分信息驱动变异”的连续优化算法。

### 6.4.4 `propose()`

它会：

1. 恢复或初始化种群
2. 选取一批 target index
3. 对每个 target 按策略生成 mutant / trial
4. repair 后返回 trial vectors

### 6.4.5 `update()`

它用本轮评估反馈去替换对应 target：

- 若 trial 优于原 target，则替换
- 更新 adapter 内部 best / runtime projection

### 6.4.6 状态能力

它实现了较完整的群体状态恢复能力，和 NSGA-II 类似，也是典型“强状态 adapter”。

### 6.4.7 工程特色

- 和 solver snapshot 集成良好
- 可通过 `best1bin` 读内部最优
- 仍统一走 repair / evaluate，而不是自己内部绕过框架

### 6.4.8 限制

- 初始种群 bootstrap 更偏工程实用，不追求严格教科书流程
- 当前更偏连续变量场景

---

## 6.5 `MOEADAdapter`

**源码**：`adapters/moead/adapter.py`

### 6.5.1 它是什么

MOEA/D 是一种非常重要的多目标方法：**把多目标优化分解成多个标量子问题**。

### 6.5.2 配置结构

配置 dataclass：`MOEADConfig`

关键项很多，重点记住：

- `population_size`
- `neighborhood_size`
- `batch_size`
- `delta`
- `nr`
- `variation`
- `objective_aggregation`
- 随机种子 / 权重相关配置

### 6.5.3 算法原理

MOEA/D 的核心思想：

1. 为多目标问题定义一组权重向量
2. 每个权重向量代表一个标量子问题
3. 每个子问题维护一个候选解
4. 邻近权重向量之间共享搜索信息
5. 通过邻域更新逐步逼近 Pareto 前沿

一句话：

> MOEA/D 不是直接在 Pareto 层面排序，而是把多目标拆成很多相关标量任务并行求解。

### 6.5.4 `propose()`

它会：

1. 初始化 / 恢复分解子问题群体
2. 选一批子问题 index
3. 往 context 写入当前子问题元数据，例如：
	- `moead_subproblem`
	- `moead_weight`
	- `moead_neighbor_mode`
4. 用 pipeline variation 或 DE 风格 variation 生成候选
5. 返回候选 batch

### 6.5.5 `update()`

它的 `update()` 不是简单地“全局保留最优”，而是：

1. 更新 `ideal point`
2. 针对当前子问题或其邻域
3. 依据标量化值（如 Tchebycheff / weighted sum）比较新旧解
4. 最多替换若干邻居

### 6.5.6 状态能力

它显式维护：

- 权重向量
- 邻域关系
- ideal point
- 当前子问题的群体解

并且支持 snapshot / population 写回。

### 6.5.7 工程特色

- 很强调 context 注入，让下游组件知道“当前正在服务哪个子问题”
- 可以和 role / controller 系统结合，用作 explorer
- 会检查某些 archive 类插件是否存在，说明作者考虑了组合运行场景

### 6.5.8 和经典 MOEA/D 的差异

- 当前实现偏轻量，不强调完整外部 archive
- 更偏工程可组合，而不是论文复现型超全实现

### 6.5.9 面试讲法

> 在这个仓库里，MOEADAdapter 的关键不是群体排序，而是“子问题化”。它在 `propose()` 阶段把当前权重向量和子问题索引注入 context，再基于邻域关系生成候选；`update()` 则只在对应子问题及邻域上做替换。这种设计很适合和表示层、控制器以及并行评估拼接。

---

# 7. 单轨迹 / 局部搜索类 Adapters

## 7.1 `VNSAdapter`

**源码**：`adapters/vns/adapter.py`

### 7.1.1 它是什么

VNS = Variable Neighborhood Search，变量邻域搜索。

### 7.1.2 配置结构

配置 dataclass：`VNSConfig`

关键项：

- `batch_size`
- `k_max`
- `base_sigma`
- `scale`
- `restart_on_stagnation`
- `objective_aggregation`

### 7.1.3 算法原理

VNS 的核心是：

1. 不只用一个邻域
2. 当前邻域找不到改进时，就扩大邻域
3. 一旦找到改进，回到较小邻域重新精修

本质上是在“局部开发”和“跳出局部最优”之间切换。

### 7.1.4 `propose()`

它会：

1. 如果还没有当前点，就初始化一个
2. 根据当前 `k` 计算实际 sigma
3. 把 `KEY_MUTATION_SIGMA` 和 `KEY_VNS_K` 写入 context
4. 围绕当前点做多次 mutate + repair
5. 返回邻域候选

### 7.1.5 `update()`

它会：

1. 从本轮候选里选最好的一个
2. 若比 incumbent 更好，则接受，并把 `k` 重置为 0
3. 若没改进，则 `k += 1`
4. 超过 `k_max` 则重启或停在最大邻域

### 7.1.6 状态能力

主要维护：

- 当前点
- 当前分数
- 当前邻域索引 `k`

### 7.1.7 工程特色

这类 adapter 非常依赖 context-aware mutation：

- adapter 不自己写复杂变异逻辑
- 而是把邻域强度通过 context 传给表示层 mutator

这是本框架很漂亮的一点。

### 7.1.8 限制

- 更像“邻域强度自适应随机局部搜索”
- 没有特别严格区分 shaking 和 local search 两段

---

## 7.2 `SimulatedAnnealingAdapter`

**源码**：`adapters/simulated_annealing/adapter.py`

### 7.2.1 它是什么

模拟退火，经典单轨迹随机搜索。

### 7.2.2 配置结构

配置 dataclass：`SAConfig`

重点记：

- 初始温度
- 冷却率
- 最低温度
- batch size
- sigma / step size

### 7.2.3 算法原理

模拟退火的关键是：

1. 当前解附近产生邻居
2. 更优解直接接受
3. 更差解以一定概率接受
4. 温度越低，接受差解的概率越低

它的价值在于有机会越过局部最优障碍。

### 7.2.4 `propose()`

会把：

- `temperature`
- 与温度耦合的 sigma

写入 context，再围绕当前点生成邻居。

### 7.2.5 `update()`

按 Metropolis 规则接受候选：

- 好的直接收
- 差的按概率收
- 然后冷却温度

### 7.2.6 状态能力

主要维护：

- 当前点
- 当前目标值
- 当前温度

### 7.2.7 工程特色

- 和表示层通过 context 协同，而不是把扰动尺度硬写死
- 保持“搜索逻辑在 adapter，扰动逻辑在 representation”

### 7.2.8 限制

- 没有 reheating
- 没有多链并行 SA
- 更偏简洁工程版

---

## 7.3 `SingleTrajectoryAdaptiveAdapter`

**源码**：`adapters/single_trajectory_adaptive/adapter.py`

### 7.3.1 它是什么

这是一个**自适应单轨迹搜索框架**，不完全对应教科书中的某个唯一标准算法名。

### 7.3.2 核心思想

它综合了几种单轨迹启发式常见思想：

- success-rate 调步长
- 停滞时重启
- 小概率接受较差解

### 7.3.3 `propose()`

围绕当前点采样多个邻居，并把：

- 当前 sigma
- 当前状态
- 当前 step 相关字段

写入 context。

### 7.3.4 `update()`

它会统计本轮是否成功改进，并根据成功率窗口自适应更新 sigma。

如果长期没有改进，则触发重启。

### 7.3.5 状态能力

这是一个明显的 stateful adapter，会维护：

- 当前点
- 当前分数
- sigma
- success history
- 停滞计数

### 7.3.6 面试提示

如果面试官问“它属于什么算法”，可以说：

> 它更像一个工程化的自适应单轨迹搜索框架，融合了随机局部搜索、步长自适应和轻量接受机制，而不是严格照搬某篇经典算法论文。

---

## 7.4 `GradientDescentAdapter`

**源码**：`adapters/gradient_descent/adapter.py`

### 7.4.1 它是什么

这是一个**不要求问题显式提供梯度**的有限差分近似梯度下降 adapter。

### 7.4.2 算法原理

核心思路：

1. 在若干维度上各做 `+eps` 和 `-eps` 探测
2. 用差分近似梯度
3. 沿负梯度方向迈一步

### 7.4.3 `propose()`

它不是直接 propose 一个更新后的点，而是先 propose 出探测点集合。

这些探测点被 solver 统一评估后，`update()` 才能近似梯度。

### 7.4.4 `update()`

它会：

1. 根据 `+/-` 探测结果重建梯度近似
2. 在采样维度上形成下降方向
3. 用学习率更新当前点
4. 若本轮改善明显，则可能放大学习率；否则衰减学习率

### 7.4.5 工程特点

- 不依赖 problem 提供解析梯度
- 只依赖统一评估接口
- 适合黑箱但比较平滑的问题

### 7.4.6 限制

- 并不是严格意义的解析梯度下降
- 对噪声、离散变量、不连续目标不友好
- 更像 gradient-inspired black-box search

---

## 7.5 `PatternSearchAdapter`

**源码**：`adapters/pattern_search/adapter.py`

### 7.5.1 它是什么

这是一个简化的模式搜索 / 坐标试探搜索。

### 7.5.2 算法原理

围绕当前点，在若干方向上试探：

- `+step`
- `-step`

如果某个方向改善，则接受，并可能放大 step；否则缩小 step。

### 7.5.3 `propose()` / `update()`

- `propose()`：生成一组方向试探点
- `update()`：选最优试探点决定是否移动与如何调整步长

### 7.5.4 工程特点

- 非常简单、稳健
- 和 solver / repair 体系自然兼容

### 7.5.5 限制

- 没有完整 MADS / mesh / poll set 理论机制
- 属于工程上够用的简化 direct search

---

# 8. 信赖域类 Adapters

## 8.1 先理解 `TrustRegionBase`

**源码**：`adapters/trust_region_base/adapter.py`

`TrustRegionBase` 不是一个给用户直接用的最终算法，而是信赖域 adapter 的公共基类。

它统一处理：

- center 初始化
- radius 管理
- 边界裁剪
- 提议候选的壳
- 成功则扩张半径，失败则缩小半径

子类只需要提供：

- 怎么采样
- 怎么打分 / 标量化

所以看信赖域类时，**一定要先看基类再看子类**。

---

## 8.2 `TrustRegionDFOAdapter`

**源码**：`adapters/trust_region_dfo/adapter.py`

### 算法原理

DFO = Derivative-Free Optimization。

这里的实现是：

- 在当前 center 周围的 trust region 里随机采样
- 评估候选
- 若有明显改进，则 center 移动到更优点，并扩大半径
- 否则缩小半径

### 特色

- 非常适合黑箱优化
- 不需要梯度
- 实现上极简，适合作为局部精修器

### 限制

- 没有经典 trust-region DFO 里的 surrogate/model fitting
- 没有 predicted reduction / actual reduction 比率判据

所以它更像**工程化轻量 trust-region 黑箱局部搜索**。

---

## 8.3 `TrustRegionMODFOAdapter`

**源码**：`adapters/trust_region_mo_dfo/adapter.py`

### 它是什么

多目标版本的 DFO trust region。

### 原理

核心不是直接维护 Pareto front，而是：

- 先把多目标向量通过权重做标量化
- 再在 trust region 里做局部搜索

### 工程特点

- 可以从 context 读取权重
- 因此容易和更高层的控制器或阶段调度结合

### 限制

- 它不是完整多目标 TR 框架
- 更像“多目标 -> 标量目标”的局部优化器

---

## 8.4 `TrustRegionSubspaceAdapter`

**源码**：`adapters/trust_region_subspace/adapter.py`

### 原理

如果维度很高，直接在全空间采样很浪费。

这个 adapter 的思路是：

- 构造一个低维子空间 basis
- 在子空间中采样 trust region 变化
- 再映射回原空间

### 适合场景

- 高维连续优化
- 怀疑有效自由度低于原始维度

### 工程特点

- 可以从 context 中读取 `subspace_basis`
- 否则自己生成随机正交 basis

### 限制

- basis 不是从样本学习出来的严格主动子空间
- 更偏随机子空间搜索

---

## 8.5 `TrustRegionNonSmoothAdapter`

**源码**：`adapters/trust_region_nonsmooth/adapter.py`

### 原理

对非光滑目标，简单求和有时不稳。

它通过：

- `L1`
- `L∞`

等聚合方式来标量化目标，使局部搜索对尖角 / 分段目标更稳健。

### 限制

- 并没有真正实现 bundle / subgradient 类 nonsmooth 方法
- 只是把 scoring 逻辑换成了更稳健的聚合

所以面试里不要把它讲成完整 nonsmooth trust-region 理论实现。

---

# 9. 图搜索类 Adapters

## 9.1 `AStarAdapter`

**源码**：`adapters/astar/adapter.py`

### 9.1.1 它是什么

这是把 A* 图搜索包装成 Adapter 的实现。

### 9.1.2 算法原理

A* 的核心是：

- `f(n) = g(n) + h(n)`

其中：

- `g(n)`：从起点到当前节点的真实代价
- `h(n)`：启发式估计到目标的剩余代价

每一步扩展 `f` 最小的节点。

### 9.1.3 在本框架里的实现方式

这个 adapter 不直接内建某个图结构，而是依赖外部回调：

- 邻接节点怎么生成
- goal 怎么判断
- heuristic 怎么算
- state 怎么哈希等

### 9.1.4 `propose()`

从 open list 取出若干节点扩展，把子节点变成 solver 可评估的候选。

### 9.1.5 `update()`

拿回 objective 后，结合 heuristic 构造 A* priority，再放回 open list。

### 9.1.6 工程意义

这说明这个框架的 adapter 并不只适合连续优化，也适合图搜索类问题。

### 9.1.7 限制

- 多目标仍被标量化
- checkpoint 对 frontier 恢复不完整

---

## 9.2 `MOAStarAdapter`

**源码**：`adapters/moa_star/adapter.py`

### 9.2.1 它是什么

MOA* = Multi-Objective A*，多目标 A* / 多标签图搜索。

### 9.2.2 算法原理

和普通 A* 不同，一个状态可能对应多个 nondominated label。

因此它要维护：

- 每个 state 的多个 label
- label dominance pruning
- 全局 Pareto 解集

### 9.2.3 `propose()` / `update()`

- `propose()`：从 open label 扩展候选
- `update()`：根据向量代价更新 state labels，并剔除被支配标签

### 9.2.4 工程特点

- 把图搜索也纳入了统一 `propose/update/evaluate` 架构
- 支持全局 Pareto 解跟踪

### 9.2.5 限制

- open priority 依然需要标量顺序，存在工程偏置
- 仍是轻量实现，不是最完整的多标签最短路系统

---

# 10. 控制器 / 协作类 Adapters

## 10.1 `RoleAdapter`

**源码**：`adapters/role_adapters/adapter.py`

### 它是什么

`RoleAdapter` 不是一种新搜索算法，而是一个包装器。

它的作用是：

- 给内部 adapter 打上 role 语义
- 往 context 注入 `role` / `role_index` / `adapter_name` 等元信息
- 统一 role 级别的报告

### 为什么重要

因为后面的多角色控制器都需要“每个策略单元是什么身份”这层语义。

---

## 10.2 `RoleRouterAdapter`

**源码**：`adapters/role_adapters/adapter.py`

### 它是什么

这是最基础的多角色编排器。

### 原理

它本身不实现搜索，而是：

1. 让每个 role adapter 自己 propose
2. 把所有候选拼成一大批
3. 评估后再按来源切回各 role 做 update

### 工程意义

它是把多个搜索器并排拼接起来的最小骨架。

### 限制

- 没有复杂预算分配
- 没有阶段切换
- 没有区域协同

这些高级能力在 `StrategyRouterAdapter` 里。

---

## 10.3 `StrategyRouterAdapter`

**源码**：`adapters/multi_strategy/adapter.py`

### 10.3.1 它是什么

这是仓库里最强的“协作控制器型 adapter”之一。

它不是单一算法，而是一个**多角色、多单元、多阶段、多区域**的搜索编排器。

### 10.3.2 配置结构

配置 dataclass：`MultiStrategyConfig`

关键能力很多：

- 总 batch size
- role 权重
- phase schedule
- stagnation window
- region update interval
- 是否 adapt weights
- 是否 enable regions

以及配套：

- `StrategySpec`
- `RoleSpec`

### 10.3.3 它的算法本质

它不是某个教科书算法，而是“控制器”。

你可以把它理解为：

> 在同一个 solver 内同时挂多个搜索子策略，再由上层控制器按阶段、预算、权重和区域来协调它们共同搜索。

### 10.3.4 `propose()`

它会做很多编排工作：

1. 计算当前 phase
2. 可能刷新 region 划分
3. 根据 role 权重分配预算
4. 把 budget / role / region / seeds 等信息写入 context
5. 调各个 unit 的 `propose()`
6. 记录每个 candidate 来自哪个 role / unit

### 10.3.5 `update()`

会把反馈：

1. 先按 candidate 来源拆回各子 unit
2. 更新 role-level best / EMA / stagnation
3. 必要时自适应调整各 role 权重
4. 汇总 shared state、reports、region stats

### 10.3.6 工程价值

这是框架“平台化”非常强的一块，因为它允许：

- 一个角色专门探索
- 一个角色专门开发
- 阶段切换时变更激活角色
- 区域化管理不同搜索子空间

### 10.3.7 限制

- 权重自适应是启发式的，不是严格 bandit 学习器
- checkpoint 对整体 child-state 恢复还不够完整

### 10.3.8 面试讲法

> 这是一个把多个 adapter 组合成“搜索组织”的控制器，重点不在某个单一元启发式，而在预算分配、阶段调度、区域协同和反馈拆分。它体现的是框架的 orchestration 能力。

---

## 10.4 `AsyncEventDrivenAdapter`

**源码**：`adapters/async_event_driven/adapter.py`

### 10.4.1 它是什么

一个事件驱动控制器。

### 10.4.2 核心思想

不是按“固定一代做一轮 propose/update”，而是维护：

- event queue
- inflight events
- archive / history

由事件来驱动下一批动作。

### 10.4.3 `propose()`

它会：

1. 补齐事件队列
2. 取若干 propose 事件
3. 把局部 event context 注入子策略
4. 调用子 adapter propose
5. 记录 inflight 映射

### 10.4.4 `update()`

1. 按 inflight 把结果还原到对应策略
2. 写 completion archive / history / stats
3. 再根据规则补充新事件
4. 把反馈分发给各策略

### 10.4.5 算法视角

它更像一个**异步调度语义层**，而不是某个优化算法。

### 10.4.6 工程意义

适合：

- 多子策略协作
- 事件驱动的调度/仿真
- 近似异步搜索

### 10.4.7 限制

- 实际仍运行在 solver 的同步 step 框架里
- 更准确地说是“事件语义异步”，不是线程意义上的完全异步

---

# 11. 模型辅助 / 混合类 Adapters

## 11.1 `MASAdapter`

**源码**：`adapters/mas/adapter.py`

### 11.1.1 它是什么

MAS 这里可以理解为一种轻量的 **Model-Assisted Search**。

### 11.1.2 算法思想

它把 batch 分成两块：

- exploration：直接随机/局部扰动采样
- exploitation：若 context 中有模型 `mas_model`，则借助模型选更有希望的点

### 11.1.3 `propose()`

1. 先做探索样本
2. 若上下文里有 surrogate/model，则生成一个候选池
3. 让模型在池中挑预测最优点
4. 合并为最终 batch

### 11.1.4 `update()`

当前实现比较轻：直接把本轮标量分数最好的 candidate 作为新当前点。

### 11.1.5 工程特点

- adapter 自己不训练模型
- 模型由 context / plugin 提供
- 因此边界非常清晰：模型能力在外面，搜索控制在 adapter

### 11.1.6 限制

- 不是严格 surrogate-assisted EA
- 没有 acquisition function
- 没有 uncertainty-aware 主动学习闭环

---

# 12. 还有一个非常重要但容易漏掉的类别：组合与基类

## 12.1 `CompositeAdapter`

**源码**：`adapters/algorithm_adapter.py`

### 它是什么

最朴素的组合器：把多个 adapter 的 `propose()` 合并。

### 用途

- 快速把多个子 adapter 拼到一起
- 做并行候选生成

### 限制

- 没有高级角色语义
- 没有预算分配 / phase
- 只是基础组合工具

---

# 13. 各 Adapter 的状态能力速记表

下面是面试时最值得记的“状态恢复能力”差异。

## 13.1 强状态、强恢复

这类通常维护种群或复杂算法态，且实现了较完整的恢复接口：

- `NSGA2Adapter`
- `NSGA3Adapter`
- `SPEA2Adapter`
- `MOEADAdapter`
- `DifferentialEvolutionAdapter`

关键词：

- `population`
- `objectives`
- `violations`
- `get_state/set_state`
- `set_population/get_population`

`state_recovery_level` 源码对照（字段名：`state_recovery_level`）：

- `NSGA2Adapter`：`L2`（`adapters/nsga2/adapter.py:39`）
- `NSGA3Adapter`：`L2`（`adapters/nsga3/adapter.py:27`）
- `SPEA2Adapter`：`L2`（`adapters/spea2/adapter.py:27`）
- `MOEADAdapter`：`L2`（`adapters/moead/adapter.py:70`）
- `DifferentialEvolutionAdapter`：`L2`（`adapters/differential_evolution/adapter.py:52`）

## 13.2 中等状态、局部搜索态

- `VNSAdapter`
- `SimulatedAnnealingAdapter`
- `SingleTrajectoryAdaptiveAdapter`
- `GradientDescentAdapter`
- `PatternSearchAdapter`
- `TrustRegion*`

关键词：

- current point
- current score
- temperature / sigma / radius / step size

`state_recovery_level` 源码对照（字段名：`state_recovery_level`）：

- `VNSAdapter`：`L1`（`adapters/vns/adapter.py:55`）
- `SimulatedAnnealingAdapter`：`L1`（`adapters/simulated_annealing/adapter.py:60`）
- `SingleTrajectoryAdaptiveAdapter`：`L1`（`adapters/single_trajectory_adaptive/adapter.py:62`）
- `GradientDescentAdapter`：`L1`（`adapters/gradient_descent/adapter.py:33`）
- `PatternSearchAdapter`：`L1`（`adapters/pattern_search/adapter.py:32`）
- `TrustRegion*`：基类声明 `L1`（`adapters/trust_region_base/adapter.py:29`），`DFO/MO-DFO/Subspace/NonSmooth` 继承该值

## 13.3 控制器状态

- `RoleRouterAdapter`
- `StrategyRouterAdapter`
- `AsyncEventDrivenAdapter`

关键词：

- candidate 来源映射
- role/unit/phase/region
- queue/inflight/history
- 子策略分发信息

`state_recovery_level` 源码对照（字段名：`state_recovery_level`）：

- `RoleRouterAdapter`：`L1`（`adapters/role_adapters/adapter.py:281`）
- `AsyncEventDrivenAdapter`：`L1`（`adapters/async_event_driven/adapter.py:95`）
- `StrategyRouterAdapter`：当前文件未显式声明该字段，使用 `AlgorithmAdapter` 默认值 `L0`（`adapters/algorithm_adapter.py:24`）

## 13.4 弱状态或外部依赖状态

- `MASAdapter`
- `AStarAdapter`
- `MOAStarAdapter`

它们内部有状态，但很多关键能力依赖外部回调、外部模型或图结构。

`state_recovery_level` 源码对照（字段名：`state_recovery_level`）：

- `MASAdapter`：`L1`（`adapters/mas/adapter.py:37`）
- `AStarAdapter`：`L0`（`adapters/astar/adapter.py:81`）
- `MOAStarAdapter`：`L0`（`adapters/moa_star/adapter.py:89`）

口述提示：`state_recovery_level` 是“声明能力级别”，并不等于“恢复后一定语义完全等价”。例如 `MASAdapter` 虽声明 `L1`，但其效果仍受外部 `mas_model` 可用性影响。

---

# 14. 各 Adapter 和 Representation / Context 的配合方式

这是面试最容易答浅的一块，必须讲清楚。

## 14.1 为什么 Adapter 不直接自己 mutate/repair 一切

因为框架要把：

- 搜索策略
- 候选解操作
- 业务可行性修复

分层。

所以很多 adapter 都会调用：

- `solver.init_candidate(context)`
- `solver.mutate_candidate(x, context)`
- `solver.repair_candidate(x, context)`

而不是自己把所有扰动细节写死。

## 14.2 为什么要通过 context 传参数

例如：

- `VNSAdapter` 会写 `mutation_sigma` 和 `vns_k`
- `SimulatedAnnealingAdapter` 会写 `temperature`
- `MOEADAdapter` 会写子问题权重
- `StrategyRouterAdapter` 会写 role / region / seeds

这样表示层可以根据不同算法上下文调整行为，而不需要 adapter 直接依赖具体 mutator 的类实现。

## 14.3 这体现了什么设计思想

这体现了一个核心思想：

> Adapter 决定“要搜哪里、搜多大、搜哪一类”，Representation 决定“候选具体怎么被变、怎么被修”。

---

# 15. 如何用面试视角比较这些算法

## 15.1 如果问“哪个更适合黑箱优化？”

可以这样分：

- **非常黑箱友好**：`DE`, `VNS`, `SA`, `PatternSearch`, `TrustRegionDFO`
- **多目标黑箱强项**：`NSGA2`, `NSGA3`, `SPEA2`, `MOEAD`
- **需要一定结构化上下文**：`AStar`, `MOAStar`, `MAS`

## 15.2 如果问“哪个更适合高维连续优化？”

- `DifferentialEvolutionAdapter`
- `TrustRegionSubspaceAdapter`
- `MOEADAdapter`（多目标）
- `NSGA2/3`（多目标但代价通常更高）

## 15.3 如果问“哪个更适合局部精修？”

- `PatternSearchAdapter`
- `GradientDescentAdapter`
- `TrustRegionDFOAdapter`
- `VNSAdapter`
- `SingleTrajectoryAdaptiveAdapter`

## 15.4 如果问“哪个更适合多策略协作？”

- `RoleRouterAdapter`
- `StrategyRouterAdapter`
- `AsyncEventDrivenAdapter`

---

# 16. 面试时最值得背的几个“高质量总结句”

## 16.1 讲 Adapter 设计

> 这个框架把算法策略抽成 Adapter，统一走 `propose/update` 两阶段：`propose` 只负责生成候选，`update` 只负责吸收评估反馈和维护内部状态。评估、插件、snapshot 和表示层都不写死在 adapter 里，因此算法能在统一控制平面下自由替换。

## 16.2 讲状态恢复

> 这个仓库里最成熟的 adapter 是 NSGA2/NSGA3/SPEA2/MOEAD/DE 这类强状态群体算法，它们不仅维护 population/objectives，还实现了 `get_state/set_state` 和 population 写回接口，因此非常适合 checkpoint、恢复运行和 runtime 插件协作。

## 16.3 讲控制器型 adapter

> `StrategyRouterAdapter` 和 `AsyncEventDrivenAdapter` 体现的是 orchestration，不是单一启发式本身。它们把多个 adapter 组织成一个多角色、多阶段或事件驱动的搜索系统，这比单一算法更接近真实工程优化平台。

## 16.4 讲 Representation 协同

> 这个框架里 adapter 不直接绑死具体变异器，而是通过 context 把温度、邻域尺度、子问题权重、角色信息传给 representation，这样搜索策略和候选解操作就能正交演化。

---

# 17. 面试复习建议：怎么背最快

## 第一层：先背框架共性

背下来这 4 句话：

1. 所有 adapter 都实现 `propose/update`
2. `Solver` 管运行，`Adapter` 管搜索
3. `Representation` 管 init/mutate/repair
4. 强状态 adapter 支持 checkpoint / snapshot 恢复

## 第二层：按类别背算法

- 单轨迹：`VNS / SA / STA / GD / Pattern`
- 群体：`DE / NSGA2 / NSGA3 / SPEA2`
- 分解：`MOEAD`
- 控制器：`Role / MultiRole / MultiStrategy / AsyncEvent`
- 图搜索：`A* / MOA*`
- 信赖域：`TR-DFO / TR-MO-DFO / TR-Subspace / TR-NonSmooth`
- 模型辅助：`MAS`

## 第三层：每类只记一个关键词

- `NSGA2`：非支配排序 + 拥挤距离
- `NSGA3`：参考点
- `SPEA2`：strength + density
- `MOEAD`：分解子问题
- `DE`：差分变异
- `VNS`：邻域切换
- `SA`：温度接受差解
- `Pattern`：方向试探
- `GD`：有限差分梯度
- `TR`：局部半径控制
- `A*`：`g+h`
- `MOA*`：多标签 nondominated
- `MAS`：模型辅助挑点
- `MultiStrategy`：角色/阶段/预算控制

---

# 18. 最后总结：这个仓库里的 Adapter 设计为什么值得面试讲

因为它体现了三个成熟工程思想：

## 18.1 算法本体与运行框架解耦

算法不再和 solver 主循环绑死，这让：

- 替换算法更容易
- 统一评估和插件机制更稳定
- checkpoint / snapshot 更容易做

## 18.2 搜索策略与表示层解耦

Adapter 决定搜索，Representation 决定候选操作。

因此：

- 同一个 VNS 可以作用于连续向量、矩阵、排列等不同表示
- 同一个 MOEAD 可以搭配不同 repair / mutate 策略

## 18.3 控制器型搜索成为一等公民

很多框架只会做“一个算法一个类”。

这个仓库更进一步，把：

- 多角色协作
- 多阶段调度
- 事件驱动搜索

也做成 adapter/controller，这更接近实际优化平台的需求。

---

## 19. 建议接下来继续复习的源码文件

如果你要继续顺着这份文档深挖，建议按以下顺序读：

1. `adapters/algorithm_adapter.py`
2. `core/composable_solver.py`
3. `adapters/nsga2/adapter.py`
4. `adapters/moead/adapter.py`
5. `adapters/multi_strategy/adapter.py`
6. `adapters/async_event_driven/adapter.py`
7. `representation/base.py`
8. `core/solver_helpers/evaluation_helpers.py`

这样最容易把“算法、状态、评估、表示层、控制器”串起来。

---

## 20. 一句话压轴版

> `nsgablack` 的 Adapter 体系，本质上是把“搜索算法”提升成可恢复、可编排、可组合、可观测的运行组件；它不只是实现算法原理，更把算法落到了统一工程控制平面里。

---

# 21. 轻量工程化是劣势吗？

结论：**不是天然劣势**。在这个框架里，轻量实现通常是“可组合留白”，不是“能力缺失”。

你可以面试里这样讲：

1. **轻量核心保证可维护**：`propose/update` 简洁、边界清晰，便于排错和替换。
2. **复杂能力外置为组件**：并行、评估代理、恢复、观测、导出由 `Solver + Plugin + Store` 承担。
3. **可按需还原经典做法**：通过 `RepresentationPipeline`、插件、控制器和参数模板逐步逼近教科书流程。

一句话口述：

> 轻量不是阉割，而是把“算法核”与“工程能力”拆开；需要经典完整流程时，通过框架组件组合就能补齐。

---

# 22. 每个 Adapter 的“经典还原做法”（可直接口述）

下面按官方导出清单给出“当前偏轻量点 -> 如何还原到更经典做法”。

边界提示（建议口述时先说这句）：**以下“还原做法”是工程等效增强路径，不等于对论文版理论假设与收敛性证明的 1:1 复刻。**

## 22.1 群体进化 / 多目标

### `NSGA2Adapter`

- 当前偏轻量点：初始化与恢复流程偏工程 bootstrap。
- 还原做法：
	1. 固定 `population_size`，首代强制完整评估后再进入进化；
	2. 用 `RepresentationPipeline` 提供稳定 `crossover + mutation + repair`；
	3. 开启 `CheckpointResumePlugin` 保持代际可回放；
	4. 用 `ParetoArchivePlugin` 做外部前沿持久化。
- 可直接组合组件：`ParetoArchivePlugin`、`CheckpointResumePlugin`。

### `NSGA3Adapter`

- 当前偏轻量点：参考点与配置仍偏工程实用。
- 还原做法：
	1. 显式设定参考点划分策略（按目标维度分档）；
	2. 让目标归一化步骤固定化（在 problem 或评估插件中）；
	3. 搭配 `ModuleReport/DecisionTrace` 跟踪 niche 选择质量。
- 可直接组合组件：`ModuleReportPlugin`、`DecisionTracePlugin`。

### `SPEA2Adapter`

- 当前偏轻量点：更多复用 NSGA2 壳。
- 还原做法：
	1. 单独配置 archive 规模并长期保留外部档案；
	2. 用插件周期评估 density/spacing 指标；
	3. 把环境选择与档案更新节奏固定成 SPEA2 教科书流程。
- 可直接组合组件：`ParetoArchivePlugin`、`BenchmarkHarnessPlugin`。

### `MOEADAdapter`

- 当前偏轻量点：强调工程可组合，外部 archive 不强绑定。
- 还原做法：
	1. 显式设置 `weights + neighborhood + delta + nr`；
	2. 固化标量化函数（Tchebycheff / weighted sum）并记录；
	3. 配 `ParetoArchivePlugin` 做全局前沿补充；
	4. 在 `MultiStrategy` 中将其定位为 explorer 角色。
- 可直接组合组件：`ParetoArchivePlugin`、`StrategyRouterAdapter`。

### `DifferentialEvolutionAdapter`

- 当前偏轻量点：初始化/首轮更新偏工程 bootstrap。
- 还原做法：
	1. 首代完整评估后再进入 trial 竞争；
	2. 固化 `strategy/F/CR` 并按维度设置 `pop_size`；
	3. 用 `CheckpointResume` 保留种群态，确保跨运行一致性。
- 可直接组合组件：`CheckpointResumePlugin`、`ProfilerPlugin`。

## 22.2 单轨迹 / 局部优化

### `VNSAdapter`

- 当前偏轻量点：更偏“邻域强度驱动”实现。
- 还原做法：
	1. 在 `RepresentationPipeline` 明确实现“shaking + local search”双阶段；
	2. 通过 `context` 传 `k/sigma`，并固定升级/重启策略；
	3. 用进度插件记录每个邻域的成功率曲线。
- 可直接组合组件：`DecisionTracePlugin`、`BenchmarkHarnessPlugin`。

### `SimulatedAnnealingAdapter`

- 当前偏轻量点：退火流程简化。
- 还原做法：
	1. 固化温度表（几何/线性/自定义）；
	2. 增加 reheating（可在控制器或插件层触发）；
	3. 将“每温度迭代次数”作为外部调度参数固定。
- 可直接组合组件：`DecisionTracePlugin`、`DynamicSwitchPlugin`。

### `SingleTrajectoryAdaptiveAdapter`

- 当前偏轻量点：是工程化融合策略，不是单一论文复现。
- 还原做法：
	1. 固定成功率窗口和 sigma 更新规则；
	2. 固定重启条件与阈值；
	3. 通过 `DecisionTrace` 输出每步自适应依据，增强可解释。
- 可直接组合组件：`DecisionTracePlugin`、`ProfilerPlugin`。

### `GradientDescentAdapter`

- 当前偏轻量点：有限差分近似，非解析梯度。
- 还原做法：
	1. 若问题可导，在 problem 侧提供梯度并加专用 adapter；
	2. 若仍黑箱，增大差分采样稳定性并做噪声平滑；
	3. 把学习率策略外置可配置（衰减/回溯）。
- 可直接组合组件：`BenchmarkHarnessPlugin`、`ModuleReportPlugin`。

### `PatternSearchAdapter`

- 当前偏轻量点：简化方向试探。
- 还原做法：
	1. 引入完整 poll set / mesh 概念（在 adapter 内扩展）；
	2. 固定 step 缩放与终止判据；
	3. 搭配 `TrustRegion` 或 `VNS` 做两阶段（全局后精修）。
- 可直接组合组件：`BenchmarkHarnessPlugin`、`DecisionTracePlugin`。

## 22.3 信赖域家族

### `TrustRegionDFOAdapter`

- 当前偏轻量点：没有完整 surrogate/model 管线。
- 还原做法：
	1. 在插件层加入局部代理模型（如二次近似）评估；
	2. 在 adapter 扩展 predicted vs actual reduction 判据；
	3. 固化 radius 更新阈值策略。
- 可直接组合组件：`SurrogateEvaluationProviderPlugin`、`SensitivityAnalysisPlugin`。

### `TrustRegionMODFOAdapter`

- 当前偏轻量点：多目标主要靠标量化。
- 还原做法：
	1. 明确权重更新机制（固定/阶段/自适应）；
	2. 搭配 `ParetoArchive` 保留全局非支配解；
	3. 与 `MOEAD` 组合形成“分解+局部TR精修”。
- 可直接组合组件：`ParetoArchivePlugin`、`StrategyRouterAdapter`。

### `TrustRegionSubspaceAdapter`

- 当前偏轻量点：子空间可随机生成。
- 还原做法：
	1. 用模型插件提供数据驱动 basis（如 PCA/主动子空间）；
	2. 固定 basis 更新周期与保真度指标；
	3. 用 `ModuleReport` 追踪子空间解释方差。

### `TrustRegionNonSmoothAdapter`

- 当前偏轻量点：以稳健聚合替代完整 nonsmooth 理论工具链。
- 还原做法：
	1. 引入分段/次梯度信息（若可获得）；
	2. 固定 `L1/Linf` 切换规则；
	3. 配 `SensitivityAnalysis` 插件监控不光滑区段行为。
- 可直接组合组件：`SensitivityAnalysisPlugin`、`BenchmarkHarnessPlugin`。

## 22.4 图搜索与模型辅助

### `AStarAdapter`

- 当前偏轻量点：依赖外部回调质量。
- 还原做法：
	1. 明确 admissible/consistent heuristic；
	2. 完整定义状态去重与闭集策略；
	3. 用 checkpoint 扩展保存 frontier 结构（若业务需要长跑）。
- 可直接组合组件：`CheckpointResumePlugin`、`ModuleReportPlugin`。

### `MOAStarAdapter`

- 当前偏轻量点：open 优先级仍需标量排序。
- 还原做法：
	1. 增强 label 管理与 dominance pruning 规则；
	2. 把多指标 tie-break 规则固定并记录；
	3. 配前沿导出插件做阶段性 Pareto 检查。
- 可直接组合组件：`ParetoArchivePlugin`、`ModuleReportPlugin`。

### `MASAdapter`

- 当前偏轻量点：模型训练在外部，不内建完整主动学习闭环。
- 还原做法：
	1. 使用 `SurrogateEvaluation` / 模型插件形成“评估-训练-回注”闭环；
	2. 明确 exploitation/exploration 比例计划；
	3. 记录模型误差与回退策略（模型失真时回真评估）。
- 可直接组合组件：`SurrogateEvaluationProviderPlugin`、`EvaluationModelProviderPlugin`。

## 22.5 控制器 / 组合

### `RoleAdapter`

- 当前偏轻量点：只做身份包装。
- 还原做法：
	1. 与 `MultiRoleController` 或 `MultiStrategy` 联用；
	2. 给每个 role 固定 context 合同与 KPI；
	3. 用 report 插件输出角色贡献。

### `RoleRouterAdapter`

- 当前偏轻量点：静态聚合为主。
- 还原做法：
	1. 在上层引入动态预算分配规则；
	2. 用 phase 控制角色激活；
	3. 结合 `MultiStrategy` 完成更完整编排。

### `StrategyRouterAdapter`

- 当前偏轻量点：权重自适应偏启发式。
- 还原做法：
	1. 固定 phase 计划后再逐步打开 adapt_weights；
	2. 让 explorer/exploiter 角色明确分工（如 `MOEAD + VNS`）；
	3. 用 `DecisionTrace` 记录每次权重变化依据。

### `AsyncEventDrivenAdapter`

- 当前偏轻量点：语义异步，执行仍在同步 step 框架。
- 还原做法：
	1. 配 `AsyncEventHubPlugin` 与外部系统事件联动；
	2. 固化事件类型、重试、超时、回压策略；
	3. 在评估插件中增加批处理与优先级策略。
- 可直接组合组件：`AsyncEventHubPlugin`、`TimeoutBudgetPlugin`。

### `CompositeAdapter`

- 当前偏轻量点：仅拼接，不做智能调度。
- 还原做法：
	1. 在上层接入 `MultiRole`/`MultiStrategy`；
	2. 对各子 adapter 定义预算与阶段；
	3. 从“拼盘”升级为“编排”。
- 可直接组合组件：`RoleRouterAdapter`、`StrategyRouterAdapter`。

## 22.6 组件装配清单（必选 / 可选 / 不建议）

> 说明：这是“工程落地”清单，不是论文复刻清单；`不建议` 指默认场景下的高风险搭配，并非绝对禁止。

| Adapter | 必选组件（建议默认带） | 可选组件（按场景增强） | 不建议（默认场景） |
| --- | --- | --- | --- |
| `NSGA2Adapter` | `RepresentationPipeline`、`ParetoArchivePlugin`、`CheckpointResumePlugin` | `DecisionTracePlugin`、`BenchmarkHarnessPlugin`、`ModuleReportPlugin` | 不带 `repair` 直接跑强约束问题 |
| `NSGA3Adapter` | `RepresentationPipeline`、`ParetoArchivePlugin`、`CheckpointResumePlugin` | `DecisionTracePlugin`、`ModuleReportPlugin` | 参考点未规划就直接 many-objective 上线 |
| `SPEA2Adapter` | `RepresentationPipeline`、`ParetoArchivePlugin`、`CheckpointResumePlugin` | `BenchmarkHarnessPlugin`、`ModuleReportPlugin` | 只看单次最优，不保留 archive |
| `DifferentialEvolutionAdapter` | `RepresentationPipeline`、`CheckpointResumePlugin` | `ProfilerPlugin`、`BenchmarkHarnessPlugin` | 高约束下不配 `repair` |
| `VNSAdapter` | `RepresentationPipeline`（可消费 `mutation_sigma/vns_k`） | `DecisionTracePlugin`、`BenchmarkHarnessPlugin` | mutator 不读 context 仍强行用 VNS 邻域参数 |
| `SimulatedAnnealingAdapter` | `RepresentationPipeline`、`DecisionTracePlugin` | `DynamicSwitchPlugin`、`ProfilerPlugin` | 温度计划未配置就在高噪声问题长期跑 |
| `SingleTrajectoryAdaptiveAdapter` | `RepresentationPipeline`、`DecisionTracePlugin` | `ProfilerPlugin`、`BenchmarkHarnessPlugin` | 不看成功率/停滞指标盲目调 sigma |
| `GradientDescentAdapter` | `RepresentationPipeline`、`BenchmarkHarnessPlugin` | `ModuleReportPlugin`、`DecisionTracePlugin` | 强噪声/离散问题直接当主力算法 |
| `PatternSearchAdapter` | `RepresentationPipeline`、`BenchmarkHarnessPlugin` | `DecisionTracePlugin`、`TrustRegionDFOAdapter`（两阶段） | 需要全局探索却只用 Pattern |
| `TrustRegionDFOAdapter` | `RepresentationPipeline`、`CheckpointResumePlugin` | `SurrogateEvaluationProviderPlugin`、`SensitivityAnalysisPlugin` | 无边界修复直接放大半径 |
| `TrustRegionMODFOAdapter` | `RepresentationPipeline`、`ParetoArchivePlugin` | `StrategyRouterAdapter`、`DecisionTracePlugin` | 权重策略未定义就做多目标结论 |
| `TrustRegionNonSmoothAdapter` | `RepresentationPipeline`、`SensitivityAnalysisPlugin` | `BenchmarkHarnessPlugin`、`ModuleReportPlugin` | 把它当作可替代所有 nonsmooth 理论算法 |
| `AStarAdapter` | `CheckpointResumePlugin`、`ModuleReportPlugin` | `DecisionTracePlugin`、`TimeoutBudgetPlugin` | 启发函数无一致性检查就上线 |
| `MOAStarAdapter` | `ParetoArchivePlugin`、`ModuleReportPlugin` | `CheckpointResumePlugin`、`DecisionTracePlugin` | 不做 label 剪枝监控 |
| `MASAdapter` | `SurrogateEvaluationProviderPlugin`、`EvaluationModelProviderPlugin` | `TimeoutBudgetPlugin`、`BenchmarkHarnessPlugin` | 全程只信代理，不留真评估回注 |
| `AsyncEventDrivenAdapter` | `AsyncEventHubPlugin`、`TimeoutBudgetPlugin` | `DecisionTracePlugin`、`BenchmarkHarnessPlugin` | 事件 schema/重试/回压未定义 |
| `CompositeAdapter` | `RoleRouterAdapter` 或 `StrategyRouterAdapter` | `DecisionTracePlugin`、`ModuleReportPlugin` | 长期只做“拼盘合并”不做调度升级 |

## 22.7 为什么选这些组件：它们各自补了什么“经典还原功能”

> 这一节是 `22.6` 的“解释层”：`22.6` 告诉你“带什么”，这里告诉你“为什么带、补哪块缺口”。

| 组件 | 为什么要选它 | 主要弥补的还原功能 | 常见适配器 |
| --- | --- | --- | --- |
| `RepresentationPipeline`（含 `repair`） | 把候选操作统一在 init/mutate/crossover/repair 链路里，避免算法内散落约束处理 | 补“可行性闭环”与“算子一致性”；把论文里默认可行域假设落到工程实现 | `NSGA2/3`、`SPEA2`、`MOEAD`、`DE`、`VNS`、`TR*` |
| `ParetoArchivePlugin` | 将外部非支配前沿持久化，不依赖单代内存态 | 补“外部档案机制”和“跨代前沿可追溯”；接近 SPEA2/NSGA 系的档案语义 | `NSGA2/3`、`SPEA2`、`MOEAD`、`MOA*` |
| `CheckpointResumePlugin` | 将运行态可恢复化，防止长跑中断后状态丢失 | 补“可回放实验条件”和“跨会话连续优化”；等效恢复经典算法迭代轨迹 | `NSGA2/3`、`DE`、`TR*`、`A*` |
| `DecisionTracePlugin` | 记录每次切换、接受、权重变更的依据 | 补“过程可解释性”；把启发式决策从黑箱变成可审计轨迹 | `SA`、`VNS`、`MultiStrategy`、`MultiRole`、`AsyncEvent` |
| `BenchmarkHarnessPlugin` | 统一产出阶段/策略收益曲线，支持对比实验 | 补“实验可比性”和“调参证据链”；避免只看单次最好值 | `DE`、`VNS`、`Pattern`、`STA`、`MAS` |
| `ModuleReportPlugin` | 输出模块级统计（角色贡献、子空间质量、路径特征） | 补“结构化诊断”；将复合流程拆解到模块维度验证 | `NSGA3`、`TR-Subspace`、`A*`、`MOA*`、`Role` |
| `SurrogateEvaluationProviderPlugin` | 用代理评估替代部分真评估以降低成本 | 补“昂贵评估可落地”；在工程上还原模型辅助优化的可执行闭环 | `MAS`、`TR-DFO`、任意高成本目标 |
| `EvaluationModelProviderPlugin` | 管理代理模型训练/推理接口与版本 | 补“模型生命周期治理”；让代理策略可持续而非一次性脚本 | `MAS`、`Surrogate` 场景 |
| `TimeoutBudgetPlugin` | 对事件/评估施加超时与预算边界 | 补“资源约束语义”；将理论流程变成可控生产执行 | `AsyncEvent`、`MAS`、外部仿真问题 |
| `AsyncEventHubPlugin` | 标准化事件入口、重试、回压与分发 | 补“异步事件编排能力”；对应事件驱动优化场景的运行语义 | `AsyncEventDrivenAdapter` |
| `SensitivityAnalysisPlugin` | 追踪扰动敏感度与不光滑区行为 | 补“稳健性诊断”；对应 nonsmooth/DFO 场景下的判据支持 | `TR-NonSmooth`、`TR-DFO` |

面试一句话总结：

> 我们不是“为了堆组件而堆组件”，而是按缺口补位：`Pipeline/Archive/Checkpoint` 先补可行性与可恢复，`Trace/Report/Benchmark` 再补可解释与可验证，`Surrogate/Orchestrator/EventHub` 最后补昂贵评估与复杂编排。这就是从轻量算法核走向经典工程闭环的路径。

与后续章节关系：

- `22.6`：回答“每个 adapter 默认怎么配”。
- `22.7`（本节）：回答“为什么这么配、补了什么功能”。
- `24.x`：回答“这些组件按什么顺序接线、怎么落地运行”。

---

# 23. 口述模板：把“可恢复性”讲得工程化

你可以用这个句式（30 秒）：

> 我们的很多 adapter 是工程化轻量核，但不是弱实现。核心搜索逻辑保持简洁，通过 `state_recovery_level + get_state/set_state` 声明并实现恢复能力，再用 `RepresentationPipeline`、`CheckpointResumePlugin`、`ParetoArchivePlugin` 和控制器型 adapter 组合，把流程还原到更经典、更完整的做法。这种分层让我们能按项目成本逐步升级复杂度，而不是一开始就维护一个难以演进的“全量巨型算法类”。

---

# 24. 具体怎么组合（实战接线手册）

这章专门回答“不是知道组件名，而是怎么把它们接起来”。

## 24.1 通用接线顺序（先后不能乱）

建议固定按 8 步：

1. **先定问题**：`problem`（目标/约束/维度）
2. **再定表示**：`RepresentationPipeline`（init/mutate/repair/crossover）
3. **选主 adapter**：单一算法或控制器算法
4. **选 solver 类**：`ComposableSolver` / `EvolutionSolver` / 业务特化 solver
5. **补评估能力**：并行、代理评估、多保真等
6. **补恢复能力**：`CheckpointResumePlugin`
7. **补观测能力**：`DecisionTracePlugin`、`BenchmarkHarnessPlugin`、`ModuleReportPlugin`
8. **补输出能力**：`ParetoArchivePlugin`、业务导出插件

面试口述要点：

> 我们先定“搜索语义”（adapter），再补“运行能力”（plugins/stores），最后补“业务可行性”（pipeline repair）。

## 24.2 组合模式 A：单算法稳态版（最容易落地）

适用：先做可靠 baseline。

- 主算法：`NSGA2Adapter` / `DEAdapter` / `VNSAdapter` 其一
- 必选能力：`CheckpointResumePlugin` + `BenchmarkHarnessPlugin`
- 多目标建议再加：`ParetoArchivePlugin`

推荐组合：

- `NSGA2Adapter` + `RepresentationPipeline` + `ParetoArchivePlugin` + `CheckpointResumePlugin`

收益：

- 结构最稳、最容易定位问题
- 适合作为后续控制器组合的参照系

主补位功能（一句话）：**先补“可恢复 + 可比较 + 可行性”三件套**，把单算法从“能跑”提升到“可复现实验基线”。

## 24.3 组合模式 B：全局探索 + 局部精修（二段式）

适用：多峰问题，既要覆盖又要收敛。

做法 1（阶段切换）：

- 前期：`DE` 或 `MOEAD`（探索）
- 后期：`VNS` / `PatternSearch` / `TrustRegionDFO`（精修）

做法 2（同代协作）：

- `StrategyRouterAdapter`
- role1=explorer（`MOEAD`/`DE`）
- role2=exploiter（`VNS`/`TrustRegion*`）

建议插件：

- `DecisionTracePlugin`（看阶段切换是否合理）
- `BenchmarkHarnessPlugin`（看探索/精修收益曲线）

主补位功能（一句话）：**补“探索-开发分工与切换证据”**，避免只探索不收敛或只局部不覆盖。

## 24.4 组合模式 C：多目标“经典还原增强版”

适用：面试官追问“怎么接近论文流程”。

推荐：

- 主算法：`NSGA2` 或 `NSGA3` 或 `SPEA2`
- 外部前沿：`ParetoArchivePlugin`
- 恢复回放：`CheckpointResumePlugin`
- 观测：`ModuleReportPlugin` + `DecisionTracePlugin`

口述重点：

> 算法核心仍在 adapter，外部档案、恢复、观测由插件补齐，形成工程等效的“经典流程闭环”。

主补位功能（一句话）：**补“外部档案 + 回放 + 过程可解释”**，把 many-objective 结果从“单次输出”升级为“可审计前沿”。

## 24.5 组合模式 D：分解 + 协同控制（MOEA/D 升级版）

适用：many-objective 或需要“组织化搜索”。

推荐：

- explorer：`MOEADAdapter`
- exploiter：`VNSAdapter` 或 `TrustRegionMODFOAdapter`
- 控制器：`StrategyRouterAdapter`

建议参数策略：

- 先固定 `phase_schedule`，后启用 `adapt_weights`
- 先小 batch 验证角色互补，再扩容

建议插件：

- `DecisionTracePlugin`（解释权重变化）
- `ParetoArchivePlugin`（稳定输出前沿）

主补位功能（一句话）：**补“分解子问题协同调度层”**，把多策略并存升级为有组织的角色编排。

## 24.6 组合模式 E：代理模型闭环（MAS/Surrogate）

适用：评估昂贵（仿真、外部求解器）。

推荐组合：

- 主搜索：`MASAdapter`（或任意 adapter）
- 评估层：`SurrogateEvaluationProviderPlugin`
- 模型层：`EvaluationModelProviderPlugin`
- 保护层：`TimeoutBudgetPlugin`（防评估超时）

关键点：

- 一定保留“真评估回注”路径，不能全程只靠代理
- 在 `BenchmarkHarness` 里记录 surrogate 命中率和误差漂移

主补位功能（一句话）：**补“昂贵评估可执行性”**，用代理降成本，同时用真评估回注防止模型漂移失真。

## 24.7 组合模式 F：事件驱动编排

适用：任务到达不均匀、外部系统事件触发计算。

推荐组合：

- 控制器：`AsyncEventDrivenAdapter`
- 事件总线：`AsyncEventHubPlugin`
- 预算约束：`TimeoutBudgetPlugin`
- 可观测：`DecisionTracePlugin`

落地提示：

- 先把事件 schema 定死（事件类型、payload、重试语义）
- 再上优先级与回压

主补位功能（一句话）：**补“异步事件运行语义”**，将外部触发型优化纳入统一预算与重试控制。

## 24.8 组合模式 G：图搜索工程版

适用：路径规划、图状态转移问题。

推荐组合：

- 单目标：`AStarAdapter`
- 多目标：`MOAStarAdapter`
- 恢复：`CheckpointResumePlugin`
- 报告：`ModuleReportPlugin`

注意：

- 图搜索成败更多取决于回调质量（邻接、启发、状态哈希）
- adapter 只提供统一运行外壳

主补位功能（一句话）：**补“长路径搜索的恢复与诊断能力”**，让图搜索从算法演示走向工程可持续运行。

## 24.9 一套“可复制”的组合模板（口述版）

你可以直接背这段：

> 我会先用单算法 baseline（例如 NSGA2 + repair pipeline + checkpoint + pareto archive）跑通，再按业务需求升级：如果要探索与开发协作，就上 MultiStrategy，把 MOEAD 放 explorer、VNS 放 exploiter；如果评估昂贵，就加 SurrogateEvaluation 与 EvaluationModel 形成闭环；全程用 DecisionTrace 和 BenchmarkHarness 做可解释监控。这样组合后是工程等效增强，不宣称与论文流程逐项同构，但在可恢复、可观测、可迭代上更适合生产。



