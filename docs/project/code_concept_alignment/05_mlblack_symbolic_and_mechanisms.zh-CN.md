# 05. mlblack 符号学习、机制组件与结构发现对齐

覆盖路径：

- `core/symbolic/*`
- `core/symbolic/feature_space/*`
- `core/mechanisms/*`
- `core/orthogonal_source/*`
- `core/symbolic/benchmark/*`
- `my_project/known_relation_symbolic/*`
- `my_project/orthogonal_source_*/*`

## 1. 符号学习主干

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `symbolic_dsl.py` | symbolic expression DSL / program grammar | 表达式语法空间。 | 符号模型不是字符串拼接，而是有 DSL 边界。 |
| `symbolic_gradient.py` | symbolic differentiation | 符号梯度。 | 梯度信号用于机制诊断和候选修正。 |
| `gradient_parser.py` | gradient signal parser | 从梯度/残差中提取结构线索。 | 把拟合误差转成结构搜索线索。 |
| `gradient_correction.py` | gradient-based correction / structure refinement | 梯度修正。 | 介于可微优化和符号结构搜索之间。 |
| `structure_optimizer.py` | symbolic structure optimizer | 结构优化器。 | 控制 symbolic candidate 的结构层搜索。 |
| `symbolic_structure_search.py` | symbolic regression search / program search | 符号结构搜索。 | 可被外层 nsgablack 接管为正式搜索问题。 |
| `truth_contracts.py` | ground-truth benchmark contract | 真值表达式契约。 | 支持 exact/family/phase 等恢复指标。 |
| `structure_contract.py` | structure schema / expression contract | 结构描述协议。 | 让符号结构可记录、比较、复现。 |
| `structure_metadata.py` | symbolic metadata | 结构元数据。 | 支持 artifact/report/audit。 |

## 2. Stagewise 与 Orthogonal Trainer

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `SymbolicStagewiseSurrogateTrainer` | stagewise symbolic regression | 分阶段加项。 | 把 symbolic search 约束在 trainer family 语义内。 |
| `SymbolicOrthogonalTrainer` | orthogonal basis symbolic regression | 正交 basis 发现与拟合。 | 强调 basis 稳定性、相对正交与结构恢复。 |
| `SymbolicOrthogonalIntervalTrainer` | interval symbolic regression | 区间预测符号模型。 | output head 从 point 扩展到 interval。 |
| `stage_head_protocol.py` | output head protocol | stage/head 语义协议。 | 区分 function family 和 output semantics。 |
| `trainer_state_io.py` | trainer state persistence | symbolic trainer 状态保存。 | 与 artifact/report 分离。 |

## 3. Orthogonal basis 与 consensus

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `orthogonal_basis_search.py` | basis function discovery / dictionary learning | 搜索候选 basis。 | 不只看拟合误差，也看残差收益、语义新颖性、正交性。 |
| `basis_consensus.py` | stability selection / ensemble consensus | 多次运行后选稳定 basis。 | 用共识机制缓解符号搜索随机性和等价表达漂移。 |
| `locked core` | fixed support refinement / warm-start selected support | 固定稳定 core 后 refinement。 | 把多次搜索形成的结构先验注入下一阶段。 |
| `basis_class_id` | equivalence class id | basis 等价类身份。 | 不只按字符串比较表达式。 |
| `representative_expression` | canonical representative | 等价类代表表达式。 | 有利于 dashboard 和报告。 |
| `semantic_family` | semantic equivalence family | 语义族。 | 支持 family-level recovery。 |
| `core_min_support_rate` | stability threshold | 共识支持率阈值。 | 类似 stability selection 的入选阈值。 |

## 4. Feature space 子系统

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `feature_space/candidate_pool.py` | candidate pool / dictionary | 候选函数池。 |
| `feature_space/generation_grammar.py` | grammar-based generation | 按语法生成候选。 |
| `feature_space/primitive_registry.py` | primitive/operator registry | 基础算子注册。 |
| `feature_space/feature_bundle.py` | feature bundle / representation bundle | 特征组合包。 |
| `feature_space/objective_policy.py` | scoring policy / objective shaping | 候选评分策略。 |
| `feature_space/evaluation_cache_key.py` | cache key / memoization identity | 评估缓存身份。 |
| `feature_space/cv_splitter.py` | cross-validation splitter | 交叉验证切分。 |
| `feature_space/fold_report.py` | fold-level report | fold 级报告。 |
| `feature_space/regime_router.py` | regime router / mixture-of-experts gate | regime 路由。 |
| `feature_space/branch_evaluator.py` | branch evaluator / conditional model path | 分支评估。 |
| `feature_space/temporal_feature_pack.py` | temporal features / lag features | 时间特征包。 |
| `feature_space/regime_feature_pack.py` | regime-specific feature pack | 分 regime 特征包。 |
| `feature_space/subset_descriptor.py` | feature subset descriptor | 特征子集描述。 |

差异点：这些组件把符号学习从“表达式搜索”扩展为“特征空间构造、候选治理、评估缓存、CV 报告、regime/branch 路由”的完整机制层。

## 5. Mechanism 层

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `core/mechanisms/protocols.py` | mechanism protocol | 机制接口协议。 | 避免机制只能藏在 trainer 内部。 |
| `family_bindings.py` | mechanism-family binding | 机制绑定到 family。 | 区分 optional/bound/defining 的思路。 |
| `runtime.py` | mechanism runtime | 机制运行时。 | 机制可被生命周期和 catalog 感知。 |
| `search_mechanism_contract.py` | search mechanism contract | 搜索机制契约。 | 明确哪些结构搜索应交给 nsgablack 外层。 |

## 6. Orthogonal source

| 代码叫法 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `core/orthogonal_source/layer.py` | orthogonal source layer / source governance | 管理多个信息源或表征源。 |
| `orthogonal_source_image_classification` | representation source search / source ensemble | 图像分类表征源搜索案例。 |
| `orthogonal_source_baseline` | baseline source pipeline | 源治理 baseline。 |

对齐说明：orthogonal source 类似 representation ensemble、multi-view learning、source selection、feature source governance 的组合。

## 7. Benchmark 与 outer proxy

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `benchmark/contracts.py` | benchmark problem contract | benchmark 契约。 | 真值、数据、指标可结构化。 |
| `bundle_pipeline.py` | benchmark data bundle builder | 构建数据和真值包。 | 评估可复现。 |
| `outer_proxy.py` | outer evaluation proxy | 给外层 optimizer 的评估接口。 | nsgablack 不需要知道 mlblack 内部细节。 |
| `SymbolicOuterSearchCandidate` | symbolic candidate payload | 外层候选结构。 | 可包含 basis、chart、head、branch 等复杂结构。 |
| `SymbolicOuterEvaluationResult` | evaluation result payload | 返回 objectives/violations/metrics/artifacts/audit。 | 比普通 objective value 更富含证据。 |

## 8. 结构恢复指标

| 你的指标/字段 | 社区常用叫法 | 含义 |
| --- | --- | --- |
| `exact_term_recovery_score` | exact symbolic recovery | 是否找回真实表达式项。 |
| `phase_equivalent_term_recovery_score` | equivalence-aware recovery | 周期/相位等价下是否恢复。 |
| `family_level_term_recovery_score` | semantic family recovery | 是否恢复到同一语义族。 |
| `test_rmse` | predictive error | 测试误差。 |
| `outer_objective_score` | scalarized objective / model selection score | 外层可用综合分数。 |
| `basis evolution` | structure evolution trace | basis 如何在多阶段演化。 |

## 9. 这一层的核心价值

| 传统写法 | 你的写法 |
| --- | --- |
| 符号回归只输出一个 best expression。 | 输出 basis、等价类、共识、locked core、leaderboard、artifact。 |
| 搜索稳定性靠多跑几次人工看。 | basis consensus 和 support rate 正式化。 |
| 只比较字符串表达式。 | exact/family/phase 多层恢复。 |
| 结构搜索藏在 trainer 内部。 | 可通过 outer proxy 交给 nsgablack 外层搜索。 |

