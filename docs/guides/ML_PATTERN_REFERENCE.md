# ML 模式速查表

每个模式：一句话直觉 + nsgablack/mlblack 能否接 + 怎么接线。不写公式，不写教程。

---

## 回归与预测

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Linear Regression** | f(x) = w·x + b。一切预测的基线 | ✅ 已有 | `model.linear_point` |
| **Ridge / Lasso** | 线性回归 + 惩罚 w 的大小（L2）/ 稀疏性（L1） | ✅ | `NeuralGraphSpec.mlp` 加 weight_decay 等价 Ridge。Lasso 用 `SymbolicExpressionModel` 搜稀疏公式 |
| **Polynomial Regression** | f(x) = w₀ + w₁x + w₂x² + ... | ✅ | `model.symbolic_expression` 搜多项式基函数 + `model.linear_point` 拟系数 |
| **Quantile Regression** | 不预测"平均"，预测"第 τ 百分位" | ✅ | 改 Problem 的 loss 为 pinball loss。`NormalDistributionModel` 换成 `QuantileModel`（新 Model，30 行） |
| **Interval Prediction** | 预测 [下界, 上界]，而非一个点 | ✅ 已有 | `model.interval_prediction` + `model.center_radius_interval` |
| **Conformal Prediction** | 给每个预测加统计保证的置信区间 | ⚠️ 半接 | 不是 Model——是 wrapping 层。在外面跑：每个候选产生预测 + 校准集算分位 → 输出区间。DataPipeline 做校准集划分 |

## 分类

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Logistic Regression** | 线性模型 + sigmoid 压到 [0,1] 之间 | ✅ 已有 | `model.binary_logistic_probability` 包裹 `model.linear_point` |
| **Softmax / Multiclass** | N 个类别各有一个得分，指数归一化 | ✅ 已有 | `model.softmax_probability` |
| **Imbalanced Classification** | 正例只有 1%，全猜负例也是 99% 准确率 | ✅ 半接 | 不是新模型——DataPipeline 做过采样/欠采样，或 Problem.evaluate 的 loss 加类别权重。`RowDatasetStream` 加 sampler 参数 |
| **Cost-Sensitive** | 把"假阴性"误判为"假阳性"的代价不同 | ✅ | Problem.evaluate 返回 `cost_weighted_loss` 而不是 `accuracy`。不改模型，改目标函数 |

## 时间序列

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **ARIMA / SARIMAX** | 经典统计模型：自回归 + 移动平均 + 差分 | ✅ 已有 | `model.arimasarimax` / `model.statsmodels_sarimax_forecast` |
| **Exponential Smoothing** | 最近的数据权重大、以前的数据指数衰减 | ⚠️ 缺 | 新 Model——但和你已有 `NaiveForecastModel` 同级，50 行。三参数（α/β/γ）对应 level/trend/seasonal |
| **Prophet** | Facebook 的时间序列框架：trend + season + holiday | ⚠️ 缺 | 用 `FittedEstimatorModel` 包裹 fbprophet |
| **VAR / VARMAX** | 多个时间序列互相预测：A 的未来取决于 B 的过去 | ⚠️ 缺 | 新 Model 类型。输入是多个 time series 的矩阵，输出也是矩阵。`TimeSeriesDataView` 需要扩一个 `multivariate=True` |
| **State Space Model** | 隐藏状态在驱动观测值，用 Kalman Filter 推断隐藏状态 | ❌ 不推荐 | 和 Codec+UnknownState 的扁向量编码模型不同。如果真需要，接 statsmodels |

## 生存分析

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Cox Proportional Hazard** | 不预测 Y，预测"在时刻 t 还没死的人下一秒会死的概率" | ⚠️ 缺 | 新 Model 类型。输出不是 point value 是 hazard function。数据需要 censored label（部分样本没观察到终点） |
| **Accelerated Failure Time** | 不同个体的"生命时钟"走的快慢不同 | ⚠️ 缺 | 等价于在 log(T) 上做回归。`LinearPointModel` + `NormalDistributionModel` 就能做 Weibull AFT。只缺一个 loss 函数 |
| **Kaplan-Meier** | 不建模，纯画生存曲线 | ❌ | 这是 EDA 工具，不是模型。不接 |

## 树与集成

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Decision Tree** | 一层层 if-else 切分数据 | ✅ 等价 | nsgablack 搜分段点 + `model.piecewise` + `model.threshold_router`。不是缺组件——是组合方式不同 |
| **Random Forest** | 一堆树投票 | ✅ 等价 | nsgablack 的多个 VNS adapter 并行搜不同的分段方案 → `PredictionIntegrationComponent.additive` 平均 |
| **Gradient Boosting** | 每棵树拟合前一棵树的残差 | ✅ 已有 | `ModelConditionedTargetComponent` = 算残差 → 新阶段拟合残差 |
| **XGBoost / LightGBM** | GB 的工程优化版：正则化、直方图加速 | ✅ 已有 | `model.fitted_estimator` + `model.estimator_spec`。不需要重写——用外部库的拟合结果做 nsgablack 的评估 |

## 聚类与降维

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **K-Means** | 把数据分成 k 堆，每堆离各自的中心最近 | ✅ | 不是 Model——是 Problem。评估函数 = 簇内平方和。nsgablack Adapter 搜中心点坐标 |
| **DBSCAN** | 密度高的地方是簇，稀疏的地方是噪声 | ⚠️ | 不需要搜索——算法是确定的。DataPipeline 挂一个 `DBSCANComponent` 做预处理 |
| **PCA** | 把高维数据投影到方差最大的几个方向上 | ✅ | DataPipeline 挂 `PCAComponent`。线性操作，fit 算投影矩阵，transform 做降维 |
| **t-SNE / UMAP** | 把高维投影到 2D/3D 方便可视化 | ❌ | 纯可视化工具，不接模型管线。导出数据后用 sklearn 跑 |
| **Autoencoder** | 神经网络把数据压缩再还原，中间层 = 降维表示 | ✅ 已有 | `NeuralGraphSpec` 做 autoencoder：输入维度 = 输出维度，bottleneck 层维度 = 降维目标。Problem.evaluate 用 reconstruction error |

## 推荐系统

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Collaborative Filtering** | "和你相似的用户也喜欢这个" | ✅ | 用户×物品矩阵 → `NumericDataView`。`NumpyMLPPointModel` 做 user embedding · item embedding。`PredictionInputSpec(kind="user_item_pair")` |
| **Content-Based** | "这个东西和你以前喜欢的很像" | ✅ | 就是普通的回归/分类，特征从物品属性来。不需新组件 |
| **Matrix Factorization** | 把用户×物品矩阵分解为两个低秩矩阵 | ✅ | `LinearPointModel` 的权重矩阵 W = user_embedding @ item_embedding^T。Codec 解码 W 时强制低秩约束 |

## 异常检测

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Statistical / IQR** | 落在 Q1-1.5×IQR 之外的数据点是异常 | ✅ | DataPipeline 挂一个 `OutlierFlagComponent`。不需要模型 |
| **Isolation Forest** | 随机切空间——需要很多次才能隔离的点是异常 | ✅ | `model.fitted_estimator` 包裹 sklearn IsolationForest |
| **Autoencoder Anomaly** | 训练 autoencoder 学正常数据模式。重构误差大的 = 异常 | ✅ 已有 | `NeuralGraphSpec` autoencoder → Problem 返回重构误差 → 阈值由 Percentile 或 nsgablack 搜 |
| **One-Class SVM** | 只用正常数据训练，学"正常"的边界 | ✅ | `model.fitted_estimator` 包裹 sklearn OneClassSVM |

## 图学习

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Graph Neural Network** | 每个节点的表示 = 它自己的特征 + 邻居节点特征的聚合 | ⚠️ 缺 | 新 Model 类型。输入是 `GraphDataView`（节点特征 + 边列表），输出是节点/边/图级预测。需要 `GraphNeuralCodec` |
| **Node Embedding** | Node2Vec / DeepWalk：在图上游走学节点向量 | ✅ | 不是 Model——是预处理。DataPipeline 加 `NodeEmbeddingComponent`。学完的向量进 `NumericDataView` |
| **Link Prediction** | 预测两个节点之间可能产生边 | ✅ | 节点嵌入后 → `NumericDataView(features=[emb_A, emb_B])` → 普通二分类 |

## 强化学习

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Q-Learning** | 学"在每个状态下做每个动作的期望回报" | ⚠️ 半接 | Problem 不是 evaluate(x) → score，是 `step(action) → (next_state, reward, done)`。`AsyncEventDrivenAdapter` 可以接事件流。需要环境接口标准 |
| **Policy Gradient** | 直接学"在状态 s 下选动作 a 的概率分布" | ⚠️ | 同上，环境接口先定。策略网络 = `NeuralGraphSpec`。nsgablack 不做 RL 训练循环——只搜策略网络架构 |
| **Multi-Armed Bandit** | 每次从 k 个选项里选一个，即时反馈 reward，目标是积累总 reward 最大化 | ✅ | 最简 RL。nsgablack 的 Adapter 搜"每个 arm 选的概率"。Problem 读 arm → 返回 reward。不需要状态——只有 action 和 reward |

## 校准与概率

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **Platt Scaling** | 拿分类器输出的原始分数，跑一个逻辑回归学"这个分数对应多大真实概率" | ✅ 已有 | `model.probability_calibration` 是做这个的 |
| **Isotonic Regression** | 同上，但不假设 sigmoid 形状——单调非降就行 | ⚠️ 缺 | `model.temperature_calibrated_probability` 是参数化的，Isotonic 是非参数化的。新 Model，40 行 |
| **Brier Score** | 衡量概率预测有多准——不是衡量分类对错 | ✅ | Problem.evaluate 返回 Brier score 而不是 accuracy。不改模型，换评估指标 |

## 因果推断

| 模式 | 一句话 | 能接吗 | 接线 |
|---|---|---|---|
| **A/B Test** | 随机分两组，比均值差 | ❌ | 统计检验，不是 ML 模型。不接 |
| **Propensity Score Matching** | 找"除了是否接受干预外其他特征相似"的人做比较 | ✅ | 不是新 Model。DataPipeline 做匹配 → `NumericDataView`（treated + control pairs）→ 普通回归 |
| **Double ML** | 用 ML 估计 treatment effect，同时控制混淆变量 | ✅ | 两个模型：一个预测 outcome ~ features，一个预测 treatment ~ features。残差对残差回归。你的 `ModelConditionedTargetComponent` 做的就是残差化 |
| **Instrumental Variables** | 当 treatment 和 outcome 有未观测混淆时，用工具变量解耦 | ✅ | 两阶段最小二乘 = 两个 LinearPointModel。第一阶段：treatment ~ IV → 拟合值。第二阶段：outcome ~ 拟合的 treatment |

---

## 速记

**不需要新组件的（只改 Problem / DataPipeline / Loss）：** Imbalanced、Cost-Sensitive、Brier Score、Quantile Regression（改 loss）、K-Means（Problem）、PCA（Pipeline）、Node Embedding（Pipeline）、Bandit（Problem 接口）

**需要新 Model 的（~50 行）：** Exponential Smoothing、Accelerated Failure Time、Isotonic Regression、VARMAX

**需要新 Codec + Model 的（值得做）：** GNN、Survival Analysis（Cox）、Matrix Factorization（低秩约束 Codec）

**不推荐接入的：** t-SNE/UMAP（可视化）、Kaplan-Meier（EDA）、A/B Test（统计检验）、Gaussian Process（和 Codec 模型冲突）
