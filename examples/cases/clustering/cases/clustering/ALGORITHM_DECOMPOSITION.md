# 算法拆解清单：nsgablack + mlblack 双框架实现

🟦 = nsgablack（搜索/优化）  🟩 = mlblack（训练/拟合）  🔷 = 混合

---

## 一、聚类家族

| 算法 | 框架 | 拆解 |
|---|---|---|
| k-means | 🟦 | Representation=质心向量, Problem=SSE, Adapter=DE |
| k-means (梯度) | 🟩 | Model=CentroidModel, Problem=SSE, Adapter=gradient_descent |
| k-medians | 🟦 | 同上, 距离=L1 |
| k-medoids (PAM) | 🟦 | Representation=medoid索引, Problem=类内距离和 |
| k-modes | 🟦 | 同上, 距离=Hamming（分类变量） |
| k-prototypes | 🟦 | 混合数值+分类距离 |
| fuzzy c-means | 🟩 | Model=隶属度矩阵, Problem=加权SSE, Adapter=gradient_descent |
| GMM | 🟩 | Model=GaussianMixture, Problem=log_likelihood, Adapter=EM |
| GMM (搜索) | 🟦 | Representation=(μ,Σ,π)扁平向量, Adapter=DE |
| DBSCAN | 🟦 | Representation=(eps, min_samples), Problem=density_reachability |
| OPTICS | 🟦 | 同上, 加reachability plot |
| HDBSCAN | 🟦 | Representation=min_cluster_size, Problem=层次稳定性 |
| 均值漂移 (Mean Shift) | 🟦 | Representation=带宽, Problem=密度梯度 |
| 谱聚类 | 🟩→🟦 | Pipeline: 拉普拉斯分解 → nsgablack搜嵌入聚类 |
| 层次聚类 (Agglomerative) | 🟦 | Representation=linkage+切割阈值, Problem=类间距离 |
| BIRCH | 🟩 | Model=CF Tree, Problem=聚类特征压缩 |
| 子空间聚类 | 🟦 | Representation=(特征子集, 簇分配), 双编码 |
| 深度聚类 (DeepCluster) | 🟩 | Model=CNN+聚类头, Problem=伪标签+重构 |
| 约束聚类 | 🟦 | + Bias: must_link, cannot_link, min/max_size |
| 多目标聚类 | 🟦 | Problem=(intra-SSE, inter-dist, silhouette), Adapter=NSGA2 |
| 共识聚类 | 🔷 | 多个聚类结果 → nsgablack 搜最优共识划分 |
| 流聚类 (Stream) | 🟩 | Model=在线更新质心, Problem=增量SSE |

---

## 二、降维家族

| 算法 | 框架 | 拆解 |
|---|---|---|
| PCA | 🟩 | Model=LinearProjection, Problem=reconstruction_MSE |
| 稀疏 PCA | 🟦 | + Bias: L1_sparsity 搜稀疏度 |
| 核 PCA | 🟩 | Pipeline: 核变换 → PCA |
| 概率 PCA | 🟩 | Model=latent Gaussian, Problem=边际似然, Adapter=EM |
| NMF | 🟦 | Representation=(W,H), Problem=Frobenius, Bias=nonnegativity |
| ICA (独立成分) | 🟩 | Problem=非高斯性最大化, Adapter=gradient_descent |
| 因子分析 | 🟩 | Model=latent factors+noise, Problem=似然, Adapter=EM |
| MDS (多维缩放) | 🟩 | Problem=距离保持, Adapter=gradient_descent |
| Isomap | 🟩→🟦 | Pipeline: 测地距离 → MDS |
| LLE (局部线性嵌入) | 🟩 | Problem=局部重构保真, Adapter=特征分解 |
| t-SNE | 🟩 | Model=低维嵌入, Problem=KL(p∥q), Adapter=gradient_descent |
| UMAP | 🟩 | Problem=交叉熵(拓扑保真), Adapter=梯度下降 |
| 自编码器 | 🟩 | Model=encoder+decoder, Problem=recon_loss, Adapter=torch_backprop |
| 变分自编码器 (VAE) | 🟩 | Model=encoder+decoder, Problem=ELBO |
| 去噪自编码器 | 🟩 | + Pipeline: 加噪 → 去噪 |
| 对比自编码器 | 🟩 | + Problem: contrastive_loss |

---

## 三、特征工程

### 特征选择

| 算法 | 框架 | 拆解 |
|---|---|---|
| Filter (方差) | 🟦 | Representation=特征掩码, Problem=方差阈值 |
| Filter (互信息) | 🟦 | Representation=特征掩码, Problem=max_MI - λ*size |
| Filter (卡方) | 🟦 | 同上, Problem=χ²统计量 |
| Filter (F值/ANOVA) | 🟦 | 同上, Problem=F_statistic |
| Wrapper (RFE) | 🔷 | nsgablack搜特征子集, mlblack Trainer训模型评估 |
| Wrapper (遗传) | 🔷 | nsgablack NSGA2同时搜子集+模型超参 |
| Embedded (LASSO) | 🟩 | Model=LinearRegression, Bias=L1_sparsity |
| Embedded (ElasticNet) | 🟩 | Bias=L1+L2 |
| Embedded (Ridge) | 🟩 | Bias=L2 |
| Embedded (树模型重要性) | 🟩 | mlblack 训TreeModel → 输出特征重要性 |
| Boruta | 🔷 | nsgablack搜shadow特征对比 |
| 稳定性选择 | 🔷 | nsgablack搜bootstrap子集 → 稳定性评分 |
| 符号特征选择 | 🟩 | SymbolicPipeline搜表达式 → 自动识别特征 |

### 特征构造

| 算法 | 框架 | 拆解 |
|---|---|---|
| 多项式特征 | 🟩 | Pipeline: PolynomialFeatureComponent |
| 交互特征 | 🟩 | SymbolicPipeline搜pair规则 |
| 分箱/离散化 | 🟦 | Representation=分箱边界, Problem=信息增益 |
| 目标编码 | 🟩 | Pipeline: TargetEncodingComponent |
| 特征哈希 | 🟩 | Pipeline: FeatureHashing |
| 自动特征工程 (DFS) | 🟦 | Representation=特征表达式树, Problem=下游模型性能 |

---

## 四、异常检测

| 算法 | 框架 | 拆解 |
|---|---|---|
| 3-sigma / Z-score | 🟩 | Problem=标准化残差 > 阈值 |
| IQR | 🟩 | Problem=超出Q1-1.5IQR / Q3+1.5IQR |
| Isolation Forest | 🟦 | Representation=树结构, Problem=平均路径长度 |
| LOF | 🟦 | Representation=(k, threshold), Problem=LOF_score |
| COF (连通离群) | 🟦 | 同上, 距离=链式距离 |
| One-Class SVM | 🟩 | Model=SVM, Head=one_class |
| SVDD (支持向量数据描述) | 🟩 | Model=超球包围, Problem=最小包围球 |
| 鲁棒马氏距离 (MCD) | 🟦 | Representation=(μ,Σ), Problem=MCD, Adapter=DE |
| 椭圆包络 | 🟦 | 同上, 更简单的bounding |
| HBOS (直方图异常分) | 🟩 | Pipeline: 每维直方图 → 乘积得分 |
| 深度异常检测 (AutoEncoder) | 🟩 | Model=AutoEncoder, Problem=recon_error |
| GAN 异常检测 | 🟩 | Model=GAN, Problem=generator不能重建异常 |
| 时间序列异常 | 🟦 | Representation=变点位置, Problem=预测残差 |
| 集成异常检测 | 🔷 | 多个检测器 → nsgablack搜最优加权 |

---

## 五、密度估计与生成

| 算法 | 框架 | 拆解 |
|---|---|---|
| 直方图密度 | 🟦 | Representation=bin边界, Problem=CV_likelihood |
| KDE | 🟦 | Representation=带宽, Problem=CV_likelihood |
| 自适应 KDE | 🟦 | Representation=每点带宽, 同上 |
| GMM | 🟩 | Model=GaussianMixture, Adapter=EM |
| 贝叶斯 GMM | 🟩 | + Prior: Dirichlet process (DPGMM) |
| 核密度分类 | 🟩 | Problem=类条件密度 × 先验 |
| VAE | 🟩 | Model=encoder+decoder, Problem=ELBO |
| GAN | 🟩 | Model=generator+discriminator, Problem=minimax |
| Normalizing Flow | 🟩 | Model=可逆变换链, Problem=log_likelihood |
| 扩散模型 | 🟩 | Model=denoiser, Problem=noise_prediction_loss |

---

## 六、回归家族

| 算法 | 框架 | 拆解 |
|---|---|---|
| 线性回归 (OLS) | 🟩 | Model=Linear, Problem=MSE |
| 岭回归 | 🟩 | + Bias: L2 |
| LASSO | 🟩 | + Bias: L1 |
| ElasticNet | 🟩 | + Bias: L1+L2 |
| 分位数回归 | 🟩 | Problem=quantile_loss (pinball) |
| Huber 回归 | 🟩 | Problem=Huber_loss |
| 多项式回归 | 🟩 | Pipeline: PolynomialFeature → Linear |
| 局部加权回归 (LOESS) | 🟩 | Problem=加权局部MSE |
| GAM | 🟩 | Model=Σ smooth_f_i(x_i), Bias=smoothness |
| 符号回归 | 🟦 | Representation=表达式树, Problem=拟合优度+复杂度 |
| 多输出回归 | 🟩 | Model=MultiOutput, Problem=multi_MSE |
| 贝叶斯线性回归 | 🟩 | Model=Linear+prior, Problem=后验似然 |
| 稳健回归 (RANSAC) | 🟦 | Representation=inlier_mask, Problem=内点MSE |
| Theil-Sen | 🟦 | Representation=采样对, Problem=中位数斜率 |

---

## 七、分类家族

| 算法 | 框架 | 拆解 |
|---|---|---|
| 逻辑回归 | 🟩 | Model=Linear+softmax, Problem=cross_entropy |
| LDA (线性判别) | 🟩 | Problem=类间/类内方差比 |
| QDA (二次判别) | 🟩 | Model=每类Σ, Problem=判别得分 |
| 朴素贝叶斯 | 🟩 | Model=条件概率表, Problem=后验 |
| k-NN | 🟩 | Problem=距离加权投票, Representation=k |
| SVM (线性) | 🟩 | Model=Linear, Problem=hinge_loss, Bias=L2 |
| SVM (核) | 🟩 | Pipeline: KernelTransform → LinearSVM |
| 决策树 | 🟦 | Representation=分裂规则序列, Problem=纯度增益 |
| 随机森林 | 🔷 | ParallelTrainer: bootstrap样本 → 多棵树 → 投票 |
| GBDT | 🔷 | CaseStageRunner/Trainer phase：每阶段训残差树 |
| XGBoost / LightGBM | 🔷 | 同上, +正则化Bias |
| 多层感知机 (MLP) | 🟩 | Model=MLP, Problem=cross_entropy, Adapter=torch_backprop |
| 最近质心分类 | 🟦 | Representation=各类质心, Problem=最近距离分类错误 |

---

## 八、集成学习

| 算法 | 框架 | 拆解 |
|---|---|---|
| Bagging | 🔷 | 🟦 划分bootstrap → 🟩 ParallelTrainer并行训 |
| Random Forest | 🔷 | Bagging + 随机特征选择 |
| AdaBoost | 🔷 | 🟩 CaseStageRunner/Trainer phase：每阶段加权重采样 |
| Gradient Boosting | 🔷 | 🟩 CaseStageRunner/Trainer phase：每阶段训残差 |
| Stacking | 🔷 | Stage1: 🟩 ParallelTrainer → Stage2: 🟩 Fusion |
| Blending | 🔷 | 同上, hold-out代替CV |
| Voting (硬/软) | 🟩 | Pipeline: 多模型预测 → 投票 |
| 动态集成 | 🔷 | 🟦 nsgablack搜每个样本的最优模型分配 |
| 异质集成 | 🔷 | 不同模型族混合 → nsgablack搜加权 |
| 级联分类 | 🔷 | 🟩 CaseStageRunner/Trainer phase：逐级过滤 |

---

## 九、时间序列

| 算法 | 框架 | 拆解 |
|---|---|---|
| AR/ARMA/ARIMA | 🟩 | Model=ARMA, Pipeline: 差分 |
| SARIMA | 🟩 | + Pipeline: 季节差分 |
| ARIMAX | 🟩 | + 外生变量 |
| VAR | 🟩 | Model=多变量AR |
| GARCH | 🟩 | Model=条件异方差 |
| STL 分解 | 🟩 | Pipeline: STLComponent → trend+seasonal+residual |
| 指数平滑 (Holt-Winters) | 🟩 | Model=平滑系数 |
| Prophet | 🟩 | Model=trend+seasonality+holidays |
| 变点检测 (PELT/BinSeg) | 🟦 | Representation=变点位置向量, Problem=分段拟合残差 |
| 变点检测 (贝叶斯) | 🟦 | + Prior: 变点稀疏先验 |
| 动态时间规整 (DTW) | 🟦 | Representation=规整路径, Problem=对齐距离 |
| 形状匹配 (shapelets) | 🟦 | Representation=判别子序列, Problem=分类信息增益 |
| 时间序列聚类 | 🟦 | Representation=多序列的质心, Problem=DTW-SSE |
| 时间序列分类 (TSF) | 🟩 | Model=时序特征+分类器 |
| 频谱分析 (FFT/小波) | 🟩 | Pipeline: FFT → 频率特征 |
| 格兰杰因果 | 🟩 | Problem=F检验, Representation=稀疏滞后系数 ✅ |
| 传递熵 | 🟩 | Problem=条件互信息 |
| 收敛交叉映射 (CCM) | 🟩 | Problem=跨变量预测能力 |

---

## 十、因果推断

| 算法 | 框架 | 拆解 |
|---|---|---|
| PC 算法 | 🟦 | Representation=DAG邻接矩阵, Problem=条件独立性 |
| FCI | 🟦 | 同上 + 潜在混杂 |
| LiNGAM | 🟦 | Representation=因果系数, Problem=非高斯独立性 |
| GES (贪婪等价搜索) | 🟦 | Representation=DAG, Problem=BIC, 邻域搜 |
| 格兰杰因果 | 🟩 | ✅ |
| 工具变量 (IV) | 🟩 | Model=2SLS, Problem=一致性 |
| 双重差分 (DiD) | 🟩 | Model=交互项, Problem=差分显著性 |
| 断点回归 (RDD) | 🟦 | Representation=断点位置, Problem=两侧差异 |
| 倾向得分匹配 (PSM) | 🟩 | Model=倾向得分, Pipeline: 匹配 |
| 反事实预测 | 🟩 | Model=预测模型, Problem=干预下预测差异 |
| do-演算 | 🟦 | Representation=干预变量组合, Problem=调整公式 |

---

## 十一、生存分析

| 算法 | 框架 | 拆解 |
|---|---|---|
| Kaplan-Meier | 🟩 | Model=生存函数, Problem=乘积极限 |
| Cox 比例风险 | 🟩 | Model=proportional_hazard, Problem=partial_likelihood |
| 加速失效时间 (AFT) | 🟩 | Model=log-linear, Problem=MSE |
| 竞争风险 | 🟩 | Model=累积发生率, Problem=cause-specific |
| 时变 Cox | 🟩 | + Pipeline: 时间窗口特征 |
| 随机生存森林 | 🔷 | ParallelTrainer: bootstrap生存树 |

---

## 十二、图与网络

| 算法 | 框架 | 拆解 |
|---|---|---|
| 最短路径 (Dijkstra) | 🟦 | A* Adapter, Problem=路径长度 |
| TSP / VRP | 🟦 | Representation=节点序列, Problem=总路程, 已有Bias |
| 最小生成树 | 🟦 | Representation=边集, Problem=树权重和, Bias=连通性 |
| 最大流/最小割 | 🟦 | 已有 max_flow Bias |
| 图着色 | 🟦 | Representation=颜色分配, Bias=邻接禁止同色 |
| 社区检测 (Louvain) | 🟦 | Representation=社区标签, Problem=模块度 |
| 图嵌入 (Node2Vec) | 🟩 | Model=skip-gram, Problem=邻域重建 |
| PageRank | 🟩 | Problem=稳态分布, Adapter=power_iteration |
| 图匹配 | 🟦 | Representation=节点映射, Problem=结构相似度 |
| 斯坦纳树 | 🟦 | Representation=附加节点+边, Problem=总权重 |
| 设施选址 | 🟦 | Representation=选址向量, Problem=覆盖/距离 |

---

## 十三、推荐系统

| 算法 | 框架 | 拆解 |
|---|---|---|
| 协同过滤 (User-Based) | 🟩 | Model=相似度矩阵, Problem=加权评分 |
| 协同过滤 (Item-Based) | 🟩 | 同上, 转置 |
| 矩阵分解 (SVD) | 🟩 | Model=U+V, Problem=Frobenius(M-UV^T), Adapter=梯度下降 |
| NMF 推荐 | 🟦 | Representation=(U,V), Problem=Frobenius, Bias=nonnegativity |
| FM (因子分解机) | 🟩 | Model=FM, Problem=MSE |
| 贝叶斯个性化排序 (BPR) | 🟩 | Problem=pairwise_ranking_loss |
| 序列推荐 | 🟩 | Model=RNN/Transformer, Problem=next_item |
| 多臂老虎机 (Bandit) | 🟦 | Representation=臂选择策略, Problem=regret |
| 上下文 Bandit | 🟩 | Model=reward_predictor, Problem=exploration_regret |
| Top-N 推荐评估 | 🟦 | Representation=推荐列表, Problem=NDCG/MAP |

---

## 十四、优化算法（框架本身可被搜索）

| 算法 | 框架 | 拆解 |
|---|---|---|
| 超参搜索 (Grid) | 🟦 | Representation=离散网格点 |
| 超参搜索 (Random) | 🟦 | Representation=采样分布 |
| 超参搜索 (Bayesian) | 🟦 | + Model=GP surrogate |
| 网络结构搜索 (NAS) | 🔷 | nsgablack搜结构, mlblack训权重 |
| 损失函数搜索 | 🔷 | SymbolicPipeline搜损失表达式 |
| 激活函数搜索 | 🔷 | SymbolicPipeline搜激活函数 |
| 优化器超参调优 | 🔷 | nsgablack搜lr/schedule, mlblack训 |

---

## 十五、统计检验（重构为优化）

| 检验 | 框架 | 拆解 |
|---|---|---|
| t 检验 | 🟦 | Representation=分组阈值, Problem=t_statistic |
| 卡方检验 | 🟦 | Representation=列联表分区, Problem=χ² |
| Mann-Whitney U | 🟦 | Problem=rank_sum |
| Kolmogorov-Smirnov | 🟦 | Problem=经验CDF最大差异 |
| 方差分析 (ANOVA) | 🟦 | Representation=分组, Problem=F_statistic |
| 多重比较校正 | 🟦 | Representation=显著性阈值, Problem=FWER/FDR |
| 功效分析 | 🟦 | Representation=样本量, Problem=power |
| 置换检验 | 🟦 | nsgablack 搜置换分布 → 计算经验p值 |

---

## 十六、缺失数据处理

| 算法 | 框架 | 拆解 |
|---|---|---|
| 均值/中位数填充 | 🟩 | Pipeline: 统计量替换 |
| k-NN 填充 | 🟦 | Representation=k+距离度量, Problem=填充误差 |
| MICE (多重插补) | 🟩 | Model=链式回归, Problem=收敛 |
| 矩阵补全 | 🟩 | Model=低秩分解, Problem=Frobenius(观测部分) |
| 深度插补 (GAIN) | 🟩 | Model=GAN, Problem=masked_recon |
| 缺失机制检验 (MCAR/MAR/MNAR) | 🟦 | Representation=缺失指示矩阵, Problem=独立性检验 |

---

## 十七、模型解释

| 算法 | 框架 | 拆解 |
|---|---|---|
| SHAP | 🟦 | Representation=特征联盟, Problem=边际贡献 |
| LIME | 🟦 | Representation=邻域采样, Problem=局部保真+简单性 |
| 部分依赖图 (PDP) | 🟩 | Pipeline: 边缘化 → 曲线 |
| 个体条件期望 (ICE) | 🟩 | Pipeline: 每条样本 → 曲线簇 |
| 排列重要性 | 🟦 | Representation=特征置换, Problem=性能下降 |
| 反事实解释 | 🟦 | Representation=最小扰动向量, Problem=分类翻转+距离最小 |
| 锚点解释 | 🟦 | Representation=规则集, Problem=精度+覆盖 |
| 综合梯度 | 🟩 | Problem=路径积分梯度 |

---

## 十八、主动学习

| 算法 | 框架 | 拆解 |
|---|---|---|
| 不确定性采样 | 🟦 | Representation=查询索引, Problem=uncertainty(entropy/margin) |
| 多样性采样 | 🟦 | Representation=查询批次, Problem=多样性+代表性 |
| 委员会查询 (QBC) | 🔷 | 多模型分歧 → 选择最不确定样本 |
| 预期模型变化 | 🟩 | Problem=expected_gradient_norm |
| 贝叶斯主动学习 | 🟩 | + Model=Bayesian, Problem=posterior_entropy |

---

## 十九、半监督 / 自监督

| 算法 | 框架 | 拆解 |
|---|---|---|
| 自训练 (Self-training) | 🟩 | CaseStageRunner/Trainer phase：伪标签 → 再训练 |
| 协同训练 (Co-training) | 🔷 | ParallelTrainer: 两个视图 → 互相标注 |
| 标签传播 | 🟩 | Model=图拉普拉斯, Problem=平滑分类 |
| SimCLR (对比学习) | 🟩 | Model=encoder+projector, Problem=NT-Xent |
| MoCo | 🟩 | Model=query+key encoder, Problem=contrastive |
| BYOL | 🟩 | Model=online+target, Problem=prediction |

---

## 二十、公平性与校准

| 算法 | 框架 | 拆解 |
|---|---|---|
| 等几率校准 | 🟦 | Representation=阈值, Problem=equalized_odds |
| 人口统计均等 | 🟦 | + Bias: demographic_parity |
| Platt 缩放 | 🟩 | Model=logistic_calibrator |
| 同位素回归校准 | 🟩 | Model=isotonic_function, Problem=MSE |
| 贝叶斯校准 | 🟩 | + Prior: calibration_curve |
| 公平重加权 | 🟦 | Representation=样本权重, Problem=公平损失 |

---

## 二十一、实验设计

| 算法 | 框架 | 拆解 |
|---|---|---|
| A/B 测试 | 🟦 | Representation=分配比例, Problem=效应量 |
| 多臂 Bandit | 🟦 | Representation=臂选择策略, Problem=regret |
| 拉丁超立方 | 🟦 | Representation=采样点排列, Problem=空间填充 |
| 响应面设计 | 🟦 | Representation=实验点, Problem=D-optimality |
| 因子设计 | 🟦 | Representation=水平组合, Problem=主效应+交互 |

---

## 实现优先级

| # | 算法 | 框架 | 冲击力 |
|---|---|---|---|
| 1 | ✅ k-means vs DE | 🟦 | 通用优化器 = 专用算法 |
| 2 | k-medians (改一行距离) | 🟦 | sklearn无, 框架一行 |
| 3 | GMM: EM vs DE | 🟩 vs 🟦 | 同一问题两种范式 |
| 4 | 多目标聚类 | 🟦 | sklearn完全做不了 |
| 5 | Wrapper特征选择 | 🔷 | 双框架教科书案例 |
| 6 | RANSAC稳健回归 | 🟦 | 统计方法的优化视角 |
| 7 | 变点检测 vs ruptures | 🟦 | 时间序列优化 |
| 8 | 图着色 / 社区检测 | 🟦 | 离散组合优化 |
| 9 | AutoML最小闭环 | 🔷 | 搜pipeline→训→评估 |
| 10 | SHAP / LIME | 🟦 | 模型解释也是优化 |
