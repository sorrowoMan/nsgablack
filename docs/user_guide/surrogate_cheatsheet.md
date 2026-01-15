# 代理模块速查表

下面是代理模块的入口类、关键配置与适用场景，便于快速选择和组合。

## 入口类与用途

| 入口/位置 | 功能 | 关键配置（常用） | 什么时候使用 |
| --- | --- | --- | --- |
| `SurrogateManager`（`surrogate/manager.py`） | 代理核心管理器：训练数据管理、预测、不确定性、缓存、自动更新、保存/加载 | `model_type`、`feature_extractor`、`strategy`、`auto_save`、`save_interval`、`scaler_method`、`model_dir` | 你要把代理“嵌入别的流程”（单机/多智能体/自定义循环）时 |
| `FeatureExtractorFactory`（`surrogate/features.py`） | 特征提取器工厂，提供多种特征工程策略 | `extractor_type`、`method`、`n_components`、`variance_ratio`、`degree`、`pipeline`、`problem_type` | 需要调整特征表达（降维/交互/问题特定特征）时 |
| `SurrogateStrategyFactory`（`surrogate/strategies.py`） | 主动学习策略（何时做真实评估） | `strategy`：`random/adaptive/bayesian/multi` | 预算有限、希望“选点更聪明”时 |
| `SurrogateTrainer`（`surrogate/trainer.py`） | 端到端训练流程：采样→训练→检测→复训（支持checkpoint） | `initial_samples`、`batch_size`、`max_iterations`、`evaluation_budget`、`checkpoint_interval`、`checkpoint_dir` | 要把代理训练流程独立跑通、可恢复训练时 |
| `SurrogateEvaluator`（`surrogate/evaluators.py`） | 评估代理质量与速度（对比基准/策略） | 评估函数参数 | 需要做代理质量对比或基准测试时 |
| `SurrogateAssistedNSGAII`（`solvers/surrogate.py`） | 代理辅助NSGA-II（预算控制、在线更新） | `surrogate_type`、`real_eval_budget`、`initial_samples`、`update_interval`、`real_evals_per_gen` | 想快速跑“代理+NSGA”的标准流程时 |
| `SurrogateUnifiedNSGAII`（`solvers/surrogate_interface.py`） | 统一接口：预筛选/评分偏置/替代评估 | `prefilter`、`score_bias`、`surrogate_eval`、`constraint_eval`、`min_training_samples` | 需要精细控制代理介入方式时 |
| `SurrogateScoreBias`（`multi_agent/bias/surrogate_score.py`） | Advisor评分偏置（代理预测→分数） | `weight`、`sign`、`objective_weights`、`use_uncertainty`、`min_samples` | 多智能体中把代理作为“建议者评分器”时 |
| `SurrogateMonteCarloOptimizer`（`solvers/monte_carlo.py`） | MC + 代理 + 进化优化 | `mc_samples`、`surrogate_type`、`initial_samples`、`max_iterations`、`samples_per_iter`、`mode` | 随机/不确定性问题，MC评估很贵时 |

## 特征提取器可选类型（`feature_extractor`）

- `identity`：原样输入（默认）
- `scaling`：标准化/归一化
- `pca`：降维
- `polynomial`：多项式特征
- `interaction`：交互特征
- `pipeline`：多步管道
- `problem_specific`：问题特定特征（如 scheduling/design/tsp）

## 快速选型建议

- **预算极紧/评估很贵**：`SurrogateAssistedNSGAII`
- **需要强可控介入**：`SurrogateUnifiedNSGAII`
- **多智能体的建议者评分**：`SurrogateScoreBias`
- **只想跑训练闭环/可恢复**：`SurrogateTrainer`
- **随机/不确定性目标**：`SurrogateMonteCarloOptimizer`

## 代理控制偏置（`bias/surrogate`）

- `PhaseScheduleBias`：分阶段切换代理策略（预热/混合/收敛）。
- `UncertaintyBudgetBias`：用不确定性动态调真实评估比例。

## 依赖提示

代理模块默认依赖 `scikit-learn`。未安装时部分模型与特征工程会不可用。
