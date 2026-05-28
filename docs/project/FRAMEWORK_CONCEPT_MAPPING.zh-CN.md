# nsgablack / mlblack 概念对齐表

状态：工作草案  
用途：把框架内部命名翻译成机器学习、优化、AutoML、符号学习和实验工程社区更常用的表达。  
边界：本文不替代 API 文档；它用于对外叙事、论文/报告写作、答辩介绍和后续 benchmark 设计。

## 1. 总体定位

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `nsgablack` | black-box optimization framework / multi-objective optimization framework / algorithm configuration framework | 不只是 NSGA 算法库，而是把外层搜索、候选表示、评估链、插件能力、运行记录和项目脚手架统一起来。 |
| `mlblack` | surrogate modeling framework / ML workflow framework / model assembly framework | 不只是训练模型，而是把 schema、numericizer、pipeline、trainer、artifact、audit 和 report 统一为可装配训练流。 |
| `nsgablack -> mlblack` | prediction-decision integration / model-based optimization / learning-augmented optimization / AutoML for inner evaluators | 外层优化搜索决策、结构、预算和配置；内层学习框架执行拟合、代理评估、符号发现和证据产出。 |
| Outer solver / inner evaluation | bilevel optimization / nested optimization / algorithm configuration / hyperparameter optimization | 内层不一定是简单目标函数，可以是完整训练流、符号搜索流或多阶段实验。 |
| 标准脚手架 surface | reproducible experiment surface / application scaffold / workflow entrypoint | 把“跑了哪个入口、挂了哪些组件、产出了什么 artifact”变成可审计记录。 |

## 2. nsgablack 优化侧

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `Solver` | optimization loop / control plane / search orchestrator | 控制生命周期、评估入口、状态管理和插件调度，不把具体算法策略写死。 |
| `Adapter` | search policy / optimizer strategy / algorithm operator | 通过 `propose/update` 解耦搜索策略，可挂 NSGA2、MOEA/D、SPEA2、DE、SA、VNS 等。 |
| `RepresentationPipeline` | encoding/decoding pipeline / genotype-phenotype mapping / repair operator | 候选表示、修复、编码和解码独立于 solver 与 adapter。 |
| `Plugin` | callback / middleware / capability extension / lifecycle hook | 日志、checkpoint、短路评估、runtime 观测、backend 接入都作为能力层挂载。 |
| `Bias` | inductive bias / prior / heuristic guidance / soft constraint | 不是硬约束替代，而是对搜索过程的软引导。 |
| `evaluate_individual` | single-candidate evaluation | 单点评估入口，可被插件或内层 runtime 接管。 |
| `evaluate_population` | batch evaluation / vectorized evaluation | 批量评估入口，强调返回 shape 与候选数量对齐。 |
| `ContextStore` | runtime context / lightweight state store | 存轻量状态、引用、指标和控制信息。 |
| `SnapshotStore` | artifact store / state snapshot / large-object store | population、objectives、trace 等大对象走 snapshot 引用，避免污染 context。 |
| `context_keys` | state schema / typed runtime keys | 用集中 key 管理运行状态，减少隐式字段和字符串漂移。 |
| `context_contracts` | component IO contract / data contract / lifecycle contract | 声明组件需要、提供、修改和缓存哪些上下文字段。 |
| `Catalog` | component registry / discoverability index / model card index | 组件可发现、可筛选，并区分 `default` 与 `framework-core` 口径。 |
| `Project Doctor` | static checker / project health check / lint for framework contracts | 检查脚手架、契约、目录边界和项目健康状态。 |
| `Run Inspector` | experiment inspector / run audit tool | 面向运行记录、上下文、组件装配和 artifact 的诊断入口。 |
| `TaskInnerRuntimeEvaluator` | nested evaluator / inner solver bridge / evaluation backend adapter | 将外层候选映射为内层任务，并把内层结果投影回外层目标。 |
| `Runtime surface tracker` | experiment lineage tracker / run registry | 记录 surface、assembly、run、artifact，使跨框架运行可对比。 |

## 3. mlblack 学习侧

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `TrainFlowSpec` | training workflow spec / experiment config | 用声明式 spec 组织数据、模型、能力和输出。 |
| `run_train_flow` | training pipeline runner / fit-evaluate-persist workflow | 不只 fit，而是包含数据准备、训练、评估、持久化和报告。 |
| `SemanticTrainFlowSpec` | schema-aware training workflow / semantic ML pipeline | 从语义 schema 进入 numericizer，再到 pipeline 和 trainer。 |
| `Numericizer` | feature encoder / tabular encoder / semantic-to-numeric transform | 把语义字段转成模型可用数值表示，是 schema 与模型之间的正式边界。 |
| `Pipeline` | preprocessing pipeline / feature transformation pipeline | 类似 sklearn pipeline，但作为框架装配层的一部分。 |
| `Trainer` | estimator / learner / model family implementation | ridge、xgboost、torch MLP、symbolic trainer 等作为可注册训练器。 |
| `Artifact` | trained model artifact / deployable model object / fitted estimator | 统一 predict、uncertainty、validity、save/load 与 metadata。 |
| `FlowCapability` | callback / plugin / training capability | 生命周期能力，如 checkpoint、resource、report、experiment tracker。 |
| `LifecycleRuntime` | hook dispatcher / workflow lifecycle engine | 管理 flow/stage 事件、capability 调度和 lifecycle report。 |
| `ExperimentOrchestrator` | staged workflow orchestrator / experiment runner | 把实验拆成多个 stage，并记录 stage payload 与 lifecycle report。 |
| `ContextStore + SnapshotStore` | ML runtime state plane / experiment state backend | 和 nsgablack 对齐的状态面，支持 memory/sqlite/redis 等后端。 |
| `ModelSpec` | model subspace spec / target-feature view | 指定某个模型使用哪些 feature 和 target 子空间。 |
| `Experiment tracker` | ML experiment tracking / metric store | 记录 run、event、metric、artifact，类似轻量 MLflow/W&B 思路。 |
| `Report writer` | experiment reporter / artifact summarizer | 将训练结果、指标和配置投影为可读报告。 |

## 4. 符号学习与结构发现

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `symbolic_stagewise` | stagewise symbolic regression / greedy symbolic model building | 分阶段增加 symbolic terms，强调预算、beam 和结构控制。 |
| `orthogonal basis search` | basis function discovery / sparse symbolic regression / dictionary learning | 关注相对正交、残差解释能力和 basis 组合。 |
| `basis consensus` | ensemble model selection / stability selection / consensus clustering | 从多次 symbolic run 中寻找稳定 core basis。 |
| `locked core` | fixed support refinement / warm-start with selected structure | 将稳定 basis 固定或注入后续 refinement，减少搜索漂移。 |
| `exact term recovery` | symbolic recovery accuracy / ground-truth structure recovery | 用于已知真值 benchmark，评估是否找回真实表达式项。 |
| `family-level recovery` | semantic family recovery / equivalence-class recovery | 不只看字符串等价，也看函数族或语义层面的恢复。 |
| `phase-equivalent recovery` | equivalence-aware symbolic matching | 处理周期、相位、等价表达式导致的“形式不同但意义接近”。 |
| `residual-guided search` | residual fitting / boosting-like symbolic search | 用当前模型解释不了的残差来引导下一批结构候选。 |
| `path memory` | search memory / tabu memory / prior over structures | 把历史搜索路径、候选和效果变成下一轮搜索的先验。 |
| `semantic novelty` | diversity regularization / novelty search / anti-redundancy | 候选不仅要拟合目标，也要避免语义重复。 |
| `SymbolicOuterEvaluationProxy` | black-box evaluator for symbolic candidates / surrogate evaluation protocol | 给外层 solver 暴露统一 evaluate 接口，而不泄露内部训练细节。 |

## 5. 预测-决策联动

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `mlblack evaluation proxy` | surrogate model / learned evaluator / response surface | 可以是完整训练流或符号搜索流，不只是一个静态回归器。 |
| 外层搜索 inner config | hyperparameter optimization / algorithm configuration / AutoML | nsgablack 搜 trainer 参数、basis 参数、预算、结构开关和资源策略。 |
| 外层搜索 representation program | neural architecture search / program synthesis / feature construction search | 候选可以是组件组合、表征程序或符号结构。 |
| 外层多目标目标向量 | multi-objective model selection | 同时优化误差、结构恢复、复杂度、稳定性、成本等目标。 |
| inner result projection | metric projection / objective shaping / scalarization interface | 将内层丰富报告压成外层可优化的 objectives/violations。 |
| resource context 注入 | resource-aware optimization / budgeted learning / constrained HPO | 外层负责预算和资源边界，内层遵守注入的资源上下文。 |
| runtime summary 打印生效配置 | experiment audit / reproducibility report | 让资源、组件、后端和命名空间可审计。 |

## 6. 实验治理与可复现

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `SurfaceRecord` | experiment entry record / workflow surface record | 说明跑的是哪个正式入口和脚手架 surface。 |
| `AssemblyRecord` | component composition record / configuration manifest | 说明实际挂载了哪些 solver、trainer、pipeline、plugin、bias。 |
| `RunRecord` | experiment run record | 记录一次具体运行的 subject、signature、状态和结果。 |
| `ArtifactRecord` | artifact lineage record | 记录模型、报告、checkpoint、trace 等产物及其来源。 |
| `assembly_signature` | reproducibility hash / configuration fingerprint | 用于比较两次运行是否装配一致。 |
| `artifact_signature` | artifact fingerprint / content identity | 用于追踪产物身份和复现链路。 |
| `replay` | experiment replay / deterministic rerun | 通过配置、snapshot、artifact 和 lineage 尽可能复现运行。 |
| `strict / soft-error` | fail-fast mode / warning mode | 外部资源或插件失败时可选择严格失败或软错误记录。 |
| `doctor --strict` | contract test / structural validation | 在运行前检查脚手架和契约，减少隐藏错误。 |

## 7. 和常见框架的关系

| 参照对象 | 社区定位 | 你的关系 |
| --- | --- | --- |
| `pymoo` / `DEAP` | evolutionary optimization libraries | nsgablack 更强调工程生命周期、插件、snapshot、catalog 和跨框架评估，而不只是算法实现。 |
| `Optuna` / `Ray Tune` | HPO / experiment tuning frameworks | nsgablack 可以覆盖 HPO，但候选表示、内层 solver、符号结构和多目标治理更通用。 |
| `sklearn Pipeline` | preprocessing + estimator pipeline | mlblack 借鉴 pipeline 思路，但加入 schema、numericizer、artifact、capability lifecycle 和运行审计。 |
| `MLflow` / `W&B` | experiment tracking | 你的 runtime surface 更贴近框架内部 assembly 和 artifact lineage，可作为轻量追踪层。 |
| `PySR` / symbolic regression tools | symbolic regression engine | mlblack 的 symbolic 部分不只是表达式搜索，还包含 basis consensus、locked core、outer orchestration 和 audit surface。 |
| AutoML / NAS 系统 | automatic model/architecture search | 你的外层 nsgablack 能搜索模型族、训练预算、符号结构、表征组件和决策参数。 |

## 8. 对外表达建议

可以把两个框架合起来描述为：

> `nsgablack` is the outer decision and search orchestration layer; `mlblack` is the inner learning, surrogate, symbolic modeling, artifact and audit layer. Together they form a reproducible prediction-decision integration stack.

中文可以说：

> nsgablack 负责外层搜索、决策、预算和运行治理；mlblack 负责内层拟合、代理评估、符号结构发现、artifact 与审计。两者通过 evaluation proxy、resource context、run surface 和 artifact contract 连接。

## 9. 后续可补的证据表

| 需要证明的问题 | 建议实验 |
| --- | --- |
| 外层搜索是否优于固定 inner config | 对比 fixed config、random search、grid search、Bayesian optimization、nsgablack outer search。 |
| consensus 是否提升符号结构稳定性 | 多 seed、不同噪声、不同样本量下比较 single run 与 consensus/locked core。 |
| artifact/replay 是否真的提升可复现性 | 固定 run surface 后重跑，检查 assembly signature、metrics 和 artifact 差异。 |
| 多目标是否必要 | 单目标 RMSE、RMSE+复杂度、RMSE+结构恢复+复杂度三组消融。 |
| resource context 是否可审计 | 比较不同 worker/GPU/budget 配置下 runtime summary 与 run record 的一致性。 |

