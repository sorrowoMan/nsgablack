# NSGABlack ML 模块

NSGABlack的机器学习工具模块，提供完整的机器学习模型管理、训练、评估和可视化功能。

## 模块结构

```
ml/
├── __init__.py              # 模块导出
├── model_manager.py         # 模型管理工具
├── checkpoint_manager.py    # 检查点和状态保存
├── data_processor.py        # 数据预处理和特征工程
├── evaluation_tools.py      # 模型评估和可视化
├── ml_models.py            # 原始ML模型（兼容）
└── README.md               # 本文档
```

## 核心组件

### 1. ModelManager - 模型管理器

统一管理机器学习模型的整个生命周期。

**主要功能：**

- 支持多种模型类型（随机森林、梯度提升等）
- 模型训练、预测、保存、加载
- 集成模型支持
- 增量学习
- 自适应训练
- 自动模型选择

**使用示例：**

```python
from nsgablack.ml import ModelManager

# 创建模型管理器
manager = ModelManager(model_dir="models")

# 创建模型
manager.create_model('random_forest', name='rf_model',
                    params={'n_estimators': 100})

# 训练模型
manager.train_model('rf_model', X_train, y_train)

# 预测
predictions = manager.predict('rf_model', X_test)

# 评估
metrics = manager.evaluate_model('rf_model', X_test, y_test)

# 增量学习
result = manager.incremental_train('rf_model', X_new, y_new)

# 自适应训练
result = manager.adaptive_training(X, y, 'rf_model')

# 保存模型
manager.save_model('rf_model')
```

**高级功能：**

1. **增量学习**

```python
# 在已有模型基础上学习新数据
result = manager.incremental_train(
    model_name='my_model',
    X_new=new_features,
    y_new=new_targets,
    validation_split=0.2
)
```

2. **自适应训练**

```python
# 动态调整批次大小的智能训练
result = manager.adaptive_training(
    X, y, 'my_model',
    initial_batch_size=100,
    growth_factor=1.5,
    convergence_threshold=0.001
)
```

3. **从检查点创建集成模型**

```python
# 使用不同时期的模型创建集成
ensemble_name = manager.create_ensemble_from_checkpoints(
    model_name_prefix='rf',
    checkpoint_names=['checkpoint_1', 'checkpoint_2', 'checkpoint_3']
)
```

### 2. CheckpointManager - 检查点管理器

提供强大的训练状态保存和恢复功能。

**主要功能：**

- 原子性文件操作（防止数据损坏）
- 自动备份机制
- 压缩和完整性验证
- 版本管理
- 元数据管理

**使用示例：**

```python
from nsgablack.ml import CheckpointManager

# 创建检查点管理器
checkpoint_mgr = CheckpointManager(
    checkpoint_dir="checkpoints",
    auto_backup=True,
    backup_count=3,
    compression=True
)

# 保存状态
state = {
    'model_weights': model_weights,
    'epoch': current_epoch,
    'loss': current_loss,
    'metadata': {...}
}
checkpoint_mgr.save_checkpoint(state, "training_checkpoint")

# 加载状态
state = checkpoint_mgr.load_checkpoint("training_checkpoint")

# 列出所有检查点
checkpoints = checkpoint_mgr.list_checkpoints()

# 获取统计信息
stats = checkpoint_mgr.get_statistics()
```

**高级功能：**

1. **自动备份**

```python
# 自动创建备份，防止数据丢失
checkpoint_mgr = CheckpointManager(
    checkpoint_dir="checkpoints",
    auto_backup=True,
    backup_count=5  # 保留最近5个备份
)
```

2. **文件完整性验证**

```python
# 使用哈希值验证文件完整性
checkpoint_mgr = CheckpointManager(
    hash_verification=True  # 启用SHA256验证
)
```

### 3. DataProcessor - 数据处理器

全面的数据预处理和特征工程工具。

**主要功能：**

- 数据缩放和标准化
- 缺失值处理
- 异常值检测
- 特征选择
- 降维（PCA）
- 特征工程

**使用示例：**

```python
from nsgablack.ml import DataProcessor, FeatureEngineer

# 创建数据处理器
processor = DataProcessor()
engineer = FeatureEngineer()

# 数据缩放
processor.fit_scaler(X_train, method='standard')
X_scaled = processor.transform_scaler(X_test, 'standard')

# 处理缺失值
X_filled = processor.handle_missing_values(X, strategy='knn')

# 特征选择
X_selected, features = processor.select_features_univariate(X, y, k=10)

# 创建工程特征
X_with_ratios = engineer.create_ratio_features(X, [(0, 1), (2, 3)])
X_with_interactions = engineer.create_interaction_features(X)

# 保存处理器状态
processor.save_processor('processor_state.pkl')
```

### 4. ModelEvaluator - 模型评估器

全面的模型性能评估和可视化工具。

**主要功能：**

- 性能指标计算
- 预测vs真实值可视化
- 残差分析
- 学习曲线
- 特征重要性可视化
- 模型比较
- HTML报告生成

**使用示例：**

```python
from nsgablack.ml import ModelEvaluator

# 创建评估器
evaluator = ModelEvaluator()

# 计算指标
metrics = evaluator.calculate_metrics(y_true, y_pred)

# 可视化结果
evaluator.plot_prediction_vs_actual(y_true, y_pred, "My Model")
evaluator.plot_residuals(y_true, y_pred, "My Model")
evaluator.plot_learning_curve(model, X, y)

# 特征重要性
evaluator.plot_feature_importance(importances, feature_names)

# 模型比较
results = evaluator.compare_models(model_results)

# 生成完整报告
report = evaluator.generate_evaluation_report(
    y_true, y_pred, "My Model",
    feature_names, feature_importance
)

# 导出HTML报告
evaluator.export_report_to_html(report, "model_report.html")
```

## 工作流程示例

### 完整的机器学习流程

```python
from nsgablack.ml import (
    ModelManager, CheckpointManager,
    DataProcessor, ModelEvaluator
)

# 1. 初始化组件
model_mgr = ModelManager("models")
checkpoint_mgr = CheckpointManager("checkpoints")
data_processor = DataProcessor()
evaluator = ModelEvaluator()

# 2. 数据预处理
data_processor.fit_scaler(X_train, method='standard')
X_train_scaled = data_processor.transform_scaler(X_train)
X_test_scaled = data_processor.transform_scaler(X_test)

# 3. 模型训练
model_mgr.create_model('random_forest', 'rf_model')
model_mgr.train_model('rf_model', X_train_scaled, y_train)

# 4. 模型评估
y_pred = model_mgr.predict('rf_model', X_test_scaled)
metrics = evaluator.calculate_metrics(y_test, y_pred)

# 5. 可视化
evaluator.plot_prediction_vs_actual(y_test, y_pred, "Random Forest")
evaluator.plot_residuals(y_test, y_pred, "Random Forest")

# 6. 保存结果
checkpoint_mgr.save_checkpoint({
    'model': model_mgr.models['rf_model'],
    'metrics': metrics,
    'data_processor': data_processor
}, "rf_final_checkpoint")

# 7. 生成报告
report = evaluator.generate_evaluation_report(
    y_test, y_pred, "Random Forest",
    feature_names, model_mgr.models['rf_model'].feature_importances_
)
evaluator.export_report_to_html(report, "rf_report.html")
```

### 增量学习流程

```python
# 初始训练
model_mgr.train_model('online_model', X_initial, y_initial)

# 持续学习循环
for new_data_batch in data_stream:
    # 增量训练
    result = model_mgr.incremental_train(
        'online_model',
        new_data_batch['X'],
        new_data_batch['y']
    )

    # 检查性能变化
    if result['performance_change']['r2_change'] < -0.1:
        print("模型性能显著下降，考虑重新训练")
        # 可以触发完全重新训练或其他应对策略
```

## 高级特性

### 1. 自适应训练策略

```python
# 根据数据特性自动调整训练策略
trainer = AdaptiveTrainer(
    model_type='auto',  # 自动选择模型类型
    feature_selection='auto',  # 自动特征选择
    scaling='auto'  # 自动数据缩放
)
```

### 2. 分布式训练支持

```python
# 分布式模型训练
distributed_manager = DistributedModelManager(
    n_workers=4,
    backend='multiprocessing'  # 或 'ray', 'dask'
)
```

### 3. 实验管理

```python
# 实验跟踪和比较
experiment = MLExperiment(
    name="production_scheduling_v1",
    tracking_uri="mlruns"
)

experiment.log_params({
    'model_type': 'random_forest',
    'n_estimators': 200,
    'max_depth': 30
})

experiment.log_metrics(metrics)
experiment.log_model(model_mgr.models['rf_model'])
```

## 最佳实践

### 1. 模型选择指南

- **随机森林**：通用性强，不易过拟合，适合中小型数据集
- **梯度提升**：性能通常更好，但需要更多调参
- **集成模型**：结合多个模型，提高稳定性

### 2. 数据预处理建议

- 始终使用训练集的统计信息处理测试集
- 处理缺失值时考虑业务含义
- 特征选择时结合领域知识

### 3. 检查点策略

- 训练大模型时使用自动备份
- 保存足够的中间状态
- 定期清理旧检查点

### 4. 评估策略

- 使用交叉验证得到稳定估计
- 关注多个指标（R²、RMSE、MAE）
- 可视化有助于发现问题

## 性能优化

### 1. 内存优化

```python
# 使用增量学习处理大数据集
for batch in data_batches:
    model_mgr.incremental_train('model', batch['X'], batch['y'])
```

### 2. 计算优化

```python
# 并行模型训练
model_mgr = ModelManager(
    n_jobs=-1,  # 使用所有CPU核心
    memory_constrained=True
)
```

### 3. 存储优化

```python
# 压缩检查点
checkpoint_mgr = CheckpointManager(
    compression=True,
    max_file_size="100MB"
)
```

## 扩展指南

### 添加新模型类型

```python
class MyModelWrapper(BaseModelWrapper):
    def create_model(self):
        return MyCustomModel(**self.model_params)

    def get_model_name(self):
        return "MyCustomModel"

# 注册到模型管理器
ModelManager.register_model_type('my_model', MyModelWrapper)
```

### 添加新的评估指标

```python
def custom_metric(y_true, y_pred):
    """自定义评估指标"""
    return np.mean(np.abs(y_true - y_pred) / (y_true + 1e-8))

# 使用自定义指标
metrics = evaluator.calculate_metrics(
    y_true, y_pred,
    metrics=['mse', 'r2', 'custom_metric']
)
```

## 常见问题

### Q: 如何处理多目标问题？

A: 为每个目标训练独立的模型，或使用复合代理模型。

### Q: 如何选择最佳模型？

A: 使用 `get_best_model()`方法，或通过交叉验证比较。

### Q: 如何处理大数据集？

A: 使用增量学习、数据分块、或采样策略。

### Q: 如何实现早停？

A: 在训练循环中监控验证集性能。

## 版本历史

- **v2.0**: 完整重构，模块化设计

  - 添加增量学习支持
  - 增强检查点管理
  - 改进评估工具
- **v1.0**: 初始版本

  - 基础模型管理
  - 简单评估功能
    - [NSGABlack主项目](https://github.com/your-org/nsgablack)
