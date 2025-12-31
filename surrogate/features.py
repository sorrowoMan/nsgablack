"""
特征提取器

提供可配置的特征提取功能，支持各种特征工程策略。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_regression


class FeatureExtractor(ABC):
    """特征提取器基类"""

    @abstractmethod
    def extract(self, X: np.ndarray) -> np.ndarray:
        """
        提取特征

        Args:
            X: 原始输入

        Returns:
            提取的特征
        """
        pass

    def fit(self, X: np.ndarray) -> 'FeatureExtractor':
        """
        拟合特征提取器

        Args:
            X: 训练数据

        Returns:
            self
        """
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        转换数据

        Args:
            X: 输入数据

        Returns:
            转换后的数据
        """
        return self.extract(X)


class IdentityExtractor(FeatureExtractor):
    """恒等特征提取器 - 不做任何变换"""

    def extract(self, X: np.ndarray) -> np.ndarray:
        return X


class ScalingExtractor(FeatureExtractor):
    """缩放特征提取器"""

    def __init__(self, method: str = 'standard'):
        """
        初始化缩放器

        Args:
            method: 缩放方法 ('standard', 'minmax')
        """
        self.method = method
        if method == 'standard':
            self.scaler = StandardScaler()
        elif method == 'minmax':
            self.scaler = MinMaxScaler()
        else:
            raise ValueError(f"不支持的缩放方法: {method}")

    def fit(self, X: np.ndarray) -> 'ScalingExtractor':
        self.scaler.fit(X)
        return self

    def extract(self, X: np.ndarray) -> np.ndarray:
        return self.scaler.transform(X)


class PCATExtractor(FeatureExtractor):
    """PCA降维特征提取器"""

    def __init__(self, n_components: Optional[int] = None, variance_ratio: float = 0.95):
        """
        初始化PCA提取器

        Args:
            n_components: 降维后的维度
            variance_ratio: 保留的方差比例
        """
        if n_components:
            self.pca = PCA(n_components=n_components)
        else:
            self.pca = PCA(n_components=variance_ratio, svd_solver='full')

    def fit(self, X: np.ndarray) -> 'PCATExtractor':
        self.pca.fit(X)
        return self

    def extract(self, X: np.ndarray) -> np.ndarray:
        return self.pca.transform(X)


class PolynomialExtractor(FeatureExtractor):
    """多项式特征提取器"""

    def __init__(self, degree: int = 2, include_bias: bool = False):
        """
        初始化多项式提取器

        Args:
            degree: 多项式度数
            include_bias: 是否包含偏置项
        """
        from sklearn.preprocessing import PolynomialFeatures
        self.poly = PolynomialFeatures(degree=degree, include_bias=include_bias)

    def fit(self, X: np.ndarray) -> 'PolynomialExtractor':
        self.poly.fit(X)
        return self

    def extract(self, X: np.ndarray) -> np.ndarray:
        return self.poly.transform(X)


class InteractionExtractor(FeatureExtractor):
    """交互特征提取器"""

    def __init__(self, feature_pairs: Optional[List[tuple]] = None):
        """
        初始化交互特征提取器

        Args:
            feature_pairs: 特征对列表，None表示创建所有可能的交互
        """
        self.feature_pairs = feature_pairs
        self.n_features = None

    def fit(self, X: np.ndarray) -> 'InteractionExtractor':
        self.n_features = X.shape[1]

        if self.feature_pairs is None:
            # 创建所有可能的交互对
            self.feature_pairs = [(i, j) for i in range(self.n_features)
                                for j in range(i+1, self.n_features)]

        return self

    def extract(self, X: np.ndarray) -> np.ndarray:
        interaction_features = []

        for i, j in self.feature_pairs:
            # 创建交互特征
            interaction = (X[:, i] * X[:, j]).reshape(-1, 1)
            interaction_features.append(interaction)

        if interaction_features:
            # 将原始特征和交互特征组合
            interactions = np.hstack(interaction_features)
            return np.hstack([X, interactions])
        else:
            return X


class PipelineExtractor(FeatureExtractor):
    """特征提取管道"""

    def __init__(self, extractors: List[FeatureExtractor]):
        """
        初始化管道

        Args:
            extractors: 特征提取器列表
        """
        self.extractors = extractors

    def fit(self, X: np.ndarray) -> 'PipelineExtractor':
        """依次拟合所有提取器"""
        X_current = X
        for extractor in self.extractors:
            extractor.fit(X_current)
            X_current = extractor.transform(X_current)
        return self

    def extract(self, X: np.ndarray) -> np.ndarray:
        """依次应用所有提取器"""
        X_current = X
        for extractor in self.extractors:
            X_current = extractor.extract(X_current)
        return X_current


class ProblemSpecificExtractor(FeatureExtractor):
    """问题特定的特征提取器"""

    def __init__(self, problem_type: str = 'general', **kwargs):
        """
        初始化问题特定提取器

        Args:
            problem_type: 问题类型
            **kwargs: 额外参数
        """
        self.problem_type = problem_type
        self.kwargs = kwargs
        self.problem_stats = {}

    def fit(self, X: np.ndarray) -> 'ProblemSpecificExtractor':
        """计算问题统计信息"""
        self.problem_stats = {
            'mean': np.mean(X, axis=0),
            'std': np.std(X, axis=0),
            'min': np.min(X, axis=0),
            'max': np.max(X, axis=0),
            'range': np.max(X, axis=0) - np.min(X, axis=0)
        }
        return self

    def extract(self, X: np.ndarray) -> np.ndarray:
        """提取问题特定特征"""
        features = [X]

        # 添加统计特征
        if self.problem_type in ['scheduling', 'production']:
            features.extend(self._extract_scheduling_features(X))
        elif self.problem_type in ['design', 'engineering']:
            features.extend(self._extract_design_features(X))
        elif self.problem_type == 'tsp':
            features.extend(self._extract_tsp_features(X))
        else:
            # 通用特征
            features.extend(self._extract_general_features(X))

        return np.hstack(features)

    def _extract_scheduling_features(self, X: np.ndarray) -> List[np.ndarray]:
        """提取调度问题特征"""
        features = []

        # 加载率和密度特征
        density = np.sum(X > 0, axis=1) / X.shape[1]
        features.append(density.reshape(-1, 1))

        # 负载平衡
        load_balance = np.std(X, axis=1)
        features.append(load_balance.reshape(-1, 1))

        # 约束违反度
        violations = np.sum(np.maximum(0, X - 1), axis=1)
        features.append(violations.reshape(-1, 1))

        return features

    def _extract_design_features(self, X: np.ndarray) -> List[np.ndarray]:
        """提取设计问题特征"""
        features = []

        # 材料分布
        material_sum = np.sum(X, axis=1)
        features.append(material_sum.reshape(-1, 1))

        # 对称性
        symmetry = np.mean(np.abs(X - np.flip(X, axis=1)), axis=1)
        features.append(symmetry.reshape(-1, 1))

        return features

    def _extract_tsp_features(self, X: np.ndarray) -> List[np.ndarray]:
        """提取TSP特征"""
        features = []

        # 路径连续性（简化实现）
        continuity = np.sum(np.diff(X, axis=1) ** 2, axis=1)
        features.append(continuity.reshape(-1, 1))

        return features

    def _extract_general_features(self, X: np.ndarray) -> List[np.ndarray]:
        """提取通用特征"""
        features = []

        # 距离到平均
        distance_to_mean = np.linalg.norm(
            X - self.problem_stats['mean'], axis=1
        )
        features.append(distance_to_mean.reshape(-1, 1))

        # 归一化值
        normalized = (X - self.problem_stats['min']) / (
            self.problem_stats['range'] + 1e-8
        )
        features.append(normalized)

        return features


class FeatureExtractorFactory:
    """特征提取器工厂"""

    @staticmethod
    def create_extractor(
        extractor_type: str,
        problem: Any = None,
        **kwargs
    ) -> FeatureExtractor:
        """
        创建特征提取器

        Args:
            extractor_type: 提取器类型
            problem: 问题实例
            **kwargs: 额外参数

        Returns:
            特征提取器实例
        """
        if extractor_type == 'identity':
            return IdentityExtractor()

        elif extractor_type == 'scaling':
            return ScalingExtractor(
                method=kwargs.get('method', 'standard')
            )

        elif extractor_type == 'pca':
            return PCATExtractor(
                n_components=kwargs.get('n_components'),
                variance_ratio=kwargs.get('variance_ratio', 0.95)
            )

        elif extractor_type == 'polynomial':
            return PolynomialExtractor(
                degree=kwargs.get('degree', 2)
            )

        elif extractor_type == 'interaction':
            return InteractionExtractor(
                feature_pairs=kwargs.get('feature_pairs')
            )

        elif extractor_type == 'pipeline':
            # 创建管道
            extractors = []
            for ext_type in kwargs.get('pipeline', []):
                extractors.append(
                    FeatureExtractorFactory.create_extractor(ext_type, problem, **kwargs)
                )
            return PipelineExtractor(extractors)

        elif extractor_type == 'problem_specific':
            # 根据问题类型自动确定
            if hasattr(problem, 'problem_type'):
                problem_type = problem.problem_type
            else:
                problem_type = kwargs.get('problem_type', 'general')
            return ProblemSpecificExtractor(problem_type, **kwargs)

        else:
            raise ValueError(f"未知的特征提取器类型: {extractor_type}")