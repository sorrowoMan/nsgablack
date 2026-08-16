# 02. nsgablack 算法策略、候选表示与偏置对齐

覆盖路径：

- `adapters/algorithm_adapter.py`
- `adapters/*/adapter.py`
- `representation/base.py`, `representation/*.py`
- `bias/core/*`, `bias/domain/*`, `bias/algorithmic/*`, `bias/surrogate/*`
- `utils/extension_contracts.py`

## 1. Adapter 总契约

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `AlgorithmAdapter` | optimizer strategy / search policy | 优化策略基类。 | 只管 propose/update，不管 solver 生命周期和评估路径。 |
| `propose(solver, context)` | ask / candidate proposal | 产生候选解。 | 允许多种算法共享同一个 solver runtime。 |
| `update(solver, candidates, feedback, context)` | tell / feedback assimilation | 根据 `feedback=(objectives, violations)` 更新内部状态。 | 把评估结果作为正式反馈流，而不是算法内部私算。 |
| `setup/teardown` | lifecycle hooks | 算法策略挂载/卸载。 | 生命周期存在但弱化，主生命周期仍归 solver。 |
| `get_state/set_state` | checkpointable optimizer state | adapter 状态恢复。 | checkpoint 可恢复算法策略，而不只恢复 solver 字段。 |
| `get_population/set_population` | population state IO | 支持插件或 checkpoint 写回种群。 | 运行态 population 归属可在 adapter 和 solver 间对齐。 |
| `get_context_contract` | component IO contract | 声明 context/artifact/phase 依赖。 | 让算法策略也能被 doctor/catalog 审计。 |
| `get_runtime_context_projection` | runtime telemetry projection | 暴露 adapter 运行切片。 | 日志/UI 不需要读 adapter 私有字段。 |
| `CompositeAdapter` | ensemble/portfolio optimizer / hybrid strategy | 合并多个 adapter 候选，并分发反馈。 | 支持多策略组合而不是写一个超级算法。 |

## 2. 具体 Adapter 家族

| 代码路径 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `adapters/nsga2/adapter.py` | NSGA-II / Pareto evolutionary search | 多目标进化搜索。 | 作为 adapter 插入控制平面，而不是 solver 主体。 |
| `adapters/nsga3/adapter.py` | NSGA-III / reference-point MOEA | 参考点多目标搜索。 | 可和相同评估/插件/snapshot 协议复用。 |
| `adapters/moead/adapter.py` | MOEA/D / decomposition-based MOEA | 分解式多目标优化。 | decomposition 只是策略层，不改变 problem/evaluation 接口。 |
| `adapters/spea2/adapter.py` | SPEA2 / strength Pareto EA | 基于 strength 的 Pareto 搜索。 | 与 NSGA 系列并列为可替换策略。 |
| `adapters/differential_evolution/adapter.py` | Differential Evolution | 差分变异和选择。 | 可服务黑箱连续优化，也可通过 representation 进入混合表示。 |
| `adapters/simulated_annealing/adapter.py` | Simulated Annealing | 单轨迹随机局部搜索。 | 和 population EA 使用同一 ask-tell 反馈协议。 |
| `adapters/vns/adapter.py` | Variable Neighborhood Search | 多邻域局部搜索。 | 邻域策略与 solver 生命周期分离。 |
| `adapters/pattern_search/adapter.py` | pattern/direct search | 无导数模式搜索。 | 适合 expensive black-box 与约束场景。 |
| `adapters/trust_region_*` | trust-region derivative-free optimization | 信赖域无导数优化。 | 可作为局部 refinement adapter 接入多策略系统。 |
| `adapters/astar`, `moa_star` | graph search / A* / multi-objective A* | 离散状态空间搜索。 | 说明 adapter 抽象不只服务进化算法。 |
| `adapters/multi_strategy`, `serial_strategy`, `role_adapters` | algorithm portfolio / strategy scheduler | 策略组合、串行策略、角色化 adapter。 | 开始接近 algorithm configuration 和 hyper-heuristics。 |

对外表达：

> Adapters are interchangeable search policies under an ask-tell contract. This makes evolutionary algorithms, local search, graph search, and trust-region methods share one runtime surface.

## 3. Representation Pipeline

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `RepresentationPipeline` | genotype-phenotype mapping / encoding pipeline | 候选表示流转管线。 | adapter 不直接拥有业务表示细节。 |
| `encoder.encode/decode` | encoding/decoding transform | 表示空间与问题空间转换。 | 让连续、离散、图、矩阵、排列等候选统一进入 solver。 |
| `repair` | repair operator / projection / feasibility restoration | 修复候选满足约束或结构合法性。 | repair 是兜底，不承载业务策略搜索。 |
| `initializer` | initialization policy | 候选初始化。 | 支持 weighted initialization 与多初始化器。 |
| `mutator` | mutation operator | 候选扰动。 | 可以被 adapter 或 representation 复用。 |
| `crossover` | recombination operator | 父代重组。 | 进化操作不必写死在具体 adapter 中。 |
| `ParallelRepair` | parallel repair / batch feasibility projection | 批量并行修复。 | 支持 thread/process/fallback/strict，带错误记录。 |
| `transactional/protect_input/copy_context/threadsafe` | defensive execution / transactional transform | 表示管线安全开关。 | 关注工程可靠性，而不只是算法算子。 |
| `get_context_contract` | representation IO contract | 汇总子组件 context 契约。 | representation 组件也可被审计和 catalog 化。 |

## 4. 表示类型

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `representation/continuous.py` | continuous vector representation | 连续优化变量。 |
| `representation/integer.py` | integer/discrete representation | 整数变量。 |
| `representation/binary.py` | binary mask / bitstring representation | 选择、开关、mask。 |
| `representation/permutation.py` | permutation encoding | 排序、路径、调度顺序。 |
| `representation/matrix.py` | matrix/tensor-like encoding | 矩阵结构候选。 |
| `representation/graph.py` | graph encoding | 图结构、网络结构或拓扑候选。 |
| `representation/dynamic.py` | dynamic representation | 运行时可变表示。 |
| `representation/context_mutators.py` | context-aware mutation | 依据 runtime context 改变扰动。 |
| `representation/constraints.py` | feasibility constraints / repair helpers | 表示层约束处理。 |

## 5. Bias 系统

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `BiasModule` / `BaseBias` | inductive bias / prior / heuristic | 软引导搜索。 | 作为可插拔层，而不是散落在算法里。 |
| `bias/core/registry.py` | bias registry | 偏置发现与创建。 | 偏置可以 catalog 化、组合化。 |
| `bias/core/manager.py` | bias manager / policy manager | 多偏置组合管理。 | 支持偏置作为一组运行能力被治理。 |
| `domain bias` | domain prior / expert prior | 业务先验。 | 业务知识不硬塞 repair 或 adapter。 |
| `algorithmic bias` | search heuristic / metaheuristic guidance | 算法层启发。 | 与 adapter 分开，避免算法类无限膨胀。 |
| `surrogate bias` | model-based guidance / acquisition-like signal | 用代理模型或不确定性引导。 | 是软引导，不等价于直接替代真实评估。 |
| `dynamic penalty` | adaptive penalty method | 约束惩罚动态调整。 | 约束处理可作为偏置能力，而不是目标函数硬编码。 |
| `tabu_search`, `diversity`, `convergence`, `levy_flight`, `pso`, `cma_es` | metaheuristic components | 常见启发式机制。 | 可以作为偏置/组件接入，而不是每个都成为完整 solver。 |

## 6. `extension_contracts`

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `normalize_candidate` | input canonicalization | 候选向量标准化。 | 把第三方/用户组件输出收敛到统一 shape。 |
| `normalize_candidates` | batch canonicalization | 候选批量标准化。 | 降低 adapter 接口错误。 |
| `normalize_bias_output` | bias output contract | 偏置输出规范化。 | 防止 bias 返回形式漂移。 |
| `stack_population` | population tensor assembly | 把候选堆成 population array。 | 在进入评估前统一 shape。 |

## 7. 这一层的核心价值

| 传统写法 | 你的写法 |
| --- | --- |
| 每个算法自己定义变量表示、repair、mutation。 | representation pipeline 统一表示流转。 |
| 业务先验散落在目标函数、repair、算法 if/else 中。 | bias 作为独立软引导层。 |
| 算法实现既生成候选又记录状态又做评估。 | adapter 只管 propose/update。 |
| 多算法组合靠复制代码。 | CompositeAdapter / multi-strategy / role adapter 形成策略组合面。 |
