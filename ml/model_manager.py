#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
机器学习模型管理工具类

提供统一的模型管理接口，包括：
- 模型创建和配置
- 模型训练和预测
- 模型保存和加载
- 增量学习支持
- 多模型集成
"""

import pickle
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.base import BaseEstimator, RegressorMixin


class BaseModelWrapper(ABC):
    """模型包装器基类"""

    def __init__(self, model_params: Dict = None):
        self.model_params = model_params or {}
        self.model = None
        self.is_trained = False

    @abstractmethod
    def create_model(self) -> BaseEstimator:
        """创建模型实例"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """获取模型名称"""
        pass

    def fit(self, X, y):
        """训练模型"""
        if self.model is None:
            self.model = self.create_model()
        self.model.fit(X, y)
        self.is_trained = True
        return self

    def predict(self, X):
        """预测"""
        if not self.is_trained:
            raise ValueError("模型尚未训练")
        return self.model.predict(X)

    def save(self, filepath: str):
        """保存模型"""
        model_data = {
            'model': self.model,
            'model_params': self.model_params,
            'model_name': self.get_model_name(),
            'is_trained': self.is_trained,
            'save_time': datetime.now().isoformat()
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    def load(self, filepath: str):
        """加载模型"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        self.model = model_data['model']
        self.model_params = model_data['model_params']
        self.is_trained = model_data['is_trained']
        return self


class RandomForestWrapper(BaseModelWrapper):
    """随机森林模型包装器"""

    def create_model(self):
        return RandomForestRegressor(
            n_estimators=self.model_params.get('n_estimators', 200),
            max_depth=self.model_params.get('max_depth', 30),
            min_samples_split=self.model_params.get('min_samples_split', 5),
            min_samples_leaf=self.model_params.get('min_samples_leaf', 2),
            n_jobs=self.model_params.get('n_jobs', 1),
            random_state=self.model_params.get('random_state', 42)
        )

    def get_model_name(self) -> str:
        return "RandomForest"


class GradientBoostingWrapper(BaseModelWrapper):
    """梯度提升模型包装器"""

    def create_model(self):
        return GradientBoostingRegressor(
            n_estimators=self.model_params.get('n_estimators', 200),
            learning_rate=self.model_params.get('learning_rate', 0.1),
            max_depth=self.model_params.get('max_depth', 6),
            random_state=self.model_params.get('random_state', 42)
        )

    def get_model_name(self) -> str:
        return "GradientBoosting"


class EnsembleWrapper(BaseModelWrapper):
    """集成模型包装器"""

    def __init__(self, models: List[BaseModelWrapper], voting: str = 'average'):
        self.models = models
        self.voting = voting
        self.ensemble_model = None
        self.is_trained = False

    def create_model(self):
        estimators = [(f"model_{i}", model.model) for i, model in enumerate(self.models)]
        return VotingRegressor(estimators=estimators)

    def get_model_name(self) -> str:
        model_names = [model.get_model_name() for model in self.models]
        return f"Ensemble({' + '.join(model_names)})"

    def fit(self, X, y):
        """训练所有模型和集成模型"""
        # 先训练各个子模型
        for model in self.models:
            model.fit(X, y)

        # 创建并训练集成模型
        self.ensemble_model = self.create_model()
        self.ensemble_model.fit(X, y)
        self.is_trained = True
        return self

    def predict(self, X):
        """使用集成模型预测"""
        if not self.is_trained:
            raise ValueError("集成模型尚未训练")
        return self.ensemble_model.predict(X)


class ModelManager:
    """模型管理器

    统一管理多个模型的生命周期，包括训练、预测、保存、加载等
    """

    def __init__(self, model_dir: str = "models"):
        """
        初始化模型管理器

        Args:
            model_dir: 模型保存目录
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)

        self.models: Dict[str, BaseModelWrapper] = {}
        self.scalers: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict] = {}

    def register_model(self, name: str, model_wrapper: BaseModelWrapper,
                      scaler_name: Optional[str] = None):
        """
        注册模型

        Args:
            name: 模型名称
            model_wrapper: 模型包装器实例
            scaler_name: 关联的数据预处理器名称
        """
        self.models[name] = model_wrapper
        if scaler_name:
            self.scalers[name] = scaler_name

        # 记录元数据
        self.model_metadata[name] = {
            'model_type': model_wrapper.get_model_name(),
            'params': model_wrapper.model_params,
            'scaler': scaler_name,
            'register_time': datetime.now().isoformat()
        }

    def create_model(self, model_type: str, name: Optional[str] = None,
                    params: Dict = None) -> BaseModelWrapper:
        """
        创建并注册模型

        Args:
            model_type: 模型类型 ('random_forest', 'gradient_boosting')
            name: 模型名称（可选）
            params: 模型参数（可选）

        Returns:
            模型包装器实例
        """
        if name is None:
            name = f"{model_type}_{len(self.models)}"

        if model_type.lower() == 'random_forest':
            model = RandomForestWrapper(params)
        elif model_type.lower() == 'gradient_boosting':
            model = GradientBoostingWrapper(params)
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

        self.register_model(name, model)
        return model

    def create_ensemble(self, model_names: List[str], ensemble_name: Optional[str] = None,
                       voting: str = 'average') -> EnsembleWrapper:
        """
        创建集成模型

        Args:
            model_names: 要集成的模型名称列表
            ensemble_name: 集成模型名称（可选）
            voting: 投票策略

        Returns:
            集成模型包装器
        """
        models = [self.models[name] for name in model_names if name in self.models]

        if not models:
            raise ValueError("没有找到可用的模型进行集成")

        if ensemble_name is None:
            ensemble_name = f"ensemble_{len(self.models)}"

        ensemble = EnsembleWrapper(models, voting)
        self.register_model(ensemble_name, ensemble)
        return ensemble

    def train_model(self, model_name: str, X, y, save_training_data: bool = False):
        """
        训练指定模型

        Args:
            model_name: 模型名称
            X: 特征数据
            y: 目标数据
            save_training_data: 是否保存训练数据
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        model = self.models[model_name]

        # 数据预处理
        if model_name in self.scalers:
            scaler_name = self.scalers[model_name]
            if scaler_name in self.scalers:
                scaler = self.scalers[scaler_name]
                X = scaler.transform(X)

        # 训练模型
        model.fit(X, y)

        # 更新元数据
        self.model_metadata[model_name].update({
            'is_trained': True,
            'training_time': datetime.now().isoformat(),
            'training_samples': len(X)
        })

        if save_training_data:
            training_data = {
                'X': X,
                'y': y,
                'model_name': model_name
            }
            training_path = self.model_dir / f"{model_name}_training_data.pkl"
            with open(training_path, 'wb') as f:
                pickle.dump(training_data, f)

    def predict(self, model_name: str, X):
        """
        使用指定模型进行预测

        Args:
            model_name: 模型名称
            X: 特征数据

        Returns:
            预测结果
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        model = self.models[model_name]

        # 数据预处理
        if model_name in self.scalers:
            scaler_name = self.scalers[model_name]
            if scaler_name in self.scalers:
                scaler = self.scalers[scaler_name]
                X = scaler.transform(X)

        return model.predict(X)

    def evaluate_model(self, model_name: str, X_test, y_test) -> Dict[str, float]:
        """
        评估模型性能

        Args:
            model_name: 模型名称
            X_test: 测试特征
            y_test: 测试目标

        Returns:
            评估指标字典
        """
        y_pred = self.predict(model_name, X_test)

        metrics = {
            'mse': mean_squared_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'mae': mean_absolute_error(y_test, y_pred),
            'r2': r2_score(y_test, y_pred)
        }

        return metrics

    def save_model(self, model_name: str, filepath: Optional[str] = None):
        """
        保存模型

        Args:
            model_name: 模型名称
            filepath: 保存路径（可选，默认使用model_dir）
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        if filepath is None:
            filepath = self.model_dir / f"{model_name}.pkl"

        # 保存模型
        model = self.models[model_name]
        model.save(filepath)

        # 保存元数据
        metadata_path = self.model_dir / f"{model_name}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.model_metadata[model_name], f, indent=2, ensure_ascii=False)

    def load_model(self, filepath: str, model_name: Optional[str] = None):
        """
        加载模型

        Args:
            filepath: 模型文件路径
            model_name: 注册名称（可选）
        """
        # 加载模型
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        # 根据模型类型创建包装器
        model_type = model_data['model_name']
        if model_type == "RandomForest":
            wrapper = RandomForestWrapper(model_data['model_params'])
        elif model_type == "GradientBoosting":
            wrapper = GradientBoostingWrapper(model_data['model_params'])
        else:
            raise ValueError(f"未知的模型类型: {model_type}")

        wrapper.model = model_data['model']
        wrapper.is_trained = model_data['is_trained']

        # 注册模型
        if model_name is None:
            model_name = Path(filepath).stem
        self.register_model(model_name, wrapper)

        # 加载元数据
        metadata_path = Path(filepath).with_suffix('_metadata.json')
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            self.model_metadata[model_name] = metadata

    def list_models(self) -> pd.DataFrame:
        """
        列出所有模型及其元数据

        Returns:
            模型信息DataFrame
        """
        data = []
        for name, metadata in self.model_metadata.items():
            data.append({
                'name': name,
                'type': metadata['model_type'],
                'trained': metadata.get('is_trained', False),
                'training_time': metadata.get('training_time', ''),
                'samples': metadata.get('training_samples', 0)
            })
        return pd.DataFrame(data)

    def get_best_model(self, metric: str = 'r2', X_test=None, y_test=None) -> str:
        """
        获取性能最好的模型

        Args:
            metric: 评估指标 ('r2', 'mse', 'mae')
            X_test: 测试数据（可选）
            y_test: 测试标签（可选）

        Returns:
            最佳模型名称
        """
        if X_test is not None and y_test is not None:
            # 评估所有模型
            scores = {}
            for name in self.models:
                if self.models[name].is_trained:
                    metrics = self.evaluate_model(name, X_test, y_test)
                    scores[name] = metrics[metric]
        else:
            # 使用元数据中的信息
            scores = {}
            for name, metadata in self.model_metadata.items():
                if metadata.get('is_trained', False):
                    # 这里可以根据元数据中的其他信息判断
                    # 暂时使用注册时间作为默认排序
                    scores[name] = 0

        # 根据指标选择最佳模型
        if metric == 'r2':
            best_model = max(scores, key=scores.get)
        else:
            best_model = min(scores, key=scores.get)

        return best_model

    def incremental_train(self, model_name: str, X_new, y_new,
                          validation_split: float = 0.1,
                          save_intermediate: bool = True) -> Dict[str, float]:
        """
        增量训练现有模型

        Args:
            model_name: 模型名称
            X_new: 新的特征数据
            y_new: 新的目标数据
            validation_split: 验证集比例
            save_intermediate: 是否保存中间结果

        Returns:
            训练指标
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        model = self.models[model_name]
        if not model.is_trained:
            raise ValueError(f"模型尚未训练: {model_name}")

        # 数据预处理
        if model_name in self.scalers:
            scaler_name = self.scalers[model_name]
            if scaler_name in self.scalers:
                scaler = self.scalers[scaler_name]
                X_new = scaler.transform(X_new)

        # 分割验证集
        if validation_split > 0:
            from sklearn.model_selection import train_test_split
            X_train_new, X_val_new, y_train_new, y_val_new = train_test_split(
                X_new, y_new, test_size=validation_split, random_state=42
            )
        else:
            X_train_new, y_train_new = X_new, y_new
            X_val_new, y_val_new = None, None

        # 记录训练前的性能
        if X_val_new is not None and y_val_new is not None:
            metrics_before = self.evaluate_model(model_name, X_val_new, y_val_new)
        else:
            metrics_before = {}

        # 增量训练（对于不支持增量学习的模型，重新训练）
        if hasattr(model.model, 'partial_fit'):
            # 支持增量学习的模型
            model.model.partial_fit(X_train_new, y_train_new)
        else:
            # 不支持增量学习的模型，需要重新训练
            # 这里需要获取历史数据，简化处理为在新数据上重新训练
            model.fit(X_train_new, y_train_new)

        # 评估训练后的性能
        if X_val_new is not None and y_val_new is not None:
            metrics_after = self.evaluate_model(model_name, X_val_new, y_val_new)
        else:
            metrics_after = {}

        # 更新元数据
        current_samples = self.model_metadata[model_name].get('training_samples', 0)
        self.model_metadata[model_name].update({
            'is_trained': True,
            'last_incremental_training': datetime.now().isoformat(),
            'training_samples': current_samples + len(X_new),
            'incremental_training_count': self.model_metadata[model_name].get('incremental_training_count', 0) + 1
        })

        # 保存模型
        if save_intermediate:
            self.save_model(model_name)

        # 计算性能变化
        performance_change = {}
        for metric in metrics_before:
            if metric in metrics_after:
                performance_change[f'{metric}_change'] = metrics_after[metric] - metrics_before[metric]

        return {
            'metrics_before': metrics_before,
            'metrics_after': metrics_after,
            'performance_change': performance_change,
            'new_samples': len(X_new),
            'total_samples': current_samples + len(X_new)
        }

    def periodic_retrain(self, X_data_pool: List[np.ndarray],
                        y_data_pool: List[np.ndarray],
                        model_name: str,
                        retrain_interval: int = 100,
                        min_samples: int = 50,
                        performance_threshold: float = 0.05) -> List[Dict]:
        """
        周期性重新训练模型

        Args:
            X_data_pool: 数据池（特征数据列表）
            y_data_pool: 数据池（目标数据列表）
            model_name: 模型名称
            retrain_interval: 重新训练间隔（样本数）
            min_samples: 最小样本数
            performance_threshold: 性能下降阈值

        Returns:
            训练历史记录
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        training_history = []
        accumulated_X = []
        accumulated_y = []
        last_performance = None

        # 加载已有数据（如果有）
        if self.models[model_name].is_trained:
            # 尝试从保存的训练数据加载
            training_data_path = self.model_dir / f"{model_name}_training_data.pkl"
            if training_data_path.exists():
                with open(training_data_path, 'rb') as f:
                    saved_data = pickle.load(f)
                    accumulated_X = list(saved_data['X'])
                    accumulated_y = list(saved_data['y'])

        # 处理数据池
        for X_batch, y_batch in zip(X_data_pool, y_data_pool):
            accumulated_X.extend(X_batch)
            accumulated_y.extend(y_batch)

            # 检查是否需要重新训练
            if len(accumulated_X) >= min_samples and len(accumulated_X) % retrain_interval == 0:
                print(f"周期性重新训练: {len(accumulated_X)} 样本")

                # 执行重新训练
                X_array = np.array(accumulated_X)
                y_array = np.array(accumulated_y)

                # 评估当前性能
                if last_performance is not None:
                    # 这里应该使用验证集评估，简化处理
                    current_performance = {'r2': 0.5}  # 占位符
                    performance_drop = last_performance.get('r2', 0) - current_performance.get('r2', 0)
                else:
                    performance_drop = 0

                # 如果性能下降超过阈值或首次训练
                if performance_drop > performance_threshold or last_performance is None:
                    # 分割数据
                    from sklearn.model_selection import train_test_split
                    X_train, X_val, y_train, y_val = train_test_split(
                        X_array, y_array, test_size=0.2, random_state=42
                    )

                    # 数据预处理
                    if model_name in self.scalers:
                        scaler_name = self.scalers[model_name]
                        if scaler_name in self.scalers:
                            scaler = self.scalers[scaler_name]
                            X_train = scaler.transform(X_train)
                            X_val = scaler.transform(X_val)

                    # 重新训练模型
                    self.models[model_name].fit(X_train, y_train)

                    # 评估性能
                    val_metrics = self.evaluate_model(model_name, X_val, y_val)
                    last_performance = val_metrics

                    # 保存模型
                    self.save_model(model_name)

                    # 记录训练历史
                    training_record = {
                        'timestamp': datetime.now().isoformat(),
                        'samples_used': len(accumulated_X),
                        'metrics': val_metrics,
                        'performance_drop': performance_drop,
                        'retrain_reason': 'performance_drop' if performance_drop > performance_threshold else 'scheduled'
                    }
                    training_history.append(training_record)

                    print(f"重新训练完成 - R²: {val_metrics['r2']:.4f}")

        return training_history

    def create_ensemble_from_checkpoints(self, model_name_prefix: str,
                                        checkpoint_names: List[str],
                                        ensemble_name: Optional[str] = None):
        """
        从检查点创建集成模型

        Args:
            model_name_prefix: 模型名称前缀
            checkpoint_names: 检查点名称列表
            ensemble_name: 集成模型名称

        Returns:
            集成模型名称
        """
        if ensemble_name is None:
            ensemble_name = f"{model_name_prefix}_ensemble_from_checkpoints"

        # 临时加载检查点模型
        temp_models = []
        for checkpoint_name in checkpoint_names:
            # 创建临时模型名称
            temp_model_name = f"temp_{checkpoint_name}"

            # 这里需要实现从检查点加载模型的逻辑
            # 简化处理，假设检查点包含完整的模型
            checkpoint_path = self.checkpoint_dir / f"{checkpoint_name}.pkl"
            if checkpoint_path.exists():
                self.load_model(str(checkpoint_path), temp_model_name)
                temp_models.append(temp_model_name)

        if temp_models:
            # 创建集成模型
            ensemble = self.create_ensemble(temp_models, ensemble_name)

            # 清理临时模型
            for temp_model in temp_models:
                if temp_model in self.models:
                    del self.models[temp_model]
                if temp_model in self.model_metadata:
                    del self.model_metadata[temp_model]

            return ensemble_name
        else:
            raise ValueError("没有找到有效的检查点模型")

    def adaptive_training(self, X, y, model_name: str,
                         initial_batch_size: int = 100,
                         growth_factor: float = 1.5,
                         max_batch_size: int = 1000,
                         convergence_threshold: float = 0.001) -> Dict:
        """
        自适应训练 - 动态调整批次大小

        Args:
            X: 特征数据
            y: 目标数据
            model_name: 模型名称
            initial_batch_size: 初始批次大小
            growth_factor: 批次增长因子
            max_batch_size: 最大批次大小
            convergence_threshold: 收敛阈值

        Returns:
            训练结果
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")

        total_samples = len(X)
        batch_size = initial_batch_size
        previous_loss = float('inf')
        training_log = []

        # 随机打乱数据
        indices = np.random.permutation(total_samples)
        X_shuffled = X[indices]
        y_shuffled = y[indices]

        # 分割验证集
        val_size = int(0.2 * total_samples)
        X_val = X_shuffled[-val_size:]
        y_val = y_shuffled[-val_size:]
        X_train = X_shuffled[:-val_size]
        y_train = y_shuffled[:-val_size]

        batch_start = 0
        epoch = 0

        while batch_start < len(X_train):
            batch_end = min(batch_start + batch_size, len(X_train))
            X_batch = X_train[batch_start:batch_end]
            y_batch = y_train[batch_start:batch_end]

            # 训练当前批次
            self.train_model(model_name, X_batch, y_batch, save_training_data=False)

            # 评估性能
            current_metrics = self.evaluate_model(model_name, X_val, y_val)
            current_loss = current_metrics['mse']

            # 记录训练日志
            log_entry = {
                'epoch': epoch,
                'batch_size': batch_size,
                'batch_start': batch_start,
                'batch_end': batch_end,
                'loss': current_loss,
                'metrics': current_metrics
            }
            training_log.append(log_entry)

            # 检查收敛
            loss_improvement = previous_loss - current_loss
            if loss_improvement < convergence_threshold:
                # 性能提升很小，增加批次大小
                batch_size = min(int(batch_size * growth_factor), max_batch_size)
                print(f"Epoch {epoch}: 损失改善 {loss_improvement:.6f} < {convergence_threshold}, 增加批次大小到 {batch_size}")
            else:
                print(f"Epoch {epoch}: 损失改善 {loss_improvement:.6f}")

            previous_loss = current_loss
            batch_start = batch_end
            epoch += 1

        # 最终评估
        final_metrics = self.evaluate_model(model_name, X_val, y_val)

        return {
            'final_metrics': final_metrics,
            'training_log': training_log,
            'total_epochs': epoch,
            'adaptive_batch_sizes': [log['batch_size'] for log in training_log]
        }