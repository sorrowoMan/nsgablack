"""
代理模型管理器

整合代理模型、特征提取、策略选择等功能的管理器。
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from ..core.base import BlackBoxProblem
from .base import BaseSurrogateModel, CompositeSurrogateModel
from .features import FeatureExtractor, FeatureExtractorFactory
from .strategies import SurrogateStrategy, SurrogateStrategyFactory
from ..ml import ModelManager, DataProcessor


class SurrogateManager:
    """代理模型管理器

    提供统一的接口来管理代理模型的整个生命周期。
    """

    def __init__(
        self,
        problem: BlackBoxProblem,
        model_type: str = 'random_forest',
        feature_extractor: Union[str, FeatureExtractor] = 'identity',
        strategy: Union[str, SurrogateStrategy] = 'adaptive',
        **kwargs
    ):
        """
        初始化管理器

        Args:
            problem: 黑盒优化问题
            model_type: 模型类型
            feature_extractor: 特征提取器
            strategy: 代理策略
            **kwargs: 额外参数
        """
        self.problem = problem
        self.dimension = problem.dimension
        self.n_objectives = problem.n_objectives

        # 初始化模型管理器
        self.model_manager = ModelManager(
            model_dir=kwargs.get('model_dir', 'surrogate_models')
        )

        # 创建特征提取器
        if isinstance(feature_extractor, str):
            self.feature_extractor = FeatureExtractorFactory.create_extractor(
                feature_extractor,
                problem,
                **kwargs
            )
        else:
            self.feature_extractor = feature_extractor

        # 创建数据处理器
        self.data_processor = DataProcessor()

        # 创建代理模型
        self.surrogate_model = self._create_surrogate_model(model_type, **kwargs)

        # 创建策略
        if isinstance(strategy, str):
            self.strategy = SurrogateStrategyFactory.create_strategy(
                strategy,
                self.surrogate_model,
                **kwargs
            )
        else:
            self.strategy = strategy

        # 配置
        self.config = {
            'model_type': model_type,
            'feature_extractor': feature_extractor,
            'strategy': strategy,
            'auto_save': kwargs.get('auto_save', True),
            'save_interval': kwargs.get('save_interval', 50),
            'max_cache_size': kwargs.get('max_cache_size', 10000),
            **kwargs
        }

        # 缓存
        self.evaluation_cache = {}
        self.prediction_cache = {}

        # 统计
        self.stats = {
            'true_evaluations': 0,
            'surrogate_evaluations': 0,
            'cache_hits': 0,
            'model_updates': 0
        }

    def _create_surrogate_model(self, model_type: str, **kwargs) -> BaseSurrogateModel:
        """创建代理模型"""
        if self.n_objectives > 1:
            # 多目标：使用复合模型
            surrogate = CompositeSurrogateModel(self.problem, **kwargs)
        else:
            # 单目标：创建特定模型
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.gaussian_process import GaussianProcessRegressor

            if model_type == 'random_forest':
                surrogate = SklearnSurrogate(
                    RandomForestRegressor(n_estimators=100, random_state=42),
                    problem=self.problem,
                    **kwargs
                )
            elif model_type == 'gaussian_process':
                surrogate = SklearnSurrogate(
                    GaussianProcessRegressor(normalize_y=True),
                    problem=self.problem,
                    **kwargs
                )
            else:
                # 默认使用包装的模型管理器
                surrogate = ManagerSurrogate(
                    self.model_manager,
                    model_type,
                    self.problem,
                    **kwargs
                )

        return surrogate

    def evaluate(self, x: np.ndarray, use_cache: bool = True) -> np.ndarray:
        """
        评估解

        Args:
            x: 解向量
            use_cache: 是否使用缓存

        Returns:
            目标值
        """
        # 转换为合适的格式
        if x.ndim == 1:
            x = x.reshape(1, -1)

        # 检查缓存
        if use_cache:
            cache_key = tuple(x.flatten())
            if cache_key in self.evaluation_cache:
                self.stats['cache_hits'] += 1
                return self.evaluation_cache[cache_key]

        # 决定是否使用代理模型
        if self.strategy.should_evaluate(x):
            # 真实评估
            result = self.problem.evaluate(x)
            self.stats['true_evaluations'] += 1

            # 添加到训练数据
            self.add_training_data(x, result)
        else:
            # 使用代理模型
            result = self.surrogate_model.evaluate(x)
            self.stats['surrogate_evaluations'] += 1

        # 缓存结果
        if use_cache:
            cache_key = tuple(x.flatten())
            self.evaluation_cache[cache_key] = result

            # 限制缓存大小
            if len(self.evaluation_cache) > self.config['max_cache_size']:
                # 删除最旧的条目
                oldest_key = next(iter(self.evaluation_cache))
                del self.evaluation_cache[oldest_key]

        return result

    def add_training_data(self, X: np.ndarray, y: np.ndarray):
        """
        添加训练数据

        Args:
            X: 输入特征
            y: 目标值
        """
        # 特征提取
        if self.feature_extractor:
            X_features = self.feature_extractor.extract(X)
        else:
            X_features = X

        # 添加到代理模型
        self.surrogate_model.add_samples(X_features, y)

        # 检查是否需要重新训练
        if len(self.surrogate_model.X_train) % self.config['save_interval'] == 0:
            self.update_surrogate()

    def update_surrogate(self):
        """更新代理模型"""
        if len(self.surrogate_model.X_train) > 0:
            X = np.array(self.surrogate_model.X_train)
            y = np.array(self.surrogate_model.y_train)

            # 数据预处理
            if len(self.surrogate_model.X_train) > 10:
                self.data_processor.fit_scaler(X)
                X = self.data_processor.transform_scaler(X)

            # 训练模型
            self.surrogate_model.fit(X, y)
            self.stats['model_updates'] += 1

            # 自动保存
            if self.config['auto_save']:
                self.save_model()

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测目标值

        Args:
            X: 输入特征

        Returns:
            预测值
        """
        # 特征提取
        if self.feature_extractor:
            X_features = self.feature_extractor.extract(X)
        else:
            X_features = X

        # 数据预处理
        if hasattr(self.surrogate_model, 'X_train') and len(self.surrogate_model.X_train) > 0:
            X_features = self.data_processor.transform_scaler(X_features)

        # 预测
        return self.surrogate_model.predict(X_features)

    def get_uncertainty(self, X: np.ndarray) -> np.ndarray:
        """
        获取预测不确定性

        Args:
            X: 输入特征

        Returns:
            不确定性
        """
        if hasattr(self.surrogate_model, 'predict_uncertainty'):
            # 特征提取
            if self.feature_extractor:
                X_features = self.feature_extractor.extract(X)
            else:
                X_features = X

            # 预测不确定性
            _, uncertainty = self.surrogate_model.predict_uncertainty(X_features)
            return uncertainty
        else:
            # 默认不确定性
            return np.ones((len(X), 1)) * 0.1

    def select_next_evaluations(
        self,
        candidates: np.ndarray,
        n_evaluations: int
    ) -> np.ndarray:
        """
        选择下一个要评估的候选解

        Args:
            candidates: 候选解
            n_evaluations: 评估次数

        Returns:
            选中的解
        """
        return self.strategy.select_next_samples(candidates, n_evaluations)

    def get_model_quality(self) -> Dict[str, float]:
        """
        获取模型质量指标

        Returns:
            质量指标
        """
        if len(self.surrogate_model.X_train) == 0:
            return {'r2': 0.0, 'rmse': float('inf')}

        # 使用交叉验证评估
        from sklearn.model_selection import cross_val_score
        from sklearn.metrics import make_scorer, mean_squared_error
        from sklearn.ensemble import RandomForestRegressor

        X = np.array(self.surrogate_model.X_train)
        y = np.array(self.surrogate_model.y_train)

        if len(X) < 10:
            return {'r2': 0.0, 'rmse': float('inf')}

        # 简单的评估
        if self.n_objectives == 1:
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            scores = cross_val_score(model, X, y.ravel(), cv=3, scoring='r2')
            return {
                'r2': np.mean(scores),
                'rmse': np.sqrt(mean_squared_error(y, model.fit(X, y).predict(X)))
            }
        else:
            # 多目标：返回每个目标的指标
            metrics = {}
            for i in range(self.n_objectives):
                y_i = y[:, i]
                model = RandomForestRegressor(n_estimators=50, random_state=42)
                scores = cross_val_score(model, X, y_i, cv=3, scoring='r2')
                metrics[f'r2_obj_{i}'] = np.mean(scores)
                metrics[f'rmse_obj_{i}'] = np.sqrt(
                    mean_squared_error(y_i, model.fit(X, y_i).predict(X))
                )
            return metrics

    def save_model(self, filepath: Optional[str] = None):
        """
        保存模型

        Args:
            filepath: 保存路径
        """
        import pickle

        if filepath is None:
            filepath = f"surrogate_model_{self.config['model_type']}.pkl"

        model_data = {
            'surrogate_model': self.surrogate_model,
            'feature_extractor': self.feature_extractor,
            'data_processor': self.data_processor,
            'config': self.config,
            'stats': self.stats,
            'cache': self.evaluation_cache
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    def load_model(self, filepath: str):
        """
        加载模型

        Args:
            filepath: 模型路径
        """
        import pickle

        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.surrogate_model = model_data['surrogate_model']
        self.feature_extractor = model_data['feature_extractor']
        self.data_processor = model_data['data_processor']
        self.config = model_data['config']
        self.stats = model_data['stats']
        self.evaluation_cache = model_data.get('cache', {})

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态

        Returns:
            状态信息
        """
        return {
            'n_training_samples': len(self.surrogate_model.X_train),
            'true_evaluations': self.stats['true_evaluations'],
            'surrogate_evaluations': self.stats['surrogate_evaluations'],
            'cache_hits': self.stats['cache_hits'],
            'model_updates': self.stats['model_updates'],
            'cache_size': len(self.evaluation_cache),
            'is_trained': self.surrogate_model.is_trained,
            'model_quality': self.get_model_quality(),
            'config': self.config
        }


class SklearnSurrogate(BaseSurrogateModel):
    """Sklearn模型的代理包装器"""

    def __init__(self, model, problem: BlackBoxProblem, **kwargs):
        super().__init__(problem, **kwargs)
        self.model = model

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'SklearnSurrogate':
        self.model.fit(X, y)
        self.is_trained = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def predict_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if hasattr(self.model, 'predict') and hasattr(self.model, 'estimators_'):
            # 对于随机森林，使用树预测的方差
            predictions = np.array([tree.predict(X) for tree in self.model.estimators_])
            mean_pred = np.mean(predictions, axis=0)
            std_pred = np.std(predictions, axis=0)
            return mean_pred, std_pred
        else:
            # 默认不确定性
            pred = self.predict(X)
            uncertainty = np.ones_like(pred) * 0.1
            return pred, uncertainty


class ManagerSurrogate(BaseSurrogateModel):
    """使用ModelManager的代理模型"""

    def __init__(
        self,
        model_manager: ModelManager,
        model_type: str,
        problem: BlackBoxProblem,
        **kwargs
    ):
        super().__init__(problem, **kwargs)
        self.model_manager = model_manager
        self.model_type = model_type
        self.model_names = []

        # 为每个目标创建模型
        for i in range(self.n_objectives):
            model_name = f'surrogate_obj_{i}'
            self.model_manager.create_model(model_type, model_name)
            self.model_names.append(model_name)

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'ManagerSurrogate':
        for i, model_name in enumerate(self.model_names):
            if y.shape[1] == 1:
                y_target = y
            else:
                y_target = y[:, i]
            self.model_manager.train_model(model_name, X, y_target)
        self.is_trained = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        predictions = []
        for model_name in self.model_names:
            pred = self.model_manager.predict(model_name, X)
            predictions.append(pred.reshape(-1, 1))
        return np.hstack(predictions)

    def predict_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        # 简单实现：返回预测和固定不确定性
        pred = self.predict(X)
        uncertainty = np.ones_like(pred) * 0.1
        return pred, uncertainty