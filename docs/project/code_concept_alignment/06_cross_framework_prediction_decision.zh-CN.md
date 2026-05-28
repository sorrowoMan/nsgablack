# 06. nsgablack / mlblack 跨框架预测-决策联动对齐

覆盖路径：

## nsgablack 侧

- `core/nested_solver.py`
- `plugins/solver_backends/mlblack_symbolic_consensus_backend.py`
- `examples/cases/mlblack_symbolic_consensus_scaffold/*`
- `my_project/etf_lane_outer_search/*`
- `my_project/phi_bundle_image_search/*`
- `my_project/learnable_conv_component_search/*`

## mlblack 侧

- `core/symbolic/benchmark/outer_proxy.py`
- `my_project/known_relation_symbolic/mlblack_side/evaluation_proxy.py`
- `my_project/known_relation_symbolic/nsgablack_side/interfaces.py`
- `my_project/etf_quant_interval_proxy/*`
- `my_project/orthogonal_source_image_classification/*`
- `core/execution/*`

## 1. 总体联动模型

| 你的叫法 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `nsgablack outer solver` | outer optimizer / decision optimizer | 搜索外层决策、结构、预算、配置。 |
| `mlblack inner evaluation proxy` | learned evaluator / surrogate workflow / inner experiment | 执行拟合、符号搜索、模型评估并返回指标。 |
| `outer candidate` | algorithm configuration / architecture candidate / program candidate | 外层候选不一定是数值点，也可以是组件组合或结构程序。 |
| `inner result projection` | objective projection / metric-to-objective mapping | 把内层丰富报告投影成外层 objectives/violations。 |
| `resource context` | resource grant / budget context | 外层授权资源，内层遵守。 |
| `run surface` | experiment surface / reproducibility surface | 两边都记录运行入口、装配、产物。 |

## 2. nsgablack 嵌套求解接口

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `InnerSolveRequest` | inner evaluation request | 候选、generation、individual、budget、metadata。 | 将外层上下文正式传给内层。 |
| `InnerSolveResult` | inner evaluation response | objectives、violation、status、cost、payload。 | 内层不只返回一个分数。 |
| `InnerRuntimeEvaluator` | nested evaluator / bilevel bridge | 构建并运行内层 solver。 | 支持 parent contract 和 budget tracking。 |
| `TaskInnerRuntimeEvaluator` | task-based inner runtime | 支持 build_inner_task / build_inner_problem / backend runner。 | 适合把 mlblack flow 当成内层任务。 |
| `evaluate_from_inner_result` | result projector | problem 将 inner payload 转成外层目标。 | 投影逻辑归 problem，不归 backend 或 solver。 |
| `on_inner_guard` | runtime guard / budget gate | 插件可拦截内层调用。 | 外层可审计和限制内层评估。 |
| fallback penalty | failed evaluation penalty | 内层失败时返回惩罚。 | soft-error 和 strict 策略可区分。 |

## 3. mlblack outer proxy 接口

| 代码叫法 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `SymbolicOuterSearchCandidate` | symbolic/program candidate | 外层传入的符号候选。 |
| `SymbolicOuterEvaluationResult` | structured evaluation result | objectives/violations/metrics/artifact_refs/audit。 |
| `SymbolicOuterEvaluationProxyProtocol` | evaluator protocol | 外层评估协议。 |
| `evaluate_individual` | single candidate scoring | 单候选评估。 |
| `evaluate_population` | batch candidate scoring | 批量评估。 |
| `KnownRelationEvaluationProxy` | project-specific proxy | 已知真值符号 benchmark 的代理评估器。 |

差异点：mlblack 侧 proxy 只暴露评估能力，不反过来接管 nsgablack 的 population、Pareto、outer budget。

## 4. symbolic consensus 联动

| nsgablack 侧机制 | mlblack 侧机制 | 社区对应概念 | 联动含义 |
| --- | --- | --- | --- |
| `MlblackSymbolicConsensusOuterProblem` | symbolic orthogonal trainer / basis consensus | algorithm configuration + symbolic regression | 外层搜索 symbolic consensus 的预算和结构参数。 |
| `_decode_plan(x)` | trainer params overrides | hyperparameter decoding | 外层向量解码成内层 symbolic 参数。 |
| `build_inner_problem` | benchmark bundle + run label | inner task construction | 为每个候选构造内层任务。 |
| `MlblackSymbolicConsensusBackend.solve` | unlocked runs + consensus + locked refinement | multi-run stability selection | 内层执行完整符号共识流程。 |
| `evaluate_from_inner_result` | recovery metrics + RMSE | multi-objective model selection | exact/family/RMSE/complexity 组成外层目标。 |
| runtime surface tracker | experiment tracker / artifact record | lineage tracking | 把内层阶段和外层运行都变成可审计 surface。 |

## 5. component override 联动

| 你的场景 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `learnable_conv_component_search` | component-level architecture search / NAS-lite | nsgablack 搜 mlblack learnable conv 组件参数。 |
| `phi_bundle_image_search` | representation program search / feature source search | nsgablack 搜 mlblack 表征对象和 source 组合。 |
| `etf_lane_outer_search` | strategy configuration search / model selection under walk-forward evaluation | nsgablack 搜 ETF 多策略 lane 配置，mlblack 做 walk-forward proxy。 |

核心点：外层候选不是“模型权重”，而是训练流、表征、组件、预算、结构的可配置自由度。

## 6. 资源边界

| 你的规则 | 社区常用叫法 | 含义 |
| --- | --- | --- |
| `nsgablack L0 owns inter-solver scheduling` | outer resource scheduler | 外层管 population/solver fanout/outer budget。 |
| `mlblack L0 owns intra-evaluation backend` | inner training backend | 内层管单次训练/评估内部资源。 |
| `ResourceContext` injection | resource grant propagation | 外层资源上下文注入内层。 |
| effective context report | resource audit | 打印并记录实际生效的 backend/device/workers。 |

## 7. 预测-决策统一的准确表达

不要说：

> 我把机器学习和优化放到一起。

更准确说：

> 我把学习系统作为可审计的内层评估器，把优化系统作为可治理的外层决策搜索器。学习负责构建和评估世界模型，优化负责搜索结构、预算、组件和决策；二者通过标准候选、评估结果、资源上下文和 artifact/run surface 对齐。

英文：

> The learning framework acts as an auditable inner evaluator, while the optimization framework acts as a governed outer decision/search layer. Learning builds and scores models; optimization searches structures, budgets, components, and decisions. They are aligned through candidate protocols, evaluation result payloads, resource contexts, and run/artifact surfaces.

## 8. 可证明的研究命题

| 命题 | 对应实验 |
| --- | --- |
| 外层搜索 inner symbolic budget 能提升结构恢复稳定性。 | fixed config vs random search vs nsgablack outer search。 |
| consensus + locked core 比单次 symbolic search 更稳定。 | 多 seed、多噪声、多样本量下的 recovery 方差。 |
| 资源上下文能避免 nested run 的黑盒资源漂移。 | 比较配置资源与 runtime report/effective context。 |
| 多目标选择比单 RMSE 更能保留可解释结构。 | RMSE-only vs RMSE+complexity vs RMSE+recovery+complexity。 |
| artifact/run surface 能提高复现和诊断能力。 | 重跑同一 assembly signature，比较 artifact 和 metrics drift。 |

## 9. 这一层的核心价值

| 传统写法 | 你的写法 |
| --- | --- |
| HPO 只调几个超参数。 | 外层可搜结构、组件、预算、表征和符号机制。 |
| 内层模型训练只返回分数。 | 返回 metrics、artifact refs、audit、stage reports。 |
| 资源控制靠脚本参数。 | ResourceContext 传递并审计。 |
| 外层优化不知道内层过程。 | run surface / artifact surface 记录内外层链路。 |

