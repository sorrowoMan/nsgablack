"""
代理模型基类

定义代理模型的核心接口和通用功能。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from ..core.base import BlackBoxProblem
from .utils import get_num_objectives, get_problem_dimension


class BaseSurrogateModel(ABC):
    """代理模型基类

    定义了所有代理模型必须实现的接口。
    """

    def __init__(self, problem: BlackBoxProblem, **kwargs):
        """
        初始化代理模型

        Args:
            problem: 黑盒优化问题
            **kwargs: 额外参数
        """
        self.problem = problem
        self.dimension = get_problem_dimension(problem)
        self.n_objectives = get_num_objectives(problem)

        # 训练数据
        self.X_train = []
        self.y_train = []
        self.evaluation_count = 0
        self.surrogate_evaluation_count = 0

        # 配置
        self.config = {
            'batch_size': kwargs.get('batch_size', 1),
            'max_samples': kwargs.get('max_samples', 1000),
            'validation_ratio': kwargs.get('validation_ratio', 0.2),
            'retrain_interval': kwargs.get('retrain_interval', 50),
            **kwargs
        }

        # 状态
        self.is_trained = False
        self.model = None
        self.feature_extractor = None
        self.scaler = None

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'BaseSurrogateModel':
        """
        训练代理模型

        Args:
            X: 输入特征
            y: 目标值

        Returns:
            self
        """
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测目标值

        Args:
            X: 输入特征

        Returns:
            预测的目标值
        """
        pass

    @abstractmethod
    def predict_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测目标值及其不确定性

        Args:
            X: 输入特征

        Returns:
            (预测值, 不确定性)
        """
        pass

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """
        使用代理模型评估解

        Args:
            x: 解向量

        Returns:
            预测的目标值
        """
        # 转换为二维数组
        if x.ndim == 1:
            x = x.reshape(1, -1)

        # 特征提取
        if self.feature_extractor:
            features = self.feature_extractor.extract(x)
        else:
            features = x

        # 预测
        self.surrogate_evaluation_count += 1
        return self.predict(features)

    def add_samples(self, X: np.ndarray, y: np.ndarray):
        """
        添加训练样本

        Args:
            X: 输入特征
            y: 目标值
        """
        if len(X.shape) == 1:
            X = X.reshape(1, -1)
        if len(y.shape) == 1:
            y = y.reshape(1, -1)

        self.X_train.extend(X.tolist())
        self.y_train.extend(y.tolist())

        # 检查是否需要重新训练
        if len(self.X_train) % self.config['retrain_interval'] == 0:
            self.retrain()

    def retrain(self):
        """重新训练模型"""
        if len(self.X_train) == 0:
            return

        X = np.array(self.X_train)
        y = np.array(self.y_train)

        self.fit(X, y)

    def should_use_surrogate(self, x: np.ndarray) -> bool:
        """
        决定是否使用代理模型

        Args:
            x: 解向量

        Returns:
            是否使用代理模型
        """
        # 简单策略：训练样本超过阈值后使用代理模型
        return len(self.X_train) >= self.config['batch_size']

    def get_uncertainty_based_samples(self, X: np.ndarray, n_samples: int) -> np.ndarray:
        """
        基于不确定性选择样本

        Args:
            X: 候选解
            n_samples: 要选择的样本数

        Returns:
            选中的样本
        """
        # 计算所有样本的不确定性
        _, uncertainties = self.predict_uncertainty(X)

        # 选择不确定性最高的样本
        if len(X) <= n_samples:
            return X
        else:
            # 选择不确定性最高的n_samples个
            indices = np.argsort(uncertainties)[-n_samples:]
            return X[indices]

    def get_diverse_samples(self, X: np.ndarray, n_samples: int) -> np.ndarray:
        """
        基于多样性选择样本

        Args:
            X: 候选解
            n_samples: 要选择的样本数

        Returns:
            选中的样本
        """
        if len(X) <= n_samples:
            return X

        # 使用聚类或其他方法选择多样化样本
        from sklearn.cluster import KMeans

        if len(X) > n_samples:
            kmeans = KMeans(n_clusters=n_samples, random_state=42)
            kmeans.fit(X)

            # 选择每个簇的中心
            centers = kmeans.cluster_centers_
            return centers

        return X

    def evaluate_batch(self, X: np.ndarray, use_surrogate: bool = None) -> np.ndarray:
        """
        批量评估

        Args:
            X: 解矩阵
            use_surrogate: 是否使用代理模型

        Returns:
            目标值矩阵
        """
        if use_surrogate is None:
            use_surrogate = self.should_use_surrogate(X[0])

        if use_surrogate:
            return self.predict(X)
        else:
            # 使用真实评估
            results = []
            for x in X:
                result = self.problem.evaluate(x)
                results.append(result)
                self.add_samples(x.reshape(1, -1), np.array(result).reshape(1, -1))
            return np.array(results)

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            模型信息字典
        """
        return {
            'type': self.__class__.__name__,
            'dimension': self.dimension,
            'n_objectives': self.n_objectives,
            'n_samples': len(self.X_train),
            'evaluation_count': self.evaluation_count,
            'surrogate_evaluation_count': self.surrogate_evaluation_count,
            'is_trained': self.is_trained,
            'config': self.config
        }


class CompositeSurrogateModel(BaseSurrogateModel):
    """复合代理模型

    组合多个代理模型，例如每个目标一个模型。
    """

    def __init__(self, problem: BlackBoxProblem, model_class=None, **kwargs):
        super().__init__(problem, **kwargs)

        self.model_class = model_class
        self.surrogates = []
        self._initialize_surrogates()

    def _initialize_surrogates(self):
        """初始化子代理模型"""
        for i in range(self.n_objectives):
            if self.model_class:
                surrogate = self.model_class(self.problem, **self.config)
            else:
                # 默认使用代理模型管理器
                from .manager import SurrogateManager
                surrogate = SurrogateManager(self.problem, **self.config)
            self.surrogates.append(surrogate)

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'CompositeSurrogateModel':
        """训练所有子代理模型"""
        for i, surrogate in enumerate(self.surrogates):
            if y.shape[1] == 1:
                y_target = y
            else:
                y_target = y[:, i:i+1]
            surrogate.fit(X, y_target)
        self.is_trained = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """使用所有子代理模型预测"""
        predictions = []
        for surrogate in self.surrogates:
            pred = surrogate.predict(X)
            if pred.ndim == 1:
                pred = pred.reshape(-1, 1)
            predictions.append(pred)
        return np.hstack(predictions)

    def predict_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """预测并返回不确定性"""
        predictions = []
        uncertainties = []
        for surrogate in self.surrogates:
            pred, unc = surrogate.predict_uncertainty(X)
            if pred.ndim == 1:
                pred = pred.reshape(-1, 1)
            if unc.ndim == 1:
                unc = unc.reshape(-1, 1)
            predictions.append(pred)
            uncertainties.append(unc)

        return np.hstack(predictions), np.hstack(uncertainties)
